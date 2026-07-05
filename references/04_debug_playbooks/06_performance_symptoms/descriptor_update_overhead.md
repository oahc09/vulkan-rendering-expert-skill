# Debug Playbook: Descriptor Update Overhead

## 0. 适用范围

### 适用

- CPU 帧时间高，profiling 显示 `vkUpdateDescriptorSets` 占比较大。
- 每帧大量 descriptor set 分配 / 更新 / 绑定。
- Draw call 数多且每个 draw 都切换 descriptor set。
- 动态物体、材质变体多，导致 descriptor 频繁变化。

### 不适用

- GPU 帧时间高（优先看 gpu_frame_time_high.md）。
- Descriptor binding 错误导致渲染错误（优先看 descriptor_binding_error.md）。
- Descriptor pool 耗尽导致分配失败（属于 pool 大小问题，非 update 开销）。

---

## 1. 现象

- CPU profiling 中 `vkUpdateDescriptorSets` 或 `vkAllocateDescriptorSets` 耗时明显。
- 每帧 descriptor update 调用次数随 draw call 数线性增长。
- 材质 / 贴图切换时 CPU 帧时间尖峰。
- 多线程录制 command buffer 时 descriptor update 成为热点。
- RenderDoc 中大量 `vkUpdateDescriptorSets` 调用集中在帧头。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 每帧为每个 draw call 重新分配并更新 descriptor set | `vkUpdateDescriptorSets` 调用次数 ≈ draw call 数；无 per-frame descriptor 缓存 | DescriptorPool / DescriptorSet |
| P0 | 未使用 descriptor template | 代码手写大量 `VkWriteDescriptorSet` 填充；换成 template 后 CPU 时间下降 | Descriptor Update |
| P0 | 未使用 dynamic offset | UBO 中 per-object 数据为每个对象单独分配 buffer 并更新 descriptor | Buffer / Descriptor |
| P1 | Descriptor set 切换过于频繁 | 每个 draw 都 `vkCmdBindDescriptorSets`，未按 material 排序 | Command Buffer / Descriptor |
| P1 | Descriptor pool 策略不当 | 每帧创建新 pool 或 reset pool 代价高 | DescriptorPool |
| P1 | Bindless / descriptor indexing 未启用 | 大量 texture 需要多个 descriptor set | Descriptor / Extension |
| P2 | 多线程更新同一 descriptor pool 产生锁竞争 | CPU 时间集中在锁等待 | DescriptorPool / Thread |

---

## 3. 快速验证路径

1. **统计每帧 `vkUpdateDescriptorSets` 和 `vkCmdBindDescriptorSets` 调用次数**。`[TOOL]`
2. **用 CPU Profiler 采样**：确认 hotspot 在 descriptor update 填充、pool 分配还是绑定。`[TOOL]`
3. **把 per-object descriptor 改为 dynamic offset + 大 UBO**：观察 update 调用次数是否下降。`[TOOL]`
4. **把手写 `VkWriteDescriptorSet` 替换为 `VkDescriptorUpdateTemplate`**：对比 CPU 时间。`[TOOL]`
5. **按 material / shader 排序 draw call**：减少 descriptor set 切换次数。`[TOOL]`
6. **评估是否可启用 `VK_EXT_descriptor_indexing` 走 bindless**：减少 descriptor set 数量。`[SPEC]`

---

## 4. Vulkan 对象链路排查

```text
DescriptorPool
→ DescriptorSet Allocation
→ vkUpdateDescriptorSets / Template
→ vkCmdBindDescriptorSets
→ Draw / Dispatch
```

逐项检查：

- 每帧 descriptor set 分配数量是否可复用（per-frame ring buffer）。`[ENGINE]`
- `vkUpdateDescriptorSets` 调用次数与 draw call 数的比例。`[TOOL]`
- 是否使用 `VkDescriptorUpdateTemplate` 批量更新同类型 descriptor。`[SPEC]`
- UBO / SSBO 是否使用 dynamic offset 减少 descriptor 数量。`[SPEC]`
- Descriptor set layout 是否按更新频率拆分（per-frame / per-material / per-draw）。`[ENGINE]`
- 是否使用 push descriptor 或 push constants 处理高频小数据。`[SPEC]`
- Descriptor pool 的 reset / allocate 策略是否合理（`VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT` 滥用）。`[SPEC]`

---

## 5. 高频根因

1. 每个 draw call 都创建新的 descriptor set 并 update。`[ENGINE]`
2. 手写 `VkWriteDescriptorSet` 数组，未使用 descriptor update template。`[ENGINE]`
3. Per-object 数据为每个对象单独分配 UBO 并单独更新 descriptor，未用 dynamic offset。`[ENGINE]`
4. 所有 descriptor 放在同一个 set，导致微小变化也需重新绑定整个 set。`[ENGINE]`
5. Descriptor pool 每帧创建 / 销毁，未使用 reset 策略。`[ENGINE]`
6. 材质变体多但未按 material 排序，频繁切换 descriptor set。`[ENGINE]`
7. 未使用 `VK_EXT_descriptor_indexing` 或 push descriptor，导致 texture / buffer 绑定路径冗长。`[SPEC]`

---

## 6. 修复方案

### 最小修复

- 对同类型 descriptor 使用 `VkDescriptorUpdateTemplate` 批量更新。`[SPEC]`
- 将 per-object UBO 合并到一个大 buffer，使用 dynamic offset 绑定。`[SPEC]`
- 按更新频率拆分 descriptor set：per-frame、per-material、per-draw。`[ENGINE]`
- 对高频小数据使用 push constants 替代 descriptor update。`[SPEC]`

### 稳定修复

- 建立 per-frame descriptor set ring buffer，每帧 reset pool 后复用。`[ENGINE]`
- 使用 bindless descriptor（`VK_EXT_descriptor_indexing`），把大量 texture / buffer 索引存入 SSBO / push constant。`[SPEC]`
- 按 material / shader / pipeline 排序 draw call，减少 descriptor set 切换。`[ENGINE]`
- 对静态资源建立 descriptor set cache，避免重复 update。`[ENGINE]`

### 工程化修复

- 封装 descriptor allocator / cache / template，限制每帧 update 次数。`[ENGINE]`
- CI 中监控 `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` 调用次数，设定阈值。`[TOOL]`
- 提供 material system 自动生成 descriptor layout 和 update template。`[ENGINE]`
- 对移动端启用 push descriptor（`VK_KHR_push_descriptor`）减少绑定开销。`[ANDROID]`

---

## 7. 回归验证

- [ ] CPU 帧时间中 descriptor update 占比降到可接受范围。
- [ ] 每帧 `vkUpdateDescriptorSets` 调用次数不再随 draw call 线性增长。
- [ ] 渲染结果正确，无 descriptor binding mismatch。
- [ ] 多线程录制 command buffer 时无 descriptor pool 锁竞争。
- [ ] resize / rotation / swapchain recreate 后 descriptor cache 仍一致。
- [ ] 低端设备上 CPU 帧时间稳定。

---

## 8. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_pool.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

## 9. 工具证据

### Validation Layer

- 关注 descriptor pool 相关 VUID（如 `VUID-vkAllocateDescriptorSets-descriptorPool-...`）。`[TOOL]`
- 关注 descriptor binding mismatch 和 layout compatibility 错误。`[TOOL]`
- 关注 `UNASSIGNED-BestPractices-DescriptorType` 等 best practice 建议。`[TOOL]`

### RenderDoc

- 查看 frame capture 中 `vkUpdateDescriptorSets` 和 `vkCmdBindDescriptorSets` 的调用次数。`[TOOL]`
- 查看每个 draw 的 bound descriptor set 数量和切换频率。`[TOOL]`
- 查看 descriptor 引用的资源是否符合预期。`[TOOL]`

### AGI / Android

- 查看 CPU 时间轴中 `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` 耗时。`[TOOL]`
- 对比优化前后 CPU 帧时间。`[TOOL]`
- 检查 descriptor update 是否集中在某一线程造成瓶颈。`[TOOL]`

### logcat

- 搜索 `vkUpdateDescriptorSets`、`descriptor pool` 相关日志。`[ANDROID]`
- 检查是否有 descriptor pool 分配失败的警告。`[ANDROID]`

---

## 10. Android 分支

Android 上 descriptor update 开销对 CPU 帧时间影响显著，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效；surface 重建时不应触发大量 descriptor 更新，除非必要。`[ANDROID]`
2. **Push descriptor 优先**：`VK_KHR_push_descriptor` 在 Android 上广泛支持，适合高频小数据绑定。`[ANDROID]`
3. **Bindless 可行性**：`VK_EXT_descriptor_indexing` 在较新 Adreno / Mali 上支持，可减少大量 texture 的 descriptor set 切换。`[ANDROID]`
4. **Descriptor pool 大小**：Android 设备内存有限，pool 大小和 reset 策略需避免过度分配。`[ANDROID]`
5. **Per-frame ring buffer**：rotation / pause-resume 时确保 per-frame descriptor set 生命周期与 frame fence 对齐，避免旧 frame 仍在使用被 reset 的 descriptor。`[ENGINE]`
6. **Texture streaming**：Android 上贴图流式加载可能频繁更新 descriptor，建议使用 bindless 索引或预留 descriptor slot。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - CPU Profiler 采样结果，确认 `vkUpdateDescriptorSets` / `vkAllocateDescriptorSets` / `vkCmdBindDescriptorSets` 各自占比。
   - 每帧 descriptor update / bind / allocate 调用次数。
   - Descriptor set layout 设计（更新频率分组）。
   - 是否使用 descriptor update template、dynamic offset、push constants、push descriptor。
   - 是否启用 bindless / descriptor indexing。
   - 材质 / draw call 排序策略。
   - RenderDoc capture 中 descriptor 相关调用分布。
   - 设备型号、GPU、驱动版本、Android 版本。
3. 给出最小验证路径：统计 update 次数 → 使用 template → 使用 dynamic offset → 拆分 set → bindless。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 descriptor update template / dynamic offset / push descriptor 规范。
   - `[TOOL]` 若 CPU Profiler 已给出明确 hotspot 证据。
   - `[ENGINE]` 若基于 descriptor 管理架构推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 mobile 扩展或 Surface 生命周期。

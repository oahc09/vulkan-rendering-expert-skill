# Debug Playbook: CPU Overhead Symptoms

> 合并自 2 个原 playbook 文件。

---

## Debug Playbook: CPU Frame Time High

### 0. 适用范围

### 适用

- 每帧 CPU 耗时明显高于目标预算，GPU 时间充足但主线程阻塞导致掉帧。
- `CPU frame time` 与 `GPU frame time` 不同步，CPU 先达到瓶颈。
- 多线程渲染中某条线程长时间占用 CPU。
- 开启 Validation Layer 后帧率显著下降。

### 不适用

- GPU 时间已满导致整体帧率低（优先排查 GPU frame time）。
- 系统级调度或功耗策略导致 CPU 降频。
- 纯网络 / 磁盘 IO 阻塞导致卡顿（应优先排查 IO）。

---

### 1. 现象

- 应用 CPU 帧时间持续高于目标值，GPU busy 较低。
- 主线程在某段代码上长时间停留，渲染线程无法及时提交。
- 开启 Validation Layer 或 debug build 后卡顿明显加剧。
- 场景复杂度增加时 CPU 时间线性上升，GPU 时间变化很小。
- 多线程渲染时某条线程成为串行瓶颈。

---

### 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Draw call 数量过大 | CPU 时间随可见物体数量线性增长；draw call 数 > 数千 | Command Buffer / Pipeline |
| P0 | Validation Layer 开销 | 关闭 validation 后 CPU 时间大幅下降 | Validation Layer |
| P0 | Descriptor 每帧频繁更新 / 分配 | `vkUpdateDescriptorSets` 或 `vkAllocateDescriptorSets` 占用高 | Descriptor Set / Pool |
| P1 | 线程同步开销或单线程录制 | 多线程录制未生效，command buffer 集中在单线程生成 | Command Buffer Pool / Threading |
| P1 | 缓存未命中 / 数据结构低效 | Profiler 显示大量时间在遍历、排序、查找 | Engine Data Structure |
| P1 | 每帧重复创建 pipeline / shader / 资源 | CPU 时间出现规律性尖峰 | Pipeline Cache / Shader Module |
| P2 | 过度使用 `vkDeviceWaitIdle` / `vkQueueWaitIdle` | 主线程频繁等待 GPU idle | Synchronization |

---

### 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | 分类计时：command buffer 录制 / queue 提交 / fence & sync 等待各段 CPU 耗时占比 | 录制占比高 → 检查 2；提交占比高 → 检查 3；等待占比高 → §5-6（主线程 submit 后立即 `vkWaitForFences` 未与下一帧重叠，§2 的 P2 过度使用 wait 假设） | 三段均衡、热点在应用逻辑层 → 检查 5 | — |
| 2 | 每帧 `vkUpdateDescriptorSets` / `vkAllocateDescriptorSets` 计数 vs draw call 数 | 计数 ≈ draw call 数或 CPU 采样显示 descriptor 函数为热点 → §5-1（§2 的 P0 Descriptor 每帧频繁更新 / 分配假设），细化排查转本文件 Descriptor Update Overhead 小节 | 计数正常 → 检查 3 | 正常时排除 §2 的 P0 Descriptor 每帧频繁更新 / 分配假设 |
| 3 | 每帧 draw call 计数（AGI / RenderDoc counter，vs 可见物体数） | 数千以上且随物体数线性增长 → §5-2（§2 的 P0 Draw call 数量过大假设） | 数量正常 → 检查 4 | 正常时排除 §2 的 P0 Draw call 数量过大假设 |
| 4 | 每帧资源创建计数：render loop 中是否出现 `vkCreate*` / `vkAllocate*`、pipeline 编译次数（首帧 vs 稳态） | 每帧重复创建 pipeline / shader / buffer / image → §5-4（§2 的 P1 每帧重复创建 pipeline / shader / 资源假设）；编译尖峰集中在首帧或变体首次出现 → 转 `pipeline_startup_stutter.md` | 无每帧创建、稳态无编译 → 检查 5 | 稳态干净时排除 §2 的 P1 每帧重复创建 pipeline / shader / 资源假设 |
| 5 | 多线程录制结构（trace：线程时间轴）：command buffer pool 是否按线程隔离、渲染线程是否真并行 | 多线程共用同一 command buffer pool → §5-5（§2 的 P1 线程同步开销假设）；单线程录制或线程空等 → §6 Minimal Fix 的 secondary command buffer 多线程条目（§2 的 P1 单线程录制假设） | 并行结构正常 → 检查 6 | 正常时排除 §2 的 P1 线程同步开销或单线程录制假设 |
| 6 | 对照实验：关闭 Validation Layer 对比 CPU 帧时间 | CPU 时间大幅下降 → §5-3（§2 的 P0 Validation Layer 开销假设；release 构建不应开启） | 变化小 → §11 不确定处理（热点多在引擎数据结构，评估 §5-7 场景遍历方向，§2 的 P1 缓存未命中 / 数据结构低效假设） | 变化小时排除 §2 的 P0 Validation Layer 开销假设 |

---

### 4. Vulkan 对象链路排查

```text
Application Logic
→ Scene Culling / Sorting / Submission
→ Descriptor Set Update / Allocation
→ Command Buffer Recording
→ Pipeline Bind / Vertex Buffer Bind
→ Queue Submit
→ Fence / Semaphore Wait
```

逐项检查：

- 每帧 draw call 数量、material 切换次数、pipeline 切换次数。`[HEUR]`
- Descriptor set 是否每帧重新分配，还是复用已在 pool 中分配好的 set。`[ENGINE]`
- Command buffer 录制是否为单线程，pool 是否按线程隔离。`[ENGINE]`
- Validation Layer 是否输出大量 warning / error 导致日志阻塞。`[TOOL]`
- 是否存在每帧创建 buffer / image / pipeline / shader 的行为。`[TOOL]`
- `vkDeviceWaitIdle` 或 `vkQueueWaitIdle` 是否被频繁调用。`[TOOL]`
- 主线程是否在等待 GPU fence 时没有做其他工作。`[ENGINE]`

---

### 5. 高频根因

1. 每帧为每个 draw call 单独分配 descriptor set，导致 pool 分配成为热点。`[ENGINE]`
2. 未使用 multi-draw / indirect draw / instancing，draw call 数量远超必要。`[ENGINE]`
3. Validation Layer 在 debug build 中对每个命令做大量状态检查，CPU 开销显著。`[TOOL]`
4. 每帧重新创建 pipeline 或未启用 pipeline cache。`[ENGINE]`
5. 多线程共用同一个 command buffer pool，导致内部锁竞争。`[SPEC]`
6. 主线程在 submit 后立刻 `vkWaitForFences`，未与下一帧逻辑重叠。`[ENGINE]`
7. 场景管理数据结构低效，每帧遍历全量物体做可见性判断。`[HEUR]`

---

### 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- 关闭非必要的 Validation Layer 扩展或降低验证级别：仅消除 validation 开销这一项，其余 CPU 根因仍在（仅 debug 临时使用，release 不应开启）。`[TOOL]`
- 临时锁定低画质档（减少物体数 / draw call）：CPU 时间回落但提交架构的根因未修，仅用于应急或验证瓶颈归属。`[HEUR]`

### Minimal Fix（针对根因的最小修复）

- 对固定资源使用 persistent descriptor set，避免每帧 `vkAllocateDescriptorSets`。`[SPEC]`
- 把频繁更新的 uniform / dynamic uniform 集中到少量 descriptor set，使用 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`。`[SPEC]`
- 对相同材质 / mesh 的物体启用 instancing 或合并 draw call。`[HEUR]`
- 把单帧内多次 `vkDeviceWaitIdle` 替换为 per-frame fence 等待。`[ENGINE]`
- 引入 multi-draw indirect，把大量相似 draw call 合并为一次 `vkCmdDrawIndirect` / `vkCmdDrawIndexedIndirect`。`[SPEC]`
- 使用 secondary command buffer 多线程录制，每个线程使用独立的 command pool。`[SPEC]`
- 启用并持久化 `VkPipelineCache`，运行期避免重新编译 shader。`[SPEC]`
- 建立渲染 pass 级别的 culling 和 sorting，减少提交到 Vulkan 的物体数量。`[ENGINE]`

### Structural Fix（结构性 / 防复发修复）

- 建立 descriptor set allocator，按 frame-in-flight 复用 set，只在必要时扩容 pool。`[ENGINE]`
- CI 集成 CPU frame time 性能测试，自动回归主线程耗时。`[TOOL]`
- 建立 draw call / descriptor update / pipeline bind 的 per-frame budget 与告警。`[ENGINE]`
- 实现 task-based command buffer 录制系统，自动负载均衡到多个 worker thread。`[ENGINE]`
- 对低端设备启用动态降质策略：减少 LOD、降低 culling 精度、限制每帧最大 draw call。`[ENGINE]`

---

### 7. 回归验证

- [ ] CPU frame time 回到预算内并稳定。
- [ ] 关闭 Validation Layer 与开启时的差距在可接受范围。
- [ ] 多线程录制后 CPU 时间下降且无数据竞争报错。
- [ ] descriptor set 每帧分配次数接近零或仅在扩容时发生。
- [ ] 不再每帧创建 pipeline / shader / buffer / image。
- [ ] resize / rotation / pause-resume 后 CPU 性能策略仍生效。
- [ ] 长时间运行无内存增长或 descriptor pool 耗尽。

---

### 8. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/08_synchronization/fence.md`

---

### 9. 工具证据

### Validation Layer

- 关注 validation 输出数量是否过大，是否每帧重复报告同一 VUID。`[TOOL]`
- 关注 `UNASSIGNED-BestPractices-DrawState-Clear` 等小 draw call 建议。`[TOOL]`
- 关注 descriptor set 是否被重复使用但未被正确更新的警告。`[TOOL]`

### RenderDoc

- 查看 event browser 中 draw call 总数、pipeline 切换次数、descriptor set 切换次数。`[TOOL]`
- 查看每个 draw 的 vertex / index count，判断是否有大量空 draw。`[TOOL]`
- 查看 resource inspector 中是否有大量同名资源每帧创建。`[TOOL]`

### AGI / Android

- 关注 `CPU frame time`、`CPU wait`、`Queue Submit Duration`。`[TOOL]`
- 查看 CPU 时间轴中 `vkQueueSubmit`、`vkUpdateDescriptorSets` 等 API 调用耗时。`[TOOL]`
- 查看多线程渲染是否真正并行，是否存在线程空等。`[TOOL]`

### logcat

- 搜索 `Choreographer: Skipped`、`dropped frames` 等系统掉帧信息。`[ANDROID]`
- 检查是否因 thermal throttling 导致 CPU 降频。`[ANDROID]`
- 检查 `vkQueueSubmit` 附近是否有 ANR 或主线程阻塞痕迹。`[ANDROID]`

---

### 10. Android 分支

Android 上 CPU frame time 受主线程负载、Surface 生命周期和系统调度影响，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且渲染循环未被 pause 阻塞；主线程应只在 `onDrawFrame` 等回调中做轻量工作。`[ANDROID]`
2. **主线程阻塞**：input、生命周期回调、资源加载是否在主线程执行，导致错过 present 时机。`[ANDROID]`
3. **Swapchain 重建同步**：rotation 或 `OUT_OF_DATE` 后，是否在主线程等待 GPU idle 过长时间。`[SPEC]`
4. **后台恢复**：pause / resume 后是否恢复 fence / semaphore 等待节奏，避免首帧 CPU 尖峰。`[ENGINE]`
5. **低端设备限制**：Android 设备 CPU 核心与频率差异大，需设置动态 draw call budget 和 culling 精度。`[ANDROID]`
6. **Thermal throttling**：长时间高负载后 CPU / GPU 可能降频，logcat 中搜索 thermal 相关日志。`[ANDROID]`

---

### 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - CPU Profiler 火焰图或调用栈（主线程和渲染线程）。
   - 每帧 draw call 数、pipeline bind 数、descriptor update 数。
   - Validation Layer 开启与关闭时的 CPU 时间对比。
   - 是否使用多线程 command buffer 录制及 pool 分配策略。
   - 每帧是否创建 / 销毁 Vulkan 对象。
   - 设备型号、CPU、Android 版本、目标刷新率。
3. 给出最小验证路径：关闭 validation → 减少 draw call → 复用 descriptor set → 检查每帧 create/allocate。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 descriptor pool、command pool 或 pipeline cache 规范。
   - `[TOOL]` 若 Profiler / Validation Layer 已给出明确证据。
   - `[ENGINE]` 若基于渲染架构或优化经验推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 Android 主线程、Surface 生命周期或功耗调度。


---

## Debug Playbook: Descriptor Update Overhead

### 0. 适用范围

### 适用

- CPU 帧时间高，profiling 显示 `vkUpdateDescriptorSets` 占比较大。
- 每帧大量 descriptor set 分配 / 更新 / 绑定。
- Draw call 数多且每个 draw 都切换 descriptor set。
- 动态物体、材质变体多，导致 descriptor 频繁变化。

### 不适用

- GPU 帧时间高（优先看 gpu_frame_time_high.md）。
- Descriptor binding 错误导致渲染错误（优先看 descriptor_pipeline_layout_errors.md）。
- Descriptor pool 耗尽导致分配失败（属于 pool 大小问题，非 update 开销）。

---

### 1. 现象

- CPU profiling 中 `vkUpdateDescriptorSets` 或 `vkAllocateDescriptorSets` 耗时明显。
- 每帧 descriptor update 调用次数随 draw call 数线性增长。
- 材质 / 贴图切换时 CPU 帧时间尖峰。
- 多线程录制 command buffer 时 descriptor update 成为热点。
- RenderDoc 中大量 `vkUpdateDescriptorSets` 调用集中在帧头。

---

### 2. 最可能原因排序

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

### 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | update / allocate / bind 调用计数：每帧 `vkUpdateDescriptorSets` / `vkAllocateDescriptorSets` / `vkCmdBindDescriptorSets` 次数 vs draw call 数与材质种类数 | update / allocate ≈ draw call 数（每 draw 重新分配并更新）→ §5-1（§2 的 P0 每帧为每个 draw call 重新分配并更新 descriptor set 假设）；bind 次数远超材质种类数 → §5-6（§2 的 P1 Descriptor set 切换过于频繁假设） | 比例正常、热点在单次调用耗时 → 检查 2 | — |
| 2 | CPU Profiler 采样细分：耗时在 `VkWriteDescriptorSet` 手写填充、pool 分配 / reset、还是 bind 调用 | 手写 `VkWriteDescriptorSet` 数组填充占比高 → §5-2（§2 的 P0 未使用 descriptor template 假设）；pool allocate / reset 占比高 → §5-5（§2 的 P1 Descriptor pool 策略不当假设）；锁等待占比高（多线程）→ §2 的 P2 多线程更新同一 descriptor pool 产生锁竞争假设 | 热点不在 descriptor 路径 → 转本文件 CPU Frame Time High 小节 | — |
| 3 | 按频率分层现状审查：descriptor set layout 是否按 per-frame / per-material / per-draw 拆分、per-object UBO 是否各自单独 buffer 并单独更新 descriptor | 所有 descriptor 放在同一个 set → §5-4（微小变化也重新绑定整个 set）；per-object 单独 UBO + 单独 descriptor → §5-3（§2 的 P0 未使用 dynamic offset 假设） | 已按更新频率分层 → 检查 4 | 已分层时排除 §2 的 P0 未使用 dynamic offset 假设的布局成因 |
| 4 | push constant 可替代项审查：高频小数据（transform / 材质参数）是否仍走 descriptor update | 高频小数据仍在每帧 update descriptor → §6 Minimal Fix 的 push constants 条目（§5-3 路径，§2 的 P0 未使用 dynamic offset 假设相关） | 已用 push constant / 无高频小数据 → 检查 5 | — |
| 5 | 对照实验：把 per-object descriptor 改为 dynamic offset + 大 UBO、手写 write 替换为 `VkDescriptorUpdateTemplate` | update 调用次数与 CPU 时间显著下降 → 印证 §5-3 / §5-2 根因，进 §6 对应修复 | 无改善 → §11 不确定处理（评估 §5-7 的 bindless / push descriptor 方向，§2 的 P1 Bindless / descriptor indexing 未启用假设） | 无改善时排除 §2 的 P0 未使用 descriptor template 与 P0 未使用 dynamic offset 假设 |

---

### 4. Vulkan 对象链路排查

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

### 5. 高频根因

1. 每个 draw call 都创建新的 descriptor set 并 update。`[ENGINE]`
2. 手写 `VkWriteDescriptorSet` 数组，未使用 descriptor update template。`[ENGINE]`
3. Per-object 数据为每个对象单独分配 UBO 并单独更新 descriptor，未用 dynamic offset。`[ENGINE]`
4. 所有 descriptor 放在同一个 set，导致微小变化也需重新绑定整个 set。`[ENGINE]`
5. Descriptor pool 每帧创建 / 销毁，未使用 reset 策略。`[ENGINE]`
6. 材质变体多但未按 material 排序，频繁切换 descriptor set。`[ENGINE]`
7. 未使用 `VK_EXT_descriptor_indexing` 或 push descriptor，导致 texture / buffer 绑定路径冗长。`[SPEC]`

---

### 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- 临时锁定低画质档或减少材质变体，降低 update 调用次数：每 draw 重新分配 / 更新 descriptor 的模式仍在，仅应急。`[HEUR]`
- Descriptor update 开销没有安全的临时绕过：跳过 update 会导致绑定过期资源，必须按根因修复。`[SPEC]`

### Minimal Fix（针对根因的最小修复）

- 对同类型 descriptor 使用 `VkDescriptorUpdateTemplate` 批量更新。`[SPEC]`
- 将 per-object UBO 合并到一个大 buffer，使用 dynamic offset 绑定。`[SPEC]`
- 按更新频率拆分 descriptor set：per-frame、per-material、per-draw。`[ENGINE]`
- 对高频小数据使用 push constants 替代 descriptor update。`[SPEC]`
- 按 material / shader / pipeline 排序 draw call，减少 descriptor set 切换。`[ENGINE]`
- 对静态资源建立 descriptor set cache，避免重复 update。`[ENGINE]`

### Structural Fix（结构性 / 防复发修复）

- 建立 per-frame descriptor set ring buffer，每帧 reset pool 后复用。`[ENGINE]`
- 使用 bindless descriptor（`VK_EXT_descriptor_indexing`），把大量 texture / buffer 索引存入 SSBO / push constant。`[SPEC]`
- 封装 descriptor allocator / cache / template，限制每帧 update 次数。`[ENGINE]`
- CI 中监控 `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` 调用次数，设定阈值。`[TOOL]`
- 提供 material system 自动生成 descriptor layout 和 update template。`[ENGINE]`
- 对移动端启用 push descriptor（`VK_KHR_push_descriptor`）减少绑定开销。`[ANDROID]`

---

### 7. 回归验证

- [ ] CPU 帧时间中 descriptor update 占比降到可接受范围。
- [ ] 每帧 `vkUpdateDescriptorSets` 调用次数不再随 draw call 线性增长。
- [ ] 渲染结果正确，无 descriptor binding mismatch。
- [ ] 多线程录制 command buffer 时无 descriptor pool 锁竞争。
- [ ] resize / rotation / swapchain recreate 后 descriptor cache 仍一致。
- [ ] 低端设备上 CPU 帧时间稳定。

---

### 8. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_pool.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

### 9. 工具证据

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

### 10. Android 分支

Android 上 descriptor update 开销对 CPU 帧时间影响显著，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效；surface 重建时不应触发大量 descriptor 更新，除非必要。`[ANDROID]`
2. **Push descriptor 优先**：`VK_KHR_push_descriptor` 在 Android 上广泛支持，适合高频小数据绑定。`[ANDROID]`
3. **Bindless 可行性**：`VK_EXT_descriptor_indexing` 在较新 Adreno / Mali 上支持，可减少大量 texture 的 descriptor set 切换。`[ANDROID]`
4. **Descriptor pool 大小**：Android 设备内存有限，pool 大小和 reset 策略需避免过度分配。`[ANDROID]`
5. **Per-frame ring buffer**：rotation / pause-resume 时确保 per-frame descriptor set 生命周期与 frame fence 对齐，避免旧 frame 仍在使用被 reset 的 descriptor。`[ENGINE]`
6. **Texture streaming**：Android 上贴图流式加载可能频繁更新 descriptor，建议使用 bindless 索引或预留 descriptor slot。`[ANDROID]`

---

### 11. 不确定时如何处理

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


---

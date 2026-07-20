# Workflow: Optimize Descriptor Updates

## 0. 适用范围

### 适用

- descriptor update 成为 CPU 瓶颈：大量材质、大量 per-object set、每帧大量 `vkUpdateDescriptorSets`。
- 希望通过 descriptor update template、dynamic offset、per-frame set、update-after-bind、push descriptor 降低开销。
- 已有基础 descriptor 管理，需要性能调优。

### 不适用

- descriptor 数量极少（< 100 / 帧），优化收益不明显。
- 渲染框架已自动处理 descriptor 优化，无需手动干预。
- 尚未解决 validation error 或同步 hazard 的工程（先保证正确性）。

---

## 1. 任务目标

降低 descriptor update 的 CPU 开销与 API 调用次数：

```text
Baseline: vkUpdateDescriptorSets per material per frame
→ Template / dynamic offset / per-frame pool / update-after-bind / push descriptor
→ Reduce CPU overhead and command buffer bloat
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 每帧 `vkUpdateDescriptorSets` 调用次数与 descriptor 类型分布。
- 是否支持 `VK_KHR_descriptor_update_template`（Vulkan 1.1 core）。
- 是否支持 `VK_EXT_descriptor_indexing` / update-after-bind（Vulkan 1.2 可选）。
- 是否支持 `VK_KHR_push_descriptor`。
- Descriptor 更新频率：static、per-frame、per-object、per-draw。
- 当前 descriptor pool 分配策略。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已统计 descriptor update 调用次数与 CPU 耗时。
- [ ] 已确认目标扩展 / feature 在物理设备上可用。
- [ ] 基础 descriptor 更新已正确运行，无 validation error。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
VkDescriptorSetLayout
→ VkDescriptorPool
→ [Baseline] vkUpdateDescriptorSets
→ [Optimized] VkDescriptorUpdateTemplate + vkUpdateDescriptorSetWithTemplate
→ [Optimized] Per-frame Descriptor Pool + Pre-allocated Sets
→ [Optimized] VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT
→ [Optimized] vkCmdPushDescriptorSetKHR
→ vkCmdBindDescriptorSets
→ Shader
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| descriptor update template | `VkDescriptorUpdateTemplate` | 批量更新 descriptor | per-layout / per-material | 否 |
| per-frame descriptor pool | `VkDescriptorPool` | 每帧独立分配/reset | per-frame | 否 |
| static descriptor set | `VkDescriptorSet` | 不频繁更新的资源 | scene / material | 否 |
| per-frame descriptor set | `VkDescriptorSet` | 每帧更新 | per-frame | 否 |
| dynamic offset buffer | `VkBuffer` | UBO/SSBO dynamic offset | per-frame | 否 |
| bindless descriptor array | `VkDescriptorSet` + indexing | 大量 texture / buffer | scene | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER_DYNAMIC` | per-frame UBO | Vertex / Fragment |
| set=1,binding=0~N | `COMBINED_IMAGE_SAMPLER` array + update-after-bind | material textures | Fragment |
| set=2,binding=0 | `STORAGE_BUFFER_DYNAMIC` | per-object SSBO | Vertex / Fragment |
| per-draw | `vkCmdPushDescriptorSetKHR` | 1~2 个变化频繁的 image | Fragment |

设计说明：

- static set 在加载时更新一次，后续只 bind [HEUR]。
- per-frame set 使用独立 pool，每帧 `vkResetDescriptorPool` 后重新分配，避免频繁 free/allocate [HEUR]。
- dynamic offset 减少 per-object descriptor set 数量 [HEUR]。
- update-after-bind 适合 bindless texture array，可在 command buffer 录制期间更新 descriptor [SPEC]。
- push descriptor 适合 per-draw 少量变化资源，省一次 `vkUpdateDescriptorSets` + pool 分配 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU `vkUpdateDescriptorSets` / template | descriptor set | CPU 侧更新 | GPU bind 时读取 |
| `vkResetDescriptorPool` | per-frame descriptor sets | 释放前需保证 GPU 不再使用 | 下一帧重新分配 |
| update-after-bind | bindless descriptor array | 更新后需 pipeline barrier / event 保证资源可用 | shader 采样 |
| push descriptor | inline descriptor write | 嵌入 command buffer | 同一 command buffer 内后续 draw |

必须说明：

- per-frame descriptor pool reset 必须在对应 frame fence signaled 后进行，否则 GPU 可能仍在读取旧 descriptor [SPEC]。
- update-after-bind 的 descriptor 更新与 shader 使用之间需要满足 synchronization scope；通常通过 pipeline barrier 或 `VK_ACCESS_SHADER_READ_BIT` 保证 [SPEC]。
- push descriptor 更新随 command buffer 执行，不需要 pool 分配，但只能用于 `VK_PIPELINE_BIND_POINT_GRAPHICS/COMPUTE` [SPEC]。

---

## 8. 实现步骤

1. **统计 baseline**：使用 CPU profiler 或 instrument 记录每帧 `vkUpdateDescriptorSets` 次数、耗时、descriptor 类型分布 [TOOL]。
2. **分类 descriptor 更新频率**：static、per-frame、per-object、per-draw [HEUR]。
3. **使用 dynamic offset**：将 per-object UBO/SSBO 合并到单个 buffer，descriptor 使用 `UNIFORM_BUFFER_DYNAMIC` / `STORAGE_BUFFER_DYNAMIC`，bind 时传 offset [SPEC]。
4. **引入 per-frame descriptor pool**：为每帧创建独立 pool，每帧开始时 `vkResetDescriptorPool`，然后批量分配该帧需要的 set；避免跨帧复用复杂化 [ENGINE]。
5. **预分配 static descriptor set**：对材质、全局资源，在加载时分配并更新，后续只 bind 不 update。
6. **使用 descriptor update template**（Vulkan 1.1+）：
   - 创建 `VkDescriptorUpdateTemplate`，描述每个 descriptor 在更新结构体中的偏移；
   - 每帧填充结构体数组；
   - 调用 `vkUpdateDescriptorSetWithTemplate` 一次性更新 [SPEC]。
7. **启用 update-after-bind**（若需要 bindless）：
   - device creation 启用 `descriptorBindingSampledImageUpdateAfterBind` 等；
   - layout 中对应 binding 设置 `VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT`；
   - 分配 set 时 pool 加 `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT` [SPEC]。
8. **评估 push descriptor**（若支持 `VK_KHR_push_descriptor`）：
   - 对每 draw 变化的 1~2 个 image/buffer，使用 `vkCmdPushDescriptorSetKHR`；
   - 注意 push descriptor 更新随 command buffer，不能跨 command buffer 复用 [SPEC]。
9. **实现 bindless texture array**（可选）：
   - 使用 `VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT` 允许数组中部分元素未使用；
   - shader 中用非动态索引访问数组 [SPEC]。
10. **模板化代码生成**：对每种 descriptor layout 类型生成 update template helper，减少手写重复代码 [ENGINE]。
11. **验证性能收益**：比较优化前后 CPU 耗时、draw call 开销、AGI 中 descriptor 相关指标 [TOOL]。
12. **接入 resize / recreate**：per-frame pool 和 static set 通常不随 swapchain 重建；若 static set 引用 swapchain image view，recreate 后重新 update。
13. **接入销毁路径**：per-frame pool 在 renderer 退出时销毁；static pool / template 按全局生命周期管理。

---

## 9. Android 注意点

- 移动端驱动对 descriptor pool 大小、update template、push descriptor 支持度不同；上线前需在目标 GPU 上验证 [ANDROID]。
- `ANativeWindow` / surface 生命周期影响 per-frame pool reset 时机；`surfaceDestroyed` 后不应再 reset 或 allocate [ANDROID]。
- swapchain recreate 时，若 static descriptor 引用 swapchain image，需在 surface 恢复后重新 update。
- update-after-bind 在旧 Mali/Adreno 上可能性能收益有限，甚至因 driver overhead 增加；需实测 [ANDROID]。
- push descriptor 适合减少 per-draw CPU 开销，但会增大 command buffer size；带宽受限场景需谨慎 [HEUR]。
- AGI / logcat 验证：关注 descriptor update 次数、command buffer 大小、validation error。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkUpdateDescriptorSetWithTemplate-*`、`VUID-VkDescriptorUpdateTemplateCreateInfo-*`、update-after-bind 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：descriptor binding 正确，无 redundant update [TOOL]。
- [ ] 截图 / 数值验证：优化后渲染结果与 baseline 一致。
- [ ] logcat（Android）：无 validation error；可输出每帧 descriptor update 次数。
- [ ] 性能指标：
  - CPU 端 descriptor update 耗时下降（目标：与 baseline 相比 measurable 降低，如下降 30%+ 或达到帧预算）；
  - 每帧 `vkUpdateDescriptorSets` 调用次数符合预期；
  - AGI 中 descriptor cache / command buffer 开销不异常 [TOOL]。
- [ ] resize / pause / resume 后 descriptor 更新策略仍正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Per-frame pool reset 过早**：GPU 还在读取上一帧 descriptor，reset 后导致 device lost [TOOL]。
2. **Update-after-bind 未启用 feature**：device creation 未启用对应 feature，创建 layout 失败 [SPEC]。
3. **Template 偏移计算错误**：`VkDescriptorUpdateTemplateEntry` 的 offset/stride 与结构体布局不匹配，导致 descriptor 写入错位 [SPEC]。
4. **Dynamic offset 未对齐**：offset 不是 `minUniformBufferOffsetAlignment` / `minStorageBufferOffsetAlignment` 整数倍 [SPEC]。
5. **Push descriptor 与 pool descriptor 混用冲突**：同一 pipeline layout 中部分 binding 用 push、部分用 pool，未正确规划 [SPEC]。
6. **Bindless 数组索引越界**：shader 中动态索引超出 `descriptorCount`，触发 validation error [SPEC]。
7. **Static set 引用 swapchain image**：recreate 后未 update，导致 image view 悬垂 [ANDROID]。
8. **过度优化导致复杂度上升**：收益不明显时引入 update-after-bind / bindless，反而增加维护成本 [HEUR]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- 每帧 descriptor update 次数与类型分布。
- 当前 descriptor pool / set 分配策略。
- 支持的扩展列表（descriptor_update_template、descriptor_indexing、push_descriptor）。
- CPU profiler / AGI 抓帧数据。
- Validation Layer 完整报错。
- Android lifecycle 日志。

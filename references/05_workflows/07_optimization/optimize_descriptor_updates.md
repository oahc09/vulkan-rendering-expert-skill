# Workflow: Optimize Descriptor Updates

## 0. 适用范围

### 适用

- descriptor update 成为 CPU 瓶颈：大量材质、大量 per-object set、每帧大量 `vkUpdateDescriptorSets`。
- 希望通过 descriptor update template、dynamic offset、per-frame set、update-after-bind、push descriptor 降低开销。
- 已有基础 descriptor 管理，需要性能调优。

### 不适用

- 尚无可比测量能确认 descriptor 管理为瓶颈；不存在通用“100/帧”收益门槛。
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
普通 set 路径:
VkDescriptorSetLayout → VkDescriptorPool → 分配 VkDescriptorSet
→ vkUpdateDescriptorSets 或 vkUpdateDescriptorSetWithTemplate
→ vkCmdBindDescriptorSets → Shader
（per-frame 管理与 update-after-bind 是需分别验证的可选条件）

Push 路径:
带 PUSH_DESCRIPTOR 标志的 VkDescriptorSetLayout → VkPipelineLayout
→ vkCmdPushDescriptorSetKHR 或 push template 命令 → Shader
（不再对同一 push set slot 调用 vkCmdBindDescriptorSets）
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
- per-frame pool 是候选管理方式；reset 前须所有引用退休。稳定 set 可直接复用，不能为制造优化收益每帧强行重分配 [HEUR]。
- dynamic offset 减少 per-object descriptor set 数量 [HEUR]。
- update-after-bind 需逐 descriptor type 的实际 feature/binding flags 与使用限制；不表示任意 pending 使用中的 descriptor 都可无同步修改 [SPEC]。
- 普通 push 路径不分配应用 descriptor set，但普通 set 可长期复用；实际录制成本与帧时间需同负载对照，不保证省去每 draw 一次分配 [HEUR]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU `vkUpdateDescriptorSets` / template | descriptor set | CPU 侧更新 | GPU bind 时读取 |
| `vkResetDescriptorPool` | per-frame descriptor sets | 释放前需保证 GPU 不再使用 | 下一帧重新分配 |
| update-after-bind | bindless descriptor array | descriptor 更新合法性与其引用资源可见性分别验证 | shader 采样 |
| push descriptor | inline descriptor write | 嵌入 command buffer | 同一 command buffer 内后续 draw |

必须说明：

- pool reset 前须该 pool 分配的所有 set 的全部 submitted 使用完成；单个 frame fence 只有覆盖这些使用时才是充分退休证据 [SPEC]。
- 资源 barrier 不能代替 update-after-bind 的 feature/flag、host 外部同步和 pending descriptor 使用限制；描述符引用资源的数据依赖按真实访问单独验证 [SPEC]。
- push 在录制时更新 descriptor 状态；不需要普通 pool 分配。pipelineBindPoint 的允许值依启用的 graphics/compute/ray-tracing 等能力与命令条件核验，不能一概排除扩展路径 [SPEC]。

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
   - PARTIALLY_BOUND 不要求静态索引；仅允许未被动态使用的 descriptor 不必有效。实际访问的元素仍须有效，动态/非一致索引各自的 feature 和 shader 标注条件独立核验 [SPEC]。
10. **模板化代码生成**：对每种 descriptor layout 类型生成 update template helper，减少手写重复代码 [ENGINE]。
11. **验证性能收益**：比较优化前后 CPU 耗时、draw call 开销、AGI 中 descriptor 相关指标 [TOOL]。
12. **接入 resize / recreate**：per-frame pool 和 static set 通常不随 swapchain 重建；若 static set 引用 swapchain image view，recreate 后重新 update。
13. **接入销毁路径**：per-frame pool 在 renderer 退出时销毁；static pool / template 按全局生命周期管理。

---

## 9. Android 注意点

- 移动端驱动对 descriptor pool 大小、update template、push descriptor 支持度不同；上线前需在目标 GPU 上验证 [ANDROID]。
- surfaceDestroyed 本身不禁止合法 Device 上的 descriptor allocate/reset；先停止依赖该 surface 的呈现工作，并核验 pool 全部使用退休及 swapchain image/view 引用寿命。Device/pool 销毁或访问条件另行判断 [ANDROID]。
- swapchain recreate 时，若 static descriptor 引用 swapchain image，需在 surface 恢复后重新 update。
- update-after-bind 在旧 Mali/Adreno 上可能性能收益有限，甚至因 driver overhead 增加；需实测 [ANDROID]。
- push 是 per-draw 管理候选；录制体积、CPU/提交成本依实现变化，需比较实际可复用 set 基线和完整帧指标 [HEUR]。
- AGI / logcat 验证：关注 descriptor update 次数、command buffer 大小、validation error。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkUpdateDescriptorSetWithTemplate-*`、`VUID-VkDescriptorUpdateTemplateCreateInfo-*`、update-after-bind 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：descriptor binding 正确，无 redundant update [TOOL]。
- [ ] 截图 / 数值验证：优化后渲染结果与 baseline 一致。
- [ ] logcat（Android）：无 validation error；可输出每帧 descriptor update 次数。
- [ ] 性能指标：
  - CPU descriptor 管理成本与完整帧指标满足预登记预算；若项目举例采用“下降30%”目标，它仅是该项目策略，不是通用收益门槛或 Vulkan 要求；
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
5. **Push/set slot 规划错误**：不同 set slot 可分别用普通 set 与 push（满足 layout 限制）；一个 set layout 不能把各 binding 任意分成普通 set/push。还须遵守兼容与 disturbance，而非全局禁止混用 [SPEC]。
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

## C2 实际路径与可撤销策略

固定场景 `cases19/binding_choice` 比较相同两代输入的普通 set 与 KHR push；普通 set 在两次 dispatch 间复用，不以人为重复分配降低基线。完整输出、退休、实际支持/启用与 API 调用计数都是独立门槛；应用 set 分配次数预算不是 driver 内存或 GPU 性能。缺可比完整帧证据时保留基线或返回 `NEEDS_MEASUREMENT`。详细来源、命令、未验范围见 [Push descriptor 有界比较](../../03_api_manual/05_descriptor/push_descriptor.md#delivery19-binding-choice)。

# Workflow: Add Pipeline Layout

## 0. 适用范围

### 适用

- 新增 `VkPipelineLayout`，聚合一个或多个 `VkDescriptorSetLayout` 与 push constant ranges。
- 需要确保 pipeline layout 与 shader reflection 结果一致。
- 需要处理 graphics / compute / ray tracing pipeline 的 layout 兼容性。
- 需要在多个 pipeline 间共享同一 pipeline layout 以减少创建开销。

### 不适用

- 使用 push descriptor（`VK_KHR_push_descriptor`）且不需要传统 pipeline layout 的场景（仍需 layout，但 descriptor 更新方式不同）。
- 完全由引擎自动生成并隐藏 pipeline layout 的渲染框架。
- 不需要自定义 shader resource binding 的简单固定功能渲染。

---

## 1. 任务目标

新增正确的 `VkPipelineLayout`：

```text
Shader Reflection (sets/bindings/push constants)
→ VkDescriptorSetLayout[0..N]
→ VkPushConstantRange[0..M]
→ VkPipelineLayoutCreateInfo
→ VkPipelineLayout
→ VkPipeline / vkCmdBindDescriptorSets / vkCmdPushConstants
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- Shader 中 set/binding 布局与 stage flags。
- Push constant 的 offset、size、stage flags。
- 是否多个 pipeline 共享同一 layout。
- 是否需要兼容 `VK_PIPELINE_LAYOUT_CREATE_INDEPENDENT_SETS_BIT_EXT`（如 descriptor buffer）。
- 当前 descriptor set layout 是否已创建。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] Shader reflection 已输出 set/binding/type/stage/push constant 信息。
- [ ] 所有引用的 descriptor set layout 已创建且有效。
- [ ] Push constant range 不重叠或按 stage 正确区分 [SPEC]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Shader Modules (VS/FS/CS/etc.)
→ Shader Reflection
→ VkDescriptorSetLayout (per set)
→ VkPushConstantRange (per block)
→ VkPipelineLayoutCreateInfo
→ VkPipelineLayout
→ VkGraphicsPipelineCreateInfo / VkComputePipelineCreateInfo
→ VkPipeline
→ Command Buffer (bind descriptor sets / push constants)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| descriptor set layout | `VkDescriptorSetLayout` | 单个 set 的 binding 方案 | 通常全局 | 否 |
| push constant range | `VkPushConstantRange` | shader 中 push constant block 的 offset/size/stage | 与 pipeline layout 同生命周期 | 否 |
| pipeline layout | `VkPipelineLayout` | 聚合 set layouts 与 push constants | 通常全局 | 否 |
| pipeline | `VkPipeline` | 引用 pipeline layout | per-shader-variant | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` | per-frame / per-scene constants | Vertex / Fragment / Compute |
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | diffuse map | Fragment |
| set=1,binding=1 | `COMBINED_IMAGE_SAMPLER` | normal map | Fragment |
| set=2,binding=0 | `STORAGE_BUFFER` | instance data | Vertex / Fragment |
| push constant (offset=0,size=16) | `VkPushConstantRange` | model matrix / draw ID | Vertex |
| push constant (offset=16,size=16) | `VkPushConstantRange` | material params | Fragment |

设计说明：

- Pipeline layout 中的 `pSetLayouts` 数组顺序对应 shader 中的 `set=0,1,2...`；缺失的 set 可填 `VK_NULL_HANDLE` [SPEC]。
- 同一 `set` 在 graphics 与 compute pipeline 中可复用同一 descriptor set layout，但 pipeline layout 整体必须兼容 [SPEC]。
- Push constant 的 `offset` 和 `size` 必须是 4 的倍数；不同 range 可重叠，但 stage 必须不同，否则按 Vulkan 规则冲突 [SPEC]。
- Pipeline layout 创建后不可修改；若 shader 增加 binding，必须重建 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU record | push constants | `vkCmdPushConstants` | shader 同一 command buffer 内读取 |
| CPU update | descriptor set | `vkUpdateDescriptorSets` | `vkCmdBindDescriptorSets` 后 shader 读取 |
| pipeline layout create | pipeline | layout 兼容检查 | `vkCreate*Pipelines` 绑定 |

必须说明：

- `vkCmdPushConstants` 更新的是 command buffer 状态，不是 descriptor；push constant 生命周期仅限于当前 command buffer 的录制 [SPEC]。
- `vkCmdBindDescriptorSets` 的 `layout` 参数必须与当前 pipeline 的 layout 兼容（set layout 相同），否则 validation error [SPEC]。
- Pipeline layout 兼容性的最小要求是：到被使用的最高 set 序号为止，所有 set layout 相同；push constant range 兼容 [SPEC]。
- 不同 pipeline 间切换时，若 pipeline layout 兼容，可只 bind 变化的 descriptor sets；不兼容时必须重新 bind 所有 sets [SPEC]。

---

## 8. 实现步骤

1. **解析 shader reflection**：
   - 收集每个 set 的 bindings：type、descriptorCount、stageFlags；
   - 收集 push constant：offset、size、stageFlags [ENGINE]。
2. **按 set 创建 descriptor set layout**：
   - 每个 set 对应一个 `VkDescriptorSetLayoutCreateInfo`；
   - 若需 update-after-bind，使用 `VkDescriptorSetLayoutBindingFlagsCreateInfo` [SPEC]。
3. **整理 push constant ranges**：
   - 按 stage 合并或拆分；
   - 确保 offset/size 4 字节对齐；
   - 不同 range 在同一 stage 内不能重叠 [SPEC]。
4. **创建 pipeline layout**：
   - 填写 `VkPipelineLayoutCreateInfo`：
     - `setLayoutCount` / `pSetLayouts`；
     - `pushConstantRangeCount` / `pPushConstantRanges` [SPEC]。
   - 调用 `vkCreatePipelineLayout`。
5. **共享 pipeline layout**：
   - 若多个 graphics/compute pipeline 使用相同 set/push 配置，复用同一 layout [HEUR]；
   - 共享 layout 可减少 descriptor set rebind 开销，但会限制单 pipeline 的特殊需求 [HEUR]。
6. **创建 pipeline 时绑定 layout**：
   - `VkGraphicsPipelineCreateInfo::layout` 或 `VkComputePipelineCreateInfo::layout` [SPEC]；
   - pipeline 创建后 layout 不可变更 [SPEC]。
7. **录制 command buffer**：
   - `vkCmdBindPipeline` 后，使用 `vkCmdBindDescriptorSets` 绑定 descriptor sets [SPEC]；
   - 使用 `vkCmdPushConstants` 更新 push constants，stage 与 layout 中定义一致 [SPEC]。
8. **处理 layout 兼容性**：
   - 切换 pipeline 时检查是否兼容；
   - 兼容时只 rebind 变化的 sets；不兼容时重新 bind 0..N [SPEC]。
9. **接入 resize / recreate**：
   - pipeline layout 通常不随 swapchain 重建；
   - 若 recreate 涉及 swapchain image format 变化，pipeline 可能需要重建，但 layout 可保留 [SPEC]。
10. **接入销毁路径**：
    - 先销毁所有引用该 layout 的 pipeline；
    - 再销毁 `VkPipelineLayout`；
    - 最后销毁 descriptor set layouts（若不再被其他 layout 使用）[ENGINE]。

---

## 9. Android 注意点

- Pipeline layout 与 descriptor set layout 创建不依赖 surface，可在 `onCreate` 阶段提前创建；但 push constant 与 descriptor 引用的资源仍受 surface 生命周期影响 [ANDROID]。
- 移动端推荐将 per-frame / per-scene / per-material 资源分到不同 set，减少 pipeline layout 变更频率 [ANDROID]。
- pause / resume 期间通常保留 pipeline layout；只有 swapchain 相关 pipeline 需要重建。
- AGI / logcat 验证：检查 `vkCreatePipelineLayout` 参数、`vkCmdBindDescriptorSets` 的 `layout` 与当前 pipeline 是否一致。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkPipelineLayoutCreateInfo-*`、`VUID-vkCmdBindDescriptorSets-*`、`VUID-vkCmdPushConstants-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：Pipeline State → Pipeline Layout 中可见 set layouts、push constant ranges；Descriptor Sets 中可见绑定资源 [TOOL]。
- [ ] 截图 / 数值验证：shader 读取的 UBO/texture/push constant 数据正确反映在渲染结果中。
- [ ] logcat（Android）：无 validation error；可输出 pipeline layout handle、set layout count、push constant ranges。
- [ ] 性能指标：
  - pipeline layout 切换次数合理；
  - descriptor set rebind 次数最小化；
  - push constant 更新不过度碎片化 [HEUR]。
- [ ] resize / pause / resume 后 pipeline layout 仍有效。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Set layout 顺序错误**：pipeline layout 中 set 顺序与 shader 中 `set=N` 不对应 [SPEC]。
2. **Push constant range 重叠**：同一 stage 内两个 range offset/size 重叠 [SPEC]。
3. **Push constant offset/size 未对齐**：不是 4 的倍数 [SPEC]。
4. **Pipeline layout 与 shader 不匹配**：shader 用了 set=2，但 layout 只提供到 set=1 [TOOL]。
5. **Bind descriptor sets 时 layout 不一致**：当前 pipeline layout 与 `vkCmdBindDescriptorSets` 的 layout 不同 [SPEC]。
6. **Push constant stage 错误**：layout 中 range stage 为 `FRAGMENT_BIT`，但 `vkCmdPushConstants` 用了 `VERTEX_BIT` [SPEC]。
7. **未等待 pipeline 销毁就销毁 layout**：导致 validation error 或 crash [SPEC]。
8. **Android recreate 后 descriptor set 悬垂**：layout 未变但 descriptor 引用的 swapchain view 已释放 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/pipeline_layout_error.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- Shader reflection 输出（set/binding/type/stage/push constants）。
- `VkPipelineLayoutCreateInfo` 完整参数。
- `vkCmdBindDescriptorSets` 与 `vkCmdPushConstants` 调用参数。
- 当前 pipeline 的 layout handle 与绑定 layout handle 是否一致。
- Validation Layer 完整报错。
- Android lifecycle 日志。

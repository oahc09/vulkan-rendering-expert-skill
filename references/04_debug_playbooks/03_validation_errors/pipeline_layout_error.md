# Debug Playbook: Pipeline Layout Error

## 0. 适用范围

### 适用

- Validation Layer 报告 pipeline layout 相关 VUID。
- `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` 返回错误。
- `vkCmdBindDescriptorSets` 报告 layout 不匹配。
- Shader 中声明的 resource 与 pipeline layout 中声明的 set / binding 不一致。

### 不适用

- Shader 编译错误（优先排查 shader_module.md）。
- Descriptor set 内容错误但 layout 本身正确（优先排查 descriptor_binding_error.md）。
- 运行时动态 uniform 更新错误但 layout 匹配。

---

## 1. 现象

- `vkCreateGraphicsPipelines` 返回 `VK_ERROR_INITIALIZATION_FAILED` 或 validation 报错。
- Validation Layer 提示 `VUID-VkGraphicsPipelineCreateInfo-layout-00756` 等 layout 相关 VUID。
- `vkCmdBindDescriptorSets` 报错 `VUID-vkCmdBindDescriptorSets-layout-01996`。
- 某些 descriptor set 绑定后渲染结果异常，但资源本身无问题。
- 同一 shader 在不同 pass 中使用不同 layout 导致错误。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Pipeline layout 与 shader 接口不匹配 | VUID 明确指出 layout 中缺少 shader 使用的 set / binding | Pipeline Layout / Shader Module |
| P0 | Descriptor set layout 与 pipeline layout 中对应 set 不一致 | `vkCmdBindDescriptorSets` 报错 layout 不匹配 | Descriptor Set Layout / Pipeline Layout |
| P1 | Push constant range 与 shader 声明不一致 | validation 报 push constant range 重叠或缺失 | Pipeline Layout / Push Constant |
| P1 | Compute pipeline 与 graphics pipeline layout 混用 | compute shader 访问的 set 在 graphics layout 中未声明 | Pipeline Layout |
| P2 | Pipeline layout 生命周期管理错误 | 已销毁的 layout 仍被 pipeline 引用 | Pipeline Layout Lifecycle |
| P2 | 动态 offset 数量与 layout 中 dynamic descriptor 数量不一致 | `vkCmdBindDescriptorSets` 报 dynamicOffsetCount 错误 | Descriptor Set Layout |

---

## 3. 快速验证路径

1. **读取 Validation Layer 报错的完整 VUID 和 object handle**，定位具体 pipeline 或 descriptor set layout。`[TOOL]`
2. **对比 shader reflection 结果与 pipeline layout 的 set / binding 声明**。`[TOOL]`
3. **检查 `vkCmdBindDescriptorSets` 的 `layout` 参数**：确认是 graphics pipeline 的 layout 还是 compute pipeline 的 layout。`[TOOL]`
4. **检查 push constant range**：确认 stageFlags、offset、size 与 shader 一致。`[TOOL]`
5. **用 `spirv-reflect` 或类似工具导出 shader 接口清单**。`[TOOL]`
6. **临时把 descriptor set 和 push constant 全部去掉**，观察错误是否消失。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Shader Module (SPIR-V)
→ Shader Reflection (set / binding / push constant)
→ Descriptor Set Layout
→ Pipeline Layout
→ Pipeline Create
→ vkCmdBindPipeline
→ vkCmdBindDescriptorSets
→ vkCmdPushConstants
→ Draw / Dispatch
```

逐项检查：

- Shader 中每个 `layout(set=X, binding=Y)` 是否在 pipeline layout 的对应 set 中有匹配的 descriptor set layout。`[SPEC]`
- Descriptor set layout 中的 descriptor type、count、stageFlags 是否与 shader 一致。`[SPEC]`
- Pipeline layout 的 `pSetLayouts` 数组长度是否覆盖 shader 使用的最大 set 编号。`[SPEC]`
- Push constant range 的 `stageFlags` 是否覆盖 shader 中声明 push constant 的 stage，且 offset/size 完全匹配。`[SPEC]`
- Compute pipeline layout 与 graphics pipeline layout 是否独立创建，不能混用。`[SPEC]`
- `vkCmdBindDescriptorSets` 传入的 layout 是否与当前绑定的 graphics / compute pipeline 的 layout 兼容。`[SPEC]`

---

## 5. 高频根因

1. Shader 增加了新的 sampler / uniform buffer 但 pipeline layout 未同步更新。`[ENGINE]`
2. 多个 shader 变体共享同一个 pipeline layout，但部分变体使用了额外的 set / binding。`[ENGINE]`
3. 动态 uniform buffer 数量与 `vkCmdBindDescriptorSets` 的 `pDynamicOffsets` 数量不一致。`[ENGINE]`
4. Push constant 的 stageFlags 只包含 vertex stage，但 fragment shader 也读取了同一 push constant block。`[ENGINE]`
5. 使用 pipeline library 时，linked pipeline 的 layout 与 shader 或 descriptor set layout 不兼容。`[SPEC]`
6. 先销毁了 descriptor set layout 再创建 pipeline，导致 layout 句柄无效。`[SPEC]`
7. Android 上热更新 shader 后未重新生成对应的 pipeline layout。`[ANDROID]`

---

## 6. 修复方案

### 最小修复

- 根据 shader reflection 更新 pipeline layout，确保每个 set / binding 都有对应 descriptor set layout 条目。`[SPEC]`
- 修正 `vkCmdBindDescriptorSets` 的 layout 参数为当前 graphics / compute pipeline 的 layout。`[SPEC]`
- 修正 push constant range 的 `stageFlags`、`offset`、`size` 与 shader 声明一致。`[SPEC]`
- 对动态 descriptor 类型，确保 `vkCmdBindDescriptorSets` 的 `dynamicOffsetCount` 与 layout 中 dynamic descriptor 数量一致。`[SPEC]`

### 稳定修复

- 建立 shader reflection 自动生成 pipeline layout 的流程，避免手动维护 set / binding 映射。`[ENGINE]`
- 对相似 shader 变体使用兼容的 descriptor set layout，但为差异变体创建独立 layout。`[SPEC]`
- 把 push constant 定义放在共享头文件中，确保 CPU 侧 range 与 shader 一致。`[ENGINE]`
- 在创建 pipeline 前验证 shader 接口与 layout 的兼容性，提前报错而非等到 bind 阶段。`[ENGINE]`

### 工程化修复

- CI 中集成 `spirv-reflect` 检查，自动比对 shader 与 pipeline layout 定义。`[TOOL]`
- 对 pipeline layout 做缓存和引用计数，避免重复创建和提前销毁。`[ENGINE]`
- 建立 layout 兼容性测试矩阵，覆盖所有 shader 变体。`[ENGINE]`
- 对 Android 热更新 shader 场景，强制重新生成并验证 pipeline layout。`[ANDROID]`

---

## 7. 回归验证

- [ ] Validation Layer 不再报 pipeline layout 相关 VUID。
- [ ] `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` 成功。
- [ ] `vkCmdBindDescriptorSets` 和 `vkCmdPushConstants` 无报错。
- [ ] 所有 shader 变体都能正确绑定 descriptor 和 push constant。
- [ ] 渲染结果与 shader 预期一致。
- [ ] 修改 shader 接口后自动生成 / 更新 pipeline layout 的流程生效。
- [ ] resize / rotation / shader 热更新后 layout 仍匹配。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`

---

## 9. 工具证据

### Validation Layer

- 关注 `VUID-VkGraphicsPipelineCreateInfo-layout-00756`：layout 与 shader 接口不兼容。`[TOOL]`
- 关注 `VUID-vkCmdBindDescriptorSets-layout-01996`：descriptor set 的 layout 与 command buffer 当前 pipeline layout 不兼容。`[TOOL]`
- 关注 `VUID-vkCmdPushConstants-layout-01796`：push constant range 与 pipeline layout 不匹配。`[TOOL]`
- 关注 `VUID-VkPipelineLayoutCreateInfo-pSetLayouts-00293`：set layout 数组中 null 或重复问题。`[TOOL]`

### RenderDoc

- 查看 pipeline state 中绑定的 pipeline layout 和 descriptor set layout。`[TOOL]`
- 查看 shader reflection 信息中的 set / binding / push constant 声明。`[TOOL]`
- 查看 descriptor 绑定是否与 shader 期望一致。`[TOOL]`

### AGI / Android

- 查看 `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` 的返回码和参数。`[TOOL]`
- 查看 `vkCmdBindDescriptorSets` 报错前后的 pipeline layout 和 descriptor set layout 句柄。`[TOOL]`
- 查看 shader disassembly 中 `OpDecorate` 的 set / binding 声明。`[TOOL]`

### logcat

- 搜索 Validation Layer 输出的 VUID 和 object handle。`[ANDROID]`
- 检查 shader 热更新或资源加载是否导致 layout 不匹配。`[ANDROID]`

---

## 10. Android 分支

Android 上 pipeline layout 错误常与 shader 变体管理和 Surface 生命周期相关，额外检查：

1. **Surface 有效性前提**：确保在 `ANativeWindow` 有效期间创建 pipeline，避免在 surface 重建过程中使用旧 pipeline layout 创建新 pipeline。`[ANDROID]`
2. **Shader 变体管理**：Android 设备支持的扩展不同，某些变体可能使用额外的 set / binding，需为每个变体准备兼容的 pipeline layout。`[ANDROID]`
3. **后台恢复**：pause / resume 后若重新编译 shader，必须同步重新生成 pipeline layout 并重新创建 pipeline。`[ENGINE]`
4. **热更新限制**：Android 上动态加载 shader 后，需在创建 pipeline 前验证新 shader 接口与旧 layout 的兼容性，必要时重建 layout。`[ANDROID]`
5. **Descriptor indexing 扩展**：若使用 `VK_EXT_descriptor_indexing`，确保 layout 中正确声明了 update-after-bind 或 variable descriptor count 标志。`[SPEC]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - Validation Layer 完整报错信息，包括 VUID、object handle、object type。
   - Shader reflection 输出的 set / binding / push constant 清单。
   - Pipeline layout 创建时的 `pSetLayouts` 数组内容。
   - `vkCmdBindDescriptorSets` 调用时的 layout 参数和 descriptor set layout。
   - Push constant range 的 stageFlags、offset、size。
   - 当前是 graphics pipeline 还是 compute pipeline，是否混用 layout。
   - 设备型号、GPU、Android 版本。
3. 给出最小验证路径：关闭 descriptor / push constant → 用最小 shader 创建 pipeline → 逐项加回并验证。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 pipeline layout、descriptor set layout、push constant range 规范。
   - `[TOOL]` 若 Validation Layer / spirv-reflect 已给出明确不匹配证据。
   - `[ENGINE]` 若基于 shader reflection 自动生成 layout 的工程经验推断。
   - `[HEUR]` 若尚未拿到完整 reflection 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 Android shader 热更新或 Surface 生命周期。

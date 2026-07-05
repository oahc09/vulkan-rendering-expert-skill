# API Card: VkPipeline

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipeline` |
| 常用 API | `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` / `vkDestroyPipeline` / `vkCmdBindPipeline` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipeline` 是 Vulkan 中描述“执行状态”的不可变对象，graphics pipeline 决定绘制状态，compute pipeline 决定 dispatch 状态；创建后除动态状态外不可变更。[SPEC]

---

## 2. 所属对象链路

```text
VkPipelineShaderStageCreateInfo[]
→ VkPipelineLayout
→ vkCreateGraphicsPipelines / vkCreateComputePipelines
→ VkPipeline
→ vkCmdBindPipeline（GRAPHICS / COMPUTE）
→ Draw / Dispatch
```

### 上游依赖

- Shader modules 与 stage 信息（graphics / compute）。[SPEC]
- Pipeline layout。[SPEC]
- Graphics pipeline 还需要 render pass / dynamic rendering 格式、顶点输入、光栅化、混合等状态。[SPEC]

### 下游影响

- 决定 draw / dispatch 的执行状态。
- 影响 descriptor set 绑定、动态状态设置、资源访问方式。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipeline`
- `VkGraphicsPipelineCreateInfo`
- `VkComputePipelineCreateInfo`
- `VkPipelineShaderStageCreateInfo`
- `VkPipelineLayout`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateGraphicsPipelines` | 创建 graphics pipeline。[SPEC] |
| `vkCreateComputePipelines` | 创建 compute pipeline。[SPEC] |
| `vkDestroyPipeline` | 销毁 pipeline。[SPEC] |
| `vkCmdBindPipeline` | 在 command buffer 中绑定 pipeline。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_graphics_pipeline_library`、`VK_KHR_ray_tracing_pipeline` 等扩展扩展了 pipeline 概念。

---

## 4. 标准使用流程

```text
准备 shader modules 与 stage 信息
→ 创建 pipeline layout
→ 配置 graphics/compute 状态
→ 指定 render pass / dynamic rendering 格式（graphics）
→ vkCreate*Pipelines（传入 pipeline cache）
→ vkCmdBindPipeline
→ 设置动态状态（如有）
→ vkCmdDraw / vkCmdDispatch
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `stageCount` / `pStages` | graphics 至少 vertex+fragment；compute 只需 compute stage。[SPEC] | 缺少必要 stage。[TOOL] |
| `layout` | 必须是已创建的 pipeline layout。[SPEC] | layout 与 shader 接口不匹配。[TOOL] |
| `pipelineCache` | 传入 cache 以加速创建。[SPEC] | 创建时传入 VK_NULL_HANDLE。[TOOL] |
| `basePipelineHandle` / `basePipelineIndex` | 用于 pipeline derivative，可加速相似 pipeline 创建。[SPEC] | 误用导致依赖错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Shader stage 与 module 是否匹配？
- [ ] Pipeline layout 是否与 shader 的 set/binding 一致？
- [ ] Graphics pipeline 的 render pass / dynamic rendering 格式是否与实际 attachment 一致？
- [ ] 是否传入了 pipeline cache？

### 使用阶段

- [ ] 是否在正确的 command buffer 状态下绑定？（graphics pipeline 在 render pass / dynamic rendering 内）
- [ ] 动态状态是否在 draw 前设置？
- [ ] Descriptor set layout 是否与 pipeline layout 兼容？

### 销毁阶段

- [ ] 是否等待 GPU 不再使用该 pipeline？

---

## 7. 高频错误

1. Pipeline layout 与 shader 的 set/binding 不匹配。[TOOL]
2. Graphics pipeline 的 attachment format 与实际 render pass 不一致。[TOOL]
3. 忘记设置动态状态或动态状态未在 `pDynamicState` 中声明。[TOOL]
4. Compute pipeline 绑定到 graphics bind point 或反之。[TOOL]
5. 在 render pass 外部绑定 graphics pipeline。[TOOL]
6. 销毁 pipeline 时它仍被 in-flight command buffer 引用。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkGraphicsPipelineCreateInfo-*` / `VUID-VkComputePipelineCreateInfo-*`：创建参数合法性。
- `VUID-vkCmdBindPipeline-*`：bind point 与 pipeline 类型匹配。
- `VUID-vkCmdDraw-*`：pipeline 状态、scissor、dynamic state。

### RenderDoc / AGI

- 查看当前绑定的 pipeline 与完整状态。
- 检查 shader stage、descriptor、顶点输入、光栅化、混合状态。

### 日志 / 代码检查

- 检查 pipeline 创建返回值。
- 检查 pipeline cache 是否启用。
- 检查动态状态设置命令。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段或按需延迟创建；建议配合 pipeline cache。[ENGINE]

### 使用时机

- 在 command buffer 中绑定后用于 draw / dispatch。[SPEC]

### 销毁时机

- 确认所有引用它的 command buffer 已完成后销毁。[SPEC]

### in-flight 风险

- Pipeline 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Pipeline 创建本身不需要 fence；销毁需要等待 GPU 完成。[SPEC]

### GPU-GPU 同步

- 切换 pipeline 属于 command buffer 内部顺序执行，无需额外同步。
- Pipeline 写入的 resource 被后续命令读取时需要 barrier。[SPEC]

### 资源访问同步

- Pipeline 本身不直接同步资源；资源同步通过 barrier / subpass dependency 完成。[SPEC]

---

## 11. Android 注意点

- Android 上 pipeline 创建耗时高，必须使用 pipeline cache 并持久化。[ANDROID][ENGINE]
- 避免在启动时一次性创建大量 pipeline，应分帧预热。[ENGINE]
- 横竖屏切换通常不需要重建 pipeline，除非 dynamic rendering 的 image 格式变化。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Pipeline 创建是常见 CPU 瓶颈；使用 cache、library、specialization constants 可减少开销。[ENGINE]
- 减少 pipeline 变体数量：使用动态状态、通用 vertex layout。[ENGINE]

### GPU 侧

- 过度切换 pipeline 会增加 command processor 开销；按 pipeline 排序 draw call。[ENGINE]
- Early-Z / Hi-Z 受 depth state 影响。[HEUR]

### 移动端

- Tile-based GPU 上，blending、MSAA、MRT 会增加 tile memory 带宽。[ENGINE]
- 尽量避免每帧创建 pipeline；启动时预热。[ENGINE]

---

## 13. 专家经验

**经验**：
把 `VkPipeline` 看作“完全烘焙的执行状态”。在设计阶段就把可变因素（viewport、scissor、blend constants、stencil reference 等）移到动态状态，把编译期分支（feature on/off、quality level）移到 specialization constants，从而把 pipeline 变体数量控制在可缓存、可预热的范围。绘制时按 material/pass 排序，减少 bind 切换。

**适用条件**：
所有 Vulkan 图形与计算渲染。

**不适用情况**：
无；只要使用 draw/dispatch 就需要 pipeline。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `graphics_pipeline.md`
- `compute_pipeline.md`
- `pipeline_layout.md`
- `pipeline_cache.md`
- `specialization_constants.md`
- `graphics_pipeline_library.md`
- `shader_module.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../03_command_buffer/command_buffer.md`

---

## 15. 需要回查官方文档的情况

1. Graphics pipeline 与 compute pipeline 在创建参数上的完整差异。
2. Pipeline derivative 与 base pipeline 的使用规则。
3. Dynamic state 扩展与核心动态状态的交互。
4. Pipeline 与 render pass / dynamic rendering 的兼容性规则。
5. 具体驱动对 pipeline cache 持久化与预热的限制。

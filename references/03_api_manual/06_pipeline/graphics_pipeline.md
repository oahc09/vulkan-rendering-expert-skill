# API Card: VkPipeline (Graphics)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipeline` |
| 常用 API | `vkCreateGraphicsPipelines` / `vkDestroyPipeline` / `vkCmdBindPipeline` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipeline`（graphics）是 Vulkan 中“完全烘焙”的 graphics 执行状态对象，包含 shader stages、顶点输入、光栅化、深度/模板、混合等所有固定功能状态；创建后不可变更，只能通过动态状态修改少量参数。[SPEC]

---

## 2. 所属对象链路

```text
VkRenderPass / Dynamic Rendering 格式信息
→ VkPipelineShaderStageCreateInfo[] (引用 VkShaderModule)
→ VkPipelineVertexInputStateCreateInfo
→ VkPipelineInputAssemblyStateCreateInfo
→ VkPipelineViewportStateCreateInfo
→ VkPipelineRasterizationStateCreateInfo
→ VkPipelineMultisampleStateCreateInfo
→ VkPipelineDepthStencilStateCreateInfo
→ VkPipelineColorBlendStateCreateInfo
→ VkPipelineDynamicStateCreateInfo
→ VkPipelineLayout
→ vkCreateGraphicsPipelines
→ VkPipeline
→ vkCmdBindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS)
→ Draw Calls
```

### 上游依赖

- Shader modules 与 stage 信息。[SPEC]
- Pipeline layout。[SPEC]
- Render pass / subpass 或 dynamic rendering 的 attachment 格式信息。[SPEC]
- Vertex input binding / attribute 描述。[SPEC]

### 下游影响

- 决定 draw call 如何解释顶点、如何光栅化、如何写入 attachment。[SPEC]
- 决定哪些动态状态可在 command buffer 中修改。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipeline`
- `VkGraphicsPipelineCreateInfo`
- `VkPipelineShaderStageCreateInfo`
- `VkPipelineVertexInputStateCreateInfo`
- `VkPipelineInputAssemblyStateCreateInfo`
- `VkPipelineViewportStateCreateInfo`
- `VkPipelineRasterizationStateCreateInfo`
- `VkPipelineMultisampleStateCreateInfo`
- `VkPipelineDepthStencilStateCreateInfo`
- `VkPipelineColorBlendStateCreateInfo`
- `VkPipelineDynamicStateCreateInfo`
- `VkPipelineRenderingCreateInfo`（Dynamic Rendering，Vulkan 1.3 / `VK_KHR_dynamic_rendering`）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateGraphicsPipelines` | 批量创建 graphics pipeline；通常一次创建多个变体。[SPEC] |
| `vkDestroyPipeline` | 销毁 pipeline；必须等待 GPU 不再使用。[SPEC] |
| `vkCmdBindPipeline` | 在 command buffer 中绑定 graphics pipeline。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_dynamic_rendering`（1.3 core）：无需 `VkRenderPass` 即可创建 pipeline，但需提供 `VkPipelineRenderingCreateInfo`。
- `VK_EXT_extended_dynamic_state` / `VK_EXT_vertex_input_dynamic_state` 等可减少 pipeline 变体。

---

## 4. 标准使用流程

```text
准备 shader modules 与 stage 数组
→ 定义 vertex input (binding/attribute)
→ 定义 input assembly (topology)
→ 定义 viewport/scissor 数量（或标记为 dynamic）
→ 定义 rasterizer (cull mode, front face, polygon mode)
→ 定义 multisample (rasterizationSamples)
→ 定义 depth/stencil state
→ 定义 color blend state (attachment count / blend factors)
→ 标记 dynamic state (viewport, scissor, blend constants 等)
→ 指定 pipeline layout
→ 指定 render pass + subpass (或 dynamic rendering 格式)
→ vkCreateGraphicsPipelines
→ vkCmdBindPipeline(GRAPHICS)
→ 设置动态状态（如有）
→ vkCmdDraw / vkCmdDrawIndexed
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `stageCount` / `pStages` | 至少包含 VERTEX + FRAGMENT；需与 pipeline layout stage 匹配。[SPEC] | 缺少 fragment stage；stage 与 shader 类型不一致。[TOOL] |
| `pVertexInputState` | binding/attribute 描述与 vertex buffer 对齐。[SPEC] | attribute offset/stride 错误导致顶点错乱。[TOOL] |
| `pViewportState` | viewport/scissor 数量；若 viewport/scissor 为 dynamic，仍需提供数量。[SPEC] | dynamic viewport 未在 `pDynamicState` 中标记。[TOOL] |
| `pRasterizationState` | cullMode、frontFace、polygonMode、depthBiasEnable。[SPEC] | cull mode 错误导致模型消失；polygonMode=LINE 需 feature。[TOOL] |
| `pMultisampleState` | `rasterizationSamples` 必须与 render pass attachment 样本数一致。[SPEC] | MSAA pipeline 用于非 MSAA render pass。[TOOL] |
| `pDepthStencilState` | depthTest/depthWrite/compareOp；render pass 含 depth attachment 时必须提供。[SPEC] | depthWrite 关闭导致深度不写入；format 不支持 depth。[TOOL] |
| `pColorBlendState` | `attachmentCount` 必须等于 subpass color attachment 数量。[SPEC] | attachmentCount 与 render pass 不匹配。[TOOL] |
| `pDynamicState` | 列出所有动态状态；未列出的状态由创建时静态值决定。[SPEC] | 想动态设置 viewport 但未加入 flags。[TOOL] |
| `layout` | 必须是已创建的 pipeline layout。[SPEC] | layout 与 shader 接口不匹配。[TOOL] |
| `renderPass` / `subpass` 或 `pNext` 链上 `VkPipelineRenderingCreateInfo` | 必须与后续实际 rendering 的 attachment 格式兼容。[SPEC] | dynamic rendering 中 color format 不匹配。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 所有 shader stage 的入口点和 module 有效？
- [ ] Vertex input 与 vertex buffer/shader 声明一致？
- [ ] Pipeline layout 与 shader 接口一致？
- [ ] Render pass / dynamic rendering 格式与实际 attachment 一致？
- [ ] `rasterizationSamples` 与 attachment 样本数一致？
- [ ] Color blend attachment count 与 subpass color attachment count 一致？
- [ ] 动态状态 flags 与后续命令一致？

### 使用阶段

- [ ] 是否在 render pass / dynamic rendering begin 之后绑定？
- [ ] 绑定的 descriptor set layout 与 pipeline layout 兼容？
- [ ] 动态状态是否在 draw 前设置？
- [ ] Scissor 是否非零区域？（scissor 为 0 时无像素输出）[TOOL]

### 销毁阶段

- [ ] 是否有 fence 保证 GPU 不再使用？
- [ ] 是否按 pipeline cache → pipeline 的顺序处理？

---

## 7. 高频错误

1. `pViewportState` 中 viewport/scissor 为 dynamic 但未在 `pDynamicState` 中声明。[TOOL]
2. `pColorBlendState.attachmentCount` 与 render pass subpass color attachment 数量不一致。[TOOL]
3. `rasterizationSamples` 与 attachment 实际样本数不一致。[TOOL]
4. Pipeline layout 与 shader 的 set/binding 不匹配。[TOOL]
5. Render pass 格式与 pipeline 创建时不兼容。[TOOL]
6. Scissor 区域为 0 导致黑屏。[TOOL]
7. Cull mode / front face 设置错误导致模型不可见。[TOOL]
8. Depth/stencil format 不支持所需操作。[TOOL]
9. 在 render pass 外部绑定 graphics pipeline。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkGraphicsPipelineCreateInfo-*`：各状态指针与字段合法性。
- `VUID-vkCmdBindPipeline-*`：bind point 与 pipeline 类型匹配。
- `VUID-vkCmdDraw-*`：render pass / pipeline 兼容性、scissor、dynamic state。

### RenderDoc / AGI

- 查看当前绑定的 graphics pipeline。
- 检查 vertex input、shader stage、rasterizer、depth/stencil、blend 状态。
- 检查 viewport/scissor 实际取值。
- 检查 render target 内容。

### 日志 / 代码检查

- 检查 `vkCreateGraphicsPipelines` 返回值。
- 检查 pipeline cache 是否启用。
- 检查动态状态设置命令。
- 检查 render pass / dynamic rendering 格式与 pipeline 是否一致。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段或按需延迟创建；建议配合 pipeline cache 持久化。[ENGINE]

### 使用时机

- 在 render pass / dynamic rendering begin 后、draw 前绑定。[SPEC]

### 销毁时机

- 确认所有引用它的 command buffer 已完成后销毁。[SPEC]

### in-flight 风险

- Pipeline 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Pipeline 创建本身是 CPU 侧工作，但 `vkCreateGraphicsPipelines` 返回后 pipeline 即可使用，无需额外 fence。[SPEC]

### GPU-GPU 同步

- 切换 pipeline 属于 command buffer 内部顺序执行，无需额外同步。
- 但 pipeline 写入的 attachment 如被后续 pass 读取，需要 barrier。[SPEC]

### 资源访问同步

- Pipeline 的 fragment output 与 input attachment / sampled image 之间需要 image memory barrier / subpass dependency。[SPEC]

---

## 11. Android 注意点

- Android 上 pipeline 创建耗时明显高于 desktop，必须启用 pipeline cache 并持久化到磁盘。[ANDROID][ENGINE]
- 避免在 onSurfaceCreated 时一次性创建过多 pipeline，应分帧预热。[ENGINE]
- 横竖屏切换导致 surface 尺寸变化时，通常只需调整 viewport/scissor，不需要重建 pipeline（除非 dynamic rendering 的 image 格式变化）。[ANDROID]
- AGI 可捕获 pipeline 状态并分析耗时。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- `vkCreateGraphicsPipelines` 是常见 CPU 瓶颈；使用 `VkPipelineCache` 并持久化可显著降低后续启动时间。[ENGINE]
- 减少 pipeline 变体数量：使用动态状态、specialization constants、通用 vertex layout。[ENGINE]

### GPU 侧

- 过度切换 pipeline 会增加 command processor 开销；按 pipeline 排序 draw call。[ENGINE]
- Early-Z / Hi-Z 受 depth state 影响；避免不必要地关闭 depth test/write。[HEUR]

### 移动端

- Tile-based GPU 上，blending、MSAA、multiple render target 会显著增加 tile memory 带宽。[ENGINE]
- 尽量避免每帧创建 pipeline；启动时预热。[ENGINE]
- 使用 `VK_KHR_dynamic_rendering` 可减少 render pass 对象数量，但需确认设备支持。[GUIDE]

---

## 13. 专家经验

**经验**：
把“可变状态”尽量移出 pipeline：使用 dynamic viewport/scissor/stencil reference/blend constants，使用 specialization constants 处理少量编译期分支，从而把 pipeline 变体数量控制在可缓存范围。将 pipeline 按 material/pass 分类排序渲染，减少 bind 切换。

**适用条件**：
复杂场景、多种 material、需要稳定帧率的项目。

**不适用情况**：
单次全屏绘制、固定状态的简单 demo。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `shader_module.md`
- `pipeline_layout.md`
- `compute_pipeline.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../04_buffer_image_memory/image_view.md`
- `../03_command_buffer/command_buffer.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. Dynamic rendering 中 `VkPipelineRenderingCreateInfo` 的字段组合。
2. 各种 dynamic state 扩展的启用与交互。
3. Pipeline derivative / base pipeline handle 的使用规则。
4. Multisample / sample shading 的 feature 要求。
5. 不同 primitive topology 与 tessellation / mesh shader 的交互。
6. 具体 GPU 的 pipeline cache 行为与持久化限制。

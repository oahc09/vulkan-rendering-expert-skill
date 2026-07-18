# API Card: Dynamic State

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | Dynamic State |
| 常用 API | `vkCmdSetViewport` / `vkCmdSetScissor` / `vkCmdSetBlendConstants` / `vkCmdSetStencilReference` / `vkCmdSetDepthBias` / `vkCmdSetRasterizerDiscardEnable` / `vkCmdSetDepthClampEnable` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0（基础 dynamic state）/ `VK_EXT_extended_dynamic_state`（1.3 core）/ `VK_EXT_extended_dynamic_state2` / `VK_EXT_extended_dynamic_state3` |

---

## 1. 一句话定位

Dynamic state 是 Vulkan 中将部分 pipeline 状态从“创建时烘焙”改为“command buffer 录制时设置”的机制，目的是减少 `VkPipeline` 变体数量；代价是每条 `vkCmdSet*` 命令增加 command buffer 录制开销与少量 GPU 状态切换开销。[SPEC]

---

## 2. 所属对象链路

```text
VkPipelineDynamicStateCreateInfo (创建 pipeline 时声明动态状态列表)
→ VkPipeline (剩余状态烘焙; 被声明为 dynamic 的字段值被忽略)
→ vkCmdBindPipeline
→ vkCmdSet* (draw 前设置当前值)
→ vkCmdDraw / vkCmdDrawIndexed (使用最近设置的动态值)
```

### 上游依赖

- `VkPipeline` 创建时必须在 `VkPipelineDynamicStateCreateInfo.pDynamicStates` 中声明后续要动态设置的状态。[SPEC]
- 被声明为 dynamic 的状态，其对应 `VkGraphicsPipelineCreateInfo` 中的静态字段值被忽略，但相关结构体指针通常仍需提供且字段合法。[SPEC]
- 大多数 extended dynamic state 需要启用对应 feature（`extendedDynamicState` / `extendedDynamicState2` / `extendedDynamicState3*` 各 sub-feature）。[SPEC]

### 下游影响

- 每条 `vkCmdSet*` 设置的值在 command buffer 内持续有效，直到下一次同类型 `vkCmdSet*` 覆盖或 command buffer reset。[SPEC]
- Draw call 使用最近一次设置的状态值；若该状态声明为 dynamic 但 draw 前从未设置，行为未定义，Validation Layer 通常报错。[SPEC][TOOL]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipelineDynamicStateCreateInfo`
- `VkDynamicState`（枚举）
- 各 `vkCmdSet*` 命令

### 常用 API（按版本分组）

#### Vulkan 1.0 基础动态状态 [SPEC]

| API | 对应 dynamic state 枚举 | 作用 |
|---|---|---|
| `vkCmdSetViewport` | `VK_DYNAMIC_STATE_VIEWPORT` | 设置 viewport 数组 |
| `vkCmdSetScissor` | `VK_DYNAMIC_STATE_SCISSOR` | 设置 scissor 数组 |
| `vkCmdSetLineWidth` | `VK_DYNAMIC_STATE_LINE_WIDTH` | 设置线宽 |
| `vkCmdSetDepthBias` | `VK_DYNAMIC_STATE_DEPTH_BIAS` | 设置 depth bias 常量 |
| `vkCmdSetBlendConstants` | `VK_DYNAMIC_STATE_BLEND_CONSTANTS` | 设置混合常量 |
| `vkCmdSetStencilCompareMask` | `VK_DYNAMIC_STATE_STENCIL_COMPARE_MASK` | stencil compare mask |
| `vkCmdSetStencilWriteMask` | `VK_DYNAMIC_STATE_STENCIL_WRITE_MASK` | stencil write mask |
| `vkCmdSetStencilReference` | `VK_DYNAMIC_STATE_STENCIL_REFERENCE` | stencil reference 值 |
| `vkCmdSetDepthBounds` | `VK_DYNAMIC_STATE_DEPTH_BOUNDS` | depth bounds 范围 |

#### `VK_EXT_extended_dynamic_state`（Vulkan 1.3 core，无 `EXT` 后缀）[SPEC][REGISTRY]

| API | 作用 |
|---|---|
| `vkCmdSetCullModeEXT` / `vkCmdSetCullMode` | 动态 cull mode |
| `vkCmdSetFrontFaceEXT` / `vkCmdSetFrontFace` | 动态 front face |
| `vkCmdSetPrimitiveTopologyEXT` / `vkCmdSetPrimitiveTopology` | 动态 primitive topology |
| `vkCmdSetViewportWithCountEXT` / `vkCmdSetViewportWithCount` | viewport 数量也动态（替代 1.0 固定数量） |
| `vkCmdSetScissorWithCountEXT` / `vkCmdSetScissorWithCount` | scissor 数量也动态 |
| `vkCmdSetDepthTestEnableEXT` / `vkCmdSetDepthTestEnable` | depth test 开关 |
| `vkCmdSetDepthWriteEnableEXT` / `vkCmdSetDepthWriteEnable` | depth write 开关 |
| `vkCmdSetDepthCompareOpEXT` / `vkCmdSetDepthCompareOp` | depth compare op |
| `vkCmdSetDepthBoundsTestEnableEXT` / `vkCmdSetDepthBoundsTestEnable` | depth bounds test 开关 |
| `vkCmdSetStencilTestEnableEXT` / `vkCmdSetStencilTestEnable` | stencil test 开关 |
| `vkCmdSetStencilOpEXT` / `vkCmdSetStencilOp` | stencil fail / depth fail / pass op |

#### `VK_EXT_extended_dynamic_state2` [SPEC]

| API | 作用 |
|---|---|
| `vkCmdSetRasterizerDiscardEnableEXT` / `vkCmdSetRasterizerDiscardEnable` | rasterizer discard 开关 |
| `vkCmdSetDepthBiasEnableEXT` / `vkCmdSetDepthBiasEnable` | depth bias 总开关 |
| `vkCmdSetPrimitiveRestartEnableEXT` / `vkCmdSetPrimitiveRestartEnable` | primitive restart 开关 |

#### `VK_EXT_extended_dynamic_state3` [SPEC]

| API | 作用 |
|---|---|
| `vkCmdSetDepthClampEnableEXT` | depth clamp 开关 |
| `vkCmdSetLogicOpEnableEXT` | logic op 开关 |
| `vkCmdSetPolygonModeEXT` | polygon mode |
| `vkCmdSetTessellationDomainOriginEXT` | tessellation domain origin |
| `vkCmdSetAlphaToCoverageEnableEXT` / `vkCmdSetAlphaToOneEnableEXT` | multisample alpha 状态 |
| `vkCmdSetRasterizationSamplesEXT` | 采样数 |
| `vkCmdSetSampleMaskEXT` | sample mask |
| `vkCmdSetColorBlendEnableEXT` / `vkCmdSetColorBlendEquationEXT` / `vkCmdSetColorWriteMaskEXT` | per-attachment blend 状态 |
| 其余约 20 个细粒度状态 | 见 spec 完整列表 |

### 相关扩展 / 版本

- Vulkan 1.0 基础动态状态：核心，无扩展。
- `VK_EXT_extended_dynamic_state`（promoted to 1.3 core，命令与枚举去 `EXT` 后缀）。[REGISTRY]
- `VK_EXT_extended_dynamic_state2`、`VK_EXT_extended_dynamic_state2_additional`（部分 `logicOp`、`rasterizationSamples` 需 additional feature）。
- `VK_EXT_extended_dynamic_state3`：状态最多但大量字段需逐 feature 查询设备支持（feature 位分散在 `VkPhysicalDeviceExtendedDynamicState3FeaturesEXT`）。[SPEC]
- `VK_EXT_vertex_input_dynamic_state`：动态 vertex input binding/attribute（与本卡相关但独立扩展）。
- Android 可用性：1.3 core 部分在 Android 14+ 主流设备基本可用；eds2/eds3 视驱动版本，必须查询 feature。[ANDROID]

---

## 4. 标准使用流程

```text
1. 查询设备 feature / extension: extendedDynamicState / ...2 / ...3 各 sub-feature
2. 启用 device extension + feature (VkPhysicalDeviceVulkan13Features /
   VkPhysicalDeviceExtendedDynamicState*FeaturesEXT)
3. 创建 pipeline 时:
   - 在 VkPipelineDynamicStateCreateInfo.pDynamicStates 中列出要动态化的状态
   - 对应的静态结构体字段填默认值 (仍需提供合法指针, 值被忽略)
   - viewport/scissor 数量: 若用 WithCount 变体, pViewportState->viewportCount/scissorCount 设 0
4. 录制 command buffer:
   - vkCmdBindPipeline
   - 在 render pass / dynamic rendering 内、draw 前:
     vkCmdSetViewport / vkCmdSetScissor / vkCmdSetCullMode / ... 按需调用
   - vkCmdDraw*
5. 同一 command buffer 内可多次设置同一状态, 后设置覆盖前一次
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkPipelineDynamicStateCreateInfo::pDynamicStates` | 必须列出所有要动态设置的状态；与 `vkCmdSet*` 命令一一对应。[SPEC] | 想动态设置但未列入；列入但实际未调用对应 `vkCmdSet*`。[TOOL] |
| `dynamicStateCount` | 数量与 `pDynamicStates` 数组匹配。[SPEC] | 计数错误。 |
| `VkPipelineViewportStateCreateInfo::viewportCount` / `scissorCount` | 用 `vkCmdSetViewport/Scissor`（1.0）时数量在 pipeline 创建时固定，运行时必须提供相同数量；用 `vkCmdSetViewportWithCount` 时 pipeline 创建时设为 0。[SPEC] | 混用 WithCount 与非 WithCount；运行时数量与创建时不一致。[TOOL] |
| `VkDynamicState` 枚举值 | 1.3 core 用无后缀枚举（如 `VK_DYNAMIC_STATE_CULL_MODE`）；EXT 扩展有 `_EXT` 后缀枚举，二者等价。[REGISTRY] | 启用了扩展却用了 core 枚举但未启用对应 feature。 |
| extended dynamic state feature 位 | 每个子能力对应独立 feature 位（尤其 eds3）。[SPEC] | 启用 extension 但未启用 feature，或未查询就调用 `vkCmdSet*` 导致 validation/未定义行为。[TOOL] |
| `vkCmdSet*` 调用时机 | 必须在 pipeline bind 之后、draw 之前；rendering inner 状态需在 `vkCmdBeginRendering` 之后。[SPEC] | 在 render pass / dynamic rendering 之外设置 only-rendering-inner 状态。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 所有 `pDynamicStates` 中列出的状态都有对应 feature 启用？[SPEC]
- [ ] 启用了 `*_EXT` extension 时是否同时启用了对应的 feature？
- [ ] `viewportCount` / `scissorCount` 是否与是否使用 WithCount 变体一致？[SPEC]
- [ ] 被声明为 dynamic 的静态字段是否仍提供了合法结构体（即使值被忽略）？[SPEC]
- [ ] `VkPipelineRenderingCreateInfo`（dynamic rendering）格式是否与实际 attachment 一致？

### 使用阶段

- [ ] 每个被声明 dynamic 的状态，在每次 draw 前都设置了当前值？[SPEC]
- [ ] `vkCmdSetViewportWithCount` 的 count 与 `vkCmdSetScissorWithCount` 的 count 是否一致（spec 要求 pipeline 创建时 viewportCount == scissorCount，WithCount 运行时也建议一致）？[SPEC]
- [ ] primitive topology 切换是否触发了 tessellation / mesh shader 路径需要特别注意？
- [ ] `vkCmdSetRasterizationSamplesEXT` 设置的样本数与 render pass attachment 一致？[SPEC]
- [ ] secondary command buffer 是否正确声明 dynamic state 继承？[SPEC]

### 销毁阶段

- [ ] dynamic state 设置命令本身不持有资源，无销毁需求。

---

## 7. 高频错误

1. 在 `VkPipelineDynamicStateCreateInfo` 中声明了某状态，但 draw 前从未调用对应 `vkCmdSet*`，validation 报 `VUID-vkCmdDraw-None-07833` 类错误。[TOOL]
2. 启用了 `VK_EXT_extended_dynamic_state` extension 但未启用 `extendedDynamicState` feature 位。[TOOL]
3. 使用 `vkCmdSetViewportWithCount` 但 pipeline 创建时 `viewportCount` 未设为 0。[SPEC]
4. eds3 的某个 `vkCmdSet*` 未查询对应 sub-feature 就调用，部分驱动静默忽略或 validation 报错。[TOOL][VENDOR]
5. 在 render pass / dynamic rendering 之外调用仅限 rendering 内的状态设置命令。[TOOL]
6. 误以为声明 dynamic 后 pipeline 创建信息中对应字段可填任意非法值（如 NULL 指针）；spec 仍要求结构体指针合法。[SPEC]
7. 切换 `primitiveTopology` 到带 adjacency / patch / list-strip 混用时，与 shader 阶段（tessellation / mesh）不匹配导致渲染错误。[HEUR]
8. `vkCmdSetViewportWithCount` 与 `vkCmdSetScissorWithCount` 运行时 count 不一致。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkGraphicsPipelineCreateInfo-pDynamicStates-*`：dynamic state 与 feature 一致性。
- `VUID-vkCmdDraw-None-07833` 系列：draw 时 dynamic state 未设置。
- `VUID-vkCmdSetViewport-*` / `VUID-vkCmdSetScissor-*` 等：`vkCmdSet*` 参数合法性。
- `VUID-vkCmdBindPipeline-*`：pipeline bind 后 dynamic state 命令顺序。

### RenderDoc / AGI

- 查看每条 draw 实际使用的 dynamic state 取值（viewport、scissor、blend constants、stencil ref 等）。
- 检查 pipeline 是否正确声明 dynamic state。
- AGI 可在 state tree 中查看 eds2/eds3 设置的 cull mode、topology、rasterizer discard 等。[AGI]

### 日志 / 代码检查

- 检查 `VkPipelineDynamicStateCreateInfo.pDynamicStates` 与实际 `vkCmdSet*` 调用列表是否对应。
- 检查 feature 启用：`VkPhysicalDeviceVulkan13Features`、`VkPhysicalDeviceExtendedDynamicState*FeaturesEXT`。
- 检查 `vkCmdSet*` 是否在 render pass / dynamic rendering 内、draw 之前。

---

## 9. 生命周期风险

### 创建时机

- dynamic state 声明在 pipeline 创建时确定，不可修改。[SPEC]

### 使用时机

- `vkCmdSet*` 在 command buffer 录制时调用；设置的值在 command buffer 内持续到下次覆盖或 reset。[SPEC]
- secondary command buffer 继承的 dynamic state 需在 `VkCommandBufferInheritanceInfo` 中正确声明。[SPEC]

### 销毁时机

- 无独立资源；pipeline 销毁后引用其声明的 dynamic state 的 command buffer 仍需 fence 同步。

### in-flight 风险

- `vkCmdSet*` 设置的值是 command buffer 内状态，不持有资源，无 in-flight 销毁风险。
- 但若动态状态引用了 pipeline（如某些状态仅在 pipeline bind 后有效），pipeline 的 in-flight 销毁仍需 fence 保护。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkCmdSet*` 是 command buffer 录制命令，本身不涉及 CPU-GPU 同步。[SPEC]
- 设置的值在 GPU 执行该 command buffer 时按顺序生效。

### GPU-GPU 同步

- dynamic state 设置命令按 command buffer 顺序执行，无需额外同步。[SPEC]
- 跨 command buffer（secondary → primary 继承）时，dynamic state 继承规则需遵守 spec。[SPEC]

### 资源访问同步

- dynamic state 本身不涉及资源访问同步。
- 但 `vkCmdSetDepthBias`、`vkCmdSetStencilReference` 等影响 depth/stencil attachment 写入，相关 attachment 的 layout transition / barrier 仍需正常处理。[SPEC]

---

## 11. Android 注意点

- Android 13+ 主流设备普遍支持 Vulkan 1.3 core（含 extended dynamic state 1），eds2/eds3 支持率视驱动版本。[ANDROID]
- 移动端 GPU 对每条 `vkCmdSet*` 的开销通常低于多 pipeline 变体带来的 cache miss + 内存占用，但需结合 AGI counter 验证。[ANDROID][AGI]
- 横竖屏切换时 viewport/scissor 用 `vkCmdSetViewport` / `vkCmdSetScissor` 即可，无需重建 pipeline。[ENGINE]
- 在 pause/resume 后重新录制 command buffer 时，所有 dynamic state 必须重新设置（command buffer reset 后状态丢失）。[SPEC]
- 部分老 Adreno / Mali 早期驱动对 eds3 支持不全，需运行时查询 feature 位并 fallback 到 baked state。[VENDOR][ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 减少 pipeline 变体数量是最大收益：cull mode、front face、topology、blend 常量、depth bias 等动态化后，可把数十个 pipeline 合并为 1 个。[ENGINE]
- 但每条 `vkCmdSet*` 增加 command buffer 录制开销；高频切换需权衡。[ENGINE]
- 推荐策略：状态变化频率低（如 per-material）用 baked state；变化频率高（如 per-draw 的 stencil ref、blend constants）用 dynamic state。[GUIDE][ENGINE]

### GPU 侧

- 大多数 `vkCmdSet*` 在 GPU 侧开销可忽略（寄存器写入）。[VENDOR]
- 切换 primitive topology、rasterization samples 可能涉及更深的 pipeline 状态刷新，需 AGI 验证。[AGI]

### 移动端

- Tile-based GPU 上，rasterizer discard、depth clamp 等切换影响 tile binning，需谨慎。[VENDOR]
- eds2 的 `rasterizerDiscardEnable` 动态化对“仅 vertex transform pass”很有用，避免单独 pipeline。[ENGINE]

---

## 13. 专家经验

**经验**：
Vulkan 1.3 项目应默认采用 extended dynamic state（eds1）把 cull mode / front face / topology / depth test / stencil test 动态化，配合 `vkCmdSetViewportWithCount` / `vkCmdSetScissorWithCount`；eds2 的 rasterizer discard / depth bias enable / primitive restart enable 也建议动态化。eds3 视项目需求选择：color blend equation / write mask 动态化对 material system 收益大，但需逐 feature 查询设备支持。viewport / scissor / blend constants / stencil reference 在 1.0 起就应动态化。原则：把“会变化的少量状态”移出 pipeline，把“稳定的 shader + 顶点结构 + attachment 格式”保留在 pipeline。

**适用条件**：
Vulkan 1.3+ 项目；material 数量多、pipeline 变体爆炸；需要 per-draw 切换 cull / blend / topology。

**不适用情况**：
Vulkan 1.0 / 1.1 项目且驱动不支持 eds 扩展；单 pass 固定状态 demo；eds3 sub-feature 设备支持不全且无 fallback 路径。

**来源**：`[GUIDE][ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `graphics_pipeline.md`
- `graphics_pipeline_library.md`
- `pipeline_layout.md`
- `specialization_constants.md`
- `../07_rendering/dynamic_rendering.md`
- `../03_command_buffer/command_buffer.md`
- `../09_debug_validation/validation_layer.md`

---

## 15. 需要回查官方文档的情况

1. `VkDynamicState` 枚举的完整列表与版本归属（哪些是 1.0、哪些是 1.3 core、哪些仅 EXT）。
2. eds3 每个 `vkCmdSet*` 对应的 feature 位（`VkPhysicalDeviceExtendedDynamicState3FeaturesEXT` 字段众多，必须逐条核对）。
3. `vkCmdSetViewportWithCount` / `vkCmdSetScissorWithCount` 与 `VK_FEATURE_LINE_RASTER` 等其它 feature 的交互。
4. secondary command buffer 中 dynamic state 继承的完整规则（`VkCommandBufferInheritanceInfo`）。
5. `VK_EXT_extended_dynamic_state2_additional` 中 `logicOp`、`rasterizationSamples` 的额外限制。
6. tessellation / mesh shader 下动态切换 primitive topology 的合法性矩阵。
7. 各 GPU 厂商对 eds3 子集的实际支持与性能开销（需查 vendor best practice + AGI trace）。

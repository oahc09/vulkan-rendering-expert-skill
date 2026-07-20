# Workflow: Add Graphics Pipeline

## 0. 适用范围

### 适用

- 新增一条 graphics pipeline，用于 mesh 渲染、fullscreen pass、deferred lighting 等。
- 需要处理 vertex input、shader stage、pipeline layout、render pass / dynamic rendering、dynamic state、pipeline cache。
- 新增 material、postprocess、UI 渲染管线等场景。

### 不适用

- 纯 compute 管线（见 `add_compute_pipeline.md`）。
- 使用光线追踪 pipeline（需要 `VK_KHR_ray_tracing_pipeline`）。
- 完全由外部引擎或渲染框架生成的管线，无需手动创建。

---

## 1. 任务目标

新增一条完整的 graphics pipeline：

```text
Vertex / Fragment Shader Module
→ Pipeline Layout (descriptor set layouts + push constants)
→ Vertex Input State
→ Input Assembly / Rasterizer / Multisample / Depth-Stencil / Color Blend
→ Render Pass / Dynamic Rendering
→ Dynamic State
→ VkPipeline (+ Pipeline Cache)
→ Command Buffer Bind
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 是否使用 RenderPass 或 Dynamic Rendering（`VK_KHR_dynamic_rendering` / Vulkan 1.3）。
- Vertex buffer layout（stride、attribute format、location）。
- Shader 文件路径 / SPIR-V 字节码。
- Descriptor set layout / push constant 需求。
- Color attachment format(s)、depth/stencil format、sample count。
- Primitive topology：triangle list / strip / line / point。
- 是否需要 dynamic state：viewport、scissor、line width、blend constants、depth bias。
- 是否已有 pipeline cache 文件可复用。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] Shader 编译链路可用，能生成 SPIR-V。
- [ ] 已确认 color attachment format 受支持。
- [ ] 已确认 descriptor set layout 与 shader reflection 一致。
- [ ] 若使用 Dynamic Rendering，已启用对应 feature / extension。
- [ ] Pipeline cache 路径可读写（如启用）。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
SPIR-V Bytecode
→ VkShaderModule (Vertex / Fragment / Geometry / etc.)
→ VkDescriptorSetLayout(s)
→ VkPipelineLayout
→ VkRenderPass 或 Dynamic Rendering Info
→ VkPipeline (with VkPipelineCache)
→ vkCmdBindPipeline
→ vkCmdDraw / vkCmdDrawIndexed
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| vertex shader | `VkShaderModule` | 顶点处理 | pipeline 生命周期 | 否 |
| fragment shader | `VkShaderModule` | 像素处理 | pipeline 生命周期 | 否 |
| pipeline layout | `VkPipelineLayout` | descriptor + push constant 布局 | 通常全局 | 否 |
| descriptor set layout | `VkDescriptorSetLayout` | 描述符绑定 | 通常全局 | 否 |
| pipeline | `VkPipeline` | 完整管线状态 | pipeline 生命周期 | 否（通常） |
| pipeline cache | `VkPipelineCache` | 加速创建 | renderer 生命周期 | 否 |
| render pass（如使用） | `VkRenderPass` | subpass 定义 | 随 swapchain / 输出格式 | 可能 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame constants | Vertex / Fragment |
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | material texture | Fragment |
| set=2,binding=0 | `STORAGE_BUFFER` | per-instance data | Vertex / Fragment |
| push constant | `VkPushConstantRange` | 小数据（material id、draw index） | Vertex / Fragment |

Pipeline 状态：

- `VkPipelineVertexInputStateCreateInfo`：binding、stride、attribute format/location 与 vertex buffer 一致 [SPEC]。
- `VkPipelineInputAssemblyStateCreateInfo`：topology 与 draw call 一致 [SPEC]。
- `VkPipelineViewportStateCreateInfo`：viewport / scissor 数量；若启用 dynamic state，可填 `nullptr` 或 dummy count [SPEC]。
- `VkPipelineRasterizationStateCreateInfo`：polygon mode、front face、cull mode、line width、depth bias [SPEC]。
- `VkPipelineMultisampleStateCreateInfo`：rasterizationSamples 与 render pass / image sample count 一致 [SPEC]。
- `VkPipelineDepthStencilStateCreateInfo`：depth test、write、compare op、stencil op [SPEC]。
- `VkPipelineColorBlendStateCreateInfo`：attachment count 与 subpass color attachment count 一致，blend factor/op [SPEC]。
- `VkPipelineDynamicStateCreateInfo`：viewport、scissor 等动态状态 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass / upload | color/depth image | 转换到 `COLOR_ATTACHMENT_OPTIMAL` / `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | graphics pipeline write |
| graphics pipeline write | color image | `COLOR_ATTACHMENT_WRITE` → next stage layout | present / next pass |
| graphics pipeline write | depth image | `DEPTH_STENCIL_ATTACHMENT_WRITE` → shader read / transfer | shadow sampling / resolve |

必须说明：

- pipeline 本身不直接参与同步，但 pipeline 引用的 render pass / dynamic rendering 的 attachment layout 必须与 command buffer 中的 barrier / rendering begin info 一致 [SPEC]。
- 使用 Dynamic Rendering 时，`VkRenderingInfo` 的 `imageLayout` 必须匹配当前 image layout [SPEC]。
- pipeline color attachment format 必须与 render pass subpass / dynamic rendering color attachment format 一致，否则创建失败 [SPEC]。

---

## 8. 实现步骤

1. **编译 shader**：使用 `glslangValidator` / `slangc` / `dxc` 将 GLSL/HLSL 编译为 SPIR-V；校验 reflection 输出的 set/binding/push constant [ENGINE]。
2. **创建 shader module**：`VkShaderModuleCreateInfo` 加载 SPIR-V 字节码，调用 `vkCreateShaderModule` [SPEC]。
3. **创建 descriptor set layout**：根据 shader reflection 填写 `VkDescriptorSetLayoutBinding`，调用 `vkCreateDescriptorSetLayout` [SPEC]。
4. **创建 pipeline layout**：组合 descriptor set layouts 与 push constant ranges，调用 `vkCreatePipelineLayout` [SPEC]。
5. **确认输出格式**：
   - RenderPass：从 `VkRenderPass` 获取 subpass color/depth format；
   - Dynamic Rendering：使用 `VkPipelineRenderingCreateInfo` 直接指定 color/depth/stencil format [SPEC]。
6. **配置 vertex input**：填写 `VkPipelineVertexInputStateCreateInfo`，binding/attribute 与 vertex buffer 完全匹配 [SPEC]。
7. **配置固定功能状态**：rasterizer、multisample、depth-stencil、color blend；multisample count 与 attachment 一致。
8. **配置 dynamic state**：至少包含 `VK_DYNAMIC_STATE_VIEWPORT` 和 `VK_DYNAMIC_STATE_SCISSOR`；移动端可额外加 `VK_DYNAMIC_STATE_DEPTH_BIAS` [HEUR]。
9. **创建或复用 pipeline cache**：`vkCreatePipelineCache`；退出时保存 cache 数据到文件以加速下次启动 [TOOL]。
10. **创建 graphics pipeline**：填写 `VkGraphicsPipelineCreateInfo`，调用 `vkCreateGraphicsPipelines`；注意 `basePipelineHandle` 与 `basePipelineIndex` 若使用 derivative pipeline [SPEC]。
11. **绑定管线**：录制 command buffer 时 `vkCmdBindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline)`。
12. **设置动态状态**：`vkCmdSetViewport`、`vkCmdSetScissor`；若启用其他 dynamic state，在 bind pipeline 后设置。
13. **绑定 descriptor / push constant**：`vkCmdBindDescriptorSets`、`vkCmdPushConstants`。
14. **绘制**：`vkCmdDraw` / `vkCmdDrawIndexed`。
15. **接入 resize / recreate**：pipeline 通常不随 swapchain 重建；若 output format 改变（如 HDR toggle），才需重建 pipeline。
16. **接入销毁路径**：按 `pipeline → pipeline layout → descriptor set layout → shader module` 顺序销毁；pipeline cache 通常最后销毁 [ENGINE]。

---

## 9. Android 注意点

- pipeline 创建必须在 `ANativeWindow` / `VkSurfaceKHR` 创建后的 device 上进行；虽然 pipeline 不直接依赖 surface，但渲染命令提交到的 queue 在 surface 创建后初始化 [ANDROID]。
- swapchain recreate 通常不触发 graphics pipeline 重建；但若 color attachment format 或 sample count 变化（如 rotation 后选择不同 format），需要重建。
- pause / resume 时保持 pipeline cache 文件可加速恢复；避免每次启动都重新编译所有管线 [ANDROID]。
- 移动端 Mali/Adreno 对 pipeline 创建开销敏感，建议异步创建 + pipeline cache；避免在 render thread 阻塞创建 [ANDROID]。
- rotation / resize 后 dynamic state（viewport、scissor）必须更新为新的 surface extent，否则画面拉伸 [ANDROID]。
- AGI / logcat 验证：检查 `vkCreateGraphicsPipelines` 耗时、validation error、`VkPipeline` handle 是否正确绑定。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkGraphicsPipelineCreateInfo-*`、`VUID-vkCmdBindPipeline-*`、`VUID-vkCmdDraw-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：Pipeline State 中可见 shader module、descriptor binding、viewport/scissor、blend/depth 状态 [TOOL]。
- [ ] 截图符合预期：vertex input、rasterizer、fragment shader 输出正确。
- [ ] logcat（Android）：无 validation error；可输出 pipeline 创建耗时与 cache hit 统计。
- [ ] 性能指标：
  - pipeline 创建耗时在预期范围（首次可能较高，cache 命中后应大幅下降）；
  - GPU frame time 稳定；
  - AGI 中无 redundant pipeline bind [TOOL]。
- [ ] resize / pause / resume / rotation 后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Color attachment format 不匹配**：pipeline 的 `pColorBlendState` attachment format 与 render pass / dynamic rendering 不一致，创建失败 [SPEC]。
2. **Vertex input 不匹配**：shader location 与 `VkVertexInputAttributeDescription` location/format 不一致，draw 时 validation error [SPEC]。
3. **Descriptor set layout 与 shader 不一致**：set/binding/type/stage 不匹配，创建 pipeline layout 或 draw 时报错 [TOOL]。
4. **Viewport / scissor 未设置**：启用 dynamic state 但未调用 `vkCmdSetViewport`/`vkCmdSetScissor`，渲染异常 [SPEC]。
5. **Depth format 不支持**：`VK_FORMAT_D32_SFLOAT` 在某些移动设备不可用，需 fallback [ANDROID]。
6. **Pipeline cache 损坏**：cache 文件与 driver 版本不匹配，加载失败；应 gracefully fallback 到空 cache [TOOL]。
7. **Multisample count 不一致**：`rasterizationSamples` 与 attachment sample count 不同，validation error [SPEC]。
8. **Android surface 旋转后 viewport 未更新**：画面拉伸或只渲染一部分 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- `VkGraphicsPipelineCreateInfo` 关键字段。
- Shader reflection 输出（set/binding/push constant）。
- Render pass / dynamic rendering attachment format。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 pipeline state 截图。
- Android lifecycle 日志。

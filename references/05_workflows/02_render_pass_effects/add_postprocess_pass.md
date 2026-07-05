# Workflow: Add Postprocess Pass

## 0. 适用范围

### 适用

- 已有前向/延迟渲染的输出 color image，需要新增后处理阶段：bloom、tonemapping、color grading、blur、distortion、FXAA 等。
- 使用 fullscreen triangle / quad 作为几何体。
- 输入为上一 pass 的 color attachment 或 offscreen image，输出到 swapchain 或另一个 offscreen image。

### 不适用

- 需要 scene geometry 或逐物体计算的 pass（见 `add_depth_pass.md`、`add_texture_sampling_pass.md`）。
- 纯 compute 后处理（见 `../03_compute_workflows/compute_blur_pass.md`、`../03_compute_workflows/compute_write_storage_image.md`）。
- 直接由外部引擎后处理栈处理，无需手动创建 fullscreen pass。

---

## 1. 任务目标

新增一个 fullscreen 后处理 pass：

```text
Previous Pass Output Image
→ Image Barrier（COLOR_ATTACHMENT_OPTIMAL → SHADER_READ_ONLY_OPTIMAL）
→ Sampler + ImageView + DescriptorSet
→ Fullscreen Graphics Pipeline
→ vkCmdDraw(3/6) 或 vkCmdDrawIndexed
→ Output Render Target（swapchain / offscreen）
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- 输入 image 来源：swapchain / offscreen / previous pass color attachment。
- 输出目标：swapchain image / offscreen image / 下一后处理阶段输入。
- 是否使用 RenderPass 或 Dynamic Rendering。
- 是否需要 input attachment（传统 RenderPass subpass input）或 sampled image。
- Fragment shader 需要的输入资源数量：单张 color、depth、multiple RT、uniform parameters。
- 输出尺寸是否固定或随 swapchain 变化。
- 是否允许 compute 路径替代 graphics fullscreen pass。

---

## 3. 前置检查

- [ ] 输入 image 已创建且 `usage` 包含 `VK_IMAGE_USAGE_SAMPLED_BIT` 或作为 input attachment [SPEC]。
- [ ] 输出 image 已创建且 `usage` 包含 `VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT` [SPEC]。
- [ ] 上一 pass 已完成对输入 image 的写入，并通过 barrier / semaphore 同步 [SPEC]。
- [ ] shader 编译链路可用，fullscreen vertex shader 与 fragment shader 已准备。
- [ ] descriptor 管理可用，可分配/更新 `COMBINED_IMAGE_SAMPLER` 或 `INPUT_ATTACHMENT`。
- [ ] RenderDoc / AGI 可抓帧 [TOOL]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪 [ANDROID]。

---

## 4. Vulkan 对象链路

```text
Previous Pass Output Image
→ VkImageView（sampled view 或 input attachment view）
→ VkSampler（sampled 路径）
→ VkDescriptorSetLayout
→ VkDescriptorSet
→ VkPipelineLayout
→ Fullscreen Graphics Pipeline
    → vertex shader: fullscreen triangle / quad
    → fragment shader: postprocess effect
    → rasterizer: cull off, depth test off
    → color blend: usually disabled or additive
→ VkRenderPass / VkRenderingInfo（output target）
→ VkFramebuffer（RenderPass 路径）
→ Command Buffer
→ Output Render Target
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| input image | `VkImage` | `COLOR_ATTACHMENT | SAMPLED` 或 `INPUT_ATTACHMENT` | previous pass 输出 | 视来源 |
| input image view | `VkImageView` | sampled / input attachment view | 跟随 input image | 视来源 |
| sampler | `VkSampler` | 输入 image 采样 | renderer / pass 生命周期 | 否 |
| output image | `VkImage` | `COLOR_ATTACHMENT` | 当前 pass 输出 | 通常是 |
| output image view | `VkImageView` | color attachment view | 跟随 output image | 通常是 |
| descriptor set | `VkDescriptorSet` | image binding | per-pass / per-frame | 视更新策略 |
| pipeline | `VkPipeline` | fullscreen postprocess | pipeline 生命周期 | 否（通常） |
| framebuffer（RenderPass 路径） | `VkFramebuffer` | output view 绑定 | 跟随 output image | 是 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` | input image view + sampler | Fragment [SPEC] |
| set=0,binding=1 | `COMBINED_IMAGE_SAMPLER`（可选） | additional input（depth、prev frame、LUT） | Fragment [SPEC] |
| set=0,binding=2 | `UNIFORM_BUFFER` / `PUSH_CONSTANT` | postprocess parameters（exposure、threshold、bloom radius） | Fragment [HEUR] |
| set=1,binding=0 | `INPUT_ATTACHMENT`（可选，RenderPass subpass 路径） | previous subpass color attachment | Fragment [SPEC] |

设计说明：

- `COMBINED_IMAGE_SAMPLER` 是通用路径，支持 arbitrary sampling kernel 与多输入 [HEUR]。
- `INPUT_ATTACHMENT` 仅在 RenderPass subpass 内有效，适合需要像素精确对应、不需要自定义采样的场景（如 deferred lighting 读取 G-Buffer） [SPEC]。
- 输出到 swapchain 时，pipeline color attachment format 必须与 swapchain `imageFormat` 一致 [SPEC]。
- Fullscreen vertex shader 通常使用硬编码顶点位置，无需 vertex buffer；也可使用 `vkCmdDraw(3)` 绘制 fullscreen triangle [HEUR]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass color write | input image | `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | postprocess fragment shader [SPEC] |
| previous subpass write | input image（input attachment） | `COLOR_ATTACHMENT_OPTIMAL` 保持，通过 subpass dependency 同步 | next subpass fragment input [SPEC] |
| postprocess fragment write | output image | `UNDEFINED` / `SHADER_READ_ONLY_OPTIMAL` → `COLOR_ATTACHMENT_OPTIMAL` | postprocess color write [SPEC] |
| postprocess fragment write | output image | `COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` / `SHADER_READ_ONLY_OPTIMAL` | present / next pass [SPEC] |

必须说明：

- input image 在 fragment shader 采样前必须转换到 `SHADER_READ_ONLY_OPTIMAL`（sampled 路径） [SPEC]。
- input attachment 路径下，layout 通常为 `COLOR_ATTACHMENT_OPTIMAL` 或 `SHADER_READ_ONLY_OPTIMAL`，具体取决于 RenderPass subpass 配置 [SPEC]。
- output image 在 `vkCmdBeginRenderPass` / `vkCmdBeginRendering` 前需转换到 `COLOR_ATTACHMENT_OPTIMAL` [SPEC]。
- 若使用 compute 路径替代，input/output image layout 可能为 `GENERAL`，需要额外 barrier [SPEC]。

---

## 8. 实现步骤

1. **编写 fullscreen shader**：
   - Vertex shader 生成 fullscreen triangle / quad，输出 UV（注意 Vulkan UV 原点与翻转） [SPEC]。
   - Fragment shader 实现后处理算法，采样输入 image。
2. **创建 sampler**：根据后处理需求设置 `magFilter`、`minFilter`、`mipmapMode`、`addressModeUVW`；通常为 `LINEAR` + `CLAMP_TO_EDGE` [HEUR]。
3. **创建 descriptor set layout**：
   - sampled 路径：`COMBINED_IMAGE_SAMPLER` + `UNIFORM_BUFFER` / push constant。
   - input attachment 路径：`INPUT_ATTACHMENT` + `UNIFORM_BUFFER` / push constant [SPEC]。
4. **创建 pipeline layout**：组合 descriptor set layouts 与 push constant ranges [SPEC]。
5. **创建 graphics pipeline**：
   - vertex input：无 binding / attribute（fullscreen triangle）或简单 quad layout。
   - input assembly：`TRIANGLE_LIST` 或 `TRIANGLE_STRIP`。
   - rasterizer：`cullMode = NONE`。
   - depth-stencil：`depthTestEnable = VK_FALSE`，`depthWriteEnable = VK_FALSE` [HEUR]。
   - color blend：通常 disabled；additive bloom 可启用 additive blend [HEUR]。
   - dynamic state：`VIEWPORT`、`SCISSOR` 至少启用 [SPEC]。
6. **准备 input image view**：确保 input image 已创建对应 view，aspect mask = `COLOR_BIT` [SPEC]。
7. **准备 output image / view**：输出到 swapchain 时使用 swapchain image view；输出到 offscreen 时创建对应 image [SPEC]。
8. **更新 descriptor set**：填写 `VkDescriptorImageInfo`（image view + sampler + layout），调用 `vkUpdateDescriptorSets` [SPEC]。
9. **录制 command buffer**：
   - 插入 input image barrier：`COLOR_ATTACHMENT_WRITE` → `SHADER_READ`，layout `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` [SPEC]。
   - 插入 output image barrier 到 `COLOR_ATTACHMENT_OPTIMAL`（如需要）。
   - begin render pass / dynamic rendering（output target） [SPEC]。
   - bind pipeline、set viewport/scissor、bind descriptor set、push constants。
   - `vkCmdDraw(3)`（fullscreen triangle）或 `vkCmdDraw(6)` / `vkCmdDrawIndexed`（quad） [HEUR]。
   - end render pass / dynamic rendering。
   - 若输出到 swapchain，插入 barrier 到 `PRESENT_SRC_KHR` [SPEC]。
10. **选择 blit/compute 路径（可选）**：
    - 若只需要简单 copy / scale，使用 `vkCmdBlitImage` 或 `vkCmdCopyImage` 比 fullscreen pass 开销更低 [HEUR]。
    - 若需要每像素复杂计算或读写 storage image，使用 compute shader（见 `../03_compute_workflows/compute_blur_pass.md`） [HEUR]。
11. **接入 resize / recreate**：input / output image 若与 swapchain 尺寸相关，recreate 后更新 image view 与 descriptor [ENGINE]。
12. **接入销毁路径**：按 `pipeline → pipeline layout → descriptor set layout → sampler → image view` 顺序销毁 [ENGINE]。

---

## 9. Android 注意点

- 输入 / 输出 image 若与 swapchain 尺寸相关，rotation 后必须重建 image view 并更新 descriptor [ANDROID]。
- 移动端 fullscreen pass 是 bandwidth 敏感操作，建议在 AGI 中检查每像素读取次数与 tile resolve 开销 [ANDROID]。
- 多个后处理 pass 串联时，考虑合并到单个 pass 或降低中间 buffer 精度/分辨率以节省 bandwidth [ANDROID]。
- pause / resume 后 staging / uniform buffer 与 descriptor 生命周期要稳定，避免悬垂 [ANDROID]。
- `preTransform` 变化后只需更新 viewport / scissor 与 swapchain 相关资源，fullscreen pipeline 通常无需重建 [ANDROID]。
- AGI / logcat 验证：检查 fullscreen draw 的 fragment shader cost、texture bandwidth、overdraw [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCmdDraw-*-None-02699`、`VUID-vkCmdPipelineBarrier-*-imageLayout`、`VUID-vkUpdateDescriptorSets-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 fullscreen draw、input texture 绑定、output render target 内容 [TOOL]。
- [ ] 截图符合预期：后处理效果正确，无拉伸 / 翻转 / 黑边。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；输出 pass 输入/输出 image extent、descriptor binding。
- [ ] 性能指标：
  - fullscreen pass GPU cost 与分辨率/采样次数成正比；
  - AGI 中 bandwidth 无异常峰值；
  - 多后处理 pass 合并后 frame time 下降（若已合并） [TOOL]。
- [ ] resize / rotation / pause / resume 后后处理输出正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 flickering。

---

## 11. 常见失败模式

1. **Input image 无 SAMPLED usage**：创建输入 image 时未加 `VK_IMAGE_USAGE_SAMPLED_BIT` [SPEC]。
2. **Layout transition 缺失**：输入 image 仍处于 `COLOR_ATTACHMENT_OPTIMAL`，fragment 采样触发 layout error [TOOL]。
3. **Descriptor imageLayout 与实际 layout 不一致**：descriptor 写 `SHADER_READ_ONLY_OPTIMAL` 但 image 实际为 `GENERAL` [SPEC]。
4. **UV 翻转或视口错误**：fullscreen triangle UV 未适配 Vulkan 坐标系，导致画面上下/左右翻转 [HEUR]。
5. **Output format 不匹配**：pipeline color attachment format 与 output image format 不一致 [SPEC]。
6. **Depth test 未关闭**：后处理 pass 意外开启 depth test，导致 fullscreen quad 被剔除 [HEUR]。
7. **Viewport / scissor 未更新**：resize 后仍为旧尺寸，画面拉伸或只渲染一部分 [ANDROID]。
8. **Input attachment 使用错误**：在 dynamic rendering 或非 subpass 场景误用 `INPUT_ATTACHMENT` [SPEC]。
9. **Blit path 误用**：需要自定义采样核时用了 `vkCmdBlitImage`，导致效果缺失 [HEUR]。
10. **Android rotation 后 descriptor 悬垂**：input/output image view 重建后未更新 descriptor set [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/06_performance_symptoms/fullscreen_pass_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_high.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / 是否使用 Dynamic Rendering。
- 输入 image 来源、format、usage、当前 layout。
- 输出 target 类型（swapchain / offscreen）、format。
- Fragment shader 输入资源（set/binding/type）。
- `VkPipelineColorBlendStateCreateInfo` 与 viewport/scissor 参数。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 input/output binding 状态截图。

---

## 15. 需要回查官方文档的情况

1. `INPUT_ATTACHMENT` 与 `COMBINED_IMAGE_SAMPLER` 在 RenderPass subpass 中的性能与功能差异。
2. Vulkan 坐标系下 fullscreen triangle 与 quad 的 UV 映射细节。
3. Dynamic Rendering 中后处理 pass 的 input image layout 限制。
4. 不同 GPU 对 multiple fullscreen pass 合并为 single pass 的 tile memory 影响。
5. Android  compositor 对 swapchain image 做后处理直接写入时的额外约束。

# Workflow: Add Depth Pass

## 0. 适用范围

### 适用

- 已有基础 color pass，需要新增 depth testing / depth writing。
- 使用传统 `VkRenderPass` 或 `VK_KHR_dynamic_rendering` / Vulkan 1.3 dynamic rendering。
- 需要创建 depth image、depth image view、配置 pipeline depth-stencil state、处理 clear / load / store。

### 不适用

- 纯 2D / UI 渲染，不需要 depth buffer。
- 使用外部引擎已封装好的 depth 处理。
- 需要 stencil 专用功能（本 workflow 以 depth 为主，stencil 仅附带说明）。

---

## 1. 任务目标

在 renderer 中新增含 depth attachment 的渲染能力：

```text
Color Attachment（swapchain / offscreen）
+ Depth Attachment（depth image + view）
→ VkRenderPass 或 Dynamic Rendering Info
→ VkPipeline Depth-Stencil State
→ vkCmdBeginRenderPass / vkCmdBeginRendering
→ Draw with depth test/write
→ End RenderPass / Rendering
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本；是否使用 Dynamic Rendering。
- 输出 color attachment 格式与尺寸。
- 目标 depth format：常用 `VK_FORMAT_D32_SFLOAT`、`VK_FORMAT_D24_UNORM_S8_UINT`、`VK_FORMAT_D16_UNORM`。
- Depth test 需求：`LESS`、`LESS_OR_EQUAL`、`GREATER`、`EQUAL` 等。
- Depth write 需求：是否写入 depth buffer。
- Clear / load / store 策略：每帧 clear、load previous、discard after pass。
- 是否需要 depth image 作为后续 pass 输入（如 shadow / depth prepass visualization）。
- Sample count：是否 MSAA。

---

## 3. 前置检查

- [ ] 已确认目标 depth format 的 `FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
- [ ] 若使用 Dynamic Rendering，已启用 `VK_KHR_dynamic_rendering` 或 Vulkan 1.3 `dynamicRendering` feature [SPEC]。
- [ ] Pipeline color attachment format 与输出 color attachment 一致 [SPEC]。
- [ ] RenderDoc / AGI 可查看 depth attachment 内容 [TOOL]。
- [ ] 当前 frame loop 已稳定处理 color attachment layout transition [ENGINE]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪；depth image 尺寸策略已确定 [ANDROID]。

---

## 4. Vulkan 对象链路

### RenderPass 路径

```text
Color Attachment Image（swapchain / offscreen）
Depth Attachment Image
→ VkImageView（depth view, aspectMask = DEPTH_BIT 或 DEPTH | STENCIL）
→ VkAttachmentDescription / Reference
→ VkSubpassDescription
→ VkRenderPass
→ VkFramebuffer（color view + depth view）
→ Graphics Pipeline（renderPass + subpass）
→ vkCmdBeginRenderPass（with VkRenderPassBeginInfo / VkClearValue）
→ Draw
→ vkCmdEndRenderPass
```

### Dynamic Rendering 路径

```text
Color Attachment Image
Depth Attachment Image
→ VkImageView
→ VkPipelineRenderingCreateInfo（depthAttachmentFormat）
→ Graphics Pipeline
→ VkRenderingInfo
    → pColorAttachments
    → pDepthAttachment（imageView / imageLayout / loadOp / storeOp / clearValue）
→ vkCmdBeginRendering
→ Draw
→ vkCmdEndRendering
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| depth image | `VkImage` | `DEPTH_STENCIL_ATTACHMENT`（可能附加 `SAMPLED` / `TRANSFER_SRC`） [SPEC] | pass / scene | 是（若尺寸绑定 swapchain） |
| depth image view | `VkImageView` | depth attachment view | 跟随 depth image | 是 |
| depth memory | `VkDeviceMemory` | device-local | 跟随 depth image | 是 |
| render pass（RenderPass 路径） | `VkRenderPass` | color + depth subpass | 跟随输出格式 | 是（若格式/样本数变化） |
| framebuffer（RenderPass 路径） | `VkFramebuffer` | color view + depth view | 跟随 swapchain | 是 |
| pipeline | `VkPipeline` | 含 depth-stencil state | pipeline 生命周期 | 否（通常） |

---

## 6. Pipeline / Descriptor 设计

本 workflow 主要调整 graphics pipeline 的固定功能状态：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | `VkPipelineDepthStencilStateCreateInfo.depthTestEnable` | 是否启用 depth test | Fragment output |
| 无 | `VkPipelineDepthStencilStateCreateInfo.depthWriteEnable` | 是否写入 depth | Fragment output |
| 无 | `VkPipelineDepthStencilStateCreateInfo.depthCompareOp` | depth 比较函数 | Fragment output |
| 无 | `VkPipelineDepthStencilStateCreateInfo.minDepthBounds` / `maxDepthBounds` | depth bounds test（可选） | Fragment output |
| 无 | `VkPipelineDepthStencilStateCreateInfo.stencilTestEnable` / `front` / `back` | stencil 测试（可选） | Fragment output |

设计说明：

- `depthTestEnable = VK_TRUE` 且 `depthCompareOp = VK_COMPARE_OP_LESS` 是常规前向渲染配置 [HEUR]。
- 透明物体通常在 color pass 中 `depthWriteEnable = VK_FALSE`、`depthCompareOp = VK_COMPARE_OP_LESS_OR_EQUAL`，避免写入 depth 导致后续不透明物体错误 [HEUR]。
- `depthBoundsTestEnable` 需要 physical device 支持 `depthBounds` feature [SPEC]。
- Pipeline 的 `pDepthStencilState` 不能为 `nullptr` 当 render pass / dynamic rendering 包含 depth attachment [SPEC]。
- Dynamic Rendering 路径下，pipeline 通过 `VkPipelineRenderingCreateInfo.depthAttachmentFormat` 指定 depth format [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous frame / undefined | depth image | `UNDEFINED` → `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | graphics pipeline depth write [SPEC] |
| graphics pipeline depth write | depth image | `DEPTH_STENCIL_ATTACHMENT_WRITE` → shader read / transfer | shadow sampling / debug visualization [SPEC] |
| graphics pipeline depth write | depth image | `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR`（仅当 depth 直接 present，极少见） | present engine [SPEC] |

必须说明：

- depth image 在 pass 开始时需转换到 `VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL` [SPEC]。
- RenderPass 路径中，attachment 的 `initialLayout` / `finalLayout` 与 subpass layout 必须匹配 [SPEC]。
- Dynamic Rendering 路径中，`VkRenderingInfo.pDepthAttachment.imageLayout` 必须为 `VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL`（写入时） [SPEC]。
- 若后续需要采样 depth，需 barrier 从 `DEPTH_STENCIL_ATTACHMENT_WRITE` 到 `SHADER_READ`，layout 转为 `DEPTH_STENCIL_READ_ONLY_OPTIMAL` 或 `SHADER_READ_ONLY_OPTIMAL`（视 format 与 usage） [SPEC]。

---

## 8. 实现步骤

1. **选择 depth format**：
   - 调用 `vkGetPhysicalDeviceFormatProperties` 检查 `VK_FORMAT_D32_SFLOAT`、`VK_FORMAT_D24_UNORM_S8_UINT`、`VK_FORMAT_D16_UNORM` 的 `optimalTilingFeatures` 是否包含 `VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
   - 移动端优先 `D32_SFLOAT` 或 `D16_UNORM`；需要 stencil 时选择 `D24_UNORM_S8_UINT` [ANDROID]。
2. **创建 depth image**：
   - 填写 `VkImageCreateInfo`：`imageType=2D`、`extent` 匹配 color attachment、`format`、 `usage=DEPTH_STENCIL_ATTACHMENT`（若需采样则附加 `SAMPLED`）、`samples` 与 color attachment 一致 [SPEC]。
3. **分配并绑定 memory**：选择 device-local memory type，调用 `vkAllocateMemory` 与 `vkBindImageMemory`；或使用 VMA [ENGINE]。
4. **创建 depth image view**：
   - `VkImageViewCreateInfo.viewType=2D`、`format` 与 depth image 一致。
   - `subresourceRange.aspectMask`：纯 depth 填 `VK_IMAGE_ASPECT_DEPTH_BIT`；含 stencil 填 `DEPTH | STENCIL` [SPEC]。
5. **RenderPass 路径**：
   - 创建 `VkAttachmentDescription`：color attachment 与 depth attachment，分别指定 `format`、`samples`、`loadOp`、`storeOp`、`initialLayout`、`finalLayout` [SPEC]。
   - 创建 `VkSubpassDescription`，`pDepthStencilAttachment` 指向 depth attachment reference [SPEC]。
   - 创建 `VkRenderPass`，调用 `vkCreateRenderPass` [SPEC]。
   - 创建 `VkFramebuffer`：绑定 color view 与 depth view，尺寸与 render pass 一致 [SPEC]。
6. **Dynamic Rendering 路径**：
   - 无需 `VkRenderPass` / `VkFramebuffer`。
   - 在 pipeline 创建时通过 `VkPipelineRenderingCreateInfo` 指定 `depthAttachmentFormat` [SPEC]。
7. **配置 pipeline depth-stencil state**：
   - 填写 `VkPipelineDepthStencilStateCreateInfo`：`depthTestEnable`、`depthWriteEnable`、`depthCompareOp`、`depthBoundsTestEnable`、`stencilTestEnable` 等 [SPEC]。
   - `depthCompareOp` 与场景坐标系/剔除策略匹配：右手坐标系看向 -Z 常用 `LESS` [HEUR]。
8. **配置 dynamic state**：建议启用 `VK_DYNAMIC_STATE_VIEWPORT`、`VK_DYNAMIC_STATE_SCISSOR`；如需动态 depth bias，启用 `VK_DYNAMIC_STATE_DEPTH_BIAS` [SPEC]。
9. **创建 graphics pipeline**：使用对应 RenderPass 或 `VkPipelineRenderingCreateInfo`，调用 `vkCreateGraphicsPipelines` [SPEC]。
10. **录制 command buffer**：
    - 插入 depth image barrier，转换到 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` [SPEC]。
    - RenderPass 路径：`vkCmdBeginRenderPass`，`pClearValues` 包含 color clear 与 depth clear [SPEC]。
    - Dynamic Rendering 路径：`vkCmdBeginRendering`，`pDepthAttachment` 指定 load/store op 与 clear value [SPEC]。
    - bind pipeline，设置 viewport / scissor，draw。
    - end render pass / rendering。
11. **接入 resize / recreate**：depth image / view / framebuffer 随 swapchain 尺寸重建；pipeline 通常不变 [ENGINE]。
12. **接入销毁路径**：按 `framebuffer → render pass → image view → image → memory` 顺序销毁；pipeline 单独管理 [ENGINE]。

---

## 9. Android 注意点

- depth image 尺寸通常与 swapchain extent 一致；rotation / resize 后必须重建 depth image / view / framebuffer [ANDROID]。
- 移动端 Mali/Adreno 对 `D32_SFLOAT` 与 `D16_UNORM` 的带宽与精度权衡不同；对精度要求不高的场景可选 `D16_UNORM` 降低带宽 [ANDROID]。
- pause / resume 不销毁 device，但 surface 销毁后 depth image 等依赖 swapchain 尺寸的资源应随 swapchain 一起销毁 [ANDROID]。
- `preTransform` 变化后只需重建 swapchain 与相关 attachments，depth pipeline 无需重建 [ANDROID]。
- AGI 中检查 depth attachment 的 load/store 行为与 bandwidth 开销 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkRenderPassCreateInfo-*`、`VUID-VkPipelineDepthStencilStateCreateInfo-*`、`VUID-vkCmdBeginRendering-*-depth` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 depth attachment 内容、depth test 状态、depth write 状态 [TOOL]。
- [ ] 截图符合预期：遮挡关系正确，近处物体遮挡远处物体。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；输出 depth format、image extent、loadOp / storeOp。
- [ ] 性能指标：
  - 开启 depth test/write 后 GPU frame time 增加在预期范围；
  - 移动端 bandwidth 无异常峰值；
  - AGI 中 depth attachment 的 load/store 开销合理 [TOOL]。
- [ ] resize / rotation / pause / resume 后 depth 渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Depth format 不支持**：未检查 `vkGetPhysicalDeviceFormatProperties`，在 Mali/Adreno 上某些 format 不可用 [ANDROID]。
2. **Image usage 缺失**：创建 depth image 时未加 `VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
3. **Aspect mask 错误**：depth image view 的 `aspectMask` 未包含 `DEPTH_BIT` [SPEC]。
4. **Pipeline depth state 未配置**：`pDepthStencilState = nullptr` 但 attachment 含 depth，validation error [SPEC]。
5. **Depth compare op 错误**：例如透明物体未关闭 depth write，导致视觉错误 [HEUR]。
6. **Layout transition 缺失**：depth image 未转换到 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` 就开始渲染 [SPEC]。
7. **Load/store op 错误**：每帧未 clear depth 而使用 `LOAD`，导致上一帧 depth 残留 [HEUR]。
8. **Framebuffer attachment 尺寸不匹配**：color 与 depth image 尺寸不一致，validation error [SPEC]。
9. **Multisample count 不一致**：depth image samples 与 color attachment / pipeline 不一致 [SPEC]。
10. **Dynamic Rendering depth format 不匹配**：`VkPipelineRenderingCreateInfo.depthAttachmentFormat` 与实际 depth image format 不一致 [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / 是否使用 Dynamic Rendering。
- 目标 depth format 与 `vkGetPhysicalDeviceFormatProperties` 输出。
- `VkPipelineDepthStencilStateCreateInfo` 关键字段。
- RenderPass attachment description 或 `VkRenderingInfo` 参数。
- Depth image `VkImageCreateInfo` 参数。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 depth attachment 状态截图。

---

## 15. 需要回查官方文档的情况

1. 不同 GPU 对 depth format 的精度、压缩、tile memory 支持差异。
2. `VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL` 与 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 在 depth sampling 场景下的精确区别。
3. Dynamic Rendering 中 `VkPipelineRenderingCreateInfo` 与 `VkRenderingInfo` 的 depth attachment 一致性规则。
4. 含 stencil 的 depth format 在 image view aspect mask 与 shader 采样时的限制。
5. Android 特定设备在 rotation 后 depth attachment 重建的最佳实践。

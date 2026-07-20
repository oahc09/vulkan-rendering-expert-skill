# Workflow: Add Dynamic Rendering Pass

## 0. 适用范围

### 适用

- 目标 Vulkan 1.3 或已启用 `VK_KHR_dynamic_rendering` 的 Vulkan 1.2/1.1 环境。
- 希望减少 `VkRenderPass` / `VkFramebuffer` 对象数量，简化多 render target / 多 pass 管理。
- 需要灵活切换 color / depth attachment 而无需重建 render pass。
- 与 RenderPass 路径并存，用于比较或渐进迁移。

### 不适用

- Vulkan 1.0 / 1.1 未启用 `VK_KHR_dynamic_rendering` 的设备。
- 需要 `VkSubpassDependency` / `input attachment` 等 RenderPass 原生功能的复杂 deferred shading 管线（动态渲染需手动 barrier） [SPEC]。
- 外部引擎强制使用 RenderPass 封装。

---

## 1. 任务目标

使用 Dynamic Rendering 新增一条渲染 pass：

```text
Color / Depth Image Views
→ VkPipelineRenderingCreateInfo（color/depth/stencil formats）
→ VkGraphicsPipelineCreateInfo.pNext
→ VkPipeline
→ VkRenderingInfo（per-frame 指定 attachments / load/store ops）
→ vkCmdBeginRendering
→ Draw / Dispatch-related commands
→ vkCmdEndRendering
→ Barrier / Layout transition for next consumer
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本：1.3 原生，或 1.1/1.2 + `VK_KHR_dynamic_rendering`。
- 是否已启用 `dynamicRendering` feature 与 `VK_KHR_dynamic_rendering` extension [SPEC]。
- 输出 color attachment 数量、format、image view。
- 是否需要 depth / stencil attachment，及其 format、image view。
- 每个 attachment 的 load / store op：`CLEAR` / `LOAD` / `DONT_CARE` / `STORE`。
- 是否需要 image layout transition 在 begin rendering 前 / 后。
- 是否需要 `VkRenderingAttachmentInfo.resolveImageView`（MSAA resolve）。
- 与 RenderPass 路径的兼容策略：是否两套并存或完全替换。

---

## 3. 前置检查

- [ ] `VK_KHR_dynamic_rendering` 在 device extension 列表中，且 `VkPhysicalDeviceDynamicRenderingFeatures.dynamicRendering = VK_TRUE` [SPEC]。
- [ ] 所有 color / depth attachment format 被 physical device 支持作为对应 attachment [SPEC]。
- [ ] 当前 pipeline 创建路径支持通过 `VkPipelineRenderingCreateInfo` 指定 format [ENGINE]。
- [ ] 已设计 command buffer 中的 barrier / layout transition 逻辑（dynamic rendering 不自动处理 subpass dependency） [SPEC]。
- [ ] RenderDoc / AGI 支持 dynamic rendering 抓帧 [TOOL]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪 [ANDROID]。

---

## 4. Vulkan 对象链路

```text
VkPhysicalDevice
→ vkGetPhysicalDeviceFeatures2(VkPhysicalDeviceDynamicRenderingFeatures)
→ VkDevice（启用 VK_KHR_dynamic_rendering 与 dynamicRendering feature）

Color Attachment Image(s)
Depth Attachment Image（可选）
Stencil Attachment Image（可选）
→ VkImageView(s)
→ VkPipelineRenderingCreateInfo
    → colorAttachmentCount
    → pColorAttachmentFormats
    → depthAttachmentFormat
    → stencilAttachmentFormat
→ VkGraphicsPipelineCreateInfo.pNext
→ vkCreateGraphicsPipelines
→ VkPipeline

Per-frame command recording:
→ VkRenderingAttachmentInfo（color / depth / stencil）
    → imageView
    → imageLayout
    → loadOp / storeOp
    → clearValue
    → resolveImageView（MSAA）
→ VkRenderingInfo
    → renderArea
    → layerCount
    → viewMask（multiview）
    → pColorAttachments
    → pDepthAttachment
    → pStencilAttachment
→ vkCmdBeginRendering
→ vkCmdBindPipeline + SetViewport/Scissor + Draw
→ vkCmdEndRendering
→ Barrier to next layout / consumer
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| color attachment image(s) | `VkImage` | `COLOR_ATTACHMENT`（可能附加 `SAMPLED` / `TRANSFER_SRC`） | pass / frame | 是（若绑定 swapchain） |
| color attachment view(s) | `VkImageView` | color attachment view | 跟随 image | 是 |
| depth attachment image | `VkImage` | `DEPTH_STENCIL_ATTACHMENT` | pass / frame | 是（若绑定 swapchain） |
| depth attachment view | `VkImageView` | depth attachment view | 跟随 image | 是 |
| pipeline | `VkPipeline` | dynamic rendering pipeline | pipeline 生命周期 | 否（通常） |
| rendering info | `VkRenderingInfo`（每帧填写） | 指定当前 pass 的 attachment 与操作 | 每帧 | 是（参数） |

注意：Dynamic Rendering 路径不需要 `VkRenderPass` 和 `VkFramebuffer` [SPEC]。

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | `VkPipelineRenderingCreateInfo.colorAttachmentCount` + `pColorAttachmentFormats` | 与 per-frame color attachment format 一致 | Fragment output [SPEC] |
| 无 | `VkPipelineRenderingCreateInfo.depthAttachmentFormat` | 与 depth image view format 一致 | Depth-Stencil [SPEC] |
| 无 | `VkPipelineRenderingCreateInfo.stencilAttachmentFormat` | 与 stencil image view format 一致（可与 depth 相同） | Depth-Stencil [SPEC] |

设计说明：

- `VkPipelineRenderingCreateInfo` 通过 `VkGraphicsPipelineCreateInfo.pNext` 链接 [SPEC]。
- pipeline 创建时指定的 color/depth/stencil format 必须与 `vkCmdBeginRendering` 时实际 attachment 的 format 一致，否则 behavior undefined [SPEC]。
- 若同一 pipeline 需要输出到不同 format 的 attachment，必须创建多个 pipeline 或使用 dynamic rendering 的 `colorAttachmentCount` 但 format 相同的场景 [HEUR]。
- Descriptor set / push constant 设计与 RenderPass 路径完全相同，dynamic rendering 只影响 attachment 声明方式 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass / present engine | color image | `UNDEFINED` / `PRESENT_SRC_KHR` / `SHADER_READ_ONLY_OPTIMAL` → `COLOR_ATTACHMENT_OPTIMAL` | dynamic rendering color write [SPEC] |
| previous pass / undefined | depth image | `UNDEFINED` → `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | dynamic rendering depth write [SPEC] |
| dynamic rendering color write | color image | `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` / `PRESENT_SRC_KHR` | next pass / present engine [SPEC] |
| dynamic rendering depth write | depth image | `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` → `DEPTH_STENCIL_READ_ONLY_OPTIMAL` / `SHADER_READ_ONLY_OPTIMAL` | next pass sample [SPEC] |

必须说明：

- Dynamic Rendering 不自动处理 attachment 之间的 layout transition；`VkRenderingAttachmentInfo.imageLayout` 必须与当前 image layout 一致 [SPEC]。
- `vkCmdBeginRendering` 前需要手动 barrier 到对应 attachment layout；`vkCmdEndRendering` 后需要手动 barrier 到下一个 consumer 的 layout [SPEC]。
- `renderArea` 仅用于 hint，不影响 correctness；但为了性能，应尽量精确 [HEUR]。
- `loadOp` / `storeOp` 在 `VkRenderingAttachmentInfo` 中直接指定，不需要 `VkAttachmentDescription` [SPEC]。

---

## 8. 实现步骤

1. **启用扩展与 feature**：
   - device extension 加入 `VK_KHR_dynamic_rendering` [SPEC]。
   - `VkPhysicalDeviceDynamicRenderingFeatures.dynamicRendering = VK_TRUE`，挂入 `VkDeviceCreateInfo.pNext` [SPEC]。
2. **创建 color / depth attachment image view**：与 RenderPass 路径相同，确保 usage 包含 `COLOR_ATTACHMENT` / `DEPTH_STENCIL_ATTACHMENT` [SPEC]。
3. **配置 `VkPipelineRenderingCreateInfo`**：
   - `colorAttachmentCount` 与每帧 color attachment 数量一致。
   - `pColorAttachmentFormats` 指向 format 数组。
   - `depthAttachmentFormat` / `stencilAttachmentFormat` 与实际 depth image format 一致（如不需要则 `VK_FORMAT_UNDEFINED`） [SPEC]。
4. **创建 graphics pipeline**：将 `VkPipelineRenderingCreateInfo` 挂入 `VkGraphicsPipelineCreateInfo.pNext`，`renderPass` 字段填 `VK_NULL_HANDLE` [SPEC]。
5. **每帧填写 `VkRenderingAttachmentInfo`**：
   - color：`imageView`、`imageLayout = COLOR_ATTACHMENT_OPTIMAL`、`loadOp`、`storeOp`、`clearValue`。
   - depth：`imageView`、`imageLayout = DEPTH_STENCIL_ATTACHMENT_OPTIMAL`、`loadOp`、`storeOp`、`clearValue`。
   - MSAA 时填写 `resolveImageView` 与 `resolveImageLayout` [SPEC]。
6. **填写 `VkRenderingInfo`**：
   - `renderArea` 通常为 `(0,0)` 到 `(width,height)`。
   - `layerCount = 1`（通常）。
   - `pColorAttachments`、`pDepthAttachment`、`pStencilAttachment` 指向步骤 5 的 info [SPEC]。
7. **录制 command buffer**：
   - 插入 attachment image barrier，转换到对应 attachment layout [SPEC]。
   - `vkCmdBeginRendering(&renderingInfo)` [SPEC]。
   - bind pipeline，设置 dynamic state，bind descriptor，draw [SPEC]。
   - `vkCmdEndRendering()` [SPEC]。
   - 插入 barrier 转换到下一 consumer layout（如 `PRESENT_SRC_KHR` 或 `SHADER_READ_ONLY_OPTIMAL`） [SPEC]。
8. **接入 resize / recreate**：重建 attachment image / view，pipeline 通常不变；若 output format 改变则重建 pipeline [ENGINE]。
9. **接入销毁路径**：销毁 pipeline、image view、image、memory；无 `VkRenderPass` / `VkFramebuffer` 需要销毁 [ENGINE]。

---

## 9. Android 注意点

- Dynamic Rendering 在 Android 12+（Vulkan 1.3 设备）广泛可用；旧设备需检查 `VK_KHR_dynamic_rendering` 扩展 [ANDROID]。
- rotation / resize 后只需重建 attachment image / view，pipeline 通常保留；注意 `VkRenderingInfo.renderArea` 必须更新为新 extent [ANDROID]。
- 移动端对 `loadOp = CLEAR` 与 `storeOp = DONT_CARE` 的 tile memory 行为敏感，合理设置可节省 bandwidth [ANDROID]。
- `preTransform` 仍由 swapchain 控制，dynamic rendering 本身不处理旋转；viewport / scissor 需按新 extent 更新 [ANDROID]。
- pause / resume 时不需要销毁 dynamic rendering pipeline，但 surface 销毁后相关 attachment 资源应释放 [ANDROID]。
- AGI 可查看 dynamic rendering 的 attachment 与 load/store 行为 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkGraphicsPipelineCreateInfo-dynamicRendering-*`、`VUID-VkPipelineRenderingCreateInfo-*`、`VUID-vkCmdBeginRendering-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 dynamic rendering pass、attachment、draw call [TOOL]。
- [ ] 截图符合预期：color / depth attachment 内容正确。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；输出 `VkPipelineRenderingCreateInfo` 与 `VkRenderingInfo` 关键参数。
- [ ] 性能指标：
  - 与 RenderPass 路径相比 frame time 在预期范围（通常接近，具体取决于 driver）；
  - 无 redundant pipeline 创建；
  - AGI 中 attachment load/store 行为符合预期 [TOOL]。
- [ ] resize / rotation / pause / resume 后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Feature 未启用**：未在 device create info pNext 中启用 `dynamicRendering` feature [SPEC]。
2. **Extension 未启用**：未启用 `VK_KHR_dynamic_rendering` device extension [SPEC]。
3. **Pipeline format 不匹配**：`VkPipelineRenderingCreateInfo` 中 color/depth format 与实际 attachment 不一致 [SPEC]。
4. **Image layout 不匹配**：`VkRenderingAttachmentInfo.imageLayout` 与当前 image layout 不一致 [SPEC]。
5. **缺少 barrier**：dynamic rendering 不自动处理 layout transition，导致 image layout error [SPEC]。
6. **renderPass 字段未置空**：创建 pipeline 时 `renderPass` 未填 `VK_NULL_HANDLE` [SPEC]。
7. **colorAttachmentCount 不一致**：pipeline 与 `VkRenderingInfo` 中 color attachment 数量不同 [SPEC]。
8. **Resolve image 配置错误**：MSAA 场景下 `resolveImageView` format / sample count 不匹配 [SPEC]。
9. **忘记 `vkCmdEndRendering`**：与 `vkCmdBeginRendering` 未成对 [SPEC]。
10. **Android 旧设备不支持**：未检查扩展可用性直接假设支持 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / 是否启用 `VK_KHR_dynamic_rendering`。
- `VkPhysicalDeviceDynamicRenderingFeatures` 输出。
- `VkPipelineRenderingCreateInfo` 参数。
- `VkRenderingInfo` 与 `VkRenderingAttachmentInfo` 参数。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 dynamic rendering pass 的显示情况。
- Android lifecycle 日志。

---

## 15. 需要回查官方文档的情况

1. `VK_KHR_dynamic_rendering` 与 Vulkan 1.3 core dynamic rendering 的 feature / extension 差异。
2. Dynamic Rendering 中 multiview / `viewMask` 的使用限制。
3. `VkRenderingAttachmentInfo` 中 `resolveMode` 与 `resolveImageLayout` 的精确规则。
4. Dynamic Rendering 与 `VK_EXT_fragment_density_map`、`VK_EXT_multisampled_render_to_single_sampled` 等扩展的交互。
5. 不同移动端 driver 对 dynamic rendering 的 tile memory 优化行为差异。

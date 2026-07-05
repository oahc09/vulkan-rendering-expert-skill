# Workflow: Setup Swapchain

## 0. 适用范围

### 适用

- 已有 `VkInstance`、`VkPhysicalDevice`、`VkDevice`、`VkQueue`，需要创建显示交换链。
- 需要选择 swapchain format、extent、present mode、image count 并完成 image view 创建。
- 需要处理 resize / rotation / surface 变化后的 swapchain recreate。

### 不适用

- 纯离屏渲染，不需要 present 到显示设备。
- 使用外部窗口系统封装（如某些引擎已内部处理 swapchain）。
- 目标平台无 surface（如 headless compute）。

---

## 1. 任务目标

创建可提交的显示交换链：

```text
VkSurfaceKHR
→ vkGetPhysicalDeviceSurfaceCapabilitiesKHR / Formats / PresentModes
→ VkSwapchainCreateInfoKHR（imageCount / format / extent / presentMode / preTransform）
→ vkCreateSwapchainKHR
→ vkGetSwapchainImagesKHR
→ VkImageView（per swapchain image）
→ Render Pass / Dynamic Rendering
→ vkQueuePresentKHR
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux / 其他。
- Vulkan 版本。
- `VkSurfaceKHR` 是否已有效创建。
- 目标 color format 与 color space 偏好（如 `VK_FORMAT_B8G8R8A8_UNORM` + `SRGB_NONLINEAR`）。
- 目标 present mode 偏好（`FIFO`、`MAILBOX`、`IMMEDIATE`）。
- 是否需要 depth/stencil attachment。
- 是否使用 RenderPass 或 Dynamic Rendering。
- 是否需要在 swapchain image 上做 transfer / sampled 操作。
- 窗口可最小化 / extent 为 0 时的处理策略。

---

## 3. 前置检查

- [ ] `VkDevice` 已启用 `VK_KHR_swapchain` [SPEC]。
- [ ] `VkSurfaceKHR` 有效，且背后窗口 / `ANativeWindow` 未销毁 [ANDROID]。
- [ ] 已调用 `vkGetPhysicalDeviceSurfaceSupportKHR` 确认 graphics / present queue 支持该 surface [SPEC]。
- [ ] 已获取 surface capabilities、formats、present modes 列表 [SPEC]。
- [ ] 已确认目标 format 在 surface formats 列表中 [SPEC]。
- [ ] 已确认目标 present mode 在 present modes 列表中，或准备了 fallback [SPEC]。
- [ ] RenderDoc / AGI 可抓帧验证 swapchain image [TOOL]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
VkPhysicalDevice
→ VkSurfaceKHR
→ vkGetPhysicalDeviceSurfaceCapabilitiesKHR
→ vkGetPhysicalDeviceSurfaceFormatsKHR
→ vkGetPhysicalDeviceSurfacePresentModesKHR
→ VkSwapchainCreateInfoKHR
    → surface
    → minImageCount
    → imageFormat / imageColorSpace
    → imageExtent
    → imageArrayLayers
    → imageUsage
    → preTransform
    → compositeAlpha
    → presentMode
    → oldSwapchain
→ vkCreateSwapchainKHR
→ VkSwapchainKHR
→ vkGetSwapchainImagesKHR → VkImage[]
→ VkImageView[]
→ Framebuffer 或 Dynamic Rendering Attachment
→ vkQueuePresentKHR
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| swapchain | `VkSwapchainKHR` | present 图像交换 | swapchain 生命周期 | 是 |
| swapchain images | `VkImage` | color attachment / present | 由 Vulkan 管理 | 是 |
| swapchain image views | `VkImageView` | attachment / sampled view | 跟随 swapchain | 是 |
| depth image | `VkImage` | depth stencil attachment | 跟随 swapchain 尺寸 | 是 |
| depth image view | `VkImageView` | depth attachment view | 跟随 depth image | 是 |
| framebuffers | `VkFramebuffer` | render pass 绑定 | 跟随 swapchain | 是（如使用 RenderPass） |
| acquire semaphore | `VkSemaphore` | image available 信号 | per-frame | 否（通常） |
| present semaphore | `VkSemaphore` | render finished 信号 | per-frame | 否（通常） |

---

## 6. Pipeline / Descriptor 设计

本 workflow 不直接创建 pipeline，但 swapchain image view 会作为 graphics pipeline 的 color attachment：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | color attachment | swapchain image view | Fragment output |
| set=0,binding=0（后处理场景） | `COMBINED_IMAGE_SAMPLER` | previous pass output image view | Fragment |

设计说明：

- 若需将 swapchain image 作为 sampled image 读取（如某些后处理直接写入 swapchain 前采样），创建 swapchain 时 `imageUsage` 必须包含 `VK_IMAGE_USAGE_SAMPLED_BIT` 或 `VK_IMAGE_USAGE_TRANSFER_SRC_BIT` [SPEC]。
- Pipeline color attachment format 必须与 swapchain `imageFormat` 一致，否则创建失败 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| present engine | swapchain image | `PRESENT_SRC_KHR` / `UNDEFINED` → `COLOR_ATTACHMENT_OPTIMAL` | graphics pipeline color write [SPEC] |
| graphics pipeline color write | swapchain image | `COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` | present engine [SPEC] |
| previous pass color write | offscreen input image | `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fragment shader sample [HEUR] |

必须说明：

- swapchain image 首次被写入时，layout 通常为 `UNDEFINED` 或 `PRESENT_SRC_KHR`；使用 RenderPass `loadOp` 为 `CLEAR`/`DONT_CARE` 时可从 `UNDEFINED` 开始 [SPEC]。
- 使用 Dynamic Rendering 时，`VkRenderingInfo.colorAttachments.imageLayout` 必须为 `VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL`（写入时）或 `PRESENT_SRC_KHR`（present 时） [SPEC]。
- `vkQueuePresentKHR` 前必须确保所有 color writes 已完成并通过 semaphore / fence 同步 [SPEC]。

---

## 8. 实现步骤

1. **查询 surface capabilities**：调用 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 获取 `minImageCount`、`currentExtent`、`currentTransform`、`min/maxImageExtent`、`supportedCompositeAlpha`、`supportedTransforms`、`supportedUsageFlags` [SPEC]。
2. **查询 surface formats**：调用 `vkGetPhysicalDeviceSurfaceFormatsKHR`，从返回列表中选择首选 format / color space；若列表包含 `VK_FORMAT_UNDEFINED`，可任选 [SPEC]。
3. **查询 present modes**：调用 `vkGetPhysicalDeviceSurfacePresentModesKHR`，按场景选择：
   - 默认稳定：`VK_PRESENT_MODE_FIFO_KHR` [SPEC]。
   - 低延迟：`VK_PRESENT_MODE_MAILBOX_KHR`（若支持） [HEUR]。
   - 最小延迟可接受撕裂：`VK_PRESENT_MODE_IMMEDIATE_KHR` [HEUR]。
4. **确定 image count**：
   - 至少 `surfaceCapabilities.minImageCount` [SPEC]。
   - 通常为 `minImageCount + 1` 以支持 triple buffering；若 `maxImageCount` 不为 0 则不超过该值 [HEUR]。
5. **确定 image extent**：
   - 若 `currentExtent.width != UINT32_MAX`，严格使用 `currentExtent` [SPEC]。
   - 否则在 `minImageExtent` 与 `maxImageExtent` 之间选择，并 clamp 到窗口 framebuffer 尺寸 [SPEC]。
6. **确定 preTransform**：优先匹配 `currentTransform` 以减少 compositor 开销；若应用自行处理旋转，可选择 `VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR` [ANDROID]。
7. **确定 compositeAlpha**：通常选择 `VK_COMPOSITE_ALPHA_OPAQUE_BIT_KHR` [SPEC]。
8. **确定 image usage**：默认 `VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT`；若需 sampled / transfer 操作，追加对应 flag [SPEC]。
9. **创建 swapchain**：填写 `VkSwapchainCreateInfoKHR`，`oldSwapchain` 传入旧 swapchain（recreate 时）以减少切换闪烁；调用 `vkCreateSwapchainKHR` [SPEC]。
10. **获取 swapchain images**：调用 `vkGetSwapchainImagesKHR` 获取 `VkImage` 数组 [SPEC]。
11. **创建 image views**：对每个 swapchain image 填写 `VkImageViewCreateInfo`，`format` 与 swapchain format 一致，`subresourceRange.aspectMask=COLOR_BIT`，调用 `vkCreateImageView` [SPEC]。
12. **创建 depth image / view（如需要）**：按 swapchain extent 创建 depth image 与 view，常用格式 `VK_FORMAT_D32_SFLOAT` 或 `VK_FORMAT_D24_UNORM_S8_UINT`（需检查支持） [SPEC]。
13. **创建 framebuffer 或 dynamic rendering attachment info（如需要）**：将 color view 与 depth view 绑定到 RenderPass 或 `VkRenderingInfo` [SPEC]。
14. **接入 frame loop**：
    - `vkAcquireNextImageKHR` 获取 image index，传递 semaphore / fence [SPEC]。
    - 渲染到对应 swapchain image [SPEC]。
    - `vkQueuePresentKHR` 提交显示 [SPEC]。
15. **接入 resize / recreate 路径**：
    - 监听 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` [SPEC]。
    - 等待 idle，销毁 framebuffer / image view / depth image，用 `oldSwapchain` 创建新 swapchain [ENGINE]。
16. **接入销毁路径**：等待 idle 后销毁 image view、depth image / view、framebuffer，最后 `vkDestroySwapchainKHR` [SPEC]。

---

## 9. Android 注意点

- swapchain 创建必须在 `ANativeWindow` 有效且 `VkSurfaceKHR` 创建之后；`APP_CMD_INIT_WINDOW` 是合适时机 [ANDROID]。
- `APP_CMD_TERM_WINDOW` 后必须停止 `vkAcquireNextImageKHR` / `vkQueuePresentKHR`，否则可能 native crash [ANDROID]。
- 横竖屏 rotation 后 `currentTransform` 与 `currentExtent` 可能变化，应触发 swapchain recreate 并更新 `preTransform` [ANDROID]。
- Android 窗口最小化或分屏时 `currentExtent` 可能为 0，此时不应创建 swapchain，等待有效尺寸 [ANDROID]。
- pause / resume 不销毁 swapchain 更安全；但 surface 销毁后必须销毁 swapchain 及其依赖资源 [ANDROID]。
- 移动端通常优先 `VK_PRESENT_MODE_FIFO_KHR` 以省电；竞技类游戏可权衡 `MAILBOX` [ANDROID]。
- `preTransform` 与 `currentTransform` 不一致时，compositor 可能做额外变换，增加功耗 [ANDROID]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkSwapchainCreateInfoKHR-*`、`VUID-vkAcquireNextImageKHR-*`、`VUID-vkQueuePresentKHR-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 swapchain image 内容、present 调用、surface / swapchain 参数 [TOOL]。
- [ ] 截图符合预期：颜色、分辨率、朝向正确。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；输出 extent、format、presentMode、imageCount。
- [ ] 性能指标：
  - `vkAcquireNextImageKHR` 不频繁阻塞；
  - present 模式符合预期延迟与功耗目标；
  - 无 redundant swapchain recreate [TOOL]。
- [ ] resize / rotation / pause / resume 后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或撕裂。

---

## 11. 常见失败模式

1. **Device extension 未启用**：未启用 `VK_KHR_swapchain` 导致 `vkCreateSwapchainKHR` 不可用 [SPEC]。
2. **Format 不支持**：选择的 `imageFormat` 不在 surface formats 列表中 [SPEC]。
3. **Extent 不匹配**：`currentExtent` 不为 `UINT32_MAX` 时未严格匹配，或 extent 为 0 时仍创建 swapchain [SPEC][ANDROID]。
4. **Image count 超限**：超过 `surfaceCapabilities.maxImageCount`（非 0 时） [SPEC]。
5. **Present mode 不支持**：假设 `MAILBOX` 一定可用，未准备 fallback [TOOL]。
6. **Image usage 不足**：后续想用 swapchain image 做 transfer / sampled 但创建时未加 flag [SPEC]。
7. **preTransform 不匹配**：rotation 后未更新 `preTransform`，compositor 额外旋转 [ANDROID]。
8. **Semaphore 复用冲突**：`vkAcquireNextImageKHR` 的 semaphore 仍被上一帧占用 [SPEC]。
9. **Old swapchain 处理错误**：recreate 时未传入 `oldSwapchain` 或过早销毁旧 swapchain，导致闪烁或 crash [ENGINE]。
10. **Image view format 不匹配**：swapchain image view format 与 swapchain format 不一致，validation error [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/08_synchronization/fence.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 输出。
- `vkGetPhysicalDeviceSurfaceFormatsKHR` 列表。
- `vkGetPhysicalDeviceSurfacePresentModesKHR` 列表。
- `VkSwapchainCreateInfoKHR` 关键字段。
- `vkAcquireNextImageKHR` / `vkQueuePresentKHR` 返回值。
- Validation Layer 完整报错。
- Android lifecycle 日志与 surface 尺寸变化记录。

---

## 15. 需要回查官方文档的情况

1. 不同 compositor / GPU 对 `preTransform` 与 `currentTransform` 的实际处理差异。
2. `VK_EXT_swapchain_maintenance1` 在 resize / rotation 场景下的 retired swapchain 行为。
3. Android 特定设备在 `onPause` / `onResume` 后对 swapchain image 的生命周期处理。
4. 多 surface / device group 场景下 `vkAcquireNextImage2KHR` 的使用。
5. `VK_PRESENT_MODE_FIFO_RELAXED_KHR` 与 `FIFO` 在低帧率下的精确行为差异。

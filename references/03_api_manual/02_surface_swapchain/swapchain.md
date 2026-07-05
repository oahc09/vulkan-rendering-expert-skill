# API Card: VkSwapchainKHR

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 显示链 |
| Vulkan 对象 | `VkSwapchainKHR` |
| 常用 API | `vkCreateSwapchainKHR` / `vkDestroySwapchainKHR` / `vkGetSwapchainImagesKHR` / `vkAcquireNextImageKHR` / `vkQueuePresentKHR` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [ANDROID] [TOOL]` |
| 适用 Vulkan 版本 | Vulkan 1.0 + `VK_KHR_swapchain` |

---

## 1. 一句话定位

`VkSwapchainKHR` 是 Vulkan 与显示引擎交换图像的机制，管理一组 presentable image，并提供 `vkAcquireNextImageKHR` / `vkQueuePresentKHR` 完成“取图 - 渲染 - 送显”循环。[SPEC]

---

## 2. 所属对象链路

```text
VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images (VkImage)
→ VkImageView
→ Render Pass / Dynamic Rendering
→ vkQueuePresentKHR
→ Display
```

### 上游依赖

- `VkSurfaceKHR` 必须有效。[SPEC]
- `VkDevice` 必须启用 `VK_KHR_swapchain` extension。[SPEC]
- 用于 present 的 queue 必须支持该 surface 的 presentation。[SPEC]

### 下游影响

- swapchain image 数量决定 frame-in-flight 上限。
- swapchain format / color space 决定 render target 格式。
- swapchain extent 决定 viewport / scissor / framebuffer 尺寸。
- present mode 决定延迟与撕裂行为。

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSwapchainKHR`
- `VkSwapchainCreateInfoKHR`
- `VkPresentInfoKHR`
- `VkAcquireNextImageInfoKHR`（用于 `vkAcquireNextImage2KHR`，多 surface / device group 场景）
- Swapchain `VkImage`（由 Vulkan 创建，应用只获取，不分配内存）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateSwapchainKHR` | 创建 swapchain，可指定 `oldSwapchain` 做无缝切换。[SPEC] |
| `vkDestroySwapchainKHR` | 销毁 swapchain 及其 image view，但 retired swapchain 仍可能直到 GPU 用完才真正释放。[SPEC] |
| `vkGetSwapchainImagesKHR` | 获取 swapchain 创建的 `VkImage` handle 数组。[SPEC] |
| `vkAcquireNextImageKHR` | 从 swapchain 获取下一帧可渲染 image index，需要 semaphore / fence 通知可用性。[SPEC] |
| `vkQueuePresentKHR` | 将渲染完成的 image 提交到 present engine。[SPEC] |
| `vkAcquireNextImage2KHR` | 支持 `VkAcquireNextImageInfoKHR`，含 `deviceMask`，用于 device group。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_swapchain` 必须启用。
- `VK_EXT_swapchain_maintenance1`：可延迟 retired swapchain 销毁，减少 recreate 卡顿。
- Android 可用性：所有支持 Vulkan 的 Android 设备均支持 `VK_KHR_swapchain`。[ANDROID]

---

## 4. 标准使用流程

```text
查询 surface capabilities / formats / present modes
→ 选择 imageCount / format / extent / presentMode / preTransform
→ vkCreateSwapchainKHR (oldSwapchain = VK_NULL_HANDLE 或旧 swapchain)
→ vkGetSwapchainImagesKHR 获取 VkImage[]
→ 为每个 swapchain image 创建 VkImageView
→ 创建 Framebuffer / Dynamic Rendering 目标
→ 每帧:
    vkAcquireNextImageKHR(..., imageAvailableSemaphore, fence)
    → 处理 VK_ERROR_OUT_OF_DATE_KHR / VK_SUBOPTIMAL_KHR
    → record command buffer 渲染到该 image
    → vkQueueSubmit(..., renderFinishedSemaphore)
    → vkQueuePresentKHR(..., renderFinishedSemaphore)
→ 销毁:
    等待 GPU idle
    → 销毁依赖 swapchain image 的 framebuffer / image view / depth image
    → vkDestroySwapchainKHR
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `surface` | 必须有效；Android 上 surface 背后的 ANativeWindow 销毁后 surface 失效。[SPEC][ANDROID] |
| `oldSwapchain` | 用于 resize / rotation 时无缝切换；创建新 swapchain 后旧 swapchain 被 retired。[SPEC] | 未传入 oldSwapchain，导致切换时画面闪烁或黑屏。[HEUR] |
| `minImageCount` | 至少为 `surfaceCapabilities.minImageCount`；通常选 `minImageCount + 1` 以支持 triple buffering。[SPEC] | 设为 1 导致 acquire 阻塞或 tearing。[SPEC] |
| `imageFormat` / `imageColorSpace` | 必须从 `vkGetPhysicalDeviceSurfaceFormatsKHR` 返回列表中选择。[SPEC] | 使用不支持的 format 导致创建失败。[TOOL] |
| `imageExtent` | `currentExtent` 不为 `0xFFFFFFFF` 时必须严格匹配；否则在 `minImageExtent` ~ `maxImageExtent` 内选择。[SPEC] | Android 上 extent 为 0 时仍创建 swapchain。[ANDROID] |
| `imageArrayLayers` | 通常 1；VR 等多层场景可设为 2。[SPEC] | 误设为 0 或非 1 值导致创建失败。[SPEC] |
| `imageUsage` | 默认 `COLOR_ATTACHMENT`；如需后处理读取需加 `TRANSFER_SRC` / `SAMPLED`。[SPEC] | 后续想用 swapchain image 做 sampled image 但 usage 未包含。[SPEC] |
| `preTransform` | 应与 `currentTransform` 一致以减少合成开销，特别是 Android 横竖屏。[ANDROID] | 填 `TRANSFORM_IDENTITY` 但 surface 当前为旋转状态，导致驱动额外旋转。[TOOL] |
| `compositeAlpha` | 决定透明通道处理方式；Android 上通常 `OPAQUE`。[ANDROID] | 误用 `PRE_MULTIPLIED` 导致 alpha 混合错误。[HEUR] |
| `presentMode` | `FIFO` / `MAILBOX` / `IMMEDIATE` / `FIFO_RELAXED`。[SPEC] | 假设所有设备支持 `MAILBOX`。[TOOL] |
| `clipped` | 通常 `VK_TRUE`，可提升性能。[GUIDE] | 需要 readback 被裁剪区域时设为 TRUE 导致内容丢失。[HEUR] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VkDevice` 是否启用 `VK_KHR_swapchain`？
- [ ] `surface` 是否仍有效？
- [ ] `imageFormat` / `imageColorSpace` 是否在 surface formats 列表中？
- [ ] `imageExtent` 是否满足 capabilities 约束？
- [ ] `minImageCount` 是否满足 `surfaceCapabilities.minImageCount`？
- [ ] `presentMode` 是否可用？是否准备了 fallback？
- [ ] `preTransform` 是否与 `currentTransform` 匹配？
- [ ] `imageUsage` 是否覆盖后续所有用途？

### 使用阶段

- [ ] `vkAcquireNextImageKHR` 返回值是否处理 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`？
- [ ] `vkQueuePresentKHR` 返回值是否处理 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`？
- [ ] acquire 使用的 semaphore / fence 是否与 submit / present 正确配对？
- [ ] 同一帧是否不会同时 acquire 多个 image 而不提交？

### 销毁阶段

- [ ] 是否先销毁依赖 swapchain image 的 framebuffer / image view / depth image？
- [ ] 是否等待 in-flight GPU 工作完成后再销毁？
- [ ] 旧 swapchain 是否已 retired 并在新 swapchain 创建后安全释放？[SPEC]

---

## 7. 高频错误

1. `vkAcquireNextImageKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR` 后继续用旧 swapchain 渲染。[SPEC]
2. `vkQueuePresentKHR` 返回 `VK_SUBOPTIMAL_KHR` 后未触发 swapchain recreate。[TOOL]
3. `imageExtent` 为 0 时创建 swapchain，Android 上常见于启动或最小化时。[ANDROID]
4. 未处理 `oldSwapchain`，resize 时直接销毁旧 swapchain 再创建新 swapchain，导致 flicker。[ENGINE]
5. `minImageCount` 设得太小，导致 CPU 等待 acquire。[TOOL]
6. `imageUsage` 未包含后续需要的 flag，例如想用 swapchain image 做 storage image。[SPEC]
7. `vkAcquireNextImageKHR` 的 semaphore 被复用，而上一帧仍占用它。[SPEC]
8. Present queue 与 graphics queue 不同，但 semaphore 未跨 queue 传递。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkSwapchainCreateInfoKHR-*`：创建参数合法性。
- `VUID-vkAcquireNextImageKHR-*`：acquire 与 semaphore / fence 状态。
- `VUID-vkQueuePresentKHR-*`：present 与 swapchain / semaphore 匹配。
- `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 提示需要 recreate。[TOOL]

### RenderDoc / AGI

- RenderDoc：验证 swapchain image 是否有内容、present 是否发生。
- AGI：查看 surface / swapchain 参数、present 时间线、GPU counter。[TOOL]

### 日志 / 代码检查

- 打印 `vkAcquireNextImageKHR` 和 `vkQueuePresentKHR` 返回值。
- 打印 `imageExtent`、`imageFormat`、`presentMode`。
- Android logcat 中查找 `VK_ERROR_DEVICE_LOST` / surface lost 信息。

---

## 9. 生命周期风险

### 创建时机

- surface 创建后、渲染循环开始前。
- Android 在 `APP_CMD_INIT_WINDOW` 后、首次渲染前。[ANDROID]

### 使用时机

- 每帧 `vkAcquireNextImageKHR` 获取 image index。
- 每帧 `vkQueuePresentKHR` 提交显示。

### 销毁时机

- resize / rotation / surface 失效前需要 recreate。
- 应用退出或 surface 销毁时。
- 必须等依赖它的 command buffer 执行完成。[SPEC]

### in-flight 风险

- swapchain image 被提交后，直到 present 完成前不能再次 acquire 或写入。[SPEC]
- retired swapchain 仍可能被 GPU 使用，创建新 swapchain 后不要立即销毁旧 swapchain，除非确认 GPU idle。[SPEC]
- swapchain image view / framebuffer 随 swapchain 重建而重建，in-flight command buffer 可能引用旧对象。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- 销毁 swapchain 前，CPU 需等待 GPU idle 或所有 in-flight fence signal。[SPEC]
- Android 切后台时，应停止 acquire / submit / present，避免 CPU 在无效 swapchain 上阻塞。[ANDROID]

### GPU-GPU 同步

- `vkAcquireNextImageKHR` 的 `imageAvailableSemaphore` 必须被 graphics queue submit 等待。[SPEC]
- `vkQueueSubmit` 的 `renderFinishedSemaphore` 必须被 `vkQueuePresentKHR` 等待。[SPEC]
- 多 queue 时，present queue 与 graphics queue 之间的 semaphore 必须匹配。[SPEC]

### 资源访问同步

- swapchain image 初始 layout 为 `UNDEFINED` 或 `PRESENT_SRC_KHR`，render pass begin 或 barrier 需处理。[SPEC]
- 如果要在 render pass 外读取 swapchain image，需要正确的 image memory barrier。[SPEC]

---

## 11. Android 注意点

- Android 上 `VK_SUBOPTIMAL_KHR` 可能在横竖屏切换或 surface 尺寸变化时出现，应触发 recreate。[ANDROID]
- `APP_CMD_TERM_WINDOW` 后必须停止 acquire / present，否则可能 native crash。[ANDROID]
- `APP_CMD_INIT_WINDOW` 提供的新 `ANativeWindow` 需要重新创建 surface 和 swapchain。[ANDROID]
- 横竖屏切换时 `currentTransform` 可能变化，`preTransform` 应与之对齐以减少合成开销。[ANDROID]
- 某些 Android 设备在 `onPause` 后仍可能保留 swapchain，但 safest path 是暂停渲染并等待 resume 后重建。[HEUR]
- extent 为 0 时不要创建 swapchain，等待有效尺寸。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 避免每帧查询 surface capabilities / formats / present modes。[ENGINE]
- swapchain recreate 是高开销操作，应尽量减少频率。[ENGINE]

### GPU 侧

- `presentMode` 直接影响延迟与功耗：`IMMEDIATE` 可能有撕裂；`FIFO` 最稳但延迟高；`MAILBOX` 低延迟但可能增加 CPU/GPU 压力。[SPEC]
- `minImageCount` 越大，latency 越高，但可减少 CPU stall。[HEUR]
- `preTransform` 与 `currentTransform` 不一致时，compositor 可能做额外变换，增加功耗。[ANDROID]

### 移动端

- 移动端通常优先 `FIFO` 以省电，竞技类游戏可权衡 `MAILBOX`。[ENGINE]
- 避免频繁 recreate swapchain；Android rotation 应尽量复用资源，只重建尺寸相关对象。[ENGINE]

---

## 13. 专家经验

**经验**：
在 Android 工程中，建议把 swapchain recreate 设计为“暂停渲染 → 等待 idle → 销毁依赖资源 → 用 oldSwapchain 创建新 swapchain → 重建 image view / framebuffer / depth → 恢复渲染”的固定流程，不要零散处理。

**适用条件**：
Android Native 渲染，生命周期事件可稳定接收，存在横竖屏切换或分屏场景。

**不适用情况**：
桌面窗口尺寸固定、无需频繁 recreate 的场景；或已有 RenderGraph / 渲染框架自动处理 swapchain 生命周期。

**来源**：`[ANDROID][ENGINE]`

---

## 14. 相关 API 卡片

- `surface.md`
- `swapchain_recreate.md`
- `../03_command_buffer/command_buffer.md`
- `../03_command_buffer/queue_submit.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`
- `../08_synchronization/semaphore.md`
- `../08_synchronization/fence.md`

---

## 15. 需要回查官方文档的情况

1. 目标平台支持的 present mode 列表及行为差异。
2. `VkSurfaceCapabilitiesKHR` 中 `currentTransform`、`supportedTransforms`、`currentExtent` 的精确语义。
3. `VK_EXT_swapchain_maintenance1` 的启用条件与 retired swapchain 行为。
4. Android 特定设备在 pause / resume 时对 swapchain 的处理差异。
5. Device group / multi-GPU 场景下 `vkAcquireNextImage2KHR` 的使用。

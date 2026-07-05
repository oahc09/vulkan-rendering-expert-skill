# Android Surface / Swapchain 生命周期

## 核心思想

Android Vulkan 很多问题不是 Vulkan API 本身不会，而是 Surface / ANativeWindow / Swapchain 生命周期没有处理好。

核心链路：

```text
SurfaceView / TextureView / Native Window
→ ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images
→ Render
→ Present
→ Surface Destroy / Resize / Rotation
→ Swapchain Recreate
```

## Android 状态变化

需要重点处理：

```text
Surface Created
Surface Changed
Surface Destroyed
App Pause
App Resume
Window Resize
Rotation
VK_ERROR_OUT_OF_DATE_KHR
VK_SUBOPTIMAL_KHR
```

## 创建流程

```text
1. Java/Kotlin 层创建 SurfaceView / Surface。
2. Native 层获取 ANativeWindow。
3. 通过平台 extension 创建 VkSurfaceKHR。
4. 查询 surface capabilities / formats / present modes。
5. 创建 VkSwapchainKHR。
6. 获取 swapchain images。
7. 创建 swapchain image views。
8. 创建 depth image / offscreen attachment / framebuffer 或 dynamic rendering attachment。
```

## 重建流程

当窗口尺寸、方向、surface 状态变化或 present/acquire 返回 out-of-date 时：

```text
1. 暂停提交使用旧 swapchain 的 frame。
2. 等待相关 GPU 工作完成，至少等待 in-flight fence，必要时 device idle。
3. 销毁旧 swapchain 相关对象：
   - framebuffers
   - swapchain image views
   - depth image / view / memory
   - size-dependent offscreen images
   - descriptor 中引用的 size-dependent image，如有
4. 重新查询 surface capabilities。
5. 重新创建 swapchain。
6. 重新获取 images 并创建 image views。
7. 重建 depth / offscreen resources。
8. 重建 framebuffer 或更新 dynamic rendering attachment。
9. 重新录制 command buffer 或确保 command buffer 不引用旧对象。
```

## 哪些对象通常需要重建？

```text
Swapchain
Swapchain ImageViews
Depth Image / ImageView / Memory
Framebuffer，若使用传统 RenderPass
尺寸相关 Offscreen Render Target
尺寸相关 Descriptor Resource
CommandBuffer，若其中记录了旧 framebuffer / image view
Viewport / Scissor 状态，若非 dynamic state
Pipeline，若 viewport/scissor 固定且尺寸相关
```

## 高频错误

1. Surface destroyed 后继续 present。
2. ANativeWindow 已失效但 native renderer 仍持有旧指针。
3. `VK_ERROR_OUT_OF_DATE_KHR` 后继续渲染旧 swapchain。
4. 只重建 swapchain，忘记重建 image views / depth / framebuffer。
5. command buffer 仍引用旧 framebuffer。
6. in-flight frame 仍在使用旧 swapchain resources。
7. pause/resume 后没有恢复 surface / swapchain 状态。
8. rotation 后 extent 改变但 offscreen image 没重建。

## Debug 顺序

Android swapchain 相关 crash / 黑屏应按以下顺序排查：

```text
1. Java/Kotlin Surface 生命周期日志。
2. ANativeWindow 是否有效。
3. vkAcquireNextImageKHR 返回值。
4. vkQueuePresentKHR 返回值。
5. swapchain recreate 是否触发。
6. 旧 image view / framebuffer 是否仍被 command buffer 引用。
7. depth / offscreen / descriptor 是否跟随尺寸重建。
8. in-flight fence 是否等待。
9. RenderDoc / AGI 是否能抓到有效 frame。
```

## 专家规则

```text
Android 横竖屏、后台恢复、Surface 重建问题，不能只查 Vulkan 对象。
必须同时查 Android 生命周期、ANativeWindow 状态、Swapchain recreate 和 in-flight resource。
```

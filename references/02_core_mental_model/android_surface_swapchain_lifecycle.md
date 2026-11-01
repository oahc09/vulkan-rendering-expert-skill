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
2. 分开确认相关 submission 完成与 present 资源退役；submit fence / device idle 不单独证明 present wait semaphore 可销毁，见下方权威 workflow。
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


<a id="multi-instance-ownership"></a>
## 多实例所有权地图（C1）

前提：仅访问应用自有或系统正常授予的 Surface；Java + JNI + C++17 是参考接入方式，不要求重写已有引擎。Android API 34+ 是建议验收区间，不是整个 Skill 的最低版本。[ENGINE]

| owner 层 | 资源/身份 | 局部 Output A 关闭时 |
|---|---|---|
| Process | service、native registry、第三方进程级函数表 | 不能因一个 Engine 退出清空全局状态 |
| VkDevice / DeviceContext | allocator、queue 协调、资源缓存、pipeline | 仍有 B 使用则保留；DEVICE_LOST 影响同 device 全部用户 |
| RenderInstance / Engine | scene、时域历史、可见性、宿主暂停状态 | 只关闭该实例；历史不可跨实例无条件共享 |
| Output + generation | ANativeWindow、VkSurfaceKHR、swapchain、extent/color capabilities | 先确认停止访问旧 Surface，再按完成证据退休该代资源 |
| frame slot | command buffer、submit fence、acquire semaphore | 该输出独立索引，重用取决于该 slot 的真实完成 |
| swapchain image | VkImage、view、present wait semaphore | 使用 imageIndex 而非 frameIndex；销毁另需 present 退役证明 |
| source frame | AImage lease、AHB、所有消费者完成集合 | 不能 A 完成就归还 B 仍使用的输入 |

DeviceContext/RenderInstance 是工程示意名称，不是 Vulkan 类型。不要用一个 currentSurface、全局 frameIndex 或 renderFinished 数组覆盖所有输出。[ENGINE]

| 架构候选 | 收益 | 成本与约束 | 失效范围 |
|---|---|---|---|
| 共享 VkDevice | 可共享同 device 缓存/分配，减少重复对象 | queue host 操作按规则外部同步；调度公平，库的全局状态须审核 | device lost 要冻结该 device 全部实例，不能只重建 A swapchain |
| 独立 VkDevice | 生命周期、逻辑状态隔离 | 重复内存/pipeline；普通 Vulkan handle 不能跨 device 复用；第三方库可能仍进程级单例 | 一个逻辑 device 的失败不证明其他 device 健康，需分别检查；不承诺物理故障隔离 |

共享 queue 可采用单提交协调线程，也可符合外部同步的锁策略；这是架构选择，不是所有引擎必须单线程的规范。跨 device 资源只在明确外部资源协议/能力与寿命合同下评估。[SPEC][ENGINE]

每个输出独立查询 present support、extent、format/colorSpace、transform、image count；独立记录 visible、hostPaused、surfaceValid、deviceHealthy，提交条件取全部适用条件，不压成一个全局 pause。
[状态与确认协议](../05_workflows/04_android_integration/handle_android_lifecycle.md#multi-surface-lifecycle)是事件处理权威；
[媒体帧合同](../03_api_manual/04_buffer_image_memory/external_resource_interop.md#android-media-frame-contract)管共享输入。

来源（2026-11-01核对）：[WallpaperService多Engine](https://developer.android.com/reference/android/service/wallpaper/WallpaperService#onCreateEngine())、[SurfaceHolder.Callback](https://developer.android.com/reference/android/view/SurfaceHolder.Callback)、[WSI semaphore reuse](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)。没有真机执行证据。

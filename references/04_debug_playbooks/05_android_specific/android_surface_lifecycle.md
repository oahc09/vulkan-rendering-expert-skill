# Debug Playbook: Android Surface Lifecycle

## 0. 适用范围

### 适用

- Android Vulkan 在 SurfaceView / NativeActivity / ANativeWindow 场景下出现黑屏、crash、resize 异常。
- pause / resume 后 Vulkan 输出异常。
- 横竖屏切换后 swapchain 失效。
- Surface destroyed 后 native render thread 仍在运行。

### 不适用

- 纯桌面 Vulkan。
- 非 Android 平台的 swapchain 问题。
- 与平台 surface 无关的 descriptor / shader 错误。

---

## 1. 现象

常见表现：

- 首次进入正常，切后台回来黑屏。
- 横竖屏切换后 crash。
- Surface destroyed 后 native crash。
- `vkAcquireNextImageKHR` 或 `vkQueuePresentKHR` 返回 out-of-date。
- ANativeWindow 为 null 或已失效。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Surface destroyed 后 render thread 仍 present | logcat lifecycle 显示 surface destroyed | Surface / Render Thread |
| P0 | ANativeWindow 生命周期管理错误 | native window invalid / crash | ANativeWindow |
| P0 | swapchain 未随 surface changed 重建 | rotation 后黑屏 | Swapchain |
| P1 | pause/resume 状态机错误 | resume 后不恢复或重复创建 | App Lifecycle |
| P1 | extent 为 0 仍创建 swapchain | minimized / layout 未完成 | Swapchain |
| P2 | 旧资源被 command buffer 引用 | validation lifetime error | CommandBuffer / Fence |

---

## 3. 快速验证路径

1. 打印 Java/Kotlin Surface 生命周期。
2. 打印 native ANativeWindow acquire/release。
3. 打印 render thread start/stop。
4. 打印 acquire / present 返回值。
5. 打印 swapchain recreate 触发原因。
6. rotation / pause / resume 循环测试。
7. 使用 AGI / logcat 关联分析。

---

## 4. Vulkan 对象链路排查

```text
SurfaceView / SurfaceHolder
→ ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images / ImageViews
→ Render Loop
→ Present
→ Surface Destroy / Recreate
```

重点检查：

- Surface destroyed 时是否停止 render loop。
- ANativeWindow 是否正确 acquire / release。
- VkSurfaceKHR 是否与当前 native window 匹配。
- Swapchain 是否重建。
- CommandBuffer 是否重新录制。
- 旧资源是否等待 GPU 完成后销毁。

---

## 5. 高频根因

1. Surface destroyed 后 native render thread 继续调用 present。
2. ANativeWindow 被 release 后仍被使用。
3. surface changed 后没有 recreate swapchain。
4. pause 时没有暂停 GPU 提交。
5. resume 时重复创建 Vulkan 对象。
6. extent 为 0 时继续创建 swapchain。
7. command buffer 仍引用旧 framebuffer / image view。

---

## 6. 修复方案

### 最小修复

- Surface destroyed 时停止 render loop。
- ANativeWindow 失效时不再 acquire / present。
- surface changed 时触发 swapchain recreate。

### 稳定修复

- 建立 Android lifecycle 状态机：
  - NoSurface
  - SurfaceReady
  - SwapchainReady
  - Rendering
  - Paused
  - Destroyed
- render thread 根据状态机运行。
- 所有 surface-dependent resource 统一重建。

### 工程化修复

- Java/Kotlin 与 native 层建立明确事件队列。
- native render thread 不直接依赖 UI thread 临时状态。
- 建立 surface generation id，防止旧 surface 被使用。

---

## 7. 回归验证

- [ ] 首次进入正常。
- [ ] 横竖屏切换多次正常。
- [ ] 切后台 / 回前台正常。
- [ ] Surface destroyed 后无 native crash。
- [ ] Validation clean。
- [ ] logcat lifecycle 顺序清晰。

---

## 8. 相关 API 卡片

- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`

---

## 9. 工具证据

### logcat

关注：

- surfaceCreated
- surfaceChanged
- surfaceDestroyed
- onPause
- onResume
- native window acquire/release
- acquire/present return code

### AGI

关注：

- surface / swapchain frame
- GPU frame 是否继续提交
- resize 后 frame 是否恢复

---

## 10. Android 分支

本 Playbook 本身就是 Android 分支。  
如果使用 SurfaceView，需要重点检查 SurfaceHolder 生命周期。  
如果使用 NativeActivity，需要重点检查 native window 回调。

---

## 11. 不确定时如何处理

需要补充：

- Surface lifecycle log
- ANativeWindow 管理代码
- Vulkan surface/swapchain 创建代码
- render thread 状态机
- pause/resume 处理代码
- logcat / tombstone

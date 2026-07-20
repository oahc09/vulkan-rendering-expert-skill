# Workflow: Handle Android Lifecycle

> 文件建议路径：`handle_android_lifecycle.md`

---

## 0. 适用范围

### 适用

- Android 应用使用 Vulkan 渲染，需要正确处理 `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed`。
- 需要管理 `ANativeWindow`、`VkSurfaceKHR`、`VkSwapchainKHR`、command buffer、fence 的生命周期。
- 需要避免 rotation / resize / 切后台 / 切前台 导致的 `DEVICE_LOST` 或崩溃。

### 不适用

- 桌面平台（Windows / Linux）无 surface 销毁 / recreate 的场景。
- 使用 OpenGL ES 或 2D UI 框架（生命周期处理逻辑不同）。
- 完全由游戏引擎（如 Unity / Unreal）托管 lifecycle 的项目。

---

## 1. 任务目标

建立 Android lifecycle 与 Vulkan 对象生命周期的映射，确保：

```text
onSurfaceCreated
→ ANativeWindow acquire → VkSurfaceKHR create → Swapchain create → Render loop start

onPause
→ Stop render thread → Wait in-flight frames → Release swapchain-dependent resources

onResume
→ Recreate swapchain if needed → Resume render thread

onSurfaceDestroyed
→ Wait GPU idle → Destroy swapchain → Destroy surface → Release ANativeWindow
```

---

## 2. 输入条件

需要确认：

- Android 版本、设备 GPU（Adreno / Mali / PowerVR）。
- 是否使用 native Activity 或 Java/Kotlin Activity + `SurfaceView` / `TextureView` / `SurfaceHolder`。
- render thread 模型：单 render thread、render thread + worker threads、专用 compute thread。
- 是否使用多 buffering（双缓冲 / 三缓冲）以及 frame-in-flight 数量。
- 是否已有 swapchain recreate 处理（如 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`）。
- 是否存在跨 frame 资源（SSBO、storage image、fence、semaphore）需要在 pause 时保留。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已能在正常启动路径创建 swapchain 并呈现多帧。
- [ ] 已能在 `VK_ERROR_OUT_OF_DATE_KHR` 时手动 recreate swapchain。
- [ ] 已跟踪每帧的 fence 与 in-flight command buffer。
- [ ] 已记录 `ANativeWindow` 的 acquire / release 调用点。
- [ ] 已确认 `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed` 的触发顺序。

---

## 4. Vulkan 对象链路

```text
Android Activity
→ SurfaceHolder.Callback
→ ANativeWindow (Java Surface → native window)
→ vkCreateAndroidSurfaceKHR
→ VkSurfaceKHR
→ vkCreateSwapchainKHR
→ VkSwapchainImageKHR[]
→ Frame-in-flight Resources:
    VkCommandBuffer[]
    VkFence[]
    VkSemaphore[] (acquire / render complete)
→ vkQueuePresentKHR
→ onSurfaceDestroyed
→ vkDeviceWaitIdle
→ vkDestroySwapchainKHR
→ vkDestroySurfaceKHR
→ ANativeWindow_release
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| ANativeWindow | `ANativeWindow*` | Android Surface 的 native 句柄 | surface 回调期间 | 是（surface 重建时） |
| surface | `VkSurfaceKHR` | Vulkan surface | surface 存在期间 | 是 |
| swapchain | `VkSwapchainKHR` | 呈现图像 | surface 有效期间 | 是 |
| swapchain image | `VkImage` | 由 swapchain 持有 | swapchain 生命周期 | 是 |
| command buffer | `VkCommandBuffer` | 每帧录制 | frame-in-flight | 否（pool 通常保留） |
| fence | `VkFence` | 帧完成信号 | frame-in-flight | 否 |
| semaphore | `VkSemaphore` | acquire / render complete | frame-in-flight | 否 |
| depth image | `VkImage` | depth attachment | swapchain extent 绑定 | 是 |
| per-frame SSBO / UBO | `VkBuffer` | 每帧数据 | frame-in-flight | 否（尺寸不变时） |

设计说明：

- `ANativeWindow` 在 `onSurfaceCreated` 时 acquire，在 `onSurfaceDestroyed` 时 release；release 前必须确保不再使用关联的 `VkSurfaceKHR` [ANDROID]。
- `VkSurfaceKHR` 与 `VkSwapchainKHR` 随 surface 重建而销毁重建；frame-in-flight 的 fence/semaphore 通常可复用，但需等待全部完成 [SPEC]。
- depth image、swapchain-dependent frame buffer 等应在 swapchain recreate 时重建 [ENGINE]。

---

## 6. Pipeline / Descriptor 设计

本工作流主要涉及生命周期管理，pipeline / descriptor 设计按渲染管线复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 被分析 pass 的 binding | `COMBINED_IMAGE_SAMPLER` / `UNIFORM_BUFFER` / `STORAGE_BUFFER` | swapchain-independent 资源 | Vertex / Fragment / Compute |

设计说明：

- swapchain-independent descriptor（如 scene UBO、texture array）在 surface 重建时通常无需更新 [ENGINE]。
- swapchain-dependent descriptor（如 per-frame color attachment 作为 input attachment）在 swapchain recreate 后需重新绑定 [ENGINE]。
- pipeline layout 与 pipeline 通常不随 swapchain 重建而重建 [HEUR]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| acquire semaphore | swapchain image | `VK_IMAGE_LAYOUT_UNDEFINED` → `COLOR_ATTACHMENT_OPTIMAL` | render pass color attachment write |
| render pass color write | swapchain image | `COLOR_ATTACHMENT_WRITE` → `COLOR_ATTACHMENT_WRITE`；`COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` | present engine |
| onPause signal | frame fence | `vkWaitForFences` 等待 in-flight frame | 安全销毁 swapchain-dependent 资源 |
| onSurfaceDestroyed | all GPU work | `vkDeviceWaitIdle` | 安全 destroy surface / swapchain |

必须说明：

- `vkAcquireNextImageKHR` 返回的 semaphore 必须在同一帧的 submit 中等待 [SPEC]。
- present 前必须将 swapchain image transition 到 `VK_IMAGE_LAYOUT_PRESENT_SRC_KHR` [SPEC]。
- `onPause` 时应停止提交新帧，等待所有 in-flight fence 完成，再释放 swapchain-dependent 资源 [ANDROID]。
- `onSurfaceDestroyed` 前必须调用 `vkDeviceWaitIdle`，确保 GPU 不再访问 surface / swapchain image [SPEC]。
- 不要在 `vkDeviceWaitIdle` 期间持有 Android UI 线程锁，避免 ANR [ANDROID]。

---

## 8. 实现步骤

1. **建立 lifecycle 桥接**：
   - Java/Kotlin `SurfaceHolder.Callback` 中转发 `surfaceCreated` / `surfaceChanged` / `surfaceDestroyed` 到 native 层。
   - Activity `onPause` / `onResume` 同步转发到 native render thread 状态机 [ANDROID]。
2. **onSurfaceCreated**：
   - 从 `Surface` 获取 `ANativeWindow`（`ANativeWindow_fromSurface`），保存句柄。
   - 调用 `vkCreateAndroidSurfaceKHR` 创建 `VkSurfaceKHR` [SPEC]。
   - 查询 surface capabilities，创建 `VkSwapchainKHR` [SPEC]。
   - 创建 / 重建 depth image、framebuffer、swapchain-dependent descriptor [ENGINE]。
3. **启动 / 恢复 render thread**：
   - 设置 `renderingAllowed = true`，唤醒 render loop [ENGINE]。
4. **正常渲染帧**：
   - acquire image → 录制 command buffer → submit（等待 acquire semaphore，signal render complete semaphore）→ present [SPEC]。
5. **处理 out-of-date / suboptimal**：
   - `vkAcquireNextImageKHR` 或 `vkQueuePresentKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 时，停止当前帧，等待 GPU idle，recreate swapchain [SPEC]。
6. **onPause**：
   - 设置 `renderingAllowed = false`，通知 render thread 停止新帧提交 [ENGINE]。
   - render thread 等待所有 in-flight fence（`vkWaitForFences` with timeout）完成 [SPEC]。
   - 释放 swapchain-dependent 资源（depth image、framebuffer）；保留 device、pipeline、descriptor layout、fence/semaphore pool [ENGINE]。
7. **onResume**：
   - 若 surface 仍存在且 swapchain 有效，直接恢复 render thread [ENGINE]。
   - 若 surface 已变化（如先 `surfaceDestroyed` 再 `surfaceCreated`），等待新的 `onSurfaceCreated` 后再创建 swapchain [ANDROID]。
8. **onSurfaceDestroyed**：
   - 设置 `renderingAllowed = false`。
   - 调用 `vkDeviceWaitIdle` 等待 GPU 完成所有工作 [SPEC]。
   - 调用 `vkDestroySwapchainKHR` 销毁旧 swapchain（可传 oldSwapchain 给新 swapchain 加速，但 surface 已销毁时不行）[SPEC]。
   - 调用 `vkDestroySurfaceKHR` 销毁 surface [SPEC]。
   - 调用 `ANativeWindow_release` 释放 `ANativeWindow` [ANDROID]。
9. **rotation / resize**：
   - 通常触发 `surfaceDestroyed` → `surfaceCreated` → `surfaceChanged`；按上述路径重建。
   - 新 swapchain extent 为 0 时（某些 Android 版本在 transition 期间），暂停渲染直到非 0 [ANDROID]。
10. **错误处理**：
    - `vkDeviceWaitIdle` 超时：记录日志，避免强制销毁，必要时调用 `ANativeActivity_finish` [ANDROID]。
    - `DEVICE_LOST`：按 `../../04_debug_playbooks/02_crash_hang/device_lost.md` 处理。
11. **接入销毁路径**：
    - Activity `onDestroy` 时确保 `onSurfaceDestroyed` 已处理；再销毁 device、instance [ENGINE]。

---

## 9. Android 注意点

- `ANativeWindow` 必须在 Java `Surface` 有效期间持有；`Surface` 销毁后再使用 `ANativeWindow` 是未定义行为 [ANDROID]。
- `onSurfaceDestroyed` 可能在 `onPause` 之后或之前触发，需用状态机管理：只要 surface 不存在或 rendering 未允许，就不提交 [ANDROID]。
- 某些设备在切后台后会销毁 surface，但不会立即触发 `onDestroy`；此时应释放 swapchain 但保留其他资源以加速恢复 [ANDROID]。
- `vkQueuePresentKHR` 在 surface 已销毁后调用会触发 `VK_ERROR_SURFACE_LOST_KHR` 或 `DEVICE_LOST`；必须在提交前检查 surface 状态 [ANDROID]。
- rotation 时 `preTransform` 应匹配 `VkSurfaceCapabilitiesKHR::currentTransform`，避免 GPU 额外旋转开销 [ANDROID]。
- extent 为 0 的处理：在 `surfaceChanged` 收到 0x0 时暂停渲染，收到非 0 后再创建 swapchain [ANDROID]。
- 不要在 UI 线程调用 `vkDeviceWaitIdle` 或 `vkQueuePresentKHR`；所有 Vulkan submit 应在 render thread 执行 [ANDROID]。
- 多窗口 / 分屏模式下 surface size 可能频繁变化，需支持快速 swapchain recreate [ANDROID]。
- 建议在 Java/Kotlin 层记录每个 lifecycle 回调的时间戳与 surface 尺寸，便于与 native 层日志对齐排错 [GUIDE]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 swapchain / surface / semaphore 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：可 capture pause / resume / rotation 后的帧 [TOOL]。
- [ ] 截图 / 数值验证：lifecycle 切换后渲染结果正确，无黑屏、拉伸、闪屏。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 `VUID-vkAcquireNextImageKHR-*`、`VUID-vkQueuePresentKHR-*`、`VUID-vkDestroySurfaceKHR-*` 等错误；可输出 lifecycle 状态日志。
- [ ] 性能指标：
  - pause / resume 耗时在可接受范围（通常 < 100 ms，高端机 < 50 ms）；
  - rotation 后 frame time 恢复稳定；
  - 无 redundant swapchain recreate [TOOL]。
- [ ] resize / pause / resume / rotation 后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **surface 已销毁仍 present**：导致 `VK_ERROR_SURFACE_LOST_KHR` 或 `DEVICE_LOST` [ANDROID]。
2. **`ANativeWindow_release` 后仍使用 surface**：`VkSurfaceKHR` 底层引用已释放，后续 Vulkan 调用崩溃 [ANDROID]。
3. **onPause 未等待 in-flight frame**：destroy swapchain 时 fence 未 signaled，触发 validation error 或 crash [SPEC]。
4. **`vkDeviceWaitIdle` 阻塞 UI 线程**：导致 ANR [ANDROID]。
5. **swapchain recreate 时 extent 为 0**：`vkCreateSwapchainKHR` 失败或创建 0x0 swapchain [ANDROID]。
6. **rotation 未更新 preTransform**：GPU 额外旋转，frame time 增加 [ANDROID]。
7. **fence / semaphore 复用未等待**：in-flight frame 未完成就 reset fence 或 reuse semaphore，导致 hazard [SPEC]。
8. **depth image 未随 swapchain 重建**：新 extent 下 depth attachment 尺寸错误，validation error [SPEC]。
9. **compute queue 在 surface destroy 后仍提交**：compute 命令虽不使用 swapchain image，但若与 graphics 同 queue，仍可能因 surface lost 导致 device lost [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- Android 设备型号 / GPU / Android 版本。
- Activity 类型（NativeActivity / SurfaceView / TextureView）与 lifecycle 回调日志。
- `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed` 的触发顺序与时间戳。
- Validation Layer 完整报错。
- `adb logcat` 中 lifecycle 与 Vulkan 的交错日志。
- swapchain recreate 代码与 `vkCreateSwapchainKHR` 参数。
- frame-in-flight 数量、fence/semaphore 管理代码。

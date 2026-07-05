# Case: Pause Resume Black Screen

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Swapchain / Android / Lifecycle |
| 平台 | Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Android App 点击 Home 键、切换应用到后台、锁屏或息屏后再次回到前台，画面全黑或 frozen 在最后一帧；有时伴随 `VK_ERROR_OUT_OF_DATE_KHR`、`VK_ERROR_SURFACE_LOST_KHR` 或 device lost。问题在首次启动正常，pause / resume 后必现或高概率出现。

---

## 2. 初始上下文

- 平台：Android。
- 使用 `ANativeWindow` / `Surface` 创建 Vulkan surface 和 swapchain。
- 渲染线程与 Java UI 线程分离。
- 在 `onPause` / `onResume` 或 `onStop` / `onStart` 中处理生命周期。
- 多 frame-in-flight，使用 fence 和 semaphore 管理帧同步。

---

## 3. 初始误判

最初容易怀疑：

```text
GPU 挂起或驱动在后台被回收；
渲染线程死锁；
Activity 重建导致 Native 层状态丢失；
swapchain 只是 suboptimal，recreate 一下就好；
fence 等待超时是因为 GPU 没响应。
```

但 log 显示 `onPause` 时 surface 已被销毁，`onResume` 后创建了新 surface，而渲染线程仍在等待旧 fence 或继续用旧 swapchain 调用 `vkAcquireNextImageKHR`。最终发现 pause / resume 后没有完整重建 surface、swapchain 和 frame-in-flight 状态。

---

## 4. 排查路径

1. 检查 `android_app_cmd` 或 Activity 生命周期回调中是否处理了 `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` / `APP_CMD_PAUSE` / `APP_CMD_RESUME`。
2. 检查 `onPause` 时是否调用了 `vkDeviceWaitIdle` 并停止渲染线程提交新帧。
3. 检查旧 surface / swapchain 是否在 pause 时被销毁。
4. 检查 `onResume` 时是否用新的 `ANativeWindow` 创建了新的 `VkSurfaceKHR`。
5. 检查 resume 后是否重新创建了 swapchain、framebuffers、command buffers 和 descriptors。
6. 检查 frame-in-flight 的 fence 状态：旧 fence 是否被 reset，是否有未 signal 的 fence 导致 `vkWaitForFences` 永久阻塞。
7. 检查 `vkAcquireNextImageKHR` 的返回值，是否对 `VK_ERROR_SURFACE_LOST_KHR` / `VK_ERROR_OUT_OF_DATE_KHR` 做了处理。

---

## 5. 关键证据

### Validation Layer

- 典型 VUID / 错误（`[SPEC]` / `[ANDROID]`）：
  - `VUID-vkAcquireNextImageKHR-surface-01257`：surface 已改变或无效。
  - `VUID-vkQueuePresentKHR-surface-01273`：presentation 的 surface 状态不再匹配 swapchain。
  - `VK_ERROR_SURFACE_LOST_KHR`：`VkSurfaceKHR` 已失效，必须重新创建。
  - `VK_ERROR_OUT_OF_DATE_KHR`：swapchain 与 surface 不再兼容，必须 recreate。

### RenderDoc / AGI

- 观察到：
  - pause 前 capture 正常；resume 后 capture 中没有 `vkQueueSubmit` 或 `vkQueuePresentKHR`。
  - 或 resume 后仍有 `vkAcquireNextImageKHR` 但返回 `VK_ERROR_OUT_OF_DATE_KHR` 且未处理。
  - 关键 resource：ANativeWindow / Surface、VkSurfaceKHR、swapchain、frame fence。

### Log / Code

- 返回值：
  - `vkAcquireNextImageKHR` 返回 `VK_ERROR_SURFACE_LOST_KHR` 或 `VK_ERROR_OUT_OF_DATE_KHR`。
  - `vkWaitForFences` 在 resume 后阻塞，因为旧 fence 从未被 signal（最后一帧没有成功 submit）。
- 生命周期日志：
  - `onPause`：surface destroyed，但渲染线程未停止。
  - `onResume`：new surface created，但 swapchain 仍是旧 handle。
- 关键代码：

```text
// 错误示例：resume 后未重建 surface/swapchain
void onResume() {
    // 只恢复了 Activity，没有重新创建 VkSurfaceKHR / swapchain
    resumeRenderThread();
}

// 错误示例：旧 fence 未 reset 导致永久等待
void renderFrame() {
    vkWaitForFences(device, 1, &frameFence, VK_TRUE, UINT64_MAX); // 上一帧未 submit，fence 永不被 signal
    vkResetCommandBuffer(cmd, 0);
    // ...
}
```

---

## 6. 根因

根因：Android pause / resume 导致原 `ANativeWindow` / `VkSurfaceKHR` 和 swapchain 失效，但渲染线程继续使用旧 surface / swapchain，或 frame-in-flight 的 fence 处于未 signal 状态，导致后续帧无法提交和呈现。

---

## 7. 修复方案

### 最小修复

- 在 `onPause` / `APP_CMD_TERM_WINDOW` 中调用 `vkDeviceWaitIdle`，停止渲染循环，销毁 swapchain、framebuffers、surface（按需），并记录暂停状态。
- 在 `onResume` / `APP_CMD_INIT_WINDOW` 中等待新的 `ANativeWindow` 就绪后，重新创建 `VkSurfaceKHR`、swapchain、framebuffers 和必要的 descriptors。
- resume 后重置所有 frame-in-flight fence 为 signaled 状态（或重新创建 fence），避免渲染线程因等待旧 fence 而阻塞。
- resume 后的第一帧重新走完整的 `acquire → record → submit → present` 流程。

### 稳定修复

- 建立 Android lifecycle 状态机：`Running` / `Paused` / `SurfaceLost` / `Resuming` / `Ready`。
- 渲染线程每帧检查状态：只有 `Ready` 时才执行 acquire / submit / present。
- 将 surface / swapchain / framebuffers 封装为可重建的 `SwapchainContext`，lifecycle 变化时自动重建。
- 对 `vkAcquireNextImageKHR` / `vkQueuePresentKHR` 的所有返回值做分支处理，触发 recreate 或等待。

### 工程化修复

- 使用 Android Game Development Library 或自研 lifecycle 框架统一处理 surface 事件。
- 在 CI 中加入自动化 pause / resume / rotation / 锁屏测试，用 AGI 或 screenshot 对比验证。
- 增加运行时 telemetry：记录 lifecycle 事件、swapchain recreate 次数、fence wait timeout 次数。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] Home 键切出再切回后画面正常。
- [ ] 锁屏 / 亮屏后画面正常。
- [ ] 多任务切换、分屏、折叠屏展开后画面正常。
- [ ] RenderDoc / AGI 中 resume 后能看到完整的 submit 和 present。
- [ ] 连续 pause / resume 10 次以上无黑屏、无 crash。
- [ ] 多 frame-in-flight 下 fence 无永久阻塞。

---

## 9. 经验抽象

Android 的 surface 是易失资源，`ANativeWindow` 在 pause 后可能失效，resume 后一定需要重新建立 Vulkan surface 和 swapchain。pause / resume 的处理不能只停渲染线程，必须同步处理：

```text
pause:  wait idle → 停止提交 → 销毁 swapchain / surface → 标记暂停
resume: 获取新 surface → 重建 swapchain → 重建依赖资源 → 重置 fence → 恢复提交
```

任何一步遗漏都会在 resume 后表现为黑屏或 device lost。

---

## 10. 预防规则

1. `onPause` 时必须 `vkDeviceWaitIdle` 并停止所有 queue submit。
2. 旧 `VkSurfaceKHR` 和 swapchain 必须在 pause 后销毁或标记失效，禁止 resume 后直接使用。
3. `onResume` 必须等待新的 `ANativeWindow` 后再创建 surface 和 swapchain。
4. resume 后必须重置或重新创建 frame-in-flight fence，避免等待未 signal 的旧 fence。
5. `vkAcquireNextImageKHR` / `vkQueuePresentKHR` 的 `VK_ERROR_SURFACE_LOST_KHR` / `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 必须显式处理。
6. 渲染线程必须受 lifecycle 状态机控制，非 Ready 状态禁止提交。

---

## 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`

---

## 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`
- `../../05_workflows/04_android_integration/pause_resume_render_thread.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/android_validation_agi_workflow.md`

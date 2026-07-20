# Cases: Swapchain / Android

> 合并自 4 个原 case 文件。关键词: android, rotation, surface, pause-resume, extent-zero

---

## Case: Android Rotation Uses Old Swapchain ImageView

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Android / Swapchain / Lifecycle |
| 平台 | Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Android 设备横竖屏切换后，Vulkan 画面黑屏或 native crash。  
首次进入 App 渲染正常。  
rotation 后 `vkQueuePresentKHR` 或 command buffer 执行阶段出现异常。

---

### 2. 初始上下文

- Android SurfaceView + Native Vulkan。
- 使用 swapchain image view 作为 render target。
- 使用 framebuffer 或 dynamic rendering attachment。
- 横竖屏切换触发 surface changed。
- 工程中有 swapchain recreate，但不完整。

---

### 3. 初始误判

最初容易怀疑：

```text
Android Surface 回调顺序异常；
Vulkan device 丢失；
shader 重新编译失败；
present mode 不兼容。
```

但 logcat 显示 Surface 已经 changed，swapchain 也重新创建了。  
最终发现 command buffer 或 framebuffer 仍引用旧 swapchain image view。

---

### 4. 排查路径

1. 打印 surface created / changed / destroyed 日志。
2. 打印 acquire / present 返回值。
3. 检查 swapchain recreate 是否触发。
4. 检查新 swapchain image count / extent。
5. 检查 image view 是否重新创建。
6. 检查 framebuffer / dynamic rendering attachment 是否重新绑定新 image view。
7. 检查 command buffer 是否重新录制。
8. 检查 in-flight command buffer 是否仍引用旧资源。
9. 用 AGI / RenderDoc 查看 resize 后 frame resource。

---

### 5. 关键证据

### Validation Layer

可能出现：

- destroyed object used
- framebuffer / image view invalid
- command buffer references invalid object
- render pass / framebuffer mismatch

### AGI / logcat

观察到：

- Surface changed 已触发。
- 新 swapchain extent 正确。
- 旧 image view handle 仍出现在 command buffer 或 framebuffer 链路中。

### Code

关键问题：

```text
recreateSwapchain() 只重建了 VkSwapchainKHR，没有重建 framebuffer 或重新录制 command buffer。
```

---

### 6. 根因

根因：Android 横竖屏切换后 swapchain image view 已失效，但 framebuffer / command buffer / descriptor 仍引用旧 swapchain image view，导致渲染或 present 阶段使用无效资源。

---

### 7. 修复方案

### 最小修复

- swapchain recreate 时重建 image views。
- 重建 framebuffer 或 dynamic rendering attachment。
- 重新录制 command buffer。
- 更新引用尺寸相关 image 的 descriptor。
- recreate 前等待 in-flight GPU work 完成。

### 稳定修复

- 建立 swapchain-dependent resource group。
- 统一管理：
  - swapchain
  - swapchain image view
  - depth image
  - framebuffer
  - offscreen image
  - command buffer
  - descriptor
- 每次 surface extent 变化时整组重建。

### 工程化修复

- 引入 resource generation id。
- command buffer 录制时绑定当前 generation。
- 运行时 assert 禁止旧 generation 资源被提交。

---

### 8. 修复后验证

- [ ] 横竖屏切换多次不 crash。
- [ ] Validation clean。
- [ ] AGI / RenderDoc 中没有旧 image view。
- [ ] framebuffer / attachment 尺寸正确。
- [ ] command buffer 已重录。
- [ ] pause / resume 后仍正常。

---

### 9. 经验抽象

Swapchain recreate 不是只重建 `VkSwapchainKHR`。  
所有尺寸相关、引用 swapchain image view 的对象都必须一起处理。

---

### 10. 预防规则

1. 所有 swapchain-dependent resources 必须集中管理。
2. command buffer 中不能长期固化旧 framebuffer / image view。
3. resize / rotation 后必须重录 command buffer。
4. descriptor 若引用 screen-sized offscreen image，必须更新。
5. recreate 前必须等待旧 GPU work 完成。

---

### 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

### 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/integrate_surfaceview_anativewindow.md`


---

## Case: Extent Zero Swapchain Create

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Swapchain / Surface / Resize |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

窗口最小化、Android surface 尚未准备好、或 display scale 变化瞬间，`vkCreateSwapchainKHR` 返回 `VK_ERROR_VALIDATION_FAILED_EXT` 或 crash；有时表现为 swapchain 创建成功但后续 `vkAcquireNextImageKHR` 异常。问题在窗口正常大小时不出现，只在 extent 为 0 或极小时触发。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android，常见于窗口最小化或 Android `onResume` 早期。
- 使用 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 获取 surface capabilities。
- 直接以 `currentExtent` 作为 `VkSwapchainCreateInfoKHR.imageExtent`。
- 没有处理 `currentExtent.width == 0 || currentExtent.height == 0` 的情况。
- 可能在 resize 回调中立即触发 swapchain recreate。

---

### 3. 初始误判

最初容易怀疑：

```text
swapchain create info 的 format / present mode 不合法；
旧的 swapchain 没有正确传递或销毁；
surface 本身创建失败；
gpu memory 不足；
驱动 bug 在特定尺寸下崩溃。
```

但 format 和 present mode 此前一直正常，surface 创建成功。最终发现是 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回的 `currentExtent` 为 0，代码未做保护直接传入 `vkCreateSwapchainKHR`。

---

### 4. 排查路径

1. 在调用 `vkCreateSwapchainKHR` 前打印 `surfaceCapabilities.currentExtent`。
2. 检查 `currentExtent` 是否为特殊值 `0xFFFFFFFF`（需要自行选择 extent）。
3. 检查窗口最小化、Android surface 创建早期、或 resize 回调瞬间的 extent。
4. 检查 `vkCreateSwapchainKHR` 的返回值和 Validation Layer 输出。
5. 检查代码是否对 `imageExtent.width` 和 `imageExtent.height` 做了 > 0 校验。
6. 检查最小化或 surface 不可见时渲染循环是否仍在尝试创建 swapchain。

---

### 5. 关键证据

### Validation Layer

- 典型 VUID（`[SPEC]`）：
  - `VUID-VkSwapchainCreateInfoKHR-imageExtent-01274`：`imageExtent.width` 和 `imageExtent.height` 必须大于 0，且不超过 `maxImageExtent`。
  - `VUID-VkSwapchainCreateInfoKHR-imageExtent-01275` / `01276`：width / height 必须在 `minImageExtent` 和 `maxImageExtent` 之间。
- Message 通常会直接指出 `imageExtent` 的非法值。

### RenderDoc / AGI

- 观察到：
  - Capture 中看不到 swapchain 创建成功，或创建参数中 extent 为 0。
  - 若 crash 发生在创建后，Texture Viewer 中没有 swapchain image。
- 关键 resource：`VkSurfaceCapabilitiesKHR`、swapchain create info。

### Log / Code

- 返回值：
  - `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回 `VK_SUCCESS`，但 `currentExtent = {0, 0}`。
  - `vkCreateSwapchainKHR` 返回 `VK_ERROR_VALIDATION_FAILED_EXT` 或触发 debug messenger 报错。
- 关键代码：

```text
// 错误示例：未校验 extent
VkSurfaceCapabilitiesKHR caps;
vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physDevice, surface, &caps);

VkSwapchainCreateInfoKHR sci{};
sci.imageExtent = caps.currentExtent; // 可能为 {0, 0}
// ...
vkCreateSwapchainKHR(device, &sci, nullptr, &swapchain);
```

---

### 6. 根因

根因：在 surface extent 为 0 或超出允许范围时直接调用 `vkCreateSwapchainKHR`，违反了 swapchain image extent 必须大于 0 的规范约束。

---

### 7. 修复方案

### 最小修复

- 在调用 `vkCreateSwapchainKHR` 前检查 `surfaceCapabilities.currentExtent.width > 0 && height > 0`。
- 若 extent 为 0，跳过该帧渲染，等待窗口恢复或 surface 就绪后再次尝试创建。
- 若 `currentExtent` 为 `0xFFFFFFFF`，根据窗口 / surface 尺寸在 `[minImageExtent, maxImageExtent]` 范围内选择合适的 extent。

### 稳定修复

- 在 swapchain manager 中引入 `Ready` / `NotReady` 状态：extent 为 0 时标记 `NotReady`，暂停 acquire / submit / present。
- 监听窗口 resize / surface 变化事件，仅在 extent 有效时触发 recreate。
- 对 `vkCreateSwapchainKHR` 的输入做前置断言：width > 0、height > 0、在 min/max 范围内。

### 工程化修复

- 在窗口系统抽象层中统一处理“surface not ready”状态，向上层返回明确的枚举值。
- 在 CI 中加入窗口最小化 / 恢复自动化测试，验证渲染循环不会 crash。
- Android 端在 `onResume` 中等待 `ANativeWindow` 尺寸有效后再创建 swapchain。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] 窗口最小化时不再调用 `vkCreateSwapchainKHR`，也不会 crash。
- [ ] 窗口从最小化恢复后自动创建 swapchain 并恢复渲染。
- [ ] Android `onResume` 早期 surface 尺寸为 0 时能正确等待。
- [ ] 连续多次最小化 / 恢复或 split-screen 切换稳定。
- [ ] `vkCreateSwapchainKHR` 调用前 extent 断言通过。

---

### 9. 经验抽象

`vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回成功并不代表当前可以创建 swapchain。必须检查 `currentExtent` 的有效性：

```text
currentExtent == {0, 0}      → surface 未就绪，不能创建 swapchain
currentExtent == {0xFFFFFFFF, 0xFFFFFFFF} → 需要自行选择 extent
否则                        → 可以直接使用 currentExtent
```

任何跳过该检查的实现都会在窗口生命周期边缘情况下崩溃。

---

### 10. 预防规则

1. 每次创建 swapchain 前必须断言 `imageExtent.width > 0 && imageExtent.height > 0`。
2. 当 surface extent 为 0 时，必须暂停渲染循环而不是强行创建 swapchain。
3. 处理 `currentExtent` 为 `0xFFFFFFFF` 的情况，在 `minImageExtent` 和 `maxImageExtent` 之间选择合适值。
4. resize / 最小化 / 恢复事件必须经过去抖和有效性检查后再触发 swapchain recreate。
5. Android `onResume` 中必须等待 `ANativeWindow` 尺寸有效后再创建 Vulkan surface 和 swapchain。

---

### 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

### 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`


---

## Case: Pause Resume Black Screen

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Swapchain / Android / Lifecycle |
| 平台 | Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Android App 点击 Home 键、切换应用到后台、锁屏或息屏后再次回到前台，画面全黑或 frozen 在最后一帧；有时伴随 `VK_ERROR_OUT_OF_DATE_KHR`、`VK_ERROR_SURFACE_LOST_KHR` 或 device lost。问题在首次启动正常，pause / resume 后必现或高概率出现。

---

### 2. 初始上下文

- 平台：Android。
- 使用 `ANativeWindow` / `Surface` 创建 Vulkan surface 和 swapchain。
- 渲染线程与 Java UI 线程分离。
- 在 `onPause` / `onResume` 或 `onStop` / `onStart` 中处理生命周期。
- 多 frame-in-flight，使用 fence 和 semaphore 管理帧同步。

---

### 3. 初始误判

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

### 4. 排查路径

1. 检查 `android_app_cmd` 或 Activity 生命周期回调中是否处理了 `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` / `APP_CMD_PAUSE` / `APP_CMD_RESUME`。
2. 检查 `onPause` 时是否调用了 `vkDeviceWaitIdle` 并停止渲染线程提交新帧。
3. 检查旧 surface / swapchain 是否在 pause 时被销毁。
4. 检查 `onResume` 时是否用新的 `ANativeWindow` 创建了新的 `VkSurfaceKHR`。
5. 检查 resume 后是否重新创建了 swapchain、framebuffers、command buffers 和 descriptors。
6. 检查 frame-in-flight 的 fence 状态：旧 fence 是否被 reset，是否有未 signal 的 fence 导致 `vkWaitForFences` 永久阻塞。
7. 检查 `vkAcquireNextImageKHR` 的返回值，是否对 `VK_ERROR_SURFACE_LOST_KHR` / `VK_ERROR_OUT_OF_DATE_KHR` 做了处理。

---

### 5. 关键证据

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

### 6. 根因

根因：Android pause / resume 导致原 `ANativeWindow` / `VkSurfaceKHR` 和 swapchain 失效，但渲染线程继续使用旧 surface / swapchain，或 frame-in-flight 的 fence 处于未 signal 状态，导致后续帧无法提交和呈现。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean。
- [ ] Home 键切出再切回后画面正常。
- [ ] 锁屏 / 亮屏后画面正常。
- [ ] 多任务切换、分屏、折叠屏展开后画面正常。
- [ ] RenderDoc / AGI 中 resume 后能看到完整的 submit 和 present。
- [ ] 连续 pause / resume 10 次以上无黑屏、无 crash。
- [ ] 多 frame-in-flight 下 fence 无永久阻塞。

---

### 9. 经验抽象

Android 的 surface 是易失资源，`ANativeWindow` 在 pause 后可能失效，resume 后一定需要重新建立 Vulkan surface 和 swapchain。pause / resume 的处理不能只停渲染线程，必须同步处理：

```text
pause:  wait idle → 停止提交 → 销毁 swapchain / surface → 标记暂停
resume: 获取新 surface → 重建 swapchain → 重建依赖资源 → 重置 fence → 恢复提交
```

任何一步遗漏都会在 resume 后表现为黑屏或 device lost。

---

### 10. 预防规则

1. `onPause` 时必须 `vkDeviceWaitIdle` 并停止所有 queue submit。
2. 旧 `VkSurfaceKHR` 和 swapchain 必须在 pause 后销毁或标记失效，禁止 resume 后直接使用。
3. `onResume` 必须等待新的 `ANativeWindow` 后再创建 surface 和 swapchain。
4. resume 后必须重置或重新创建 frame-in-flight fence，避免等待未 signal 的旧 fence。
5. `vkAcquireNextImageKHR` / `vkQueuePresentKHR` 的 `VK_ERROR_SURFACE_LOST_KHR` / `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 必须显式处理。
6. 渲染线程必须受 lifecycle 状态机控制，非 Ready 状态禁止提交。

---

### 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`

---

### 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`
- `../../05_workflows/04_android_integration/pause_resume_render_thread.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/android_validation_agi_workflow.md`


---

## Case: Surface Destroyed But Render Thread Still Presents

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Android / Surface / Crash |
| 平台 | Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Android App 切后台或销毁 Surface 后 native crash。  
logcat 中可以看到 `surfaceDestroyed` 已触发，但 render thread 仍在调用 acquire / submit / present。

---

### 2. 初始上下文

- Java/Kotlin 使用 SurfaceView。
- Native 层有独立 render thread。
- Surface 生命周期通过回调传到 native。
- Vulkan swapchain 依赖 ANativeWindow。
- pause / resume 与 surface destroyed 顺序不稳定。

---

### 3. 初始误判

最初容易怀疑：

```text
Vulkan driver bug；
swapchain recreate 不完整；
device lost；
present mode 不兼容。
```

但 logcat 证明 Surface 已 destroyed，render thread 仍在 present，说明核心是 Android 生命周期与 native render thread 状态机问题。

---

### 4. 排查路径

1. 打印 SurfaceView 生命周期。
2. 打印 native render thread 状态。
3. 打印 ANativeWindow acquire / release。
4. 打印 acquire / present 返回值。
5. 检查 surfaceDestroyed 是否通知 native。
6. 检查 render loop 是否能被安全停止。
7. 检查 old swapchain 是否在 GPU 完成后销毁。

---

### 5. 关键证据

### Validation Layer

可能不一定能捕获所有平台生命周期错误。

### logcat

关键证据：

```text
surfaceDestroyed
native render loop still running
vkQueuePresentKHR called after surface destroyed
```

### Native Crash Stack

可能出现在：

- present
- acquire
- swapchain
- window / surface 相关 native 调用

---

### 6. 根因

根因：Android Surface destroyed 后，native render thread 没有及时停止，仍继续使用依赖旧 ANativeWindow / swapchain 的资源进行 acquire / present，导致 native crash。

---

### 7. 修复方案

### 最小修复

- `surfaceDestroyed` 时设置 renderPaused / surfaceInvalid。
- render thread 立即停止 acquire / submit / present。
- 等待 in-flight GPU work。
- 销毁 swapchain-dependent resources。
- release ANativeWindow。

### 稳定修复

- 建立 Android lifecycle 状态机：
  ```text
  NoSurface
  → SurfaceReady
  → SwapchainReady
  → Rendering
  → Paused
  → SurfaceDestroyed
  ```
- render thread 只在 `Rendering` 状态提交 GPU work。
- Surface destroyed 和 App pause 都能安全进入非渲染状态。

### 工程化修复

- Java/Kotlin → native 使用事件队列。
- render thread 统一消费 lifecycle event。
- ANativeWindow 使用引用计数或明确 ownership。
- 所有 surface-dependent resources 挂到 surface generation。

---

### 8. 修复后验证

- [ ] 切后台不 crash。
- [ ] surfaceDestroyed 后没有 present 调用。
- [ ] Surface recreated 后能恢复渲染。
- [ ] 横竖屏切换正常。
- [ ] logcat 状态机清晰。
- [ ] AGI 中不会看到 destroyed surface 后继续提交。

---

### 9. 经验抽象

Android Vulkan 稳定性问题不能只看 Vulkan API。  
Surface / ANativeWindow 生命周期和 render thread 状态机是同等重要的渲染链路组成部分。

---

### 10. 预防规则

1. Surface destroyed 后 render thread 必须停止提交。
2. ANativeWindow release 后不能再被任何 Vulkan 路径使用。
3. Surface lifecycle event 必须进入 native 状态机。
4. pause/resume 不能和 surface lifecycle 混用成单一布尔值。
5. 所有 surface-dependent resource 必须集中销毁和重建。

---

### 11. 关联 API 卡片

- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`

---

### 13. 关联 Workflow

- `../../05_workflows/04_android_integration/integrate_surfaceview_anativewindow.md`
- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`


---

# Workflow: Pause Resume Render Thread

> 文件建议路径：`pause_resume_render_thread.md`

---

## 0. 适用范围

### 适用

- Android 应用使用独立 render thread 提交 Vulkan 命令。
- 需要在 `onPause` 时安全停止渲染、在 `onResume` 时恢复渲染。
- 需要处理 in-flight frame、避免 `DEVICE_LOST`、避免 ANR。
- render thread 与 UI thread / compute thread / IO thread 有交互。

### 不适用

- 渲染直接在 UI thread 同步完成的简单应用。
- 使用外部引擎已内置 lifecycle 管理的项目。
- 无需在 pause 时保留 GPU 状态的单帧应用。

---

## 1. 任务目标

设计 render thread 的 pause / resume 状态机，确保：

```text
onPause
→ signal stop → render thread finish current frame → wait fences → block new acquire/present

onResume
→ signal resume → recreate swapchain if needed → restart render loop

onSurfaceDestroyed
→ stop render thread → wait all fences → idle device → destroy swapchain/surface
```

---

## 2. 输入条件

需要确认：

- render thread 模型：单线程渲染、渲染 + 工作线程、专用 compute queue。
- frame-in-flight 数量（2 / 3 / N）。
- fence 管理策略：per-frame fence、per-submit fence、timeline semaphore。
- 是否存在异步 upload / compute 提交需要在 pause 时同步。
- 是否使用 `std::condition_variable` / `std::atomic` / `std::thread` 或平台线程 API。
- `onPause` / `onResume` 期望的最大停顿时间（避免 ANR）。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已能在正常路径渲染多帧且无 hazard。
- [ ] 已跟踪每帧的 fence 与 in-flight command buffer。
- [ ] 已确认 render thread 的启动 / 停止 / 唤醒机制。
- [ ] 已确认 `onPause` / `onResume` 与 surface 事件的时序。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
UI Thread
→ Lifecycle Callback (onPause/onResume/onSurfaceDestroyed)
→ Atomic State + Condition Variable
→ Render Thread
    → Check pause signal
    → Finish current frame recording
    → vkQueueSubmit
    → vkQueuePresentKHR
    → vkWaitForFences (all in-flight frames)
    → Block on condition variable or exit loop
→ GPU
    → Complete in-flight commands
    → Signal fences
→ UI Thread / Resume
    → Recreate swapchain if needed
    → Signal resume
    → Render Thread restarts loop
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| render thread | `std::thread` | 提交 Vulkan 命令 | 应用运行期间 | 否 |
| pause/resume condition | `std::atomic<bool>` / `std::condition_variable` | 线程间状态同步 | 应用运行期间 | 否 |
| frame fence | `VkFence` | 每帧 GPU 完成信号 | frame-in-flight | 否 |
| per-frame command buffer | `VkCommandBuffer` | 每帧录制 | frame-in-flight | 否（pool 保留） |
| swapchain | `VkSwapchainKHR` | 呈现 | surface 有效期间 | 是 |
| surface | `VkSurfaceKHR` | 窗口系统接口 | surface 存在期间 | 是 |
| per-frame SSBO / UBO | `VkBuffer` | 每帧 uniform / storage | frame-in-flight | 否（尺寸不变时） |

设计说明：

- fence 与 command buffer 是 frame-in-flight 的核心；pause 时必须等待全部 fence 以避免资源被 GPU 仍在使用 [SPEC]。
- render thread 本身不销毁，只是阻塞在 condition variable 上；resume 时直接唤醒，减少 thread 创建开销 [ENGINE]。
- swapchain / surface 在 `onSurfaceDestroyed` 时销毁，而不是在 `onPause` 时销毁 [ANDROID]。

---

## 6. Pipeline / Descriptor 设计

本工作流主要关注线程生命周期，pipeline / descriptor 设计按渲染管线复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 被分析 pass 的 binding | `COMBINED_IMAGE_SAMPLER` / `UNIFORM_BUFFER` / `STORAGE_BUFFER` | swapchain-independent 资源 | Vertex / Fragment / Compute |

设计说明：

- pause / resume 不应导致 pipeline / descriptor layout 重建；这些对象通常与 surface 无关 [ENGINE]。
- per-frame descriptor set 在 resume 后继续使用，但需确认其引用的 buffer/image 在 pause 期间未被释放 [HEUR]。
- 若 descriptor 引用了 swapchain-dependent image view（如 input attachment），recreate swapchain 后必须重新更新 descriptor [ENGINE]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| render thread submit | command buffer | `vkQueueSubmit` 等待 acquire semaphore，signal render complete semaphore | GPU execution |
| GPU execution | frame fence | fence signaled | render thread `vkWaitForFences` |
| pause signal | render thread | 停止新 acquire/present，完成当前 submit | safe wait for fences |
| resume signal | render thread | 重新允许 acquire/present | swapchain recreate if needed |
| surface destroyed | all GPU work | `vkDeviceWaitIdle` | safe destroy swapchain/surface |

必须说明：

- `onPause` 时应先设置 `renderingAllowed = false`，让 render thread 自然结束当前帧，而不是在任意位置中断 [ENGINE]。
- 当前帧 submit 后，必须等待所有 in-flight fence（`vkWaitForFences`）完成，才能安全释放 swapchain-dependent 资源 [SPEC]。
- `vkDeviceWaitIdle` 可在 `onSurfaceDestroyed` 使用，但 `onPause` 通常只需等待 fence；`vkDeviceWaitIdle` 会强制所有 queue idle，可能增加 pause 耗时 [HEUR]。
- 等待 fence 时设置合理 timeout（如 1s），超时时记录日志并视为错误，避免无限阻塞 [ENGINE]。

---

## 8. 实现步骤

1. **定义 render thread 状态机**：
   - `State::Running`：正常渲染。
   - `State::Pausing`：收到 pause 信号，完成当前帧后进入 Paused。
   - `State::Paused`：阻塞等待 resume。
   - `State::Resuming`：收到 resume，检查 surface/swapchain，进入 Running [ENGINE]。
2. **lifecycle 回调转发**：
   - `onPause`：UI thread 设置 `requestPause = true`，通知 render thread [ANDROID]。
   - `onResume`：UI thread 设置 `requestResume = true`，通知 render thread [ANDROID]。
   - `onSurfaceDestroyed`：UI thread 设置 `requestPause = true` 并等待 render thread 进入 Paused，再调用 `vkDeviceWaitIdle` 并销毁 swapchain/surface [ANDROID]。
3. **render loop 结构**：

   ```cpp
   while (!exitRequested) {
       if (state == Paused) {
           waitOnResumeCondition();
           continue;
       }
       if (requestPause) {
           state = Pausing;
       }
       // acquire image, record, submit, present
       if (state == Pausing) {
           waitForAllInFlightFences();
           state = Paused;
           continue;
       }
   }
   ```

4. **等待 in-flight frame**：
   - 收集所有 frame-in-flight fence；
   - `vkWaitForFences(device, fenceCount, fences, VK_TRUE, timeout)` [SPEC]；
   - 超时则记录 error，必要时触发 `DEVICE_LOST` 处理流程 [ENGINE]。
5. **停止新提交**：
   - `onPause` 设置标志后，不再调用 `vkAcquireNextImageKHR` 和 `vkQueuePresentKHR` [ANDROID]。
   - 已开始录制的 command buffer 仍可 submit，但不再开始新帧 [ENGINE]。
6. **恢复渲染**：
   - `onResume` 后若 surface 有效且 swapchain 有效，直接设置 `state = Running`。
   - 若 surface 已销毁，等待 `onSurfaceCreated` 创建新 swapchain 后再恢复 [ANDROID]。
7. **surface destroy 时的完整同步**：
   - render thread 进入 Paused 并等待所有 fence；
   - UI thread 调用 `vkDeviceWaitIdle`；
   - 销毁 swapchain、surface、释放 `ANativeWindow` [SPEC]。
8. **处理 async compute / upload**：
   - 若存在专用 compute queue 或 transfer queue，pause 时同样需要等待其 fence / semaphore [SPEC]。
   - 跨 queue 的 semaphore 在 surface destroy 前应确保已 signal / wait [SPEC]。
9. **避免 UI 线程阻塞**：
   - 所有 `vkWaitForFences` / `vkDeviceWaitIdle` 放在 render thread，UI thread 只负责发信号 [ANDROID]。
   - 若必须同步等待（如 `onSurfaceDestroyed`），使用 condition variable 等待 render thread 完成，设置 timeout [ENGINE]。
10. **日志与调试**：
    - 在状态转换点输出 logcat 日志，便于追踪 pause/resume 时序 [TOOL]。
    - 使用 AGI 验证 pause/resume 后第一帧的 barrier / descriptor 是否正确 [TOOL]。

---

## 9. Android 注意点

- `onPause` 后系统可能继续调用 `onSurfaceChanged` 或 `onSurfaceDestroyed`；render thread 必须能处理 surface 事件与 pause 状态的任意组合 [ANDROID]。
- 不要在 `onPause` 中直接调用 `vkDeviceWaitIdle`；应在 render thread 完成当前帧后再等待，避免 UI 线程 ANR [ANDROID]。
- 某些设备在 `onPause` 后几帧内才触发 surface destroy；需确保这几帧不再 submit [ANDROID]。
- `vkQueuePresentKHR` 在 pause 后仍可能返回 `VK_SUBOPTIMAL_KHR` 或 `VK_ERROR_OUT_OF_DATE_KHR`；此时应停止 present，不尝试 recreate swapchain（因为 surface 可能即将销毁）[ANDROID]。
- resume 时若 swapchain 已 out-of-date，应先 recreate swapchain 再开始 render loop；否则第一帧 present 会失败 [ANDROID]。
- frame-in-flight fence 在 pause 后可能已被 reset；resume 后需重新 reset 再使用 [SPEC]。
- 多 buffering 下，in-flight 帧数越多，pause 等待时间越长；若 ANR 阈值紧张，可减少 frame-in-flight 数量，但会增加 latency [HEUR]。
  - 适用条件：低端机、复杂场景、pause/resume 频繁的应用。
- 建议在调试阶段为每个状态转换点命名（如 `PausedBySurfaceDestroyed`、`PausedByLifecycle`），便于在复杂时序中定位问题 [GUIDE]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 fence / semaphore / submit 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：可 capture pause / resume 后的第一帧 [TOOL]。
- [ ] 截图 / 数值验证：resume 后渲染结果正确，无黑屏、卡顿、丢失帧。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出 render thread 状态转换日志与每帧 fence 等待耗时。
- [ ] 性能指标：
  - `onPause` 到 render thread 进入 Paused 的时间 < 100 ms（高端机 < 50 ms）；
  - `onResume` 到第一帧呈现的时间 < 200 ms；
  - 连续 pause/resume 10 次无 `DEVICE_LOST` 或 ANR [TOOL]。
- [ ] resize / rotation / pause / resume 组合操作后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **`onPause` 在 UI 线程等待 GPU**：导致 ANR [ANDROID]。
2. **in-flight frame 未等待就销毁 swapchain**：触发 validation error 或 crash [SPEC]。
3. **render thread 在 pause 期间继续 acquire image**：`vkAcquireNextImageKHR` 返回 `VK_ERROR_SURFACE_LOST_KHR` 或 `VK_ERROR_OUT_OF_DATE_KHR` [ANDROID]。
4. **resume 后旧 fence 未 reset 就 submit**：fence 状态错误，submit 失败 [SPEC]。
5. **pause 期间 surface 销毁后仍 present**：导致 `DEVICE_LOST` [ANDROID]。
6. **跨 queue compute 未同步**：graphics queue idle 但 compute queue 仍有工作，destroy 相关 resource 触发 hazard [SPEC]。
7. **condition variable 虚假唤醒未检查状态**：导致 pause 期间错误渲染一帧 [ENGINE]。
8. **timeout 过短**：正常 frame-in-flight 完成时间超过 timeout，误判为错误 [HEUR]。
9. **resume 后未检查 swapchain 状态**：直接开始 render loop，第一帧 present 失败 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- Android 设备型号 / GPU / Android 版本。
- render thread 实现方式（std::thread / pthread / 平台线程）。
- frame-in-flight 数量与 fence 管理代码。
- `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed` 的触发顺序与时间戳。
- logcat 中 render thread 状态转换日志。
- Validation Layer 完整报错。
- AGI / RenderDoc 中 pause/resume 后第一帧的 barrier / descriptor 状态。

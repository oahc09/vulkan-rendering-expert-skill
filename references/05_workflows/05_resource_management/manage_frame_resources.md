# Workflow: Manage Frame Resources

## 0. 适用范围

### 适用

- 管理 frame-in-flight 资源：per-frame command buffer、fence、semaphore、uniform buffer、staging buffer、query pool 等。
- 实现 ring index 轮询，保证 CPU 不覆盖 GPU 正在使用的资源。
- 处理 swapchain recreate 时的资源清理与重建路径。

### 不适用

- 单缓冲、非实时渲染或离线渲染。
- 资源生命周期完全由外部引擎托管、无需自定义 frame ring 的场景。
- 不使用 swapchain 的 headless / compute-only 程序（部分概念可参考，但本节以 graphics frame loop 为主）。

---

## 1. 任务目标

建立稳定的 per-frame 资源管理：

```text
Frame N-2        Frame N-1        Frame N
  (GPU)            (GPU/CPU)        (CPU record)
   fence            fence            fence
   cmd buffer       cmd buffer       cmd buffer
   UBO slot         UBO slot         UBO slot
   semaphore        semaphore        semaphore
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- Frame-in-flight 数量（通常 2~3，受 `minImageCount` 与 latency 需求影响）。
- 需要 per-frame 的资源类型：command buffer、UBO、image、fence、semaphore、query pool 等。
- 是否使用 single command pool per frame 或 resettable pool。
- Swapchain recreate 策略：in-place、full teardown、partial rebuild。
- 是否使用 dynamic rendering 或 render pass。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] swapchain recreate 路径已有基础处理。
- [ ] command pool 支持 `VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT` 或按 frame 分配。
- [ ] fence / semaphore 创建逻辑可用。
- [ ] 已确认 `minImageCount` 与期望 frame-in-flight 数量匹配。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Swapchain
→ Frame Index (acquire image index)
→ Per-Frame Ring Index (mod frameInFlight)
→ VkFence (frame complete)
→ VkCommandPool / VkCommandBuffer
→ Per-Frame Buffer / Image
→ VkSemaphore (image acquired, render complete)
→ Queue Submit
→ Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| per-frame command pool | `VkCommandPool` | 录制当前帧命令 | per-frame | 否（通常） |
| per-frame command buffer | `VkCommandBuffer` | 当前帧录制 | per-frame | 否 |
| per-frame fence | `VkFence` | GPU 完成信号 | per-frame | 否 |
| image acquired semaphore | `VkSemaphore` | acquire 信号 | per-frame | 否 |
| render complete semaphore | `VkSemaphore` | 渲染完成信号 | per-frame | 否 |
| per-frame UBO | `VkBuffer` | 当前帧常量 | per-frame | 否 |
| per-frame staging | `VkBuffer` | 当前帧上传 | per-frame | 否 |
| per-frame color/depth | `VkImage` | 当前帧中间输出 | per-frame | 是（若尺寸依赖 swapchain） |

---

## 6. Pipeline / Descriptor 设计

本工作流主要涉及资源管理，descriptor 设计按资源类型复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame UBO | Vertex / Fragment / Compute |
| set=N,binding=M | `COMBINED_IMAGE_SAMPLER` | per-frame image view | Fragment / Compute |

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU record | per-frame command buffer | `vkBeginCommandBuffer` / `vkEndCommandBuffer` | queue submit |
| queue submit | per-frame fence | `vkQueueSubmit` with fence | CPU `vkWaitForFences` |
| acquire semaphore | swapchain image | `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` wait | render begin |
| render complete semaphore | swapchain image | `VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT` / present | `vkQueuePresentKHR` |
| previous frame GPU | per-frame UBO / staging | fence signaled | CPU reuse same ring slot |

必须说明：

- `vkAcquireNextImageKHR` 返回的 `imageIndex` 是 swapchain image index，不一定是 ring index；frame-in-flight 使用独立的 `currentFrame % frameInFlight` [SPEC]。
- `vkQueueSubmit` 的 wait semaphore stage 应为 `COLOR_ATTACHMENT_OUTPUT_BIT`（graphics），而非 `TOP_OF_PIPE` [SPEC]。
- fence 等待后必须 `vkResetFences` 再 submit 下一帧使用同一 fence [SPEC]。
- command buffer 复用前可 `vkResetCommandBuffer` 或 `vkResetCommandPool` [SPEC]。

---

## 8. 实现步骤

1. **确定 frame-in-flight 数量**：通常 2~3；移动端 2 可降低 latency，PC 3 可提升吞吐 [HEUR]。
2. **创建 per-frame fence**：`VK_FENCE_CREATE_SIGNALED_BIT`，初始状态为 signaled，第一帧 `vkWaitForFences` 不阻塞 [ENGINE]。
3. **创建 semaphore**：每帧一对 `imageAcquiredSemaphore` 和 `renderFinishedSemaphore`。
4. **创建 per-frame command pool**：`VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT`，每帧一个 pool 可简化 reset；或单 pool + `vkResetCommandBuffer` [SPEC]。
5. **分配 per-frame command buffer**：从对应 pool 分配 primary command buffer。
6. **创建 per-frame 资源**：UBO、staging buffer、query pool 等按 frameInFlight 数量分配。
7. **Frame loop 流程**：
   - `vkWaitForFences(perFrameFence[currentFrame], TRUE, timeout)` [SPEC]
   - `vkResetFences(perFrameFence[currentFrame])` [SPEC]
   - `vkAcquireNextImageKHR(..., imageAcquiredSemaphore[currentFrame], ...)`
   - 重置并录制 command buffer
   - `vkQueueSubmit(..., wait=imageAcquiredSemaphore, signal=renderFinishedSemaphore, fence=perFrameFence[currentFrame])`
   - `vkQueuePresentKHR(..., wait=renderFinishedSemaphore)`
   - `currentFrame = (currentFrame + 1) % frameInFlight`
8. **处理 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`**：停止录制，等待 GPU idle，重建 swapchain 与尺寸相关的 per-frame image [SPEC]。
9. **Recreate 路径**：
   - `vkDeviceWaitIdle` 或等待所有 per-frame fence [SPEC]
   - 销毁尺寸相关的 image / image view / framebuffer / depth image
   - 重建 swapchain
   - 重建尺寸相关资源
   - 重置 `currentFrame` 到 0
10. **销毁路径**：
    - 等待 device idle
    - 按 `command buffer → command pool → fence → semaphore → per-frame buffer/image → memory` 顺序销毁 [ENGINE]
11. **Ring index 管理**：资源数组大小 = frameInFlight，CPU 写入前确保对应 fence signaled；swapchain imageIndex 仅用于选择 present image，不用于资源索引 [SPEC]。
12. **错误处理**：acquire / present 返回 `OUT_OF_DATE` 时，标记 recreate 标志，不直接 crash [ANDROID]。

---

## 9. Android 注意点

- `ANativeWindow` 创建后必须在 Java/Kotlin 层跟踪 `surfaceCreated` / `surfaceChanged` / `surfaceDestroyed`；`surfaceDestroyed` 后不得再 submit 任何命令 [ANDROID]。
- pause / resume 时通常销毁 swapchain 并停止 render thread；resume 后重新创建 surface 与 swapchain。
- rotation / resize 会改变 `ANativeWindow` 尺寸，触发 `VK_ERROR_OUT_OF_DATE_KHR` 或 `VK_SUBOPTIMAL_KHR`，必须重建 swapchain 与尺寸相关资源 [ANDROID]。
- `extent.width == 0 || extent.height == 0` 时暂停渲染循环，等待 surface 恢复非零尺寸 [ANDROID]。
- render thread 状态机：`RUNNING → PAUSED → RESUMED → RUNNING`，在 `PAUSED` 状态不调用 `vkAcquireNextImageKHR`。
- AGI / logcat 验证：检查 `vkQueuePresentKHR` 返回码、fence 等待时间、每帧资源索引。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkAcquireNextImageKHR-*`、`VUID-vkQueuePresentKHR-*`、`VUID-vkQueueSubmit-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见连续多帧的 submit、present、semaphore/fence 状态 [TOOL]。
- [ ] 截图 / 帧率：无 tearing、无 flickering、frame time 稳定。
- [ ] logcat（Android）：
  - `adb logcat -s vulkan` 无 validation error；
  - 自定义 tag 输出 `acquireImageIndex`、`currentFrame`、`fence status`。
- [ ] 性能指标：
  - CPU 端 `vkWaitForFences` 等待时间合理（不过长说明 GPU 并行度低，过短可能未正确等待）；
  - GPU frame time 在 AGI 中稳定；
  - 无 redundant fence/semaphore [HEUR]。
- [ ] resize / pause / resume / rotation 后正常渲染。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **fence 未 reset**：同一 fence 重复 submit 触发 validation error [SPEC]。
2. **frame index 与 swapchain imageIndex 混淆**：用 imageIndex 索引 per-frame UBO，导致数据错位 [ENGINE]。
3. **semaphore stage 错误**：wait stage 用 `TOP_OF_PIPE`，acquire 信号实际在 `COLOR_ATTACHMENT_OUTPUT` 等待 [SPEC]。
4. **recreate 时未等待 GPU idle**：销毁旧 swapchain image 时仍被 GPU 使用，触发 device lost [TOOL]。
5. **command buffer 未 reset 就录制**：旧命令残留或 validation error [SPEC]。
6. **fence 初始未 signaled**：第一帧 `vkWaitForFences` 永久阻塞 [ENGINE]。
7. **present 与 submit 使用不同 semaphore**：present 等待的 semaphore 未被 submit signal [SPEC]。
8. **Android surface destroy 后继续 submit**：导致 `VK_ERROR_DEVICE_LOST` [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- frame-in-flight 数量与 `minImageCount`。
- `vkAcquireNextImageKHR` 返回的 imageIndex 序列。
- fence / semaphore 创建参数。
- recreate 触发条件与处理顺序。
- Validation Layer 完整报错。
- Android lifecycle 日志（surfaceCreated/Changed/Destroyed、pause/resume）。

# Case: Black Screen Caused by Missing Queue Submit

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Command Buffer / Queue Submit |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

App 正常运行，无 crash，但画面全黑或一直显示上一帧内容。
RenderDoc 中可以看到 command buffer 已被录制，也能看到 render pass 和 draw call，但屏幕没有任何新输出；Validation Layer 通常不报错，或只在呈现阶段报出与 swapchain image 相关的警告。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 Vulkan graphics pipeline，已创建 command buffer 并录制了 render pass。
- 多 frame-in-flight 结构，每帧复用 command buffer 和 fence。
- 可能使用 Dynamic Rendering 或传统 RenderPass。
- 刚修改过 frame loop、渲染线程同步或 swapchain 呈现逻辑。

---

## 3. 初始误判

最初容易怀疑：

```text
fragment shader 输出错误；
clear color 被覆盖；
image layout transition 缺失；
swapchain image 没有正确 acquire；
GPU 挂起或驱动 bug。
```

但 RenderDoc 中 draw call 已录制、pipeline 状态正常，且 Validation Layer 对 shader / layout / barrier 保持 silent。最终发现 command buffer 录制完成后并没有被提交到 queue，或提交后没有等待 fence，也没有调用 present。

---

## 4. 排查路径

1. 在 render loop 中确认 `vkAcquireNextImageKHR` 是否成功返回有效 image index。
2. 检查 command buffer 录制起点到终点之间的 draw / end / 提交调用链。
3. 在 `vkEndCommandBuffer` 后确认是否调用了 `vkQueueSubmit`。
4. 检查 submit 的 `pSignalSemaphores` 和 present 的 `pWaitSemaphores` 是否配对。
5. 检查 fence 是否被正确 wait，以及 wait 返回是否被忽略。
6. 检查 `vkQueuePresentKHR` 是否在 render 线程主循环中被意外注释或提前 return。
7. 沿 `acquire → record → submit → wait → present` 链路定位缺失环节。

---

## 5. 关键证据

### Validation Layer

- 通常无直接报错（`[SPEC]`），因为录制 command buffer 本身合法。
- 若仍尝试 present 未提交渲染的 image，可能触发：
  - `VUID-vkQueuePresentKHR-pSwapchains-01283`：`pImageIndices` 对应的 image 没有 semaphore 信号保证完成。
  - `VUID-vkAcquireNextImageKHR-swapchain-01802`：未在合理时间内释放 swapchain image。
- 若 fence 未等待就复用 command buffer，后续帧可能报 command buffer 生命周期错误。

### RenderDoc / AGI

- 观察到：
  - Capture 中显示了 command buffer 的内容，包括 render pass 和 draw call。
  - 但 Event Browser 中没有 Queue Submit 节点，或 Submit 后没有 Present 调用。
  - Texture Viewer 中 swapchain image 保持为初始 acquire 状态或上一帧内容。
- 关键 resource：command buffer、queue submit info、fence、swapchain semaphore。

### Log / Code

- 返回值：
  - `vkQueueSubmit` 返回 `VK_SUCCESS`，但函数从未被调用。
  - `vkQueuePresentKHR` 返回 `VK_SUCCESS`，但参数中 wait semaphore 数量为零或信号从未被发出。
- 关键代码：

```text
// 录制完成但缺少以下任一调用：
vkQueueSubmit(graphicsQueue, 1, &submitInfo, frameFence);
vkWaitForFences(device, 1, &frameFence, VK_TRUE, timeout);
vkQueuePresentKHR(graphicsQueue, &presentInfo);
```

---

## 6. 根因

根因：command buffer 录制完成后，没有通过 `vkQueueSubmit` 提交到 GPU，或提交后没有等待 fence、没有调用 present，导致 GPU 从未执行该帧的渲染命令。

---

## 7. 修复方案

### 最小修复

- 在 `vkEndCommandBuffer` 后显式调用 `vkQueueSubmit`，并传入该帧对应的 fence。
- 在复用 command buffer 或交换到下一帧之前，先 `vkWaitForFences` 等待 fence signaled。
- 在 submit 之后调用 `vkQueuePresentKHR`，并确保 present wait semaphores 与 submit signal semaphores 一致。

### 稳定修复

- 在 frame loop 中建立 `acquire → record → submit → wait → present` 的显式状态断言。
- 每帧维护一个 FrameState 结构，记录是否已 submit、是否已 present；若某个分支提前 return，必须清理状态。
- 对 `vkQueueSubmit` 和 `vkQueuePresentKHR` 的返回值做检查，遇到 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 时触发 swapchain recreate。

### 工程化修复

- 封装 FrameLoop 类，把 acquire、record、submit、present 封装为不可跳过的固定阶段。
- 引入 Tracy / custom GPU profiler marker，确保每个 frame 都能追踪到 submit / present 事件。
- 在 CI 中增加 smoke test：运行 N 帧后检查 fence 被 signal 的次数是否等于 frame 数。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中能看到 Queue Submit 和 Present 调用。
- [ ] Texture Viewer 中 swapchain image 内容每帧更新。
- [ ] 多帧运行稳定，无卡顿或撕裂。
- [ ] resize / pause / resume / rotation 后仍能正常 submit / present。
- [ ] 多 frame-in-flight 下 fence 等待无超时。

---

## 9. 经验抽象

录制 command buffer 不等于执行。必须验证整条链路：

```text
acquire image
→ record commands
→ submit to queue with fence
→ wait fence before reuse
→ present with correct wait semaphore
```

任何一环缺失都会表现为“逻辑正确但屏幕无输出”。排查时应优先检查调用链是否完整，而不是深入 shader 或 barrier。

---

## 10. 预防规则

1. 每帧必须显式调用 `vkQueueSubmit` 与 `vkQueuePresentKHR`，禁止在分支中静默 return。
2. 每个 submit 必须关联一个 fence，并在复用资源前等待其 signaled。
3. present 的 wait semaphores 必须与 submit 的 signal semaphores 一一对应。
4. frame loop 中应添加断言：submit 后必须 present，fence wait 成功后才能 reset command buffer。
5. 代码审查时重点检查 render loop 的异常分支，确保不会跳过 submit / present。

---

## 11. 关联 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/pause_resume_render_thread.md`

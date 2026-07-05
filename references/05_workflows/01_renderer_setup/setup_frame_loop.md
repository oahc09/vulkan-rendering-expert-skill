# Workflow: Setup Vulkan Frame Loop

## 0. 适用范围

### 适用

- 已完成基础 Vulkan device / swapchain 初始化，需要建立稳定 frame loop。
- 需要支持 frames-in-flight。
- 需要处理 acquire / submit / present。
- 需要为后续 pass 扩展建立稳定骨架。

### 不适用

- 尚未创建 surface / swapchain。
- 只修复某个单独同步错误。
- 只做离屏 compute，无 present。

---

## 1. 任务目标

建立稳定的一帧渲染流程：

```text
Wait Fence
→ Acquire Swapchain Image
→ Reset Fence
→ Reset / Record CommandBuffer
→ Queue Submit
→ Present
```

---

## 2. 输入条件

需要确认：

- frames-in-flight 数量。
- swapchain image count。
- 每帧 command buffer 分配策略。
- 每帧资源是否独立。
- 是否区分 frame index 和 image index。
- 是否支持 swapchain recreate。

---

## 3. 前置检查

- [ ] swapchain 创建成功。
- [ ] command pool 创建成功。
- [ ] command buffer 可录制。
- [ ] fence / semaphore 创建成功。
- [ ] clear color pass 可运行。
- [ ] API 返回值有日志。

---

## 4. Vulkan 对象链路

```text
FrameResource
→ inFlightFence
→ imageAvailableSemaphore
→ renderFinishedSemaphore
→ CommandBuffer
→ vkAcquireNextImageKHR
→ vkQueueSubmit
→ vkQueuePresentKHR
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| imageAvailableSemaphore | `VkSemaphore` | acquire → submit | per-frame | 否 |
| renderFinishedSemaphore | `VkSemaphore` | submit → present | per-frame | 否 |
| inFlightFence | `VkFence` | CPU 等 GPU | per-frame | 否 |
| command buffer | `VkCommandBuffer` | record frame commands | per-frame 或 per-image | 视策略而定 |

---

## 6. Pipeline / Descriptor 设计

Frame loop 本身不直接设计 pipeline / descriptor。  
但必须为后续 pass 预留：

- current frame index
- current swapchain image index
- per-frame descriptor
- per-frame uniform buffer
- command buffer record callback

---

## 7. 同步与 Layout 设计

同步关系：

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| Present Engine | Swapchain Image | imageAvailableSemaphore | Graphics Queue |
| Graphics Queue | Swapchain Image | renderFinishedSemaphore | Present Engine |
| Graphics Queue | Frame Resource | inFlightFence | CPU |

注意：

- Fence 管 CPU-GPU。
- Semaphore 管 GPU-GPU / Queue-Present。
- frame index 不等于 swapchain image index。
- command buffer 被 GPU 使用期间不能 reset / free。

---

## 8. 实现步骤

1. 创建 per-frame sync objects。
2. 每帧 wait 当前 frame fence。
3. 调用 `vkAcquireNextImageKHR`。
4. 处理 `VK_ERROR_OUT_OF_DATE_KHR`。
5. reset fence。
6. reset command buffer。
7. record command buffer。
8. submit command buffer，并等待 imageAvailableSemaphore。
9. signal renderFinishedSemaphore。
10. present 等待 renderFinishedSemaphore。
11. 处理 `VK_SUBOPTIMAL_KHR` / `VK_ERROR_OUT_OF_DATE_KHR`。
12. frame index 递增。

---

## 9. Android 注意点

- Surface destroyed 后 frame loop 必须暂停。
- acquire / present 返回 out-of-date 时触发 recreate。
- pause 时不要阻塞 UI thread。
- resume 后检查 surface 是否可用。
- extent 为 0 时不要继续渲染。
- logcat 记录 frame loop 状态。

---

## 10. 验证方式

- [ ] clear color 连续稳定显示。
- [ ] 多帧运行无 validation error。
- [ ] resize / rotation 后 frame loop 恢复。
- [ ] frame index / image index 日志正确。
- [ ] RenderDoc / AGI 可连续抓帧。
- [ ] 无 fence wait 死锁。

---

## 11. 常见失败模式

1. fence reset 在 acquire 失败后执行，导致死锁。
2. frame index 和 image index 混用。
3. command buffer 仍 in-flight 就 reset。
4. present 没等待 renderFinishedSemaphore。
5. acquire 返回 out-of-date 后继续提交。
6. Android Surface destroyed 后继续 render。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`

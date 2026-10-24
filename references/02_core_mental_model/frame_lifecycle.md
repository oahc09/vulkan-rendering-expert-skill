# 一帧渲染生命周期

## 核心思想

Vulkan 一帧不是简单的 draw，而是 CPU、GPU、Present Engine 之间的协作。

标准帧流程：

```text
Frame Begin
→ Wait In-flight Fence
→ Acquire Swapchain Image
→ Reset / Allocate Command Buffer
→ Record Command Buffer
→ Reset Fence（acquire / 录制成功，确定会 submit）
→ Submit To Queue
→ GPU Execute
→ Signal Semaphore / Fence
→ Present
→ Frame End
```

## CPU 侧流程

```text
1. 等待当前 frame 的 in-flight fence。
2. vkAcquireNextImageKHR 获取 swapchain image index。
3. OUT_OF_DATE 返回并重建；TIMEOUT / NOT_READY 跳过；SUCCESS / SUBOPTIMAL 继续，后者标记稍后重建。
3b. 处理 VK_ERROR_SURFACE_LOST_KHR — Surface 已失效，需等待 Surface 重建后再恢复渲染。
4. reset command buffer。
5. record command buffer；成功 acquire 后若中途退出，必须处理 image 与 acquire 信号。
6. 确定提交后 reset fence。
7. vkQueueSubmit 并检查返回值；失败进入恢复，不继续普通 present / fence wait。
8. vkQueuePresentKHR。
```

## GPU / Present 侧流程

```text
1. imageAvailableSemaphore 被 signal 后，graphics queue 可以开始渲染。
2. GPU 执行 command buffer。
3. 渲染完成后 signal renderFinishedSemaphore。
4. Present 等待 renderFinishedSemaphore。
5. Present Engine 显示 swapchain image。
6. Fence signal 表示该 frame 的 GPU 工作完成，CPU 可安全复用相关 frame resource。
```

## Fence 与 Semaphore 的角色

```text
Fence：CPU 等 GPU。
Semaphore：GPU 队列之间 / acquire-render-present 之间同步。
```

常见用法：

```text
inFlightFence：防止 CPU 覆盖 GPU 仍在使用的 per-frame resource。
imageAvailableSemaphore：acquire → render。
renderFinishedSemaphore：render → present。
```

## Frames in Flight 模型

```text
FrameResource[0]
  - CommandBuffer
  - Fence
  - ImageAvailableSemaphore
  - Uniform Ring Slice

FrameResource[1]
  - CommandBuffer
  - Fence
  - ImageAvailableSemaphore
  - Uniform Ring Slice

SwapchainImageResource[imageIndex]
  - RenderFinishedSemaphore（binary，submit signal → present wait）
```

`imageAvailableSemaphore` 按 frame slot 复用；`renderFinishedSemaphore` 按 swapchain image 复用。再次 acquire 同一 image 并等待 acquire 同步后，才能重新 signal 对应 present semaphore；submit fence 不保证此前 present 已消费该 semaphore。依据：[Swapchain Semaphore Reuse](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)。[SPEC][GUIDE]

原则：

```text
CPU 可以提前准备下一帧，但不能覆盖 GPU 仍在使用的资源。
```

## 高频错误

1. 没有等待 fence 就复用 command buffer。
2. reset fence 的时机错误。
3. acquire 返回 out-of-date 后继续使用旧 swapchain。
4. present 返回 suboptimal / out-of-date 后不重建 swapchain。
5. per-frame uniform buffer 被 CPU 覆盖，但 GPU 仍在读取。
6. command buffer 引用了旧 framebuffer / image view / depth image。

## 专家规则

```text
CommandBuffer 录制完成不代表 GPU 执行完成。
vkQueueSubmit 返回不代表 GPU 执行完成。
Present 成功不代表该 frame resource 立即可复用。
资源复用必须看 fence 或更明确的同步策略。
```

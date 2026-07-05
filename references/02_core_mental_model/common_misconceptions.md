# 高频误区

## 误区 1：CommandBuffer 录制完成就代表 GPU 执行完成

错误。

CommandBuffer 只是记录命令。只有提交到 queue 后，GPU 才可能执行。CPU 需要 fence 或其他同步方式判断 GPU 是否完成。

## 误区 2：vkQueueSubmit 返回就代表渲染完成

错误。

`vkQueueSubmit` 返回只表示提交完成，不表示 GPU 已执行完成。GPU 完成需要 fence / semaphore / timeline semaphore 等同步确认。

## 误区 3：Acquire 到 swapchain image 后就可以随便写

错误。

Acquire 只是获得可用于渲染的 image index。仍需要通过 semaphore、render pass / dynamic rendering、layout 和 command buffer 建立正确访问关系。

## 误区 4：Image 创建后可以直接采样

错误。

Image 需要：

```text
正确 usage
memory binding
image view
layout transition
descriptor image info
barrier
```

## 误区 5：Descriptor 更新成功就说明 shader 能读到

错误。

还要检查：

```text
shader set / binding
descriptor set layout
pipeline layout
descriptor type
descriptor count
stage flags
bind point
resource lifetime
```

## 误区 6：黑屏大概率是 shader 错

不一定。

Vulkan 黑屏更应该先查：

```text
render loop
acquire
command buffer
submit
present
clear color
viewport / scissor
pipeline
descriptor
image layout
surface / swapchain
```

## 误区 7：Validation clean 就说明完全正确

错误。

Validation layer 能发现大量 API 使用错误，但不保证视觉正确、性能合理，也不能覆盖所有驱动或硬件行为。仍需 RenderDoc / AGI / 截图 / trace 验证。

## 误区 8：Dynamic Rendering 就不需要理解 Render Target

错误。

Dynamic Rendering 简化了 RenderPass / Framebuffer 管理，但仍需要理解：

```text
attachment image
image view
image layout
load / store
pipeline rendering info
barrier
```

## 误区 9：Barrier 写宽一点总是好

不准确。

过宽的 barrier 可能安全但影响性能。专家应该从 producer / consumer 推导 stage / access，而不是无脑使用 ALL_COMMANDS 和 MEMORY_READ_WRITE。

## 误区 10：Android 横竖屏只是重建 swapchain

不完整。

通常还要重建：

```text
swapchain image views
depth image
offscreen attachment
framebuffer
尺寸相关 descriptor
command buffer
viewport / scissor 状态
```

并且要确认旧资源不再被 GPU 使用。

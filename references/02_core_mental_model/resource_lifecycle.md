# 资源生命周期

## 核心思想

Vulkan 资源问题不能只看创建代码。

必须同时看：

```text
usage flag
memory property
memory binding
image layout
access mask
pipeline stage
descriptor imageLayout
GPU 使用期
销毁时机
```

## 通用生命周期

```text
Create
→ Allocate Memory
→ Bind Memory
→ Initialize Content
→ Transition Layout / Prepare Access
→ Use As Producer
→ Barrier
→ Use As Consumer
→ Wait GPU Finished
→ Destroy
```

## Buffer 生命周期

```text
VkBuffer
→ vkGetBufferMemoryRequirements
→ vkAllocateMemory
→ vkBindBufferMemory
→ Map / Upload / Copy
→ Use as Vertex / Index / Uniform / Storage / Transfer
→ GPU 使用完成
→ vkDestroyBuffer
→ vkFreeMemory
```

关注点：

1. `usage` 是否包含实际用途，例如 VERTEX_BUFFER、UNIFORM_BUFFER、STORAGE_BUFFER、TRANSFER_DST。
2. memory type 是否符合 CPU upload 或 GPU local 的需求。
3. host visible memory 是否需要 flush / invalidate。
4. uniform buffer offset 是否满足 alignment。
5. buffer 被 GPU 使用时不能提前销毁或覆盖。

## Image 生命周期

```text
VkImage
→ vkGetImageMemoryRequirements
→ vkAllocateMemory
→ vkBindImageMemory
→ VkImageView
→ Layout Transition
→ Use as Attachment / Sampled / Storage / Transfer
→ Barrier
→ GPU 使用完成
→ vkDestroyImageView
→ vkDestroyImage
→ vkFreeMemory
```

关注点：

1. `usage` 是否包含 COLOR_ATTACHMENT、SAMPLED、STORAGE、TRANSFER_SRC / DST 等实际用途。
2. format 是否支持目标 usage。
3. image view aspect 是否正确，例如 color / depth / stencil。
4. layout 是否匹配访问方式。
5. descriptor 中填写的 imageLayout 是否和 shader 访问时一致。
6. storage image 与 sampled image 的 layout / access 不同，不能混淆。

## Swapchain Image 生命周期

```text
Swapchain 创建
→ vkGetSwapchainImagesKHR
→ 为每个 image 创建 ImageView
→ Acquire Image
→ Render To Image
→ Present Image
→ Swapchain Recreate 时整体销毁重建相关 image view / depth / framebuffer / attachment
```

关注点：

1. Swapchain image 由 swapchain 管理，不需要手动 allocate / free memory。
2. Swapchain 重建时，所有依赖旧 swapchain extent / image / image view 的对象都要重建。
3. command buffer 不能继续引用旧 swapchain image view / framebuffer。
4. Android surface destroy 后，旧 swapchain 资源必须谨慎处理。

## Producer / Consumer 模型

资源访问应按 producer / consumer 分析：

```text
Producer 写资源
→ Barrier / 同步
→ Consumer 读资源
```

示例：

```text
Transfer 写 texture image
→ Barrier
→ Fragment shader 采样 texture
```

```text
Color attachment 写 offscreen image
→ Barrier
→ Fullscreen pass 采样 offscreen image
```

```text
Compute 写 storage buffer
→ Barrier
→ Graphics 读取 vertex / storage buffer
```

## 销毁规则

```text
资源销毁前必须确保 GPU 不再使用该资源。
```

常见策略：

1. 等待 device idle，简单但粗暴。
2. 等待相关 frame fence，适合 frames-in-flight。
3. 延迟销毁队列，等 N 帧后销毁。
4. Render Graph 中记录资源最后使用点。

## 专家规则

```text
Image 创建成功不代表可以直接使用。
Buffer 上传成功不代表 shader 能读到。
Descriptor 更新成功不代表资源生命周期正确。
销毁对象时不能只看 CPU 引用，还要看 GPU 是否仍在使用。
```

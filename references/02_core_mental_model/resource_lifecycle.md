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
3. 延迟销毁队列按全部实际使用的completion tokens退役；固定N帧只是调度策略，不是完成证明。
4. Render Graph 中记录资源最后使用点。

## 幂等销毁

幂等shutdown由wrapper状态、有效父对象和逐命令的可空参数规则保证。不能泛称所有destroy/free API都容忍NULL；数组、pool、Device与外部同步要求仍须满足。[SPEC][ENGINE]

```text
VulkanApp::shutdown():
    if isShutdown: return              // 幂等入口
    isShutdown = true
    if device != VK_NULL_HANDLE and device仍有效:
        result = vkDeviceWaitIdle(device) // 检查device-lost等结果；遵守host同步
    未创建的对象由wrapper跳过，不对无效Device调用API
    按依赖顺序销毁：下游 → 上游
    每个 handle destroy 后立即置 VK_NULL_HANDLE
```

关键规则：

1. 只对有效Device调用vkDeviceWaitIdle；同一有效Device上可重复等待，不等于NULL、已销毁Device或并发shutdown合法。[SPEC]
2. 每个 `vkDestroy*` 后立即把 handle 置 `VK_NULL_HANDLE`，防止 destructor 与显式 shutdown 双重销毁同一 handle [ENGINE]。
3. 创建时提供allocator则销毁时必须提供compatible allocator，不要求结构体地址相同；双方分配的内存须能由另一方相应free/reallocation释放。创建时NULL则对应销毁也不能提供allocator，callbacks及其依赖状态须保持有效。[SPEC]
4. swapchain recreate 与 shutdown 共用清理函数时，必须通过 flag 区分"仅 swapchain-dependent 资源"与"全部资源" [ENGINE]。
5. destructor 必须调用 shutdown 并能容忍"对象从未成功创建"场景：所有 handle 为 NULL，wrapper 走 no-op 路径 [ENGINE]。
6. device lost不会自动销毁子对象，handle仍有效；停止正常工作、协调host线程，按lost-device规则与有效使用要求清理。不能把检测到device lost泛化为允许任意并发销毁；等待可能返回SUCCESS或DEVICE_LOST，内容不再保证有效。[SPEC]
7. `vkDestroyDescriptorSet` 不存在；descriptor set可由vkResetDescriptorPool/vkDestroyDescriptorPool整体回收；pool含VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT时也可vkFreeDescriptorSets逐个释放。两条路径都须满足相关已提交使用完成与host同步；wrapper跟踪有效set/pool状态 [SPEC]。
8. swapchain image / implicit dispatchable handle 由父对象拥有，应用不能直接 destroy，幂等设计需跳过 [SPEC]。

## 专家规则

```text
Image 创建成功不代表可以直接使用。
Buffer 上传成功不代表 shader 能读到。
Descriptor 更新成功不代表资源生命周期正确。
销毁对象时不能只看 CPU 引用，还要看 GPU 是否仍在使用。
```


v1.0.17定向事实复核依据（不代表全文全域认证）：[memory#memory-allocation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory.adoc#memory-allocation)；[descriptorsets#descriptors-allocation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/descriptorsets.adoc#descriptors-allocation)；[devsandqueues#devsandqueues-lost-device](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/devsandqueues.adoc#devsandqueues-lost-device)；[synchronization#synchronization-wait-idle](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#synchronization-wait-idle)。[SPEC]

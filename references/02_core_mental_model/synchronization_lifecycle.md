# 同步生命周期

## 核心思想

Vulkan 同步的本质不是“加一个 barrier”，而是回答四个问题：

```text
谁写了资源？
谁要读资源？
写入何时完成？
读者何时能看到写入结果？
```

核心模型：

```text
Producer
→ Execution Dependency
→ Memory Availability
→ Memory Visibility
→ Consumer
```

## 三类同步

### 1. CPU-GPU 同步

```text
VkFence
```

作用：CPU 等 GPU。

典型场景：

1. frames-in-flight。
2. command buffer 复用前等待。
3. per-frame resource 复用前等待。
4. 资源销毁前确认 GPU 已完成。

### 2. GPU-GPU / Queue 同步

```text
VkSemaphore
Timeline Semaphore
```

作用：queue submit 之间、acquire / render / present 之间同步。

典型场景：

```text
vkAcquireNextImageKHR signal imageAvailableSemaphore
→ vkQueueSubmit wait imageAvailableSemaphore
→ vkQueueSubmit signal renderFinishedSemaphore
→ vkQueuePresentKHR wait renderFinishedSemaphore
```

### 3. 资源访问同步

```text
Pipeline Barrier
Image Memory Barrier
Buffer Memory Barrier
Layout Transition
```

作用：建立资源访问的执行依赖和内存依赖。

典型场景：

```text
Color Attachment Write
→ Barrier
→ Shader Sampled Read
```

```text
Compute Shader Write Storage Image
→ Barrier
→ Fragment Shader Read Sampled Image
```

```text
Transfer Write Buffer
→ Barrier
→ Vertex Shader / Vertex Input Read
```

## Stage / Access 心智模型

```text
srcStage：producer 发生在哪个 pipeline stage。
srcAccess：producer 对资源做了什么访问。
dstStage：consumer 发生在哪个 pipeline stage。
dstAccess：consumer 对资源做什么访问。
```

不要机械使用 `ALL_COMMANDS` / `MEMORY_READ_WRITE`。这会更安全但可能过度保守，影响性能。

## Image Layout 心智模型

Image layout 描述 image 在某种用途下的访问布局。

常见状态示例：

```text
UNDEFINED
TRANSFER_DST_OPTIMAL
SHADER_READ_ONLY_OPTIMAL
COLOR_ATTACHMENT_OPTIMAL
GENERAL
PRESENT_SRC_KHR
```

示例流转：

```text
UNDEFINED
→ TRANSFER_DST_OPTIMAL
→ SHADER_READ_ONLY_OPTIMAL
```

```text
UNDEFINED
→ COLOR_ATTACHMENT_OPTIMAL
→ SHADER_READ_ONLY_OPTIMAL
```

```text
UNDEFINED
→ COLOR_ATTACHMENT_OPTIMAL
→ PRESENT_SRC_KHR
```

注意：这只是示例，不是所有 image 都必须这样流转。

## Synchronization2

Vulkan 1.3+ 项目默认使用 Synchronization2 API：

```text
VkDependencyInfo
VkImageMemoryBarrier2
VkBufferMemoryBarrier2
vkCmdPipelineBarrier2
```

它将 stage / access / image layout transition / dependency flag 集中到一个 `VkDependencyInfo` 结构体，表达更清晰，也更符合现代 Vulkan 同步心智模型。

默认策略：

- 新项目或已声明 Vulkan 1.3+ 的环境，优先使用 `vkCmdPipelineBarrier2` 与 `VkDependencyInfo`。
- 需兼容 Vulkan 1.2 以下或目标设备不支持 Synchronization2 时，保留旧版 `vkCmdPipelineBarrier` 作为 fallback，并显式说明版本约束。

[SPEC][GUIDE]

## 高频错误

1. 只做 layout transition，不设置正确 access mask。
2. srcStage / dstStage 与真实访问不匹配。
3. compute 写 storage image 后，fragment 采样缺少 barrier。
4. transfer upload 后，shader 采样缺少 barrier。
5. 过度使用 device idle，导致性能差。
6. 重建 swapchain 时没有等待旧 command buffer 完成。
7. timeline semaphore / binary semaphore 使用语义混淆。

## 专家规则

```text
Barrier 不是魔法。
必须先找到 producer 和 consumer，再写 stage / access / layout。
```

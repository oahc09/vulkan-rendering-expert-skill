# Vulkan 对象链路

## 核心思想

Vulkan 不是一组孤立 API，而是一组对象链路。

一个高级 Vulkan 专家在分析问题时，不应只看某个 API，而要先建立对象关系图。

## 总体关系

```text
Application
→ VkInstance
→ VkPhysicalDevice
→ VkDevice
→ VkQueue
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain VkImage
→ VkImageView
→ VkCommandPool
→ VkCommandBuffer
→ VkPipelineLayout
→ VkPipeline
→ VkDescriptorSet
→ vkQueueSubmit
→ vkQueuePresentKHR
```

这不是严格线性流程，而是多个子链路汇合。

## 设备链

```text
VkInstance
→ VkPhysicalDevice
→ Queue Family
→ VkDevice
→ VkQueue
```

关注点：

1. Instance extension 是否包含平台 surface extension。
2. PhysicalDevice 是否支持目标 feature / extension。
3. Queue family 是否支持 graphics / compute / present。
4. Device extension 是否包含 swapchain 或其他必要扩展。
5. VkQueue 是否来自正确 queue family。

## 显示链

```text
Platform Window / ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images
→ VkImageView
→ Present
```

关注点：

1. Surface 是否仍有效。
2. Swapchain format / present mode / extent 是否正确。
3. Swapchain image view 是否随 swapchain 重建。
4. Present queue 是否支持 surface present。
5. `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 是否正确处理。

## 命令链

```text
VkCommandPool
→ VkCommandBuffer
→ Begin
→ Record Commands
→ End
→ Submit
```

关注点：

1. Command pool 是否属于正确 queue family。
2. Command buffer 是否在正确状态下 reset / begin / end。
3. Command buffer 是否引用已销毁或旧 swapchain 资源。
4. 多帧复用时 fence 是否确保 GPU 已完成。

## 资源链

```text
VkBuffer / VkImage
→ VkDeviceMemory
→ Bind Memory
→ Descriptor / Attachment / Vertex / Index / Storage
→ Shader / Render Pass / Dynamic Rendering / Compute
```

关注点：

1. usage flag 是否覆盖实际用途。
2. memory property 是否适合上传或 GPU 使用。
3. image layout 是否匹配访问方式。
4. descriptor 中的 imageLayout 是否匹配真实使用。
5. 资源销毁前 GPU 是否已完成访问。

## Pipeline 链

```text
Shader Module
→ DescriptorSetLayout
→ PipelineLayout
→ Graphics / Compute Pipeline
→ vkCmdBindPipeline
→ vkCmdDraw / vkCmdDispatch
```

关注点：

1. Shader input / resource binding 是否与 Vulkan 侧 layout 匹配。
2. PipelineLayout 是否包含正确 DescriptorSetLayout。
3. Render target format / dynamic rendering info 是否与 pipeline 创建兼容。
4. Viewport / scissor / depth / blend 状态是否符合预期。

## 专家规则

```text
遇到 Vulkan 问题，不要先看某个 API。
先判断问题属于设备链、显示链、命令链、资源链、Pipeline 链还是同步链。
```

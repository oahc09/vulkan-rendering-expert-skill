# Mental Model Checklist

在输出 Vulkan 设计、代码、调试、优化方案前，先检查是否覆盖以下心智模型。

## Object Chain

- 是否说明 Instance / PhysicalDevice / Device / Queue？
- 是否说明 Surface / Swapchain？
- 是否说明 CommandPool / CommandBuffer？
- 是否说明 Pipeline / PipelineLayout？
- 是否说明 DescriptorSetLayout / DescriptorSet？
- 是否说明 Buffer / Image / Memory？
- 是否说明 Queue Submit / Present？

## Frame Lifecycle

- 是否说明 wait fence？
- 是否说明 acquire swapchain image？
- 是否说明 command buffer reset / record？
- 是否说明 submit？
- 是否说明 semaphore？
- 是否说明 present？
- 是否说明 frames-in-flight resource 复用？

## Resource Lifecycle

- 是否说明 usage flag？
- 是否说明 memory property？
- 是否说明 image view？
- 是否说明 image layout？
- 是否说明 producer / consumer？
- 是否说明销毁时机？
- 是否说明 GPU 是否仍在使用？

## Synchronization

- 是否区分 CPU-GPU 同步？
- 是否区分 GPU-GPU 同步？
- 是否说明 barrier？
- 是否说明 stage / access？
- 是否说明 image layout transition？
- 是否说明 resource visibility？

## Pipeline / Descriptor

- 是否说明 shader set / binding？
- 是否说明 descriptor set layout？
- 是否说明 pipeline layout？
- 是否说明 descriptor update？
- 是否说明 bind point？
- 是否说明 resource lifetime？

## Render Target

- 是否说明 attachment image？
- 是否说明 image view？
- 是否说明 layout？
- 是否说明 load / store？
- 是否说明 RenderPass 或 Dynamic Rendering？
- 是否说明后续 pass 如何读取？

## Android

- 是否考虑 Surface 生命周期？
- 是否考虑 ANativeWindow 是否有效？
- 是否考虑 swapchain recreate？
- 是否考虑 depth / offscreen / framebuffer 重建？
- 是否考虑旧 command buffer 引用旧资源？
- 是否考虑 pause / resume / rotation？

## Compute

- 是否说明 compute producer？
- 是否说明 graphics consumer？
- 是否说明 storage buffer / storage image？
- 是否说明 dispatch 后 barrier？
- 是否说明 queue ownership，如涉及多队列？

## 输出前硬检查

如果答案涉及 Vulkan 工程修改，至少要说明：

```text
修改文件
新增 Vulkan 对象
初始化流程
每帧执行流程
同步关系
资源销毁 / 重建流程
验证方式
```

# API Manual Index

> 文件建议路径：`api_index.md`

---

## 使用方式

按“对象链路”或“当前问题关键词”定位到单张 API Card。不要一次性加载全部卡片。

检索顺序：

```text
确定对象/问题
→ 查本索引找到对应卡片
→ 读卡片中的“对象链路”与“正确性检查点”
→ 必要时跳转相关卡片
→ 仍不确定时回查官方文档
```

---

## Instance / Device / Queue 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkInstance` | `01_instance_device_queue/instance.md` |
| `VkDevice` / Logical Device | `01_instance_device_queue/logical_device.md` |

---

## Surface / Swapchain 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkSurfaceKHR` | `02_surface_swapchain/surface.md` |
| `VkSwapchainKHR` | `02_surface_swapchain/swapchain.md` |
| Swapchain Recreate | `02_surface_swapchain/swapchain_recreate.md` |

---

## Android Platform 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `ANativeWindow` | `10_android_platform/anativewindow.md` |
| Android Surface 生命周期 | `10_android_platform/android_surface.md` |

---

## Command Buffer 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkCommandBuffer` | `03_command_buffer/command_buffer.md` |
| `vkQueueSubmit` | `03_command_buffer/queue_submit.md` |
| Command Buffer 生命周期 | `03_command_buffer/command_buffer_lifetime.md` |
| `VkFence` / `VkSemaphore` 对比 | `03_command_buffer/fence_semaphore.md` |

---

## Buffer / Image / Memory 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkImage` | `04_buffer_image_memory/image.md` |
| `VkImageView` | `04_buffer_image_memory/image_view.md` |
| `VkBuffer` | `04_buffer_image_memory/buffer.md` |
| Memory Allocation | `04_buffer_image_memory/memory_allocation.md` |
| `VkFramebuffer` | `04_buffer_image_memory/framebuffer.md` |
| Image Layout | `04_buffer_image_memory/image_layout.md` |
| `VkSampler` | `04_buffer_image_memory/sampler.md` |

---

## Descriptor 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkDescriptorSetLayout` | `05_descriptor/descriptor_set_layout.md` |
| `VkDescriptorSet` | `05_descriptor/descriptor_set.md` |
| `vkUpdateDescriptorSets` | `05_descriptor/descriptor_update.md` |
| `VkDescriptorPool` | `05_descriptor/descriptor_pool.md` |
| Sampled Image Descriptor | `05_descriptor/sampled_image_descriptor.md` |
| Storage Buffer / Image Descriptor | `05_descriptor/storage_buffer_image_descriptor.md` |
| Uniform Buffer Descriptor | `05_descriptor/uniform_buffer_descriptor.md` |

---

## Pipeline 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkShaderModule` | `06_pipeline/shader_module.md` |
| `VkPipelineLayout` | `06_pipeline/pipeline_layout.md` |
| `VkPipeline` (Graphics) | `06_pipeline/graphics_pipeline.md` |
| `VkPipeline` (Compute) | `06_pipeline/compute_pipeline.md` |
| `VkPipeline` 通用 | `06_pipeline/pipeline.md` |
| Graphics Pipeline Library | `06_pipeline/graphics_pipeline_library.md` |
| `VkPipelineCache` | `06_pipeline/pipeline_cache.md` |
| Specialization Constants | `06_pipeline/specialization_constants.md` |

---

## Rendering 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkRenderPass` | `07_rendering/render_pass.md` |
| Dynamic Rendering | `07_rendering/dynamic_rendering.md` |
| Attachment Load / Store | `07_rendering/attachment_load_store.md` |
| Render Target Layout | `07_rendering/render_target_layout.md` |

---

## Synchronization 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkFence` | `08_synchronization/fence.md` |
| `VkSemaphore` | `08_synchronization/semaphore.md` |
| `vkCmdPipelineBarrier` | `08_synchronization/pipeline_barrier.md` |
| `VkImageMemoryBarrier` | `08_synchronization/image_memory_barrier.md` |
| `VkBufferMemoryBarrier` | `08_synchronization/buffer_memory_barrier.md` |
| `VkEvent` | `08_synchronization/event.md` |
| `VK_KHR_synchronization2` | `08_synchronization/synchronization2.md` |

---

## Debug / Validation 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| Validation Layer | `09_debug_validation/validation_layer.md` |
| Debug Utils | `09_debug_validation/debug_utils.md` |
| VUID 解码 | `09_debug_validation/vuid_decode.md` |

---

## 按问题快速定位

| 问题 | 推荐首张卡片 |
|---|---|
| 黑屏、无输出 | `04_buffer_image_memory/image.md` / `08_synchronization/image_memory_barrier.md` |
| Validation 报 descriptor | `05_descriptor/descriptor_set_layout.md` |
| Validation 报 layout | `04_buffer_image_memory/image.md` / `08_synchronization/image_memory_barrier.md` |
| Validation 报 sync hazard | `08_synchronization/pipeline_barrier.md` |
| Swapchain recreate 失败 | `02_surface_swapchain/swapchain_recreate.md` |
| Compute 无输出 | `06_pipeline/compute_pipeline.md` / `08_synchronization/pipeline_barrier.md` |
| Pipeline 创建失败 | `06_pipeline/graphics_pipeline.md` / `06_pipeline/pipeline_layout.md` |
| 如何启用验证层 | `09_debug_validation/validation_layer.md` |
| Android 横竖屏 / Surface 变化 | `10_android_platform/android_surface.md` |
| Compute → Graphics 同步 | `08_synchronization/buffer_memory_barrier.md` / `08_synchronization/pipeline_barrier.md` |

---

## 写作规范与索引

| 主题 | 文件 |
|---|---|
| API Card 写作规则 | `api_card_writing_rules.md` |
| 错误码索引 | `error_index.md` |
| 生命周期索引 | `lifecycle_index.md` |

# Lifecycle Index

> 文件建议路径：`lifecycle_index.md`

---

## 用途

当任务涉及“对象何时创建、何时销毁、是否被 GPU 引用、何时可复用”时，先查本索引定位生命周期相关 API Card 或核心心智模型文档。

---

## 对象生命周期入口

| Vulkan 对象 | 生命周期入口卡片 | 关键生命周期风险 |
|---|---|---|
| `VkSurfaceKHR` | `02_surface_swapchain/surface.md` | 与 Android `ANativeWindow` 同生命周期；pause / destroy 后失效。 |
| `VkSwapchainKHR` | `02_surface_swapchain/swapchain.md` | recreate 时必须等待 GPU idle；旧 image view 仍在 in-flight 中不能销毁。 |
| `VkCommandBuffer` / `VkCommandPool` | `03_command_buffer/command_buffer.md`<br>`03_command_buffer/command_buffer_lifetime.md` | 被 submit 后 fence signal 前不能 reset / free。 |
| `VkImage` / `VkImageView` | `04_buffer_image_memory/image.md`<br>`04_buffer_image_memory/image_view.md` | layout 状态必须显式 transition；view 必须在 image 有效期间存在。 |
| `VkBuffer` | `04_buffer_image_memory/buffer.md` | CPU-GPU 并发访问需通过 barrier / fence 同步。 |
| `VkDeviceMemory` | `04_buffer_image_memory/memory_allocation.md` | 释放前确保没有 resource 仍被 GPU 使用。 |
| `VkDescriptorSetLayout` | `05_descriptor/descriptor_set_layout.md` | 被 pipeline / descriptor set 引用期间不能销毁。 |
| `VkDescriptorSet` / `VkDescriptorPool` | `05_descriptor/descriptor_set.md` | in-flight 期间不能 reset / free；resource 引用需保持有效。 |
| `VkPipelineLayout` | `06_pipeline/pipeline_layout.md` | 相关 pipeline 仍使用时销毁需谨慎。 |
| `VkPipeline` | `06_pipeline/graphics_pipeline.md`<br>`06_pipeline/compute_pipeline.md` | in-flight command buffer 引用时不能销毁。 |
| `VkShaderModule` | `06_pipeline/shader_module.md` | pipeline 创建后可销毁，但复用期间需保留。 |
| `VkFence` | `08_synchronization/fence.md` | signal 前 reset 是非法的；destroy 前确保不被等待。 |
| `VkSemaphore` | `08_synchronization/semaphore.md` | 每个 signal 必须对应一次 wait；不能重置。 |
| Timeline Semaphore | `08_synchronization/timeline_semaphore.md` | value 单调递增；允许 wait-before-signal，只需最终存在可满足该 wait 的 signal 并维持 forward progress。 |
| Frames in Flight | `03_command_buffer/frames_in_flight.md` | per-frame 资源在 fence signal 前不能复用。 |
| `VkQueryPool` | `04_buffer_image_memory/query_pool.md` | 查询结果在 available 前不能读取；reset 后不能立即使用。 |

---

## 帧生命周期入口

| 主题 | 文档 |
|---|---|
| 完整帧生命周期模型 | `../02_core_mental_model/frame_lifecycle.md` |
| Acquire / Submit / Present 同步 | `03_command_buffer/queue_submit.md`<br>`08_synchronization/semaphore.md`<br>`08_synchronization/fence.md` |
| Swapchain recreate 生命周期 | `02_surface_swapchain/swapchain_recreate.md` |
| Android Surface / Swapchain 生命周期 | `../02_core_mental_model/android_surface_swapchain_lifecycle.md`<br>`../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md` |

---

## 资源复用与 in-flight 风险

| 场景 | 推荐卡片 |
|---|---|
| Per-frame 资源复用 | `../05_workflows/05_resource_management/manage_frame_resources.md` |
| Command buffer reset | `03_command_buffer/command_buffer_lifetime.md` |
| Descriptor set 复用 | `05_descriptor/descriptor_set.md` |
| Image layout 跟踪 | `04_buffer_image_memory/image.md`<br>`08_synchronization/image_memory_barrier.md` |

---

## 销毁顺序检查

销毁时应遵循“从下游到上游”的依赖顺序：

```text
先等待 GPU idle / fence
→ 销毁 command buffer / descriptor set / framebuffer / image view
→ 销毁 image / buffer / pipeline / command pool / descriptor pool
→ 销毁 pipeline layout / descriptor set layout / render pass / swapchain
→ 销毁 surface / device
```

> 具体对象的销毁约束以各 API Card 第 9 节“生命周期风险”为准。[SPEC]

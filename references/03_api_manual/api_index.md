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
| `VkPhysicalDevice` | `01_instance_device_queue/physical_device.md` |
| Maintenance 扩展系列 | `01_instance_device_queue/maintenance_extensions.md` |

---

## Surface / Swapchain 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkSurfaceKHR` | `02_surface_swapchain/surface.md` |
| `VkSwapchainKHR` | `02_surface_swapchain/swapchain.md` |
| Swapchain Recreate | `02_surface_swapchain/swapchain_recreate.md` |
| Desktop Windowing（SDL/GLFW/Win32） | `02_surface_swapchain/desktop_windowing.md` |

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
| Frames in Flight | `03_command_buffer/frames_in_flight.md` |
| Indirect Draw / Dispatch | `03_command_buffer/indirect_commands.md` |

---

## Buffer / Image / Memory 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkImage` | `04_buffer_image_memory/image.md` |
| `VkImageView` | `04_buffer_image_memory/image_view.md` |
| `VkBuffer` | `04_buffer_image_memory/buffer.md` |
| 外部资源 / memory FD / sync FD / AHB | `04_buffer_image_memory/external_resource_interop.md` |
| Memory Allocation | `04_buffer_image_memory/memory_allocation.md` |
| `VkFramebuffer` | `04_buffer_image_memory/framebuffer.md` |
| Image Layout | `04_buffer_image_memory/image_layout.md` |
| `VkSampler` | `04_buffer_image_memory/sampler.md` |
| Copy / Blit / Resolve 命令 | `04_buffer_image_memory/copy_blit_resolve.md` |
| Host Image Copy | `04_buffer_image_memory/host_image_copy.md` |
| `VkQueryPool` | `04_buffer_image_memory/query_pool.md` |
| VMA (Vulkan Memory Allocator) | `04_buffer_image_memory/vma_usage.md` |

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
| Push Descriptor | `05_descriptor/push_descriptor.md` |
| Descriptor Indexing | `05_descriptor/descriptor_indexing.md` |
| Descriptor Buffer | `05_descriptor/descriptor_buffer.md` |
| Descriptor Heap / slot stride 与写入大小 | `05_descriptor/descriptor_heap.md` |

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
| Dynamic State | `06_pipeline/dynamic_state.md` |
| Mesh / Task Shader（`VK_EXT_mesh_shader`） | `06_pipeline/mesh_shader.md` |

---

## Rendering 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkRenderPass` | `07_rendering/render_pass.md` |
| 移动tile / local read / QCOM能力与回退 | `07_rendering/mobile_tile_rendering.md` |
| Dynamic Rendering | `07_rendering/dynamic_rendering.md` |
| Attachment Load / Store | `07_rendering/attachment_load_store.md` |
| Render Target Layout | `07_rendering/render_target_layout.md` |

---

## Synchronization 链

| 对象 / 主题 | 入口卡片 |
|---|---|
| `VkFence` | `08_synchronization/fence.md` |
| `VkSemaphore` | `08_synchronization/semaphore.md` |
| Timeline Semaphore | `08_synchronization/timeline_semaphore.md` |
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


v1.0.12仅按章节扩展既有Android Surface、媒体采样与颜色输出内容，API/Workflow文件数不变；新主题按唯一任务路由中的显式锚点读取，未命中不预载。

## Shader / 资源 / GPU-driven 规模化主题

| 问题 | 按需入口 |
|---|---|
| Shader manifest / SPIR-V / reflection / FP16 | `../03_api_manual/06_pipeline/shader_module.md#shader-artifact-contract` |
| Pipeline key / cache / Binary / GPL | `../03_api_manual/06_pipeline/pipeline_cache.md#cache-compatibility` |
| VMA / 流式预算 / OOM背压 | `../03_api_manual/04_buffer_image_memory/vma_usage.md#streaming-budget-policy` |
| Indirect能力回退 / firstInstance / DrawID | `../03_api_manual/03_command_buffer/indirect_commands.md#indirect-capability-fallback` |
| Indirect count溢出/command ABI | `../03_api_manual/03_command_buffer/indirect_commands.md#indirect-capacity-safety` |
| Mesh/task / meshlet / 传统fallback | `../03_api_manual/06_pipeline/mesh_shader.md#mesh-path-fallback` |


## v1.0.15 定向知识

- [Blend格式能力](06_pipeline/graphics_pipeline.md#blend-format-capability)
- [透明附件精度](04_buffer_image_memory/image.md#transparent-target-precision)
- [折射读写边界](07_rendering/render_target_layout.md#refraction-read-write-boundary)


<a id="vulkan-domain-map"></a>
## Vulkan 1.4.368 全域导航与覆盖边界

先沿既有 API / implementation / debug / performance / architecture 路由确定任务，再只读下表命中领域的合同段落。此表是导航，不是“所有符号语义审计通过”的证书。范围冻结为标准 Vulkan Core1.0–1.4 与公开稳定扩展；preview 单列，disabled 和其他 API variant 明示排除；SC 不作本轮全覆盖或安全认证。每个扩展仍须核对独有语义、完整 depends、feature enable、limits/format/platform、失败和合法回退。

| 领域 | 首选知识入口 | 尚需逐项核对 |
|---|---|---|
| VK01 初始化、加载与版本 | [合同入口](01_instance_device_queue/instance.md#loader-dispatch-contract) | Loader/ICD/layers、allocation callbacks、版本/alias细节仍需逐项复核 |
| VK02 设备、队列与能力 | [合同入口](01_instance_device_queue/physical_device.md#device-group-capability-contract) | queue priority、全部features/limits/profiles组合 |
| VK03 对象与命令管理 | [合同入口](03_command_buffer/command_buffer.md) | 各命令host sync、secondary/inheritance、conditional rendering组合 |
| VK04 内存与驻留 | [合同入口](04_buffer_image_memory/memory_allocation.md#memory-host-alias-contract) | 全部allocation/BDA/sparse/protected/alias扩展差异 |
| VK05 资源、格式与数据移动 | [合同入口](04_buffer_image_memory/image.md) | 逐format/多平面/压缩格式/usage/copy组合 |
| VK06 同步与内存模型 | [合同入口](08_synchronization/synchronization2.md#cross-queue-host-contract) | 全部stage/access适用性和memory model交互 |
| VK07 资源绑定与布局 | [合同入口](05_descriptor/push_descriptor.md#push-descriptor-count-lifetime) | 各binding model与pipeline layout兼容性的全量扩展合同 |
| VK08 Shader / SPIR-V | [合同入口](06_pipeline/shader_module.md#shader-artifact-contract) | 全部capability/opcode/feature映射、grammar差异 |
| VK09 Pipeline 与状态 | [合同入口](06_pipeline/shader_module.md#shader-object-contract) | 全部dynamic state/cache/binary/library/parallel create条件 |
| VK10 光栅与帧缓冲 | [合同入口](07_rendering/mobile_tile_rendering.md#tile-capability-matrix) | raster/depth/stencil/blend/MSAA/FDM/FSR等逐扩展审计 |
| VK11 绘制与 GPU 生成工作 | [合同入口](03_command_buffer/indirect_commands.md#device-generated-commands-contract) | DGC/transform feedback/mesh/task全部命令规则 |
| VK12 Query 与测量 | [合同入口](04_buffer_image_memory/query_pool.md#query-generation-contract) | 性能query/calibrated timestamp全部扩展规则 |
| VK13 WSI 与平台 | [合同入口](02_surface_swapchain/surface.md) | 每个公开平台扩展、present timing/id/wait/maintenance组合 |
| VK14 完整光追 API 链 | [合同入口](06_pipeline/pipeline.md#ray-tracing-pipeline-contract) | 全量AS/SBT/RT条件扩展，未测设备 |
| VK15 Vulkan Video | [合同入口](04_buffer_image_memory/image.md#vulkan-video-codec-differences) | codec全部valid usage和辅助扩展深层合同，未测codec设备 |
| VK16 特殊计算与新扩展族 | [合同入口](06_pipeline/compute_pipeline.md#special-compute-contract) | optical/tensor/data graph/cooperative/地址类逐扩展差异 |
| VK17 外部互操作与隔离 | [合同入口](04_buffer_image_memory/external_resource_interop.md#interop-handle-matrix) | 各平台handle消费/权限与跨API兼容完整组合 |
| VK18 调试、鲁棒性与工程治理 | [合同入口](../04_debug_playbooks/02_crash_hang/device_lost.md#fault-report-order-1368) | 全部robustness/error/VUID/capture规则与真实宿主行为 |

L0登记/可找到入口不等于 L1 的条件语义或 L2 的实施/排错流程；本候选仍存在稳定扩展逐项审计缺口。未审完不得用一个通用 modern_patterns 链接替代专有合同。不存在/拼错的符号与教学反例分别审查，不按字符串出现次数估算知识覆盖。Registry 分母、章节图、审计来源和状态保存在配套 tests 仓库，评估答案与rubric不进入运行时知识包。

固定权威：[Registry vk.xml](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/xml/vk.xml)、[规范目录](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/vkspec.adoc)。遇到包内缺口时回查对应官方章节并如实声明未验证，不自行创造枚举/feature/VUID。

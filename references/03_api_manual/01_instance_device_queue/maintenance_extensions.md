# API Card: Maintenance 扩展系列（VK_KHR_maintenance1～7 / VK_EXT_swapchain_maintenance1）

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 |
| Vulkan 对象 | Maintenance 扩展系列 |
| 常用 API | `vkGetDeviceBufferMemoryRequirements` / `vkGetDeviceImageMemoryRequirements` / `vkCmdBindIndexBuffer2` 等 |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | maintenance1-3: Vulkan 1.1 core; maintenance4: Vulkan 1.3 core; maintenance5-6: Vulkan 1.4 core; maintenance7: 扩展 |

---

## 1. 一句话定位

Maintenance 系列扩展是 Khronos 对 Vulkan 核心规范做的累积修订包，按版本号收敛长期存在的语义缺口、补齐遗漏查询入口、放宽过严约束、统一不同来源的行为；它们不引入新渲染能力，但决定了"哪些用法合法、哪些查询入口可用、哪些边界条件合法"。[SPEC]

---

## 2. 所属对象链路

```text
VkInstance
→ VkPhysicalDevice
→ vkEnumerateDeviceExtensionProperties / vkGetPhysicalDeviceProperties2
→ 检测 maintenance1-7 / swapchain_maintenance1 是否可用
→ VkDeviceCreateInfo.ppEnabledExtensionNames（老版本）或 VkPhysicalDeviceVulkan13Features / VkPhysicalDeviceVulkan14Features 聚合结构（新版本通过 pNext 启用 maintenance features；也可使用独立的 VkPhysicalDeviceMaintenance4Features / Maintenance5Features / Maintenance6Features）
→ VkDevice
→ 实际功能入口：
   - vkGetDeviceBufferMemoryRequirements / vkGetDeviceImageMemoryRequirements（maintenance4）
   - vkCmdBindIndexBuffer2（maintenance5）
   - 简化同步表达 / maintenance6 sync hint
   - VK_EXT_swapchain_maintenance1 的 present mode 切换 / retired swapchain 延迟销毁
```

### 上游依赖

- 已创建的 `VkInstance`、`VkPhysicalDevice`、`VkDevice`。[SPEC]
- 每条 maintenance 扩展都是 device-level extension，启用前必须确认 `vkEnumerateDeviceExtensionProperties` 返回对应字符串。[SPEC]
- Vulkan 1.3+ 中 `VK_KHR_maintenance4` 已进核心，扩展字符串自动可用，但仍需通过 `VkPhysicalDeviceVulkan13Features.maintenance4` 显式启用 feature；Vulkan 1.4+ 中 `VK_KHR_maintenance5` / `VK_KHR_maintenance6` 进核心，需通过 `VkPhysicalDeviceVulkan14Features.maintenance5` / `.maintenance6` 启用（也可使用独立结构 `VkPhysicalDeviceMaintenance4Features` / `Maintenance5Features` / `Maintenance6Features`）。[SPEC]

### 下游影响

- 决定 `vkCmdBindIndexBuffer2`、`vkGetDeviceBufferMemoryRequirements` 等 API 入口是否可调用。[SPEC]
- 决定 `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` 等 layout 枚举是否合法。[SPEC]
- 决定 `VkMemoryAllocator` 类工具能否实现"先查后建"的资源创建路径。[ENGINE]
- 影响 `VkSwapchainPresentScalingCreateInfoEXT` 等 swapchain 维护入口可用性。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPhysicalDeviceMaintenance*Properties` / `VkPhysicalDeviceVulkan13Features`（含 maintenance4）/ `VkPhysicalDeviceVulkan14Features`（含 maintenance5 / maintenance6）/ 独立 `VkPhysicalDeviceMaintenance4Features` / `Maintenance5Features` / `Maintenance6Features`
- `VkDeviceBufferMemoryRequirements`、`VkDeviceImageMemoryRequirements`（maintenance4）
- `VkBindIndexBufferIndirectCommand` 等关联结构（按需）
- `VkPipelineCreateFlags2CreateInfo`、`VkSwapchainPresentModesCreateInfoEXT`（maintenance6 / swapchain_maintenance1）

### 常用 API

| API | 来源扩展 | 作用 |
|---|---|---|
| `vkGetDeviceBufferMemoryRequirements` | maintenance4 (1.3 core) | 在不创建 `VkBuffer` 的情况下查询 memory requirements。[SPEC] |
| `vkGetDeviceImageMemoryRequirements` / `vkGetDeviceImageSparseMemoryRequirements` | maintenance4 (1.3 core) | 在不创建 `VkImage` 的情况下查询 memory requirements。[SPEC] |
| `vkCmdBindIndexBuffer2` | maintenance5 (1.4 core) | 相比 `vkCmdBindIndexBuffer` 增加 `size` 参数，支持 partial index range 绑定；indexType 与原 API 一致。[SPEC] |
| `vkGetImageSubresourceLayout2KHR` | maintenance5 (1.4 core) | 扩展 layout 查询，支持 `mipLevel` / `arrayLayer` 维度。[SPEC] |
| `vkGetRenderingAreaGranularityKHR` | maintenance5 (1.4 core) | 在 dynamic rendering 下查询 render area granularity。[SPEC] |
| `vkGetDeviceImageSubresourceLayoutKHR` | maintenance5 (1.4 core) | 对未持有 `VkImage` handle 的图像资源查询 layout。[SPEC] |
| `vkMapMemory2` / `vkUnmapMemory2` | `VK_KHR_map_memory2` (1.4 core promote) | 取代 `vkMapMemory`，支持 `pNext` 链与 `VkMemoryMapInfo`；来自独立扩展 `VK_KHR_map_memory2`，**不属于** maintenance6。[SPEC] |
| `vkGetSwapchainImagesKHR` + `VkSwapchainPresentModesCreateInfoEXT` | swapchain_maintenance1 | present mode 运行时切换。[SPEC] |

### 相关扩展 / 版本

| 扩展 | 入核心版本 | 关键能力 |
|---|---|---|
| `VK_KHR_maintenance1` | Vulkan 1.1 | 负 viewport height、`VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT`、command buffer simultaneous use 放宽、`VK_ERROR_OUT_OF_DATE_KHR` 语义统一。[SPEC] |
| `VK_KHR_maintenance2` | Vulkan 1.1 | `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` / `VK_IMAGE_LAYOUT_DEPTH_ATTACHMENT_STENCIL_READ_ONLY_OPTIMAL`、`VK_IMAGE_CREATE_BLOCK_TEXEL_VIEW_COMPATIBLE_BIT`、specifying image aspect mask 规则。[SPEC] |
| `VK_KHR_maintenance3` | Vulkan 1.1 | `maxPerSetDescriptors` / `maxMemoryAllocationSize` 查询、`VkDescriptorSetLayoutSupport` 查询入口。[SPEC] |
| `VK_KHR_maintenance4` | Vulkan 1.3 | `VkDeviceBufferMemoryRequirements` / `VkDeviceImageMemoryRequirements`，无需创建对象即可查 memory requirements；`VkPhysicalDeviceMaintenance4Properties` 提供 `maxBufferSize`。[SPEC] |
| `VK_KHR_maintenance5` | Vulkan 1.4 | `vkCmdBindIndexBuffer2`（新增 `size` 参数，支持 partial index binding）、`vkGetImageSubresourceLayout2KHR` / `vkGetDeviceImageSubresourceLayoutKHR`、`vkGetRenderingAreaGranularityKHR`、`VkPhysicalDeviceMaintenance5Properties`、对 `VkPipelineCreateFlags2` 的若干补充位等。[SPEC] |
| `VK_KHR_map_memory2` | Vulkan 1.4 core promote | `vkMapMemory2` / `vkUnmapMemory2` 与 `VkMemoryMapInfoKHR` / `VkMemoryUnmapInfoKHR`；**独立扩展**，与 maintenance6 无关。[SPEC] |
| `VK_KHR_maintenance6` | Vulkan 1.4 核心 | `VkBindMemoryStatusKHR`、`VkPhysicalDeviceMaintenance6Properties`、`VK_PIPELINE_CREATE_2_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT` 行为收敛、若干 sync/queue 语义修正。[SPEC] |
| `VK_KHR_maintenance7` | Vulkan 1.3 扩展（2024 年发布） | sample locations 支持、稳定 present mode 查询、`VkPhysicalDeviceMaintenance7PropertiesKHR`。[SPEC] |
| `VK_EXT_swapchain_maintenance1` | 扩展 | retired swapchain 延迟销毁、present mode 运行时切换、present fence、`VkSwapchainPresentModesCreateInfoEXT`。[SPEC] |

---

## 4. 标准使用流程

```text
Step 1：在 device 创建前查询扩展与 feature
→ vkEnumerateDeviceExtensionProperties 检查 VK_KHR_maintenance* / VK_EXT_swapchain_maintenance1
→ Vulkan 1.3+ 项目使用 vkGetPhysicalDeviceFeatures2 + VkPhysicalDeviceVulkan13Features 检查 maintenance4
→ Vulkan 1.4+ 项目使用 VkPhysicalDeviceVulkan14Features 检查 maintenance5 / maintenance6

Step 2：在 VkDeviceCreateInfo 中启用扩展与 feature
→ 老版本（Vulkan 1.0/1.1）将扩展名写入 ppEnabledExtensionNames
→ Vulkan 1.3+ 通过 VkPhysicalDeviceVulkan13Features.maintenance4 显式启用
→ Vulkan 1.4+ 通过 VkPhysicalDeviceVulkan14Features.maintenance5 / .maintenance6 显式启用

Step 3：使用对应能力
→ maintenance3: 查询 VkPhysicalDeviceMaintenance3Properties → maxPerSetDescriptors / maxMemoryAllocationSize → 用 VkDescriptorSetLayoutSupport 校验 descriptor set layout
→ maintenance4: 用 VkDeviceBufferMemoryRequirements / VkDeviceImageMemoryRequirements 预查 memory requirements → 分配 VkDeviceMemory → 再创建对象
→ maintenance5: 使用 vkCmdBindIndexBuffer2 替代 vkCmdBindIndexBuffer，显式指定 index range（size）；vkGetRenderingAreaGranularityKHR / vkGetDeviceImageSubresourceLayoutKHR 也在 maintenance5 中
→ map_memory2: vkMapMemory2 / vkUnmapMemory2 来自独立扩展 VK_KHR_map_memory2，不是 maintenance6
→ maintenance6: 使用 VkBindMemoryStatusKHR 跟踪 bind 状态；查阅 VkPhysicalDeviceMaintenance6Properties
→ swapchain_maintenance1: 通过 VkSwapchainPresentModesCreateInfoEXT 在 vkQueuePresentKHR 时切换 present mode

Step 4：销毁
→ 普通资源按原生命周期销毁
→ swapchain_maintenance1 允许 retired swapchain 延迟到 present 完成后再销毁
```

---

## 5. 关键字段

| 字段 / 入口 | 所属扩展 | 专家关注点 | 常见错误 |
|---|---|---|---|
| `viewport.height` 为负 | maintenance1 (1.1) | 允许 `height < 0` 实现 Y 翻转；通过 negative height 与 `VK_KHR_maintenance1` 行为统一。[SPEC] | 在未启用 maintenance1 / 老 Vulkan 1.0 设备上使用负 viewport height 产生 Validation Error。[TOOL] |
| `VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT` | maintenance1 (1.1) | 允许从 3D image 创建 2D array view；影响 image view 兼容性。[SPEC] | 未设该 bit 却尝试从 3D image 创建 2D view。[TOOL] |
| `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` / `VK_IMAGE_LAYOUT_DEPTH_ATTACHMENT_STENCIL_READ_ONLY_OPTIMAL` | maintenance2 (1.1) | 替代早期混用 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`，明确分离 aspect 用途。[SPEC] | 仍沿用旧 layout 导致 stencil/depth aspect 访问不一致。[TOOL] |
| `VK_IMAGE_CREATE_BLOCK_TEXEL_VIEW_COMPATIBLE_BIT` | maintenance2 (1.1) | 允许对 block-compressed image 创建非格式兼容 view；常用于 BC/ASTC 纹理。[SPEC] | 未设该 bit 却尝试创建 mismatched format view。[TOOL] |
| `maxPerSetDescriptors` / `maxMemoryAllocationSize` | maintenance3 (1.1) | 通过 `VkPhysicalDeviceMaintenance3Properties` 查询，用于描述符集上限与单次分配上限校验。[SPEC] | 假设无上限或硬编码阈值，造成 descriptor set 创建失败或 allocation 失败。[TOOL] |
| `VkDescriptorSetLayoutSupport` | maintenance3 (1.1) | `vkGetDescriptorSetLayoutSupport` 用于预校验 descriptor set layout 是否合法。[SPEC] | 跳过预校验直接创建，遇到 VUID 报错才回头查。[TOOL] |
| `VkDeviceBufferMemoryRequirements.pCreateInfo` | maintenance4 (1.3) | 传入 create info 而非已创建的 `VkBuffer`，即可查 memory requirements。[SPEC] | 仍按老路径先创建 buffer 再查询，造成短暂对象创建开销。[ENGINE] |
| `VkDeviceImageMemoryRequirements.pCreateInfo` | maintenance4 (1.3) | 同上，针对 image；支持 sparse 内存需求查询。[SPEC] | 忽略 `pImageInfo->usage` 与 `flags` 字段，导致查询结果与实际创建不符。[TOOL] |
| `maxBufferSize` | maintenance4 (1.3) | `VkPhysicalDeviceMaintenance4Properties` 提供，用于校验超大 buffer。[SPEC] | 未查询就尝试创建 > 4GB buffer 失败。[TOOL] |
| `vkCmdBindIndexBuffer2.size` | maintenance5 (1.4) | 相比旧 API 新增 `size` 参数，显式指定 index range，便于 partial draw；size 与 indexType 都受校验；**与 `firstInstance` 无关**。[SPEC] | 用 `VK_WHOLE_SIZE` 退化为旧 API 行为，丢失 partial binding 优势。[ENGINE] |
| `VkBindMemoryStatusKHR` | maintenance6 (1.4) | 提供 bind 操作的状态反馈机制。[SPEC] | 忽略 status 字段，无法感知 bind 失败。[TOOL] |
| `VkMemoryMapInfoKHR` / `VkMemoryUnmapInfoKHR` | `VK_KHR_map_memory2` (1.4) | `vkMapMemory2` / `vkUnmapMemory2` 取代旧 `vkMapMemory`，支持 `pNext` 链与扩展行为；**来自独立扩展，非 maintenance6**。[SPEC] | 误以为是 maintenance6 能力；或仍混用旧 API 与新 pNext 结构，导致类型链错乱。[TOOL] |
| `VkSwapchainPresentModesCreateInfoEXT` | swapchain_maintenance1 | 在 `vkQueuePresentKHR` 时通过 `pNext` 传入新 present mode，实现运行时切换。[SPEC] | 切换到未在 `VkSurfacePresentModesEXT` 查询列表中的 mode。[TOOL] |
| retired swapchain 延迟销毁 | swapchain_maintenance1 | 旧 swapchain 不立即销毁，等 GPU 完成所有 in-flight present。[SPEC] | 在未启用扩展时假设有延迟销毁语义，导致 use-after-destroy。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `vkEnumerateDeviceExtensionProperties` 返回值是否包含所需 maintenance 扩展？[SPEC]
- [ ] Vulkan 1.3+ 项目是否通过 `VkPhysicalDeviceVulkan13Features.maintenance4` 显式启用 maintenance4 feature？[SPEC]
- [ ] Vulkan 1.4+ 项目是否通过 `VkPhysicalDeviceVulkan14Features.maintenance5` / `.maintenance6` 显式启用对应 feature？[SPEC]
- [ ] 是否同时启用依赖的扩展（如 swapchain_maintenance1 通常依赖 `VK_KHR_swapchain` 与 `VK_KHR_surface`）？[SPEC]
- [ ] `VkDeviceCreateInfo.pNext` 链上 feature 结构是否与 `ppEnabledExtensionNames` 一致？[TOOL]
- [ ] 是否在创建 descriptor set layout / buffer / image 前用 maintenance3/4 API 预校验？[ENGINE]

### 使用阶段

- [ ] `vkGetDeviceBufferMemoryRequirements` / `vkGetDeviceImageMemoryRequirements` 调用前 device 是否启用了 maintenance4？[SPEC]
- [ ] `vkCmdBindIndexBuffer2` 调用前是否启用 maintenance5？[SPEC]
- [ ] `vkMapMemory2` / `vkUnmapMemory2` 调用前是否启用了独立的 `VK_KHR_map_memory2` 扩展或 Vulkan 1.4 + `VkPhysicalDeviceVulkan14Features` 对应字段（**不是** maintenance6）？[SPEC]
- [ ] `VkSwapchainPresentModesCreateInfoEXT` 切换 mode 前，是否通过 `vkGetPhysicalDeviceSurfacePresentModes2EXT` 查询目标 mode 可用？[SPEC]
- [ ] retired swapchain 在未启用 swapchain_maintenance1 时不能依赖延迟销毁语义？[SPEC]
- [ ] negative `viewport.height` 是否仅在启用 maintenance1 后才使用？[SPEC]

### 销毁阶段

- [ ] retired swapchain 是否等待所有 in-flight image 被 acquire 后再销毁？[SPEC]
- [ ] `vkUnmapMemory2` 后是否仍引用 `VkDeviceMemory`？[SPEC]
- [ ] 维护性扩展本身不引入对象，不需要单独销毁；但其派生对象按原生命周期销毁。[SPEC]

---

## 7. 高频错误

1. 在 Vulkan 1.0 设备上使用 negative viewport height / `VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT`，未启用 `VK_KHR_maintenance1`。[TOOL]
2. 在未启用 maintenance2 的情况下使用 `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL`，触发 Validation Error `VUID-VkAttachmentDescription-layout-03077` 类报错。[TOOL]
3. 想从 3D image 创建 2D view 但未设 `VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT`。[TOOL]
4. 未启用 maintenance4 仍调用 `vkGetDeviceBufferMemoryRequirements`，造成 `VK_ERROR_FEATURE_NOT_PRESENT` 或 Validation 报错。[TOOL]
5. 未启用 maintenance5 仍调用 `vkCmdBindIndexBuffer2`，validation 报 "function pointer not loaded"。[TOOL]
6. 在 `VkDeviceCreateInfo` 中同时启用 Vulkan 1.3 core 与 `VK_KHR_maintenance4` 扩展字符串（Vulkan 1.3 中已不需要扩展字符串），导致冗余但通常无害。[ENGINE]
7. 使用 `vkMapMemory2` 时 `VkMemoryMapInfoKHR.sType` 填错或 `pNext` 链断裂。[TOOL]
8. `VkSwapchainPresentModesCreateInfoEXT` 切换到未在 `VkSurfacePresentModeCapabilitiesEXT` 列表中的 mode。[TOOL]
9. 误以为 retired swapchain 自动延迟销毁，实际未启用 swapchain_maintenance1，导致 use-after-destroy。[TOOL]
10. 在 descriptor set 设计超 `maxPerSetDescriptors` 时未提前用 `vkGetDescriptorSetLayoutSupport` 预校验。[ENGINE]
11. 假设 `maxBufferSize` 无上限，尝试创建超大 buffer 失败。[TOOL]
12. `vkCmdBindIndexBuffer2` 中 `size` 写成字节而非元素数 / 与 `indexType` 不匹配。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDeviceCreateInfo-pNext-02829`：maintenance feature 与扩展启用一致性。[SPEC]
- `VUID-vkCmdBindIndexBuffer2-*`：maintenance5 index buffer 绑定合法性。
- `VUID-VkMemoryMapInfoKHR-*`：maintenance6 内存映射结构合法性。
- `VUID-VkSwapchainPresentModesCreateInfoEXT-*`：present mode 切换合法性。
- `VUID-VkDeviceBufferMemoryRequirements-*` / `VUID-VkDeviceImageMemoryRequirements-*`：maintenance4 查询入口合法性。
- `VUID-VkImageCreateInfo-flags-00688` 等：`VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT` / `BLOCK_TEXEL_VIEW_COMPATIBLE_BIT` 合法性。
- `VUID-VkAttachmentDescription-layout-03077` 等：maintenance2 layout 合法性。

### RenderDoc / AGI

- 在 capture 前确认 device extensions 与 features 已启用。
- 检查 `vkCmdBindIndexBuffer2` 是否被工具正确解析（旧 RenderDoc 版本可能未识别 maintenance5 入口）。
- 检查 dynamic rendering render area 是否与 `vkGetRenderingAreaGranularityKHR` 返回的 granularity 对齐。
- 检查 present mode 切换是否在 timeline 上生效。

### 日志 / 代码检查

- 打印 device 创建时的扩展与 feature 清单，确认 maintenance1-7 / swapchain_maintenance1 已显式启用。
- 检查 `vkGetDeviceBufferMemoryRequirements` 返回的 `memoryRequirements.size` 与 `alignment`。
- 检查 `vkGetDescriptorSetLayoutSupport` 返回的 `supported` 字段。
- 检查 `vkMapMemory2` 返回值与 `VkMemoryMapInfoKHR.pNext` 链。
- 检查 `VkSwapchainPresentModesCreateInfoEXT` 中 present mode 与目标场景是否匹配。
- 检查 retired swapchain 销毁时机是否等待 `vkAcquireNextImageKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR` 或 in-flight 完成后再销毁。

---

## 9. 生命周期风险

### 创建时机

- maintenance 扩展本身在 `VkDevice` 创建时一次性启用，整个 device 生命周期内可用。[SPEC]
- swapchain_maintenance1 派生的 present mode 切换、retired swapchain 延迟销毁语义在 swapchain 创建时通过 `pNext` 链配置。[SPEC]

### 使用时机

- maintenance3 属性查询应在 descriptor set layout 设计阶段进行。[ENGINE]
- maintenance4 memory requirements 查询应在 buffer/image 创建前进行，用于决定 `VkDeviceMemory` 分配策略。[ENGINE]
- maintenance5 `vkCmdBindIndexBuffer2`（含 `size` 参数的 partial index binding）、`vkGetRenderingAreaGranularityKHR` / `vkGetDeviceImageSubresourceLayoutKHR` 在 command buffer recording / 资源查询阶段使用。[SPEC]
- `VK_KHR_map_memory2` 提供的 `vkMapMemory2` / `vkUnmapMemory2` 在 host 端需要持久 / 暂时映射时使用（**非 maintenance6**）。[SPEC]
- swapchain_maintenance1 present mode 切换在 `vkQueuePresentKHR` 调用前通过 `pNext` 注入。

### 销毁时机

- 普通派生对象按各自卡片规则销毁。
- swapchain_maintenance1 启用后，retired swapchain 可延迟到 GPU 完成所有 present 后再销毁；未启用时必须按原 swapchain 卡片规则同步等待。[SPEC]

### in-flight 风险

- maintenance6 引入的 `VkBindMemoryStatusKHR` 用于跟踪 bind 操作完成状态，避免 bind 后立即被 in-flight 命令引用。[SPEC]
- swapchain_maintenance1 retired swapchain 在 in-flight present 未完成前不能销毁。[SPEC]
- `vkCmdBindIndexBuffer2` 引用的 buffer 必须在 command buffer 完成 fence signal 前不被销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `VK_KHR_map_memory2` 提供的 `vkMapMemory2` 提供更明确的映射状态，但仍需配合 host memory barrier 与 `vkDeviceWaitIdle` / fence 使用（**非 maintenance6**）。[SPEC]
- swapchain_maintenance1 提供 present fence，允许 host 等待 present 完成，便于 retired swapchain 销毁时机控制。[SPEC]

### GPU-GPU 同步

- maintenance6 简化同步表达：在 `synchronization2` 基础上进一步收敛 stage/access mask 语义，降低跨 queue 同步表达复杂度。[SPEC]
- maintenance6 的 `VkDependencyInfoKHR` 在 `synchronization2` 之上扩展，但不要混用旧 `vkCmdPipelineBarrier` 与新 `vkCmdPipelineBarrier2KHR`。[ENGINE]

### 资源访问同步

- maintenance2 引入的 `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` 等新 layout 仅在对应 aspect 被读写时使用，需配合 image memory barrier 完成 layout transition。[SPEC]
- maintenance4 提前查 memory requirements 不会改变资源访问同步，但影响 `VkDeviceMemory` 分配与 bind 顺序。[ENGINE]
- swapchain_maintenance1 present mode 切换不直接产生 barrier，但可能改变 vsync / immediate 行为，影响 swapchain image 可用时机。[SPEC]

---

## 11. Android 注意点

不适用：maintenance 系列本身是通用平台扩展，Android 设备根据 GPU 与驱动版本支持度差异较大，需运行时查询。

补充说明：

- Adreno / Mali / PowerVR 早期驱动对 maintenance4（1.3）支持度参差，maintenance5/6（1.4）在现役 Android 设备上覆盖度更低；需查询 `vkEnumerateDeviceExtensionProperties` 或对应版本 feature struct。[ANDROID]
- Android 上 swapchain_maintenance1 支持度与 GPU 厂商驱动版本强相关，部分旧驱动仅支持 `VK_PRESENT_MODE_FIFO_KHR`；切换到 `MAILBOX_KHR` / `IMMEDIATE_KHR` 前必须查询 `VkSurfacePresentModeCapabilitiesEXT`。[ANDROID]
- Android 上 retired swapchain 在 surface 重建（resize / orientation change）场景中常见，未启用 swapchain_maintenance1 时需自己管理 retired swapchain 等待逻辑。[ANDROID]
- maintenance6 在 Android 上的支持度依赖 Vulkan 1.4 驱动可用性，多数现役设备尚未普遍支持；建议先用 `VkPhysicalDeviceVulkan14Properties` 查询 maintenance6 properties 再决定是否启用。[ANDROID]
- `vkMapMemory2` 在 Android 上若启用 `VK_KHR_map_memory2` 扩展或 Vulkan 1.4 可优先使用，否则退回 `vkMapMemory`（**非 maintenance6**）。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- maintenance4 的 `vkGetDeviceBufferMemoryRequirements` / `vkGetDeviceImageMemoryRequirements` 可省去"先创建对象 → 查询 → 销毁"的临时对象创建开销，特别适合 VMA 类分配器预查阶段。[ENGINE]
- `vkGetDescriptorSetLayoutSupport`（maintenance3）可在 layout 设计阶段一次性校验上限，避免运行时反复创建失败。[ENGINE]
- `vkMapMemory2` 支持扩展 pNext 链与一次性 mapping 操作，比旧 API 更便于 batch mapping。[ENGINE]

### GPU 侧

- maintenance6 简化同步表达主要减少 CPU 端表达开销，对 GPU 同步行为本身不变；不会自动带来 GPU 性能提升。[ENGINE]
- swapchain_maintenance1 present mode 切换可在不重建 swapchain 的情况下从 `FIFO` 切换到 `MAILBOX`，减少 stutter；切换本身不产生额外 GPU 工作。[ENGINE]
- maintenance5 `vkCmdBindIndexBuffer2` 支持 partial index binding，可用于实现 mesh LOD 的 sub-draw，减少 CPU 端 buffer 切换。[ENGINE]

### 移动端

- 移动端 GPU 对 `VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT`、`BLOCK_TEXEL_VIEW_COMPATIBLE_BIT` 等支持度参差，启用前查询 `VkPhysicalDeviceImageFormatProperties2`。[ANDROID]
- 移动端 swapchain_maintenance1 present mode 切换到 `IMMEDIATE_KHR` 可能导致 tearing，仅在性能调试或低延迟场景启用。[ANDROID]
- maintenance4 在移动端 VMA 集成中可显著减少临时 buffer/image 创建，降低内存碎片。[ANDROID]
- maintenance6 在 Vulkan 1.4 设备普及前可暂不启用，使用 `synchronization2` + 工程层封装即可。[ANDROID]

---

## 13. 专家经验

经验：
- maintenance 扩展是 Vulkan 工程的"必备修订包"，新项目至少启用 maintenance1-3（Vulkan 1.1）+ maintenance4（Vulkan 1.3）+ maintenance5/6（Vulkan 1.4）+ swapchain_maintenance1（如需要 present mode 切换 / retired swapchain 延迟销毁）。
- 使用 VMA 或自研分配器时，强烈推荐启用 maintenance4，使 memory requirements 查询与对象创建解耦，避免一次性临时对象创建。
- 在 descriptor set 设计阶段，使用 maintenance3 的 `vkGetDescriptorSetLayoutSupport` 进行预校验，避免运行时创建失败。
- maintenance5 启用后，统一使用 `vkCmdBindIndexBuffer2` 替代 `vkCmdBindIndexBuffer`，未来兼容性更好。
- `VK_KHR_map_memory2` 在 Vulkan 1.4 设备上启用后，可逐步迁移 `vkMapMemory` → `vkMapMemory2`；`synchronization2` 启用后可迁移 `vkCmdPipelineBarrier` → `vkCmdPipelineBarrier2`。两者均**不属于 maintenance6**。
- swapchain_maintenance1 在桌面与 Android 高端设备上启用收益明显，特别是窗口 resize / orientation change 场景可显著简化 retired swapchain 处理。
- 不要硬编码 Vulkan 版本号假设 maintenance 扩展可用，必须运行时查询扩展与 feature。

适用条件：
- 新项目或重构项目应优先启用 maintenance1-5 + swapchain_maintenance1。
- Vulkan 1.4 设备项目可考虑启用 maintenance6。
- 需要 sample locations 稳定查询或维护性增强的项目可考虑 maintenance7（扩展，非核心）。

不适用情况：
- 旧项目必须兼容 Vulkan 1.0 设备时，maintenance1+ 均需作为扩展显式启用，且部分功能（如 maintenance4/5/6）不可用。
- 目标平台驱动版本过低（如 Vulkan 1.1 之前）无法使用 maintenance4+。
- 对 swapchain 延迟销毁语义有自定义处理逻辑的项目，可暂不启用 swapchain_maintenance1。

来源：`[ENGINE][SPEC][ANDROID]`

---

## 14. 相关 API 卡片

- `instance.md`
- `logical_device.md`
- `../04_buffer_image_memory/memory_allocation.md`
- `../04_buffer_image_memory/buffer.md`
- `../02_surface_swapchain/swapchain.md`
- `../02_surface_swapchain/swapchain_recreate.md`
- `../08_synchronization/synchronization2.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. 各 maintenance 扩展在不同 Vulkan 版本中的入核心时间与扩展字符串可用性规则。[SPEC]
2. maintenance4 中 `VkDeviceBufferMemoryRequirements` / `VkDeviceImageMemoryRequirements` 的字段合法组合与 sparse image 查询语义。[SPEC]
3. maintenance5 `vkCmdBindIndexBuffer2` 中 `size` 与 `indexType` 的合法组合、`VK_WHOLE_SIZE` 语义；maintenance5 中 `vkGetRenderingAreaGranularityKHR` / `vkGetDeviceImageSubresourceLayoutKHR` 的字段要求。[SPEC]
4. `VK_KHR_map_memory2` 中 `vkMapMemory2` / `vkUnmapMemory2` 的 `VkMemoryMapInfoKHR` pNext 链允许的扩展结构（**独立扩展，非 maintenance6**）。[SPEC]
5. maintenance7 `VkPhysicalDeviceMaintenance7PropertiesKHR` 与 sample locations 相关字段的具体定义。[SPEC]
6. swapchain_maintenance1 中 `VkSwapchainPresentModesCreateInfoEXT` 与 `VkSurfacePresentModeCapabilitiesEXT` 的查询路径与合法切换组合。[SPEC]
7. 各扩展的 VUID 列表与 Validation Layer 检测覆盖度。[TOOL]
8. Android 不同 GPU 厂商驱动对 maintenance4/5/6 / swapchain_maintenance1 的支持矩阵。[ANDROID]
9. Vulkan 1.4 中 maintenance5 / maintenance6 入核心后是否仍需作为扩展启用、与 `VkPhysicalDeviceVulkan14Features.maintenance5` / `.maintenance6`（或独立 `VkPhysicalDeviceMaintenance5Features` / `Maintenance6Features`）的对应关系。[SPEC]
10. maintenance2 中 `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` 等新 layout 与 render pass / dynamic rendering attachment description 的合法组合。[SPEC]

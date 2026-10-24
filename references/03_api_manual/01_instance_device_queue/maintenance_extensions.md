# API Card: Maintenance 扩展系列（VK_KHR_maintenance1～7 / VK_EXT_swapchain_maintenance1）

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 |
| Vulkan 对象 | Maintenance 扩展系列 |
| 常用 API | `vkGetDeviceBufferMemoryRequirements` / `vkGetDeviceImageMemoryRequirements` / `vkCmdBindIndexBuffer2` |
| 适用平台 | 通用，包括 Android |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | maintenance1-3: Vulkan 1.1 core；maintenance4: Vulkan 1.3 core；maintenance5-6: Vulkan 1.4 core；maintenance7: 扩展 |
| 核对基线 | Vulkan 1.4.365 的 `vk.xml`、`vulkan_core.h`、`validusage.json`；官方参考页见第 15 节 |

## 1. 一句话定位

Maintenance 系列汇集若干独立的小功能、查询入口与规范修订；编号不是功能依赖链，也不能把后续扩展当作自动启用全部前序功能的总开关。[SPEC]

## 2. 所属对象链路

```text
VkInstance → VkPhysicalDevice
→ 确认 API 版本、扩展依赖、features 与 properties
→ VkDeviceCreateInfo：选择核心或扩展路径，启用所需 feature
→ VkDevice → 资源查询 / 命令记录 / swapchain 呈现
```

### 上游依赖

- 采用扩展路径时，枚举并启用设备扩展，满足其全部依赖；实例扩展在实例创建时启用。采用已提升的核心路径时，不要求同名扩展字符串一定被枚举，也无需为核心功能启用该字符串。[SPEC]
- `VK_KHR_maintenance4`、`VK_KHR_maintenance6`、`VK_KHR_maintenance7` 的扩展依赖均为 Vulkan 1.1；maintenance5 依赖 Vulkan 1.1 + `VK_KHR_dynamic_rendering`，或 Vulkan 1.3。不能把 maintenance4+ 全部写成“只在其提升后的核心版本才可用”。[SPEC]
- maintenance4 feature 可通过 `VkPhysicalDeviceMaintenance4Features` 或 `VkPhysicalDeviceVulkan13Features` 启用；maintenance5/6 可通过各自独立结构或 `VkPhysicalDeviceVulkan14Features` 启用。聚合结构与其覆盖的独立结构不能同时加入设备创建链。[SPEC]
- 区分“入口由版本/扩展提供”与“某项行为由 feature 控制”。例如 maintenance4 的三个 memory-requirements 查询入口不要求启用 `maintenance4` feature；该 feature 控制其定义列出的 shader、pipeline-layout 生命周期及其他保证。[SPEC]
- EXT swapchain 路径依赖 `VK_KHR_swapchain`、`VK_EXT_surface_maintenance1`，以及 Vulkan 1.1 或 `VK_KHR_get_physical_device_properties2`，并须满足这些依赖的传递依赖；查询并启用 `VkPhysicalDeviceSwapchainMaintenance1FeaturesEXT.swapchainMaintenance1`。[SPEC]

### 下游影响

影响资源预查询、描述符命令参数扩展、索引绑定范围和 WSI 生命周期管理。VMA 等分配器是工具库，不是 Vulkan 对象类型。[ENGINE]

## 3. 核心对象与 API

| 扩展 / 核心版本 | 代表能力与入口 |
|---|---|
| `VK_KHR_maintenance1` / 1.1 | 负 viewport height、3D image 的 2D/2D-array view 支持、`vkTrimCommandPool`。[SPEC] |
| `VK_KHR_maintenance2` / 1.1 | 混合 depth/stencil layouts、`VK_IMAGE_CREATE_BLOCK_TEXEL_VIEW_COMPATIBLE_BIT`、input attachment aspect 指定。[SPEC] |
| `VK_KHR_maintenance3` / 1.1 | `VkPhysicalDeviceMaintenance3Properties` 的 `maxPerSetDescriptors` / `maxMemoryAllocationSize`，`vkGetDescriptorSetLayoutSupport`。[SPEC] |
| `VK_KHR_maintenance4` / 1.3 | `vkGetDeviceBufferMemoryRequirements`、`vkGetDeviceImageMemoryRequirements`、`vkGetDeviceImageSparseMemoryRequirements`；`maxBufferSize`。[SPEC] |
| `VK_KHR_maintenance5` / 1.4 | `vkCmdBindIndexBuffer2`、`vkGetImageSubresourceLayout2`、`vkGetDeviceImageSubresourceLayout`、`vkGetRenderingAreaGranularity`；`VkPipelineCreateFlags2CreateInfo`。[SPEC] |
| `VK_KHR_maintenance6` / 1.4 | `VkBindMemoryStatus` 返回逐资源绑定结果；`vkCmdBindDescriptorSets2` / `vkCmdPushConstants2` 等可扩展参数命令；空索引绑定规则和若干属性。[SPEC] |
| `VK_KHR_maintenance7` / 扩展 | depth/stencil sibling-aspect 访问属性、layered implementation 信息、dynamic buffer 总数限制、fragment shading rate attachment robustness 查询等。[SPEC] |
| `VK_EXT_swapchain_maintenance1` / 扩展 | present fence、逐次 present mode 选择、缩放配置、延迟分配、释放已 acquire 的图像；已提升为 `VK_KHR_swapchain_maintenance1`，不是 Vulkan 1.4 core。[SPEC] |

表中已入核心命令使用无后缀名称；扩展路径使用相应 KHR 名称。EXT swapchain 结构仍是有效别名，本文保留 EXT 路径说明。[SPEC]

`VK_KHR_map_memory2` 提供 `vkMapMemory2` / `vkUnmapMemory2`，并已提升到 Vulkan 1.4；它是独立扩展，没有名为 `mapMemory2` 的 Vulkan 1.4 feature 成员，也不属于 maintenance6。[SPEC]

## 4. 标准使用流程

1. 确认应用与物理设备可用的核心版本；若走扩展路径，枚举扩展并解析依赖。[SPEC]
2. 用 `vkGetPhysicalDeviceFeatures2` 查询 feature，用 `vkGetPhysicalDeviceProperties2` 查询属性；按实际使用的 feature 规则构造设备创建链，不重复加入聚合与独立结构。[SPEC]
3. maintenance3：查询描述符上限，用 `vkGetDescriptorSetLayoutSupport` 获取布局支持结果。此查询不替代所有创建参数合法性检查。[SPEC]
4. maintenance4：以 `VkDeviceBufferMemoryRequirements.pCreateInfo` / `VkDeviceImageMemoryRequirements.pCreateInfo` 查询需求；后续实际创建参数须匹配查询条件。继续满足专用分配、内存类型和绑定规则。[SPEC]
5. maintenance5：需要显式索引范围时使用 `vkCmdBindIndexBuffer2`；`offset` 和 `size` 都以字节计。[SPEC]
6. maintenance6：把 `VkBindMemoryStatus` 加入相应 `VkBindBufferMemoryInfo` / `VkBindImageMemoryInfo.pNext`，通过 `pResult` 获取各项绑定结果；这不是异步完成通知。[SPEC]
7. swapchain present-mode 切换按下列三阶段执行：[SPEC]
   - 查询：在 `VkPhysicalDeviceSurfaceInfo2KHR.pNext` 放 `VkSurfacePresentModeEXT`，在输出 `VkSurfaceCapabilities2KHR.pNext` 放 `VkSurfacePresentModeCompatibilityEXT`，调用 `vkGetPhysicalDeviceSurfaceCapabilities2KHR` 查询兼容模式。
   - 创建：在 `VkSwapchainCreateInfoKHR.pNext` 放 `VkSwapchainPresentModesCreateInfoEXT`，声明将使用的兼容模式集合。
   - 呈现：在 `VkPresentInfoKHR.pNext` 放 `VkSwapchainPresentModeInfoEXT`，为各 swapchain 选择创建时声明的模式，再调用 `vkQueuePresentKHR`。
8. 生命周期管理：需要 present 资源回收信号时，在 `VkPresentInfoKHR.pNext` 使用 `VkSwapchainPresentFenceInfoEXT`；其精确保证见第 9 节。[SPEC]

## 5. 关键字段

| 字段 / 结构 | 关注点 |
|---|---|
| `VkViewport.height` | maintenance1 / Vulkan 1.1 允许负高度；仍须满足 viewport 范围规则。[SPEC] |
| `VK_IMAGE_CREATE_2D_ARRAY_COMPATIBLE_BIT` | 允许符合规则的 3D image 创建 2D 或 2D-array view；不是任意图像视图转换许可。[SPEC] |
| `VK_IMAGE_CREATE_BLOCK_TEXEL_VIEW_COMPATIBLE_BIT` | 配合格式、image/view 类型等约束使用，不允许任意不兼容格式视图。[SPEC] |
| `maxBufferSize` | 查询实现限制；不能硬编码成 4 GB，也不保证该范围内分配总能成功。[SPEC] |
| `vkCmdBindIndexBuffer2.size` | 字节数；非 `VK_WHOLE_SIZE` 时须是索引类型大小的整数倍，且 `offset + size` 不超 buffer 大小。[SPEC] |
| `VkBindMemoryStatus.pResult` | 指向输出 `VkResult`；逐项绑定结果，不是 fence 或 GPU 使用状态。[SPEC] |
| `VkPhysicalDeviceMaintenance6Properties` | 包含 `blockTexelViewCompatibleMultipleLayers`、`maxCombinedImageSamplerDescriptorCount`、`fragmentShadingRateClampCombinerInputs`。[SPEC] |
| `VkPhysicalDeviceMaintenance7PropertiesKHR` | 包含 `separateDepthStencilAttachmentAccess`、`robustFragmentShadingRateAttachmentAccess` 及 dynamic buffer 总量限制；不是 sample locations 或 present-mode 查询结构。[SPEC] |
| `VkSwapchainPresentModesCreateInfoEXT` | swapchain 创建时声明模式集合。[SPEC] |
| `VkSwapchainPresentModeInfoEXT` | 每次呈现时选择集合内模式。[SPEC] |

## 6. 正确性检查点

### 创建阶段

- [ ] 所用入口由可用核心版本或已启用扩展提供，所有依赖满足。
- [ ] 使用的可选行为已查询并按要求启用 feature。
- [ ] Vulkan 1.3 / 1.4 聚合 feature 结构与其覆盖的独立 feature 结构没有重复。
- [ ] 查询 memory requirements 的参数与后续创建一致，且满足查询结构自身的限制。
- [ ] swapchain 声明的模式是查询所得兼容集合的子集。

### 使用阶段

- [ ] 索引范围以字节计，满足对齐、usage、绑定和范围规则。
- [ ] `VK_WHOLE_SIZE` 是合法选择，不是错误或必然的性能损失。
- [ ] 每次呈现使用 `VkSwapchainPresentModeInfoEXT`，不是创建结构。
- [ ] properties 查询没有被误当作 feature 启用。

### 销毁阶段

- [ ] 资源的所有相关使用已经满足销毁条件。
- [ ] present fence 与提交 fence 的覆盖范围没有混淆。
- [ ] 没有把 acquire 返回 `VK_ERROR_OUT_OF_DATE_KHR` 当成所有旧 present 已可安全回收的证明。

## 7. 高频错误

1. 认为扩展提升为核心后，驱动必须继续枚举同名扩展字符串。
2. 认为 maintenance 编号越大就自动启用较小编号的全部行为。
3. 给 `void` 返回的 memory-requirements 查询编造 `VK_ERROR_FEATURE_NOT_PRESENT` 返回值。
4. 把 memory-requirements 查询入口的可用性误写成必须启用 maintenance4 feature。
5. 把 `vkCmdBindIndexBuffer2.size` 当作元素数量；实际单位是字节。
6. 将 maintenance6 描述为 synchronization2 的升级或 stage/access-mask 简化包。
7. 将 `VkBindMemoryStatus.pResult` 当作异步内存绑定完成标志。
8. 把 maintenance7 描述成 sample locations / present-mode 扩展。
9. 在 `VkPresentInfoKHR.pNext` 放 `VkSwapchainPresentModesCreateInfoEXT`。
10. 认为 present fence signal 等于图像已经完成屏幕显示，或扩展会自动销毁 retired swapchain。

## 8. Debug 检查路径

### Validation Layer

以下 VUID 已按本卡基线逐条核对；当前 registry 对 EXT/KHR 别名可能采用 KHR 规范名：[TOOL]

- `VUID-VkDeviceCreateInfo-pNext-06532`：Vulkan 1.3 聚合结构不能与其覆盖的独立结构（包括 maintenance4）同链。
- `VUID-VkDeviceCreateInfo-pNext-10360`：Vulkan 1.4 聚合结构不能与其覆盖的独立结构（包括 maintenance5/6）同链。
- `VUID-vkCmdBindIndexBuffer2-size-08767`：显式 size 必须是索引类型大小的整数倍。
- `VUID-vkCmdBindIndexBuffer2-size-08768`：显式 `offset + size` 不得超出 buffer。
- `VUID-vkCmdBindIndexBuffer2-None-09493`：未启用 maintenance6 时 buffer 不能是空句柄。
- `VUID-VkSwapchainPresentModesCreateInfoKHR-pPresentModes-07763`：创建模式集合受 surface compatibility 查询结果约束。
- `VUID-VkSwapchainPresentModeInfoKHR-pPresentModes-07761`：逐次呈现模式须在对应 swapchain 的创建声明中。

`VUID-VkDeviceCreateInfo-pNext-02829` 实际涉及 Vulkan 1.1 聚合 feature 结构与对应独立结构互斥，不是 maintenance feature 与扩展字符串一致性的通用规则。[SPEC]

### 工具 / 日志

记录有效 API 版本、实际启用的扩展和 feature、查询参数与结果、索引范围及各项 bind 结果。使用支持目标 API 的验证层和捕获工具；具体工具覆盖度按版本实测。[TOOL]

## 9. 生命周期风险

- Maintenance 不引入一个需要销毁的“maintenance 对象”；各资源仍遵循自身生命周期。[SPEC]
- `VkBindMemoryStatus` 只报告绑定调用结果，不允许资源提前销毁，也不替代提交同步。[SPEC]
- present fence 在有关队列操作完成且呈现引擎取得所需对象 payload 引用后 signal；它不一定等到呈现操作完成。[SPEC]
- 对一个 swapchain，引用它的所有历史 present 请求所关联的 fence 都 signal 后，可依据该机制销毁 swapchain；还须满足其他使用的生命周期规则。这个机制不执行自动销毁。[SPEC]
- 不应尝试从 retired swapchain 继续 acquire 来“清空”所有呈现；按规范定义的回收机制管理旧链。[ENGINE]

## 10. 同步风险

- maintenance6 不取代 synchronization2，也没有引入 `VkDependencyInfo`；资源依赖仍按正常 stage/access、布局和队列所有权规则处理。[SPEC]
- 映射/取消映射不会自动等待 GPU 或替代非一致性内存的 flush/invalidate；`vkMapMemory2` 仍是独立映射 API。[SPEC]
- 改变 present mode 不会自动建立渲染到呈现的同步依赖。[SPEC]
- depth/stencil 混合 layouts 应与实际 aspect 使用和 barrier 配套；不能把旧 layout 的使用本身一概认定为错误。[SPEC]

## 11. Android 注意点

- 同样依据实际设备版本、扩展、feature 和 surface 查询结果选择路径；不按 GPU 品牌或“现役设备”概括支持率。[ENGINE]
- 图像支持查询使用 `vkGetPhysicalDeviceImageFormatProperties2`，输入为 `VkPhysicalDeviceImageFormatInfo2`，输出为 `VkImageFormatProperties2`。[SPEC]
- surface 重建、旋转和 resize 时重新评估 swapchain；模式切换仅限兼容集合，不能假设 FIFO、MAILBOX、IMMEDIATE 可相互切换。[SPEC]

## 12. 性能注意点

- maintenance4 查询可省去部分临时对象创建，适合分配器规划；不保证降低碎片或保证分配成功。[ENGINE]
- `vkGetDescriptorSetLayoutSupport` 可提前发现布局支持问题，但不是无条件的性能优化。[ENGINE]
- 可兼容的模式切换可减少重建需求，实际时延、功耗、撕裂和流畅度须测量。[ENGINE]
- 显式索引绑定范围表达可访问范围，不应直接等同于减少 draw 或 buffer 切换。[ENGINE]
- `vkMapMemory2` 具有可扩展参数结构，但单次调用仍映射一个内存对象，不是 batch-mapping API。[SPEC]

## 13. 专家经验

按工程需要选择功能，并保留清晰的核心/扩展入口装载路径。不要仅因编号较新就默认启用，也不要把 properties、features、扩展枚举和实际 surface 能力查询合并成一个“支持”布尔值。[ENGINE]

需要预查询内存时优先评估 maintenance4；需要可扩展 descriptor 命令时评估 maintenance6；需要分层驱动信息或 maintenance7 的属性时查询对应扩展；需要 present 资源回收和模式切换时评估 swapchain maintenance。[ENGINE]

## 14. 相关 API 卡片

- `instance.md`
- `logical_device.md`
- `../04_buffer_image_memory/memory_allocation.md`
- `../04_buffer_image_memory/buffer.md`
- `../02_surface_swapchain/swapchain.md`
- `../02_surface_swapchain/swapchain_recreate.md`
- `../08_synchronization/synchronization2.md`
- `../08_synchronization/pipeline_barrier.md`

## 15. 需要回查官方文档的情况

以下为官方最新参考页；若与固定基线产生差异，应按目标 SDK 对应规范版本核对。[SPEC]

- [Maintenance4 扩展与依赖](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_maintenance4.html)、[maintenance4 feature 的实际范围](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceMaintenance4Features.html)、[buffer memory requirements 查询](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDeviceBufferMemoryRequirements.html)。
- [Maintenance5](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_maintenance5.html)、[索引范围绑定](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdBindIndexBuffer2.html)。
- [Maintenance6](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_maintenance6.html)、[Maintenance7](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_maintenance7.html)。
- [EXT swapchain maintenance 与 KHR 提升](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_swapchain_maintenance1.html)。
- [兼容 present modes 查询及 EXT 别名](https://docs.vulkan.org/refpages/latest/refpages/source/VkSurfacePresentModeCompatibilityKHR.html)、[逐次呈现模式](https://docs.vulkan.org/refpages/latest/refpages/source/VkSwapchainPresentModeInfoKHR.html)。
- [Present fence 的精确回收保证](https://docs.vulkan.org/refpages/latest/refpages/source/VkSwapchainPresentFenceInfoKHR.html)。
- [设备创建 feature 链规则](https://docs.vulkan.org/refpages/latest/refpages/source/VkDeviceCreateInfo.html)。

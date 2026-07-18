# API Card: VkPhysicalDevice

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 |
| Vulkan 对象 | `VkPhysicalDevice` |
| 常用 API | `vkEnumeratePhysicalDevices` / `vkGetPhysicalDeviceFeatures` / `vkGetPhysicalDeviceProperties` / `vkGetPhysicalDeviceMemoryProperties` / `vkEnumerateDeviceExtensionProperties` / `vkGetPhysicalDeviceQueueFamilyProperties` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE] [ANDROID]` |
| 适用 Vulkan 版本 | Vulkan 1.0 核心；feature 查询在 1.1+ 通过 `VkPhysicalDeviceVulkan11Features` 等结构体链 |

---

## 1. 一句话定位

`VkPhysicalDevice` 是对系统实际 GPU 的不可变句柄，承担"能力查询"职责：在创建 `VkDevice` 前，必须通过它查询 features、properties、memory types、queue families、extensions，确定目标硬件能否支持项目所需的渲染/计算路径。[SPEC]

---

## 2. 所属对象链路

```text
VkInstance
→ vkEnumeratePhysicalDevices
→ VkPhysicalDevice[]
→ vkGetPhysicalDeviceProperties / Features / MemoryProperties / QueueFamilyProperties
→ vkEnumerateDeviceExtensionProperties
→ 选择目标 VkPhysicalDevice
→ VkDeviceQueueCreateInfo[]
→ VkDeviceCreateInfo（pNext 链接 VkPhysicalDeviceFeatures2 / Vulkan11Features / Vulkan12Features / ...）
→ vkCreateDevice
→ VkDevice
```

### 上游依赖

- 已成功创建的 `VkInstance`。[SPEC]
- 系统中存在至少一个支持 Vulkan 的 GPU。[SPEC]

### 下游影响

- 决定 `VkDevice` 启用的 features、extensions、queue family 数量与能力。[SPEC]
- 决定可用的 memory type / heap 布局，影响内存分配策略。[SPEC]
- `apiVersion` 决定可使用的 Vulkan 核心 API 版本。[SPEC]
- `limits` / `sparseProperties` 决定资源上限（最大纹理尺寸、UBO 对齐、subgroup 大小等）。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPhysicalDevice`
- `VkPhysicalDeviceProperties` / `VkPhysicalDeviceProperties2`
- `VkPhysicalDeviceFeatures` / `VkPhysicalDeviceFeatures2`
- `VkPhysicalDeviceMemoryProperties` / `VkPhysicalDeviceMemoryProperties2`
- `VkQueueFamilyProperties` / `VkQueueFamilyProperties2`
- `VkExtensionProperties`

### Vulkan 1.1+ 结构体链

- `VkPhysicalDeviceVulkan11Features` / `VkPhysicalDeviceVulkan11Properties`
- `VkPhysicalDeviceVulkan12Features` / `VkPhysicalDeviceVulkan12Properties`
- `VkPhysicalDeviceVulkan13Features` / `VkPhysicalDeviceVulkan13Properties`

这组结构把分散在各 extension 中的 feature/property 按 Vulkan 版本聚合，必须通过 `pNext` 链查询。[SPEC]

### 常用 API

| API | 作用 |
|---|---|
| `vkEnumeratePhysicalDevices` | 枚举系统中所有支持 Vulkan 的物理设备。[SPEC] |
| `vkGetPhysicalDeviceFeatures` | 查询核心 1.0 feature 支持情况（`VkPhysicalDeviceFeatures`）。[SPEC] |
| `vkGetPhysicalDeviceFeatures2` | 通过 `pNext` 链查询扩展 feature（1.1+ 推荐入口）。[SPEC] |
| `vkGetPhysicalDeviceProperties` | 查询 `apiVersion`、`driverVersion`、`deviceName`、`vendorID`、`deviceType`、`limits`、`sparseProperties`。[SPEC] |
| `vkGetPhysicalDeviceProperties2` | 通过 `pNext` 链查询扩展 property。[SPEC] |
| `vkGetPhysicalDeviceMemoryProperties` | 查询 memory type / heap 数量与属性（`deviceLocal` / `hostVisible` / `hostCoherent` / `hostCached` / `lazilyAllocated`）。[SPEC] |
| `vkEnumerateDeviceExtensionProperties` | 查询物理设备支持的 device-level extensions。[SPEC] |
| `vkGetPhysicalDeviceQueueFamilyProperties` | 查询每个 queue family 的 `queueFlags`、`queueCount`、`timestampValidBits`、`minImageTransferGranularity`。[SPEC] |
| `vkGetPhysicalDeviceFormatProperties` | 查询 format 在 linear / optimal tiling 下的 supported usage。[SPEC] |
| `vkGetPhysicalDeviceImageFormatProperties` | 查询特定 image 配置（format/type/tiling/usage/flags）是否支持及资源上限。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心：所有上述查询 API。
- Vulkan 1.1+：`vkGetPhysicalDeviceFeatures2` / `vkGetPhysicalDeviceProperties2` / `vkGetPhysicalDeviceMemoryProperties2` / `vkGetPhysicalDeviceQueueFamilyProperties2` 通过 `pNext` 链提供扩展能力查询。[SPEC]
- `VK_KHR_get_physical_device_properties2`（Vulkan 1.0 上的扩展形态，1.1 升为核心）。
- 厂商 property 扩展：`VK_KHR_driver_properties`（1.2 核心）、`VK_EXT_pci_bus_info`、`VK_EXT_fragment_density_map` 等。

---

## 4. 标准使用流程

```text
vkCreateInstance
→ vkEnumeratePhysicalDevices（先取 count，再取数组）
→ 对每个 physical device：
   vkGetPhysicalDeviceProperties（取得 apiVersion / deviceType / vendorID / limits）
   vkGetPhysicalDeviceFeatures2（pNext 链接项目所需的 Vulkan11Features / Vulkan12Features / Vulkan13Features / 各扩展 feature 结构）
   vkEnumerateDeviceExtensionProperties（确认所需 extension）
   vkGetPhysicalDeviceQueueFamilyProperties（取得 queue family 列表）
   vkGetPhysicalDeviceMemoryProperties（取得 memory type / heap）
   配合 surface 调用 vkGetPhysicalDeviceSurfaceSupportKHR 确定 present queue family
→ 按 feature / extension / queue family / memory 评分选择目标 physical device
→ 构造 VkDeviceQueueCreateInfo[] / VkDeviceCreateInfo（features 与查询结果一致）
→ vkCreateDevice
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkPhysicalDeviceProperties.apiVersion` | 决定可使用的核心 API 版本；驱动可能支持高于 instance 的 `apiVersion`，但只能用到 `min(device, instance)`。[SPEC] | 误以为 `apiVersion` 高就直接调用 1.2+ API，但 instance 未启用 1.2。[TOOL] |
| `driverVersion` | 厂商自定义编码，**不可直接做版本比较**；不同 vendor 编码规则不同。[SPEC] | 按数值大小比较不同 vendor 的 driverVersion。[ENGINE] |
| `deviceType` | `DISCRETE_GPU` / `INTEGRATED_GPU` / `VIRTUAL_GPU` / `CPU` / `OTHER`；影响性能策略与功耗预期。[SPEC] | 移动端 SoC 通常报 `INTEGRATED_GPU`，desktop iGPU 也可能报 `INTEGRATED_GPU`，不要仅凭字段判移动端。[ANDROID] |
| `vendorID` / `deviceID` | 用于厂商识别（NVIDIA=0x10DE、AMD=0x1002、Intel=0x8086、ARM=0x13B5、Qualcomm=0x5143 等）。[SPEC] | 用 `deviceName` 字符串匹配判断厂商，遇到本地化或驱动改名失效。[ENGINE] |
| `limits.maxImageDimension2D` / `maxStorageBufferRange` / `minUniformBufferOffsetAlignment` | 影响纹理上限、UBO/SSBO 偏移对齐、动态索引步长。[SPEC] | 未查询对齐就计算 dynamic offset，导致 validation error。[TOOL] |
| `VkPhysicalDeviceFeatures.samplerAnisotropy` / `geometryShader` / `tessellationShader` / `shaderStorageImageWriteWithoutFormat` 等 | 必须先查询再启用；不支持时需 fallback 路径。[SPEC] | 直接在 `VkDeviceCreateInfo` 中硬编码 `VK_TRUE`，在不支持设备上 `vkCreateDevice` 失败。[TOOL] |
| `VkPhysicalDeviceMemoryProperties.memoryTypes[i].propertyFlags` | 决定 buffer/image 应绑定到哪类内存；典型选择 `DEVICE_LOCAL_BIT`（GPU 高速）、`HOST_VISIBLE_BIT | HOST_COHERENT_BIT`（CPU 上传）、`DEVICE_LOCAL_BIT | HOST_VISIBLE_BIT`（集成 GPU 共享内存）。[SPEC] | 桌面端把 upload buffer 选到 `DEVICE_LOCAL` 而非 `HOST_VISIBLE`，CPU 无法 map。[ENGINE] |
| `memoryHeaps[i].size` | 决定可分配总内存；移动端 heap 通常远小于桌面端。[SPEC] | 未检查 heap size 就预分配大块 VRAM，在低端机 OOM。[ANDROID] |
| `VkQueueFamilyProperties.queueFlags` | `GRAPHICS` / `COMPUTE` / `TRANSFER` / `SPARSE_BINDING` / `PROTECTED`；graphics queue 隐式支持 transfer，compute 隐式支持 transfer。[SPEC] | 假设存在独立的 transfer queue，但移动端常只有 graphics+compute 合一的 queue。[ANDROID] |
| `queueCount` | 每个 family 的可用 queue 数量；多数 GPU 每个 family 只暴露 1 个 queue。[SPEC] | 假设可创建多个 queue 提升并行度，实际无收益。[ENGINE] |
| `timestampValidBits` | 0 表示该 family 不支持 timestamp query。[SPEC] | 在不支持 timestamp 的 queue 上提交 timestamp query，结果未定义。[TOOL] |

---

## 6. 正确性检查点

### 查询阶段

- [ ] `vkEnumeratePhysicalDevices` 是否先取 `pPhysicalDeviceCount`，再以正确 size 取数组？[SPEC]
- [ ] `vkGetPhysicalDeviceQueueFamilyProperties` 是否先以 `NULL` 取 count，再以正确 size 取数组？[SPEC]
- [ ] `vkEnumerateDeviceExtensionProperties` 是否传入了 `pLayerName` 为 `NULL` 以查询实现层扩展？[SPEC]
- [ ] feature 查询是否使用 `vkGetPhysicalDeviceFeatures2` + `pNext` 链而非仅 `vkGetPhysicalDeviceFeatures`？[ENGINE]
- [ ] 是否查询了 `VkPhysicalDeviceVulkan11Features` / `Vulkan12Features` / `Vulkan13Features` 而非逐个扩展结构体？[SPEC]
- [ ] `apiVersion` 与 instance `apiVersion` 取 `min` 后是否仍满足项目要求？[SPEC]

### 选择阶段

- [ ] 是否检查目标 features（如 `samplerAnisotropy`、`shaderStorageImageReadWithoutFormat`、`multiDrawIndirect`、`drawIndirectFirstInstance`）是否支持？[SPEC]
- [ ] 是否检查目标 device extensions（`VK_KHR_swapchain`、`VK_KHR_dynamic_rendering`、`VK_EXT_descriptor_indexing`、`VK_KHR_synchronization2`、`VK_EXT_mesh_shader` 等）是否在 `vkEnumerateDeviceExtensionProperties` 结果中？[SPEC]
- [ ] 是否验证 graphics queue family 存在且 surface present 支持？[SPEC]
- [ ] 是否检查 `limits.maxPerSetDescriptors` / `maxBoundDescriptorSets` 满足 descriptor 设计？[ENGINE]
- [ ] 是否检查 `limits.minUniformBufferOffsetAlignment` 以计算 dynamic UBO 偏移？[SPEC]

### 与 logical device 一致性

- [ ] `VkDeviceCreateInfo.pEnabledFeatures` 或 `pNext` 链上的 feature 结构与查询结果一致（不支持的字段必须为 `VK_FALSE`）？[SPEC]
- [ ] 启用的 extensions 是否都出现在 `vkEnumerateDeviceExtensionProperties` 结果中？[SPEC]
- [ ] `VkDeviceQueueCreateInfo.queueFamilyIndex` 是否引用有效 family？[SPEC]

---

## 7. 高频错误

1. 直接使用 `vkGetPhysicalDeviceFeatures`（1.0 入口）查询，遗漏所有 1.1+ 扩展 feature（如 `shaderDrawParameters`、`descriptorIndexing`、`bufferDeviceAddress`、`timelineSemaphore`、`dynamicRendering`）。[TOOL]
2. 在 `VkDeviceCreateInfo` 中启用 `VkPhysicalDeviceFeatures2` 与 `pEnabledFeatures` 同时非空，结构冲突。[TOOL]
3. 假设存在独立 transfer queue，未运行时查询 `queueFlags`，导致 mobile 上选不到专用 transfer queue。[ANDROID]
4. 用 `deviceName` 字符串匹配判断 vendor，遇到驱动改名或本地化失败；应使用 `vendorID`。[ENGINE]
5. 把 `driverVersion` 当作语义化版本号比较；不同 vendor 编码规则不一致。[ENGINE]
6. 桌面端为 upload buffer 选择纯 `DEVICE_LOCAL` memory type，结果无法 `vkMapMemory`。[ENGINE]
7. 在 `vkGetPhysicalDeviceImageFormatProperties` 未调用前假设某 format+usage+tiling 组合一定支持，在低端机 `vkCreateImage` 失败。[TOOL]
8. 多 GPU 系统（如笔记本 dual GPU）选错 physical device，渲染到非显示 GPU 导致 present 失败或性能差。[ENGINE]
9. `VkPhysicalDeviceVulkan12Features` 中字段（如 `scalarBlockLayout`、`uniformBufferStandardLayout`、`shaderFloat16`、`shaderInt8`）查询后未在 `VkDeviceCreateInfo` 中启用就使用对应功能。[TOOL]
10. 移动端未查询 `protectedMemory` / `subgroupProperties` 等 property，假设 desktop 行为通用。[ANDROID]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCreateDevice-physicalDevice-*`：physical device 合法性。
- `VUID-VkDeviceCreateInfo-pEnabledFeatures-*`：启用的 feature 在该 physical device 上是否支持。
- `VUID-VkDeviceCreateInfo-ppEnabledExtensionNames-*`：扩展依赖与可用性。
- `VUID-vkGetDeviceQueue-queueFamilyIndex-*`：queue family 索引越界。

### RenderDoc / AGI

- RenderDoc 启动时显示物理设备名、driver version、enabled extensions / features，可交叉确认查询结果。[TOOL]
- AGI System Profiler 显示 GPU 型号、driver、memory 布局，用于核对 mobile 上的 `memoryTypes`。[ANDROID]

### 日志 / 代码检查

- 打印 `VkPhysicalDeviceProperties` 全字段（`apiVersion` / `driverVersion` / `deviceName` / `vendorID` / `deviceType`）。
- 打印 `VkPhysicalDeviceMemoryProperties` 的 `memoryTypeCount` / `memoryHeapCount` 及每个 type 的 `propertyFlags` 与所属 `heapIndex`。
- 打印每个 queue family 的 `queueFlags` / `queueCount` / `timestampValidBits`。
- 打印 `VkPhysicalDeviceVulkan11Features` / `Vulkan12Features` / `Vulkan13Features` 关键字段。
- 比对 `vkEnumerateDeviceExtensionProperties` 输出与 `VkDeviceCreateInfo.ppEnabledExtensionNames` 列表。

### 厂商工具

- NVIDIA Nsight Graphics / AMD Radeon Developer Tool Suite / Intel Graphics Performance Analyzer 可查看物理设备详细能力与建议。[VENDOR]

---

## 9. 生命周期风险

### 创建时机

- `VkInstance` 创建之后立即查询，用于 device 选择。[SPEC]

### 使用时机

- 整个应用生命周期内可调用查询 API；`VkPhysicalDevice` 句柄在 `VkInstance` 销毁前一直有效。[SPEC]
- 可在运行时再次查询（如 swapchain recreate 后查询 surface format / present mode）。[SPEC]

### 销毁时机

- `VkPhysicalDevice` 本身不需要销毁；随 `VkInstance` 销毁失效。[SPEC]

### in-flight 风险

- 无。`VkPhysicalDevice` 是不可变句柄，不参与 GPU 命令执行；其派生的 `VkDevice` / `VkQueue` 才有 in-flight 风险。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 查询 API（`vkGetPhysicalDevice*`）为同步 CPU 调用，不涉及 GPU 同步。[SPEC]

### GPU-GPU 同步

- 无。

### 资源访问同步

- 无。

---

## 11. Android 注意点

- Android GPU 阵列高度异构（Adreno / Mali / PowerVR / Xclipse），不同 SoC 的 `memoryTypes` / `queueFamilyProperties` / `limits` 差异大，**所有能力必须运行时查询，不要硬编码**。[ANDROID]
- 移动端 GPU 多为 unified memory 架构，通常存在 `DEVICE_LOCAL_BIT | HOST_VISIBLE_BIT | HOST_COHERENT_BIT` memory type，适合 CPU 写入 + GPU 读取的共享资源；但仍需遍历 `memoryTypes` 选择最优组合。[ANDROID]
- `apiVersion` 取决于设备的 Vulkan loader 与驱动；旧 Android（< Android 10）可能仅支持 Vulkan 1.0；Android 11+ 才大量出现 Vulkan 1.1 驱动；Vulkan 1.2/1.3 需 Android 12+ 与对应驱动。[ANDROID]
- 部分设备报告的 `deviceName` 可能包含 SoC 代号或厂商字符串，不能用于精确匹配。[ANDROID]
- Adreno 设备的 `driverVersion` 编码与 desktop 不同，需查 Qualcomm 文档解读。[ANDROID]
- `VK_KHR_swapchain` / `VK_KHR_android_surface` 是 present 必需，但还有 `VK_ANDROID_external_memory_android_hardware_buffer` 用于与 Gralloc / HardwareBuffer 共享，需查询支持。[ANDROID]
- Mali / Adreno 部分老驱动对 `VkPhysicalDeviceVulkan12Features.scalarBlockLayout` / `uniformBufferStandardLayout` 支持不一，需 fallback 到 std140/std430 传统布局。[ANDROID]
- 多 GPU 设备（如 Samsung DeX、Chromebook）可能枚举出多个 physical device，需根据 `deviceType` 与 surface present 支持选择。[ANDROID]
- Android 上 `vkGetPhysicalDeviceSurfacePresentModesKHR` / `vkGetPhysicalDeviceSurfaceFormatsKHR` 必须每次 swapchain recreate 时重新查询，横竖屏切换或 display 变化可能改变可用集合。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 查询 API 调用次数应集中在初始化阶段，避免每帧调用 `vkGetPhysicalDevice*`。[ENGINE]
- `vkEnumerateDeviceExtensionProperties` 多次调用会反复分配与拷贝字符串数组，应缓存结果。[ENGINE]

### GPU 侧

- 物理设备选择直接决定 GPU 性能上限；笔记本 dual GPU 系统应优先选择 `DISCRETE_GPU`，但需考虑功耗与 present 路径。[ENGINE]
- `deviceType == INTEGRATED_GPU` 通常意味着 unified memory，CPU-GPU 数据传输更便宜，可调整上传策略。[ENGINE]

### 移动端

- 移动端 `limits.maxImageDimension2D` 通常为 4096 或 8192，桌面端为 16384 或 32768；纹理流送需适配。[ANDROID]
- `limits.maxStorageBufferRange` 在部分移动 GPU 上较桌面小，大 SSBO 需分页。[ANDROID]
- `limits.maxPerStageDescriptorStorageImages` / `maxPerStageDescriptorStorageBuffers` 在移动端可能仅为 4~16，影响 bindless 设计。[ANDROID]
- `limits.maxComputeSharedMemorySize` / `maxComputeWorkGroupInvocations` 影响计算 shader 设计，移动端通常远小于桌面。[ANDROID]
- 部分移动 GPU 的 `subgroupProperties` 报告较小 subgroup size（如 Mali 16/32），影响 wave-level 优化；需查询 `VkPhysicalDeviceSubgroupProperties`。[ANDROID]

---

## 13. 专家经验

**经验**：
启动时建立一张"能力快照表"：把 `apiVersion` / `deviceType` / `vendorID` / `deviceName` / 关键 `limits` 字段 / 启用的 features / 启用的 extensions / queue family 布局 / memory type 表全部序列化到日志或 dump 文件。一旦线上出现兼容性或性能问题，第一件事是比对设备能力快照与项目假设的差距。Feature 查询统一走 `vkGetPhysicalDeviceFeatures2` + `VkPhysicalDeviceVulkan11Features` / `Vulkan12Features` / `Vulkan13Features` 链，而非分散查每个扩展结构体——后者容易遗漏或重复。

多 GPU 系统选择策略：优先 `DISCRETE_GPU` 且支持 surface present 的设备；若仅 `INTEGRATED_GPU`，注意功耗预算。Android 上禁止硬编码 vendor/queue family/memory type 索引，所有决策必须基于运行时查询。

**适用条件**：
所有 Vulkan 应用启动阶段；运行时 swapchain recreate 后的 surface 能力查询。

**不适用情况**：
无（所有 Vulkan 应用都必须经过物理设备查询）。

**来源**：`[ENGINE][ANDROID][SPEC]`

---

## 14. 相关 API 卡片

- `instance.md`
- `logical_device.md`
- `maintenance_extensions.md`
- `../02_surface_swapchain/surface.md`
- `../02_surface_swapchain/swapchain.md`
- `../04_buffer_image_memory/memory_allocation.md`
- `../10_android_platform/android_surface.md`

---

## 15. 需要回查官方文档的情况

1. `VkPhysicalDeviceVulkan11Features` / `Vulkan12Features` / `Vulkan13Features` 中每个字段的精确语义与对应的扩展来源（哪些字段是 promoted 自哪个扩展）。
2. `VkPhysicalDeviceLimits` 中各字段的精确含义、单位与对齐规则（如 `minStorageBufferOffsetAlignment` / `optimalBufferCopyOffsetAlignment` / `bufferImageGranularity`）。
3. `VkPhysicalDeviceMemoryProperties` 中 memory type / heap 的合法组合与 `lazilyAllocated` 的语义。
4. 各厂商 `driverVersion` 编码规则（NVIDIA / AMD / Intel / Qualcomm / ARM 各不相同）。
5. `vkGetPhysicalDeviceImageFormatProperties` 的 `tiling` / `usage` / `flags` 合法组合与各 format 的支持矩阵。
6. `VkPhysicalDeviceSubgroupProperties` 中 `supportedStages` / `supportedOperations` / `quadOperationsInAllStages` 的精确语义。
7. Android 上 `VK_ANDROID_external_memory_android_hardware_buffer` 与 Gralloc 用法对应的 physical device 查询入口。
8. 多 GPU 系统（dual GPU / multi-display）下选择 physical device 的最佳实践与厂商文档。
9. Vulkan 1.3 中 `VkPhysicalDeviceVulkan13Properties` 新增字段的精确语义（如 `subgroupSize`、`maxInlineUniformBlockSize` 等）。
10. 不同 vendor 对 `protectedMemory` / `subgroupQuadControl` / `shaderSubgroupRotateClustered` 等高级 feature 的支持矩阵。

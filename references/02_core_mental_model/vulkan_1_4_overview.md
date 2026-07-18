# Vulkan 1.4 概览

> 本文件聚焦 Vulkan 1.4 相对 1.3 的工程级差异。所有硬规则均标注来源等级。
> 来源等级体系：`[SPEC]` > `[ANDROID]` > `[GUIDE]` > `[ENGINE]` > `[HEUR]`（详见 `../01_source_map_and_api_manual_strategy/source_tags.md`）。

---

## 1. 概述

Vulkan 1.4 于 2024 年 12 月正式发布（Khronos 于 2024-12-04 公开宣布）。[SPEC]

核心变更可以概括为三类：

```text
1. 把若干 KHR 扩展 promote 到 core API（含 VK_KHR_maintenance6 等 11 项）。[SPEC]
2. 把 1.3 时代已 promote 但仍为可选的特性升级为 mandatory：
   synchronization2、dynamic rendering、maintenance5、shader integer dot product 等。[SPEC]
3. 把若干 1.4 新 promote 的特性直接设为 mandatory：
   push descriptor、dynamic rendering local read、scalar block layout、
   shader expect assume、shader float controls2、index type uint8 等。[SPEC]
```

工程意义：在 1.4 设备上，过去需要逐项 `vkGetPhysicalDeviceFeatures2` 查询并开启扩展的几项关键能力，现在可以直接依赖 core 行为，简化引擎 feature negotiation 路径。[GUIDE][ENGINE]

判断设备是否为 1.4：

```text
VkPhysicalDeviceProperties.apiVersion >= VK_VERSION_1_4
```

`apiVersion` 由驱动返回，代表驱动实际支持的最高 Vulkan API 版本，与 `instance` 创建时传入的 `vkGetInstanceProcAddr` 链无关。[SPEC]

---

## 2. 核心化扩展

Vulkan 1.4 把以下 KHR 扩展 promote 进 core（不再需要 `VK_KHR_*` 扩展名 / 不再需要在 device extensions 列表里加入这些扩展名）：[SPEC]

```text
VK_KHR_maintenance6
VK_KHR_line_rasterization
VK_KHR_calibrated_timestamps
VK_KHR_push_descriptor              （同时成为 mandatory feature，见 §3）
VK_KHR_shader_expect_assume
VK_KHR_shader_subgroup_rotate
VK_KHR_shader_float_controls2
VK_KHR_dynamic_rendering_local_read （同时成为 mandatory feature，见 §3）
VK_KHR_global_priority
VK_KHR_index_type_uint8
VK_KHR_load_store_op_none
```

重点说明：

### 2.1 VK_KHR_maintenance6 [SPEC]

`maintenance6` 主要修补了若干 1.3 时代遗留的边角场景，对工程实现影响较大的条目：

```text
- VkBindMemoryStatus：vkBindBufferMemory2 / vkBindImageMemory2 可携带返回结果状态，
  便于一次性检查批量 bind 是否成功。
- VkPipelineCreateFlags2CreateInfo：pipeline create flags 升级到 64-bit，
  替代旧的 32-bit VkPipelineCreateFlagBits，避免未来 flag 位用尽。
- vkCmdBindDescriptorSets2KHR：descriptor set 绑定接口的扩展版本，
  支持与 push descriptor / descriptor set variable count 配合更紧凑的绑定路径。
- 允许 vkCmdBindVertexBuffers2 在 vertexInputBindingStride == 0 时复用上一次的 stride。
- 支持 sparse 的 push descriptor 更新（partial update）。
```

工程影响：引擎层在 1.4 设备上可以直接使用 `VkPipelineCreateFlags2CreateInfo` 和 `vkCmdBindDescriptorSets2KHR`，无需在 device extensions 列表声明 `VK_KHR_maintenance6`。[ENGINE]

### 2.2 注意：扩展名仍可保留

虽然 promote 到 core 后不再需要启用扩展，但旧代码继续把扩展名放进 `ppEnabledExtensionNames` 不会报错，只是冗余。建议在 1.4 代码路径下移除这些扩展名，避免 device extension 数量增长。[GUIDE]

---

## 3. 强制功能

Vulkan 1.4 把以下 feature 设为 mandatory，所有声称支持 1.4 的实现必须支持（通过 `vkGetPhysicalDeviceFeatures2` 返回的对应字段必为 `VK_TRUE`）：[SPEC]

```text
pushDescriptor                    （来自 VK_KHR_push_descriptor）
dynamicRenderingLocalRead         （来自 VK_KHR_dynamic_rendering_local_read）
scalarBlockLayout                 （来自 VK_KHR_scalar_block_layout / VK_EXT_scalar_block_layout）
synchronization2                  （1.3 已 promote，1.4 升为 mandatory）
dynamicRendering                  （1.3 已 promote，1.4 升为 mandatory）
maintenance5                      （1.4 promote 并 mandatory）
maintenance6                      （1.4 promote 并 mandatory）
shaderIntegerDotProduct           （1.3 promote，1.4 mandatory）
shaderSubgroupUniformControlFlow
shaderTerminateInvocation
shaderZeroInitializeWorkgroupMemory
uniformBufferStandardLayout
workgroupMemoryExplicitLayout
indexTypeUint8
lineRasterization
calibratedTimestamps
shaderExpectAssume
shaderFloatControls2
shaderSubgroupRotate
globalPriorityQuery
loadStoreOpNone
```

> **注意**：mandatory 只表示"实现必须支持"，**不等于"自动启用"**。使用上述任何 feature 前，仍需在 `VkDeviceCreateInfo.pNext` 中通过对应版本的 feature struct 显式启用（1.2 promote → `VkPhysicalDeviceVulkan12Features`；1.3 promote → `VkPhysicalDeviceVulkan13Features`；1.4 promote → `VkPhysicalDeviceVulkan14Features`）。详见 §6.3 与 §7.2。[SPEC]

### 3.1 Push Descriptors [SPEC]

```text
- 1.4 mandatory：min maxPushDescriptors >= 32。
- 允许不预先创建 VkDescriptorPool / VkDescriptorSet，直接通过 vkCmdPushDescriptorSet2
  （或 1.4 之前的 vkCmdPushDescriptorSetKHR）在 command buffer 中绑定 descriptor。
- 适合 per-draw 频繁变更、binding 数量较少的 descriptor set（slot 0/1 上的 per-object data）。
- 与 push constants 互补：push constants 走 inline 立即数据，push descriptor 走 descriptor 指针。
```

工程影响：1.4 引擎可以为 per-draw 的 `view + proj + object params` 这种小数据量直接使用 push descriptor，避免在 `VkDescriptorPool` 中频繁 alloc/free。[GUIDE][ENGINE]

### 3.2 Dynamic Rendering Local Read [SPEC]

```text
- 允许在 vkCmdBeginRendering / vkCmdEndRendering 之间，
  fragment shader 通过 subpassInput / subpassLoad 读取同一 render pass 中
  前序 pipeline 写入的 color / depth attachment。
- 仍使用 input attachment 机制（subpassInput / subpassLoad），不是普通 texture read。
- 需通过 VkRenderingInputAttachmentIndexInfo 建立 input attachment index 映射，
  通过 VkRenderingAttachmentLocationInfo 控制 attachment 位置映射。
- image 必须处于 VK_IMAGE_LAYOUT_RENDERING_LOCAL_READ_KHR layout，
  并通过 pipeline barrier 建立可见性。
- 深度 / 模板和 MSAA 的 local read 受独立 properties 限制，
  并非所有 1.4 设备都保证支持全部 local read 子特性。
  两个能力字段位于 VkPhysicalDeviceVulkan14Properties：
  dynamicRenderingLocalReadDepthStencilAttachments /
  dynamicRenderingLocalReadMultisampledAttachments（不存在独立的
  VkPhysicalDeviceDynamicRenderingLocalReadPropertiesKHR 结构）。[SPEC]
```

工程影响：deferred / forward+ / tile-based deferred renderer 可以在 dynamic rendering 上下文中使用 local read 读取 G-Buffer，无需创建 `VkRenderPass` / `VkFramebuffer`，但仍需在 shader 中使用 `subpassInput` / `subpassLoad` 并正确配置 attachment index 映射与 layout。[GUIDE][ENGINE]

### 3.3 Scalar Block Layout [SPEC]

```text
- 允许 buffer / uniform / storage block 按 scalar（4-byte）对齐，而非 std140 / std140 relaxed 规则。
- shader 端通过 SCALAR 扩展修饰（GLSL `scalar` / HLSL 风格）或 SPIR-V 的 ScalarBlockLayout 装饰启用。
- 1.4 强制支持，意味着引擎在 1.4 设备上可以统一使用 scalar layout，
  简化 CPU 端结构体布局与 GPU 端读取的对齐处理。
```

工程影响：在 1.4 设备上，可以安全地用 C/C++ `struct` 直接 memcpy 到 uniform buffer，不需要手动加 padding，前提是 struct 中没有比 4 字节更小的类型混排导致跨平台问题。[GUIDE][HEUR]

### 3.4 Synchronization2 与 Dynamic Rendering 的强制化 [SPEC]

```text
- 1.3 时代 promote 但仍可选 → 1.4 mandatory。
- 引擎在 1.4 设备上可以省略：
    if (hasSync2) vkCmdPipelineBarrier2(...) else vkCmdPipelineBarrier(...)
  这类 fallback 路径（"无需 feature 检查" 指无需 vkGetPhysicalDeviceFeatures2 查询是否支持，
   因 mandatory 保证被支持；但仍需在 VkDeviceCreateInfo.pNext 中显式启用对应字段，见 §3 注意）。
- 同理 vkCmdBeginRendering / vkCmdEndRendering 在 1.4 上无需运行时查询支持性，
  但仍需通过 VkPhysicalDeviceVulkan13Features.dynamicRendering 显式启用。
```

---

## 4. 最低限制提升

Vulkan 1.4 把若干 `VkPhysicalDeviceLimits` 字段的最低要求值上调。1.4 实现返回的 limit 不得低于下表。[SPEC]

| Limit 字段 | 1.3 最低 | 1.4 最低 | 工程影响 |
|---|---|---|---|
| `maxFramebufferWidth` | 4096 | **7680** | 可直接渲染大尺寸 RT，无需先查询 |
| `maxFramebufferHeight` | 4096 | **7680** | 同上 |
| `maxFramebufferLayers` | 256 | **2048** | 多层渲染 / 立体贴图 / array RT 能力大幅提升 |
| `maxColorAttachments` | 7 | **8** | deferred / G-Buffer 路径可绑定 8 个 color attachment |
| `maxBoundDescriptorSets` | 4 | **7** | 可同时绑定 7 个 descriptor set（push descriptor + bindless 配合） |
| `maxPushDescriptors` | （扩展定义，0 表示不支持） | **>= 32** | push descriptor 至少 32 个 binding 可用 |
| `maxPushConstantsSize` | 128 | **256** | push constants 容量翻倍，可放更多 per-draw 数据 |

注意点：

```text
1. 8K 渲染不等于 8K swapchain。Swapchain 尺寸受 Surface / display / memory 限制，
   仍需查询 VkSurfaceCapabilitiesKHR.currentExtent / maxImageExtent。[ANDROID][SPEC]
2. maxColorAttachments 提升到 8 仅意味着 attachment 数量上限，
   不保证 8 个 attachment 都能在 tile 内一次性 resolve（移动端 tile memory 仍是真实瓶颈）。[VENDOR]
3. 7 个 bound descriptor sets 是上限值，pipeline layout 实际使用的 set 数量
   仍需匹配 shader 中声明的 set 索引。[SPEC]
4. maxPushConstantsSize 提升到 256 字节，但仍需按 4 字节对齐使用。[SPEC]
```

最低限制只是 floor。具体设备的 limit 仍可能更高，必须用 `vkGetPhysicalDeviceProperties` 读取实际值后再使用。[SPEC]

---

## 5. 与 Vulkan 1.3 的差异

| 维度 | Vulkan 1.3 | Vulkan 1.4 |
|---|---|---|
| 发布时间 | 2022-01 | 2024-12 [SPEC] |
| 核心 promote 的 KHR 扩展数 | 11 项（含 sync2、dynamic rendering、maintenance4 等） | 11 项新增（含 maintenance6、push descriptor、dynamic rendering local read 等）[SPEC] |
| mandatory feature 数 | 较少（dynamic state、descriptor indexing 等仍可选） | 大幅增加（sync2、dynamic rendering、push descriptor、scalar block layout、maintenance5/6 等 mandatory）[SPEC] |
| maxFramebufferWidth/Height 下限 | 4096 | 7680 [SPEC] |
| maxColorAttachments 下限 | 7 | 8 [SPEC] |
| maxFramebufferLayers 下限 | 256 | 2048 [SPEC] |
| maxBoundDescriptorSets 下限 | 4 | 7 [SPEC] |
| maxPushConstantsSize 下限 | 128 | 256 [SPEC] |
| Push Descriptor | 可选（`VK_KHR_push_descriptor`） | mandatory，min 32 [SPEC] |
| Dynamic Rendering Local Read | 不存在 | mandatory [SPEC] |
| Scalar Block Layout | 可选（`VK_KHR_scalar_block_layout`） | mandatory [SPEC] |
| Pipeline Create Flags | 32-bit | 64-bit（`VkPipelineCreateFlags2CreateInfo`，来自 maintenance6）[SPEC] |
| Android 平台要求 | Android 14 起新设备 Vulkan 1.3 要求 | Android 16 起新设备开始支持 Vulkan 1.4（详见 §6）[ANDROID] |
| 典型驱动覆盖 | 主流桌面 + Android 主流设备成熟 | 桌面较快跟进，Android 移动端 2025-2026 逐步覆盖 [ANDROID][VENDOR] |

工程结论：1.4 不是颠覆性升级，而是 1.3 时代“事实标准”特性的正式 mandatory 化。从 1.3 升级到 1.4 的工作量主要在 feature negotiation 简化与 limit 假设更新，而非 API 重写。[GUIDE][ENGINE]

---

## 6. Android 支持时间线

### 6.1 平台层 [ANDROID]

```text
- Android 14（2023 发布）：要求新设备支持 Vulkan 1.3（针对特定硬件档位）。
- Android 15（2024 发布）：扩大 Vulkan 1.3 覆盖范围。
- Android 16（2025 发布）：平台开始支持 Vulkan 1.4。
  注意：平台支持 != 所有 Android 16 设备都升级到 1.4 驱动。
  Android 16 提供了 1.4 的 CTS / 平台 API 路径，
  但具体是否为 1.4 取决于 SoC 厂商驱动是否完成适配。
```

### 6.2 厂商驱动跟进 [VENDOR][ANDROID]

```text
- Imagination（PowerVR）：基于 Rogue / DXT 架构的新驱动逐步支持 1.4。
- Qualcomm（Adreno）：Adreno 7.x / 8.x 系列驱动从 2025 起逐步支持 1.4。
- Arm（Mali）：Valhall / 5th Gen 架构驱动从 2025-2026 逐步跟进。
- 三星 Xclipse（AMD 定制 GPU）：依 AMD 桌面驱动进度跟进。
```

厂商驱动具体可用性必须运行时查询，不能按 SoC 型号硬编码判断。[VENDOR][ANDROID]

### 6.3 运行时查询 [SPEC]

```text
VkPhysicalDeviceProperties props;
vkGetPhysicalDeviceProperties(physicalDevice, &props);

if (props.apiVersion >= VK_VERSION_1_4) {
    // 1.4 路径：mandatory feature 保证被支持（vkGetPhysicalDeviceFeatures2 返回 VK_TRUE），
    //          但仍需在 VkDeviceCreateInfo.pNext 中显式启用对应字段：
    //          - Vulkan 1.3 promote（sync2 / dynamicRendering / scalarBlockLayout 等）
    //            → VkPhysicalDeviceVulkan13Features 对应字段；
    //          - Vulkan 1.4 promote（push descriptor / dynamic rendering local read /
    //            maintenance5 / maintenance6 等）
    //            → VkPhysicalDeviceVulkan14Features 对应字段。
    //          注意 sync2 是 1.3 promote，字段在 Vulkan13Features，不在 Vulkan14Features。
    //          省略启用会导致调用相关 API 时 validation error 或 undefined behavior。[SPEC]
} else if (props.apiVersion >= VK_VERSION_1_3) {
    // 1.3 路径：仍需查询 VkPhysicalDeviceVulkan13Features 中的 sync2 / dynamicRendering。
} else {
    // 1.2 及以下：扩展路径 + 完整 feature 查询。
}
```

注意：

```text
1. apiVersion 是驱动支持的最高 API 版本，与 instance 创建时传入的版本无关。
   instance 版本只决定可用的入口函数集合。[SPEC]
2. Android 上同一设备的 apiVersion 可能随 OTA 驱动更新而提升，
   不要在 APK 里硬编码 1.4 / 1.3 分支，必须每次启动时查询。[ANDROID]
3. 即使 apiVersion >= 1.4，仍应优先走 validation layer 验证 1.4 行为，
   早期驱动可能存在 bug。[TOOL][ANDROID]
```

---

## 7. 迁移建议

### 7.1 何时迁移到 1.4 基线 [GUIDE][ENGINE]

```text
- 目标设备以桌面 GPU + 2025 年后的 Android 高端机为主：可立即以 1.4 为目标基线。
- 目标设备仍包含 Android 14 / 15 中低端机：保留 1.3 fallback，1.4 作为优化路径。
- 项目当前以 1.3 + 大量 KHR 扩展启用：迁移成本低，主要是清理冗余的 feature 查询。
```

### 7.2 迁移步骤 [ENGINE]

```text
1. 升级 Vulkan Headers / Loader 到 1.4（含 VK_VERSION_1_4 宏）。
2. 升级 Validation Layer 到匹配版本，避免误报。
3. 在 device selection 阶段加入 apiVersion >= VK_VERSION_1_4 分支。
4. 在 1.4 分支内：
   a. 移除 VK_KHR_push_descriptor / VK_KHR_dynamic_rendering_local_read /
      VK_KHR_scalar_block_layout / VK_KHR_maintenance6 等扩展名。
   b. 移除对应 feature 的查询代码（仍可保留一次 sanity assert 确认驱动合规）。
      注意：mandatory 不等于不需启用 — 仍需在 VkDeviceCreateInfo.pNext 中通过
      VkPhysicalDeviceVulkan14Features 显式启用对应字段。[SPEC]
   c. 用 VkPipelineCreateFlags2CreateInfo 替换旧 pipeline flags（可选）。
   d. 引擎层 renderer 把 G-Buffer 读取从传统 input attachment 迁移到 local read
      （仍使用 subpassInput / subpassLoad，但无需 VkRenderPass / VkFramebuffer）。
   e. 在 VkDeviceCreateInfo.pNext 中按字段所在版本启用对应 feature struct：
      - VkPhysicalDeviceVulkan12Features: scalarBlockLayout（1.2 promote）
      - VkPhysicalDeviceVulkan13Features: synchronization2 / dynamicRendering（1.3 promote）
      - VkPhysicalDeviceVulkan14Features: pushDescriptor / dynamicRenderingLocalRead /
        maintenance5 / maintenance6（1.4 promote）
      切勿把 1.2/1.3 promote 字段写入 Vulkan14Features —— 该结构体中不存在这些字段。[SPEC]
5. 更新 limit 假设：maxFramebufferWidth/Height 可直接假设 >= 7680，
   maxColorAttachments >= 8，maxBoundDescriptorSets >= 7，maxPushConstantsSize >= 256。
6. 移除 sync2 / dynamic rendering 的 fallback 路径（仅在 1.4 分支内）。
```

### 7.3 不要做的事 [HEUR][ENGINE]

```text
- 不要在 1.4 分支内完全删除 feature 查询代码，保留一份 minimal assert 用作驱动合规性检查。
- 不要把 7680 framebuffer 当成日常 RT，移动端 tile memory 与带宽仍是真实约束。
- 不要假设所有 1.4 设备都把 maintenance6 的 partial push descriptor update 实现得很好，
  上线前用 RenderDoc / AGI 抓帧验证。[TOOL]
- 不要立刻全面切换 push descriptor 替代传统 descriptor pool，
  建议先在 per-draw 小数据量场景试点，确认性能与正确性后再扩展。[GUIDE]
```

### 7.4 验证路径 [TOOL]

```text
1. Validation Layer（1.4 匹配版本）跑过完整渲染路径，无 VUID 报错。
2. RenderDoc 抓帧确认：
   - descriptor binding 路径正确（含 push descriptor）。
   - dynamic rendering local read 在 G-Buffer 读取场景下输出正确。
   - scalar block layout 下，C struct 与 shader 读取一致。
3. AGI 在 Android 高端机上 trace，确认无 1.4 路径性能退化。
4. 多设备回归：至少覆盖一家 Adreno / Mali / PowerVR / 桌面 NVIDIA / AMD。
```

---

## 8. 相关文件

- `synchronization_lifecycle.md` — Synchronization2 fallback 与 1.4 简化路径。
- `modern_patterns.md` — bindless / timeline semaphore / dynamic state 等 1.3+ 模式。
- `frame_lifecycle.md` — frames-in-flight 与 1.4 limit 提升后的资源管理。
- `../03_api_manual/05_descriptor/push_descriptor.md` — push descriptor API 细节。
- `../03_api_manual/07_rendering/dynamic_rendering.md` — dynamic rendering 与 local read API。

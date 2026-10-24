# Vulkan 1.4 概览

> 本文件聚焦 Vulkan 1.4 相对 1.3 的工程级差异。所有硬规则均标注来源等级。
> 来源等级体系：`[SPEC]` > `[ANDROID]` > `[GUIDE]` > `[ENGINE]` > `[HEUR]`（详见 `../01_source_map_and_api_manual_strategy/source_tags.md`）。

---

## 1. 概述

Vulkan 1.4 于 2024 年 12 月正式发布（Khronos 于 2024-12-04 公开宣布）。[SPEC]

核心变更可以概括为三类：

```text
1. 把 16 项 KHR / EXT 扩展 promote 到 core API（含 maintenance5 / maintenance6）。[SPEC]
2. 把早期核心版本中仍可选的特性升级为 mandatory，例如 scalarBlockLayout。
   synchronization2、dynamicRendering、shaderIntegerDotProduct 在 1.3 已必须支持。[SPEC]
3. 把若干 1.4 新 promote 的特性直接设为 mandatory：
   push descriptor、dynamic rendering local read、
   shader expect assume、shader float controls2、index type uint8 等。[SPEC]
```

工程意义：在 1.4 设备上，过去需要逐项 `vkGetPhysicalDeviceFeatures2` 查询并开启扩展的几项关键能力，现在可以直接依赖 core 行为，简化引擎 feature negotiation 路径。[GUIDE][ENGINE]

判断设备是否为 1.4：

```text
VkPhysicalDeviceProperties.apiVersion >= VK_API_VERSION_1_4
```

`apiVersion` 是物理设备支持的 API 版本；核心调用路径还必须匹配应用请求的 API 版本和实际可用入口。`VK_VERSION_1_4` 是头文件能力宏，不能用作版本数值比较。[SPEC]

---

## 2. 核心化扩展

Vulkan 1.4 把以下 16 项扩展 promote 进 core；走对应核心路径时无需启用原扩展字符串，但 feature、properties 和核心化后的差异仍需核对：[SPEC]

```text
VK_KHR_maintenance6
VK_KHR_maintenance5
VK_KHR_map_memory2
VK_KHR_line_rasterization
VK_KHR_push_descriptor              （同时成为 mandatory feature，见 §3）
VK_KHR_shader_expect_assume
VK_KHR_shader_subgroup_rotate
VK_KHR_shader_float_controls2
VK_KHR_dynamic_rendering_local_read （同时成为 mandatory feature，见 §3）
VK_KHR_global_priority
VK_KHR_index_type_uint8
VK_KHR_load_store_op_none
VK_KHR_vertex_attribute_divisor
VK_EXT_host_image_copy
VK_EXT_pipeline_protected_access
VK_EXT_pipeline_robustness
```

重点说明：

### 2.1 VK_KHR_maintenance6 [SPEC]

`maintenance6` 主要修补了若干 1.3 时代遗留的边角场景，对工程实现影响较大的条目：

```text
- VkBindMemoryStatus：vkBindBufferMemory2 / vkBindImageMemory2 可携带返回结果状态，
  便于一次性检查批量 bind 是否成功。
- vkCmdBindDescriptorSets2 / vkCmdPushConstants2：提供可通过 pNext 扩展的绑定接口。
- 配合 push descriptor 提供 vkCmdPushDescriptorSet2 / vkCmdPushDescriptorSetWithTemplate2。
- 放宽 index buffer 的空 handle 绑定规则；读取零值仍需 nullDescriptor 等前提。
- VkPipelineCreateFlags2CreateInfo 来自 maintenance5，不属于 maintenance6。
```

工程影响：按需启用 maintenance5 / maintenance6 feature 后使用对应核心命令，不把 64-bit pipeline flags 或 stride 行为误归到 maintenance6。依据：[maintenance5](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_maintenance5.html)、[maintenance6](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_maintenance6.html)。[SPEC][ENGINE]

### 2.2 核心化不保证扩展名仍被枚举

核心化不保证设备仍枚举原扩展名。只有 `vkEnumerateDeviceExtensionProperties` 确认支持的扩展才能放进 `ppEnabledExtensionNames`；走 1.4 核心路径时移除不再需要的字符串，低版本扩展路径继续按查询结果启用。[SPEC]

---

## 3. 强制功能

下列为常用 feature 的最低核心支持版本与字段归属，完整清单查 [Feature Requirements](https://docs.vulkan.org/spec/latest/chapters/features.html#features-requirements)。不要把扩展名、feature 字段和无独立 feature bit 的功能混列。[SPEC]

```text
Vulkan 1.2 已必须支持（VkPhysicalDeviceVulkan12Features）：
  timelineSemaphore / uniformBufferStandardLayout
Vulkan 1.3 已必须支持（VkPhysicalDeviceVulkan13Features）：
  synchronization2 / dynamicRendering / shaderIntegerDotProduct /
  shaderTerminateInvocation / shaderZeroInitializeWorkgroupMemory / maintenance4
Vulkan 1.4 新增必须支持：
  scalarBlockLayout（VkPhysicalDeviceVulkan12Features，1.2 已核心化）
  pushDescriptor / dynamicRenderingLocalRead / maintenance5 / maintenance6 /
  indexTypeUint8 / bresenhamLines / shaderExpectAssume / shaderFloatControls2 /
  shaderSubgroupRotate / shaderSubgroupRotateClustered / globalPriorityQuery /
  pipelineRobustness（以上字段位于 VkPhysicalDeviceVulkan14Features）
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
- 按成员 scalar 类型的大小计算对齐，不是统一 4-byte；向量、矩阵和数组仍需核对布局。
- GLSL 使用 GL_EXT_scalar_block_layout 与 layout(scalar)；SPIR-V 通过 Offset /
  ArrayStride / MatrixStride 等表达具体布局，不存在 ScalarBlockLayout 装饰。
- 1.4 强制支持，意味着引擎在 1.4 设备上可以统一使用 scalar layout，
  简化 CPU 端结构体布局与 GPU 端读取的对齐处理。
```

工程影响：可减少部分 padding，但 memcpy 前仍需用反射结果与 `offsetof` / `sizeof` 核对成员偏移、数组/矩阵 stride、矩阵主序和 host 类型布局，不能因启用 scalar layout 就假设任意 C/C++ struct 自动匹配。依据：[Shader Memory Layout](https://docs.vulkan.org/guide/latest/shader_memory_layout.html)。[GUIDE][ENGINE]

### 3.4 Synchronization2 与 Dynamic Rendering 的版本边界 [SPEC]

```text
- 1.3 已核心化且必须支持，1.4 继承该要求。
- 应用采用 1.3+ 核心路径并显式启用 feature 后，可以省略：
    if (hasSync2) vkCmdPipelineBarrier2(...) else vkCmdPipelineBarrier(...)
  这类 fallback 路径（"无需 feature 检查" 指无需 vkGetPhysicalDeviceFeatures2 查询是否支持，
   因 mandatory 保证被支持；但仍需在 VkDeviceCreateInfo.pNext 中显式启用对应字段，见 §3 注意）。
- 同理 vkCmdBeginRendering / vkCmdEndRendering 在 1.3+ 上保证支持，
  但仍需通过 VkPhysicalDeviceVulkan13Features.dynamicRendering 显式启用。
```

---

## 4. 最低限制提升

Vulkan 1.4 把若干 `VkPhysicalDeviceLimits` 字段的最低要求值上调。1.4 实现返回的 limit 不得低于下表。[SPEC]

| Limit 字段 | 1.3 最低 | 1.4 最低 | 工程影响 |
|---|---|---|---|
| `maxFramebufferWidth` | 4096 | **7680** | 仍需核对 image format、samples、内存与 surface 限制 |
| `maxFramebufferHeight` | 4096 | **7680** | 同上 |
| `maxFramebufferLayers` | 256 | **256** | 1.4 未将该下限提高到 2048 |
| `maxImageArrayLayers` | 256 | **2048** | 区分 image array 层数与 framebuffer 层数 |
| `maxColorAttachments` | 4 | **8** | 1.3 核心下限为 4，Roadmap 2022 才要求 7 |
| `maxBoundDescriptorSets` | 4 | **7** | 可同时绑定 7 个 descriptor set（push descriptor + bindless 配合） |
| `maxPushDescriptors` | 非 1.3 核心保证；扩展路径查询 | **>= 32** | 限制单个 push descriptor set 的 descriptor 总数，不是 binding 数 |
| `maxPushConstantsSize` | 128 | **256** | push constants 容量翻倍，可放更多 per-draw 数据 |

注意点：

```text
1. 8K 渲染不等于 8K swapchain。Swapchain 尺寸受 Surface / display / memory 限制，
   仍需查询 VkSurfaceCapabilitiesKHR.currentExtent / maxImageExtent。[ANDROID][SPEC]
2. maxColorAttachments 提升到 8 仅意味着 attachment 数量上限，
   不保证 8 个 attachment 都能在 tile 内一次性 resolve（移动端 tile memory 仍是真实瓶颈）。[VENDOR]
3. 7 是 1.4 对 maxBoundDescriptorSets 的最低保证值，不是所有设备的固定上限；
   实际数量查设备属性，pipeline layout 覆盖 shader 中使用的 set 索引。[SPEC]
4. maxPushConstantsSize 提升到 256 字节，但仍需按 4 字节对齐使用。[SPEC]
```

最低限制只是 floor。具体设备的 limit 仍可能更高，必须用 `vkGetPhysicalDeviceProperties` 读取实际值后再使用。[SPEC]

依据：[Limits / Required Limits](https://docs.vulkan.org/spec/latest/chapters/limits.html#limits-minmax)。`maxPushDescriptors` 在 1.4 通过 `VkPhysicalDeviceVulkan14Properties` 查询，不是 `VkPhysicalDeviceLimits` 成员。

---

## 5. 与 Vulkan 1.3 的差异

| 维度 | Vulkan 1.3 | Vulkan 1.4 |
|---|---|---|
| 发布时间 | 2022-01 | 2024-12 [SPEC] |
| 核心化能力 | 已包含 sync2、dynamic rendering、maintenance4 | 新增 16 项 KHR / EXT 扩展，见 §2 [SPEC] |
| 必须支持的 feature | 包含 sync2、dynamic rendering 等 | 新增 pushDescriptor、scalarBlockLayout、maintenance5/6 等要求 [SPEC] |
| maxFramebufferWidth/Height 下限 | 4096 | 7680 [SPEC] |
| maxColorAttachments 下限 | 4 | 8 [SPEC] |
| maxFramebufferLayers 下限 | 256 | 256 [SPEC] |
| maxBoundDescriptorSets 下限 | 4 | 7 [SPEC] |
| maxPushConstantsSize 下限 | 128 | 256 [SPEC] |
| Push Descriptor | 可选（`VK_KHR_push_descriptor`） | mandatory，min 32 [SPEC] |
| Dynamic Rendering Local Read | 可通过 KHR 扩展使用 | 基础 local read 必须支持，depth/stencil / MSAA 查 properties [SPEC] |
| Scalar Block Layout | 1.2 已核心化，核心支持可选；扩展名为 `VK_EXT_scalar_block_layout` | 必须支持 [SPEC] |
| Pipeline Create Flags | 核心为 32-bit，可用 maintenance5 扩展路径 | 核心包含 64-bit flags，来自 maintenance5 [SPEC] |
| Android 可用性 | 按设备实际能力选择 | 按设备实际能力选择，见 §6 [ANDROID] |

工程结论：1.4 不是颠覆性升级，而是 1.3 时代“事实标准”特性的正式 mandatory 化。从 1.3 升级到 1.4 的工作量主要在 feature negotiation 简化与 limit 假设更新，而非 API 重写。[GUIDE][ENGINE]

---

## 6. Android 能力边界

### 6.1 平台层 [ANDROID]

```text
- Android 系统版本、NDK 头文件版本与设备驱动暴露的 Vulkan 能力分别核对。
- 不按 Android 大版本直接推断所有设备的 Vulkan API 版本。
- 发行要求涉及 Android CDD / CTS 时，必须查询目标版本对应的官方条款。
```

### 6.2 设备与驱动 [VENDOR][ANDROID]

```text
- 记录 GPU、driverVersion、apiVersion、所需 extension / feature / properties。
- 同一 SoC 的设备与 OTA 驱动可能不同，不使用未核实的厂商支持时间线作为能力依据。
```

厂商驱动具体可用性必须运行时查询，不能按 SoC 型号硬编码判断。[VENDOR][ANDROID]

平台依据：[Android Vulkan Getting Started](https://developer.android.com/ndk/guides/graphics/getting-started)。

### 6.3 运行时查询 [SPEC]

```text
VkPhysicalDeviceProperties props;
vkGetPhysicalDeviceProperties(physicalDevice, &props);

if (props.apiVersion >= VK_API_VERSION_1_4) {
    // 1.4 路径：mandatory feature 保证被支持（vkGetPhysicalDeviceFeatures2 返回 VK_TRUE），
    //          但仍需在 VkDeviceCreateInfo.pNext 中显式启用对应字段：
    //          - Vulkan 1.2 promote：scalarBlockLayout → VkPhysicalDeviceVulkan12Features；
    //          - Vulkan 1.3 promote（sync2 / dynamicRendering）
    //            → VkPhysicalDeviceVulkan13Features 对应字段；
    //          - Vulkan 1.4 promote（push descriptor / dynamic rendering local read /
    //            maintenance5 / maintenance6 等）
    //            → VkPhysicalDeviceVulkan14Features 对应字段。
    //          注意 sync2 是 1.3 promote，字段在 Vulkan13Features，不在 Vulkan14Features。
    //          省略启用会导致调用相关 API 时 validation error 或 undefined behavior。[SPEC]
} else if (props.apiVersion >= VK_API_VERSION_1_3) {
    // 1.3 路径：sync2 / dynamicRendering 已必须支持，但仍需显式启用。
    // scalarBlockLayout 的核心支持仍可选，按需查询并启用。
} else {
    // 1.2 及以下：扩展路径 + 完整 feature 查询。
}
```

注意：

```text
1. 上述仅为设备能力分支；创建 instance 前还需协商应用请求版本与 loader 版本，
   核心路径匹配应用版本、设备版本与可用入口，不能仅凭设备版本调用更高版本 API。[SPEC]
2. Android 上同一设备的 apiVersion 可能随 OTA 驱动更新而提升，
   不要在 APK 里硬编码 1.4 / 1.3 分支，必须每次启动时查询。[ANDROID]
3. 即使 apiVersion >= 1.4，仍应优先走 validation layer 验证 1.4 行为，
   早期驱动可能存在 bug。[TOOL][ANDROID]
```

---

## 7. 迁移建议

### 7.1 何时迁移到 1.4 基线 [GUIDE][ENGINE]

```text
- 目标设备清单已验证满足 1.4 及所需能力：可将 1.4 作为项目基线。
- 目标清单仍包含较低版本设备：保留相应核心或扩展路径，不以年份和档位代替查询。
- 项目当前以 1.3 + 大量 KHR 扩展启用：迁移成本低，主要是清理冗余的 feature 查询。
```

### 7.2 迁移步骤 [ENGINE]

```text
1. 升级 Vulkan Headers / Loader 到 1.4（含 VK_VERSION_1_4 宏）。
2. 升级 Validation Layer 到匹配版本，避免误报。
3. 在 device selection 阶段加入 apiVersion >= VK_API_VERSION_1_4 分支，并匹配应用版本。
4. 在 1.4 分支内：
   a. 移除 VK_KHR_push_descriptor / VK_KHR_dynamic_rendering_local_read /
      VK_EXT_scalar_block_layout / VK_KHR_maintenance6 等不再需要的扩展名。
   b. 移除对应 feature 的查询代码（仍可保留一次 sanity assert 确认驱动合规）。
      注意：mandatory 不等于不需启用 — 仍需在 VkDeviceCreateInfo.pNext 中通过
      对应版本的 feature struct 显式启用字段，不能全部写进 Vulkan14Features。[SPEC]
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
6. 1.3+ 核心路径显式启用 sync2 / dynamic rendering 后，可移除该分支内的旧 API fallback。
```

### 7.3 不要做的事 [HEUR][ENGINE]

```text
- 不要在 1.4 分支内完全删除 feature 查询代码，保留一份 minimal assert 用作驱动合规性检查。
- 不要把 7680 framebuffer 当成日常 RT，移动端 tile memory 与带宽仍是真实约束。
- 不要把 maintenance6 的扩展绑定接口视为同步替代，
  上线前仍需检查 descriptor 有效性、资源生命周期与目标设备输出。[TOOL]
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

- [Vulkan 1.4 核心化清单与差异](https://docs.vulkan.org/refpages/latest/refpages/source/VK_VERSION_1_4.html)
- [API 版本数值宏](https://docs.vulkan.org/refpages/latest/refpages/source/VK_API_VERSION_1_4.html)
- [Vulkan12Features](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceVulkan12Features.html) / [Vulkan13Features](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceVulkan13Features.html) / [Vulkan14Features](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceVulkan14Features.html)

- `synchronization_lifecycle.md` — Synchronization2 fallback 与 1.3+ 核心路径。
- `modern_patterns.md` — bindless / timeline semaphore / dynamic state 等 1.3+ 模式。
- `frame_lifecycle.md` — frames-in-flight 与 1.4 limit 提升后的资源管理。
- `../03_api_manual/05_descriptor/push_descriptor.md` — push descriptor API 细节。
- `../03_api_manual/07_rendering/dynamic_rendering.md` — dynamic rendering 与 local read API。

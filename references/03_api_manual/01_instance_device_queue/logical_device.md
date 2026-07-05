# API Card: VkDevice

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 |
| Vulkan 对象 | `VkDevice` |
| 常用 API | `vkCreateDevice` / `vkDestroyDevice` / `vkGetDeviceQueue` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkDevice` 是对 `VkPhysicalDevice` 的逻辑抽象，负责启用设备特性、扩展与队列族，是创建几乎所有 Vulkan 资源对象的入口。[SPEC]

---

## 2. 所属对象链路

```text
VkInstance
→ vkEnumeratePhysicalDevices
→ VkPhysicalDevice
→ vkGetPhysicalDeviceQueueFamilyProperties
→ VkDeviceQueueCreateInfo[]
→ VkDeviceCreateInfo（queue families / enabled features / extensions）
→ vkCreateDevice
→ VkDevice
→ vkGetDeviceQueue
→ VkQueue
```

### 上游依赖

- 已创建的 `VkInstance`。[SPEC]
- 已选择的 `VkPhysicalDevice`。[SPEC]
- 已确定需要的 queue family、features、extensions。

### 下游影响

- 决定可用的 device-level extensions（如 swapchain、dynamic rendering、descriptor indexing）。
- 决定 queue 数量与能力，影响并行渲染与计算策略。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDevice`
- `VkDeviceCreateInfo`
- `VkDeviceQueueCreateInfo`
- `VkPhysicalDeviceFeatures` / `VkPhysicalDeviceFeatures2`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateDevice` | 从 physical device 创建逻辑设备。[SPEC] |
| `vkDestroyDevice` | 销毁逻辑设备；会自动释放大部分子对象。[SPEC] |
| `vkGetDeviceQueue` / `vkGetDeviceQueue2` | 获取 device 创建的 queue。[SPEC] |
| `vkEnumerateDeviceExtensionProperties` | 查询物理设备支持的 device extensions。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- 常见 device extensions：`VK_KHR_swapchain`、`VK_KHR_dynamic_rendering`、`VK_EXT_descriptor_indexing`、`VK_KHR_synchronization2`。
- Vulkan 1.1+ 使用 `VkPhysicalDeviceFeatures2` 与 `pNext` 链启用扩展特性。

---

## 4. 标准使用流程

```text
vkEnumeratePhysicalDevices
→ 选择目标 physical device
→ vkGetPhysicalDeviceQueueFamilyProperties
→ 确定 graphics / compute / transfer / present queue family
→ 构造 VkDeviceQueueCreateInfo[]
→ 构造 VkPhysicalDeviceFeatures2（启用所需 features）
→ 构造 VkDeviceCreateInfo（extensions / features / queues）
→ vkCreateDevice
→ vkGetDeviceQueue 获取 queue handles
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `queueCreateInfoCount` / `pQueueCreateInfos` | 每个 queue family 的 queue 数量与优先级。[SPEC] | 同一 family 重复创建或优先级未归一化。[TOOL] |
| `pEnabledFeatures` / `pNext` 链上的 features | 必须显式启用才能使用，如 `samplerAnisotropy`。[SPEC] | 未启用 feature 就使用对应功能。[TOOL] |
| `ppEnabledExtensionNames` | device extensions，如 swapchain、dynamic rendering。[SPEC] | 漏开 `VK_KHR_swapchain`。[TOOL] |
| `pNext` | 可接 `VkPhysicalDeviceFeatures2`、feature structures。[SPEC] | 结构体类型链错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否查询了 physical device features 与 extensions？
- [ ] Queue family 是否能满足 graphics/compute/transfer/present 需求？
- [ ] 是否启用了所有后续需要的 features 与 extensions？
- [ ] `pEnabledFeatures` 与 `pNext` 链上的 feature 结构是否一致？

### 使用阶段

- [ ] 是否通过 `vkGetDeviceQueue` 获取了所需 queue？
- [ ] Queue family 索引是否与创建时一致？

### 销毁阶段

- [ ] 是否在销毁 device 前等待所有 queue 空闲？
- [ ] 是否在 instance 销毁前销毁 device？

---

## 7. 高频错误

1. 未启用 `VK_KHR_swapchain` 就创建 swapchain。[TOOL]
2. 使用 `samplerAnisotropy` 等 feature 但未在 `VkPhysicalDeviceFeatures` 中启用。[TOOL]
3. Queue family 不支持某种操作却向其提交对应命令。[TOOL]
4. `pEnabledFeatures` 与 `pNext` 链上的 feature 结构冲突或重复。[TOOL]
5. 销毁 device 时仍有 in-flight command buffer 或处于 recording 状态的 command buffer。[TOOL]
6. 同一 queue family 创建多个 `VkDeviceQueueCreateInfo` 导致失败。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDeviceCreateInfo-*`：queue family、features、extensions 合法性。
- `VUID-vkCreateDevice-ppEnabledExtensionNames-01387` 等。

### RenderDoc / AGI

- 捕获前确认 device extensions 与 features 已启用。

### 日志 / 代码检查

- 检查 `vkCreateDevice` 返回值。
- 检查启用的 device extensions 与 features 列表。
- 检查 queue family 索引与 queue 获取。

---

## 9. 生命周期风险

### 创建时机

- 应用启动时，在 instance 创建与 physical device 选择之后。[ENGINE]

### 使用时机

- 整个应用生命周期内用于创建几乎所有 Vulkan 对象（buffer、image、pipeline、swapchain 等）。[SPEC]

### 销毁时机

- 应用退出时，在所有 device-level 对象销毁之后、instance 销毁之前。[SPEC]

### in-flight 风险

- Device 销毁后所有派生对象失效；销毁前需等待所有 queue 完成。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkDestroyDevice` 会隐式等待所有 queue 完成；但显式 `vkDeviceWaitIdle` 更安全。[SPEC]

### GPU-GPU 同步

- Device 本身不提供同步；同步通过 queue submit 中的 semaphore/fence 实现。[SPEC]

### 资源访问同步

- 无。

---

## 11. Android 注意点

- Android 上常见需要启用的 device extensions：`VK_KHR_swapchain`、`VK_KHR_android_surface`（instance）、`VK_KHR_dynamic_rendering`（如使用）。[ANDROID]
- 不同 GPU（Adreno/Mali/PowerVR）的 queue family 布局不同，需运行时查询，不要假设 graphics/compute/transfer 完全分离或完全重合。[ANDROID]
- 部分移动端 feature（如 `shaderStorageImageReadWithoutFormat`、`samplerAnisotropy`）支持度不一，需查询并 fallback。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Device 创建是一次性开销，但启用过多不必要的 features/extensions 可能增加初始化时间。[ENGINE]

### GPU 侧

- Queue family 选择影响任务调度；合理使用 graphics/compute/transfer queue 可提升并行度。[ENGINE]

### 移动端

- 避免创建过多 queue；通常 1 个 graphics + 1 个 compute/transfer 足够。[ANDROID]
- 不要启用项目不需要的 features，避免驱动走未优化路径。[ANDROID]

---

## 13. 专家经验

**经验**：
创建 device 前一定要做好 feature/extension 清单：列出项目必需项、可选项、不支持时的 fallback。对移动端，优先查询 `shaderStorageImageReadWithoutFormat`、`samplerAnisotropy`、`fullDrawIndexUint32`、`textureCompressionASTC/ETC2` 等关键特性。Queue family 选择不要硬编码索引，而是根据 `queueFlags` 和 surface present 支持动态选择。

**适用条件**：
所有 Vulkan 应用。

**不适用情况**：
无。

**来源**：`[ENGINE][ANDROID][SPEC]`

---

## 14. 相关 API 卡片

- `instance.md`
- `../03_command_buffer/queue_submit.md`
- `../03_command_buffer/command_buffer.md`
- `../02_surface_swapchain/swapchain.md`
- `../10_android_platform/android_surface.md`

---

## 15. 需要回查官方文档的情况

1. 目标物理设备对核心版本、extensions、features 的支持矩阵。
2. `VkPhysicalDeviceFeatures2` 与 `pNext` 链上各 feature 结构的启用规则。
3. Queue family 的 `queueFlags` 与 present 支持查询。
4. Device extension 之间的依赖关系。
5. 不同 GPU 厂商对同一 feature 的语义差异。

# API Card: VkInstance

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 |
| Vulkan 对象 | `VkInstance` |
| 常用 API | `vkCreateInstance` / `vkDestroyInstance` / `vkEnumerateInstanceExtensionProperties` / `vkEnumerateInstanceLayerProperties` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkInstance` 是 Vulkan 的运行时入口，承载应用信息、启用的 instance layers 与 extensions，并用于枚举物理设备。[SPEC]

---

## 2. 所属对象链路

```text
VkApplicationInfo（app name / engine name / apiVersion）
→ VkInstanceCreateInfo（layers / extensions / debug messenger）
→ vkCreateInstance
→ VkInstance
→ vkEnumeratePhysicalDevices
→ VkPhysicalDevice
```

### 上游依赖

- 已加载 Vulkan loader（如 `vulkan-1.dll` / `libvulkan.so`）。[SPEC]
- 明确需要的 instance layers（如 validation）与 extensions（如 surface）。

### 下游影响

- 决定哪些 instance-level 扩展可用，例如 `VK_KHR_surface`、`VK_EXT_debug_utils`。
- 决定 validation layer 等行为。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkInstance`
- `VkInstanceCreateInfo`
- `VkApplicationInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateInstance` | 创建 Vulkan instance。[SPEC] |
| `vkDestroyInstance` | 销毁 instance；需先销毁所有子对象。[SPEC] |
| `vkEnumerateInstanceExtensionProperties` | 查询 loader 支持的 instance extensions。[SPEC] |
| `vkEnumerateInstanceLayerProperties` | 查询可用的 instance layers。[SPEC] |
| `vkEnumeratePhysicalDevices` | 通过 instance 枚举物理设备。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- 常见 instance extensions：`VK_KHR_surface`、`VK_KHR_android_surface`、`VK_EXT_debug_utils`。
- 常见 instance layers：`VK_LAYER_KHRONOS_validation`。

---

## 4. 标准使用流程

```text
加载 Vulkan loader / 获取 vkGetInstanceProcAddr
→ 查询支持的 instance extensions 与 layers
→ 构造 VkApplicationInfo（apiVersion 建议目标版本，如 1.1/1.2/1.3）
→ 构造 VkInstanceCreateInfo（启用所需 extensions / layers）
→ vkCreateInstance
→ 获取 instance-level function pointers
→ vkEnumeratePhysicalDevices
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `pApplicationInfo->apiVersion` | 应用请求的 Vulkan API 版本；物理设备可能不高于此版本。[SPEC] | 设为 1.3 但设备只支持 1.1。[TOOL] |
| `ppEnabledExtensionNames` | 必须包含后续需要的 instance extensions，如 surface。[SPEC] | 漏开 `VK_KHR_surface` 导致无法创建 surface。[TOOL] |
| `ppEnabledLayerNames` | Validation layer 等；release 版本通常关闭。[SPEC] | 发布包仍开启 validation。[ENGINE] |
| `pNext` | 可接 `VkDebugUtilsMessengerCreateInfoEXT` 等。[SPEC] | 结构体类型链错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否先查询了 extensions / layers 可用性？
- [ ] `apiVersion` 是否与项目目标版本一致？
- [ ] 是否启用了 surface、debug utils 等必要 extension？
- [ ] Debug messenger 是否通过 `pNext` 在创建时启用？

### 使用阶段

- [ ] 是否通过 instance 获取了所有 instance-level function pointers？
- [ ] 是否枚举并选择了合适的 physical device？

### 销毁阶段

- [ ] 是否在所有 device、surface、debug messenger 销毁后再销毁 instance？
- [ ] 销毁顺序是否遵循“子对象先销毁”原则？

---

## 7. 高频错误

1. `apiVersion` 设置过高导致旧设备无法运行。[TOOL]
2. 漏开 `VK_KHR_surface` 或平台相关的 surface extension。[TOOL]
3. 启用未安装的 validation layer，创建 instance 失败。[TOOL]
4. 在 release 版本中未移除 validation layer。[ENGINE]
5. 销毁 instance 前未销毁 debug messenger 或 surface。[TOOL]
6. 未查询扩展可用性就直接启用。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkInstanceCreateInfo-*`：layer/extension 名称、apiVersion 合法性。
- `VUID-vkCreateInstance-ppEnabledLayerNames-01377` 等。

### RenderDoc / AGI

- 捕获前需确认 instance extensions 已启用所需功能。

### 日志 / 代码检查

- 检查 `vkCreateInstance` 返回值。
- 检查启用的 layers/extensions 列表。
- 检查销毁顺序。

---

## 9. 生命周期风险

### 创建时机

- 应用启动时最早创建，通常在窗口系统初始化之后、物理设备选择之前。[ENGINE]

### 使用时机

- 整个应用生命周期内用于枚举物理设备、创建 surface、管理 debug messenger。[SPEC]

### 销毁时机

- 应用退出时，最后销毁；需确保所有子对象已销毁。[SPEC]

### in-flight 风险

- Instance 销毁后所有派生对象都失效；不要在 GPU 仍在执行时销毁 instance。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Instance 创建/销毁本身不涉及 GPU 同步；但销毁前需等待所有 device 空闲。[SPEC]

### GPU-GPU 同步

- 无。

### 资源访问同步

- 无。

---

## 11. Android 注意点

- Android 上必须启用 `VK_KHR_android_surface` 才能创建 Android surface。[ANDROID]
- 不同 Android 设备支持的 Vulkan 版本差异大，建议 `apiVersion` 按项目最低目标设置，而不是设备最高支持。[ANDROID]
- Release 版本务必关闭 validation layer，避免性能开销与额外依赖。[ANDROID][ENGINE]
- 部分 OEM 设备对 instance extensions 支持有差异，建议运行时查询并 fallback。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Instance 创建是一次性开销，通常不是瓶颈。[ENGINE]
- Validation layer 会显著增加 CPU 开销，release 版本应关闭。[ENGINE]

### GPU 侧

- Instance 本身不产生 GPU 开销。[ENGINE]

### 移动端

- 启动时尽量减少不必要的 layer/extension 启用。[ANDROID]
- 不要依赖 validation layer 做运行时错误处理。[ANDROID]

---

## 13. 专家经验

**经验**：
把 `VkInstance` 当作“Vulkan 运行时的根证书”。创建时只启用真正需要的 layers 和 extensions，查询可用性后再启用，避免硬编码。`apiVersion` 建议设置为项目计划使用的最低核心版本（例如 1.1），然后通过 `vkEnumerateInstanceVersion` 确认 loader 是否支持；设备能力再通过 physical device properties 查询。Debug 版本通过 `pNext` 接 debug messenger，release 版本彻底移除 validation layer。

**适用条件**：
所有 Vulkan 应用。

**不适用情况**：
无。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `logical_device.md`
- `../10_android_platform/android_surface.md`
- `../02_surface_swapchain/surface.md`
- `../09_debug_validation/debug_utils.md`
- `../09_debug_validation/validation_layer.md`

---

## 15. 需要回查官方文档的情况

1. 目标平台 loader 对 Vulkan 版本与 extensions 的支持矩阵。
2. Instance layer 与 extension 的启用顺序与依赖关系。
3. Debug messenger 在 `vkCreateInstance` 时通过 `pNext` 启用的规则。
4. `apiVersion` 与 physical device 版本的关系。
5. 不同 Android 版本与 OEM 对 instance extensions 的差异。

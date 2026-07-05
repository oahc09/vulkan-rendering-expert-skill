# API Card: Validation Layer

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 调试链 |
| Vulkan 对象 | `VkLayerProperties` / `VkDebugUtilsMessengerEXT` / `VkDebugReportCallbackEXT` |
| 常用 API | `vkEnumerateInstanceLayerProperties` / `vkCreateInstance` / `vkCreateDebugUtilsMessengerEXT` / `vkDestroyDebugUtilsMessengerEXT` / `vkCreateDebugReportCallbackEXT` / `vkDestroyDebugReportCallbackEXT` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ANDROID] [GUIDE] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 / 扩展 |

---

## 1. 一句话定位

Validation Layer 是 Vulkan 生态的核心调试基础设施，它在应用调用处或驱动前端拦截 API 调用，检查参数、状态、同步与生命周期合法性，并以 VUID 编码的错误/警告信息输出。[SPEC]

---

## 2. 所属对象链路

```text
VkInstance（启用 layer + extension）
→ VkPhysicalDevice（可选 device layer）
→ VkDevice（启用 device-layer 或继承 instance layer）
→ Command Buffer / Queue Submit
→ Validation Layer 拦截与检查
→ Debug Messenger / Debug Report 回调输出
```

### 上游依赖

- Instance layer 名称列表（如 `VK_LAYER_KHRONOS_validation`）。[SPEC]
- Debug extension 可用性（`VK_EXT_debug_utils` 或 `VK_EXT_debug_report`）。[SPEC]
- `VkInstanceCreateInfo.ppEnabledLayerNames` 在创建时正确填入。[SPEC]

### 下游影响

- 应用日志/回调输出内容决定排错方向。[TOOL]
- Release build 是否移除/禁用影响性能与信息安全。[ENGINE]
- 最佳实践层输出可指导性能优化。[GUIDE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkLayerProperties`
- `VkDebugUtilsMessengerEXT`
- `VkDebugReportCallbackEXT`
- `VkDebugUtilsMessengerCreateInfoEXT`
- `VkDebugReportCallbackCreateInfoEXT`
- `VkDebugUtilsMessageSeverityFlagBitsEXT`
- `VkDebugUtilsMessageTypeFlagBitsEXT`

### 常用 API

| API | 作用 |
|---|---|
| `vkEnumerateInstanceLayerProperties` | 列出 instance 可用 layer。[SPEC] |
| `vkEnumerateDeviceLayerProperties` | 列出 device 可用 layer；现代项目通常依赖 instance layer，device layer 已较少单独使用。[SPEC] |
| `vkCreateInstance` | 启用 layer 与 debug extension。[SPEC] |
| `vkCreateDebugUtilsMessengerEXT` | 创建 debug utils messenger。[SPEC] |
| `vkDestroyDebugUtilsMessengerEXT` | 销毁 messenger。[SPEC] |
| `vkCreateDebugReportCallbackEXT` | 旧版 debug report 回调。[SPEC] |
| `vkDestroyDebugReportCallbackEXT` | 销毁 debug report callback。[SPEC] |

### 相关扩展 / 版本

- `VK_LAYER_KHRONOS_validation`：Khronos 官方验证层，推荐优先使用。[GUIDE]
- `VK_EXT_debug_utils`：现代调试消息扩展，支持 severity/type/对象名/标签。[SPEC]
- `VK_EXT_debug_report`：旧版调试消息扩展，新项目不建议使用。[SPEC]
- Android 是否可用：是，需关注 logcat 与 AGI。[ANDROID]

---

## 4. 标准使用流程

```text
编译期/启动期选择 layer 名称（VK_LAYER_KHRONOS_validation）
→ vkEnumerateInstanceLayerProperties 确认可用
→ 填充 VkInstanceCreateInfo.ppEnabledLayerNames
→ 填充 VK_EXT_debug_utils 到 ppEnabledExtensionNames
→ vkCreateInstance
→ 填充 VkDebugUtilsMessengerCreateInfoEXT（severity / type / pfnCallback / pUserData）
→ vkCreateDebugUtilsMessengerEXT
→ 应用运行期间自动输出 validation message
→ 销毁 instance 前 vkDestroyDebugUtilsMessengerEXT
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkLayerProperties.layerName` | 精确匹配字符串，大小写敏感。[SPEC] | 拼写错误导致 layer 未加载而完全静默。[TOOL] |
| `VkLayerProperties.implementationVersion` | 版本是否满足需求；新版 layer 覆盖更多 VUID。[SPEC] | 旧版 layer 漏检新引入的 VUID。[TOOL] |
| `VkDebugUtilsMessengerCreateInfoEXT.messageSeverity` | 选择 `VERBOSE` / `INFO` / `WARNING` / `ERROR`。[SPEC] | 线上误开 `VERBOSE` 导致日志洪水。[ENGINE] |
| `VkDebugUtilsMessengerCreateInfoEXT.messageType` | 选择 `GENERAL` / `VALIDATION` / `PERFORMANCE` / `DEVICE_ADDRESS_BINDING`。[SPEC] | 未启用 `PERFORMANCE` 漏掉最佳实践警告。[TOOL] |
| `pfnUserCallback` | 回调函数签名与 `pUserData`。[SPEC] | 回调内调用 Vulkan API 引发重入或死锁。[TOOL] |
| `VkDebugReportCallbackCreateInfoEXT.flags` | 旧版的 message flags 组合。[SPEC] | 用旧 API 时 severity/type 映射混乱。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否在 `vkCreateInstance` 前枚举了可用 layer？
- [ ] `ppEnabledLayerNames` 中的名称拼写是否完全正确？
- [ ] 是否同时启用了 `VK_EXT_debug_utils` instance extension？
- [ ] messenger create info 的 severity/type 是否符合当前调试需求？
- [ ] 回调函数是否线程安全？是否在回调内避免 Vulkan API 调用？

### 使用阶段

- [ ] 是否处理了所有 `ERROR` severity？
- [ ] 是否对已知误报设置过滤或 `break on validation` 策略？
- [ ] 是否区分了 instance layer 与 device layer 的启用场景？

### 销毁阶段

- [ ] 是否在 `vkDestroyInstance` 之前销毁 messenger？
- [ ] `pUserData` 与回调指针的生命周期是否长于 messenger？[SPEC]

---

## 7. 高频错误

1. Layer 名称拼写错误导致完全静默。[TOOL]
2. 只在 device extension 中启用 `VK_EXT_debug_utils`，却忘记在 instance extension 中启用。[TOOL]
3. messenger 创建在 `vkCreateInstance` 之后，导致 instance 创建阶段的验证信息丢失。[TOOL]
4. 回调函数内调用 `vkDestroyDebugUtilsMessengerEXT` 或其他 Vulkan API，造成重入或崩溃。[TOOL]
5. 未过滤 `VERBOSE`/`INFO`，导致日志淹没真正错误。[ENGINE]
6. Release 包未移除 validation layer，造成性能下降与信息泄露。[ENGINE]
7. 忽略 `PERFORMANCE` 或最佳实践层信息，错过潜在优化点。[GUIDE]
8. Android 上未正确过滤 logcat 标签，导致无法快速定位 VUID。[ANDROID]

---

## 8. Debug 检查路径

### Validation Layer

- 观察 VUID 编码与 `pMessageIdName`。[SPEC]
- 观察 object handle / object type，定位具体资源。[TOOL]
- 观察 command buffer state 与 labels，定位发生场景。[TOOL]
- 观察 message severity 与 type，决定处理优先级。[TOOL]

### RenderDoc / AGI

- RenderDoc：验证层消息通常与 capture 一起记录；结合 Events / Texture / Pipeline 状态交叉验证。[TOOL]
- AGI（Android GPU Inspector）：在 Android 上捕获 frame，查看 validation 输出与 GPU 状态。[TOOL]
- 工具捕获无法替代 validation layer 的前端参数检查。[HEUR]

### 日志 / 代码检查

- Android：`adb logcat -s DEBUG` 或按自定义 tag 过滤。[ANDROID]
- 检查 `vkCreateInstance` 的 enabled layers/extensions。
- 检查回调函数实现是否线程安全。
- 检查 Release 配置是否彻底移除 layer。

---

## 9. 生命周期风险

### 创建时机

- Instance 创建时启用 layer。[SPEC]
- Messenger 通常在 instance 创建后立即创建；若要捕获 instance 创建本身的信息，需将 `VkDebugUtilsMessengerCreateInfoEXT` 作为 `pNext` 链入 `VkInstanceCreateInfo`，并注意 `vkGetInstanceProcAddr` 获取函数指针的时机。[GUIDE]

### 使用时机

- 整个应用运行期间持续生效。

### 销毁时机

- 在 `vkDestroyInstance` 之前销毁 messenger。[SPEC]
- callback 与 `pUserData` 生命周期需覆盖 messenger 生命周期。[SPEC]

### in-flight 风险

- 无 GPU in-flight 问题，但回调可能在多线程被并发调用，需保证回调内部线程安全。[TOOL]

---

## 10. 同步风险

### CPU-GPU 同步

- 回调运行在 CPU，不直接涉及 GPU 同步。[SPEC]
- 回调可能打断应用线程，需注意锁的使用，避免在持有锁时调用可能阻塞的操作。[ENGINE]

### GPU-GPU 同步

- 不涉及。

### 资源访问同步

- 回调中访问 `pUserData` 需线程安全。
- 不要在回调内部调用 Vulkan API，尤其是可能触发 validation 的 API，避免重入。[TOOL]

---

## 11. Android 注意点

- Android Studio / Gradle 中需将 validation layer 库打包到 APK 的 `lib/` 下或从系统加载。[ANDROID]
- 使用 AGI 时可直接启用系统验证层，无需手动打包。[TOOL]
- logcat 中 Khronos validation 消息通常带有 tag，可用 `adb logcat -s "Validation"` 或自定义 tag 过滤。[ANDROID]
- 部分 OEM 设备可能剥离或替换验证层，行为可能与桌面不同。[ANDROID]
- 横竖屏切换 / surface recreate 不会直接影响 validation layer，但可能暴露新的 swapchain 相关 VUID。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Validation layer 会显著增加 CPU 开销，尤其是 draw call 密集场景；Release build 应完全禁用。[ENGINE]
- Best Practices 层额外检查性能反模式，开销更大。[GUIDE]
- 每帧产生的大量 validation message 会通过回调/日志 I/O 进一步拖慢帧率。[ENGINE]

### GPU 侧

- 验证层主要影响 CPU，但对 GPU 时间线也有少量同步检查开销。[HEUR]

### 移动端

- 移动端 CPU 预算紧张，验证层可能导致帧率大幅下降；仅在调试/剖析阶段开启。[ENGINE]
- logcat 缓冲区有限，高频 message 可能滚动丢失；建议在回调内写文件。[ANDROID]

---

## 13. 专家经验

**经验**：
优先使用 `VK_LAYER_KHRONOS_validation` 单一 layer，而不是过时的 `VK_LAYER_LUNARG_standard_validation` 组合；使用 `VK_EXT_debug_utils` 替代 `VK_EXT_debug_report`。在回调中只做日志/断点/统计，不做 Vulkan API 调用；为不同构建类型配置 severity mask：DEBUG 全开，PROFILE 仅 `WARNING`/`ERROR`，RELEASE 彻底关闭。

**适用条件**：
需要定位 API 误用、同步错误、生命周期错误的开发调试阶段。

**不适用情况**：
性能测试、Release 包、线上 Telemetry；这些场景应使用自定义统计或后置分析，而非 validation layer。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `debug_utils.md`
- `vuid_decode.md`
- `../03_command_buffer/command_buffer.md`
- `../03_command_buffer/queue_submit.md`
- `../02_surface_swapchain/swapchain_recreate.md`

---

## 15. 需要回查官方文档的情况

1. 具体 VUID 的精确含义与触发条件。
2. 不同验证层实现（LunarG、OEM）的行为差异。
3. `VkDebugUtilsMessengerCreateInfoEXT` 与 `VkInstanceCreateInfo` `pNext` 链的组合规则。
4. `VK_EXT_debug_report` 到 `VK_EXT_debug_utils` 的 message flag 映射。
5. Android 系统验证层加载路径与 AGI 的交互细节。
6. Best Practices layer 的最新启用方式与过滤规则。

# Workflow: Setup Instance Device Queue

## 0. 适用范围

### 适用

- 从头创建 Vulkan renderer，需要初始化 instance、physical device、logical device、queue。
- 迁移现有 renderer 的 device/queue 创建逻辑，或替换为显式控制扩展 / layer / feature 的版本。
- 需要自定义 physical device 选择策略、queue family 分配、异步 compute / transfer queue 配置。

### 不适用

- 使用已有引擎或渲染框架封装好的 context（如 Unreal/Unity），无需手动创建 device。
- 只需要创建 command buffer 或 shader module，而不涉及 instance/device 层级。
- 目标平台没有 Vulkan loader（如纯 OpenGL ES 应用）。

---

## 1. 任务目标

建立 Vulkan 渲染器的基础上下文：

```text
Vulkan Loader
→ VkInstance（extensions + layers + application info）
→ VkPhysicalDevice（枚举 + 选择）
→ Queue Family（graphics / compute / transfer / present）
→ VkDevice（extensions + features + queue create infos）
→ VkQueue（vkGetDeviceQueue）
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux / 其他。
- Vulkan 版本目标：1.0 / 1.1 / 1.2 / 1.3。
- 必须启用的 instance extensions（如 `VK_KHR_surface`、`VK_EXT_debug_utils`）。
- 必须启用的 device extensions（如 `VK_KHR_swapchain`、`VK_KHR_dynamic_rendering`）。
- 必须启用的 validation layers（如 `VK_LAYER_KHRONOS_validation`）。
- 必须启用的 physical device features（如 `samplerAnisotropy`、`fillModeNonSolid`、`dynamicRendering`）。
- 是否需要独立 compute / transfer queue。
- surface 是否已创建（影响 present queue 选择）。
- 目标设备限制：`maxImageDimension2D`、`maxSamplerAllocationCount`、`timestampPeriod` 等。

---

## 3. 前置检查

- [ ] 系统已安装 Vulkan Loader；`vkEnumerateInstanceVersion` / `vkCreateInstance` 可用 [SPEC]。
- [ ] 目标 instance extension 在 `vkEnumerateInstanceExtensionProperties` 返回列表中 [SPEC]。
- [ ] 目标 validation layer 在 `vkEnumerateInstanceLayerProperties` 返回列表中 [TOOL]。
- [ ] 至少存在一个支持 Vulkan 的 physical device [SPEC]。
- [ ] 目标 device extension 在 `vkEnumerateDeviceExtensionProperties` 返回列表中 [SPEC]。
- [ ] 目标 feature 在 `VkPhysicalDeviceFeatures` / `VkPhysicalDeviceFeatures2` 中受支持 [SPEC]。
- [ ] 已确认 graphics queue family index 与 surface present queue family index [SPEC]。
- [ ] RenderDoc / AGI 可 attach 到即将创建的 instance [TOOL]。

---

## 4. Vulkan 对象链路

```text
Application
→ VkInstanceCreateInfo
    → pApplicationInfo（apiVersion、pEngineName）
    → ppEnabledExtensionNames（surface / debug_utils 等）
    → ppEnabledLayerNames（validation layer 等）
    → pNext 链（debug messenger create info / validation features）
→ vkCreateInstance
→ vkEnumeratePhysicalDevices
→ VkPhysicalDevice
    → vkGetPhysicalDeviceProperties / Features / MemoryProperties
    → vkEnumerateDeviceExtensionProperties
    → vkGetPhysicalDeviceQueueFamilyProperties
    → vkGetPhysicalDeviceSurfaceSupportKHR（如存在 surface）
→ VkDeviceQueueCreateInfo（queue family index + queue count + priorities）
→ VkDeviceCreateInfo
    → ppEnabledExtensionNames
    → pEnabledFeatures 或 pNext 链 VkPhysicalDeviceFeatures2
→ vkCreateDevice
→ vkGetDeviceQueue
```

---

## 5. 资源设计

| 资源 | 类型 | Usage / 作用 | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| instance | `VkInstance` | Vulkan 上下文入口 | 应用生命周期 | 否 |
| physical device | `VkPhysicalDevice` | 查询能力与选择 | 跟随 instance | 否 |
| logical device | `VkDevice` | 创建资源、提交命令 | 应用生命周期 | 否 |
| graphics queue | `VkQueue` | 图形命令提交 | 跟随 device | 否 |
| present queue | `VkQueue` | present 命令提交 | 跟随 device | 否 |
| compute queue | `VkQueue` | 异步 compute | 跟随 device | 否（可选） |
| transfer queue | `VkQueue` | 异步 upload/copy | 跟随 device | 否（可选） |
| debug messenger | `VkDebugUtilsMessengerEXT` | 输出 validation message | instance 生命周期 | 否（可选） |

---

## 6. Pipeline / Descriptor 设计

本 workflow 不直接创建 graphics/compute pipeline，但需要为后续 pipeline 创建奠定以下基础：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | `VkPhysicalDeviceFeatures.samplerAnisotropy` | 启用后允许各向异性采样 | Fragment / Compute |
| 无 | `VkPhysicalDeviceFeatures.fillModeNonSolid` | 启用后允许 wireframe / point 模式 | Vertex / Fragment |
| 无 | `VkPhysicalDeviceDynamicRenderingFeatures.dynamicRendering` | 启用后支持 dynamic rendering | Graphics |

设计说明：

- `pEnabledFeatures` 与 `pNext` 链 `VkPhysicalDeviceFeatures2` 二选一；Vulkan 1.1+ 推荐后者，以便链接 `VkPhysicalDeviceFeatures2` → `VkPhysicalDeviceVulkan11Features` → `VkPhysicalDeviceVulkan12Features` → `VkPhysicalDeviceVulkan13Features` 等 [SPEC]。
- 移动端若不需要某些 feature，保持关闭以减少 driver 编译路径分歧 [ANDROID]。
- `robustBufferAccess` 在调试时打开，发布时关闭 [GUIDE]。

---

## 7. 同步与 Layout 设计

本 workflow 不直接操作 image layout，但需要规划 queue family ownership：

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| graphics queue submit | buffer / image | `queueFamilyIndex` 为 graphics family | graphics queue |
| compute queue submit | buffer / image | 跨 queue family 时需要 `QUEUE_FAMILY_OWNERSHIP_TRANSFER` [SPEC] | compute queue |
| transfer queue submit | staging buffer | 跨 queue family 时需要 ownership release/acquire [SPEC] | graphics queue |

必须说明：

- 若 graphics 与 present 使用同一 queue family，则无需 queue family ownership transfer [SPEC]。
- 若 compute / transfer queue 为独立 queue family，资源在 queue 之间切换时必须显式 barrier [SPEC]。
- swapchain image 由 present engine 产生，首次写入前通常视为 `VK_IMAGE_LAYOUT_UNDEFINED` 或按 `VkRenderPass` loadOp 处理 [SPEC]。

---

## 8. 实现步骤

1. **加载 Vulkan Loader**：
   - Windows：`vkGetInstanceProcAddr` 通过 `vulkan-1.dll` 获取。
   - Android：通过 `vulkan_wrapper.h` / `dlopen libvulkan.so` 加载 [ANDROID]。
   - Linux：通过 `libvulkan.so.1` 加载。
2. **查询 instance 版本**：调用 `vkEnumerateInstanceVersion` 确认运行时 Vulkan 版本 [SPEC]。
3. **组装 instance extensions**：
   - 调用 `vkEnumerateInstanceExtensionProperties` 获取可用列表 [SPEC]。
   - 必须包含 `VK_KHR_surface`（如需要窗口）和平台相关 surface extension（`VK_KHR_win32_surface`、`VK_KHR_android_surface` 等） [SPEC]。
   - 调试时加入 `VK_EXT_debug_utils` [TOOL]。
4. **组装 instance layers**：
   - 调用 `vkEnumerateInstanceLayerProperties` 获取可用列表 [SPEC]。
   - 调试时加入 `VK_LAYER_KHRONOS_validation` 或 `VK_LAYER_LUNARG_standard_validation`（旧版） [TOOL]。
5. **创建 instance**：填写 `VkInstanceCreateInfo`，调用 `vkCreateInstance`；若启用 debug utils，将 `VkDebugUtilsMessengerCreateInfoEXT` 挂入 `pNext` 以捕获创建/销毁阶段消息 [SPEC]。
6. **枚举 physical device**：调用 `vkEnumeratePhysicalDevices` 获取所有 `VkPhysicalDevice` [SPEC]。
7. **选择 physical device**：
   - 调用 `vkGetPhysicalDeviceProperties` 查看 device type、driver version、API version [SPEC]。
   - 调用 `vkGetPhysicalDeviceFeatures` / `vkGetPhysicalDeviceFeatures2` 检查必需 feature [SPEC]。
   - 调用 `vkEnumerateDeviceExtensionProperties` 检查必需 extension [SPEC]。
   - 调用 `vkGetPhysicalDeviceMemoryProperties` 确认 device-local / host-visible 内存类型 [SPEC]。
   - 移动端优先选择 `VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU` 或按性能/功耗策略选择 [ANDROID]。
8. **查询 queue family**：
   - 调用 `vkGetPhysicalDeviceQueueFamilyProperties` 获取所有 queue family [SPEC]。
   - 选择至少包含 `VK_QUEUE_GRAPHICS_BIT` 的 family 作为 graphics family。
   - 若需要 present，调用 `vkGetPhysicalDeviceSurfaceSupportKHR` 确认该 family 支持 surface [SPEC]。
   - 可选选择独立 compute / transfer family：包含 `VK_QUEUE_COMPUTE_BIT` / `VK_QUEUE_TRANSFER_BIT` 但不包含 `GRAPHICS_BIT` [HEUR]。
9. **创建 logical device**：
   - 填写 `VkDeviceQueueCreateInfo`：每个 queue family 一个；指定 queue count 与 priorities [SPEC]。
   - 填写 `VkDeviceCreateInfo`：启用 device extensions（如 `VK_KHR_swapchain`）与 features [SPEC]。
   - 调用 `vkCreateDevice`。
10. **获取 queue handles**：调用 `vkGetDeviceQueue` 获取每个 queue family 的 `VkQueue` [SPEC]。
11. **对象命名（可选）**：使用 `vkSetDebugUtilsObjectNameEXT` 为 instance / device / queue 命名，便于 RenderDoc / AGI 识别 [TOOL]。
12. **接入销毁路径**：按 `device → debug messenger → instance` 顺序销毁；`vkDestroyDebugUtilsMessengerEXT` 必须在 `vkDestroyInstance` 前调用 [SPEC]。

---

## 9. Android 注意点

- 必须在 `ANativeWindow` 可用后创建 `VkSurfaceKHR`，但 instance / device 可在 surface 之前创建；device extension `VK_KHR_swapchain` 只需在 device 创建时启用 [ANDROID]。
- Android 上 instance 创建通常需要 `VK_KHR_android_surface`；不要在 `ANativeWindow` 销毁后继续使用其关联的 `VkSurfaceKHR` [ANDROID]。
- 部分 Android 设备只提供一个 queue family（graphics + compute + transfer 合一），此时所有 queue 来自同一 family，无需 queue family ownership transfer [ANDROID]。
- `vkEnumerateInstanceExtensionProperties` 在 Android 上可能不列出某些桌面扩展；务必检查返回值而非假设支持 [ANDROID]。
- 应用 `onPause` / `onResume` 时不应销毁 device，只需暂停 submit / present；device 重建成本高 [ANDROID]。
- rotation / resize 只影响 swapchain，不影响 instance / device / queue [ANDROID]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkInstanceCreateInfo-*`、`VUID-VkDeviceCreateInfo-*`、`VUID-vkCreateDevice-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI 能识别 instance、device、queue，并正确 attach 到应用 [TOOL]。
- [ ] `vkEnumeratePhysicalDevices` 返回目标 GPU，且选择逻辑符合预期。
- [ ] `vkGetDeviceQueue` 返回有效 queue handle，graphics / present / compute / transfer index 与预期一致。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出 instance version、physical device name、queue family index。
- [ ] 性能指标：
  - instance / device 创建耗时在可接受范围（通常 < 200 ms，具体视平台和 driver 而定）；
  - 无重复创建 device 或泄露 instance [TOOL]。
- [ ] 多帧运行稳定，无 `VK_ERROR_DEVICE_LOST`。
- [ ] 销毁路径无 validation error 或 crash。

---

## 11. 常见失败模式

1. **Instance extension 不存在**：假设 `VK_EXT_debug_utils` 一定可用，导致 `vkCreateInstance` 失败 [TOOL]。
2. **Layer 名称拼写错误**：`VK_LAYER_KHRONOS_validation` 拼写错误导致 layer 未启用 [TOOL]。
3. **Device extension 未启用**：未启用 `VK_KHR_swapchain` 却在后续创建 swapchain，产生 `VUID-vkCreateSwapchainKHR-*` 错误 [SPEC]。
4. **Feature 未检查**：直接启用 `samplerAnisotropy` 但 physical device 不支持，device 创建失败 [SPEC]。
5. **Queue family 不支持 present**：未调用 `vkGetPhysicalDeviceSurfaceSupportKHR` 确认，导致 present 失败 [SPEC]。
6. **Queue priority 越界**：`queuePriorities` 元素不在 `[0.0, 1.0]` 范围内，device 创建失败 [SPEC]。
7. **ApiVersion 设置过高**：`VkApplicationInfo.apiVersion` 大于 loader 支持的版本，instance 创建失败 [SPEC]。
8. **Android surface extension 缺失**：未启用 `VK_KHR_android_surface` 就创建 Android surface [ANDROID]。
9. **pNext 链顺序错误**：多个 feature struct 链接顺序不符合 Vulkan 规范，validation 报错 [SPEC]。
10. **Device 销毁前未等待 idle**：销毁 device 时仍有 in-flight command buffer，可能导致 crash 或 DEVICE_LOST [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/09_debug_validation/debug_utils.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan Loader 版本。
- `vkEnumerateInstanceExtensionProperties` / `vkEnumerateInstanceLayerProperties` 输出。
- `vkEnumeratePhysicalDevices` 列表与选择逻辑。
- `VkPhysicalDeviceProperties`、`VkPhysicalDeviceFeatures` 输出。
- `vkGetPhysicalDeviceQueueFamilyProperties` 返回的 family 与 flags。
- `vkCreateInstance` / `vkCreateDevice` 返回值与 validation message。
- Android lifecycle 日志（`APP_CMD_INIT_WINDOW` / `APP_CMD_TERM_WINDOW`）。

---

## 15. 需要回查官方文档的情况

1. 不同平台 `vkEnumerateInstanceVersion` 返回的版本语义与 Loader 行为差异。
2. `VkPhysicalDeviceFeatures2` pNext 链中各 feature struct 的启用顺序与兼容性。
3. 多 GPU / device group 场景下的 physical device 选择策略。
4. 独立 transfer queue family 与 graphics queue family 之间的 ownership transfer 精确规则。
5. Android 特定设备对 `VK_KHR_swapchain` 与 surface extension 的支持差异。

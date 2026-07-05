# API Card: VkSurfaceKHR

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 显示链 / Android 平台链 |
| Vulkan 对象 | `VkSurfaceKHR` |
| 常用 API | `vkCreateAndroidSurfaceKHR` / `vkCreateWin32SurfaceKHR` / `vkCreateXlibSurfaceKHR` / `vkDestroySurfaceKHR` / `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` / `vkGetPhysicalDeviceSurfaceFormatsKHR` / `vkGetPhysicalDeviceSurfacePresentModesKHR` |
| 适用平台 | 通用，平台相关创建函数不同 |
| 来源等级 | `[SPEC] [ANDROID] [TOOL]` |
| 适用 Vulkan 版本 | Vulkan 1.0 + `VK_KHR_surface` + 平台 surface extension |

---

## 1. 一句话定位

`VkSurfaceKHR` 是 Vulkan 与平台窗口系统之间的桥梁，定义了“可以呈现图像的目标表面”；它的能力直接决定 swapchain 的 format、extent、present mode 等参数。[SPEC]

---

## 2. 所属对象链路

```text
Platform Window / ANativeWindow / HWND
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images
→ VkImageView
→ Present Engine
```

### 上游依赖

- 平台窗口句柄：Android 的 `ANativeWindow`，Windows 的 `HWND` / `HINSTANCE`，X11 的 `Window` / `Display` 等。[SPEC]
- `VkInstance` 必须启用对应平台 surface extension，例如 `VK_KHR_android_surface`、`VK_KHR_win32_surface`。[SPEC]

### 下游影响

- `VkSwapchainKHR` 必须基于 surface 创建。
- `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回的 `minImageCount`、`currentExtent`、`maxImageCount`、`supportedTransforms` 等直接约束 swapchain 参数。[SPEC]
- `vkQueuePresentKHR` 需要 surface 有效。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSurfaceKHR`
- `VkAndroidSurfaceCreateInfoKHR` / `VkWin32SurfaceCreateInfoKHR` / `VkXlibSurfaceCreateInfoKHR`
- `VkSurfaceCapabilitiesKHR`
- `VkSurfaceFormatKHR`
- `VkPresentModeKHR`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateAndroidSurfaceKHR` | Android 平台从 `ANativeWindow` 创建 surface。[ANDROID] |
| `vkCreateWin32SurfaceKHR` | Windows 平台从 `HWND` 创建 surface。[SPEC] |
| `vkDestroySurfaceKHR` | 销毁 surface，必须在 swapchain 销毁之后、instance 销毁之前调用。[SPEC] |
| `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` | 查询 surface 能力。[SPEC] |
| `vkGetPhysicalDeviceSurfaceFormatsKHR` | 查询可用 format / color space。[SPEC] |
| `vkGetPhysicalDeviceSurfacePresentModesKHR` | 查询可用 present mode。[SPEC] |
| `vkGetPhysicalDeviceSurfaceSupportKHR` | 查询指定 queue family 是否支持 presentation。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_surface`（核心已普及，通常必须显式启用）。
- `VK_KHR_android_surface` / `VK_KHR_win32_surface` / `VK_KHR_xlib_surface` 等平台扩展。
- Android 可用性：所有支持 Vulkan 的 Android 设备均可用，但 `ANativeWindow` 有效性由 Android 生命周期控制。[ANDROID]

---

## 4. 标准使用流程

```text
创建平台窗口（ANativeWindow / HWND / Window）
→ 在 VkInstance 启用平台 surface extension
→ vkCreateXxxSurfaceKHR
→ vkGetPhysicalDeviceSurfaceCapabilitiesKHR
→ vkGetPhysicalDeviceSurfaceFormatsKHR
→ vkGetPhysicalDeviceSurfacePresentModesKHR
→ 选择 swapchain format / present mode / extent
→ vkCreateSwapchainKHR
→ ... 渲染循环 ...
→ vkDestroySwapchainKHR
→ vkDestroySurfaceKHR
→ vkDestroyInstance
```

---

## 5. 关键字段

| 字段 / 参数 | 专家关注点 | 常见错误 |
|---|---|---|
| `window` / `hwnd` / `dpy` | 平台句柄必须在 surface 整个生命周期内有效。 | Android 中 `ANativeWindow` 已销毁但 surface 仍在使用。[ANDROID] |
| `flags` | 通常填 0。 | 误填保留标志导致创建失败。[SPEC] |
| `currentExtent` | `0xFFFFFFFF` 表示可自定义；否则必须严格使用返回值。[SPEC] | Android 上忽略 `currentExtent` 为 0 的情况，直接创建 swapchain。[ANDROID] |
| `supportedUsageFlags` | 决定 swapchain image 是否可被用作 transfer dst / sampled / color attachment。[SPEC] | 想用 swapchain image 做后处理输入但 usage 未包含 `TRANSFER_SRC`。[SPEC] |
| `minImageCount` / `maxImageCount` | 决定 swapchain image 数量。 | `minImageCount` 低于 2 导致双缓冲缺失；高于 `maxImageCount` 创建失败。[SPEC] |
| `presentModes` | `FIFO` / `MAILBOX` / `IMMEDIATE` 可用性因平台 / 驱动而异。 | 假设 `MAILBOX` 一定存在。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VkInstance` 是否启用了对应平台 surface extension？
- [ ] 平台窗口句柄是否仍有效？
- [ ] 用于 present 的 queue family 是否通过 `vkGetPhysicalDeviceSurfaceSupportKHR` 验证？
- [ ] 是否在创建 swapchain 前查询了 surface capabilities / formats / present modes？

### 使用阶段

- [ ] 是否检查 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回值？
- [ ] `currentExtent` 为 0 时是否延迟创建 swapchain？（Android 常见）[ANDROID]
- [ ] 是否只在主线程或持有 surface 生命周期的线程操作 surface？

### 销毁阶段

- [ ] 是否先销毁 `VkSwapchainKHR` 再销毁 `VkSurfaceKHR`？[SPEC]
- [ ] 销毁 surface 前是否确认没有 in-flight present 仍引用它？[SPEC]
- [ ] Android `onDestroy` / surface destroyed 后是否不再调用 present？[ANDROID]

---

## 7. 高频错误

1. `ANativeWindow` 在 `onSurfaceDestroyed` 后被继续使用，导致 native crash。[ANDROID]
2. 未查询 `supportedTransforms`，横竖屏切换后 image orientation 错误。[ANDROID]
3. `currentExtent` 为 0 时仍调用 `vkCreateSwapchainKHR`，返回错误。[ANDROID]
4. 选择 `presentMode` 时未做 fallback，某些设备不支持 `MAILBOX`。[TOOL]
5. 销毁顺序错误：先销毁 surface 再销毁 swapchain。[SPEC]
6. 多 `VkDevice` 共享同一 surface 时出现 ownership 或生命周期混乱。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- 关注 `VUID-vkCreate*SurfaceKHR-*` 相关错误。
- 关注 `VUID-vkDestroySurfaceKHR-surface-01266`（surface 仍被 swapchain 使用）。[SPEC]
- 关注 `vkQueuePresentKHR` 返回 `VK_ERROR_SURFACE_LOST_KHR`。[TOOL]

### RenderDoc / AGI

- RenderDoc 通常抓不到 surface 本身，但可验证 swapchain image 是否正确输出。
- AGI 可验证 Android surface / swapchain 状态与 lifecycle 事件。[TOOL]

### 日志 / 代码检查

- 检查 `vkCreate*SurfaceKHR` 返回值。
- 检查 `ANativeWindow` 生命周期日志。
- 检查 `onSurfaceCreated` / `onSurfaceDestroyed` / `onPause` / `onResume` 回调中 surface 的创建与销毁时机。[ANDROID]

---

## 9. 生命周期风险

### 创建时机

- 平台窗口创建后、swapchain 创建前。
- Android 通常在 `android_app_cmd` 的 `APP_CMD_INIT_WINDOW` 或 `SurfaceHolder.Callback.surfaceCreated` 中创建。[ANDROID]

### 使用时机

- 创建 swapchain 时使用。
- 每帧 `vkQueuePresentKHR` 时隐式依赖 surface 有效。
- 查询 surface capabilities 时使用。

### 销毁时机

- 在 `vkDestroySwapchainKHR` 之后、`vkDestroyInstance` 之前。[SPEC]
- Android 在 `APP_CMD_TERM_WINDOW` 或 `surfaceDestroyed` 之后应尽快销毁，并停止渲染线程。[ANDROID]

### in-flight 风险

- `vkQueuePresentKHR` 可能异步持有 surface 引用；销毁 surface 前需确保 GPU 已完成相关工作，或 render loop 已停止。[SPEC]
-  retired swapchain 不影响 surface 生命周期，但 surface 销毁必须等 swapchain 销毁完成。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 销毁 surface 前，CPU 需等待 GPU idle 或至少确认没有 pending present。[SPEC]
- Android 切后台时，render thread 应在 surface 销毁前停止提交。[ANDROID]

### GPU-GPU 同步

- surface 本身不直接参与 GPU-GPU 同步；swapchain acquire / present semaphore 是实际同步点。

### 资源访问同步

- 若使用 swapchain image 作为 transfer src / sampled image，必须通过 barrier 转换 layout。[SPEC]

---

## 11. Android 注意点

- `ANativeWindow` 由 Android 系统管理，可能在 `onPause` / `surfaceDestroyed` 后失效。[ANDROID]
- `APP_CMD_TERM_WINDOW` 收到后，必须停止调用 `vkQueuePresentKHR`，否则可能 native crash。[ANDROID]
- `APP_CMD_INIT_WINDOW` 收到后，需在新 `ANativeWindow` 上重新创建 surface 和 swapchain。[ANDROID]
- 横竖屏切换时 `ANativeWindow` 可能变化，旧 surface 必须销毁后重建。[ANDROID]
- `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 在 surface 失效后调用会返回错误，应作为生命周期状态的一部分处理。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- surface 查询（capabilities / formats / present modes）通常在初始化阶段完成，不应每帧调用。[ENGINE]
- 平台 surface extension 创建开销通常可忽略，但应避免反复创建 / 销毁 surface。[HEUR]

### GPU 侧

- surface 本身不直接消耗 GPU 资源；相关性能成本来自 swapchain image 数量、present mode、format 带宽。[SPEC]

### 移动端

- Android 上 `FIFO` 通常更省电，`MAILBOX` 延迟更低但可能增加功耗。[ENGINE]
- `BGRA8_UNORM` 与 `RGBA8_UNORM` 在部分移动端 GPU 上 bandwidth 不同，应结合 AGI 验证。[VENDOR][TOOL]

---

## 13. 专家经验

**经验**：
在 Android 工程中，建议把 `VkSurfaceKHR` 的生命周期与 `ANativeWindow` 严格绑定，不要提前创建或延迟销毁。

**适用条件**：
Android Native Activity / SurfaceView / TextureView 渲染场景，生命周期事件可稳定接收。

**不适用情况**：
桌面窗口句柄长期稳定、不会频繁销毁重建的场景。

**来源**：`[ANDROID][ENGINE]`

---

## 14. 相关 API 卡片

- `swapchain.md`
- `swapchain_recreate.md`
- `../03_command_buffer/queue_submit.md`
- `../08_synchronization/semaphore.md`
- `../09_debug_validation/validation_layer.md`

---

## 15. 需要回查官方文档的情况

1. 目标平台 surface extension 名称与创建函数（Win32 / Xlib / Wayland / macOS MVK 等）。
2. 特定 GPU 对 `VkSurfaceCapabilitiesKHR` 中 `currentTransform`、`supportedTransforms` 的具体行为。
3. Android `ANativeWindow` 与 `VkSurfaceKHR` 的精确生命周期边界。
4. 多 GPU / 多 surface 场景下的 queue family present 支持查询。

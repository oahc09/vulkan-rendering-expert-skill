# API Card: Desktop Windowing Integration（SDL / GLFW / Win32）

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 显示链（Surface/Swapchain）+ Desktop 平台 |
| Vulkan 对象 | `VkSurfaceKHR` / `VkSwapchainKHR` / `VkExtent2D` |
| 常用 API | `vkCreateWin32SurfaceKHR` / `vkCreateSwapchainKHR` / `vkAcquireNextImageKHR` / `vkQueuePresentKHR` |
| 适用平台 | Windows（Win32 / SDL2 / GLFW3）；Linux/macOS 思路一致但窗口 API 不同 |
| 来源等级 | `[SPEC] [GUIDE] [ENGINE] [HEUR]` |
| 适用 Vulkan 版本 | Vulkan 1.x + `VK_KHR_surface` / `VK_KHR_win32_surface`（多数为 instance 扩展，1.0 可用） |

---

## 1. 一句话定位

把桌面窗口系统的窗口句柄桥接为 `VkSurfaceKHR`，并处理桌面特有事件（最小化 / resize / DPI 变化）下的 swapchain 生命周期，是 Android Surface 生命周期问题的桌面对等物。

---

## 2. 所属对象链路

```text
窗口句柄（HWND / SDL_Window / GLFWwindow）
→ vkCreateWin32SurfaceKHR（或 SDL_Vulkan_CreateSurface / glfwCreateWindowSurface）
→ vkGetPhysicalDeviceSurfaceSupportKHR（选 present queue）
→ vkGetPhysicalDeviceSurfaceCapabilitiesKHR（当前 extent）
→ vkCreateSwapchainKHR
→ acquire / submit / present 循环
```

### 上游依赖

- instance 扩展：`VK_KHR_surface` + `VK_KHR_win32_surface`；所需扩展清单可由 SDL/GLFW 查询函数返回，仍需在创建 instance 时显式启用。[SPEC][TOOL]

### 下游影响

- 窗口事件（resize / 最小化 / DPI）直接映射为 swapchain 依赖资源组重建，规则与 Android rotation 相同，生命周期模型见 `02_core_mental_model/android_surface_swapchain_lifecycle.md`（Android 视角，桌面事件按同一模型映射）。

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSurfaceKHR`
- `VkWin32SurfaceCreateInfoKHR`（`hwnd` / `hinstance`）
- `VkSurfaceCapabilitiesKHR` / `VkExtent2D`
- `VkSwapchainKHR`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateWin32SurfaceKHR` | 原生路径，`VkWin32SurfaceCreateInfoKHR` 填窗口句柄 `hwnd` 与模块句柄 `hinstance`。[SPEC] |
| `SDL_Vulkan_CreateSurface` | SDL2 ≥ 2.0.6；SDL3 同名函数签名有变（新增 instance 创建信息与 allocator 参数），使用前核对版本。[TOOL] |
| `glfwCreateWindowSurface` | GLFW ≥ 3.2 的官方封装，替代手写平台分支。[TOOL] |
| `vkGetPhysicalDeviceSurfaceSupportKHR` | 逐 queue family 验证是否支持该 surface 的 present。[SPEC] |
| `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` | 查询 `currentExtent` / min-max image count / transform 约束。[SPEC] |
| `vkGetPhysicalDeviceSurfaceFormatsKHR` / `vkGetPhysicalDeviceSurfacePresentModesKHR` | 查询可用 format / present mode。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_surface` + `VK_KHR_win32_surface`：instance 级扩展，Vulkan 1.0 即可用；Linux 对应 `VK_KHR_xlib_surface` / `VK_KHR_wayland_surface`，macOS 对应 `VK_EXT_metal_surface`。[SPEC]
- `VK_KHR_swapchain`：device 级扩展。[SPEC]
- 扩展清单查询：`SDL_Vulkan_GetInstanceExtensions` / `glfwGetRequiredInstanceExtensions`（各自返回所需 instance 扩展集合，签名随库版本有差异）。[TOOL]
- Android 是否可用：不适用（本卡为桌面平台，Android 用 `vkCreateAndroidSurfaceKHR`）。

---

## 4. 标准使用流程

```text
创建窗口（不自动创建 OpenGL 上下文）
→ 创建 instance 并启用 surface 扩展
→ 创建 VkSurfaceKHR（库封装或原生 API）
→ 选 present queue（surfaceSupport 检查）
→ 查询 surface capabilities / formats / present modes
→ 创建 swapchain（extent 取 clamp(capabilities.currentExtent)）
→ 渲染循环：acquire → submit（含 present/wait semaphore）→ present
→ 处理窗口事件 → 必要时 recreate swapchain
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `capabilities.currentExtent` | 为 `0xFFFFFFFF`（`UINT32_MAX` 特殊值，width/height 各分量）时需用窗口实际像素尺寸，并 clamp 到 min/max extent。[SPEC] | 直接用窗口逻辑尺寸（DPI 缩放后不一致）。[TOOL] |
| `imageExtent` | 必须在 min/max extent 范围内 clamp。[SPEC] | 未 clamp 直接用窗口尺寸。[SPEC] |
| `clipped` | 通常 VK_TRUE（被遮挡区域不保证内容）。[GUIDE] | 期望遮挡区仍可读回时误开 clipped。[GUIDE] |
| present mode | FIFO 保底可用；MAILBOX/IMMEDIATE 视平台。[SPEC] | 未确认支持即请求 MAILBOX。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] instance 是否启用了 `VK_KHR_surface` + 平台 surface 扩展（或采用 SDL/GLFW 查询到的扩展清单）？[SPEC]
- [ ] surface 创建函数返回值是否检查？封装函数失败常见于扩展未启用或窗口句柄无效。[TOOL]
- [ ] present queue family 是否通过 `vkGetPhysicalDeviceSurfaceSupportKHR` 验证？[SPEC]
- [ ] `imageExtent` 是否按 `currentExtent` 特殊值规则取值并 clamp 到 min/max？[SPEC]
- [ ] presentMode 是否从查询结果中选择，且以 FIFO 为 fallback？[SPEC]

### 使用阶段

- [ ] acquire / present 是否处理 `VK_ERROR_OUT_OF_DATE_KHR`（必须 recreate 后才能继续 present）与 `VK_SUBOPTIMAL_KHR`（本帧已成功，可延迟到帧末 recreate）？[SPEC]
- [ ] 最小化期间是否暂停渲染循环，restore 后再恢复？[ENGINE]
- [ ] resize 消息风暴是否去抖（合并为至多每帧一次 recreate）？[ENGINE]
- [ ] DPI 变化后是否以窗口像素尺寸（framebuffer size）为准，而非逻辑尺寸？[TOOL]

### 销毁阶段

- [ ] 窗口销毁前是否按依赖逆序：先销毁 swapchain 及其依赖资源，再销毁 surface？[SPEC]
- [ ] 事件回调里销毁 Vulkan 对象前是否先暂停渲染线程？[ENGINE]
- [ ] 退出路径是否等待 GPU idle / in-flight fence 后再销毁？[SPEC]

---

## 7. 高频错误

1. 最小化后仍持续 present：应暂停渲染循环，等 restore（最小化时 client area / extent 可能为 0，继续创建或 present 会失败或空耗 CPU/GPU）。[ENGINE]
2. resize 消息风暴中每帧 recreate swapchain：应去抖，或改为由 acquire / present 返回错误触发。[ENGINE]
3. DPI 缩放下用逻辑坐标当像素坐标：`imageExtent` 与真实 framebuffer 尺寸不符，画面被合成器拉伸或 extent 校验失败。[TOOL]
4. `VK_ERROR_OUT_OF_DATE_KHR` 处理遗漏：swapchain 已不能用于 present，必须 recreate。[SPEC]
5. `VK_SUBOPTIMAL_KHR` 被永久忽略：本帧仍有效但应尽快 recreate，否则持续以次优方式呈现。[SPEC]
6. 窗口销毁时先销毁 surface 再销毁 swapchain（违反依赖逆序）。[SPEC]
7. 在窗口事件回调里同步销毁 Vulkan 对象，与渲染线程竞争：应置标志位，暂停渲染线程后在统一路径处理。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkSwapchainCreateInfoKHR-imageExtent-01274`：extent 越界（resize / 最小化期间常见）。
- `VUID-vkCreateWin32SurfaceKHR-*`：句柄 / 扩展启用问题。
- `VUID-vkAcquireNextImageKHR-*` / `VUID-vkQueuePresentKHR-*`：返回码处理与 semaphore 配对。

### RenderDoc / AGI

- RenderDoc 本身运行于桌面窗口系统：直接抓帧验证 present 内容、swapchain image 顺序、resize 后依赖资源是否重建。
- AGI 面向 Android；桌面 GPU 分析用厂商工具（Nsight Graphics / Radeon GPU Profiler）替代。[TOOL]

### 日志 / 代码检查

- 打印 acquire / present 返回值，确认 recreate 触发路径。
- 打印 `currentExtent`、窗口像素尺寸（framebuffer size）、窗口逻辑尺寸三者对比，定位 DPI 问题。
- 打印最小化 / restore / resize / DPI 事件时序，确认暂停与恢复逻辑生效。

---

## 9. 生命周期风险

### 创建时机

- 窗口创建后、渲染循环启动前；SDL/GLFW 封装函数在 instance 创建后调用。[TOOL]

### 使用时机

- 每帧 acquire / submit / present；窗口事件驱动 recreate。

### 销毁时机

- 窗口或应用退出时，按 framebuffer / image view → swapchain → surface 的依赖逆序。[SPEC]
- surface 销毁前，所有基于它创建的 swapchain 必须已销毁。[SPEC]

### in-flight 风险

- 事件回调销毁旧资源时，in-flight command buffer 可能仍引用旧 swapchain image / framebuffer：必须先等待 fence signal 或暂停渲染线程。[SPEC]
- recreate 时旧 swapchain 通过 `oldSwapchain` 退休，GPU 用完前不得销毁旧句柄。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 窗口事件线程与渲染线程共享 swapchain 状态：recreate / 销毁前先暂停渲染线程并等待 in-flight fence（或 `vkDeviceWaitIdle`）。[ENGINE]
- 窗口销毁路径在销毁 surface 前需确认无 pending present。[SPEC]

### GPU-GPU 同步

- acquire 的 signal semaphore 与 present 的 wait semaphore 配对规则，与 `03_api_manual/03_command_buffer/fence_semaphore.md` 相同。[SPEC]

### 资源访问同步

- swapchain image 初始 layout 为 `UNDEFINED` / `PRESENT_SRC_KHR`，首帧与 recreate 后首次渲染需正确 transition，见 `03_api_manual/02_surface_swapchain/swapchain.md`。[SPEC]

---

## 11. Android 注意点

不适用（本卡为桌面平台）。Android 对等卡见 `03_api_manual/10_android_platform/android_surface.md` 与 `02_core_mental_model/android_surface_swapchain_lifecycle.md`。

---

## 12. 性能注意点

### CPU 侧

- resize 风暴期间去抖 recreate，避免每帧销毁 / 创建整组尺寸相关资源。[ENGINE]
- 最小化时暂停渲染循环（等待 restore），避免空转与对无效 swapchain 的重试。[ENGINE]

### GPU 侧

- 窗口模式 vs 全屏独占的 present mode 与 tearing 行为差异大（窗口走合成器 flip 路径；全屏独占路径及 `VK_EXT_full_screen_exclusive` 等扩展需核对目标平台与现行 registry 状态）。[HEUR][TOOL]
- HDR / 可变刷新率：需先查询 surface format / color space 与相关扩展支持后再启用，不得假设可用。[TOOL]

### 移动端

- 不适用（本卡为桌面平台）；移动端显示链见 `03_api_manual/10_android_platform/android_surface.md`。

---

## 13. 专家经验

```text
经验：
桌面 swapchain recreate 的触发策略优先“由 acquire/present 返回码驱动”，而不是仅依赖窗口事件；事件只作提前提示。

适用条件：
窗口系统事件可能丢失或延迟（远程桌面、合成器行为差异）的多平台桌面应用。

不适用情况：
事件可靠且需要即时响应的单一平台应用（如仅 Windows 原生），可只监听消息循环。
```

**来源**：`[ENGINE][HEUR]`

---

## 14. 相关 API 卡片

- `03_api_manual/02_surface_swapchain/swapchain.md`
- `03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `03_api_manual/03_command_buffer/fence_semaphore.md`
- `03_api_manual/03_command_buffer/frames_in_flight.md`

---

## 15. 需要回查官方文档的情况

1. SDL/GLFW 封装函数在所用版本的确切签名（版本差异大 [TOOL]）。
2. 各平台 surface 扩展（win32/xlib/wayland/metal）的字段要求。
3. present mode / composite alpha 在目标合成器的实际支持。

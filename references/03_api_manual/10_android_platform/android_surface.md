# API Card: Android Surface / VK_KHR_android_surface

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Android 平台链 |
| Vulkan 对象 | `VkSurfaceKHR` |
| 常用 API | `vkCreateAndroidSurfaceKHR` / `vkDestroySurfaceKHR` |
| 适用平台 | Android |
| 来源等级 | `[SPEC] [ANDROID] [TOOL]` |
| 适用 Vulkan 版本 | Vulkan 1.0 + `VK_KHR_android_surface` |

---

## 1. 一句话定位

Android Surface 是 Vulkan 与 Android 窗口系统（`ANativeWindow` / `Surface`）之间的桥梁，通过 `VK_KHR_android_surface` 创建 `VkSurfaceKHR`，为 swapchain 提供可呈现的图像队列。[SPEC][ANDROID]

---

## 2. 所属对象链路

```text
ANativeWindow / Surface（Java/Kotlin 层或 Native 层）
→ VkInstance + VK_KHR_android_surface
→ vkCreateAndroidSurfaceKHR(VkAndroidSurfaceCreateInfoKHR)
→ VkSurfaceKHR
→ vkCreateSwapchainKHR
→ VkSwapchainKHR
```

### 上游依赖

- 已启用 `VK_KHR_android_surface` instance extension。[SPEC]
- 持有有效的 `ANativeWindow*` 指针，通常来自 `SurfaceView`、`TextureView` 或 `AHardwareBuffer` 等窗口句柄。[ANDROID]

### 下游影响

- `VkSurfaceKHR` 用于查询 surface capabilities 并创建 swapchain。[SPEC]
- Surface 尺寸/格式变化时，需要 recreate swapchain。[ANDROID]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSurfaceKHR`
- `VkAndroidSurfaceCreateInfoKHR`
- `VkAndroidSurfaceCreateFlagsKHR`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateAndroidSurfaceKHR` | 从 `ANativeWindow` 创建 Vulkan surface。[SPEC] |
| `vkDestroySurfaceKHR` | 销毁 surface；需确保相关 swapchain 已销毁。[SPEC] |
| `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` | 查询 surface 当前范围、minImageCount 等。[SPEC] |
| `vkGetPhysicalDeviceSurfaceFormatsKHR` | 查询支持的 color space 与 format。[SPEC] |
| `vkGetPhysicalDeviceSurfacePresentModesKHR` | 查询 present mode（FIFO、MAILBOX 等）。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_android_surface`：Android 平台必需。
- `VK_KHR_surface` / `VK_KHR_swapchain`：通用 surface 与 swapchain 扩展。

---

## 4. 标准使用流程

```text
启用 VK_KHR_android_surface instance extension
→ 从 SurfaceView / TextureView 获取 ANativeWindow
→ 构造 VkAndroidSurfaceCreateInfoKHR（window = ANativeWindow*）
→ vkCreateAndroidSurfaceKHR
→ 查询 surface capabilities / formats / present modes
→ vkCreateSwapchainKHR
→ 每帧 acquire → render → present
→ surface 变化时 recreate swapchain
→ 销毁 swapchain 后再销毁 surface
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `window` | `ANativeWindow*` 必须有效且生命周期覆盖 surface。[SPEC] | ANativeWindow 提前释放导致 surface 失效。[TOOL] |
| `sType` | 必须为 `VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR`。[SPEC] | 结构体类型填错。[TOOL] |
| `flags` | 当前保留为 0。[SPEC] | 误填非零值。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否在 instance create info 中启用了 `VK_KHR_android_surface`？
- [ ] `ANativeWindow` 是否已准备就绪？
- [ ] 是否检查了 surface 创建返回值？

### 使用阶段

- [ ] 是否在 `ANativeWindow` 有效期间使用 surface？
- [ ] Swapchain 是否与 surface 兼容？
- [ ] 是否处理 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`？[ANDROID]

### 销毁阶段

- [ ] 是否先销毁 swapchain 再销毁 surface？
- [ ] 是否等待 GPU 完成 present？

---

## 7. 高频错误

1. 未启用 `VK_KHR_android_surface` instance extension 就调用创建函数。[TOOL]
2. `ANativeWindow` 在 surface 销毁前已被释放。[TOOL]
3. 在 `SurfaceView` 未创建完成时过早创建 surface。[ANDROID]
4. 销毁顺序错误：先销毁 surface 再销毁 swapchain。[TOOL]
5. 忽略 `VK_ERROR_OUT_OF_DATE_KHR`，导致继续向已变化的 surface 提交。[ANDROID]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkAndroidSurfaceCreateInfoKHR-window-01223`：`window` 必须指向有效 `ANativeWindow`。
- `VUID-vkCreateAndroidSurfaceKHR-instance-01292`：instance extension 已启用。

### RenderDoc / AGI

- AGI 可捕获 surface、swapchain、present 调用与 ANativeWindow 生命周期事件。[TOOL]
- 检查 surface capabilities 与实际窗口尺寸是否一致。

### 日志 / 代码检查

- logcat 中查看 `vkCreateAndroidSurfaceKHR` 返回值。
- 检查 Java/Kotlin 层 SurfaceHolder 回调与 native surface 创建的对齐。
- 检查 `ANativeWindow_release` 的调用时机。

---

## 9. 生命周期风险

### 创建时机

- 在 `SurfaceHolder.Callback.surfaceCreated` 或等效 native 事件后创建。[ANDROID]

### 使用时机

- Surface 有效期间用于 swapchain 创建与 present。[SPEC]

### 销毁时机

- 在 `surfaceDestroyed` 或 activity 退出时销毁；必须先销毁 swapchain 及所有引用 swapchain image 的对象。[ANDROID][SPEC]

### in-flight 风险

- `ANativeWindow` 被释放或 surface 被销毁后，不能再进行 acquire/present；需等待 fence 确保 GPU 完成。[ANDROID]

---

## 10. 同步风险

### CPU-GPU 同步

- 销毁 surface 前需确保所有引用 swapchain image 的 command buffer 已完成，通常用 fence 等待。[SPEC]

### GPU-GPU 同步

- Present 依赖 acquire semaphore 与 render complete semaphore，详见 `../02_surface_swapchain/swapchain.md`。[SPEC]

### 资源访问同步

- Swapchain image 在 acquire 后、present 前需要正确的 layout transition 与 access mask。[SPEC]

---

## 11. Android 注意点

- `SurfaceView` 与 `TextureView` 的生命周期不同：`SurfaceView` 的 surface 在后台可独立存在，`TextureView` 受 view 树影响更大。[ANDROID]
- 横竖屏切换或分屏时，surface size 会变化，必须处理 `VK_ERROR_OUT_OF_DATE_KHR` 并 recreate swapchain。[ANDROID]
- Activity `onPause` / `onResume` 时，surface 可能暂时不可用；需暂停渲染循环并重新初始化。[ANDROID]
- 部分 OEM 设备对 surface 格式有额外限制，建议运行时查询 formats 而非硬编码。[ANDROID]
- 从 Java `Surface` 获取 `ANativeWindow` 后，native 层需要负责 `ANativeWindow_release`。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Surface 创建本身开销小，但 swapchain recreate 涉及 image 分配与对象重建，应避免频繁触发。[ENGINE]

### GPU 侧

- Surface 不直接产生 GPU 开销；相关开销主要来自 swapchain present 与 composite。[ENGINE]

### 移动端

- 避免在 `onSurfaceCreated` 中做大量同步初始化，防止 ANR。[ANDROID]
- 尺寸变化时延迟一帧再 recreate swapchain，可减少抖动。[HEUR]

---

## 13. 专家经验

**经验**：
把 `VkSurfaceKHR` 与 `ANativeWindow` 的生命周期绑定管理：谁持有 `ANativeWindow`，谁就负责在销毁 surface 后释放它。不要在 Java 层 surface 还未创建完成时从 native 层急创 Vulkan surface。对 `SurfaceView`，建议在 `surfaceCreated` 中创建、在 `surfaceDestroyed` 中等待 GPU 空闲后再销毁。

**适用条件**：
所有 Android Vulkan 应用。

**不适用情况**：
Headless Vulkan（如离屏 compute）不需要 surface。

**来源**：`[ANDROID][ENGINE]`

---

## 14. 相关 API 卡片

- `anativewindow.md`
- `../02_surface_swapchain/surface.md`
- `../02_surface_swapchain/swapchain.md`
- `../02_surface_swapchain/swapchain_recreate.md`
- `../01_instance_device_queue/instance.md`
- `../01_instance_device_queue/logical_device.md`

---

## 15. 需要回查官方文档的情况

1. 不同 Android 版本对 `VK_KHR_android_surface` 的支持差异。
2. `TextureView` / `SurfaceView` / `AHardwareBuffer` 各自获取 `ANativeWindow` 的具体方式。
3. 分屏、折叠屏、自由窗口模式下的 surface size 变化规则。
4. 特定 OEM 对 surface format 与 present mode 的限制。
5. `vkQueuePresentKHR` 在 surface 被销毁时的行为。

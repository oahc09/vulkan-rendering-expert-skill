# API Card: ANativeWindow

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Android 平台链 |
| Vulkan 对象 | `ANativeWindow*`（Android NDK） |
| 常用 API | `ANativeWindow_fromSurface` / `ANativeWindow_acquire` / `ANativeWindow_release` |
| 适用平台 | Android |
| 来源等级 | `[ANDROID] [SPEC] [ENGINE]` |
| 适用 Vulkan 版本 | N/A（Android NDK） |

---

## 1. 一句话定位

`ANativeWindow` 是 Android NDK 对 Java `Surface` 的原生抽象，Vulkan 通过它创建 Android surface，其引用计数与生命周期直接决定窗口句柄是否有效。[ANDROID]

---

## 2. 所属对象链路

```text
Java Surface / SurfaceHolder（Android UI 层）
→ ANativeWindow_fromSurface（NDK）
→ ANativeWindow*（引用计数 +1）
→ vkCreateAndroidSurfaceKHR
→ VkSurfaceKHR
→ VkSwapchainKHR
```

### 上游依赖

- Java/Kotlin 层已创建 `Surface` 或 `SurfaceHolder`。[ANDROID]
- 调用线程已 Attach 到 JVM（若从 native 线程调用）。[ANDROID]

### 下游影响

- `ANativeWindow*` 作为 `VkAndroidSurfaceCreateInfoKHR.window` 创建 Vulkan surface。[SPEC]
- 窗口尺寸、方向变化时，需要 recreate swapchain。[ANDROID]

---

## 3. 核心对象与 API

### 核心 Android NDK 对象

- `ANativeWindow`
- `ASurfaceTexture` / `SurfaceHolder`（Java 层来源）

### 常用 API

| API | 作用 |
|---|---|
| `ANativeWindow_fromSurface` | 从 Java `jobject Surface` 获取 `ANativeWindow*`，引用计数 +1。[ANDROID] |
| `ANativeWindow_fromSurfaceTexture` | 从 `ASurfaceTexture` 获取 `ANativeWindow*`。[ANDROID] |
| `ANativeWindow_acquire` | 显式增加引用计数。[ANDROID] |
| `ANativeWindow_release` | 减少引用计数；计数为 0 时释放。[ANDROID] |
| `ANativeWindow_getWidth` / `getHeight` | 查询窗口当前尺寸。[ANDROID] |
| `ANativeWindow_setBuffersGeometry` | 设置缓冲区格式与尺寸（通常由 swapchain 决定，非必需）。[ANDROID] |

### 相关扩展 / 版本

- 与 Vulkan `VK_KHR_android_surface` 扩展配合使用。

---

## 4. 标准使用流程

```text
在 SurfaceHolder.Callback.surfaceCreated 中接收 Surface
→ JNIEnv* 调用 ANativeWindow_fromSurface(surface)
→ ANativeWindow_acquire 一次（若需跨函数持有）
→ 用 ANativeWindow* 创建 VkSurfaceKHR
→ 创建 swapchain、渲染循环
→ surface 变化或销毁时：
   → 等待 GPU 空闲
   → 销毁 swapchain
   → 销毁 VkSurfaceKHR
   → ANativeWindow_release
```

---

## 5. 关键字段

| 字段 / API | 专家关注点 | 常见错误 |
|---|---|---|
| `ANativeWindow_fromSurface` | 返回的指针引用计数 +1，需要对应 release。[ANDROID] | 忘记 release 导致窗口泄漏。[TOOL] |
| `ANativeWindow_acquire` / `release` | 配对使用；跨层传递时需要明确所有权。[ANDROID] | 重复 release 或 acquire 缺失。[TOOL] |
| `getWidth` / `getHeight` | 获取当前缓冲区尺寸，可能随时变化。[ANDROID] | 用旧尺寸创建 swapchain。[TOOL] |
| `setBuffersGeometry` | 一般不需要；swapchain 会自行协商。[ANDROID] | 错误设置 format/size 导致呈现异常。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `ANativeWindow_fromSurface` 返回非空？
- [ ] 引用计数管理是否明确（谁 acquire、谁 release）？
- [ ] 是否在 surface 有效期间创建 Vulkan surface？

### 使用阶段

- [ ] 是否检查窗口尺寸变化并触发 swapchain recreate？
- [ ] 是否在 surface 销毁前停止使用？

### 销毁阶段

- [ ] 是否先释放 swapchain / surface 再 release `ANativeWindow`？
- [ ] `release` 调用次数是否与 `acquire` + `fromSurface` 次数匹配？

---

## 7. 高频错误

1. `ANativeWindow_fromSurface` 后未 `release`。[TOOL]
2. 在 `surfaceDestroyed` 之后仍使用 `ANativeWindow*`。[ANDROID]
3. 先 release `ANativeWindow` 再销毁 `VkSurfaceKHR`。[TOOL]
4. 多线程下未对 `ANativeWindow` 引用计数做同步。[TOOL]
5. 用 `ANativeWindow_getWidth/Height` 的返回值作为渲染分辨率但未处理旋转/缩放。[ANDROID]

---

## 8. Debug 检查路径

### Validation Layer

- Validation layer 主要检查 `VkSurfaceKHR`，不直接检查 `ANativeWindow` 引用计数，但 surface 失效通常伴随 VUID 错误。[TOOL]

### RenderDoc / AGI

- AGI 可追踪 surface 创建与 `ANativeWindow` 句柄。[TOOL]

### 日志 / 代码检查

- logcat 中检查 surface 相关崩溃（如 `ANativeWindow` 已释放后访问）。
- 检查 `ANativeWindow_fromSurface` 与 `ANativeWindow_release` 的配对。
- 检查 `SurfaceHolder` 回调顺序。

---

## 9. 生命周期风险

### 创建时机

- 在 Java `Surface` 可用后（`surfaceCreated` 回调）创建。[ANDROID]

### 使用时机

- 在 `ANativeWindow` 有效期间用于创建 Vulkan surface 和 swapchain。[ANDROID]

### 销毁时机

- 在 `surfaceDestroyed` 或 activity 退出时，先销毁 Vulkan 相关对象，再 release `ANativeWindow`。[ANDROID]

### in-flight 风险

- `ANativeWindow` 被 release 后，所有依赖它的 Vulkan 对象都必须已销毁，否则会出现 use-after-free。[ANDROID]

---

## 10. 同步风险

### CPU-GPU 同步

- 销毁 `ANativeWindow` 前需等待 GPU 完成，避免 in-flight swapchain image 访问已释放的窗口。[SPEC][ANDROID]

### GPU-GPU 同步

- 不直接涉及；swapchain present 的同步由 semaphore 与 fence 处理。[SPEC]

### 资源访问同步

- 无。

---

## 11. Android 注意点

- `SurfaceView` 的 surface 生命周期与 Activity 生命周期不完全相同；后台时 surface 可能仍存在，也可能被销毁，取决于系统与 OEM。[ANDROID]
- 从 Java 层向 native 层传递 `Surface` 时，确保在 native 使用期间 Java 对象不被 GC。[ANDROID]
- 多窗口/分屏/折叠屏下，`ANativeWindow` 尺寸可能在运行时变化，不要缓存为常量。[ANDROID]
- 部分设备在 `onResume` 后会重新创建 surface，需重新初始化渲染上下文。[ANDROID]
- 使用 `ANativeWindow_acquire` 显式持有引用，可避免 Java 层提前释放 surface 导致 native 层崩溃。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- `ANativeWindow_fromSurface` 和 `release` 开销很小，但频繁创建/销毁 surface 会连带触发 swapchain recreate。[ENGINE]

### GPU 侧

- `ANativeWindow` 本身不产生 GPU 开销。[ENGINE]

### 移动端

- 避免在 `surfaceCreated` 中做阻塞式初始化，防止 UI 线程卡顿或 ANR。[ANDROID]
- 在 `surfaceDestroyed` 中等待 GPU 空闲时间不宜过长，可考虑异步清理。[HEUR]

---

## 13. 专家经验

**经验**：
用 RAII 或明确的所有权对象包装 `ANativeWindow*`：构造时 `fromSurface` + `acquire`，析构时先释放 swapchain 和 surface 再 `release`。永远不要让 `ANativeWindow` 的生命周期比 `VkSurfaceKHR` 短。对 `SurfaceView`，建议把 `ANativeWindow` 的创建与销毁与 `surfaceCreated`/`surfaceDestroyed` 回调一一对应。

**适用条件**：
所有使用 Android surface 的 Vulkan 应用。

**不适用情况**：
纯离屏渲染或 headless Vulkan 不需要 `ANativeWindow`。

**来源**：`[ANDROID][ENGINE]`

---

## 14. 相关 API 卡片

- `android_surface.md`
- `../02_surface_swapchain/surface.md`
- `../02_surface_swapchain/swapchain.md`
- `../02_surface_swapchain/swapchain_recreate.md`
- `../01_instance_device_queue/instance.md`

---

## 15. 需要回查官方文档的情况

1. 不同 Android 版本对 `ANativeWindow` API 的可用性与行为差异。
2. `TextureView` / `SurfaceView` / `AHardwareBuffer` 各自获取 `ANativeWindow` 的线程与 JVM Attach 要求。
3. `ANativeWindow_setBuffersGeometry` 对 Vulkan swapchain 的影响。
4. 折叠屏/多窗口下 `ANativeWindow` 尺寸变化的官方推荐处理。
5. 特定 OEM 对 surface 生命周期回调的额外触发时机。

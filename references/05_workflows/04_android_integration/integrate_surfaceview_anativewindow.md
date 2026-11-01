# Workflow: Integrate Android SurfaceView / ANativeWindow

## 0. 适用范围

### 适用

- Android Java/Kotlin SurfaceView 接入 Native Vulkan。
- 通过 `ANativeWindow` 创建 Vulkan Surface。
- 需要处理 Surface created / changed / destroyed。
- 需要 native render thread 和 UI lifecycle 协作。

### 不适用

- 纯桌面 Vulkan。
- 只做 offscreen Vulkan compute。
- 不经过 Android Surface 的渲染。

---

## 1. 任务目标

建立 Android SurfaceView 到 Vulkan swapchain 的稳定桥接：

```text
SurfaceView / SurfaceHolder
→ Surface
→ ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Render Loop
```

---

## 2. 输入条件

需要确认：

- Java/Kotlin 层使用 SurfaceView / TextureView / NativeActivity。
- Native 层线程模型。
- Surface 生命周期回调位置。
- 是否已有 Vulkan instance / device。
- 是否已有 render thread。
- 是否支持 pause / resume。
- 是否支持 rotation / resize。

---

## 3. 前置检查

- [ ] Android NDK Vulkan 可用。
- [ ] Java/Kotlin 能把 Surface 传到 native。
- [ ] native 能获取 `ANativeWindow`。
- [ ] logcat 可记录 lifecycle。
- [ ] render thread 状态可控。
- [ ] Surface destroyed 后可停止渲染。

---

## 4. Vulkan 对象链路

```text
SurfaceView
→ SurfaceHolder.Callback
→ Surface
→ ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images
→ Render Loop
→ Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| Java Surface | Android Object | platform surface | Surface lifecycle | 是 |
| ANativeWindow | Native Handle | Vulkan surface input | Surface lifecycle | 是 |
| VkSurfaceKHR | Vulkan Surface | swapchain source | Surface lifecycle | 是 |
| VkSwapchainKHR | Vulkan Swapchain | present images | surface/size lifecycle | 是 |

---

## 6. Pipeline / Descriptor 设计

本 workflow 不直接涉及 pipeline / descriptor。
但必须保证：

- pipeline viewport / scissor 跟随 surface size。
- descriptor 若引用尺寸相关 offscreen image，surface changed 后必须更新。
- render pass / dynamic rendering attachment format 与 swapchain format 匹配。

---

## 7. 同步与 Layout 设计

重点不是 image barrier，而是 lifecycle 同步：

```text
UI Thread Surface Event
→ Native State Update
→ Render Thread Stop / Recreate / Resume
```

需要保证：

- Surface destroyed 后 render thread 不再 acquire / present。
- Recreate 前等待 in-flight GPU work。
- 旧 swapchain 资源不被 command buffer 继续引用。

---

## 8. 实现步骤

1. Java/Kotlin 实现 `SurfaceHolder.Callback`。
2. `surfaceCreated` 时传 Surface 到 native。
3. native 获取 `ANativeWindow`。
4. 创建 / 更新 `VkSurfaceKHR`。
5. 创建 swapchain。
6. 启动或恢复 render thread。
7. `surfaceChanged` 时触发 swapchain recreate。
8. `surfaceDestroyed` 对指定output/generation关闭入口，等待render线程停止访问确认后才返回；只投递事件不够。
9. 独立记录GPU submission完成与present退役证据，不能仅由frame fence或idle推断全部退休。
10. 销毁 surface-dependent resources。
11. release `ANativeWindow`。
12. pause/resume、可见性、Surface有效性和device健康分别记录，由组合条件控制该输出。

---

## 9. Android 注意点

必须建立状态机：

```text
NoSurface
→ SurfaceReady
→ SwapchainReady
→ Rendering
→ Paused
→ SurfaceDestroyed
```

关键规则：

- Surface created 不等于尺寸可用。
- Surface destroyed 后不能继续 present。
- pause 不一定意味着 surface destroyed。
- resume 不一定意味着 surface 已创建。
- rotation 可能触发 surface changed / destroyed / recreated。
- extent 为 0 时暂停创建 swapchain。

---

## 10. 验证方式

- [ ] 首次进入正常。
- [ ] surface created / changed / destroyed 日志完整。
- [ ] 横竖屏切换正常。
- [ ] 切后台 / 回前台正常。
- [ ] Surface destroyed 后无 native crash。
- [ ] AGI / logcat 可关联 frame。
- [ ] Validation clean。

---

## 11. 常见失败模式

1. Surface destroyed 后 render thread 继续运行。
2. `ANativeWindow` release 后仍被使用。
3. Surface changed 后没有 recreate swapchain。
4. pause/resume 与 surface lifecycle 状态冲突。
5. extent 为 0 仍创建 swapchain。
6. rotation 后 descriptor 引用旧尺寸资源。

---

## 12. 相关 API 卡片

- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`


<a id="android-host-contract"></a>
## Android 宿主桥接合同

前提：只使用应用拥有或公开平台正常授予的Surface；Java/JNI/C++17为参考，不强制Kotlin依赖。每个宿主实例分配稳定engineId/outputId，Surface每次替换递增generation。Java Surface传JNI后 `ANativeWindow_fromSurface` 所得引用最终匹配release；window引用不能延长Surface有效访问时段。[ANDROID][ENGINE]

| 宿主 | 入口/边界 | 验证条件 |
|---|---|---|
| 前台Activity的两个SurfaceView | 两套Callback/output状态，资源可按owner共享 | A局部销毁B继续；两Surface能力分别查询 |
| WallpaperService.Engine | preview与真实壁纸可同时多个Engine | 以真实回调与isPreview等公开信息识别；不硬编码实例数/锁屏OEM顺序 |
| AppWidget/RemoteViews | 受支持的远程视图集合，不是任意native view容器 | 不承诺直接嵌SurfaceView；可选合法静态内容/跳转应用内宿主 |
| OEM/系统专有宿主 | 不属于普通应用默认权限 | 单列公开协议/权限与实测，未验证不能宣称支持 |

Surface销毁回调等待“对应代线程已停止访问”的确认；不要持有render需获取的锁，也不要让render等待UI才能ack。后续资源退休不再访问失效Surface；完整状态机只在[生命周期权威段](handle_android_lifecycle.md#multi-surface-lifecycle)维护。

摄像头仅在明确授权且系统允许的前台测试路径；Wallpaper测试默认色条/非私密本地输入，不默认后台相机可用。无需root、隐藏API、接管其他应用Surface或绕过保护内容。
来源：[Callback](https://developer.android.com/reference/android/view/SurfaceHolder.Callback)、[WallpaperService](https://developer.android.com/reference/android/service/wallpaper/WallpaperService)、[RemoteViews](https://developer.android.com/reference/android/widget/RemoteViews)。

# Case: Surface Destroyed But Render Thread Still Presents

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Android / Surface / Crash |
| 平台 | Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Android App 切后台或销毁 Surface 后 native crash。  
logcat 中可以看到 `surfaceDestroyed` 已触发，但 render thread 仍在调用 acquire / submit / present。

---

## 2. 初始上下文

- Java/Kotlin 使用 SurfaceView。
- Native 层有独立 render thread。
- Surface 生命周期通过回调传到 native。
- Vulkan swapchain 依赖 ANativeWindow。
- pause / resume 与 surface destroyed 顺序不稳定。

---

## 3. 初始误判

最初容易怀疑：

```text
Vulkan driver bug；
swapchain recreate 不完整；
device lost；
present mode 不兼容。
```

但 logcat 证明 Surface 已 destroyed，render thread 仍在 present，说明核心是 Android 生命周期与 native render thread 状态机问题。

---

## 4. 排查路径

1. 打印 SurfaceView 生命周期。
2. 打印 native render thread 状态。
3. 打印 ANativeWindow acquire / release。
4. 打印 acquire / present 返回值。
5. 检查 surfaceDestroyed 是否通知 native。
6. 检查 render loop 是否能被安全停止。
7. 检查 old swapchain 是否在 GPU 完成后销毁。

---

## 5. 关键证据

### Validation Layer

可能不一定能捕获所有平台生命周期错误。

### logcat

关键证据：

```text
surfaceDestroyed
native render loop still running
vkQueuePresentKHR called after surface destroyed
```

### Native Crash Stack

可能出现在：

- present
- acquire
- swapchain
- window / surface 相关 native 调用

---

## 6. 根因

根因：Android Surface destroyed 后，native render thread 没有及时停止，仍继续使用依赖旧 ANativeWindow / swapchain 的资源进行 acquire / present，导致 native crash。

---

## 7. 修复方案

### 最小修复

- `surfaceDestroyed` 时设置 renderPaused / surfaceInvalid。
- render thread 立即停止 acquire / submit / present。
- 等待 in-flight GPU work。
- 销毁 swapchain-dependent resources。
- release ANativeWindow。

### 稳定修复

- 建立 Android lifecycle 状态机：
  ```text
  NoSurface
  → SurfaceReady
  → SwapchainReady
  → Rendering
  → Paused
  → SurfaceDestroyed
  ```
- render thread 只在 `Rendering` 状态提交 GPU work。
- Surface destroyed 和 App pause 都能安全进入非渲染状态。

### 工程化修复

- Java/Kotlin → native 使用事件队列。
- render thread 统一消费 lifecycle event。
- ANativeWindow 使用引用计数或明确 ownership。
- 所有 surface-dependent resources 挂到 surface generation。

---

## 8. 修复后验证

- [ ] 切后台不 crash。
- [ ] surfaceDestroyed 后没有 present 调用。
- [ ] Surface recreated 后能恢复渲染。
- [ ] 横竖屏切换正常。
- [ ] logcat 状态机清晰。
- [ ] AGI 中不会看到 destroyed surface 后继续提交。

---

## 9. 经验抽象

Android Vulkan 稳定性问题不能只看 Vulkan API。  
Surface / ANativeWindow 生命周期和 render thread 状态机是同等重要的渲染链路组成部分。

---

## 10. 预防规则

1. Surface destroyed 后 render thread 必须停止提交。
2. ANativeWindow release 后不能再被任何 Vulkan 路径使用。
3. Surface lifecycle event 必须进入 native 状态机。
4. pause/resume 不能和 surface lifecycle 混用成单一布尔值。
5. 所有 surface-dependent resource 必须集中销毁和重建。

---

## 11. 关联 API 卡片

- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`

---

## 13. 关联 Workflow

- `../../05_workflows/04_android_integration/integrate_surfaceview_anativewindow.md`
- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`

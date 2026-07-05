# Case: Android Rotation Uses Old Swapchain ImageView

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Android / Swapchain / Lifecycle |
| 平台 | Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Android 设备横竖屏切换后，Vulkan 画面黑屏或 native crash。  
首次进入 App 渲染正常。  
rotation 后 `vkQueuePresentKHR` 或 command buffer 执行阶段出现异常。

---

## 2. 初始上下文

- Android SurfaceView + Native Vulkan。
- 使用 swapchain image view 作为 render target。
- 使用 framebuffer 或 dynamic rendering attachment。
- 横竖屏切换触发 surface changed。
- 工程中有 swapchain recreate，但不完整。

---

## 3. 初始误判

最初容易怀疑：

```text
Android Surface 回调顺序异常；
Vulkan device 丢失；
shader 重新编译失败；
present mode 不兼容。
```

但 logcat 显示 Surface 已经 changed，swapchain 也重新创建了。  
最终发现 command buffer 或 framebuffer 仍引用旧 swapchain image view。

---

## 4. 排查路径

1. 打印 surface created / changed / destroyed 日志。
2. 打印 acquire / present 返回值。
3. 检查 swapchain recreate 是否触发。
4. 检查新 swapchain image count / extent。
5. 检查 image view 是否重新创建。
6. 检查 framebuffer / dynamic rendering attachment 是否重新绑定新 image view。
7. 检查 command buffer 是否重新录制。
8. 检查 in-flight command buffer 是否仍引用旧资源。
9. 用 AGI / RenderDoc 查看 resize 后 frame resource。

---

## 5. 关键证据

### Validation Layer

可能出现：

- destroyed object used
- framebuffer / image view invalid
- command buffer references invalid object
- render pass / framebuffer mismatch

### AGI / logcat

观察到：

- Surface changed 已触发。
- 新 swapchain extent 正确。
- 旧 image view handle 仍出现在 command buffer 或 framebuffer 链路中。

### Code

关键问题：

```text
recreateSwapchain() 只重建了 VkSwapchainKHR，没有重建 framebuffer 或重新录制 command buffer。
```

---

## 6. 根因

根因：Android 横竖屏切换后 swapchain image view 已失效，但 framebuffer / command buffer / descriptor 仍引用旧 swapchain image view，导致渲染或 present 阶段使用无效资源。

---

## 7. 修复方案

### 最小修复

- swapchain recreate 时重建 image views。
- 重建 framebuffer 或 dynamic rendering attachment。
- 重新录制 command buffer。
- 更新引用尺寸相关 image 的 descriptor。
- recreate 前等待 in-flight GPU work 完成。

### 稳定修复

- 建立 swapchain-dependent resource group。
- 统一管理：
  - swapchain
  - swapchain image view
  - depth image
  - framebuffer
  - offscreen image
  - command buffer
  - descriptor
- 每次 surface extent 变化时整组重建。

### 工程化修复

- 引入 resource generation id。
- command buffer 录制时绑定当前 generation。
- 运行时 assert 禁止旧 generation 资源被提交。

---

## 8. 修复后验证

- [ ] 横竖屏切换多次不 crash。
- [ ] Validation clean。
- [ ] AGI / RenderDoc 中没有旧 image view。
- [ ] framebuffer / attachment 尺寸正确。
- [ ] command buffer 已重录。
- [ ] pause / resume 后仍正常。

---

## 9. 经验抽象

Swapchain recreate 不是只重建 `VkSwapchainKHR`。  
所有尺寸相关、引用 swapchain image view 的对象都必须一起处理。

---

## 10. 预防规则

1. 所有 swapchain-dependent resources 必须集中管理。
2. command buffer 中不能长期固化旧 framebuffer / image view。
3. resize / rotation 后必须重录 command buffer。
4. descriptor 若引用 screen-sized offscreen image，必须更新。
5. recreate 前必须等待旧 GPU work 完成。

---

## 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/integrate_surfaceview_anativewindow.md`

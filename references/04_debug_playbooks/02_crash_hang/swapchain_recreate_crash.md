# Debug Playbook: Swapchain Recreate Crash

## 0. 适用范围

### 适用

- Android 横竖屏切换后 crash。
- 窗口 resize 后 crash。
- `VK_ERROR_OUT_OF_DATE_KHR` 后处理异常。
- pause / resume 后 Vulkan 输出异常。
- Surface 重建后继续使用旧 swapchain 资源。

### 不适用

- App 首次启动即 crash 且未创建 swapchain。
- 纯 shader / pipeline 编译错误。
- 非 swapchain 相关资源崩溃。

---

## 1. 现象

常见表现：

- rotation 后 native crash。
- pause/resume 后黑屏或 crash。
- `vkQueuePresentKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR`。
- `vkAcquireNextImageKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR`。
- command buffer 引用旧 framebuffer / image view。
- depth image 尺寸和 swapchain 不一致。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 旧 swapchain image view 仍被使用 | resize 后 crash / validation | Swapchain / ImageView |
| P0 | in-flight command buffer 引用旧资源 | crash 或 validation lifetime error | CommandBuffer / Fence |
| P0 | depth / framebuffer 未重建 | framebuffer size mismatch | Depth / Framebuffer |
| P1 | Surface / ANativeWindow 已失效 | Android lifecycle 日志异常 | Surface / ANativeWindow |
| P1 | 没处理 OUT_OF_DATE / SUBOPTIMAL | acquire / present 返回异常 | Swapchain |
| P2 | descriptor 仍引用旧 offscreen image | 后处理黑屏或 crash | Descriptor / Image |

---

## 3. 快速验证路径

1. 打印 acquire / present 返回值。
2. 打印 surface changed / destroyed / created。
3. 打印 swapchain recreate 开始和结束。
4. 打印新旧 swapchain extent。
5. 检查 recreate 前是否等待相关 in-flight fence。
6. 检查所有尺寸相关资源是否重建。
7. 用 RenderDoc / AGI 抓 resize 后第一帧。

---

## 4. Vulkan 对象链路排查

```text
Surface / ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images
→ ImageViews
→ Depth / Offscreen Images
→ Framebuffer / Dynamic Rendering Attachment
→ CommandBuffer
→ Descriptor
→ Present
```

重点检查：

- 是否创建新 swapchain。
- 是否销毁旧 image view。
- 是否重建 depth image。
- 是否重建 framebuffer 或 dynamic rendering attachment。
- 是否重新录制 command buffer。
- 是否更新 descriptor。
- 是否等待旧 GPU 工作完成。

---

## 5. 高频根因

1. 只重建 swapchain，没有重建 image view。
2. 重建 image view，但 framebuffer 没重建。
3. depth image 仍是旧尺寸。
4. command buffer 没重新录制，仍引用旧 framebuffer。
5. descriptor 仍引用旧 offscreen render target。
6. 没等待 in-flight command buffer 完成就销毁旧资源。
7. Android Surface destroyed 后仍 present。
8. extent 为 0 时继续创建 swapchain。

---

## 6. 修复方案

### 最小修复

- acquire / present 返回 OUT_OF_DATE 时触发 recreate。
- recreate 前等待相关 frame fence。
- 重建 swapchain image view、depth、framebuffer、command buffer。

### 稳定修复

- 把所有尺寸相关资源归为 swapchain-dependent resources。
- 建立统一 recreate 函数。
- Surface destroyed 时暂停 render loop。
- Surface recreated 后重新创建 surface/swapchain。
- 为每个 frame resource 建立明确生命周期。

### 工程化修复

- 使用 render graph 统一管理尺寸相关资源。
- 建立 resource generation id，防止 command buffer 引用旧资源。
- 建立 Android lifecycle 状态机。

---

## 7. 回归验证

- [ ] rotation 多次不 crash。
- [ ] pause / resume 不 crash。
- [ ] resize 后画面正常。
- [ ] Validation clean。
- [ ] RenderDoc / AGI 中不再引用旧 image view。
- [ ] extent 为 0 时不会继续渲染。

---

## 8. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/10_android_platform/android_surface.md`
- `../../03_api_manual/10_android_platform/anativewindow.md`

---

## 9. 工具证据

### Validation Layer

关注：

- destroyed object
- invalid image view
- framebuffer mismatch
- command buffer references invalid object

### AGI / logcat

关注：

- surface destroyed / created
- native window invalid
- acquire / present return code
- resize extent

---

## 10. Android 分支

Android 必须额外处理：

1. Surface destroyed 时停止渲染。
2. ANativeWindow 释放后不能继续使用。
3. Surface changed 时触发 swapchain recreate。
4. pause 时处理 render thread 状态。
5. resume 后重新检查 surface 是否有效。
6. rotation 后等待新 surface 尺寸非 0。

---

## 11. 不确定时如何处理

需要补充：

- surface lifecycle 日志
- acquire / present 返回值
- swapchain recreate 代码
- command buffer 录制代码
- frame resource 管理代码
- native crash stack

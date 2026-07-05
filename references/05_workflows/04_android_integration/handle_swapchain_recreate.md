# Workflow: Handle Swapchain Recreate

## 0. 适用范围

### 适用

- Android rotation / resize。
- Window resize。
- `vkAcquireNextImageKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR`。
- `vkQueuePresentKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR` 或 `VK_SUBOPTIMAL_KHR`。
- Surface size 变化。
- 需要重建尺寸相关资源。

### 不适用

- 首次创建 swapchain。
- 非显示链路资源重建。
- 纯 offscreen compute。

---

## 1. 任务目标

建立稳定的 swapchain recreate 流程：

```text
Detect Out-of-date
→ Pause / Wait In-flight
→ Destroy Old Size-dependent Resources
→ Create New Swapchain
→ Recreate ImageViews / Depth / Offscreen / Framebuffer
→ Re-record CommandBuffer
→ Update Descriptor
→ Resume Render
```

---

## 2. 输入条件

需要确认：

- 哪些资源依赖 swapchain 尺寸。
- 是否使用 framebuffer。
- 是否使用 dynamic rendering。
- 是否有 depth image。
- 是否有 offscreen image。
- descriptor 是否引用尺寸相关 image。
- command buffer 是否需要重录。
- Android surface 是否有效。

---

## 3. 前置检查

- [ ] acquire / present 返回值有处理。
- [ ] frame resource 有 fence。
- [ ] 可以等待 in-flight work。
- [ ] 资源销毁顺序明确。
- [ ] surface extent 可查询。
- [ ] extent 为 0 时可暂停。

---

## 4. Vulkan 对象链路

```text
Surface / Window Size
→ Surface Capability
→ Swapchain
→ Swapchain Images
→ ImageViews
→ Depth / Offscreen Images
→ Framebuffer / Rendering Attachment
→ CommandBuffer
→ Descriptor
→ Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| swapchain | `VkSwapchainKHR` | present | surface/extent lifecycle | 是 |
| swapchain image view | `VkImageView` | color attachment | swapchain lifecycle | 是 |
| depth image | `VkImage` | depth attachment | swapchain extent | 是 |
| framebuffer | `VkFramebuffer` | render target | swapchain image view | 是 |
| offscreen image | `VkImage` | sampled / attachment | screen-sized pass | 通常是 |
| descriptor | `VkDescriptorSet` | sampled image | depends on image | 视情况 |

---

## 6. Pipeline / Descriptor 设计

通常 pipeline 不一定需要重建，除非：

- render pass compatibility 变化。
- color/depth format 变化。
- dynamic rendering format 变化。
- viewport/scissor 是 baked static state 且尺寸变化。
- pipeline layout / descriptor layout 变化。

Descriptor 必须更新，如果它引用：

- 旧 offscreen image view。
- 旧 depth / color attachment。
- 旧 swapchain-sized sampled image。

---

## 7. 同步与 Layout 设计

recreate 前必须确保旧资源不再被 GPU 使用：

| Producer | Resource | Barrier / Sync | Consumer |
|---|---|---|---|
| GPU in-flight work | old swapchain resources | fence wait / device idle | CPU destroy |
| CPU create new resources | new swapchain resources | initial layout transition | next frame |

不要直接销毁可能被 submitted command buffer 引用的资源。

---

## 8. 实现步骤

1. 在 acquire / present 检测 out-of-date / suboptimal。
2. 设置 recreate pending flag。
3. Android 上确认 Surface / ANativeWindow 仍有效。
4. 如果 extent 为 0，暂停 recreate。
5. 等待相关 in-flight fence，必要时 `vkDeviceWaitIdle`。
6. 销毁旧 framebuffer / image view / depth / offscreen resources。
7. 创建新 swapchain，可传 oldSwapchain。
8. 获取新 swapchain images。
9. 创建新 image views。
10. 重建 depth / offscreen image。
11. 重建 framebuffer 或 dynamic rendering attachment。
12. 更新 descriptor。
13. 重新录制 command buffer。
14. 恢复 frame loop。

---

## 9. Android 注意点

- Surface destroyed 时不要 recreate。
- Surface changed 后等尺寸有效再 recreate。
- pause 状态下不要强行 present。
- rotation 可能导致多次 changed，避免重复 recreate。
- ANativeWindow 变化可能需要重新创建 `VkSurfaceKHR`。
- logcat 必须记录 recreate 原因和新 extent。

---

## 10. 验证方式

- [ ] 横竖屏切换多次不 crash。
- [ ] resize 后画面尺寸正确。
- [ ] Validation clean。
- [ ] RenderDoc / AGI 不再看到旧 image view。
- [ ] descriptor 指向新资源。
- [ ] extent 为 0 时不会死循环或 crash。
- [ ] 多帧稳定。

---

## 11. 常见失败模式

1. 只重建 swapchain，不重建 image view。
2. depth / framebuffer 没重建。
3. command buffer 没重录。
4. descriptor 仍指向旧 offscreen image。
5. 没等待 GPU 完成就销毁旧资源。
6. Surface destroyed 时仍 recreate。
7. pipeline 依赖旧 render pass format。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/10_android_platform/android_surface.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

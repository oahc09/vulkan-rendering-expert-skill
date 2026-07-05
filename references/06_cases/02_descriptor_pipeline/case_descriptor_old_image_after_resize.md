# Case: Descriptor References Old Image After Resize

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Swapchain / Resize |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

窗口 resize、Android 横竖屏切换或 display scale 变化后，画面变黑、拉伸、闪烁，或出现 validation error 提示使用了已销毁的 image view。问题在 resize 前正常，resize 后必现或高概率出现。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android，尤其是 Android rotation。
- 使用 swapchain 作为后处理输入，或 descriptor 中引用了 swapchain image view 用于 UI / debug 显示。
- 有明确的 swapchain recreate 流程，但只重建了 swapchain 和 framebuffers。
- 多 frame-in-flight，per-frame descriptor pool 或 descriptor set。
- 可能使用 Dynamic Rendering，依赖 image view 直接作为 rendering attachment 或 sampled input。

---

## 3. 初始误判

最初容易怀疑：

```text
swapchain recreate 失败；
新 swapchain image 没有正确 acquire；
pipeline viewport 没有更新；
surface capabilities 获取错误导致 extent 不匹配；
resize 触发了 validation error 被忽略。
```

但 `vkCreateSwapchainKHR` 返回成功，新的 swapchain image 已创建，viewport 也已更新。最终发现 descriptor set 中仍保存着旧 swapchain 的 `VkImageView` handle，GPU 采样或写入时访问了无效或尺寸错误的 image。

---

## 4. 排查路径

1. 检查 resize 后 `vkCreateSwapchainKHR` 是否成功，新 image count 是否与旧 image count 一致。
2. 检查新 swapchain 的 image view 是否已重新创建。
3. 检查 descriptor set update 调用：是否仍使用旧 `VkImageView` handle。
4. 在 RenderDoc 中对比 resize 前后的 Bound Resources，确认 image view handle 是否变化。
5. 检查 descriptor pool / set 是否在 resize 时被释放并重新分配。
6. 确认 resize 后的第一次渲染是否重新执行了 `vkUpdateDescriptorSets`。
7. 检查 frame-in-flight 的 descriptor set 是否全部更新，而不仅是当前帧。

---

## 5. 关键证据

### Validation Layer

- 若旧 image view 已被销毁但 descriptor 仍引用（`[SPEC]`）：
  - `VUID-vkUpdateDescriptorSets-None-03047`：descriptor 更新的 image view 必须有效。
  - `VUID-vkCmdDraw-None-02699`：descriptor image layout 与 image 实际 layout 不匹配。
- 若旧 image view 尚未销毁但已属于旧 swapchain：
  - 可能无直接报错，但渲染结果异常。

### RenderDoc / AGI

- 观察到：
  - resize 后 Texture Viewer 中显示的 swapchain image 尺寸为旧尺寸。
  - Bound Resources 中 image view handle 与当前 swapchain image view 不一致。
  - 采样该 image view 时得到黑色或拉伸内容。
- 关键 resource：swapchain image view、descriptor set、`VkDescriptorImageInfo`。

### Log / Code

- 返回值：
  - `vkCreateSwapchainKHR` 返回 `VK_SUCCESS`。
  - `vkUpdateDescriptorSets` 若使用已销毁 image view 可能触发 validation error。
- 生命周期日志：
  - 旧 swapchain image view 在 `cleanupSwapchain()` 中被销毁。
  - 但 descriptor update 仍发生在销毁之后且未重新分配新 view。
- 关键代码：

```text
// 错误示例：resize 后没有更新 descriptor
void recreateSwapchain() {
    cleanupSwapchain();          // 销毁旧 swapchain image views
    createSwapchain();           // 创建新 swapchain 和 image views
    createFramebuffers();        // 创建 framebuffers
    // 缺少：重新分配/更新 descriptor sets
}
```

---

## 6. 根因

根因：swapchain recreate 后，descriptor set 仍引用旧 swapchain 的 image view，导致 GPU 访问了已失效或尺寸不匹配的图像资源。

---

## 7. 修复方案

### 最小修复

- 在 swapchain recreate 完成后，重新分配并更新所有引用 swapchain image view 的 descriptor set。
- 确保 `VkDescriptorImageInfo.imageView` 来自新 swapchain。
- 若 descriptor pool 已满或需要释放旧 set，在 cleanup 阶段先释放 descriptor set，再销毁旧 image view。

### 稳定修复

- 维护 swapchain-dependent resource group：swapchain、image views、framebuffers、descriptors 统一在 recreate 时重建。
- 在 resource manager 中标记“swapchain 依赖资源”，resize 时自动失效并重新创建。
- 对每帧 descriptor set 做版本管理，swapchain 版本号变化时强制重新 update。

### 工程化修复

- 使用 RenderGraph / FrameGraph 自动处理资源生命周期：resize 时重新分配依赖资源并更新所有 descriptor。
- 引入 descriptor set allocator 与缓存，按 swapchain 版本隔离 descriptor set。
- 在 CI 中增加 resize / rotation 自动化测试，验证 descriptor 引用的 image view 与新 swapchain 一致。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 Bound Resources 的 image view handle 与新 swapchain 一致。
- [ ] resize / rotation 后画面正常，无黑屏、拉伸、闪烁。
- [ ] 多 frame-in-flight 下所有 descriptor set 均已更新。
- [ ] 连续多次 resize 仍正常。
- [ ] Android pause / resume 后 descriptor 引用正确。

---

## 9. 经验抽象

Swapchain recreate 不只是重建 swapchain 本身。任何引用 swapchain image view 的资源（framebuffer、descriptor、render pass attachment）都属于 swapchain-dependent 资源链，必须在同一次 recreate 中同步更新：

```text
swapchain
→ swapchain image views
→ framebuffers
→ descriptors (sampled input / storage image)
→ pipeline dynamic state (viewport/scissor)
```

只更新其中一部分会导致静默错误。

---

## 10. 预防规则

1. 把 swapchain、image views、framebuffers、相关 descriptor set 归为同一生命周期组，recreate 时统一重建。
2. resize / rotation 后必须重新执行 `vkUpdateDescriptorSets`，禁止复用旧 swapchain 的 image view。
3. 多 frame-in-flight 下，所有 in-flight 帧的 descriptor set 都必须按新 swapchain 更新。
4. 在 descriptor update 处增加断言：image view 必须属于当前 swapchain 版本。
5. 代码审查时把 resize 处理路径作为重点检查对象，确保没有资源遗漏更新。

---

## 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`

---

## 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`

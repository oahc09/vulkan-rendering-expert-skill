# Case: Swapchain Dependent Resource Group

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / Swapchain / Resize / Resource Group |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [ENGINE] [SPEC] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 窗口 resize、Android rotation、分屏或折叠屏展开后，画面比例异常、黑边、黑屏或 crash。
- 有时 swapchain 已重建，但 depth buffer 仍是旧尺寸，导致 Validation Layer 报 `VUID-vkCmdDraw-renderPass-02684` 等错误。
- 偶发 offscreen render target 尺寸与 swapchain 不一致，后处理 pass 输出被拉伸或裁剪。
- 某些依赖 swapchain 尺寸的 MSAA resolve buffer 未重建，导致 present 时 device lost。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android，resize / rotation / 分屏场景常见。
- 使用 `VkSwapchainKHR`，surface 尺寸变化时需要 recreate swapchain。
- Swapchain image 尺寸变化会牵出一族资源：depth stencil image、MSAA color/depth resolve buffer、offscreen color image、framebuffer、command buffer 录制参数。
- 这些资源分散在不同子系统中，没有统一的管理入口。
- 部分资源按 swapchain extent 创建，但重建逻辑只处理了 swapchain image 本身。

---

## 3. 初始误判

最初容易怀疑：

```text
Swapchain recreate 逻辑本身有 bug；
Surface capabilities 获取错误；
Android lifecycle 处理不当；
Framebuffer 没重建；
Viewport / scissor 还是旧值。
```

但 swapchain 和 framebuffer 重建后问题仍存在。最终发现是 swapchain 变化触发的一整族资源（depth、offscreen、MSAA、postprocess target）没有作为 group 统一重建，导致尺寸不一致 `[ENGINE]` `[ANDROID]`。

---

## 4. 排查路径

1. 捕获 resize / rotation 前后的 surface capabilities 和 swapchain extent。
2. 检查 swapchain recreate 后，哪些资源仍使用旧 extent。
3. 列出所有按 swapchain extent 派生尺寸的资源清单。
4. 检查 depth stencil image、MSAA resolve image、offscreen color image 的重建时机。
5. 检查 framebuffers、render pass、pipeline 是否依赖这些 image 的尺寸或格式。
6. 检查 viewport / scissor / dynamic rendering 的 `renderingArea` 是否更新。
7. 检查 Android 的 `onSurfaceChanged` / `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` 是否传播到所有相关子系统。
8. 用 Validation Layer 和 RenderDoc 确认具体是哪个资源尺寸不匹配。

---

## 5. 关键证据

### Validation Layer

- `VUID-vkCmdDraw-renderPass-02684`：render area 或 framebuffer 尺寸与 image 不匹配。
- `VUID-vkCreateFramebuffer-attachmentImage-00757`：framebuffer 的 attachment 尺寸不一致。
- `VUID-vkCmdBeginRenderPass-renderArea-02881`：render area 超出 framebuffer 范围。
- `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`：swapchain 与 surface 不再兼容 `[SPEC]`。

### RenderDoc / AGI

- RenderDoc：resize 后 swapchain image 已是新尺寸，但 depth attachment 仍是旧尺寸。
- RenderDoc：offscreen pass 的 render target 尺寸与 final blit 目标尺寸不一致，导致拉伸或裁剪。
- AGI：rotation 后 `vkQueuePresentKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR` 且未处理。
- 关键 resource：swapchain images、depth stencil image、MSAA color/depth image、offscreen images、framebuffers。

### Log / Code

- 错误代码模式：

```text
void onResize(uint32_t w, uint32_t h) {
    recreateSwapchain(w, h);          // 重建 swapchain
    recreateFramebuffers();           // 重建 framebuffer
    // 漏了：depth、MSAA、offscreen 未重建
}
```

- 关键日志：

```text
Swapchain extent: 1080x1920 -> 1920x1080
Depth image extent: 1080x1920  <-- 未更新
Offscreen extent: 1080x1920    <-- 未更新
MSAA resolve extent: 1080x1920 <-- 未更新
```

---

## 6. 根因

根因：swapchain extent 变化时，只重建了 swapchain 和直接依赖它的 framebuffer，而没有把 depth、MSAA、offscreen、postprocess target 等一族尺寸耦合的资源作为 group 统一重建，导致资源尺寸不一致 `[ENGINE]`。

---

## 7. 修复方案

### 最小修复

- 在 swapchain recreate 回调中，统一列出并重建所有按 swapchain extent 派生的资源。
- 至少包含：depth stencil image、MSAA color/depth resolve image、offscreen color image、framebuffers。
- 更新 viewport、scissor、dynamic rendering 的 `renderingArea`、postprocess 的 UV 和 resolution uniform。

### 稳定修复

- 建立 `SwapchainDependentResourceGroup` 抽象：注册所有尺寸随 swapchain 变化的资源，swapchain recreate 时统一触发重建。
- 每个资源声明其尺寸计算函数（如 `extent = swapchainExtent` 或 `extent = swapchainExtent / 2`）。
- 重建顺序：swapchain → depth/MSAA/offscreen images → framebuffers → render passes / pipelines（若依赖尺寸）→ viewport / scissor / uniforms。
- 在 Android  lifecycle 中，将 `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` / `onSurfaceChanged` 统一映射为 `RecreateSwapchainDependentResources` 事件。

### 工程化修复

- 引入 resolution scale 配置：将内部渲染分辨率与 swapchain 分辨率解耦，swapchain 变化时内部分辨率按策略调整。
- 建立资源依赖图：自动检测哪些 image/buffer 的尺寸直接或间接依赖 swapchain extent，并在变化时自动重建。
- CI 中加入 resize / rotation / 分屏自动化测试，用 screenshot 对比验证比例正确。
- 运行时增加尺寸一致性断言：任何按 swapchain extent 创建的资源在 render loop 中必须与当前 swapchain extent 一致。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] 窗口 resize 后画面无黑边、无拉伸、无 crash。
- [ ] Android rotation / 分屏 / 折叠屏展开后画面正常。
- [ ] Swapchain extent 变化后，depth / MSAA / offscreen / framebuffer 尺寸一致。
- [ ] Viewport / scissor / renderingArea 已更新为新尺寸。
- [ ] Postprocess 和 UI 的 resolution uniform 已同步更新。
- [ ] 连续多次 resize / rotation 后仍稳定，无资源泄漏或 device lost。

---

## 9. 经验抽象

Swapchain extent 是渲染器的“基准分辨率”，很多资源都直接或间接从它派生。必须把它当作一个资源 group 的入口：

```text
Swapchain extent 变化
→ depth stencil image
→ MSAA color / depth resolve image
→ offscreen / postprocess render targets
→ framebuffers
→ viewport / scissor / renderingArea
→ resolution-dependent uniforms / UV
```

只重建 swapchain image 而不重建整族资源，是导致 resize/rotation 后各种异常的根本原因 `[ENGINE]` `[ANDROID]`。

---

## 10. 预防规则

1. 任何按 swapchain extent 创建的资源必须注册到 `SwapchainDependentResourceGroup`。
2. Swapchain recreate 时必须统一重建整族资源，禁止只重建 swapchain image 和 framebuffer。
3. 重建顺序必须满足依赖关系：swapchain → images → framebuffers → pipelines → viewport/uniforms。
4. Android 的 surface 变化事件必须传播到所有相关子系统，禁止局部处理。
5. 新增任何分辨率相关资源时，必须声明其尺寸来源（swapchain extent、固定值、比例值）。
6. 在 debug 构建中增加尺寸一致性断言，发现不一致立即崩溃并提示。
7. CI 必须覆盖 resize / rotation / 分屏 / 折叠屏等场景。
8. Viewport / scissor / renderingArea / resolution uniform 必须在 swapchain 重建后同步更新。

---

## 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

## 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`
- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`

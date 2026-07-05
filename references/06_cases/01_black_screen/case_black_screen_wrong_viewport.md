# Case: Black Screen Caused by Wrong Viewport or Scissor

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Viewport / Scissor / 光栅化 |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

App 正常运行，clear color 可见，但几何体完全消失或只显示极小部分。画面没有 shader 编译错误，也没有 Validation Layer 报错（除非 viewport 宽度为负且未开启相关特性）。RenderDoc 中 draw call 存在，但 rasterized pixels 为 0。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 Dynamic Viewport/Scissor（`vkCmdSetViewport` / `vkCmdSetScissor`）。
- 刚实现窗口 resize、DPI 变化、横竖屏切换或离屏渲染。
- 管线创建时未启用 `VkPipelineViewportStateCreateInfo` 的静态 viewport，而是使用 dynamic state。

---

## 3. 初始误判

最初容易怀疑：

```text
MVP 矩阵错误把模型移出视锥；
顶点数据为空或索引偏移错误；
cull mode / depth test 把像素全部剔除；
fragment shader discard 了所有片段。
```

但 RenderDoc 中顶点输出坐标在 NDC 范围内，cull 和 depth 状态正常，fragment shader 根本没有被执行。最终发现 viewport 或 scissor 的参数导致光栅化区域为空或与 render target 不重叠。

---

## 4. 排查路径

1. 检查 RenderDoc Pipeline State → Rasterizer 中 Viewport 和 Scissor 的数值。
2. 检查 `vkCmdSetViewport` 的 `x`、`y`、`width`、`height` 是否与 render target extent 一致。
3. 检查 `vkCmdSetScissor` 的 `offset` 和 `extent` 是否覆盖了有效区域。
4. 确认 `width` 和 `height` 没有写反、没有符号错误、没有因为整数除法被截断为 0。
5. 检查 resize 后是否及时更新了 viewport / scissor，而不是仍使用旧窗口尺寸。
6. 检查是否只在 begin render pass 后设置了一次 dynamic state，后续又被错误覆盖。

---

## 5. 关键证据

### Validation Layer

- 若 `width` 为负且未启用 `VkPhysicalDeviceFeatures::wideLines` 或 `negativeViewportHeight` 特性（`[SPEC]`）：
  - 可能报 `VUID-VkViewport-width-01770`：width 必须大于 0.0。
- 若 scissor 超出 framebuffer 范围：
  - 可能报 `VUID-vkCmdSetScissor-firstScissor-00593`：scissor 矩形不得超出 framebuffer 维度。
- 多数情况下 Validation 不报错，因为参数本身合法但范围恰好为零。

### RenderDoc / AGI

- 观察到：
  - Pipeline State → Viewport 面板显示 width 或 height 为 0，或 x/y 偏移到 render target 外部。
  - Scissor 矩形显示为 0×0 或与 viewport 无重叠。
  - Draw call 的 Rasterized primitives 存在，但 Pixels Written / Passed 为 0。
- 关键 pass：出问题的 graphics pass；关键 resource：dynamic viewport / scissor state。

### Log / Code

- 返回值：
  - `vkCmdSetViewport` 和 `vkCmdSetScissor` 是录制命令，无运行时返回值。
- 关键代码：

```text
// 错误示例：height 写反或为 0
VkViewport viewport{};
viewport.x = 0;
viewport.y = 0;
viewport.width = swapExtent.width;   // 正确
viewport.height = 0;                 // 错误：光栅化高度为 0
viewport.minDepth = 0.0f;
viewport.maxDepth = 1.0f;

// 或 scissor 范围错误
VkRect2D scissor{};
scissor.offset = {0, 0};
scissor.extent = {0, 0};             // 错误：裁剪区域为空
```

---

## 6. 根因

根因：viewport 或 scissor 的参数设置错误，导致光栅化后的有效像素区域为空，几何体被裁剪到 render target 之外。

---

## 7. 修复方案

### 最小修复

- 将 `vkCmdSetViewport` 的 `width` / `height` 设置为当前 render target 的 extent。
- 将 `vkCmdSetScissor` 的 `extent` 设置为与 render target 相同或至少与 viewport 重叠的非零区域。
- 若使用 OpenGL 风格坐标系，注意 Vulkan 默认 Y 向下；如需翻转需使用 `negativeViewportHeight` 并在管线中启用相关特性。

### 稳定修复

- 在每次 resize 或 render target 变化时，统一重新计算 viewport 和 scissor。
- 对 viewport / scissor 做范围校验：width > 0、height > 0、scissor extent > 0、rect 在 framebuffer 内。
- 将 viewport / scissor 更新逻辑与 swapchain recreate 绑定，避免旧尺寸残留。

### 工程化修复

- 在 RenderGraph / FrameGraph 中根据当前 render target 自动推导 viewport 和 scissor。
- 添加 debug overlay 显示当前 viewport / scissor 数值，便于快速定位异常。
- 在 CI 中增加窗口最小化 / 最大化 / 旋转测试，验证 viewport 更新正确性。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 Viewport / Scissor 覆盖整个 render target。
- [ ] Draw call 的 Pixels Written 大于 0。
- [ ] 画面正常显示几何体。
- [ ] 窗口 resize / Android 横竖屏切换后 viewport 自动更新。
- [ ] 多帧运行稳定，无闪烁或黑边。

---

## 9. 经验抽象

在 Vulkan 中，clear color 不受 viewport / scissor 限制，因此 clear 正常而几何体消失时，应优先怀疑光栅化状态而非 fragment shader 或 transform。凡是“clear 可见、draw 不见”，必须检查：

```text
viewport.x/y/width/height
scissor.offset/extent
minDepth/maxDepth
动态状态是否被覆盖
resize 后是否更新
```

---

## 10. 预防规则

1. 每次 begin render pass 后必须设置与当前 render target 匹配的 viewport 和 scissor。
2. viewport 的 width / height 必须大于 0；scissor 的 extent.width / extent.height 必须大于 0。
3. resize / rotation / surface 变化后必须同步更新 viewport / scissor。
4. 禁止在 render pass 中无意义地重复设置 dynamic state，若必须设置需确保参数正确。
5. 在 RenderDoc 中排查黑屏时，优先查看 Rasterizer 状态的 viewport 和 scissor 数值。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

## 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/02_render_pass_effects/add_fullscreen_pass.md`

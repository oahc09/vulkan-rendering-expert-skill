# Case: Black Screen Caused by Depth Test or Cull Mode

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Depth / Cull / 光栅化状态 |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

App 正常运行，clear color 可见，但几何体完全不可见。某些视角下突然出现，或改为 wireframe 后可见。RenderDoc 中 draw call 存在，顶点输出在 NDC 范围内，但 rasterized fragments 为 0 或全部 depth test fail。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 graphics pipeline，刚创建或修改了 `VkPipelineRasterizationStateCreateInfo` / `VkPipelineDepthStencilStateCreateInfo`。
- 可能刚导入新模型、切换坐标系（左手系 / 右手系）、或从 OpenGL 迁移到 Vulkan。
- 使用 depth attachment 且 clear value 已设置。

---

## 3. 初始误判

最初容易怀疑：

```text
顶点数据为空或索引越界；
MVP 矩阵把模型移出视锥；
viewport / scissor 把像素裁剪光了；
fragment shader 全部 discard；
front face 或法线方向错误但只是“模型反面”看不见。
```

但 RenderDoc 中顶点位置正确，viewport / scissor 正常，fragment shader 没有 discard。最终发现是 cull mode / front face 与 mesh winding 不匹配，或 depth compare op / depth range 与 clip-space Z 方向不匹配，导致所有图元被剔除或深度测试失败。

---

## 4. 排查路径

1. 检查 RenderDoc Pipeline State → Rasterizer 的 `cullMode` 和 `frontFace`。
2. 检查 Pipeline State → Depth & Stencil 的 `depthTestEnable`、`depthWriteEnable`、`depthCompareOp`。
3. 确认 mesh 的三角形绕向（winding order）是 CCW 还是 CW。
4. 确认投影矩阵产生的 clip-space Z 范围：OpenGL 风格 `[−1, 1]` 或 Vulkan 风格 `[0, 1]`，以及是否使用 reverse-Z。
5. 检查 depth attachment 的 clear value 是否合理（例如 `1.0` 对应 far plane）。
6. 临时将 `cullMode` 设为 `VK_CULL_MODE_NONE`，观察几何体是否出现。
7. 临时将 `depthTestEnable` 设为 `VK_FALSE`，观察几何体是否出现。

---

## 5. 关键证据

### Validation Layer

- 通常无直接报错（`[ENGINE]`），因为管线状态本身合法。
- 若 depth attachment 的 image layout 与 render pass 不一致，可能报：
  - `VUID-vkCmdBeginRenderPass-initialLayout-00899` 或相关 layout mismatch。
- 若 depth image 没有 `VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT`：
  - `VUID-VkFramebufferCreateInfo-attachments-00891`。

### RenderDoc / AGI

- 观察到：
  - Rasterizer 中 `cullMode = BACK`，`frontFace = CLOCKWISE`，但 mesh 实际为 CCW，导致全部背面剔除。
  - 或 `depthCompareOp = LESS`，但 clip-space Z 已映射为 `[0, 1]` 且 far = 0（reverse-Z），导致所有 fragment depth fail。
  - Draw call 的 Primitives culled 数量等于输入数量；Fragments passing depth test 为 0。
- 关键 resource：`VkPipelineRasterizationStateCreateInfo`、`VkPipelineDepthStencilStateCreateInfo`、depth attachment。

### Log / Code

- 关键代码：

```text
// 错误示例 1：cull mode 与 mesh winding 不匹配
VkPipelineRasterizationStateCreateInfo rs{};
rs.cullMode = VK_CULL_MODE_BACK_BIT;
rs.frontFace = VK_FRONT_FACE_CLOCKWISE; // mesh 为 CCW -> 全部被剔除

// 错误示例 2：depth compare op 与 clip-space Z 不匹配
VkPipelineDepthStencilStateCreateInfo ds{};
ds.depthTestEnable = VK_TRUE;
ds.depthCompareOp = VK_COMPARE_OP_LESS; // 若使用 reverse-Z 应为 GREATER_OR_EQUAL

// 错误示例 3：depth clear value 与 compare op 不匹配
depthClearValue = 0.0f; // 与 LESS 配合时所有新 fragment 都大于 0，全部被拒
```

---

## 6. 根因

根因：pipeline 的 cull mode / front face 与 mesh 三角形绕向不匹配，或 depth compare op / clear value / clip-space Z 范围不匹配，导致所有几何图元被背面剔除或深度测试拒绝。

---

## 7. 修复方案

### 最小修复

- 临时将 `cullMode` 设为 `VK_CULL_MODE_NONE` 验证几何体是否出现；确认后改回 `BACK` 并同步修正 `frontFace`。
- 根据 mesh winding 设置正确的 `frontFace`：CCW 用 `VK_FRONT_FACE_COUNTER_CLOCKWISE`，CW 用 `VK_FRONT_FACE_CLOCKWISE`。
- 根据投影矩阵和 depth convention 设置 `depthCompareOp`：标准 Z 用 `LESS` 或 `LESS_OR_EQUAL`；reverse-Z 用 `GREATER` 或 `GREATER_OR_EQUAL`。
- 确保 depth clear value 与 compare op 一致（标准 far = 1.0；reverse-Z far = 0.0）。

### 稳定修复

- 在 mesh import 阶段记录并统一 winding order，导出时翻转以匹配引擎约定。
- 为材质 / pipeline 建立 depth mode 枚举（Standard / Reverse / Disabled），集中管理 compare op 和 clear value。
- 在 pipeline 创建时断言 `cullMode` / `frontFace` 与 mesh 元数据一致。

### 工程化修复

- 引入 shader / pipeline manifest，明确声明 coordinate system、winding、depth convention。
- 在 CI 中增加回归测试：渲染简单 cube 并比较像素值，检测 cull / depth 配置错误。
- 提供运行时 debug 开关一键关闭 cull 和 depth test，用于快速定位可见性问题。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc 中 draw call 的 Fragments passing depth test 大于 0。
- [ ] 关闭 cull 后几何体可见；开启正确 cull 后仍可见且没有背面穿透。
- [ ] 不同视角、不同模型下渲染正常。
- [ ] reverse-Z（若使用）下 far/near 深度精度正常。
- [ ] 多帧运行稳定，无闪烁或部分缺失。

---

## 9. 经验抽象

“clear 可见、模型不见”时，若顶点位置和 viewport 都正确，接下来应优先检查光栅化剔除和深度测试：

```text
mesh winding  vs  frontFace
clip-space Z range  vs  depthCompareOp
depth clear value  vs  compare op
```

不要先改 shader。先把 cull 和 depth test 关闭，确认几何体能出现，再逐步恢复并修正状态。

---

## 10. 预防规则

1. 导入模型时必须记录并标准化三角形绕向，并在 pipeline 中匹配 `frontFace`。
2. 引擎必须统一 clip-space Z 约定（标准或 reverse-Z），并同步设置 `depthCompareOp` 与 clear value。
3. 新增 graphics pipeline 时必须显式声明 `cullMode` 和 `frontFace`，禁止依赖默认值。
4. 从 OpenGL 迁移到 Vulkan 时，必须检查 Z 范围和 front face 语义差异。
5. 提供一键禁用 cull / depth test 的 debug 工具，用于快速排除可见性问题。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

## 13. 关联 Workflow

- `../../05_workflows/02_render_pass_effects/add_depth_pass.md`
- `../../05_workflows/02_render_pass_effects/add_fullscreen_pass.md`
- `../../05_workflows/06_pipeline_descriptor/add_graphics_pipeline.md`

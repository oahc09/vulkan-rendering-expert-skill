# Debug Playbook: Depth Test Wrong

## 0. 适用范围

### 适用

- 画面出现全黑、远处物体消失、近处物体被远处遮挡、物体穿插闪烁。
- 透明或不透明物体的前后关系错误。
- 特定视角下 depth 相关渲染结果异常。
- 怀疑 depth attachment、depth test state 或 depth write 配置错误。

### 不适用

- 完全黑屏且与 depth 无关（优先排查 black_screen.md）。
- 纹理或颜色输出错误但 depth 关系正确。
- 物理碰撞或裁剪导致的可见性问题。

---

## 1. 现象

- 屏幕全黑或只显示 clear color，模型不可见。
- 远处物体覆盖近处物体，透视关系反转。
- 物体重叠处出现 Z-fighting 闪烁。
- 透明物体在不透明物体之后绘制但显示在不透明物体之前。
- Shadow map 中物体消失或阴影位置错误。
- 某些像素明明应该被遮挡却仍然可见。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Depth test 比较函数错误 | 远近关系反转；`VK_COMPARE_OP_GREATER` 与 `VK_COMPARE_OP_LESS` 使用不当 | Pipeline DepthStencilState |
| P0 | Depth write 未开启 | 第一帧正确，后续帧或重叠物体处出现错乱 | Pipeline DepthStencilState |
| P0 | Depth attachment 未正确清除或加载 | 首帧或切换后 depth buffer 包含旧值 | Render Pass / Attachment |
| P1 | Depth attachment 格式不支持或精度不足 | 远距离处出现 Z-fighting | Image Format |
| P1 | Viewport / depth range 设置错误 | 所有物体被裁剪到近/远平面之外 | Viewport |
| P1 | Depth bias 设置不当 | Shadow acne 或 peter-panning | Pipeline DepthStencilState |
| P2 | Scissor 或 viewport 覆盖了 depth 区域 | 部分区域 depth 不更新 | Scissor / Viewport |

---

## 3. 快速验证路径

1. **强制关闭 depth test 和 depth write**：若画面可见但前后关系错乱，说明 depth 配置是根因。`[TOOL]`
2. **把 fragment shader 输出固定颜色**：若模型轮廓可见但黑屏，说明 depth 把模型都剔除了。`[TOOL]`
3. **检查 depth attachment 清除值**：确认 load op 为 `CLEAR` 且 clear depth 为 1.0（对 `LESS` 比较）。`[TOOL]`
4. **RenderDoc 查看 depth buffer 内容**：确认 depth 值范围、清除结果和写入状态。`[TOOL]`
5. **切换 compare op**：临时改为 `VK_COMPARE_OP_ALWAYS` 或 `VK_COMPARE_OP_LESS`，观察变化。`[TOOL]`
6. **检查 projection matrix**：确认 handedness 和 depth range 与 Vulkan 的 [0,1] Z 范围一致。`[ENGINE]`

---

## 4. Vulkan 对象链路排查

```text
Render Pass / Subpass
→ Depth Attachment (Image / ImageView)
→ VkPipelineDepthStencilStateCreateInfo
→ Viewport / Scissor
→ Command Buffer Draw
→ Present
```

逐项检查：

- Depth attachment format 是否支持 depth stencil，如 `VK_FORMAT_D32_SFLOAT`、`VK_FORMAT_D24_UNORM_S8_UINT`。`[SPEC]`
- Render pass 中 depth attachment 的 load op 是 `CLEAR` / `LOAD` / `DONT_CARE` 中的哪一种。`[SPEC]`
- Pipeline 中 `depthTestEnable`、`depthWriteEnable`、`depthCompareOp` 是否与预期一致。`[SPEC]`
- Pipeline 中 `depthBoundsTestEnable` 是否启用并设置了错误范围。`[SPEC]`
- Viewport 的 `minDepth` / `maxDepth` 是否为 [0.0, 1.0] 或是否被动态修改。`[SPEC]`
- 投影矩阵是否将 Z 映射到 [0,1]；OpenGL 风格的 [-1,1] 投影在 Vulkan 中需调整。`[ENGINE]`
- 多 pass 渲染时后续 pass 是否错误地依赖了未清除的 depth buffer。`[ENGINE]`

---

## 5. 高频根因

1. `depthCompareOp` 误设为 `GREATER`，但 depth buffer 清除为 1.0 且未开启反向 Z。`[ENGINE]`
2. `depthWriteEnable = VK_FALSE` 被默认设置或复制了错误 pipeline 状态。`[ENGINE]`
3. Depth attachment load op 为 `LOAD` 或 `DONT_CARE`，导致残留上一帧或随机值。`[ENGINE]`
4. 投影矩阵使用 OpenGL 约定，depth 范围 [-1,1]，而 Vulkan 使用 [0,1]，导致近裁剪面异常。`[ENGINE]`
5. Shadow map pass 未正确设置 depth bias，产生 shadow acne 或 peter-panning。`[ENGINE]`
6. 透明 pass 错误开启 depth write，破坏后续透明物体的深度比较。`[ENGINE]`
7. 多采样或 resolve 后 depth buffer 内容未保留，后续 pass 读取错误。`[SPEC]`

---

## 6. 修复方案

### 最小修复

- 把 `depthCompareOp` 改为与投影和清除值匹配的比较函数；标准前向渲染使用 `VK_COMPARE_OP_LESS` 并清除 depth 为 1.0。`[SPEC]`
- 对需要写入 depth 的 pass 开启 `depthWriteEnable = VK_TRUE`。`[SPEC]`
- 把 depth attachment 的 load op 设为 `VK_ATTACHMENT_LOAD_OP_CLEAR`，并在 `VkRenderPassBeginInfo::pClearValues` 中提供深度清除值。`[SPEC]`
- 把投影矩阵调整为 Vulkan 的 [0,1] depth range，或启用 `VK_EXT_depth_clip_control` 使用 [-1,1]。`[SPEC]`

### 稳定修复

- 建立 pipeline state 描述系统，集中管理 depth test / write / compare op，避免硬编码错误。`[ENGINE]`
- 对 shadow map 等敏感 pass 使用 slope-scaled depth bias 并做 bias 参数调优。`[ENGINE]`
- 明确区分 opaque pass（depth write on）和 transparent pass（depth test on / depth write off）。`[ENGINE]`
- 对 reverse-Z 方案统一使用 `VK_COMPARE_OP_GREATER` / `GREATER_OR_EQUAL` 并清除 depth 为 0.0，提高远距精度。`[ENGINE]`（适用条件：浮点 depth buffer 可用；需全项目统一 convention。）

### 工程化修复

- CI 中增加 depth buffer 可视化测试，自动检测全黑 / 反转 / Z-fighting。`[TOOL]`
- 建立 render pass 模板，强制要求每个 subpass 声明 depth load/store op 和 compare op。`[ENGINE]`
- 对复杂场景增加 depth 精度分析工具，远距离自动切换更高精度 depth format 或 reverse-Z。`[ENGINE]`
- 在 debug 视图叠加 depth buffer 可视化，便于快速定位异常。`[TOOL]`

---

## 7. 回归验证

- [ ] 正常视角下物体前后关系正确。
- [ ] 无 Z-fighting 闪烁。
- [ ] 透明物体与不透明物体层级正确。
- [ ] Shadow map 无 acne / peter-panning。
- [ ] 切换 camera / resize / rotation 后 depth 行为一致。
- [ ] Validation Layer 无 depth / attachment 相关错误。
- [ ] RenderDoc 中 depth buffer 值范围符合预期。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 9. 工具证据

### Validation Layer

- 关注 `VUID-VkGraphicsPipelineCreateInfo-rasterizerDiscardEnable-00751` 等 depth stencil state 相关 VUID。`[TOOL]`
- 关注 render pass 中 attachment description 与 image view format 不匹配的警告。`[TOOL]`
- 关注 depth attachment image layout 是否从 `UNDEFINED` 正确过渡到 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`。`[TOOL]`

### RenderDoc

- 查看 texture / resource 面板中的 depth buffer 内容，确认清除后是否为统一值。`[TOOL]`
- 查看 pipeline state 中 `Depth Test`、`Depth Write`、`Depth Function` 是否预期。`[TOOL]`
- 使用 RenderDoc 的 mesh 或 pixel history 工具查看特定像素的深度测试过程。`[TOOL]`
- 查看 depth attachment 的 load / store op 和 clear value。`[TOOL]`

### AGI / Android

- 查看 frame 中 depth attachment 的内容和格式。`[TOOL]`
- 查看 pipeline state 中 depth test / write / compare op 配置。`[TOOL]`
- 查看 GPU counter 中 early-Z / late-Z 相关指标是否异常。`[TOOL]`

### logcat

- 搜索 `Vulkan`、`Depth`、`Attachment` 等关键字。`[ANDROID]`
- 检查是否因 depth format 不支持导致 fallback 或错误。`[ANDROID]`

---

## 10. Android 分支

Android 上 depth test 问题常与 Surface / Swapchain 尺寸变化和 tile-based GPU 相关，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且尺寸与 swapchain / depth attachment 一致；rotation 后 depth attachment 必须按新 extent 重建。`[ANDROID]`
2. **Swapchain 重建完整性**：横竖屏切换后 depth image 和 framebuffer 是否跟随 swapchain image 重建，旧 depth image view 是否仍被 descriptor 引用。`[SPEC]`
3. **Tile-based GPU 的 depth 处理**：Adreno / Mali 在 tile 内处理 depth，某些 load/store op 组合可能导致 depth 内容在 tile 间不一致；优先使用 `CLEAR` 或 `LOAD` 明确声明需求。`[ANDROID]`
4. **内存带宽限制**：移动设备上高精度 depth format（如 D32）带宽更高，可根据场景切换为 D16 或 D24S8。`[ANDROID]`（适用条件：对精度要求不高的近景场景。）
5. **后台恢复**：pause / resume 后确保 depth attachment 被正确清除，不会残留旧帧数据。`[ENGINE]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - RenderDoc capture 中 depth buffer 可视化和 pipeline state 截图。
   - Render pass 中 depth attachment description、load/store op、clear value。
   - Pipeline 中 `depthTestEnable`、`depthWriteEnable`、`depthCompareOp` 的值。
   - Projection matrix 及 depth range 设置。
   - Viewport 的 `minDepth` / `maxDepth`。
   - 设备型号、GPU、Android 版本。
3. 给出最小验证路径：临时 compare op `ALWAYS` → 检查 depth clear → 检查 depth write → 检查投影矩阵。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 depth stencil state、render pass attachment、viewport depth range 规范。
   - `[TOOL]` 若 RenderDoc / Validation Layer 已给出明确证据。
   - `[ENGINE]` 若基于 reverse-Z、shadow bias、pass 划分等工程经验推断。
   - `[HEUR]` 若尚未拿到工具数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 mobile GPU tile 架构或 Surface 生命周期。

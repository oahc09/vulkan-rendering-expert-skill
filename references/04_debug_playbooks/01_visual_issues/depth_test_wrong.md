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

## 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | Validation Layer | 有 depth / attachment 相关 VUID → §5 对应根因（§9 关注项） | clean → 检查 2 | — |
| 2 | RenderDoc：depthCompareOp vs clip-space Z 范围 | 比较方向与实际映射/clear不符，或负一到一 clip-Z 未配置对应 depthClipControl → §5-1 / §5-4 | 一致 → 检查 3 | 只降低当前捕获draw范围的比较函数/映射嫌疑，仍核对动态覆盖与实际输出 |
| 3 | RenderDoc：clear value / load op vs compare op | clear与比较方向不符，或LOAD读取的内容/依赖未建立（合法LOAD不必然错误） → §5-1 / §5-3 | 匹配 → 检查 4 | 只降低当前attachment范围的清除/加载嫌疑，不外推其他帧/代际 |
| 4 | RenderDoc：depth write 与 buffer 内容 | 全为clear → 检查write/test使能、覆盖、裁剪、discard、比较是否全部拒绝；不能直接归因write关闭 | 有写入 → 检查 5 | 有写入只证明该观察范围有写入，不能排除其他draw/像素状态错误 |
| 5 | reverse-Z 判定 | 是 reverse-Z 但 clear / compare / 投影约定不统一 → §6 Structural Fix 的 reverse-Z 统一约定；shadow 场景 → §5-5 bias | 非 reverse-Z 且以上均正常 → §11 不确定处理 | — |

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
- 检查 clip depth、viewport映射和启用特性：默认 clip-Z 为[0,w]，显式 depthClipControl 可选择[-w,w]，需支持/启用并配置negativeOneToOne。`[ENGINE]`
- 多 pass 渲染时后续 pass 是否错误地依赖了未清除的 depth buffer。`[ENGINE]`

---

## 5. 高频根因

1. `depthCompareOp` 误设为 `GREATER`，但 depth buffer 清除为 1.0 且未开启反向 Z。`[ENGINE]`
2. `depthWriteEnable = VK_FALSE` 被默认设置或复制了错误 pipeline 状态。`[ENGINE]`
3. LOAD 未有有效保存内容/依赖，或需要初始深度却使用 DONT_CARE；正确 LOAD（例如 prepass 后）本身完全合法。`[ENGINE]`
4. 投影仍用负一到一clip约定，但没有启用并配置depthClipControl对应路径，导致默认零到一clip下近裁剪异常。`[ENGINE]`
5. Shadow map pass 未正确设置 depth bias，产生 shadow acne 或 peter-panning。`[ENGINE]`
6. 透明 pass 错误开启 depth write，破坏后续透明物体的深度比较。`[ENGINE]`
7. 多采样或 resolve 后 depth buffer 内容未保留，后续 pass 读取错误。`[SPEC]`

---

## 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- 暂时关闭 depth test 先恢复画面输出（会引起绘制顺序错误；仅用于验证 depth 链路是否为问题源头，交付前必须恢复）。`[HEUR]`

### Minimal Fix（针对根因的最小修复）

- 把 `depthCompareOp` 改为与投影和清除值匹配的比较函数；常见正Z前向渲染选择 LESS并clear=1，反Z选择GREATER并clear=0，这是依实际映射选择的工程合同，不是唯一SPEC配置。`[ENGINE]`
- 对需要写入 depth 的 pass 开启 `depthWriteEnable = VK_TRUE`。`[SPEC]`
- 若不需要保留旧深度，可选择CLEAR并提供清除值；传统路径在pClearValues，dynamic rendering在对应attachment.clearValue。需要prepass深度时保留正确LOAD，不能盲目清除。`[SPEC]`
- 把投影矩阵调整为 Vulkan 的 [0,1] depth range，或启用 `VK_EXT_depth_clip_control` 使用 [-1,1]。`[SPEC]`

### Structural Fix（结构性 / 防复发修复）

- 建立 pipeline state 描述系统，集中管理 depth test / write / compare op，避免硬编码错误。`[ENGINE]`
- 对 shadow map 等敏感 pass 使用 slope-scaled depth bias 并做 bias 参数调优。`[ENGINE]`
- 明确区分 opaque pass（depth write on）和 transparent pass（depth test on / depth write off）。`[ENGINE]`
- 对 reverse-Z 方案统一使用 `VK_COMPARE_OP_GREATER` / `GREATER_OR_EQUAL` 并清除 depth 为 0.0，提高远距精度。`[ENGINE]`（适用条件：浮点 depth buffer 可用；需全项目统一 convention。）
- CI 中增加 depth buffer 可视化测试，自动检测全黑 / 反转 / Z-fighting。`[TOOL]`
- 建立 render pass 模板，分别记录attachment的load/store合同、subpass引用及pipeline/动态depth compare状态，不把这些状态都当成subpass字段。`[ENGINE]`
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

- 按实际冻结规范与路径检查 depth/stencil state 条件，例如1.4.309传统路径09028、dynamic路径09033及depthBounds实际启用00598；不要把旧版00751泛套到所有路径。`[TOOL]`
- 关注 render pass 中 attachment description 与 image view format 不匹配的警告。`[TOOL]`
- 关注实际 depth attachment layout 与声明及访问相符，复用时不能伪称一直从UNDEFINED且免除旧访问依赖。`[TOOL]`

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
3. **Tile-based GPU 的 depth 处理**：按实际保留需求使用CLEAR/LOAD/store及同步；tile架构不允许合法程序凭空产生跨tile不一致，先排查未定义内容和依赖，不用厂商品牌代替证据。`[ANDROID]`
4. **内存带宽限制**：移动设备上depth format 的实际带宽受压缩、tile驻留、store和实现影响，不由位宽单独决定，可根据场景切换为 D16 或 D24S8。`[ANDROID]`（适用条件：对精度要求不高的近景场景。）
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

深度比较使用 incoming fragment depth 与 stored depth；开启 depthWrite 不能单独保证写入，还需 depthTest 开启并通过，以及实际覆盖/其他测试条件。关闭 depthTest 的合法场景可能完全没有诊断，却改变遮挡语义。验证时保留 draw 顺序、近远值和区域输出，不能把 Validation clean 当作遮挡正确。

可执行的限定对照见 [depth遮挡跨功能链](../../05_workflows/02_render_pass_effects/add_depth_pass.md#delivery19-depth-occlusion-chain)：合法关闭depthTest的真实输出失败与非法format匹配拒绝是两种不同证据，不用“无VUID”替代视觉正确性。

# Cases: Black Screen

> 合并自 4 个原 case 文件。关键词: black-screen, image-layout, viewport, depth, cull, submit

---

## Case: Black Screen Caused by Depth Test or Cull Mode

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Depth / Cull / 光栅化状态 |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

App 正常运行，clear color 可见，但几何体完全不可见。某些视角下突然出现，或改为 wireframe 后可见。RenderDoc 中 draw call 存在，顶点输出在 NDC 范围内，但 rasterized fragments 为 0 或全部 depth test fail。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 graphics pipeline，刚创建或修改了 `VkPipelineRasterizationStateCreateInfo` / `VkPipelineDepthStencilStateCreateInfo`。
- 可能刚导入新模型、切换坐标系（左手系 / 右手系）、或从 OpenGL 迁移到 Vulkan。
- 使用 depth attachment 且 clear value 已设置。

---

### 3. 初始误判

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

### 4. 排查路径

1. 检查 RenderDoc Pipeline State → Rasterizer 的 `cullMode` 和 `frontFace`。
2. 检查 Pipeline State → Depth & Stencil 的 `depthTestEnable`、`depthWriteEnable`、`depthCompareOp`。
3. 确认 mesh 的三角形绕向（winding order）是 CCW 还是 CW。
4. 确认投影矩阵产生的 clip-space Z 范围：OpenGL 风格 `[−1, 1]` 或 Vulkan 风格 `[0, 1]`，以及是否使用 reverse-Z。
5. 检查 depth attachment 的 clear value 是否合理（例如 `1.0` 对应 far plane）。
6. 临时将 `cullMode` 设为 `VK_CULL_MODE_NONE`，观察几何体是否出现。
7. 临时将 `depthTestEnable` 设为 `VK_FALSE`，观察几何体是否出现。

---

### 5. 关键证据

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

### 6. 根因

根因：pipeline 的 cull mode / front face 与 mesh 三角形绕向不匹配，或 depth compare op / clear value / clip-space Z 范围不匹配，导致所有几何图元被背面剔除或深度测试拒绝。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc 中 draw call 的 Fragments passing depth test 大于 0。
- [ ] 关闭 cull 后几何体可见；开启正确 cull 后仍可见且没有背面穿透。
- [ ] 不同视角、不同模型下渲染正常。
- [ ] reverse-Z（若使用）下 far/near 深度精度正常。
- [ ] 多帧运行稳定，无闪烁或部分缺失。

---

### 9. 经验抽象

“clear 可见、模型不见”时，若顶点位置和 viewport 都正确，接下来应优先检查光栅化剔除和深度测试：

```text
mesh winding  vs  frontFace
clip-space Z range  vs  depthCompareOp
depth clear value  vs  compare op
```

不要先改 shader。先把 cull 和 depth test 关闭，确认几何体能出现，再逐步恢复并修正状态。

---

### 10. 预防规则

1. 导入模型时必须记录并标准化三角形绕向，并在 pipeline 中匹配 `frontFace`。
2. 引擎必须统一 clip-space Z 约定（标准或 reverse-Z），并同步设置 `depthCompareOp` 与 clear value。
3. 新增 graphics pipeline 时必须显式声明 `cullMode` 和 `frontFace`，禁止依赖默认值。
4. 从 OpenGL 迁移到 Vulkan 时，必须检查 Z 范围和 front face 语义差异。
5. 提供一键禁用 cull / depth test 的 debug 工具，用于快速排除可见性问题。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

### 13. 关联 Workflow

- `../../05_workflows/02_render_pass_effects/add_depth_pass.md`
- `../../05_workflows/02_render_pass_effects/add_fullscreen_pass.md`
- `../../05_workflows/06_pipeline_descriptor/add_graphics_pipeline.md`


---

## Case: Black Screen Caused by Missing Image Layout Transition

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Image Layout / 后处理 |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

App 正常运行，无 crash。  
clear color 可见，但新增 fullscreen 后处理 pass 后画面变黑。  
RenderDoc 中可以看到 draw call，pipeline 也绑定成功，但 fragment shader 采样 input texture 后输出为黑色。

---

### 2. 初始上下文

- 平台：Android / Desktop 均可能发生。
- 使用 Vulkan graphics pipeline。
- 前一个 pass 输出到 offscreen color image。
- 后一个 pass 通过 combined image sampler 采样该 offscreen image。
- 使用多 pass 后处理链路。
- 可能使用 RenderPass 或 Dynamic Rendering。

---

### 3. 初始误判

最初容易怀疑：

```text
fragment shader 写错；
descriptor 没绑定；
sampler 创建错误；
纹理内容为空。
```

但 RenderDoc 中前一个 pass 的 offscreen image 实际有内容，descriptor 也绑定到了正确 image view。  
后续排查发现是 pass 间缺少 layout transition。

---

### 4. 排查路径

1. 检查 render loop，确认 acquire / submit / present 正常。
2. 检查 clear color，确认 swapchain 输出正常。
3. 用 RenderDoc 查看前一个 pass 输出，确认 offscreen image 有内容。
4. 查看 fullscreen pass 的 bound resource，确认 descriptor 指向该 image。
5. 检查 image 使用链路：
   ```text
   Color Attachment Write
   → Fragment Shader Sampled Read
   ```
6. 检查 barrier，发现没有从 `COLOR_ATTACHMENT_OPTIMAL` transition 到 `SHADER_READ_ONLY_OPTIMAL`。
7. 检查 descriptor imageLayout，发现填写为 shader read，但实际 image 状态仍停留在 color attachment。

---

### 5. 关键证据

### Validation Layer

可能出现：

- image layout mismatch
- descriptor imageLayout 与实际 layout 不匹配
- synchronization hazard

### RenderDoc / AGI

观察到：

- producer pass 的 render target 有正确内容。
- consumer pass 的 descriptor 绑定了该 image view。
- consumer pass 采样结果异常。
- pass 之间缺少合理的 image memory barrier。

### Log / Code

关键代码：

- offscreen image usage 有 `COLOR_ATTACHMENT` 和 `SAMPLED`。
- command buffer 中缺少 color write → shader read barrier。

---

### 6. 根因

根因：前一个 pass 以 color attachment 方式写入 offscreen image 后，没有通过 image memory barrier 将其转换为 fragment shader sampled read 所需状态，导致后续 fullscreen pass 采样到无效内容。

---

### 7. 修复方案

### 最小修复

在 producer pass 结束后、consumer pass 开始前插入 image memory barrier：

```text
srcStage  = COLOR_ATTACHMENT_OUTPUT
srcAccess = COLOR_ATTACHMENT_WRITE
oldLayout = COLOR_ATTACHMENT_OPTIMAL

dstStage  = FRAGMENT_SHADER
dstAccess = SHADER_SAMPLED_READ
newLayout = SHADER_READ_ONLY_OPTIMAL
```

### 稳定修复

- 每个 pass 显式声明 input / output layout。
- 每个 image 维护当前 layout。
- descriptor imageLayout 必须与实际 consumer layout 一致。

### 工程化修复

- 建立 RenderGraph。
- 由 RenderGraph 根据 producer / consumer 自动插入 barrier。
- 对每个 pass 的 resource state 做 debug assertion。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc 中 producer pass 输出正常。
- [ ] Consumer pass 能看到 input texture。
- [ ] Fullscreen pass 输出正常。
- [ ] 多帧运行稳定。
- [ ] resize 后仍能正确 transition。

---

### 9. 经验抽象

凡是 image 被跨 pass 使用，都必须同时检查：

```text
usage
layout
producer stage/access
consumer stage/access
descriptor imageLayout
barrier subresource range
```

不要只检查 image 创建和 descriptor 更新。

---

### 10. 预防规则

1. 每个 pass 必须声明资源读写意图。
2. 每个 image 必须有状态跟踪。
3. Descriptor imageLayout 不能和实际 layout 脱节。
4. 新增后处理 pass 时必须设计 input/output layout。
5. RenderDoc 中必须验证 pass 输入和输出。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/05_descriptor/sampled_image_descriptor.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/02_render_pass_effects/add_fullscreen_pass.md`
- `../../05_workflows/02_render_pass_effects/add_offscreen_render_pass.md`


---

## Case: Black Screen Caused by Missing Queue Submit

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Command Buffer / Queue Submit |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

App 正常运行，无 crash，但画面全黑或一直显示上一帧内容。
RenderDoc 中可以看到 command buffer 已被录制，也能看到 render pass 和 draw call，但屏幕没有任何新输出；Validation Layer 通常不报错，或只在呈现阶段报出与 swapchain image 相关的警告。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 Vulkan graphics pipeline，已创建 command buffer 并录制了 render pass。
- 多 frame-in-flight 结构，每帧复用 command buffer 和 fence。
- 可能使用 Dynamic Rendering 或传统 RenderPass。
- 刚修改过 frame loop、渲染线程同步或 swapchain 呈现逻辑。

---

### 3. 初始误判

最初容易怀疑：

```text
fragment shader 输出错误；
clear color 被覆盖；
image layout transition 缺失；
swapchain image 没有正确 acquire；
GPU 挂起或驱动 bug。
```

但 RenderDoc 中 draw call 已录制、pipeline 状态正常，且 Validation Layer 对 shader / layout / barrier 保持 silent。最终发现 command buffer 录制完成后并没有被提交到 queue，或提交后没有等待 fence，也没有调用 present。

---

### 4. 排查路径

1. 在 render loop 中确认 `vkAcquireNextImageKHR` 是否成功返回有效 image index。
2. 检查 command buffer 录制起点到终点之间的 draw / end / 提交调用链。
3. 在 `vkEndCommandBuffer` 后确认是否调用了 `vkQueueSubmit`。
4. 检查 submit 的 `pSignalSemaphores` 和 present 的 `pWaitSemaphores` 是否配对。
5. 检查 fence 是否被正确 wait，以及 wait 返回是否被忽略。
6. 检查 `vkQueuePresentKHR` 是否在 render 线程主循环中被意外注释或提前 return。
7. 沿 `acquire → record → submit → wait → present` 链路定位缺失环节。

---

### 5. 关键证据

### Validation Layer

- 通常无直接报错（`[SPEC]`），因为录制 command buffer 本身合法。
- 若仍尝试 present 未提交渲染的 image，可能触发：
  - `VUID-vkQueuePresentKHR-pSwapchains-01283`：`pImageIndices` 对应的 image 没有 semaphore 信号保证完成。
  - `VUID-vkAcquireNextImageKHR-swapchain-01802`：未在合理时间内释放 swapchain image。
- 若 fence 未等待就复用 command buffer，后续帧可能报 command buffer 生命周期错误。

### RenderDoc / AGI

- 观察到：
  - Capture 中显示了 command buffer 的内容，包括 render pass 和 draw call。
  - 但 Event Browser 中没有 Queue Submit 节点，或 Submit 后没有 Present 调用。
  - Texture Viewer 中 swapchain image 保持为初始 acquire 状态或上一帧内容。
- 关键 resource：command buffer、queue submit info、fence、swapchain semaphore。

### Log / Code

- 返回值：
  - `vkQueueSubmit` 返回 `VK_SUCCESS`，但函数从未被调用。
  - `vkQueuePresentKHR` 返回 `VK_SUCCESS`，但参数中 wait semaphore 数量为零或信号从未被发出。
- 关键代码：

```text
// 录制完成但缺少以下任一调用：
vkQueueSubmit(graphicsQueue, 1, &submitInfo, frameFence);
vkWaitForFences(device, 1, &frameFence, VK_TRUE, timeout);
vkQueuePresentKHR(graphicsQueue, &presentInfo);
```

---

### 6. 根因

根因：command buffer 录制完成后，没有通过 `vkQueueSubmit` 提交到 GPU，或提交后没有等待 fence、没有调用 present，导致 GPU 从未执行该帧的渲染命令。

---

### 7. 修复方案

### 最小修复

- 在 `vkEndCommandBuffer` 后显式调用 `vkQueueSubmit`，并传入该帧对应的 fence。
- 在复用 command buffer 或交换到下一帧之前，先 `vkWaitForFences` 等待 fence signaled。
- 在 submit 之后调用 `vkQueuePresentKHR`，并确保 present wait semaphores 与 submit signal semaphores 一致。

### 稳定修复

- 在 frame loop 中建立 `acquire → record → submit → wait → present` 的显式状态断言。
- 每帧维护一个 FrameState 结构，记录是否已 submit、是否已 present；若某个分支提前 return，必须清理状态。
- 对 `vkQueueSubmit` 和 `vkQueuePresentKHR` 的返回值做检查，遇到 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 时触发 swapchain recreate。

### 工程化修复

- 封装 FrameLoop 类，把 acquire、record、submit、present 封装为不可跳过的固定阶段。
- 引入 Tracy / custom GPU profiler marker，确保每个 frame 都能追踪到 submit / present 事件。
- 在 CI 中增加 smoke test：运行 N 帧后检查 fence 被 signal 的次数是否等于 frame 数。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中能看到 Queue Submit 和 Present 调用。
- [ ] Texture Viewer 中 swapchain image 内容每帧更新。
- [ ] 多帧运行稳定，无卡顿或撕裂。
- [ ] resize / pause / resume / rotation 后仍能正常 submit / present。
- [ ] 多 frame-in-flight 下 fence 等待无超时。

---

### 9. 经验抽象

录制 command buffer 不等于执行。必须验证整条链路：

```text
acquire image
→ record commands
→ submit to queue with fence
→ wait fence before reuse
→ present with correct wait semaphore
```

任何一环缺失都会表现为“逻辑正确但屏幕无输出”。排查时应优先检查调用链是否完整，而不是深入 shader 或 barrier。

---

### 10. 预防规则

1. 每帧必须显式调用 `vkQueueSubmit` 与 `vkQueuePresentKHR`，禁止在分支中静默 return。
2. 每个 submit 必须关联一个 fence，并在复用资源前等待其 signaled。
3. present 的 wait semaphores 必须与 submit 的 signal semaphores 一一对应。
4. frame loop 中应添加断言：submit 后必须 present，fence wait 成功后才能 reset command buffer。
5. 代码审查时重点检查 render loop 的异常分支，确保不会跳过 submit / present。

---

### 11. 关联 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/pause_resume_render_thread.md`


---

## Case: Black Screen Caused by Wrong Viewport or Scissor

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Viewport / Scissor / 光栅化 |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

App 正常运行，clear color 可见，但几何体完全消失或只显示极小部分。画面没有 shader 编译错误，也没有 Validation Layer 报错（除非 viewport 宽度为负且未开启相关特性）。RenderDoc 中 draw call 存在，但 rasterized pixels 为 0。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 Dynamic Viewport/Scissor（`vkCmdSetViewport` / `vkCmdSetScissor`）。
- 刚实现窗口 resize、DPI 变化、横竖屏切换或离屏渲染。
- 管线创建时未启用 `VkPipelineViewportStateCreateInfo` 的静态 viewport，而是使用 dynamic state。

---

### 3. 初始误判

最初容易怀疑：

```text
MVP 矩阵错误把模型移出视锥；
顶点数据为空或索引偏移错误；
cull mode / depth test 把像素全部剔除；
fragment shader discard 了所有片段。
```

但 RenderDoc 中顶点输出坐标在 NDC 范围内，cull 和 depth 状态正常，fragment shader 根本没有被执行。最终发现 viewport 或 scissor 的参数导致光栅化区域为空或与 render target 不重叠。

---

### 4. 排查路径

1. 检查 RenderDoc Pipeline State → Rasterizer 中 Viewport 和 Scissor 的数值。
2. 检查 `vkCmdSetViewport` 的 `x`、`y`、`width`、`height` 是否与 render target extent 一致。
3. 检查 `vkCmdSetScissor` 的 `offset` 和 `extent` 是否覆盖了有效区域。
4. 确认 `width` 和 `height` 没有写反、没有符号错误、没有因为整数除法被截断为 0。
5. 检查 resize 后是否及时更新了 viewport / scissor，而不是仍使用旧窗口尺寸。
6. 检查是否只在 begin render pass 后设置了一次 dynamic state，后续又被错误覆盖。

---

### 5. 关键证据

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

### 6. 根因

根因：viewport 或 scissor 的参数设置错误，导致光栅化后的有效像素区域为空，几何体被裁剪到 render target 之外。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 Viewport / Scissor 覆盖整个 render target。
- [ ] Draw call 的 Pixels Written 大于 0。
- [ ] 画面正常显示几何体。
- [ ] 窗口 resize / Android 横竖屏切换后 viewport 自动更新。
- [ ] 多帧运行稳定，无闪烁或黑边。

---

### 9. 经验抽象

在 Vulkan 中，clear color 不受 viewport / scissor 限制，因此 clear 正常而几何体消失时，应优先怀疑光栅化状态而非 fragment shader 或 transform。凡是“clear 可见、draw 不见”，必须检查：

```text
viewport.x/y/width/height
scissor.offset/extent
minDepth/maxDepth
动态状态是否被覆盖
resize 后是否更新
```

---

### 10. 预防规则

1. 每次 begin render pass 后必须设置与当前 render target 匹配的 viewport 和 scissor。
2. viewport 的 width / height 必须大于 0；scissor 的 extent.width / extent.height 必须大于 0。
3. resize / rotation / surface 变化后必须同步更新 viewport / scissor。
4. 禁止在 render pass 中无意义地重复设置 dynamic state，若必须设置需确保参数正确。
5. 在 RenderDoc 中排查黑屏时，优先查看 Rasterizer 状态的 viewport 和 scissor 数值。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

### 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/02_render_pass_effects/add_fullscreen_pass.md`


---

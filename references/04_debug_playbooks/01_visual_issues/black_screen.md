# Debug Playbook: Black Screen

## 0. 适用范围

### 适用

- App 正常运行，无 crash，但屏幕全黑。
- 只显示黑色或只显示背景色。
- Render loop 看似运行，但没有可见图形输出。

### 不适用

- App 启动即 crash。
- Shader 编译失败导致 pipeline 创建失败。
- 明确出现 device lost。
- 只有特定纹理黑，其他内容正常。

---

## 1. 现象

常见表现：

- 屏幕全黑。
- clear color 不可见。
- clear color 可见但模型不可见。
- Android 上 Surface 正常创建，但 Vulkan 无输出。
- 无明显 Validation Error，但画面没有内容。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Render loop / acquire / submit / present 没走通 | 没有 clear color 或 present 日志异常 | Swapchain / Queue / CommandBuffer |
| P0 | CommandBuffer 未正确录制或提交 | RenderDoc 无 draw call | CommandBuffer / Queue Submit |
| P0 | Viewport / Scissor 错误 | draw call 存在但无像素覆盖 | Pipeline State |
| P1 | Pipeline / Descriptor 未正确绑定 | draw call 存在但 shader resource 为空 | Pipeline / Descriptor |
| P1 | Image layout / barrier 错误 | Validation 报 layout 或 RenderDoc 中输入贴图异常 | Image / Barrier |
| P1 | Depth / MVP 错误 | Mesh 存在但被裁掉或 depth test 全失败 | Depth / Matrix |
| P2 | Android Surface / Swapchain 生命周期错误 | rotation / resume 后出现 | Surface / ANativeWindow / Swapchain |

---

## 3. 快速验证路径

1. 打印 render loop 是否每帧执行。
2. 检查 `vkAcquireNextImageKHR` 返回值。
3. 检查 `vkQueueSubmit` 返回值。
4. 检查 `vkQueuePresentKHR` 返回值。
5. 把 clear color 改成明显颜色。
6. 用 RenderDoc / AGI 抓帧。
7. 用最简单 fullscreen triangle / triangle 替代复杂 pass。

---

## 4. Vulkan 对象链路排查

按以下顺序检查：

```text
Surface / Swapchain
→ Acquire
→ CommandBuffer Recording
→ Queue Submit
→ Pipeline Bind
→ Descriptor Bind
→ Draw
→ Render Target
→ Present
```

重点检查：

- Swapchain image 是否成功 acquire。
- CommandBuffer 是否 begin/end 成功。
- 是否调用 `vkCmdBeginRenderPass` / `vkCmdBeginRendering`。
- 是否绑定 graphics pipeline。
- 是否绑定 descriptor set。
- 是否调用 `vkCmdDraw` / `vkCmdDrawIndexed`。
- 是否 signal renderFinished semaphore。
- Present 是否等待正确 semaphore。

---

## 5. 高频根因

1. 忘记处理 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`。[SPEC]
2. CommandBuffer 没有重新录制。[ENGINE]
3. Viewport / Scissor 尺寸为 0 或不匹配 swapchain。[SPEC]
4. Graphics pipeline 创建成功但未绑定。[ENGINE]
5. DescriptorSet 未绑定或绑定到错误 set index。[ENGINE]
6. Image layout 没有 transition 到正确状态。[SPEC]
7. Depth test 导致所有片元失败。[ENGINE]
8. MVP 矩阵把模型送出裁剪空间。[HEUR]
9. Android Surface destroyed 后仍使用旧 swapchain。[ANDROID]
10. Render target / framebuffer 尺寸不匹配。[ENGINE]

---

## 6. 修复方案

### 最小修复

- 先确保 clear color 可见。[TOOL]
- 用最小 triangle 验证 pipeline 和 command buffer。[TOOL]
- 暂时关闭 depth test。[HEUR]
- 暂时移除复杂 descriptor，只保留常量颜色输出。[HEUR]

### 稳定修复

- 为 acquire / submit / present 增加返回值检查。[ENGINE]
- 为 swapchain recreate 建立完整路径。[ENGINE]
- 为 command buffer 录制增加状态日志。[TOOL]
- 用 RenderDoc 验证每个 pass 的输入输出。[TOOL]

### 工程化修复

- 建立 frame graph 或 render pass graph。[ENGINE]
- 建立统一 swapchain-size resource recreate 机制。[ENGINE]
- 建立 debug marker / object name。[TOOL]
- 建立 validation layer + RenderDoc / AGI 抓帧流程。[TOOL]

---

## 7. 回归验证

- [ ] clear color 可见。
- [ ] RenderDoc / AGI 能看到 draw call。
- [ ] Render target 有像素输出。
- [ ] Validation clean 或无相关错误。
- [ ] rotation / resize / pause / resume 后仍正常。
- [ ] 多帧运行无闪烁。

---

## 8. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 9. 工具证据

### Validation Layer

关注：

- image layout
- descriptor binding
- command buffer state
- render pass / dynamic rendering state
- synchronization hazard

### RenderDoc / AGI

关注：

- 是否存在 draw call。
- draw call 是否有 primitive。
- pipeline state 是否正确。
- descriptor 是否绑定正确资源。
- render target 是否有输出。

---

## 10. Android 分支

额外检查：

1. Surface 是否 destroyed。
2. ANativeWindow 是否有效。
3. swapchain extent 是否为 0。
4. rotation 后是否完整 recreate swapchain。
5. depth / framebuffer / offscreen image 是否同步重建。
6. in-flight command buffer 是否仍引用旧 image view。

---

## 11. 不确定时如何处理

需要补充：

- Validation message / VUID
- RenderDoc / AGI capture
- logcat
- acquire / submit / present 返回值
- swapchain recreate 代码
- command buffer 录制代码

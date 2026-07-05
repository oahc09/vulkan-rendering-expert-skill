# Workflow: Port OpenGL To Vulkan

## 0. 适用范围

### 适用

- 已有 OpenGL / OpenGL ES 渲染器，需要迁移到 Vulkan。
- 需要快速建立对象映射表、状态映射表与关键迁移检查点。
- 适用于自研渲染器、中小型项目、或作为迁移规划文档使用。

### 不适用

- 需要逐 API 手把手教学的完整教程。
- 使用第三方引擎封装的项目，引擎已负责 Vulkan 后端。
- 只需要迁移 shader 而不涉及 GL 对象映射的场景。

---

## 1. 任务目标

输出一份 OpenGL → Vulkan 迁移总览，涵盖：

```text
对象映射（GL object → Vulkan object）
状态映射（GL state → Vulkan pipeline / dynamic state）
资源映射（buffer / texture / FBO → buffer / image / image view / framebuffer / render pass）
同步映射（GL implicit sync → Vulkan explicit barrier / semaphore / fence）
常见陷阱与检查点
```

本工作流不展开为完整教程，仅提供映射表与关键迁移检查点。

---

## 2. 输入条件

需要确认：

- 原 OpenGL 版本：GL 3.3 / GL 4.x / GLES 3.x。
- 目标平台：Android / Windows / Linux。
- 目标 Vulkan 版本：1.0 / 1.1 / 1.2 / 1.3，是否使用 dynamic rendering。
- 原渲染器规模：immediate mode、retained mode、forward / deferred、postprocess 管线数量。
- 是否已有 shader 源码（GLSL）可复用。
- 是否已有窗口系统抽象（GLFW/SDL/原生）。
- 是否使用多线程 / 多 context。

---

## 3. 前置检查

- [ ] 目标物理设备支持所需 Vulkan 版本与扩展 [SPEC]。
- [ ] Validation Layer 可启用，能捕获迁移过程中大部分对象/同步错误 [TOOL]。
- [ ] RenderDoc / AGI 可抓帧，用于对比 GL 与 Vulkan 渲染结果 [TOOL]。
- [ ] shader 编译链路可用，GLSL 能编译为 SPIR-V。
- [ ] 窗口系统已准备好创建 `VkSurfaceKHR`（Android 为 `ANativeWindow`）。
- [ ] 团队已理解 Vulkan 显式资源管理与同步模型 [GUIDE]。

---

## 4. Vulkan 对象链路

```text
OpenGL Context State
→ Vulkan Instance / PhysicalDevice / Device / Queue
→ VkSurfaceKHR / VkSwapchainKHR
→ VkCommandPool / VkCommandBuffer
→ VkBuffer / VkImage / VkImageView / VkSampler
→ VkRenderPass or Dynamic Rendering
→ VkFramebuffer (if using RenderPass)
→ VkPipelineLayout / VkPipeline
→ VkDescriptorSetLayout / VkDescriptorSet
→ VkFence / VkSemaphore / VkEvent
→ VkQueue Submit → Present
```

---

## 5. 资源设计

| OpenGL 对象 | Vulkan 对象 | 说明 |
|---|---|---|
| `GLuint` buffer (VBO/UBO/SSBO) | `VkBuffer` + `VkDeviceMemory` | Vulkan buffer 为显式内存对象；UBO/SSBO 通过 usage 与 descriptor type 区分 [SPEC] |
| `GLuint` texture | `VkImage` + `VkImageView` + `VkSampler` | GL texture object 相当于 Vulkan image；sampler 在 Vulkan 中独立 [SPEC] |
| `GLuint` FBO / renderbuffer | `VkRenderPass` + `VkFramebuffer` 或 Dynamic Rendering | 多个 color/depth attachment 组合成 subpass [SPEC] |
| `GLuint` shader program | `VkShaderModule` + `VkPipelineLayout` + `VkPipeline` | GL program 在 Vulkan 中拆分为 module、layout、pipeline [SPEC] |
| `GLsync` / implicit sync | `VkFence` / `VkSemaphore` / `VkEvent` / pipeline barrier | Vulkan 无隐式同步，必须显式声明 [SPEC] |
| `glViewport` / `glScissor` | `VkPipelineViewportStateCreateInfo` 或 dynamic state | 推荐 dynamic state 以减少 pipeline 数量 [HEUR] |
| `glBlendFunc` / `glDepthFunc` | `VkPipelineColorBlendStateCreateInfo` / `VkPipelineDepthStencilStateCreateInfo` | 状态 baked 进 pipeline [SPEC] |
| `glVertexAttribPointer` | `VkPipelineVertexInputStateCreateInfo` | binding / attribute 描述与 buffer 分离 [SPEC] |
| `glUniform*` | UBO / push constant / specialization constant | 小数据用 push constant，per-frame 数据用 UBO [HEUR] |
| `glBindTexture` unit | descriptor set binding (set/binding) | 通过 descriptor set 绑定，不再依赖 texture unit [SPEC] |

---

## 6. Pipeline / Descriptor 设计

| OpenGL 概念 | Vulkan 对应 | 备注 |
|---|---|---|
| `glUseProgram` | `vkCmdBindPipeline` + `vkCmdBindDescriptorSets` | pipeline 绑定后才能 draw/dispatch [SPEC] |
| `layout(location=N)` in/out | `VkVertexInputAttributeDescription` location / `VkPipelineInputAssemblyStateCreateInfo` | vertex input 在 pipeline 创建时固定 [SPEC] |
| `layout(binding=N)` sampler | descriptor set `binding=N`，type=`COMBINED_IMAGE_SAMPLER` | 需要同时提供 image view 与 sampler [SPEC] |
| `glUniformBlockBinding` | `vkCmdBindDescriptorSets` 指定 set index | set 索引与 pipeline layout 匹配 [SPEC] |
| `glTexParameter*` (filter/wrap) | `VkSamplerCreateInfo` | 一个 sampler 对象可复用于多个 image view [SPEC] |
| `glPolygonMode` / `glCullFace` / `glFrontFace` | `VkPipelineRasterizationStateCreateInfo` | 大部分状态 baked into pipeline [SPEC] |
| `glDepthMask` / `glDepthFunc` / `glStencilOp` | `VkPipelineDepthStencilStateCreateInfo` | depth/stencil 状态在 pipeline 中 [SPEC] |
| `glBlendEquation` / `glBlendFunc` | `VkPipelineColorBlendAttachmentState` | per-attachment blend state [SPEC] |

设计说明：

- OpenGL 大量状态在 Vulkan 中需要预先 bake 进 pipeline；状态变化频繁时应优先使用 dynamic state（viewport、scissor、line width、depth bias、blend constants、stencil reference）以减少 pipeline 数量 [HEUR]。
- uniform 数据应迁移到 UBO 或 push constant；避免在 Vulkan 中模拟 `glUniform*` 的 per-draw CPU 更新，除非数据极小且使用 push constant [HEUR]。
- OpenGL 的 `glActiveTexture` + `glBindTexture` 多纹理单元模型，在 Vulkan 中通过 descriptor array 或多个 binding 实现 [SPEC]。

---

## 7. 同步与 Layout 设计

| OpenGL 行为 | Vulkan 对应 | 说明 |
|---|---|---|
| implicit memory barrier after `glTexSubImage2D` | explicit `vkCmdPipelineBarrier` | 上传后需 transition layout 到 `SHADER_READ_ONLY_OPTIMAL` [SPEC] |
| implicit FBO attachment sync | explicit `VkSubpassDependency` 或 pipeline barrier | render pass 内 subpass dependency 自动处理；pass 之间手动 barrier [SPEC] |
| `glFinish` | `vkDeviceWaitIdle` / `vkQueueWaitIdle` / fence | 高开销，仅在关键同步点使用 [HEUR] |
| `glFlush` | `vkQueueSubmit` | submit 本身即将命令提交到 device [SPEC] |
| `glClientWaitSync` | `vkWaitForFences` | CPU 等待 GPU 完成 [SPEC] |
| swap buffer | `vkAcquireNextImageKHR` + `vkQueuePresentKHR` + semaphores | 需要 image available / render finished semaphores [SPEC] |

必须说明：

- OpenGL 驱动自动处理的大部分同步在 Vulkan 中需要显式声明；遗漏 barrier 是迁移后最常见的 crash / corruption 原因 [GUIDE]。
- Image layout 是 Vulkan 特有概念；每个 image 在生命周期中需明确经过 `UNDEFINED` → `TRANSFER_DST_OPTIMAL` / `COLOR_ATTACHMENT_OPTIMAL` / `SHADER_READ_ONLY_OPTIMAL` 等状态 [SPEC]。
- `vkQueueSubmit` 的 signal semaphore 与 `vkAcquireNextImageKHR` 的 signal semaphore 必须成对使用，否则 present engine 与 rendering 发生竞争 [SPEC]。

---

## 8. 实现步骤（迁移检查点）

1. **建立对象映射表**：按第 5 节表格，列出原 GL 对象清单与对应 Vulkan 对象。
2. **建立状态映射表**：按第 6 节表格，将 GL 状态分组为 pipeline state；标记哪些状态需要 dynamic state。
3. **建立同步映射表**：按第 7 节表格，将原 GL 隐式同步点转换为 Vulkan barrier / semaphore / fence。
4. **迁移窗口系统**：GL context → Vulkan instance + surface + swapchain；Android 需处理 `ANativeWindow` 生命周期 [ANDROID]。
5. **迁移 shader**：GLSL → SPIR-V；补齐 `layout(set, binding)`；将 `glUniform*` 数据迁移到 UBO / push constant。
6. **迁移资源**：
   - VBO/IBO → `VkBuffer` + staging upload。
   - texture → `VkImage` + `VkImageView` + `VkSampler` + layout transition。
   - FBO → `VkRenderPass` / dynamic rendering + `VkFramebuffer`（如使用 render pass）。
7. **迁移绘制命令**：
   - `glBindVertexArray` / `glDrawElements` → `vkCmdBindVertexBuffers` / `vkCmdBindIndexBuffer` / `vkCmdDrawIndexed`。
   - `glUseProgram` → `vkCmdBindPipeline` + `vkCmdBindDescriptorSets`。
   - `glViewport` / `glScissor` → dynamic state 设置。
8. **接入 swapchain 循环**：`vkAcquireNextImageKHR` → record CB → `vkQueueSubmit` → `vkQueuePresentKHR`。
9. **验证单帧渲染正确性**：RenderDoc / AGI 抓帧对比 GL 与 Vulkan 的 draw call、resource binding、输出 attachment。
10. **验证多帧稳定性**：开启 Validation Layer，运行 100+ 帧，检查 synchronization hazard 与 layout error。
11. **接入 resize / recreate / Android 生命周期**：按第 9 节处理。

---

## 9. Android 注意点

- OpenGL ES 的 `EGLSurface` 与 `ANativeWindow` 绑定模型在 Vulkan 中对应 `VkSurfaceKHR` + `VkSwapchainKHR`；必须在 `ANativeWindow` 有效时创建 surface，销毁 surface 前等待 GPU idle [ANDROID]。
- GLES 的隐式 sync 在 Android Vulkan 中必须显式化；Adreno/Mali 对缺失 barrier 非常敏感，易出现画面撕裂或 `DEVICE_LOST` [ANDROID]。
- rotation / resize 后 surface extent 可能变为 0，必须等待有效值再重建 swapchain [ANDROID]。
- pause / resume 时保留 `VkPipelineCache` 与编译后的 SPIR-V 可加速恢复；swapchain 与 surface 通常需要重建 [ANDROID]。
- GLES 中常见的 `glTexImage2D` 同步上传会阻塞，Vulkan 中应使用 staging buffer + transfer queue（若独立）并插入 fence [HEUR]。
- AGI / logcat 验证：对比 GLES 与 Vulkan 版本的 GPU frame time、bandwidth、validation error。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-*` 错误，特别是 synchronization hazard、image layout、descriptor binding [TOOL]。
- [ ] RenderDoc / AGI：渲染结果与原 OpenGL 版本一致；draw call 数量、资源绑定、pipeline state 正确 [TOOL]。
- [ ] 截图符合预期：逐像素或视觉上与 GL 版本一致。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出迁移后的 draw call 数与 pipeline 数。
- [ ] 性能指标：
  - GPU frame time 与 GL 版本持平或更优；
  - pipeline 数量可控，未因状态变化频繁而爆炸 [HEUR]；
  - barrier 数量合理，无 over-barrier [TOOL]。
- [ ] resize / pause / resume / rotation 后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或内存泄漏。

---

## 11. 常见失败模式

1. **假设隐式同步仍然存在**：遗漏 barrier 或 semaphore，导致 read-after-write 或 present 竞争 [SPEC]。
2. **Pipeline 状态爆炸**：将过多 GL 状态变化 bake 进 pipeline，导致成千上万条 pipeline [HEUR]。
3. **Image layout 未管理**：texture 上传后未 transition 到 `SHADER_READ_ONLY_OPTIMAL`，渲染时 validation error 或黑屏 [TOOL]。
4. **Descriptor set layout 与 shader 不一致**：GLSL 未写 `layout(set, binding)` 或 set/binding 冲突 [SPEC]。
5. **Swapchain semaphore 缺失或顺序错误**：`vkAcquireNextImageKHR` 的 signal semaphore 未在 submit 时 wait [SPEC]。
6. **Surface 生命周期未处理**：Android rotation 或 pause 后仍使用旧 surface/swapchain，导致 crash [ANDROID]。
7. **Uniform 更新方式错误**：大量 per-draw 数据仍用 UBO 动态更新，未考虑 `minUniformBufferOffsetAlignment` 与 descriptor 更新开销 [HEUR]。
8. **OpenGL 状态默认值依赖**：Vulkan pipeline 必须显式设置所有状态，不能依赖 GL 的默认 enable/disable [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_overuse.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 原 OpenGL 版本与目标 Vulkan 版本。
- 对象映射清单（GL handle → Vulkan handle）。
- 状态变化频率统计（用于判断 dynamic state 需求）。
- 原 GL 渲染循环与同步点。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 GL 与 Vulkan 的对比截图。
- Android lifecycle 日志。

# Workflow: Convert Single Pass To Render Graph

## 0. 适用范围

### 适用

- 已有单 pass 渲染器，希望用 RenderGraph 自动推导资源依赖、barrier 与 layout transition。
- 需要把硬编码的 `vkCmdPipelineBarrier` / `vkCmdBeginRenderPass` 迁移到声明式 pass node。
- 目标框架为自研 RenderGraph、FrameGraph 或类似声明式调度系统。
- 适合 offscreen pass、postprocess、deferred / forward 单 pass 的迁移。

### 不适用

- 纯即时模式渲染器且没有抽象需求。
- 使用第三方引擎内置 RenderGraph（如 UE5 RDG、Godot），应遵循其接口。
- 需要跨 frame 持久化的复杂异步计算管线（需额外处理事件/信号量）。

---

## 1. 任务目标

将一条手动管理 barrier 与 layout 的 graphics/compute pass 转换为 RenderGraph 节点，使资源声明、依赖推导、barrier 生成、layout tracking 全部由 RenderGraph 负责。

```text
原始手动路径：
CPU 代码直接调用 vkCmdPipelineBarrier / vkCmdBeginRenderPass
→ RenderGraph 路径：
声明 RenderGraphResource (image/buffer)
→ 声明 RenderPassNode / ComputePassNode
→ 声明 read/write dependency
→ RenderGraph 自动插入 barrier 与 layout transition
→ 执行 compiled command buffer
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本与是否启用 `VK_KHR_dynamic_rendering` / Vulkan 1.3。
- 现有 RenderGraph 实现是否支持 image / buffer resource、pass node、subresource tracking。
- 原 pass 的输入资源（color/depth attachment、sampled image、uniform buffer、storage buffer）。
- 原 pass 的输出资源（color attachment、storage image、write buffer）。
- 原 pass 的 pipeline layout、descriptor set、push constant 需求。
- 是否需要保留 backbuffer present、offscreen intermediate、或 history buffer。
- 是否涉及 per-frame 资源（如 ping-pong）或 persistent 资源（如下采样 pyramid）。

---

## 3. 前置检查

- [ ] Validation Layer 已启用，可捕获 synchronization hazard 与 layout error [TOOL]。
- [ ] RenderDoc / AGI 可抓帧，能对比迁移前后的 pass 结构与 barrier。
- [ ] 原 pass 在迁移前已能稳定渲染（baseline）。
- [ ] RenderGraph 的 resource registry、pass culling、barrier scheduler 已通过单元测试。
- [ ] swapchain recreate / resize 路径已接入 RenderGraph 的输出 flush。
- [ ] command buffer / frame-in-flight 池稳定。
- [ ] shader 编译链路可用，SPIR-V set/binding 与原 pass 一致。

---

## 4. Vulkan 对象链路

```text
RenderGraph Builder
→ RenderGraphResource (VkImage / VkBuffer / VkImageView)
→ RenderPassNode / ComputePassNode
→ Resource Dependency (read / write / create)
→ RenderGraph Compiler
→ Auto-generated VkImageMemoryBarrier / VkBufferMemoryBarrier / VkMemoryBarrier
→ Compiled RenderPass or Dynamic Rendering Info
→ VkCommandBuffer
→ VkQueue Submit
→ VkFence / VkSemaphore (frame-in-flight)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| render target image | `VkImage` | `COLOR_ATTACHMENT` / `DEPTH_STENCIL_ATTACHMENT` | pass 输出 | 是（若绑定 swapchain 尺寸） |
| intermediate image | `VkImage` | `COLOR_ATTACHMENT \| SAMPLED` / `STORAGE` | per-frame 或 persistent | 视 RenderGraph 策略 |
| uniform buffer | `VkBuffer` | `UNIFORM_BUFFER` | per-frame | 否 |
| storage buffer | `VkBuffer` | `STORAGE_BUFFER` | per-frame 或 persistent | 否 |
| sampled input | `VkImageView` + `VkSampler` | `SAMPLED` | 资源生命周期 | 否 |
| image view | `VkImageView` | attachment / sampled | 跟随 image | 视 image 重建策略 |
| pipeline | `VkPipeline` | 管线状态 | pipeline 生命周期 | 否 |
| descriptor set | `VkDescriptorSet` | binding | per-frame / per-pass | 视更新策略 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame constants | Vertex / Fragment / Compute |
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | input texture | Fragment / Compute |
| set=1,binding=1 | `STORAGE_IMAGE` | UAV / write image | Compute / Fragment（如支持） |
| set=2,binding=0 | `STORAGE_BUFFER` | per-draw data | Vertex / Fragment / Compute |
| push constant | `VkPushConstantRange` | pass id / draw index | Vertex / Fragment / Compute |

设计说明：

- RenderGraph 不负责 shader binding 细节，只保证资源在 pass 执行时处于合法 layout 与可见性；descriptor 与 pipeline layout 仍按常规管线设计 [ENGINE]。
- 若 RenderGraph 自动生成 descriptor set，必须保证 set/binding/type/stage 与 shader reflection 一致 [SPEC]。
- pass node 内部通过回调拿到 physical `VkImageView` / `VkBuffer` handle 后再执行 `vkCmdBindDescriptorSets` 与 `vkCmdBindPipeline` [ENGINE]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass write / external upload | render target image | `UNDEFINED` / `GENERAL` / `TRANSFER_DST` → `COLOR_ATTACHMENT_OPTIMAL` | graphics pass color attachment write |
| graphics pass color attachment write | color image | `COLOR_ATTACHMENT_WRITE` → next stage；`COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` / `PRESENT_SRC_KHR` | next pass sample / present |
| compute pass storage image write | storage image | `SHADER_WRITE` → `SHADER_READ`；`GENERAL` → `GENERAL`（layout 不变，access 改变） | next compute / graphics sample |
| transfer upload | buffer | `TRANSFER_WRITE` → `SHADER_READ` | vertex / compute shader read |

必须说明：

- RenderGraph 通过资源声明推导 dependency：producer pass 写入 `RenderGraphResource`，consumer pass 读取同一 resource，compiler 自动插入 barrier [ENGINE]。
- 若 RenderGraph 不支持 subresource tracking，整张 image 的 layout 会被统一推进；需评估 false dependency 与 over-barrier 开销 [HEUR]。
- 手动写入 pass 的 barrier 必须与 RenderGraph 推导结果一致；重复 barrier 不会导致错误，但会降低性能 [HEUR]。
- Dynamic Rendering 下，`VkRenderingInfo` 的 `imageLayout` 由 RenderGraph 在 compile 时根据当前 tracked layout 填写 [SPEC]。
- 多 queue 场景（async compute / transfer）需要 RenderGraph 显式处理 semaphore 或 `VK_KHR_synchronization2` 的 queue family ownership transfer [SPEC]。

---

## 8. 实现步骤

1. **为原 pass 创建 RenderGraphResource**：
   - 声明输入资源（read）：`RenderGraphResource::Read(inputImage)`。
   - 声明输出资源（write）：`RenderGraphResource::Write(outputImage, initialLayout, finalLayout)`。
   - 声明创建资源（create）：若资源为 transient，由 RenderGraph 分配并复用内存 [ENGINE]。
2. **创建 Pass Node**：
   - graphics pass：声明 color/depth attachment、sampled input、resolve attachment。
   - compute pass：声明 storage image / buffer read/write。
3. **在 Pass Node 回调中实现渲染逻辑**：
   - 通过 RenderGraph context 查询 physical `VkImageView` / `VkBuffer`。
   - 绑定 pipeline、descriptor set、push constant。
   - 调用 `vkCmdDraw` / `vkCmdDrawIndexed` / `vkCmdDispatch`。
   - 不要在此回调中手动插入 barrier（除非 RenderGraph 显式允许 emergency barrier）[ENGINE]。
4. **连接 Pass 依赖**：
   - 按数据流声明 producer → consumer；RenderGraph 据此计算 execution order。
   - 若两个 pass 可并行且无资源依赖，标记为可 culling / async [HEUR]。
5. **编译 RenderGraph**：
   - 推导资源生命周期、分配 transient memory、生成 barrier、合并 render pass / dynamic rendering info。
   - 输出 compiled command buffer 或 command buffer 录制函数 [ENGINE]。
6. **替换原渲染路径**：
   - 删除原 pass 中手动的 `vkCmdPipelineBarrier`、`vkCmdBeginRenderPass`。
   - 在 frame loop 中调用 `renderGraph.compile()` 与 `renderGraph.execute()`。
7. **接入 resize / recreate**：
   - swapchain 重建时，标记 swapchain-size-dependent 资源为 invalid；RenderGraph 重新分配 transient image [ENGINE]。
   - persistent resource（如下采样 pyramid）若尺寸变化，手动重建。
8. **接入销毁路径**：
   - transient resource 由 RenderGraph allocator 释放；persistent resource 按原生命周期销毁 [ENGINE]。
9. **验证 barrier 生成**：
   - 对比 RenderGraph 生成的 barrier 与原手动 barrier 的 stage/access/layout 是否等价。

---

## 9. Android 注意点

- 创建 RenderGraph 的 transient image 前，必须确保 `ANativeWindow` 已绑定到 `VkSurfaceKHR` 且 swapchain 已创建；RenderGraph 的 backbuffer 资源依赖于 surface extent [ANDROID]。
- rotation / resize 后 surface extent 可能变为 0，必须在 `onSurfaceChanged` 中等待有效 extent 后再触发 RenderGraph 重新编译 [ANDROID]。
- pause / resume 时保留 pipeline cache 与 persistent resource；transient swapchain-dependent image 应延迟到 resume 后重新分配 [ANDROID]。
- 移动端 Mali/Adreno 对 barrier 与 render pass 合并敏感；验证 RenderGraph 是否将多个小 pass 合并为单个 subpass 或 dynamic rendering 调用，以减少 tile bandwidth [ANDROID]。
- 若 RenderGraph 默认使用 `GENERAL` layout，Adreno 可能性能下降；应确保 color attachment 使用 `COLOR_ATTACHMENT_OPTIMAL`，sampled image 使用 `SHADER_READ_ONLY_OPTIMAL` [ANDROID]。
- AGI / logcat 验证：检查 RenderGraph 生成的 barrier 数量、pass 合并情况、`vkCmdBeginRendering` 调用次数。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCmdPipelineBarrier-*`、`VUID-vkCmdBeginRendering-*`、`VUID-vkCmdDraw-*` 错误；特别关注 synchronization hazard 与 image layout 报错 [TOOL]。
- [ ] RenderDoc / AGI：pass 结构、attachment、draw call 与迁移前一致；barrier 数量合理且位置正确 [TOOL]。
- [ ] 截图符合预期：color/depth 输出、postprocess 效果与手动路径逐像素一致。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出 RenderGraph compile 耗时与 barrier 数量统计。
- [ ] 性能指标：
  - GPU frame time 与迁移前持平或更优；
  - AGI 中 barrier count 未显著增加（若增加，说明 RenderGraph 未充分合并 pass）[TOOL]；
  - 移动端 tile bandwidth 未因 layout 选择不当而上升 [ANDROID]。
- [ ] resize / pause / resume / rotation 后渲染正常，transient resource 正确重建。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 flickering。

---

## 11. 常见失败模式

1. **RenderGraph 推导的 layout 与 shader 期望不符**：如 attachment 实际为 `GENERAL` 但 shader 按 `SHADER_READ_ONLY_OPTIMAL` 采样，导致 validation error [TOOL]。
2. **False dependency 导致 pass 串行化**：资源粒度太粗，两张实际无关的 texture 被声明为同一 `RenderGraphResource`，compiler 插入多余 barrier [HEUR]。
3. **Persistent resource 未正确声明跨 frame 依赖**：下一张读取上一帧结果时未标记 external/history dependency，出现 read-after-write hazard [SPEC]。
4. **Pass 回调中手动插入 barrier 与 RenderGraph 冲突**：造成重复 transition 或 layout mismatch [ENGINE]。
5. **Swapchain 重建后 transient image 尺寸未更新**：导致 attachment extent 与 surface 不一致，创建或渲染失败 [ANDROID]。
6. **Multi-queue 资源未处理 ownership transfer**：async compute 写入的 buffer 被 graphics queue 读取时未插入 queue family ownership barrier [SPEC]。
7. **RenderGraph 未正确清除 transient image 初始状态**：首次写入前未从 `UNDEFINED` transition 到目标 layout，导致旧数据被读取 [TOOL]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_overuse.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / RenderGraph 实现。
- 原 pass 的手动 barrier 代码与 attachment layout 序列。
- RenderGraph 编译日志（barrier 列表、pass order、resource alias）。
- Validation Layer 完整报错。
- RenderDoc / AGI 中迁移前后的 pass 与 barrier 对比。
- Android lifecycle 日志（surface create/destroy、pause/resume、rotation）。

# Debug Playbook: GPU Frame Time High

## 0. 适用范围

### 适用

- GPU 帧时间（frame time）明显高于目标预算（如 16.67 ms / 33.33 ms）。
- `GPU Busy %`、`GPU Duration` 等指标接近或达到 100%。
- 某类 pass（shadow、base pass、post-process）耗时突增。
- 同一场景在不同 GPU 上帧时间差异大。

### 不适用

- CPU 帧时间高导致整体卡顿（优先排查 CPU profiling）。
- 帧率被 swapchain present 间隔或 vsync 限制。
- 应用被后台调度或系统功耗策略降频。

---

## 1. 现象

- GPU frame time 持续高于目标预算。
- `GPU % Busy` 接近 100%，frame time 波动与 GPU 时间轴一致。
- 某些 draw call 的 GPU 耗时占整帧比例异常高。
- 关闭部分 pass 后帧时间明显下降。
- 低端设备掉帧严重，高端设备正常。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Fragment / ROP 瓶颈 | `GPU % Busy` 高、`Pixel Shader` / `ROP` counter 高；降低分辨率帧时间显著下降 | Fragment Shader / Attachment |
| P0 | Vertex / Geometry 瓶颈 | `Vertex Shader` / `Geometry Shader` / `Tessellation` counter 高；draw call 数多、顶点数大 | Vertex Shader / Buffer |
| P0 | 过度同步 / barrier / wait | GPU 时间轴存在大量空泡；`IDLE` 或 `WAIT` 占比高 | Barrier / Semaphore |
| P1 | Compute 任务过重或调度不当 | Compute queue 长时间占用；graphics 等待 compute | Compute Pipeline |
| P1 | 大量小 draw call 导致 command processor 开销 | Draw call 数 > 数千；`CP` / `Command Buffer` 负载高 | Command Buffer / Pipeline |
| P1 | Texture / bandwidth 瓶颈 | `Texture Fetch` / `Bandwidth` counter 高；降低 texture 质量帧时间下降 | Image / Sampler |
| P2 | 驱动编译或 pipeline cache 未命中 | 首帧或 shader 变体切换时帧时间尖峰 | Pipeline Cache / Shader Module |

---

## 3. 快速验证路径

1. **用 GPU Profiler 抓取一帧**，确认瓶颈所在 pipeline stage。`[TOOL]`
2. **降低渲染分辨率 50%**：若帧时间近似减半，瓶颈在 fragment / ROP。`[TOOL]`
3. **减少 draw call 数或顶点数**：若帧时间显著下降，瓶颈在 vertex / geometry。`[TOOL]`
4. **注释掉 suspicious pass**：二分定位耗时大户。`[TOOL]`
5. **检查 barrier 数量与位置**：看 GPU 时间轴是否有大量空泡。`[TOOL]`
6. **检查 texture / buffer 尺寸与格式**：降低采样质量或分辨率测试。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Command Buffer Submit
→ Vertex Input / Index Buffer
→ Vertex Shader
→ Tessellation / Geometry Shader
→ Rasterization
→ Fragment Shader
→ ROP / Color Blend
→ Attachment Write
→ Barrier / Present
```

逐项检查：

- 每帧 draw call 数量、instance 数量、顶点数量是否合理。`[HEUR]`
- Vertex shader 输出 interpolant 数量是否过多。`[HEUR]`
- Fragment shader 中 ALU / texture 采样复杂度。`[HEUR]`
- Render target 分辨率、MSAA 级别、MRT 数量。`[HEUR]`
- Barrier 是否导致 GPU 空等，是否存在 `vkDeviceWaitIdle` 或过度 `vkQueueWaitIdle`。`[TOOL]`
- Compute dispatch 是否与 graphics 合理交错，是否存在长时间独占 GPU。`[TOOL]`
- Pipeline 是否频繁切换导致 command processor 开销。`[TOOL]`

---

## 5. 高频根因

1. Fragment shader 过度使用复杂光照、shadow map 采样、noise 函数。`[ENGINE]`
2. Overdraw 严重，透明物体未按深度排序或未启用 early-z。`[ENGINE]`
3. 高分辨率 render target + MSAA + MRT 导致 ROP 和带宽压力。`[ENGINE]`
4. 大量小 draw call，command processor 和 descriptor binding 开销占主导。`[ENGINE]`
5. 不必要的 `vkDeviceWaitIdle`、`vkQueueWaitIdle` 或过度 barrier 导致 GPU 空闲。`[ENGINE]`
6. Compute 任务过重且未与 graphics overlap，导致 graphics queue 空等。`[ENGINE]`
7. 未使用 pipeline cache，运行期编译 shader 导致帧时间尖峰。`[ENGINE]`

---

## 6. 修复方案

### 最小修复

- 对 fragment 瓶颈：降低渲染分辨率、降低 overdraw、简化 shader。`[HEUR]`
- 对 vertex 瓶颈：减少 draw call（batch / instancing）、LOD、减少 vertex attribute。`[HEUR]`
- 对 barrier 瓶颈：合并 barrier、移除不必要的 `vkDeviceWaitIdle`。`[ENGINE]`
- 对 compute 瓶颈：将 compute 拆小并与 graphics 交错 submit，或调整 dispatch 尺寸。`[HEUR]`

### 稳定修复

- 实施延迟渲染、forward+ 等降低 overdraw 的架构。`[ENGINE]`
- 建立 LOD、occlusion culling、depth prepass 降低 vertex / fragment 工作量。`[ENGINE]`
- 使用 bindless / multi-draw indirect 减少 draw call 和 descriptor 切换。`[ENGINE]`
- 建立 render graph 自动合并 barrier 并减少 global barrier。`[ENGINE]`
- 预编译 pipeline 并使用 `VkPipelineCache` 持久化。`[SPEC]`

### 工程化修复

- CI 集成性能测试，自动回归 GPU frame time。`[TOOL]`
- 建立 per-pass GPU time budget 和自动告警。`[ENGINE]`
- 对低端设备启用动态分辨率、动态 LOD、画质分级。`[ENGINE]`
- 使用 GPU-driven rendering 减少 CPU-GPU 往返。`[ENGINE]`

---

## 7. 回归验证

- [ ] GPU frame time 回到预算内并稳定。
- [ ] 目标设备上不再掉帧。
- [ ] 性能优化未引入新的 sync hazard 或 image layout 错误。
- [ ] 不同画质等级 / 分辨率下帧时间符合预期。
- [ ] resize / rotation 后性能策略仍生效。
- [ ] 长时间运行无热降频导致的帧时间退化。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`

---

## 9. 工具证据

### Validation Layer

- Validation 本身不直接给出性能数据，但关注是否因过度 barrier 触发 best practice 警告。`[TOOL]`
- 关注 `UNASSIGNED-BestPractices-DrawState-Clear` 等小 draw call 相关建议。`[TOOL]`

### RenderDoc

- 查看 event browser 中每个 draw / dispatch 的 GPU duration。`[TOOL]`
- 查看 pipeline state 中 shader 复杂度、texture 绑定数量。`[TOOL]`
- 使用 RenderDoc 的 pixel history / overdraw 可视化工具检查 overdraw。`[TOOL]`
- 查看 mesh 数据，确认顶点数、index count、instance count。`[TOOL]`

### AGI / Android

- 关注 `GPU % Busy`、`GPU Duration`、`Vertex Duration`、`Fragment Duration`。`[TOOL]`
- 查看 `Vertex Shader Invocations`、`Fragment Shader Invocations` 与输入顶点 / 像素比例。`[TOOL]`
- 查看 `Texture Fetch` / `Texture Cache Miss` 判断 texture 瓶颈。`[TOOL]`
- 查看 GPU 时间轴是否有空泡（barrier / wait）或阶段重叠不足。`[TOOL]`

### logcat

- 搜索 `Choreographer`、`dropped frames`、`frame time` 等系统帧率信息。`[ANDROID]`
- 检查是否触发 thermal throttling 导致 GPU 降频。`[ANDROID]`

---

## 10. Android 分支

Android 上 GPU frame time 受 Surface / ANativeWindow / Swapchain 生命周期和功耗影响，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且尺寸与 swapchain 一致；异常 surface 会导致 present 阻塞或额外重试。`[ANDROID]`
2. **Swapchain 与刷新率匹配**：确认 `VkSwapchainCreateInfoKHR::presentMode` 与设备刷新率匹配；`FIFO` 模式下帧时间会被 present 间隔量化。`[SPEC]`
3. **Thermal throttling**：长时间高负载后 GPU 可能降频；logcat 中搜索 thermal 相关日志。`[ANDROID]`
4. **Tile-based GPU 特性**：Adreno / Mali 上 FSAA、MRT、粗粒度 depth/stencil 操作开销与 desktop 不同；优先用 AGI 查看 tile 相关 counter。`[ANDROID]`
5. **分辨率动态调整**：Android 设备分辨率多样，建议实现动态分辨率缩放并在 swapchain recreate 时生效。`[ANDROID]`
6. **后台 / 分屏 / 画中画**：`ANativeWindow` 尺寸变化或应用进入后台后应降低渲染负载。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - GPU Profiler 抓取的帧时间轴截图（RenderDoc / AGI / NVIDIA Nsight / Radeon GPU Profiler）。
   - 各 pipeline stage 的耗时分布。
   - 每帧 draw call 数、顶点数、fragment shader invocation 数。
   - Render target 分辨率、MSAA 设置、MRT 数量。
   - Barrier / wait 的位置和数量。
   - Compute dispatch 的尺寸和与 graphics 的交错情况。
   - 设备型号、GPU、驱动版本、Android 版本、目标刷新率。
   - 是否启用 vsync、present mode、动态分辨率。
3. 给出最小验证路径：降低分辨率 / 注释 pass / 合并 barrier，逐项二分。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 swapchain present mode 或 pipeline cache 规范。
   - `[TOOL]` 若 Profiler 已给出明确瓶颈证据。
   - `[ENGINE]` 若基于渲染架构或优化经验推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 mobile GPU 功耗、thermal、tile 架构或 Surface 生命周期。

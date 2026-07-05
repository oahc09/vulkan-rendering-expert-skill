# Debug Playbook: Fullscreen Pass Cost

## 0. 适用范围

### 适用

- 后处理、UI、全屏特效、deferred shading light pass 等 fullscreen quad / triangle 耗时高。
- 降低渲染分辨率后帧时间近似线性下降。
- Profiler 显示 fullscreen pass 的 fragment shader invocation 数接近或超过屏幕像素数。
- 移动设备上 fullscreen pass 导致发热或带宽飙升。

### 不适用

- 几何密集型 pass（优先看 gpu_frame_time_high.md 的 vertex 瓶颈）。
- Compute dispatch 替代 fullscreen draw 的性能问题。
- 非 fullscreen 的透明物体 overdraw（虽相关，但本 Playbook 聚焦全屏 pass）。

---

## 1. 现象

- 单个或少数几个 fullscreen draw 占据整帧较大比例 GPU 时间。
- 降低 output resolution 后该 pass 时间明显下降。
- Fragment shader 复杂度高，采样次数多，ALU 运算重。
- 每个 fullscreen pass 都读写 fullscreen attachment，带宽叠加。
- 移动端 tile-based GPU 上 fullscreen pass 后出现明显 tile flush 或 bandwidth 峰值。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Fragment shader ALU / 采样过重 | `Fragment Duration` 高；简化 shader 后时间大幅下降 | Fragment Shader / Sampler |
| P0 | 多个 fullscreen pass 顺序读写 attachment | 每个 pass 都读写 fullscreen RT；合并 pass 后时间下降 | Render Pass / Image |
| P0 | Texture 采样过多或 cache miss 高 | `Texture Fetch` / `Texture Cache Miss` 高；降低 sample 数后改善 | Sampler / Image |
| P1 | Overdraw / 重复 fullscreen draw | 同一区域被多个 fullscreen pass 覆盖；可合并或剔除 | Command Buffer |
| P1 | 未利用 tile-based 本地读取 | Mobile GPU 上未使用 subpass / input attachment，导致 system memory 往返 | Render Pass / Android |
| P1 | Fullscreen pass 分辨率过高 | 使用原生分辨率而非 dynamic resolution / half resolution | Image |
| P2 | MSAA / HDR / 高精度 format | Attachment 格式增加 ROP / 带宽压力 | Attachment / Format |

---

## 3. 快速验证路径

1. **用 Profiler 定位耗时 fullscreen pass**，查看其 GPU duration。`[TOOL]`
2. **把该 pass 的 fragment shader 替换为简单输出**：若时间大幅下降，瓶颈在 shader。`[TOOL]`
3. **降低 fullscreen pass 输出分辨率 50%**：若时间近似减半，瓶颈在 fragment / ROP / 带宽。`[TOOL]`
4. **合并相邻 fullscreen pass**：减少中间 attachment 读写。`[TOOL]`
5. **检查 fragment shader 中 texture 采样次数和 filter 模式**。`[TOOL]`
6. **在 mobile 上检查是否可用 subpass input attachment 替代 texture 采样**。`[ANDROID]`

---

## 4. Vulkan 对象链路排查

```text
Fullscreen Vertex Buffer / Procedural Triangle
→ Graphics Pipeline
→ Fragment Shader
→ Texture Sample / Input Attachment Read
→ Color Attachment Write
→ Next Fullscreen Pass ...
```

逐项检查：

- Fullscreen pass 数量及每个 pass 的 input / output attachment。`[TOOL]`
- 每个 fullscreen pass 的 fragment shader 复杂度（ALU、branch、texture sample）。`[TOOL]`
- Texture 分辨率、format、mipmap、filter 设置。`[HEUR]`
- Attachment format（`RGBA8` vs `RGBA16F` vs `RGBA32F`）和 bandwidth 影响。`[HEUR]`
- 是否使用了 subpass dependency / input attachment 在 tile memory 内传递数据。`[SPEC]`
- 是否可合并相邻 pass 减少 attachment 读写。`[ENGINE]`
- 是否可对部分 pass 使用降低分辨率（bloom、blur 常用 half / quarter resolution）。`[HEUR]`

---

## 5. 高频根因

1. Fragment shader 中多次采样 full-resolution texture 做复杂后处理（如 SSR、SSAO、DOF、bloom 合并）。`[ENGINE]`
2. 每个后处理 pass 都输出到独立 fullscreen RT，再被下一 pass 采样，带宽成倍增加。`[ENGINE]`
3. 未使用 mipmap 或降低分辨率做模糊 / bloom，导致大量 full-resolution 采样。`[ENGINE]`
4. 未按 mobile tile-based 架构优化，未使用 subpass / input attachment。`[ANDROID]`
5. Fullscreen pass 使用高精度 attachment（`RGBA16F` / `RGBA32F`）但画质收益有限。`[ENGINE]`
6. 多个 UI 全屏层叠，每层都独立绘制并混合。`[ENGINE]`
7. 未开启 early-z 或 depth test 优化 fullscreen pass（部分后处理可利用 stencil 剔除）。`[HEUR]`

---

## 6. 修复方案

### 最小修复

- 简化 fragment shader，减少 texture 采样次数和 ALU 运算。`[HEUR]`
- 合并相邻 fullscreen pass，减少中间 attachment 数量。`[ENGINE]`
- 对 bloom / blur 等效果使用 half / quarter resolution。`[HEUR]`
- 降低 fullscreen pass output format 精度（如 `RGBA16F` → `RGBA8` 或 `R11G11B10F`）。`[HEUR]`

### 稳定修复

- 建立后处理管线，自动合并可合并的 fullscreen pass。`[ENGINE]`
- 使用 subpass input attachment 在 tile memory 内读取上一 pass 输出（尤其 mobile）。`[ANDROID]`
- 对常用后处理效果建立 downsample / upsample 链，避免全分辨率采样。`[ENGINE]`
- 使用 compute shader 替代部分 fullscreen pass，可能更高效（需结合平台实测）。`[HEUR]`
- 对 UI 全屏层进行 batch 和剔除，减少重叠绘制。`[ENGINE]`

### 工程化修复

- CI 集成 per-pass GPU time 预算，fullscreen pass 超过阈值自动告警。`[TOOL]`
- 根据设备性能自动调整后处理质量等级（分辨率、采样数、pass 数）。`[ENGINE]`
- 在 mobile 上优先使用 subpass / input attachment，并自动检测平台支持。`[ANDROID]`
- 建立 fullscreen pass 开销分析工具，统计每个 pass 的 bandwidth 和 ALU。`[TOOL]`

---

## 7. 回归验证

- [ ] 目标 fullscreen pass GPU time 回到预算内。
- [ ] 合并 / 降采样后画面质量在可接受范围。
- [ ] 未引入 image layout / sync hazard。
- [ ] Mobile 设备上发热和带宽改善。
- [ ] 不同画质等级 / 分辨率下 fullscreen pass 开销可控。
- [ ] resize / rotation 后动态分辨率策略仍生效。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 9. 工具证据

### Validation Layer

- 关注 image layout / subpass input attachment 相关 VUID。`[TOOL]`
- 关注 best practice 关于 fullscreen clear / 小 draw 的建议。`[TOOL]`

### RenderDoc

- 查看每个 fullscreen pass 的 GPU duration 和 fragment shader 复杂度。`[TOOL]`
- 查看 texture 采样次数、filter、分辨率。`[TOOL]`
- 查看 input / output attachment 格式和尺寸。`[TOOL]`
- 使用 overdraw / pixel history 检查是否有重复 fullscreen 覆盖。`[TOOL]`

### AGI / Android

- 关注 `Fragment Duration`、`Fragment Shader Invocations`、`Texture Fetch`。`[TOOL]`
- 查看 `Color Bandwidth`、`Bytes/Pixel` 判断 fullscreen pass 带宽。`[TOOL]`
- 查看 GPU 时间轴中 fullscreen pass 是否导致大量 tile flush。`[TOOL]`
- 检查 `GPU % Busy` 在 fullscreen pass 期间是否满载。`[TOOL]`

### logcat

- 搜索 `thermal`、`throttling` 判断 fullscreen pass 是否导致降频。`[ANDROID]`
- 检查是否有 subpass / input attachment 相关驱动警告。`[ANDROID]`

---

## 10. Android 分支

Android 上 fullscreen pass 与 tile-based GPU、Surface 生命周期、功耗密切相关，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且尺寸稳定；surface 重建后 fullscreen pass 的 attachment 尺寸需同步更新。`[ANDROID]`
2. **Tile-based GPU 本地读取**：Adreno / Mali 上应优先使用 subpass / input attachment 在 tile memory 内读取前序 pass 输出，避免写回 system memory 再采样。`[ANDROID]`
3. **Attachment 压缩**：确认 fullscreen attachment 是否启用 AFBC / UBWC；未压缩的 16F / 32F attachment 会大幅增加带宽。`[ANDROID]`
4. **Dynamic resolution**：Android 设备分辨率多样，建议 fullscreen pass 输出使用可调整的 render target 分辨率，而非固定 native resolution。`[ANDROID]`
5. **Present 前最终 pass**：最终 fullscreen pass 到 swapchain 之间尽量减少额外 layout transition 和 barrier，直接输出到 `COLOR_ATTACHMENT_OPTIMAL` 然后 transition 到 `PRESENT_SRC_KHR`。`[SPEC]`
6. **UI 层管理**：Android 上 UI 全屏层叠常见，应 batch 和剔除隐藏层，减少重复 fullscreen blend。`[ANDROID]`
7. **后台 / 分屏**：`ANativeWindow` 尺寸变化或应用进入后台时，应降低或跳过非关键 fullscreen pass。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - GPU Profiler 抓取的 fullscreen pass GPU duration 截图。
   - Fragment shader 源码及 texture 采样次数。
   - Fullscreen pass 数量、输入输出 attachment 格式 / 分辨率。
   - 是否使用 subpass / input attachment。
   - 是否使用 dynamic resolution、downsample / upsample 链。
   - RenderDoc capture 中该 pass 的 pipeline state 和 resource 绑定。
   - 设备型号、GPU、驱动版本、Android 版本。
3. 给出最小验证路径：替换为简单 shader → 降低分辨率 → 合并 pass → 使用 subpass input attachment。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 subpass / input attachment / layout transition 规范。
   - `[TOOL]` 若 Profiler 已给出明确 fullscreen pass 耗时证据。
   - `[ENGINE]` 若基于后处理管线或 UI 架构推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 tile-based GPU、压缩格式或 Surface 生命周期。

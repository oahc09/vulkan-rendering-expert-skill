# Debug Playbook: Bandwidth / Fullscreen Pass Cost

> 合并自 2 个原 playbook 文件。

---

## Debug Playbook: Bandwidth High

### 0. 适用范围

### 适用

- GPU 带宽指标（memory bandwidth、texture bandwidth、attachment bandwidth）持续高位。
- 帧时间高且降低 texture 分辨率 / 关闭 MSAA / 减少 MRT 后明显改善。
- Profiler 显示 `Bandwidth` / `Bytes/Pixel` / `Texture Cache Miss` 偏高。
- 移动设备发热严重、续航下降，怀疑带宽是主因。

### 不适用

- 纯 ALU / compute 瓶颈（带宽正常但 frame time 高）。
- CPU 与 GPU 之间 PCIe / 总线传输瓶颈（优先看 staging / upload 策略）。
- 网络或磁盘 IO 导致的带宽问题。

---

### 1. 现象

- GPU memory bandwidth counter 接近或超过设备峰值。
- 降低 texture / render target 分辨率后帧时间显著下降。
- 开启 MSAA / 增加 MRT 后帧时间非线性上升。
- 透明 pass、后处理 pass、粒子系统带宽占用高。
- 移动设备快速发热、电池消耗大。

---

### 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Texture 采样带宽过高 | `Texture Fetch` / `Texture Cache Miss` 高；降低 texture 分辨率帧时间下降 | Image / Sampler / Shader |
| P0 | Render target / attachment 写带宽高 | `Color/Depth Bandwidth` 高；降低分辨率 / 关闭 MSAA 后改善 | Attachment / Image |
| P0 | Buffer 读写带宽高 | `Buffer Bandwidth` 高；大量 SSBO / UBO / indirect draw 数据未命中 cache | Buffer / Descriptor |
| P1 | 未使用压缩格式 | Texture / attachment 使用未压缩或 32 位浮点格式；改为压缩格式后带宽下降 | Image / Format |
| P1 | 频繁 Resolve / Copy | MSAA resolve、blit、copy 次数多；中间 render target 多 | Image / Command Buffer |
| P1 | MRT / MSAA 过度使用 | `MRT` / `Samples` 数超过场景需求 | Render Pass / Attachment |
| P2 | 不合理的 sampler filter / LOD | 使用各向异性过滤、三线性过滤、负 LOD bias 增加采样量 | Sampler |

---

### 3. 快速验证路径

1. **用 GPU Profiler 查看 bandwidth counter**，确认是 texture、attachment 还是 buffer 带宽高。`[TOOL]`
2. **降低所有 texture 分辨率 50%**：若帧时间明显下降，瓶颈在 texture 采样。`[TOOL]`
3. **降低 render target 分辨率或关闭 MSAA**：若帧时间明显下降，瓶颈在 attachment 带宽。`[TOOL]`
4. **用压缩格式替换未压缩 texture**：观察带宽和帧时间变化。`[TOOL]`
5. **统计每帧 blit / copy / resolve 次数**：减少不必要的中间 buffer / image 拷贝。`[TOOL]`
6. **检查 fragment shader 中 texture 采样次数和 filter 模式**。`[TOOL]`

---

### 4. Vulkan 对象链路排查

```text
Texture / Buffer / Attachment
→ Sampler / ImageView / Format
→ Shader 采样 / Load / Store
→ Render Pass Attachment
→ Resolve / Blit / Copy
→ Present
```

逐项检查：

- Texture 格式是否使用 ASTC / BC / ETC2 等压缩格式（视平台支持）。`[HEUR]`
- Texture 分辨率是否超出屏幕像素密度需求。`[HEUR]`
- Sampler 是否使用 anisotropic / trilinear 等高开销 filter。`[HEUR]`
- Render target 分辨率、format（如 `RGBA32F` vs `RGBA8`）、MSAA 级别。`[HEUR]`
- Depth / stencil attachment 格式和精度是否过高。`[HEUR]`
- 每帧 MRT 数量和每个 target 的 bit depth。`[HEUR]`
- 是否存在大量 `vkCmdCopyImage`、`vkCmdBlitImage`、`vkCmdResolveImage`。`[TOOL]`
- SSBO / UBO / indirect buffer 访问模式是否 cache friendly。`[ENGINE]`

---

### 5. 高频根因

1. 4K / 2K texture 大量采样，且未启用 mipmap 或各向异性过滤过度。`[ENGINE]`
2. Render target 使用 `RGBA32F` 或 `R32G32B32A32` 等未压缩高精度格式。`[ENGINE]`
3. MSAA 4x / 8x 与 heavy overdraw 叠加，颜色 / 深度带宽成倍增长。`[ENGINE]`
4. 后处理链路过长，每个 pass 都读写 fullscreen attachment。`[ENGINE]`
5. 缺少 attachment 压缩（如 ARM AFBC、Qualcomm UBWC）或未使用 tile-based 优势。`[ANDROID]`
6. 频繁在 GPU 内存与 CPU 可见内存之间 copy buffer。`[ENGINE]`
7. Particle / decal 使用 alpha test 或 heavy texture array 采样，导致随机访问 cache miss。`[ENGINE]`

---

### 6. 修复方案

### 最小修复

- 对高带宽 texture：降低分辨率、启用 mipmap、使用压缩格式。`[HEUR]`
- 对高带宽 attachment：降低 render target 分辨率、使用 16 位或 11-11-10 格式、关闭不必要的 MSAA。`[HEUR]`
- 合并相邻 fullscreen pass，减少中间 attachment 读写。`[ENGINE]`
- 移除不必要的 `vkCmdCopyImage` / `vkCmdBlitImage` / `vkCmdResolveImage`。`[ENGINE]`

### 稳定修复

- 建立 texture 导入管线，按平台自动选择 ASTC / BC / ETC2 格式和 mipmap。`[ENGINE]`
- 建立 render target 池，根据画质等级自动选择分辨率、format、MSAA。`[ENGINE]`
- 对后处理使用 subpass input attachment 或 tile-based 本地读取，减少全局内存读写。`[ANDROID]`
- 对 MSAA 使用 custom resolve 或降低 sample 数。`[HEUR]`
- 对 UBO / SSBO 使用 cache-friendly 布局和合并访问。`[ENGINE]`

### 工程化修复

- CI 集成 bandwidth counter 自动检测，设定 per-pass / per-frame 带宽预算。`[TOOL]`
- 在低端设备上启用 aggressive 画质降级：低分辨率 texture、低精度 attachment、无 MSAA。`[ENGINE]`
- 使用 framebuffer compression 和 memoryless attachment（若平台支持 `VK_ANDROID_external_memory_android_hardware_buffer` 或 `VK_EXT_image_drm_format_modifier` 等）。`[ANDROID]`
- 建立 bandwidth-driven LOD 系统，根据运行时带宽动态调整。`[ENGINE]`

---

### 7. 回归验证

- [ ] GPU bandwidth counter 回到合理范围。
- [ ] 帧时间满足目标预算。
- [ ] 画面质量在可接受范围内。
- [ ] 不同分辨率 / 画质等级下带宽策略生效。
- [ ] 移动设备发热和耗电改善。
- [ ] 未引入 image layout / sync hazard / format 不兼容问题。

---

### 8. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`

---

### 9. 工具证据

### Validation Layer

- Validation 本身不直接测量带宽，但关注 format / usage / image layout 错误是否影响压缩格式使用。`[TOOL]`
- 关注 `VUID-vkCreateImage-format-...` 等与 format capability 相关的错误。`[TOOL]`

### RenderDoc

- 查看 texture / attachment 的格式、分辨率、MSAA 设置。`[TOOL]`
- 查看每个 pass 的 input / output attachment，识别冗余读写。`[TOOL]`
- 查看 shader 中 texture 采样次数和 sampler 设置。`[TOOL]`
- 使用 RenderDoc 的 statistics 面板查看 draw call 数和 resource 大小。`[TOOL]`

### AGI / Android

- 关注 `Memory Bandwidth`、`Texture Bandwidth`、`Color Bandwidth`、`Depth Bandwidth`。`[TOOL]`
- 查看 `Texture Cache Miss Rate`、`Bytes/Pixel`、`MRT Count`。`[TOOL]`
- 使用 AGI 的 framebuffer / texture 视图检查压缩格式是否生效。`[TOOL]`
- 观察带宽与 frame time 的对应关系。`[TOOL]`

### logcat

- 搜索 `thermal`、`throttling` 判断高带宽是否导致降频。`[ANDROID]`
- 检查是否有 format / compression 相关驱动警告。`[ANDROID]`

---

### 10. Android 分支

Android 上带宽与 tile-based GPU、功耗、Surface 生命周期强相关，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且尺寸稳定；surface 异常重建会导致 attachment 尺寸变化和带宽突增。`[ANDROID]`
2. **Tile-based GPU 本地读取**：Adreno / Mali 上尽量使用 subpass / input attachment 在 tile memory 内读取，避免写回 system memory 再读。`[ANDROID]`
3. **Framebuffer compression**：确认是否启用 ARM AFBC、Qualcomm UBWC 等；未压缩的 attachment 会显著增加带宽。`[ANDROID]`
4. **Swapchain 分辨率**：Android 设备分辨率多样，建议根据性能动态调整 swapchain / render target 分辨率。`[ANDROID]`
5. **Texture 压缩格式**：优先使用 ASTC（Adreno / Mali 均支持），ETC2 作为 fallback；避免未压缩 RGBA8。`[ANDROID]`
6. **Present mode 与功耗**：`FIFO` 模式下固定刷新率有助于稳定带宽；`MAILBOX` / `IMMEDIATE` 可能增加功耗。`[SPEC]`
7. **后台 / 分屏**：进入后台或分屏时 `ANativeWindow` 尺寸变化，应降低渲染负载。`[ANDROID]`

---

### 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - GPU Profiler 带宽 counter 截图（RenderDoc / AGI / NVIDIA Nsight / Radeon GPU Profiler）。
   - 每帧 texture / attachment / buffer 带宽分布。
   - Texture 总分辨率、格式、mipmap 情况。
   - Render target 分辨率、format、MSAA、MRT 数量。
   - 每帧 copy / blit / resolve 次数和尺寸。
   - Fragment shader 中采样次数和 sampler 配置。
   - 设备型号、GPU、驱动版本、Android 版本。
   - 是否启用 texture 压缩、AFBC / UBWC、dynamic resolution。
3. 给出最小验证路径：降低 texture 分辨率 → 降低 render target 分辨率 → 关闭 MSAA → 合并 pass。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 format capability 或 present mode 规范。
   - `[TOOL]` 若 Profiler 已给出明确带宽证据。
   - `[ENGINE]` 若基于资源管线和画质分级经验推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 tile-based GPU、压缩格式或 Surface 生命周期。


---

## Debug Playbook: Fullscreen Pass Cost

### 0. 适用范围

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

### 1. 现象

- 单个或少数几个 fullscreen draw 占据整帧较大比例 GPU 时间。
- 降低 output resolution 后该 pass 时间明显下降。
- Fragment shader 复杂度高，采样次数多，ALU 运算重。
- 每个 fullscreen pass 都读写 fullscreen attachment，带宽叠加。
- 移动端 tile-based GPU 上 fullscreen pass 后出现明显 tile flush 或 bandwidth 峰值。

---

### 2. 最可能原因排序

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

### 3. 快速验证路径

1. **用 Profiler 定位耗时 fullscreen pass**，查看其 GPU duration。`[TOOL]`
2. **把该 pass 的 fragment shader 替换为简单输出**：若时间大幅下降，瓶颈在 shader。`[TOOL]`
3. **降低 fullscreen pass 输出分辨率 50%**：若时间近似减半，瓶颈在 fragment / ROP / 带宽。`[TOOL]`
4. **合并相邻 fullscreen pass**：减少中间 attachment 读写。`[TOOL]`
5. **检查 fragment shader 中 texture 采样次数和 filter 模式**。`[TOOL]`
6. **在 mobile 上检查是否可用 subpass input attachment 替代 texture 采样**。`[ANDROID]`

---

### 4. Vulkan 对象链路排查

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

### 5. 高频根因

1. Fragment shader 中多次采样 full-resolution texture 做复杂后处理（如 SSR、SSAO、DOF、bloom 合并）。`[ENGINE]`
2. 每个后处理 pass 都输出到独立 fullscreen RT，再被下一 pass 采样，带宽成倍增加。`[ENGINE]`
3. 未使用 mipmap 或降低分辨率做模糊 / bloom，导致大量 full-resolution 采样。`[ENGINE]`
4. 未按 mobile tile-based 架构优化，未使用 subpass / input attachment。`[ANDROID]`
5. Fullscreen pass 使用高精度 attachment（`RGBA16F` / `RGBA32F`）但画质收益有限。`[ENGINE]`
6. 多个 UI 全屏层叠，每层都独立绘制并混合。`[ENGINE]`
7. 未开启 early-z 或 depth test 优化 fullscreen pass（部分后处理可利用 stencil 剔除）。`[HEUR]`

---

### 6. 修复方案

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

### 7. 回归验证

- [ ] 目标 fullscreen pass GPU time 回到预算内。
- [ ] 合并 / 降采样后画面质量在可接受范围。
- [ ] 未引入 image layout / sync hazard。
- [ ] Mobile 设备上发热和带宽改善。
- [ ] 不同画质等级 / 分辨率下 fullscreen pass 开销可控。
- [ ] resize / rotation 后动态分辨率策略仍生效。

---

### 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

### 9. 工具证据

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

### 10. Android 分支

Android 上 fullscreen pass 与 tile-based GPU、Surface 生命周期、功耗密切相关，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且尺寸稳定；surface 重建后 fullscreen pass 的 attachment 尺寸需同步更新。`[ANDROID]`
2. **Tile-based GPU 本地读取**：Adreno / Mali 上应优先使用 subpass / input attachment 在 tile memory 内读取前序 pass 输出，避免写回 system memory 再采样。`[ANDROID]`
3. **Attachment 压缩**：确认 fullscreen attachment 是否启用 AFBC / UBWC；未压缩的 16F / 32F attachment 会大幅增加带宽。`[ANDROID]`
4. **Dynamic resolution**：Android 设备分辨率多样，建议 fullscreen pass 输出使用可调整的 render target 分辨率，而非固定 native resolution。`[ANDROID]`
5. **Present 前最终 pass**：最终 fullscreen pass 到 swapchain 之间尽量减少额外 layout transition 和 barrier，直接输出到 `COLOR_ATTACHMENT_OPTIMAL` 然后 transition 到 `PRESENT_SRC_KHR`。`[SPEC]`
6. **UI 层管理**：Android 上 UI 全屏层叠常见，应 batch 和剔除隐藏层，减少重复 fullscreen blend。`[ANDROID]`
7. **后台 / 分屏**：`ANativeWindow` 尺寸变化或应用进入后台时，应降低或跳过非关键 fullscreen pass。`[ANDROID]`

---

### 11. 不确定时如何处理

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


---

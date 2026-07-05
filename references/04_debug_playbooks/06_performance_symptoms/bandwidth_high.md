# Debug Playbook: Bandwidth High

## 0. 适用范围

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

## 1. 现象

- GPU memory bandwidth counter 接近或超过设备峰值。
- 降低 texture / render target 分辨率后帧时间显著下降。
- 开启 MSAA / 增加 MRT 后帧时间非线性上升。
- 透明 pass、后处理 pass、粒子系统带宽占用高。
- 移动设备快速发热、电池消耗大。

---

## 2. 最可能原因排序

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

## 3. 快速验证路径

1. **用 GPU Profiler 查看 bandwidth counter**，确认是 texture、attachment 还是 buffer 带宽高。`[TOOL]`
2. **降低所有 texture 分辨率 50%**：若帧时间明显下降，瓶颈在 texture 采样。`[TOOL]`
3. **降低 render target 分辨率或关闭 MSAA**：若帧时间明显下降，瓶颈在 attachment 带宽。`[TOOL]`
4. **用压缩格式替换未压缩 texture**：观察带宽和帧时间变化。`[TOOL]`
5. **统计每帧 blit / copy / resolve 次数**：减少不必要的中间 buffer / image 拷贝。`[TOOL]`
6. **检查 fragment shader 中 texture 采样次数和 filter 模式**。`[TOOL]`

---

## 4. Vulkan 对象链路排查

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

## 5. 高频根因

1. 4K / 2K texture 大量采样，且未启用 mipmap 或各向异性过滤过度。`[ENGINE]`
2. Render target 使用 `RGBA32F` 或 `R32G32B32A32` 等未压缩高精度格式。`[ENGINE]`
3. MSAA 4x / 8x 与 heavy overdraw 叠加，颜色 / 深度带宽成倍增长。`[ENGINE]`
4. 后处理链路过长，每个 pass 都读写 fullscreen attachment。`[ENGINE]`
5. 缺少 attachment 压缩（如 ARM AFBC、Qualcomm UBWC）或未使用 tile-based 优势。`[ANDROID]`
6. 频繁在 GPU 内存与 CPU 可见内存之间 copy buffer。`[ENGINE]`
7. Particle / decal 使用 alpha test 或 heavy texture array 采样，导致随机访问 cache miss。`[ENGINE]`

---

## 6. 修复方案

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

## 7. 回归验证

- [ ] GPU bandwidth counter 回到合理范围。
- [ ] 帧时间满足目标预算。
- [ ] 画面质量在可接受范围内。
- [ ] 不同分辨率 / 画质等级下带宽策略生效。
- [ ] 移动设备发热和耗电改善。
- [ ] 未引入 image layout / sync hazard / format 不兼容问题。

---

## 8. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`

---

## 9. 工具证据

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

## 10. Android 分支

Android 上带宽与 tile-based GPU、功耗、Surface 生命周期强相关，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且尺寸稳定；surface 异常重建会导致 attachment 尺寸变化和带宽突增。`[ANDROID]`
2. **Tile-based GPU 本地读取**：Adreno / Mali 上尽量使用 subpass / input attachment 在 tile memory 内读取，避免写回 system memory 再读。`[ANDROID]`
3. **Framebuffer compression**：确认是否启用 ARM AFBC、Qualcomm UBWC 等；未压缩的 attachment 会显著增加带宽。`[ANDROID]`
4. **Swapchain 分辨率**：Android 设备分辨率多样，建议根据性能动态调整 swapchain / render target 分辨率。`[ANDROID]`
5. **Texture 压缩格式**：优先使用 ASTC（Adreno / Mali 均支持），ETC2 作为 fallback；避免未压缩 RGBA8。`[ANDROID]`
6. **Present mode 与功耗**：`FIFO` 模式下固定刷新率有助于稳定带宽；`MAILBOX` / `IMMEDIATE` 可能增加功耗。`[SPEC]`
7. **后台 / 分屏**：进入后台或分屏时 `ANativeWindow` 尺寸变化，应降低渲染负载。`[ANDROID]`

---

## 11. 不确定时如何处理

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

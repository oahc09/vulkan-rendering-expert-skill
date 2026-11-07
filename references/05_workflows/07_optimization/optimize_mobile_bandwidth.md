# Workflow: Optimize Mobile Bandwidth

## 0. 适用范围

### 适用

- 移动端（Android）渲染性能优化，关注 GPU memory bandwidth。
- 需要优化 attachment format、compression、MSAA、MRT、fullscreen pass、load/store。
- 目标为具有 tile-based 渲染路径的移动 GPU；具体架构/工作模式与能力按设备核实，不仅凭 Adreno/Mali/PowerVR 品牌判断。

### 不适用

- 非移动端任务可复用测量方法，但不能预先排除桌面 GPU 的带宽瓶颈。
- 纯 compute / headless 无 color/depth attachment 的场景。
- 尚未保证渲染正确性的工程（先解决 validation / sync）。

---

## 1. 任务目标

降低移动端 GPU memory bandwidth：

```text
High bandwidth render targets / fullscreen passes
→ Format selection / compression / tile-friendly resolve
→ Optimized load/store / MSAA / MRT
→ Bandwidth-efficient postprocess chain
```

---

## 2. 输入条件

需要确认：

- 目标 GPU：Adreno / Mali / PowerVR / 其他。
- 屏幕分辨率、target frame rate。
- 当前 render target 格式与 bit depth。
- 是否使用 MSAA、MRT、postprocess、deferred shading。
- 是否支持 ASTC / ETC2 / BC 压缩。
- 是否支持 `VK_KHR_depth_stencil_resolve`、`VK_EXT_fragment_density_map` 等扩展。
- 是否使用 subpass / render pass 或 dynamic rendering。
- AGI / Snapdragon Profiler / Mali Offline Compiler 是否可用。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] 记录可用 profiler / timestamp / trace；Mali Offline Compiler 仅提供离线 shader 分析，不是运行时带宽采集器。
- [ ] 若设备/工具提供对应 counter，采集 bandwidth baseline；否则明确带宽未测，不阻止其他定位。
- [ ] 已确认目标压缩格式受支持。
- [ ] 已确认 MSAA sample count 与 resolve 路径。
- [ ] 已确认 load/store op 设置合理。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Swapchain Image / Offscreen Attachment
→ VkRenderPass / VkRenderingInfo
→ VkPipeline (color/depth format, sample count)
→ VkFramebuffer / Image Views
→ Load/Store Op + Multisample Resolve
→ Tile Memory (on TBDR)
→ Present / Next Pass
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| color attachment | `VkImage` | `COLOR_ATTACHMENT` | per-frame / per-pass | 是（若尺寸相关） |
| depth attachment | `VkImage` | `DEPTH_STENCIL_ATTACHMENT` | per-frame / per-pass | 是 |
| resolve attachment | `VkImage` | `COLOR_ATTACHMENT` | per-frame | 是 |
| multisample attachment | `VkImage` | `TRANSIENT_ATTACHMENT | COLOR_ATTACHMENT` | per-frame | 是 |
| compressed texture | `VkImage` | `SAMPLED` | scene | 否 |
| framebuffer | `VkFramebuffer` | 绑定 attachments | per-pass | 是 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` | compressed scene texture | Fragment |
| set=1,binding=0 | `INPUT_ATTACHMENT` | subpass-local G-Buffer | Fragment |
| push constant | `VkPushConstantRange` | exposure / bloom params | Fragment |

Pipeline 状态：

- color attachment format 尽量选 lower bit-depth（如 `R10G10B10A2_UNORM` 替代 `R16G16B16A16_SFLOAT` 若精度足够） [ANDROID]。
- depth format 优先 `D16_UNORM` 或 `D24_UNORM_S8_UINT`；仅在需要精度时用 `D32_SFLOAT` [ANDROID]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| G-Buffer pass | MRT attachments | `COLOR_ATTACHMENT_OPTIMAL`，subpass dependency | lighting subpass |
| lighting subpass | lit color | `COLOR_ATTACHMENT_OPTIMAL` → resolve | resolve / present |
| postprocess | fullscreen input | `SHADER_READ_ONLY_OPTIMAL` | fullscreen fragment |
| postprocess | output | `COLOR_ATTACHMENT_OPTIMAL` | present |

必须说明：

- TBDR GPU 上，正确的 framebuffer-local subpass dependency 可为 tile-local 实现提供条件，但不保证 G-Buffer 一定片上驻留或不写回 [SPEC][ENGINE]。
- `TRANSIENT_ATTACHMENT` 与受支持的 `LAZILY_ALLOCATED` memory 是可选策略；仅在内容生命周期允许时丢弃，带宽收益需要实测，不是规范保证 [SPEC][ENGINE]。
- fullscreen pass 的输入/输出应尽量减少大尺寸 FP16 attachment，使用 `R11G11B10_UFLOAT` 等紧凑 HDR format [HEUR]。

---

## 8. 实现步骤

1. **测量 baseline bandwidth**：使用 AGI / Snapdragon Profiler 抓取典型场景，记录 read/write bytes per frame、各 attachment 占比 [TOOL]。
2. **选择合适 attachment format**：
   - LDR color：`R8G8B8A8_UNORM` 或 `B8G8R8A8_UNORM`；
   - HDR color：`R11G11B10_UFLOAT` 或 `R10G10B10A2_UNORM`（精度足够时）；
   - Normal：`R8G8B8A8_SNORM` 或 `R16G16_SNORM`；
   - Depth：优先 `D16_UNORM` 或 `D24_UNORM_S8_UINT` [ANDROID]。
3. **启用纹理压缩**：
   - ASTC（Adreno/Mali 支持好）用于 diffuse / normal；
   - ETC2 作为 fallback；
   - 调用 `vkGetPhysicalDeviceFormatProperties` 确认支持 [ANDROID]。
4. **优化 MSAA**：
   - 仅在必要时使用 MSAA；移动端常用 2x 或 4x；
   - 使用 `VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` + `LAZILY_ALLOCATED` memory 存储 multisample attachment；
   - 在 subpass 中通过 `pResolveAttachments` 解析到 single-sample image [SPEC]。
5. **优化 MRT / deferred shading**：
   - 减少 G-Buffer 通道数量与 bit depth；
   - 评估 subpass 将 G-Buffer 生成与 lighting 放在同一 render pass；是否减少写回由目标设备测量确认 [ENGINE]。
6. **优化 load/store op**：
   - 首 pass color：`LOAD_OP_CLEAR` 或 `LOAD_OP_DONT_CARE`；
   - 中间 pass color/depth：`LOAD_OP_LOAD` / `STORE_OP_STORE` 仅在需要时；
   - 最终 present color：`STORE_OP_STORE`；
   - transient MSAA：`STORE_OP_DONT_CARE` [SPEC]。
7. **优化 fullscreen pass**：
   - 合并后处理：bloom + tone mapping + color grading 尽量在一个 fullscreen pass 完成 [HEUR]；
   - 使用 half-resolution 输入（如 bloom）降低带宽 [HEUR]；
   - 避免多次全屏采样 4K offscreen texture [ANDROID]。
8. **利用 subpass input attachment**：deferred lighting 可用同像素 input attachment 依赖；是否片上实现及收益需测量，不替代任意邻域纹理采样 [SPEC][ENGINE]。
9. **评估降分辨率渲染**：对不透明场景使用 `VK_KHR_fragment_shading_rate` 或动态 resolution scale，降低 fragment 与 bandwidth 开销 [ANDROID]；需评估画质损失。
10. **验证 bandwidth 改善**：AGI 中比较优化前后 read/write bandwidth、frame time、GPU active time [TOOL]。
11. **接入 resize / recreate**：format / sample count / resolution 选择逻辑在 swapchain recreate 时重新评估；确保新 surface extent 下带宽仍达标。
12. **接入销毁路径**：MSAA / transient attachment 在 swapchain 相关资源销毁时一并释放。

---

## 9. Android 注意点

- `ANativeWindow` / `VkSurfaceKHR` 创建后才能确定 surface format 与 extent；format 选择（如 `BGRA8` vs `RGBA8`）影响 bandwidth，需在 surface 创建后决策 [ANDROID]。
- rotation / resize 改变 extent 后，attachment 尺寸与 bandwidth 预算需重新计算；必要时动态调整 resolution scale。
- pause / resume 不自动释放 transient attachment；由应用在相关提交完成后退休，按实际尺寸变化决定是否重建。
- 不同内容和设备对 compression 的质量/成本不同；ASTC block size 按内容误差、支持能力与实测选择，不按品牌固定 [ENGINE]。
- TBDR 上 `STORE_OP_STORE` 的 attachment 数量直接影响 external memory bandwidth；尽量减少需要 store 的 attachment [ANDROID]。
- AGI / logcat 验证：关注 `GPU Memory Read/Write`、`External Memory Bandwidth`、各 render target 读写量。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 attachment format、load/store op、sample count 相关错误 [TOOL]。
- [ ] 可用的运行时 GPU profiler（离线 compiler 不能代替这些计数）：
  - 优化前/后 bandwidth 数值对比；
  - 各 attachment read/write 量；
  - tile memory 利用率 [TOOL]。
- [ ] 截图 / 画质评估：压缩、降采样、format 变更后画面质量可接受。
- [ ] logcat（Android）：无 validation error；可输出当前 format、sample count、resolution scale。
- [ ] 性能指标：
  - GPU 每帧 bandwidth（MB）下降；
  - frame time 在目标设备上满足预算；
  - GPU active % 合理，无长时间 stall [TOOL]。
- [ ] resize / pause / resume / rotation 后带宽优化策略仍生效。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 artifact。

---

## 11. 常见失败模式

1. **Format 精度不足**：HDR 用 `R11G11B10_UFLOAT` 导致 banding，需根据内容选择 [HEUR]。
2. **压缩格式不支持**：未检查 `vkGetPhysicalDeviceFormatProperties`，在部分设备上回退到未压缩导致带宽暴涨 [ANDROID]。
3. **MSAA 策略未经验证**：普通内存路径不因此非法；transient/lazy 是否可用及有收益需单独验证 [SPEC][ENGINE]。
4. **Store op 设置不当**：中间 depth 用 `STORE_OP_STORE` 但实际不需要，浪费带宽 [SPEC]。
5. **Dependency 与访问不匹配**：检查 framebuffer-local 依赖；缺少 BY_REGION 不能直接推导必然写回或带宽倍增 [SPEC][ENGINE]。
6. **Fullscreen pass 过多**：每个后处理一个 fullscreen pass，重复读写全屏 texture [HEUR]。
7. **MRT 通道过宽**：normal 用 `R16G16B16A16_SFLOAT` 而非 `R8G8B8A8_SNORM`，大幅增加 bandwidth [HEUR]。
8. **Android rotation 后未调整 resolution scale**：新 extent 下性能预算变化，仍用旧 scale导致掉帧 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标 GPU（Adreno / Mali / PowerVR / 具体型号）。
- 当前 attachment format、bit depth、sample count。
- AGI / Profiler 抓帧的 bandwidth 数据。
- Render pass / subpass 结构图。
- 纹理格式与压缩策略。
- Android lifecycle 日志。

<a id="mobile-tile-choice"></a>
## 15. Tile-aware 路径选择与标准回退

先按 [Mobile Tile Rendering](../../03_api_manual/07_rendering/mobile_tile_rendering.md#tile-access-patterns) 区分同像素附件、邻域采样、storage、MSAA 与depth/stencil；不是所有后处理都可迁移local read。
保留现有 RenderPass/subpass 或普通 texture pass 作为 standard path；dynamic local read 与 QCOM tile 能力按支持、启用、properties、资源寿命逐项选择。
Vulkan 1.4 不保证全部 depth/MSAA local read，QCOM tile heap 也不等于普通 transient/lazy attachment。

A/B 固定输入、分辨率、画质、刷新率与热状态；比较图像误差、GPU时间分布、显存与实际可用带宽counter。
计数器不可得就写未测，不从“Compute”“subpass”“local read”名称预填收益。缺少能力或回归失败立即选标准路径，不要求更换GPU或提高项目最低Vulkan版本。[ENGINE]


<a id="coverage-budget"></a>
## 透明与 Gaussian 屏幕覆盖预算（C4）

适用透明/局部雾/GS 的质量与性能选择，不用点数代替实际工作。输入固定资源 hash、seed、camera path、曝光/分辨率/质量档、设备/OS/driver/features 与热状态；输出分阶段时耗、覆盖估计、内存峰值、误差和有条件回退。[ENGINE]

先用低侵入 timestamp 和计算估计，再按需启用原子重诊断。查询 queue family timestampValidBits、timestampPeriod 和可用阶段；处理计数 wrap、availability、CPU/GPU 时域区别。并行 queue 的区间不能相加伪装帧时间。不可用的硬件 counter 标 UNMEASURED。

| 记录 | 解释与边界 |
|---|---|
| visible primitives/GS、projected-size buckets | 数量与分布，不是着色成本 |
| clipped quad/ellipse footprint、tile coverage | 不同估计量，不能叫硬件 fragment invocation |
| unique covered pixels、层数 histogram/p95/max | 方法、sample/cutoff、原子开销与饱和/溢出单列 |
| projection、sort、raster、resolve GPU time；CPU submit/upload | 优化主攻方向，包含生产路径的同步等待 |
| intermediate images/OIT pool/sort scratch/upload/驻留峰值 | 含 frames-in-flight 与新旧 generation 并存 |
| linear color、alpha/T error 与相机序列 pop/闪烁 | 先冻结容差；单帧 PSNR 不足 |

基础档为合法排序 blend、单层折射、有限局部雾与 instanced splats，不强制 RGBA8。平衡档在 format/误差/内存允许时启用 FP16、WBOIT、低分辨率雾和保守背景 LOD。增强档的 bounded lists/interlock/条件排序复用逐项能力和证据门控，不按 GPU 品牌硬编码。失去能力/容量/质量预算立即回退并记录原因，旧资源按最后完成点退休。[ENGINE]

背景 LOD/合并只在远景低视差、高重叠且内容证据支持时研究；保留前景、轮廓、运动、视差结构。点数下降但剩余 footprint 变大可更慢。参数简单平均不保持 radiance/transmittance，需相同相机序列、视点变化和背景颜色下对照，分别报告点数、coverage、排序/光栅成本、误差与内存。

A/B 固定可见内容、曝光、实际分辨率、质量、camera、seed 与持续热状态；记录 cold/warm、p50/p95/p99、内存峰值与真实渲染/呈现/生成帧。删内容、降低层数或改曝光是另一个实验，不算等质量加速；重诊断帧时间不冒充生产帧时间。无功耗工具不称节电，无 Adreno/Mali 实机只称已测实现。容量/采样/内存/时间安全阈值预设，中止保留结果，不无限压力运行。

验证两个独立轴：固定点数改变 footprint、固定覆盖改变点数；再比较低/高层数、RGBA8/受支持 FP16、背景/前景 LOD。细分 Static/host_unit/shader_unit/vulkan_integration/Live/Host/mobile_visual/mobile_performance/Package；未执行不继承旧 PASS。

[REF] [Gaussian rasterization](https://nvpro-samples.github.io/vk_gaussian_splatting/deep-dives/rasterization_of_3d_gaussian_splatting/)；[SPEC] [Queries](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc)。

# Workflow: Optimize Mobile Bandwidth

## 0. 适用范围

### 适用

- 移动端（Android）渲染性能优化，关注 GPU memory bandwidth。
- 需要优化 attachment format、compression、MSAA、MRT、fullscreen pass、load/store。
- 目标设备为 tile-based deferred rendering（TBDR）GPU：Adreno、Mali、PowerVR。

### 不适用

- 桌面端 GPU 带宽通常不是首要瓶颈，部分建议可参考但不作为核心目标。
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
- 是否支持 `VK_KHR_depth_stencil_resolve`、`VK_EXT_fragment_density_overlay` 等扩展。
- 是否使用 subpass / render pass 或 dynamic rendering。
- AGI / Snapdragon Profiler / Mali Offline Compiler 是否可用。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] AGI / Snapdragon Profiler / Mali Offline Compiler 至少一种可用。
- [ ] 已统计当前 frame 的 attachment bandwidth（AGI Bandwidth counter）。
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

- TBDR GPU 上，subpass dependency 配合 `BY_REGION_BIT` 可让 G-Buffer 保持在 tile memory 中，避免写回 system memory [ANDROID]。
- `TRANSIENT_ATTACHMENT` + `LAZY` allocation 的 MSAA color/depth 在 tile memory 中解析，解析后丢弃，显著降低带宽 [SPEC]。
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
   - 使用 subpass 将 G-Buffer 生成与 lighting 放在同一 render pass，避免写回 system memory [ANDROID]。
6. **优化 load/store op**：
   - 首 pass color：`LOAD_OP_CLEAR` 或 `LOAD_OP_DONT_CARE`；
   - 中间 pass color/depth：`LOAD_OP_LOAD` / `STORE_OP_STORE` 仅在需要时；
   - 最终 present color：`STORE_OP_STORE`；
   - transient MSAA：`STORE_OP_DONT_CARE` [SPEC]。
7. **优化 fullscreen pass**：
   - 合并后处理：bloom + tone mapping + color grading 尽量在一个 fullscreen pass 完成 [HEUR]；
   - 使用 half-resolution 输入（如 bloom）降低带宽 [HEUR]；
   - 避免多次全屏采样 4K offscreen texture [ANDROID]。
8. **利用 subpass input attachment**：deferred lighting 直接从 tile memory 读 G-Buffer，避免采样 offscreen texture [ANDROID]。
9. **评估降分辨率渲染**：对不透明场景使用 `VK_EXT_fragment_shading_rate` 或动态 resolution scale，降低 fragment 与 bandwidth 开销 [ANDROID]；需评估画质损失。
10. **验证 bandwidth 改善**：AGI 中比较优化前后 read/write bandwidth、frame time、GPU active time [TOOL]。
11. **接入 resize / recreate**：format / sample count / resolution 选择逻辑在 swapchain recreate 时重新评估；确保新 surface extent 下带宽仍达标。
12. **接入销毁路径**：MSAA / transient attachment 在 swapchain 相关资源销毁时一并释放。

---

## 9. Android 注意点

- `ANativeWindow` / `VkSurfaceKHR` 创建后才能确定 surface format 与 extent；format 选择（如 `BGRA8` vs `RGBA8`）影响 bandwidth，需在 surface 创建后决策 [ANDROID]。
- rotation / resize 改变 extent 后，attachment 尺寸与 bandwidth 预算需重新计算；必要时动态调整 resolution scale。
- pause / resume 期间 transient attachment 会被释放，恢复后按新 surface 重新分配。
- 不同 GPU 对 compression 支持不同：Adreno 推荐 ASTC 6x6 / 8x8；Mali 推荐 ASTC 4x4 / 6x6；需按目标设备分级 [ANDROID]。
- TBDR 上 `STORE_OP_STORE` 的 attachment 数量直接影响 external memory bandwidth；尽量减少需要 store 的 attachment [ANDROID]。
- AGI / logcat 验证：关注 `GPU Memory Read/Write`、`External Memory Bandwidth`、各 render target 读写量。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 attachment format、load/store op、sample count 相关错误 [TOOL]。
- [ ] AGI / Snapdragon Profiler / Mali Offline Compiler：
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
3. **MSAA resolve 路径错误**：multisample attachment 未使用 `TRANSIENT_ATTACHMENT` + `LAZILY_ALLOCATED`，写回 system memory [SPEC]。
4. **Store op 设置不当**：中间 depth 用 `STORE_OP_STORE` 但实际不需要，浪费带宽 [SPEC]。
5. **Subpass dependency 未加 `BY_REGION_BIT`**：G-Buffer 数据被强制写回系统内存，lighting pass 再读回，带宽倍增 [ANDROID]。
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

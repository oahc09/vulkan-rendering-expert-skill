# Workflow: Reduce Pipeline Creation Stutter

## 0. 适用范围

### 适用

- 运行时创建 `VkPipeline` 导致 frame time spike 或卡顿。
- 需要优化 startup loading 阶段大量 pipeline 编译时间。
- 需要实现 pipeline cache 持久化、异步编译、derivative pipeline、pre-warm、specialization constants。
- 目标平台包括 Android（移动 GPU）与桌面端。

### 不适用

- Pipeline 全部在启动时一次性创建且总量很小的程序（stutter 不明显）。
- 使用 runtime shader compilation 直接生成 SPIR-V 的复杂引擎（需额外处理 shader cache）。
- 完全不关心 startup 时间和运行时卡顿的离线 / 非实时渲染场景。

---

## 1. 任务目标

降低 pipeline 创建带来的卡顿：

```text
Cold Pipeline Creation (blocking, slow)
→ Pipeline Cache (disk + memory)
→ Startup Pre-warm (blocking but expected)
→ Runtime Async Compile (non-blocking fallback)
→ Derivative Pipeline (faster variant)
→ Specialization Constants (fewer pipelines)
→ Smooth Frame Time
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 当前 pipeline 创建耗时（首创建 vs cache hit）。
- Pipeline 总量与变体数量。
- 是否使用 `VkPipelineCache`。
- 是否有后台线程可用于异步编译。
- 是否支持 `VK_EXT_graphics_pipeline_library`（GPL）。
- 是否支持 `VK_KHR_pipeline_executable_properties` 用于分析。
- Swapchain recreate 时是否需要重建 pipeline（通常不需要，除非 render pass format 改变）。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI / Nsight 可抓帧。
- [ ] 已测量 `vkCreate*Pipelines` 耗时分布。
- [ ] 已确认 pipeline cache 是否启用及命中率。
- [ ] 已确认 pipeline 创建是否发生在 render thread 关键路径。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
SPIR-V Shader Modules
→ VkPipelineCache (memory + disk)
→ VkPipelineLayout
→ VkGraphicsPipelineCreateInfo / VkComputePipelineCreateInfo
→ vkCreate*Pipelines
   ├─ Startup Pre-warm (blocking)
   ├─ Runtime Sync Create (blocking fallback)
   ├─ Runtime Async Create (background thread)
   └─ Derivative Pipeline (basePipelineHandle)
→ VkPipeline
→ Bind & Draw
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| pipeline cache | `VkPipelineCache` | 缓存 pipeline 创建结果 | 全局 / 跨会话 | 否 |
| pipeline cache data | `uint8_t[]` / file | 持久化到磁盘 | 跨进程 | 否 |
| pipeline | `VkPipeline` | 渲染/计算状态对象 | per-variant | 否（通常） |
| async compile task | struct | 后台创建 pipeline 请求 | 直到完成或取消 | 否 |
| fallback pipeline | `VkPipeline` | 异步编译完成前的临时 pipeline | 直到 async pipeline ready | 否 |
| base pipeline | `VkPipeline` | derivative 的父 pipeline | 全局 | 否 |
| specialization constants | `VkSpecializationInfo` | 减少 shader 变体数量 | per-pipeline | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER_DYNAMIC` | scene/view constants | Vertex / Fragment / Compute |
| set=1,binding=0..N | `COMBINED_IMAGE_SAMPLER` | material textures | Fragment |
| push constant | `VkPushConstantRange` | per-draw / per-material params | Vertex / Fragment |

Pipeline 状态：

- 使用 specialization constants 替代预处理宏，减少 shader 变体数量；例如用 `const_id` 控制 feature toggle、LOD bias、light count [SPEC]。
- 对大量相似 pipeline（如不同 blend mode、cull mode），使用 `basePipelineHandle` 创建 derivative，可能降低编译时间 [SPEC]；效果因驱动而异，需实测 [HEUR]。
- 使用 `VK_EXT_graphics_pipeline_library` 将 vertex input / pre-rasterization / fragment output / fragment shader 分库编译，可显著减少 runtime pipeline 创建耗时 [SPEC]；需要 Vulkan 1.3 或扩展支持。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| async compile thread | `VkPipeline` | `vkCreate*Pipelines` 完成 | main thread bind |
| main thread | fallback pipeline | 同步使用 | async pipeline ready 后切换 |
| pipeline cache | cache data | `vkGetPipelineCacheData` | disk write / next launch load |
| pipeline layout create | pipeline | layout compatibility | draw / dispatch |

必须说明：

- `VkPipeline` 不是 internally synchronized object；多线程同时调用 `vkCreate*Pipelines` 使用同一 `VkPipelineCache` 是允许的，但 `vkDestroyPipeline` 与创建/使用不能并发 [SPEC]。
- Async pipeline 创建完成后，必须在 GPU 未使用 fallback pipeline 的帧边界切换到新 pipeline；通常通过 frame fence 保证 [ENGINE]。
- Pipeline cache 数据写入磁盘应在非关键路径（如退出时或后台线程），避免 I/O stall [HEUR]。

---

## 8. 实现步骤

### Startup Pre-warm（启动时预编译）

1. **收集需预编译的 pipeline 列表**：
   - 根据场景、材质、shader variant 预估首屏所需 pipeline；
   - 不必全部预编译，优先热路径 [HEUR]。
2. **加载 disk pipeline cache**：
   - 启动时读取上次保存的 cache blob；
   - 用 `VkPipelineCacheCreateInfo::pInitialData` 传入 [SPEC]；
   - cache 版本与驱动相关，加载失败时回退空 cache [ENGINE]。
3. **预创建关键 pipeline**：
   - 在 loading screen 期间调用 `vkCreate*Pipelines`；
   - 使用同一 `VkPipelineCache`，让后续创建受益 [HEUR]。
4. **保存 cache 数据**：
   - 退出或后台时调用 `vkGetPipelineCacheData` 写入磁盘 [SPEC]。

### Runtime Async Compile（运行时异步编译）

5. **识别运行时可能新增的 pipeline**：
   - 新材质、新 shader variant、dynamic state 组合等。
6. **准备 fallback pipeline**：
   - 使用一个简单但兼容的 pipeline（如默认材质）作为 fallback；
   - 或跳过渲染直到 async pipeline ready [HEUR]。
7. **提交 async compile task**：
   - 后台线程调用 `vkCreate*Pipelines`，共享全局 `VkPipelineCache` [SPEC]；
   - 任务包含 `VkGraphicsPipelineCreateInfo`、layout、render pass 信息。
8. **切换到 async pipeline**：
   - 完成后通过原子标志或 frame fence 通知主线程；
   - 在下一帧开始使用新 pipeline，旧 fallback 可延迟销毁 [ENGINE]。
9. **使用 derivative pipeline**：
   - 创建 base pipeline 时设置 `VK_PIPELINE_CREATE_ALLOW_DERIVATIVES_BIT` [SPEC]；
   - 创建 derivative 时设置 `VK_PIPELINE_CREATE_DERIVATIVE_BIT` 并填 `basePipelineHandle` [SPEC]；
   - 注意：base 与 derivative 必须在同一 `vkCreate*Pipelines` 调用中创建，或 base 先创建并设置 allow derivatives [SPEC]。
10. **使用 specialization constants 减少变体**：
    - 将编译期常量改为 `layout(constant_id = N)`；
    - 同一 shader module 配合不同 `VkSpecializationInfo` 创建不同 pipeline，减少 SPIR-V 文件数量 [SPEC]。
11. **考虑 Graphics Pipeline Library（GPL）**：
    - 将 pipeline 拆分为 vertex input、pre-rasterization、fragment shader、fragment output 四个库；
    - 运行时链接为完整 pipeline，显著降低 stutter [SPEC]；
    - 需要启用 `VK_EXT_graphics_pipeline_library` 并处理 flags。
12. **监控与调优**：
    - 统计 cache hit/miss、async compile 等待时间、startup pre-warm 耗时；
    - 对高频 miss 的变体进行预编译或合并 [HEUR]。

---

## 9. Android 注意点

- `ANativeWindow` / surface 创建后 render pass format 才确定；依赖 surface format 的 pipeline 必须在 surface 创建后创建，启动预编译阶段若尚未有 surface，只能预编译 format-independent 部分或使用 GPL [ANDROID]。
- 移动端后台线程资源受限，async compile 线程数建议 1~2，避免与 render thread 争用 CPU/GPU driver lock [ANDROID]。
- Pipeline cache blob 在 Android 上可保存到应用私有目录；注意不同设备/驱动间 cache 不通用，建议按 device ID / driver version 分文件 [ANDROID]。
- rotation / resize 通常不改变 pipeline（除非 surface format 变化），但若启用了 GPL 的 fragment output 库且 format 改变，需要重建对应库 [ANDROID]。
- pause / resume 期间保留 pipeline cache 与已创建 pipeline；不要销毁 cache，否则下次启动失去加速 [ANDROID]。
- AGI / logcat 验证：监控 `vkCreate*Pipelines` 调用耗时、cache hit 情况、async task 完成时间。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkPipelineCacheCreateInfo-*`、`VUID-VkGraphicsPipelineCreateInfo-*`、derivative / async 相关错误 [TOOL]。
- [ ] RenderDoc / AGI / Nsight：
  - 可见 async pipeline 在完成后被绑定；
  - startup 阶段预编译 pipeline 列表正确；
  - cache hit 后 `vkCreate*Pipelines` 耗时显著降低 [TOOL]。
- [ ] 截图 / 数值验证：fallback 切换到 async pipeline 时无画面跳变或 artifact。
- [ ] logcat（Android）：无 validation error；可输出 `pipelineCreationTime`、`cacheHitRate`、`asyncCompileQueueSize`。
- [ ] 性能指标：
  - startup pre-warm 总耗时在可接受范围；
  - runtime 首次遇到新 pipeline 时 fallback 不造成明显 spike；
  - async compile 完成后 frame time 恢复平稳；
  - 99th percentile frame time 无异常尖峰 [HEUR]。
- [ ] resize / pause / resume / rotation 后 pipeline cache 与已创建 pipeline 仍有效。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 pipeline 绑定错误。

---

## 11. 常见失败模式

1. **Pipeline cache 未持久化**：每次启动冷编译所有 pipeline，startup 极慢 [HEUR]。
2. **Async pipeline 未完成就使用**：主线程未等 async 完成就绑定，导致渲染错误或未定义行为 [ENGINE]。
3. **Base/derivative pipeline 创建顺序错误**：base 未设置 `ALLOW_DERIVATIVES_BIT` 或不在同一调用中 [SPEC]。
4. **多线程并发销毁 pipeline**：`vkDestroyPipeline` 与创建/使用并发导致 crash [SPEC]。
5. **Specialization constants 与 layout 不匹配**：constant ID、size、offset 错误 [TOOL]。
6. **Pipeline cache blob 跨设备混用**：不同 GPU/driver 加载失败或产生无效 cache [ANDROID]。
7. **GPL 库链接失败**：未正确设置所有 pipeline library flags 或缺少必要 stage [SPEC]。
8. **Android surface 未创建就预编译 format-dependent pipeline**：创建失败或只能等到 surface 创建后 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_cache.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/specialization_constants.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline_library.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/pipeline_creation_stutter.md`
- `../../04_debug_playbooks/06_performance_symptoms/startup_time_high.md`
- `../../04_debug_playbooks/06_performance_symptoms/cpu_frame_time_high.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / GPU 型号 / Vulkan 版本。
- `vkCreate*Pipelines` 耗时分布（首创建 vs cache hit）。
- Pipeline 总量与变体数量。
- 是否使用 `VkPipelineCache` 及其命中率。
- Async compile 线程模型与同步方式。
- 是否使用 GPL / derivative / specialization constants。
- Android lifecycle 日志。

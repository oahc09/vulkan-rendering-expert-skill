# Workflow: Android Validation and AGI

> 文件建议路径：`android_validation_agi_workflow.md`

---

## 0. 适用范围

### 适用

- 在 Android 设备上启用 Vulkan Validation Layer，捕获并修复 spec 违规。
- 使用 Android GPU Inspector（AGI）抓取一帧或多帧，分析 barrier、descriptor、pipeline 状态。
- 需要排查 Android 特定的 synchronization hazard、layout error、descriptor binding 问题。
- 需要在真实设备上验证渲染管线的正确性与性能。

### 不适用

- 仅桌面平台（Windows / Linux）开发；AGI 主要针对 Android，桌面应优先 RenderDoc。
- 无需抓帧、只需 logcat 快速验证的场景（可简化为单独启用 validation layer）。
- 设备未解锁 / 未开启开发者选项 / 驱动不支持 AGI 的旧机型。

---

## 1. 任务目标

在 Android 上建立完整的验证与抓帧闭环：

```text
启用 Validation Layer
→ 连接 AGI / logcat 收集报错
→ 运行目标场景
→ AGI 抓取 frame
→ 分析 Barrier / Descriptor / Pipeline
→ 修复问题并重新验证
```

---

## 2. 输入条件

需要确认：

- Android 设备型号、GPU（Adreno / Mali / PowerVR）、Android 版本。
- Vulkan 版本与驱动版本。
- 是否已启用开发者选项、USB 调试。
- 应用包名、主 Activity、入口渲染场景。
- 是否已集成 Android Game Development Extension（AGDE）或直接使用 AGI。
- 当前应用是否已携带 validation layer 二进制，或依赖系统层。
- 目标抓帧场景：静态画面、动态场景、pause/resume、rotation。

---

## 3. 前置检查

- [ ] 设备已开启开发者选项与 USB 调试。
- [ ] `adb devices` 能识别设备。
- [ ] 应用可正常启动并渲染（至少没有立即崩溃）。
- [ ] 已下载与设备 / Android 版本匹配的 AGI 版本。
- [ ] 已确认设备在 AGI 支持列表中（Adreno 5xx+、Mali-Gxx、部分 PowerVR）。
- [ ] 应用 `AndroidManifest.xml` 未禁用 debuggable（AGI 通常需要 debuggable 或 root）。
- [ ] 已备份当前工程，避免调试配置污染发布包。

---

## 4. Vulkan 对象链路

```text
Android Application
→ ANativeWindow / Surface
→ vkCreateInstance (with VK_LAYER_KHRONOS_validation)
→ vkCreateDevice
→ vkCreateSwapchainKHR
→ Command Buffer Recording
→ vkQueueSubmit
→ vkQueuePresentKHR
→ Validation Layer Message (logcat / AGI)
→ AGI Capture
→ Frame Analysis (Barriers / Descriptors / Pipelines / GPU Counters)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| validation layer | `VkLayerProperties` | 运行时验证 | 实例生命周期 | 否 |
| debug messenger | `VkDebugUtilsMessengerEXT` | 回调收集 validation 信息 | 实例生命周期 | 否 |
| AGI trace file | `.gfxtrace` / `.perfetto` | 抓帧数据 | 分析阶段 | 不适用 |
| logcat buffer | 系统日志 | 实时查看 VUID 报错 | 运行阶段 | 不适用 |
| device config | `vk_layer_settings.txt` / 环境变量 | 控制 validation 细项 | 应用启动期 | 否 |

设计说明：

- Validation Layer 通过 instance extension `VK_EXT_debug_utils` 或 `VK_EXT_debug_report` 输出消息 [SPEC]。
- AGI 使用设备端的 interceptor / driver instrumentation 抓取 command buffer、memory、pipeline 状态 [TOOL]。
- 建议在 debug build 中同时启用 validation layer 与 AGI；release build 应移除 validation layer 与 debug messenger [ENGINE]。

---

## 6. Pipeline / Descriptor 设计

本工作流主要关注验证与抓帧，pipeline / descriptor 设计按被分析对象复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 被分析 pass 的 binding | `COMBINED_IMAGE_SAMPLER` / `STORAGE_IMAGE` / `STORAGE_BUFFER` / `UNIFORM_BUFFER` | 对应 image / buffer | 被分析 stage |
| push constants | `VkPushConstantRange` | 每 draw/dispatch 参数 | Vertex / Fragment / Compute |

设计说明：

- AGI 中可查看每个 draw / dispatch 的完整 descriptor set 绑定、pipeline layout、push constants [TOOL]。
- 验证 layer 会检查 descriptor type 与 shader 是否匹配、descriptor 是否更新、image layout 是否合法 [SPEC]。
- 若 AGI 中某 draw 的 descriptor 显示为空白或 stale，通常说明 descriptor set 更新时机错误或在 submit 后更新 [TOOL]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| validation layer 检测 | 所有 image / buffer / render pass | 报告 hazard / layout mismatch / access error | 开发者修复 |
| AGI 抓取 | 一帧内所有 submit | 记录实际 layout transition 与 barrier | 分析工具 |
| 应用绘制 | swapchain image | 实际 acquire → render → present 同步 | AGI / validation 校验 |

必须说明：

- validation layer 的 synchronization validation 会追踪 image layout、access mask、stage mask 的匹配性；报出 `SYNC-HAZARD` 即说明存在未正确同步 [TOOL]。
- AGI 抓取时会在 driver 层插入 instrumentation，对 frame time 有一定影响，性能数据应取多次 capture 的平均值 [TOOL]。
- 分析 barrier 时应关注：srcStage/dstStage 是否过宽（如 `ALL_COMMANDS`）、access mask 是否缺失、layout 转换是否冗余 [HEUR]。
- 分析 descriptor 时应关注：descriptor set 是否已更新、image layout 与 descriptor 中声明的是否一致、buffer offset/size 是否越界 [TOOL]。

---

## 8. 实现步骤

1. **启用 Validation Layer（方式一：打包到 APK）**：
   - 在 `src/main/jniLibs/<abi>/` 下放置 `libVkLayer_khronos_validation.so`。
   - 在 `vkCreateInstance` 的 `ppEnabledLayerNames` 中加入 `"VK_LAYER_KHRONOS_validation"` [SPEC]。
   - 创建 `VkDebugUtilsMessengerEXT` 回调，将消息输出到 logcat 或断言 [SPEC]。
2. **启用 Validation Layer（方式二：系统层，需 root 或调试配置）**：
   - `adb shell settings put global enable_gpu_debug_layers 1`。
   - `adb shell settings put global gpu_debug_app <package_name>`。
   - `adb shell settings put global gpu_debug_layers VK_LAYER_KHRONOS_validation` [TOOL]。
3. **配置 validation 细项**：
   - 通过 `vk_layer_settings.txt` 启用 `khronos_validation.enables = VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT` [TOOL]。
   - 若只关注 descriptor / pipeline，可关闭同步验证以减少噪声 [HEUR]。
4. **安装并启动 AGI**：
   - 下载 AGI，连接设备，选择应用包名与 Activity [TOOL]。
   - 配置 capture：System Profiler 或 Frame Profiler；选择 Vulkan API [TOOL]。
5. **启动应用并抓取帧**：
   - 在目标场景稳定后点击 Capture Frame；AGI 会拦截并保存 `.gfxtrace` [TOOL]。
   - 也可使用 System Profiler 连续抓取多帧，分析 frame time 与 counter 趋势 [TOOL]。
6. **分析 Validation Layer 输出**：
   - `adb logcat -s vulkan` 过滤 `VUID-` 前缀；按 VUID 在 Vulkan-Docs 或 `../../03_api_manual/09_debug_validation/vuid_decode.md` 查找含义 [TOOL]。
   - 优先修复 `SYNC-HAZARD-*`、`VUID-vkCmdDraw-*-None-02721`（descriptor 未更新）、`VUID-vkCmdPipelineBarrier-oldLayout-01181` [TOOL]。
7. **分析 AGI Barrier**：
   - 打开 Frame → Command Tree，定位到可疑 draw / dispatch。
   - 查看 Events / Dependencies 面板，确认 producer/consumer stage 与 access mask [TOOL]。
   - 若存在 `ALL_COMMANDS` 或 `MEMORY_READ|WRITE`，按 `../07_optimization/optimize_barriers.md` 优化 [HEUR]。
8. **分析 AGI Descriptor**：
   - 在 Pipeline / Descriptor 面板查看每个 set/binding 的 resource、type、image layout、buffer range [TOOL]。
   - 对比 GLSL / SPIR-V 确认类型匹配；发现 `STORAGE_BUFFER` 绑定到 `uniform` 块即为错误 [SPEC]。
9. **分析 AGI Pipeline**：
   - 确认 shader module、pipeline layout、vertex input、rasterization、blend、depth stencil 状态 [TOOL]。
   - 检查 compute pipeline 的 workgroup size 与 dispatch 调用是否一致。
10. **修复并重新验证**：
    - 修复代码后重新打包；先确认 validation clean，再重新 AGI capture [ENGINE]。
    - 建议每修复一类问题就单独验证，避免多变更叠加导致 root cause 模糊 [HEUR]。
11. **关闭调试配置**：
    - release build 移除 validation layer 库与 `VK_LAYER_KHRONOS_validation`。
    - 关闭系统层：`adb shell settings delete global enable_gpu_debug_layers` 等 [TOOL]。

---

## 9. Android 注意点

- Validation Layer 在 Android 上的性能开销显著，低端机可能帧率下降 30%–50%；仅用于 debug / profile build [ANDROID]。
- AGI 抓帧需要应用处于 debuggable 状态或设备已 root；发布版本无法直接 capture [ANDROID]。
- 某些 OEM 驱动对 validation layer 支持不完整，可能漏报或误报；此时以 spec 行为与 RenderDoc / AGI 实际状态为准 [ANDROID]。
- `ANativeWindow` / surface 生命周期影响 AGI capture：在 `surfaceDestroyed` 后立即抓帧会失败；应在 surface 稳定渲染期间 capture [ANDROID]。
- rotation / resize 后 AGI 显示的 swapchain extent、render area、scissor 可能变化；分析时需确认当前帧的 surface transform [ANDROID]。
- Mali GPU 在 AGI 中可能显示 tile-based 特有的 `LOAD/STORE` 模式；分析 barrier 时需结合 tile memory 行为 [ANDROID]。
- logcat 中 `VulkanLoader` 信息可确认 validation layer 是否成功加载；若未加载，检查 ABI 匹配与库路径 [TOOL]。
- 启用 GPU debug layers 后，若应用启动变慢或 ANR，可降低 validation 细项或只在关键场景启用 [HEUR]。
- 抓帧前让目标场景稳定运行 2–3 秒，避免 capture 首帧的 warmup 开销影响分析结论 [GUIDE]。

---

## 10. 验证方式

- [ ] Validation Layer clean：logcat 中无 `VUID-` 报错（或仅存在已确认的误报） [TOOL]。
- [ ] AGI 可成功 capture frame，command tree 可见所有 draw / dispatch [TOOL]。
- [ ] AGI 中 Barrier / Dependency 面板显示的 stage / access / layout 与代码设计一致 [TOOL]。
- [ ] AGI 中 Descriptor 面板显示的资源、类型、layout、range 与 shader 声明一致 [TOOL]。
- [ ] 截图 / 数值验证：修复后渲染结果与预期一致，无 flickering / black screen。
- [ ] logcat（Android）：`adb logcat -s vulkan` 可看到 debug messenger 输出；AGI 启动日志无 critical error。
- [ ] 性能指标：
  - AGI GPU counters 中 stall / idle 时间与 barrier 设计匹配；
  - 修复 hazard 后 frame time 稳定；
  - validation 开启前后性能下降在可接受范围 [TOOL]。
- [ ] resize / pause / resume 后 validation 与 AGI capture 仍稳定。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Validation Layer 未加载**：库 ABI 不匹配、未加入 `ppEnabledLayerNames`、系统层设置错误 [TOOL]。
2. **AGI 无法连接设备**：设备未开启开发者选项、USB 调试未授权、AGI 版本与 Android 版本不匹配 [TOOL]。
3. **AGI capture 导致应用崩溃**：应用非 debuggable、驱动不支持 instrumentation、surface 生命周期与 capture 时序冲突 [ANDROID]。
4. **大量 validation 噪声**：同步验证开启后误报增多；可关闭 `BEST_PRACTICES` 或按 VUID 过滤 [HEUR]。
5. **只修 validation 不修 AGI 可见问题**：validation clean 不代表性能正确，需同时检查 AGI barrier/descriptor [TOOL]。
6. **Descriptor 在 AGI 中显示 stale**：`vkUpdateDescriptorSets` 在 submit 之后调用，或 descriptor pool 被重置过早 [SPEC]。
7. **Barrier stage mask 过宽**：AGI 显示 `ALL_COMMANDS` 导致 GPU stall；需精确化 [HEUR]。
8. **Android surface 销毁后仍抓帧**：AGI capture 失败或触发 `DEVICE_LOST` [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/09_debug_validation/validation_layer.md`
- `../../03_api_manual/09_debug_validation/debug_utils.md`
- `../../03_api_manual/09_debug_validation/vuid_decode.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_overuse.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- Android 设备型号 / GPU / Android 版本 / Vulkan 驱动版本。
- AGI 版本与 capture 失败日志。
- `adb logcat -s vulkan` 完整输出。
- 应用包名、Activity、是否 debuggable。
- 当前 `vkCreateInstance` 的 layer / extension 列表。
- 触发问题的具体场景（启动、rotation、pause/resume、特定 draw）。
- AGI capture 中可疑 draw/dispatch 的 barrier / descriptor / pipeline 截图。

# Workflow: Add Compute Pipeline

## 0. 适用范围

### 适用

- 新增 compute shader pipeline，用于后处理、粒子、culling、clustering、FFT、神经网络推理等。
- 需要处理 shader module、pipeline layout、specialization constants、pipeline cache、bind/dispatch。
- 与 graphics pipeline 共享同一 device 和 queue，但使用 compute queue 或 graphics-compute 通用 queue。

### 不适用

- 纯 graphics pipeline（应参考 graphics pipeline workflow）。
- 使用 ray tracing pipeline（需 RT pipeline 专用 workflow）。
- 完全由外部 compute framework（如 OpenCL / CUDA）处理的场景。

---

## 1. 任务目标

新增可工作的 compute pipeline：

```text
SPIR-V Compute Shader
→ VkShaderModule
→ VkPipelineLayout (descriptor set layouts + push constants)
→ VkPipelineCache (optional)
→ VkPipeline
→ vkCmdBindPipeline(COMPUTE)
→ vkCmdBindDescriptorSets
→ vkCmdDispatch / vkCmdDispatchIndirect
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- Compute shader SPIR-V 文件或编译源码。
- Shader 中 set/binding 布局与 descriptor 类型。
- 是否需要 specialization constants（如 local size、feature toggle）。
- Work group size 与全局 dispatch size。
- 使用 graphics queue 还是专用 compute queue。
- 是否已有 pipeline cache。
- 输出 image / buffer 的 layout 与 access flag。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] Shader 编译链路可用，SPIR-V 合法。
- [ ] `vkGetPhysicalDeviceQueueFamilyProperties` 已确认 compute queue family 可用 [SPEC]。
- [ ] Pipeline layout 已创建并引用对应 descriptor set layout。
- [ ] Descriptor pool 对 `STORAGE_BUFFER`、`STORAGE_IMAGE`、`UNIFORM_BUFFER` 等类型有余量。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
SPIR-V (compute shader)
→ VkShaderModule
→ VkPipelineLayout
→ VkPipelineCache
→ VkComputePipelineCreateInfo
→ VkPipeline
→ Command Buffer
→ vkCmdBindPipeline (VK_PIPELINE_BIND_POINT_COMPUTE)
→ vkCmdBindDescriptorSets
→ vkCmdDispatch / vkCmdDispatchIndirect
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| compute shader module | `VkShaderModule` | compute stage entry | per-pipeline 或共享 | 否 |
| pipeline layout | `VkPipelineLayout` | descriptor set layout + push constant 聚合 | 通常全局 | 否 |
| pipeline cache | `VkPipelineCache` | 加速 pipeline 创建 | 全局 / 跨会话 | 否 |
| compute pipeline | `VkPipeline` | 计算状态对象 | per-shader / per-spec | 否 |
| descriptor set | `VkDescriptorSet` | 绑定 SSBO / image / sampler | per-frame / per-dispatch | 通常否 |
| storage buffer / image | `VkBuffer` / `VkImage` | compute 读写目标 | 视算法而定 | 否（通常） |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | compute params | Compute |
| set=0,binding=1 | `STORAGE_BUFFER` | input SSBO | Compute |
| set=0,binding=2 | `STORAGE_BUFFER` | output SSBO | Compute |
| set=1,binding=0 | `STORAGE_IMAGE` | output image | Compute |
| set=1,binding=1 | `COMBINED_IMAGE_SAMPLER` | input texture | Compute |
| push constant | `VkPushConstantRange` | dispatch 参数 / 动态常量 | Compute |

Pipeline 状态：

- Compute pipeline 仅包含一个 compute shader stage，无 vertex input、rasterization、blend 等状态 [SPEC]。
- `VkComputePipelineCreateInfo::stage.stage` 必须为 `VK_SHADER_STAGE_COMPUTE_BIT` [SPEC]。
- `VkComputePipelineCreateInfo::layout` 必须与 shader 引用的 descriptor set layout 和 push constant range 兼容 [SPEC]。
- Specialization constants 通过 `VkSpecializationInfo` 传入，可用于在 pipeline 创建时固化 work group 相关常量 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU upload | input SSBO | `TRANSFER_WRITE` → `SHADER_READ` | compute shader read |
| graphics pass | input image | `COLOR_ATTACHMENT_OPTIMAL` → `GENERAL` / `SHADER_READ_ONLY_OPTIMAL` | compute shader sample |
| compute dispatch | output SSBO | `SHADER_WRITE` | next compute / graphics read |
| compute dispatch | output image | `GENERAL`（写入） | graphics fragment sample / transfer |
| previous compute | intermediate buffer | `vkCmdPipelineBarrier` memory barrier | next compute dispatch |

必须说明：

- Compute shader 读取 buffer 前，buffer 必须处于 `VK_ACCESS_SHADER_READ_BIT`，stage `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` [SPEC]。
- Compute shader 写入 storage image 时，image layout 应为 `GENERAL` [SPEC]。
- Dispatch 后若 graphics 消费，barrier 的 src stage 为 `COMPUTE_SHADER_BIT`，dst stage 按下游定（如 `FRAGMENT_SHADER_BIT`、`COLOR_ATTACHMENT_OUTPUT_BIT`）[SPEC]。
- 若使用同一个 queue 连续 dispatch，buffer/image 的 barrier 不可省略 [SPEC]。

---

## 8. 实现步骤

1. **编译 compute shader**：
   - 使用 `glslangValidator -V compute.comp -o compute.spv` 或 `dxc -spirv -T cs_6_0` [ENGINE]。
   - 推荐在 build 时编译 SPIR-V，避免运行时编译开销 [HEUR]。
2. **创建 shader module**：
   - 读取 SPIR-V 字节码，填写 `VkShaderModuleCreateInfo`，调用 `vkCreateShaderModule` [SPEC]。
3. **确认 pipeline layout**：
   - 聚合 descriptor set layouts；
   - 定义 push constant range，stage 为 `VK_SHADER_STAGE_COMPUTE_BIT` [SPEC]。
4. **处理 specialization constants**（可选）：
   - 若 shader 中 `layout(constant_id = 0) const uint WORKGROUP_SIZE_X = 256;`；
   - 创建 `VkSpecializationMapEntry` 和 `VkSpecializationInfo`；
   - 同一 shader 配不同 spec 常量可生成多个 pipeline（如不同 local size） [SPEC]。
5. **创建 / 复用 pipeline cache**：
   - 使用 `VkPipelineCache`；
   - 退出时保存 cache 数据到磁盘，下次启动加载，可显著减少 stutter [ENGINE]。
6. **创建 compute pipeline**：
   - 填写 `VkComputePipelineCreateInfo`；
   - 调用 `vkCreateComputePipelines`（注意复数接口，可批量创建） [SPEC]。
7. **准备 descriptor set**：
   - 按 shader set/binding 更新 UBO/SSBO/storage image/sampler descriptor；
   - image descriptor layout 必须与实际使用 layout 一致 [SPEC]。
8. **录制 command buffer**：
   - `vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline)` [SPEC]；
   - `vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, layout, ...)` [SPEC]；
   - 可选 `vkCmdPushConstants(cmd, layout, COMPUTE_BIT, ...)` [SPEC]；
   - `vkCmdDispatch(cmd, groupCountX, groupCountY, groupCountZ)`；groupCount = (workSize + localSize - 1) / localSize [SPEC]。
9. **处理间接 dispatch**（可选）：
   - 使用 `vkCmdDispatchIndirect`，buffer 需 `VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT` [SPEC]。
10. **同步**：
    - dispatch 前后插入 `vkCmdPipelineBarrier`，确保 producer/consumer 顺序 [SPEC]。
11. **接入 frame loop**：
    - compute pass 可在 graphics pass 前、后或独立提交；
    - 若使用不同 queue，需要 semaphore 或 barrier 跨 queue 同步 [SPEC]。
12. **接入销毁路径**：
    - 按 `pipeline → pipeline cache → shader module → pipeline layout` 顺序销毁；
    - 若 shader module 被多个 pipeline 共享，等所有 pipeline 销毁后再销毁 [ENGINE]。

---

## 9. Android 注意点

- Compute pipeline 创建不依赖 surface，但 compute 读取的 image/buffer 可能依赖 swapchain 尺寸；`surfaceDestroyed` 后不得再 submit 引用 swapchain image 的命令 [ANDROID]。
- 移动端通常只有 1 个 graphics-compute 通用 queue family，compute 与 graphics 串行执行；若存在专用 compute queue，需要 semaphore 同步 [ANDROID]。
- Work group size 建议选择 64 / 128 / 256 的倍数以适配 Adreno / Mali warp/wavefront；可用 Mali Offline Compiler 或 Adreno Profiler 验证 occupancy [ANDROID]。
- pause / resume 期间保留 compute pipeline 与 descriptor layout；但 per-frame descriptor 引用的资源需按生命周期重新更新。
- AGI / logcat 验证：检查 `vkCreateComputePipelines` 耗时、`vkCmdDispatch` 参数、descriptor set 绑定。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkComputePipelineCreateInfo-*`、`VUID-vkCmdDispatch-*`、`VUID-vkCmdBindDescriptorSets-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 compute dispatch、pipeline state、descriptor sets、resource handles [TOOL]。
- [ ] 截图 / 数值验证：compute 输出 buffer/image 数据符合预期。
- [ ] logcat（Android）：无 validation error；可输出 dispatch size、work group size、pipeline creation time。
- [ ] 性能指标：
  - `vkCreateComputePipelines` 耗时在可接受范围（可用 cache 加速）；
  - dispatch 占用在 AGI 中可见；
  - 无 redundant barrier / descriptor bind [HEUR]。
- [ ] resize / pause / resume 后 compute pipeline 仍可用。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Pipeline layout 与 shader 不匹配**：descriptor set 数量、binding、type 不一致 [TOOL]。
2. **忘记设置 `VK_SHADER_STAGE_COMPUTE_BIT`**：push constant range stage 错误 [SPEC]。
3. **Work group size 超限**：超过 `maxComputeWorkGroupSize` / `maxComputeWorkGroupInvocations` [SPEC]。
4. **Storage image layout 错误**：compute write 时 image 不是 `GENERAL` [SPEC]。
5. **Barrier 缺失**：dispatch 后 graphics pass 读取结果未做 memory barrier [TOOL]。
6. **Descriptor 更新滞后**：bind 时 descriptor 仍指向旧 buffer/image [ENGINE]。
7. **Pipeline cache 未持久化**：每次启动重新编译 compute shader，造成启动卡顿 [HEUR]。
8. **Android 上 compute 与 graphics 未同步**：不同 queue 间无 semaphore，导致读写竞争 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/pipeline_cache.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- Compute shader SPIR-V 与 reflection 输出。
- `VkComputePipelineCreateInfo`、`VkPipelineLayoutCreateInfo` 参数。
- Descriptor set / binding 内容。
- Dispatch size 与 work group size。
- Barrier / layout transition 参数。
- Android lifecycle 日志。

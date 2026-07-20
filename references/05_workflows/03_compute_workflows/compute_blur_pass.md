# Workflow: Compute Blur Pass

> 文件建议路径：`compute_blur_pass.md`

---

## 0. 适用范围

### 适用

- 使用 compute shader 实现图像 blur（高斯 / 双边 / 方框模糊），替代 fragment shader 的 fullscreen pass，减少 rasterization overhead。
- 输入为 `VkImage`（如 color attachment、scene texture、downsampled 贴图），输出为另一张 `VkImage` 或同一 image 的不同 mip/array layer。
- 需要将 compute 输出作为后续 graphics pass 的 sampled image / input attachment 消费。
- 单/多 pass separable blur（horizontal + vertical）场景。

### 不适用

- 简单 clear / blit 操作（应使用 `vkCmdBlitImage` 或 graphics copy）。
- 不需要跨 workgroup 协作的 per-pixel 简单变换（compute 启动开销可能不划算）。
- 目标平台 compute queue 与 graphics queue 非同队列且频繁 ping-pong（跨 queue 同步成本可能抵消收益）。

---

## 1. 任务目标

新增一个 compute blur pass，完成以下数据流：

```text
Input Image (SHADER_READ_ONLY_OPTIMAL / GENERAL)
→ Compute Descriptor (input sampled image / storage image)
→ Compute Pipeline (gaussian / bilateral kernel via push constant / specialization)
→ Output Image (GENERAL write, then transition to SHADER_READ_ONLY_OPTIMAL)
→ Barrier / Layout Transition
→ Graphics Pass / Present
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本（是否支持 Vulkan 1.3 / `VK_KHR_synchronization2`）。
- 输入 image 格式、尺寸、mip 层级（blur 通常针对 single mip）。
- 输出 image 是新建，还是复用输入 image 的 alias / ping-pong。
- blur 类型：gaussian、box、bilateral；kernel radius（1D 或 2D）。
- 是否需要 separable（horizontal + vertical）双 pass。
- workgroup size 限制：`maxComputeWorkGroupInvocations`、`maxComputeWorkGroupSize`。
- 后续 consumer 阶段：graphics fragment shader 采样、compute 继续处理、input attachment。
- 是否使用专用 compute queue 或复用 graphics queue。

---

## 3. 前置检查

- [ ] Validation Layer 可用，建议启用 synchronization validation。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `maxComputeWorkGroupInvocations`、`maxComputeWorkGroupSize[3]`、`maxComputeSharedMemorySize`。
- [ ] 当前 renderer 已能创建 compute pipeline 与 descriptor。
- [ ] 输入 / 输出 image 的 `sampleCount = VK_SAMPLE_COUNT_1_BIT`（compute 不支持 multisample image 直接读写）。
- [ ] 若输出 image 需要后续 graphics 采样，已规划 layout transition。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Input Image (VK_IMAGE_USAGE_SAMPLED_BIT | STORAGE_BIT)
→ VkImageView (2D, single mip/layer)
→ VkSampler (blur input 若使用 sampled image)
→ VkDescriptorSetLayout (input image + output image + params)
→ VkDescriptorSet
→ VkPipelineLayout (push constants / specialization constants)
→ VkComputePipeline (blur shader module)
→ vkCmdBindPipeline(COMPUTE)
→ vkCmdBindDescriptorSets
→ vkCmdDispatch(workgroupX, workgroupY, 1)
→ VkImageMemoryBarrier(output: GENERAL → SHADER_READ_ONLY_OPTIMAL)
→ Consumer Graphics Pipeline / Compute Pipeline
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| input image | `VkImage` | `SAMPLED_BIT`（或 `STORAGE_BIT` 用于 storage image 读取） | per-pass / scene | 否（通常） |
| output image | `VkImage` | `STORAGE_BIT` + `SAMPLED_BIT`（如需后续采样） | per-pass / scene | 否（通常） |
| intermediate image（separable 双 pass） | `VkImage` | `STORAGE_BIT` + `SAMPLED_BIT` | per-pass | 否 |
| input image view | `VkImageView` | sampled / storage image view | per-pass | 否 |
| output image view | `VkImageView` | storage image view | per-pass | 否 |
| blur params buffer（可选） | `VkBuffer` | `UNIFORM_BUFFER_BIT` 或 push constants | per-frame | 否 |
| descriptor set | `VkDescriptorSet` | input + output + kernel params | per-frame / per-pass | 视策略而定 |

设计说明：

- input image 若仅作为 sampled image 读取，无需 `STORAGE_BIT`，布局保持 `SHADER_READ_ONLY_OPTIMAL` [SPEC]。
- output image 必须带 `VK_IMAGE_USAGE_STORAGE_BIT`；若后续 graphics pass 需采样，再加 `SAMPLED_BIT` [SPEC]。
- separable blur 需要 ping-pong：H pass 输出到 intermediate，V pass 读 intermediate 写最终 output [ENGINE]。

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` 或 `STORAGE_IMAGE` | input image（blur 源） | Compute |
| set=0,binding=1 | `STORAGE_IMAGE` | output image（blur 目标） | Compute |
| set=0,binding=2 | `UNIFORM_BUFFER` 或 push constants | kernel radius / direction / sigma / bilateral coefficients | Compute |

设计说明：

- 高斯 / 双边 / 方框模糊选择可通过 specialization constant（编译期确定分支，减少 divergence）或 push constant（运行期切换）实现 [ENGINE]。
  - specialization 适合发布时只启用一种 kernel；push constant 适合运行时 UI 切换。
- bilateral blur 需要额外 depth / color variance 输入，可增加 set=0,binding=3 的 `COMBINED_IMAGE_SAMPLER` [GUIDE]。
- workgroup size 建议设为 `(8, 8, 1)` 或 `(16, 16, 1)`，但需小于 `maxComputeWorkGroupInvocations` 和设备 warp/wavefront 偏好 [HEUR]。
  - 适用条件：image 宽 / 高为 workgroup size 整数倍；否则 dispatch 向上取整并在 shader 中用边界检查避免 out-of-bounds [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| graphics pass write / transfer upload | input image | `COLOR_ATTACHMENT_WRITE` / `TRANSFER_WRITE` → `SHADER_READ`；layout `COLOR_ATTACHMENT_OPTIMAL` / `TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | compute blur read |
| compute blur write | output image | `SHADER_WRITE` → `SHADER_READ`；layout `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | graphics fragment sample |
| compute H-pass write | intermediate image | `SHADER_WRITE` → `SHADER_READ`；layout `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | compute V-pass read |
| compute V-pass write | final output image | `SHADER_WRITE` → `SHADER_READ`；layout `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | graphics fragment sample / present blit |

必须说明：

- producer stage / access：根据实际写入方设置，常见为 `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` + `VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT`，或 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` + `VK_ACCESS_SHADER_WRITE_BIT` [SPEC]。
- layout 转换：compute 写入 storage image 时布局必须为 `VK_IMAGE_LAYOUT_GENERAL` [SPEC]；写入完成后 transition 到 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 供 fragment shader 采样。
- oldLayout 必须与实际当前布局一致，否则触发 `VUID-vkCmdPipelineBarrier-oldLayout-01181` 类 validation error [TOOL]。
- subresource range 应精确到单 mip / 单 layer；separable pass 若只处理 mip0，range 只包含 `baseMipLevel=0, levelCount=1` [HEUR]。
- 同 command buffer 内 producer/consumer 距离很近时，可用 `VkEvent` 替代 pipeline barrier，但 graphics → compute → graphics 链路通常 barrier 足够清晰 [SPEC]。

---

## 8. 实现步骤

1. **确认限制**：查询 `maxComputeWorkGroupInvocations`、`maxComputeWorkGroupSize`、`maxComputeSharedMemorySize`；确认 image format 支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`（输出）与 `VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT`（输入）[SPEC]。
2. **选择 blur 类型**：通过 specialization constant 或 push constant 传入 kernel 类型、radius、sigma、bilateral 阈值 [ENGINE]。
3. **创建 output image**：`usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT`；`initialLayout = VK_IMAGE_LAYOUT_UNDEFINED`；device-local memory [SPEC]。
4. **创建 image view**：output 使用非 multisample 2D view；separable pass 额外创建 intermediate image view。
5. **创建 descriptor set layout**：binding0 `COMBINED_IMAGE_SAMPLER` 或 `STORAGE_IMAGE`，binding1 `STORAGE_IMAGE`，binding2 `UNIFORM_BUFFER` / push constants，stageFlags = `VK_SHADER_STAGE_COMPUTE_BIT` [SPEC]。
6. **创建 compute pipeline**：编译 `blur.comp`；通过 specialization 设置 workgroup 局部大小或 kernel 类型 [SPEC]。
7. **分配并更新 descriptor set**：input image 使用 `VkDescriptorImageInfo`（sampler + imageView + layout），output image 使用 `VkDescriptorImageInfo`（imageView + layout = `GENERAL`），调用 `vkUpdateDescriptorSets` [SPEC]。
8. **录制 command buffer**：
   - transition input image 到 `SHADER_READ_ONLY_OPTIMAL`（若尚未在该布局）。
   - transition output image 到 `GENERAL`。
   - `vkCmdBindPipeline(COMPUTE)`、`vkCmdBindDescriptorSets`。
   - 通过 push constant 传入 direction（H/V）与 radius。
   - `vkCmdDispatch((width + wgX - 1)/wgX, (height + wgY - 1)/wgY, 1)`。
   - 插入 `vkCmdPipelineBarrier`，output image 从 `GENERAL` + `SHADER_WRITE` 转到 `SHADER_READ_ONLY_OPTIMAL` + `SHADER_READ`。
9. **separable blur**：重复步骤 8 两次，第一次 output = intermediate，第二次 input = intermediate，output = final [ENGINE]。
10. **接入 frame loop**：将 compute blur pass 放在 producer pass 之后、consumer graphics pass 之前。
11. **接入 resize / recreate**：blur image 尺寸通常不随 swapchain 变化；若与 viewport 绑定，resize 后按新 extent 重建 image view 与 descriptor [ANDROID]。
12. **接入销毁路径**：按 `descriptor set → pipeline → pipeline layout → image view → image → memory` 释放；VMA 用户统一 `vmaDestroyImage`。

---

## 9. Android 注意点

- 创建 blur output image 的 device 必须在 `ANativeWindow` 绑定到 surface 后获取，queue 才稳定 [ANDROID]。
- 移动端 Mali / Adreno 对 compute shader 读写 image 的 cache 一致性敏感：compute 写后必须显式 image memory barrier 到 `SHADER_READ_ONLY_OPTIMAL` 才能被 fragment shader 读取，不能依赖隐式同步 [ANDROID]。
- TBDR GPU 上 compute pass 与 graphics pass 交替会增加 external memory 带宽；若 blur 后续直接用于 fullscreen fragment pass，需评估 compute blur 是否真的比 fragment fullscreen pass 更快 [ANDROID]。
  - 适用条件：blur radius 较大、需要 separable、或需要显式共享 memory / subgroup 优化时，compute 收益更明显 [HEUR]。
- rotation / resize 触发 swapchain recreate，通常不影响 scene blur image；若 blur 目标与 surface extent 绑定，recreate 时按新 extent 重建 image 与 descriptor [ANDROID]。
- pause / resume 时，若 compute pass 与 swapchain image 在同一 frame 内提交，需确保 surface destroy 后不再提交含旧 swapchain image 的命令 [ANDROID]。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkCmdDispatch-*-None-02721`（image 格式支持）、`VUID-vkCmdPipelineBarrier-oldLayout-01181`（layout 错误）等 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 synchronization hazard、layout mismatch、descriptor type 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 compute dispatch、image 读写布局转换、output image 内容 [TOOL]。
- [ ] 截图 / 数值验证：blur 结果与参考实现一致，无黑边、条纹、闪烁。
- [ ] logcat（Android）：无 validation error；可输出每帧 dispatch 耗时与 workgroup 数量。
- [ ] 性能指标：
  - compute dispatch 耗时稳定，无 oversized workgroup；
  - AGI 中 compute pass 与 graphics consumer 之间无过长 GPU idle；
  - bandwidth 在 separable 双 pass 下优于 2D 单 pass（理论 2×radius vs radius²） [TOOL]。
- [ ] resize / pause / resume 后 blur 结果正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **输出 image 未加 `STORAGE_BIT`**：descriptor update 失败或 validation error [SPEC]。
2. **compute 写布局错误**：storage image 写入时未 transition 到 `GENERAL`，触发 `VUID-vkCmdDispatch-None-04547` [SPEC]。
3. **compute → graphics 同步缺失**：output image 未 barrier 到 `SHADER_READ_ONLY_OPTIMAL`，fragment shader 读到旧数据或 hazard [TOOL]。
4. **workgroup 尺寸过大**：超过 `maxComputeWorkGroupInvocations`，pipeline 创建失败 [SPEC]。
5. **separable pass 方向参数错误**：H/V 方向常量传反，导致只在一个方向 blur [ENGINE]。
6. **kernel radius 越界**：shader 中采样坐标超出 image 范围，产生黑边或 artifact [GUIDE]。
7. **oldLayout 与实际不符**：input image 尚未从 `COLOR_ATTACHMENT_OPTIMAL` transition，barrier 报 layout 错误 [TOOL]。
8. **Android surface recreate 期间提交 compute**：queue 关联的 surface 已 destroy，导致 device lost [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- blur 类型（gaussian / bilateral / box）、kernel radius、是否 separable。
- input / output image 格式、尺寸、usage、mip 层级。
- compute shader 代码与 workgroup size。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 compute dispatch 与 image layout 状态。
- Android lifecycle 日志。

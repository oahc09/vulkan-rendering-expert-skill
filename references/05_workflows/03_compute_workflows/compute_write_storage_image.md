# Workflow: Compute Write Storage Image

> 文件建议路径：`compute_write_storage_image.md`

---

## 0. 适用范围

### 适用

- compute shader 直接写入 `VkImage`（storage image），用于生成 procedural texture、post-processing target、lighting accumulation buffer、voxelization slice 等。
- 输出需要作为 image 被后续 graphics pass 采样，或作为 storage image 被后续 compute pass 继续读写。
- 相比 storage buffer，数据具有 2D/3D 局部性，适合 image load/store 操作。

### 不适用

- 输出数据本质上是结构化数组、随机访问非 2D（优先 storage buffer）。
- 目标 image format 不支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`（需 fallback 到 buffer 或 graphics pass）。
- 需要 automatic mipchain generation（compute 写入后需显式生成或上传）。

---

## 1. 任务目标

新增一个 compute pass，将结果写入 storage image，完成以下数据流：

```text
Compute Shader (imageStore)
→ VkImage (VK_IMAGE_USAGE_STORAGE_BIT)
→ Layout GENERAL (write)
→ Barrier (SHADER_WRITE → SHADER_READ)
→ Layout SHADER_READ_ONLY_OPTIMAL (graphics sample) / GENERAL (next compute read/write)
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 输出 image 格式、尺寸、mip/array layer 数量。
- 目标 format 是否支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT` 与 `VK_FORMAT_FEATURE_STORAGE_IMAGE_ATOMIC_BIT`（如使用 atomic）。
- 是否需要 per-frame ping-pong 或复用历史帧。
- 后续 consumer：compute 继续读写、graphics fragment 采样、blit/copy。
- workgroup size 限制与局部内存策略（shared memory tile）。

---

## 3. 前置检查

- [ ] Validation Layer 可用，建议启用 synchronization validation。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `maxComputeWorkGroupInvocations`、`maxComputeWorkGroupSize`、`maxComputeSharedMemorySize`。
- [ ] 已确认目标 format 支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`。
- [ ] 已规划 image layout transition：`GENERAL`（compute 写）→ `SHADER_READ_ONLY_OPTIMAL`（graphics 读）。
- [ ] compute pipeline 与 descriptor 已支持 storage image。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Compute Shader (imageStore)
→ VkDescriptorSetLayout (STORAGE_IMAGE binding)
→ VkDescriptorSet
→ VkImage (VK_IMAGE_USAGE_STORAGE_BIT | SAMPLED_BIT)
→ VkImageView (single mip/layer, non-multisample)
→ VkComputePipeline
→ vkCmdBindPipeline(COMPUTE)
→ vkCmdBindDescriptorSets
→ vkCmdDispatch
→ VkImageMemoryBarrier(GENERAL → SHADER_READ_ONLY_OPTIMAL)
→ Consumer Graphics / Compute Pass
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| output storage image | `VkImage` | `STORAGE_BIT` + `SAMPLED_BIT`（如需后续采样） | scene / frame | 否（通常） |
| storage image view | `VkImageView` | storage image view | per-pass | 否 |
| input image（可选） | `VkImage` | `SAMPLED_BIT` 或 `STORAGE_BIT` | scene / frame | 否 |
| input image view（可选） | `VkImageView` | sampled / storage view | per-pass | 否 |
| params buffer（可选） | `VkBuffer` | `UNIFORM_BUFFER_BIT` 或 push constants | per-frame | 否 |
| descriptor set | `VkDescriptorSet` | storage image binding | per-frame / per-pass | 视策略而定 |

设计说明：

- storage image 写入时必须处于 `VK_IMAGE_LAYOUT_GENERAL` [SPEC]。
- 若后续 graphics pass 需采样，必须加 `VK_IMAGE_USAGE_SAMPLED_BIT` 并在 barrier 后 transition 到 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` [SPEC]。
- 若 compute 后续继续读写，可保持 `GENERAL` 布局，只需同步 access mask [HEUR]。

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `STORAGE_IMAGE` | output image（compute 写入） | Compute |
| set=0,binding=1 | `COMBINED_IMAGE_SAMPLER` 或 `STORAGE_IMAGE` | input image（compute 读取） | Compute |
| set=0,binding=2 | `UNIFORM_BUFFER` 或 push constants | dispatch params / frame constants | Compute |

设计说明：

- compute shader 中 `layout(rgba8, binding=0, set=0) uniform image2D outImage;` 对应 `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` [SPEC]。
- `imageStore` 的 format qualifier 必须与 image 实际 format 兼容，否则触发 `VUID-vkCmdDispatch-None-08612` [SPEC]。
- workgroup 内可使用 `shared` memory 做 tile cache，减少 global image 访问；适用条件：输出像素与相邻像素有复用（如 box blur、convolution）[HEUR]。
- 输出 image 若同时作为输入（ping-pong），需确保 read/write 同步，通常使用双缓冲避免 self-dependency hazard [ENGINE]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| transfer upload / graphics pass | input image | `TRANSFER_WRITE` / `COLOR_ATTACHMENT_WRITE` → `SHADER_READ`；`TRANSFER_DST_OPTIMAL` / `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | compute shader read |
| compute shader write | output image | `SHADER_WRITE` → `SHADER_READ`；`GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | graphics fragment sample |
| compute shader write | output image | `SHADER_WRITE` → `SHADER_READ` / `SHADER_WRITE`；保持 `GENERAL` | next compute pass read/write |
| compute shader write | output image | `SHADER_WRITE` → `TRANSFER_READ`；`GENERAL` → `TRANSFER_SRC_OPTIMAL` | `vkCmdBlitImage` / `vkCmdCopyImage` |

必须说明：

- producer stage / access：compute shader 写入为 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` + `VK_ACCESS_SHADER_WRITE_BIT`。
- consumer stage / access：graphics fragment 采样为 `VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` + `VK_ACCESS_SHADER_READ_BIT` [SPEC]。
- image barrier 的 `subresourceRange` 应精确到目标 mip / layer；3D image 作为 storage image 时 `baseArrayLayer=0, layerCount=1` [SPEC]。
- 若使用 `imageStore` + `imageLoad` 在同一 image 上（in-place compute），必须用 ping-pong 或 event 精确同步，否则触发 write-after-read hazard [SPEC]。
- 跨 queue（compute queue → graphics queue）必须使用 semaphore，不能仅靠 pipeline barrier [SPEC]。

---

## 8. 实现步骤

1. **确认 format 支持**：通过 `vkGetPhysicalDeviceFormatProperties` 确认 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`；若需 atomic，确认 `VK_FORMAT_FEATURE_STORAGE_IMAGE_ATOMIC_BIT` [SPEC]。
2. **创建 output image**：`usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT`（若后续采样）；`initialLayout = VK_IMAGE_LAYOUT_UNDEFINED`；`samples = VK_SAMPLE_COUNT_1_BIT` [SPEC]。
3. **创建 image view**：`viewType = VK_IMAGE_VIEW_TYPE_2D`，`subresourceRange` 限定目标 mip/layer；multisample image 不能直接作为 storage image [SPEC]。
4. **创建 descriptor set layout**：binding0 `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE`，stageFlags = `VK_SHADER_STAGE_COMPUTE_BIT`；binding1 可选 `COMBINED_IMAGE_SAMPLER` 或 `STORAGE_IMAGE` [SPEC]。
5. **更新 descriptor set**：output image 的 `imageLayout = VK_IMAGE_LAYOUT_GENERAL`；input sampled image 的 `imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` [SPEC]。
6. **创建 compute pipeline**：编写 `write_storage_image.comp`，使用 `layout(set=0, binding=0, rgba8) uniform image2D outImage;`；编译 shader module 并创建 compute pipeline [SPEC]。
7. **录制 command buffer**：
   - transition output image `UNDEFINED` → `GENERAL`（首次）或 `SHADER_READ_ONLY_OPTIMAL` → `GENERAL`（后续帧复用）。
   - 若读 input image，transition 到 `SHADER_READ_ONLY_OPTIMAL`。
   - `vkCmdBindPipeline(COMPUTE)`、`vkCmdBindDescriptorSets`。
   - 设置 push constants（如需要）。
   - `vkCmdDispatch((width + wgX - 1)/wgX, (height + wgY - 1)/wgY, 1)`。
   - 插入 `vkCmdPipelineBarrier`：output image `GENERAL` + `SHADER_WRITE` → `SHADER_READ_ONLY_OPTIMAL` + `SHADER_READ`。
8. **consumer pass 接入**：graphics pass 中绑定 output image 为 sampled texture；compute next pass 中保持 `GENERAL` 并只更新 access mask。
9. **ping-pong 处理**：若 compute 多 pass 原位迭代，准备 A/B 两张 image，每帧交换 descriptor 指向 [ENGINE]。
10. **接入 resize / recreate**：storage image 通常不随 swapchain 重建；若与 surface extent 绑定，resize 后重建 image、view、descriptor [ANDROID]。
11. **接入销毁路径**：按 `descriptor set → pipeline → pipeline layout → image view → image → memory` 释放；VMA 用户统一 `vmaDestroyImage`。

---

## 9. Android 注意点

- 创建 storage image 的 device 必须在 `ANativeWindow` 绑定到 surface 后获取，queue 才稳定 [ANDROID]。
- 移动端 Mali / Adreno 对 `imageStore` 的 tile memory 写入路径敏感；若输出 image 后续被 fragment shader 采样，确保 barrier 到 `SHADER_READ_ONLY_OPTIMAL` 后再采样，否则 cache 不一致 [ANDROID]。
- TBDR 架构下 compute storage image 与 graphics sampled image 频繁切换会增加 external memory traffic；若 compute 输出直接用于 fullscreen fragment pass，需评估是否真的比 fragment shader 直接写更高效 [ANDROID]。
  - 适用条件：compute 需要 shared memory tile 优化、subgroup 操作、或跨 workgroup 聚合时收益明显 [HEUR]。
- rotation / resize 触发 swapchain recreate，若 storage image 与 surface extent 绑定，需重建并重新 transition [ANDROID]。
- pause / resume 时，避免在 surface destroy 后提交含 storage image 的 compute 命令 [ANDROID]。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkCmdDispatch-None-04547`（storage image layout 错误）、`VUID-vkCmdDispatch-None-08612`（format qualifier 不匹配）等 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 storage image descriptor、layout、format qualifier 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：Texture Viewer 中可见 compute 写入后的 image 内容；Image Layout 状态正确 [TOOL]。
- [ ] 截图 / 数值验证：compute 输出 image 在后续 graphics pass 中采样结果正确，无色彩偏移、黑屏、条纹。
- [ ] logcat（Android）：无 validation error；可输出 storage image 尺寸与 dispatch 网格用于校验。
- [ ] 性能指标：
  - compute dispatch 耗时稳定，无过大 workgroup；
  - AGI 中 storage image write 与 graphics read 之间无过长 stall；
  - bandwidth 在适用场景下优于 graphics fullscreen pass [TOOL]。
- [ ] resize / pause / resume 后 storage image 内容正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **未加 `STORAGE_BIT`**：image usage 缺失导致 descriptor update 失败 [SPEC]。
2. **compute 写布局错误**：storage image 写入时未在 `GENERAL` 布局，触发 validation error [SPEC]。
3. **format qualifier 不匹配**：GLSL `layout(rgba8)` 与 image format 不一致 [SPEC]。
4. **compute → graphics 同步缺失**：output image 未 barrier 到 `SHADER_READ_ONLY_OPTIMAL`，fragment shader 采样读到旧数据 [TOOL]。
5. **multisample storage image**：创建 image 时 `samples > 1`，compute pipeline 无法绑定 [SPEC]。
6. **subresource range 错误**：barrier 范围与实际 image 维度不匹配，导致部分区域未同步 [SPEC]。
7. **in-place read/write hazard**：同一 image 既读又写未做 ping-pong，产生 artifact [SPEC]。
8. **Android surface recreate 期间提交 compute**：queue 关联的 surface 已 destroy，导致 device lost [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- storage image 格式、尺寸、usage、mip 层级。
- format properties 中 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT` 是否支持。
- compute shader `imageStore` 代码与 format qualifier。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 storage image layout 与内容。
- Android lifecycle 日志。

# Workflow: Add Texture Sampling Pass

## 0. 适用范围

### 适用

- 已有 mesh / scene 渲染 pass，需要为材质新增 texture 采样（albedo / diffuse / normal / roughness / metallic / AO 等）。
- 需要完整走通 sampler、image view、descriptor set、shader 采样、layout transition、生命周期管理。
- 新增带贴图的 object / material pass，或将纯色材质替换为纹理材质。

### 不适用

- 纯 procedurally generated 颜色，不需要 texture。
- 纯 compute shader 采样 storage image（见 `../03_compute_workflows/compute_write_storage_image.md`）。
- 纹理仅用于后处理 fullscreen pass（见 `add_postprocess_pass.md`）。
- 使用外部材质系统已封装好的 texture binding。

---

## 1. 任务目标

在 graphics pass 中新增 material texture 采样：

```text
Material Texture Data（file / procedural）
→ Upload to VkImage（staging buffer / host-visible image）
→ Layout Transition to SHADER_READ_ONLY_OPTIMAL
→ VkImageView + VkSampler
→ Descriptor Set Update（COMBINED_IMAGE_SAMPLER / SAMPLED_IMAGE + SAMPLER）
→ Bind Descriptor Set in Command Buffer
→ Fragment Shader samples texture
→ Color output to render target
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 纹理源：文件（PNG/JPG/KTX）、程序化生成、streaming、atlas。
- 纹理格式：`VK_FORMAT_R8G8B8A8_UNORM`、`VK_FORMAT_BC7_UNORM_BLOCK`、`VK_FORMAT_ASTC_*` 等。
- 尺寸、mip 层级、数组层、sample count（通常为 1）。
- 用途：`TRANSFER_DST | SAMPLED`，可能附加 `COLOR_ATTACHMENT` / `STORAGE`。
- 是否压缩纹理；目标 GPU 对 BC/ASTC/ETC 的支持。
- 采样需求：filter、mipmap mode、address mode、anisotropy、compare op。
- 是否使用 descriptor array / bindless；是否使用 descriptor indexing。
- 是否已有 descriptor set layout / pipeline layout 可复用。

---

## 3. 前置检查

- [ ] 目标 format 的 `optimalTilingFeatures` 包含 `VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT` [SPEC]。
- [ ] 若使用压缩格式，已检查 physical device 对 `BC` / `ASTC` / `ETC` 的支持 [ANDROID]。
- [ ] `maxImageDimension2D` / `maxSamplerAllocationCount` / `maxBoundDescriptorSets` 不超限 [SPEC]。
- [ ] Staging buffer / upload queue / upload command buffer 可用。
- [ ] Descriptor pool 对 `COMBINED_IMAGE_SAMPLER` / `SAMPLED_IMAGE` / `SAMPLER` 有足够容量 [SPEC]。
- [ ] Shader 中 set/binding/type 与 descriptor set layout 一致 [TOOL]。
- [ ] RenderDoc / AGI 可抓帧验证 texture 内容与 binding [TOOL]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪 [ANDROID]。

---

## 4. Vulkan 对象链路

```text
CPU Pixel Data
→ VkBuffer（Staging / Host-visible, usage = TRANSFER_SRC）
→ VkCommandBuffer
    → Pipeline Barrier: UNDEFINED → TRANSFER_DST_OPTIMAL
    → vkCmdCopyBufferToImage
    → Generate Mipmaps（vkCmdBlitImage + barriers, optional）
    → Pipeline Barrier: TRANSFER_DST_OPTIMAL → SHADER_READ_ONLY_OPTIMAL
→ VkImage（usage = TRANSFER_DST | SAMPLED, tiling = OPTIMAL）
→ VkDeviceMemory / VMA allocation
→ VkImageView（viewType = 2D, aspectMask = COLOR_BIT）
→ VkSampler（magFilter / minFilter / mipmapMode / addressModeUVW / maxAnisotropy）
→ VkDescriptorSetLayout（binding = COMBINED_IMAGE_SAMPLER）
→ VkDescriptorSet
→ VkPipelineLayout
→ Graphics Pipeline
→ vkCmdBindDescriptorSets
→ Fragment Shader（texture(sampler2D, texCoord)）
→ Render Target
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| staging buffer | `VkBuffer` | `TRANSFER_SRC` | 上传完成后可释放或复用 | 否 |
| texture image | `VkImage` | `TRANSFER_DST | SAMPLED` [SPEC] | 资源 / 场景 / 材质生命周期 | 否（通常） |
| texture memory | `VkDeviceMemory` | device-local | 跟随 image | 否 |
| texture image view | `VkImageView` | `VK_IMAGE_VIEW_TYPE_2D` | 跟随 image | 否 |
| sampler | `VkSampler` | 采样参数 | renderer 或 per-material 生命周期 | 否 |
| descriptor set | `VkDescriptorSet` | texture binding | per-material / per-frame | 视更新策略 |
| uniform buffer / push constant | `VkBuffer` / push constant | material constants（tiling、UV scale、blend） | per-frame / per-draw | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | albedo image view + sampler | Fragment [SPEC] |
| set=1,binding=1 | `COMBINED_IMAGE_SAMPLER` | normal map image view + sampler | Fragment [SPEC] |
| set=1,binding=2 | `COMBINED_IMAGE_SAMPLER` | roughness/metallic/AO image view + sampler | Fragment [SPEC] |
| set=1,binding=3 | `SAMPLED_IMAGE` + `SAMPLER`（可选，分离采样） | image view / sampler | Fragment [SPEC] |
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame constants（MVP） | Vertex / Fragment [HEUR] |
| push constant | `VkPushConstantRange` | material id、UV scale、blend factor | Vertex / Fragment [HEUR] |

设计说明：

- 常规材质优先使用 `COMBINED_IMAGE_SAMPLER`，移动端驱动优化路径更成熟 [ANDROID]。
- 若同一张 texture 在不同 draw 中需要不同采样方式（如 nearest vs linear），使用分离 `SAMPLED_IMAGE + SAMPLER` 可减少 sampler 数量 [HEUR]。
- Descriptor 中 `imageLayout` 必须为 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`（graphics 采样）或 `VK_IMAGE_LAYOUT_GENERAL`（compute 采样） [SPEC]。
- Normal map 建议使用 `VK_FORMAT_R8G8B8A8_UNORM` 或 `VK_FORMAT_R16G16_SFLOAT`；移动端优先压缩格式 [ANDROID]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| upload copy (`TRANSFER`) | texture image | `TRANSFER_WRITE` → `SHADER_READ` / `TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fragment shader sample [SPEC] |
| graphics/compute write | texture image | `COLOR_ATTACHMENT_WRITE` / `SHADER_WRITE` → `SHADER_READ` | fragment shader sample [SPEC] |
| previous frame sample | texture image | 保持 `SHADER_READ_ONLY_OPTIMAL` | 当前 frame fragment shader sample（无需 barrier） [HEUR] |

必须说明：

- producer stage：`VK_PIPELINE_STAGE_TRANSFER_BIT`（上传）或 `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` / `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT`（运行时写入）。
- producer access：`VK_ACCESS_TRANSFER_WRITE_BIT` / `VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT` / `VK_ACCESS_SHADER_WRITE_BIT`。
- oldLayout：`VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL` 或 `VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL` / `VK_IMAGE_LAYOUT_GENERAL`。
- newLayout：`VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`（graphics 采样）或 `VK_IMAGE_LAYOUT_GENERAL`（compute 读写）。
- consumer stage：`VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` 或 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT`。
- consumer access：`VK_ACCESS_SHADER_READ_BIT`。

---

## 8. 实现步骤

1. **确认格式支持**：
   - 调用 `vkGetPhysicalDeviceFormatProperties` 检查 `optimalTilingFeatures` 是否包含 `FORMAT_FEATURE_SAMPLED_IMAGE_BIT` [SPEC]。
   - 压缩格式需检查对应 `BC` / `ASTC` / `ETC` feature；移动端优先 ASTC/ETC2 [ANDROID]。
2. **创建 `VkImage`**：
   - `imageType=2D`、`extent`、`mipLevels`、`arrayLayers`、`format`、`samples=1`。
   - `tiling=OPTIMAL`。
   - `usage=VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT`；若需运行时写入，追加对应 flag [SPEC]。
3. **分配并绑定 memory**：查询 `vkGetImageMemoryRequirements`，选择 device-local memory type，调用 `vkAllocateMemory` + `vkBindImageMemory`；或使用 VMA [ENGINE]。
4. **创建 staging buffer**：
   - `usage=TRANSFER_SRC`，大小 >= 图像数据总大小。
   - 内存类型：`HOST_VISIBLE` + `HOST_COHERENT` 或手动 `vkFlushMappedMemoryRanges` [SPEC]。
5. **上传数据**：
   - `vkMapMemory` 拷入像素数据；非 coherent 内存调用 `vkFlushMappedMemoryRanges` [SPEC]。
6. **录制上传命令**：
   - barrier：`UNDEFINED` → `TRANSFER_DST_OPTIMAL` [SPEC]。
   - `vkCmdCopyBufferToImage` [SPEC]。
   - 若生成 mipmaps：循环 `vkCmdBlitImage` + barrier [SPEC]。
   - barrier：`TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` [SPEC]。
7. **提交上传**：提交到 graphics / transfer queue，使用 `VkFence` 或 `vkQueueWaitIdle` 等待完成。
8. **释放/复用 staging**：上传完成后销毁 staging buffer / memory 或回收到 upload ring buffer [ENGINE]。
9. **创建 `VkImageView`**：
   - `viewType=2D`、`format` 与 image 一致、`aspectMask=COLOR_BIT`（depth texture 使用 `DEPTH_BIT`） [SPEC]。
10. **创建 `VkSampler`**：
    - 设置 `magFilter`、`minFilter`、`mipmapMode`、`addressModeUVW`、`anisotropyEnable`、`maxAnisotropy`、`compareOp` 等。
    - `maxAnisotropy` 需 `samplerAnisotropy` feature 支持 [SPEC]。
11. **更新 descriptor**：
    - 填写 `VkDescriptorImageInfo`（image view + sampler + layout）。
    - 调用 `vkUpdateDescriptorSets` 写入 `VkWriteDescriptorSet` [SPEC]。
12. **创建 / 更新 pipeline layout**：确保 descriptor set layout 包含 texture binding [SPEC]。
13. **编写 shader**：
    - Vertex shader 输出 UV。
    - Fragment shader 使用 `layout(set=1, binding=0) uniform sampler2D albedoTex;` 采样 [SPEC]。
14. **录制渲染命令**：
    - bind pipeline。
    - `vkCmdBindDescriptorSets` 绑定包含 texture 的 descriptor set。
    - push constants / bind vertex & index buffers。
    - draw [SPEC]。
15. **接入 resize / recreate**：纯静态 texture 通常不随 swapchain 重建；若 texture 尺寸与 viewport 绑定，重建后更新 image view 和 descriptor [ENGINE]。
16. **接入销毁路径**：按 `image view → image → memory → sampler` 顺序销毁；sampler 若为全局复用则按全局生命周期管理 [ENGINE]。

---

## 9. Android 注意点

- 创建 `VkImage` 前确保 `ANativeWindow` / `VkSurfaceKHR` 已创建；texture 上传命令通常提交到与渲染同一 queue，queue 必须在 device 创建后有效 [ANDROID]。
- 移动端优先使用 ASTC / ETC2 压缩格式降低 bandwidth；需调用 `vkGetPhysicalDeviceFormatProperties` 确认支持 [ANDROID]。
- Android 10+ 部分设备对 `LINEAR` tiling sampled image 支持有限，纹理默认使用 `OPTIMAL` tiling [SPEC]。
- pause / resume 时 staging buffer 可能被释放；恢复后若 texture 未持久化到 device-local memory，需要重新上传 [ANDROID]。
- rotation / resize 导致 swapchain recreate 时，仅当 texture 尺寸/比例与 surface 相关时才重建 [ANDROID]。
- `samplerAnisotropy` 在部分低端 Android 设备不可用，需 fallback 到 `anisotropyEnable = VK_FALSE` [ANDROID]。
- AGI / logcat 验证：上传完成后检查 `adb logcat -s vulkan` 无 `VUID-vkCmdCopyBufferToImage-*` 错误；AGI 中确认 texture 采样 bandwidth [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCreateImage-*`、`VUID-vkCmdCopyBufferToImage-*`、`VUID-vkUpdateDescriptorSets-*`、`VUID-vkCmdDraw-*-None-02699` 错误 [TOOL]。
- [ ] RenderDoc / AGI：Texture 查看器中可见 image 内容、format、尺寸、mip 层级；Pipeline State 中可见 sampler 与 descriptor binding [TOOL]。
- [ ] 截图符合预期：fragment shader 采样结果颜色/纹理细节正确，材质区分明显。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出自定义 tag 确认 upload fence 完成与 descriptor binding。
- [ ] 性能指标：
  - 单张 texture upload CPU 耗时 < 预期阈值（按分辨率/格式）；
  - GPU 采样阶段 bandwidth 在 AGI 中无异常峰值；
  - 多材质场景下 sampler / descriptor 数量未超限 [TOOL]。
- [ ] resize / pause / resume 后 texture 仍正确绑定。
- [ ] 多帧运行稳定，无 flickering 或 descriptor 悬垂。

---

## 11. 常见失败模式

1. **格式不支持**：未检查 `vkGetPhysicalDeviceFormatProperties`，在 Mali/Adreno 上某些 `BC` 格式不可用 [ANDROID]。
2. **Image usage 缺失**：创建 image 时未加 `VK_IMAGE_USAGE_TRANSFER_DST_BIT` 或 `VK_IMAGE_USAGE_SAMPLED_BIT`，导致 copy 或采样报错 [SPEC]。
3. **Layout transition 缺失/错误**：上传后仍处于 `TRANSFER_DST_OPTIMAL`，fragment shader 采样触发 `IMAGE_LAYOUT_ERROR` [TOOL]。
4. **Descriptor imageLayout 与实际 layout 不一致**：descriptor 写 `SHADER_READ_ONLY_OPTIMAL` 但 image 实际为 `GENERAL` [SPEC]。
5. **Shader set/binding 不匹配**：descriptor set layout 与 shader 反射不一致，draw 时报错 [TOOL]。
6. **Staging buffer 未对齐**：`vkGetBufferMemoryRequirements` alignment 未满足，copy offset 产生 validation error [SPEC]。
7. **Mip 层级不匹配**：`mipLevels > 1` 但未生成 mip，sampler `mipmapMode=LINEAR` 时画面闪烁 [HEUR]。
8. **Sampler 数量超限**：未检查 `maxSamplerAllocationCount`，大量材质时 `vkCreateSampler` 失败 [SPEC]。
9. **Anisotropy 未检查 feature**：在 unsupported device 上启用 `anisotropyEnable = VK_TRUE` [SPEC]。
10. **Android rotation 后 descriptor 悬垂**：texture 与 viewport 尺寸相关时，重建后未更新 descriptor set [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / GPU / Vulkan 版本。
- 目标 format 及 `vkGetPhysicalDeviceFormatProperties` 输出。
- `VkImageCreateInfo`、`VkSamplerCreateInfo` 参数。
- Shader 反射输出（set/binding/type/stage）。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 image view / descriptor / sampler 绑定状态。
- Upload command buffer 的 barrier 参数。
- Android lifecycle 日志。

---

## 15. 需要回查官方文档的情况

1. 不同 GPU 对压缩格式（BC/ASTC/ETC）的采样与过滤支持差异。
2. `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 与 `VK_IMAGE_LAYOUT_GENERAL` 在不同 shader stage 与 image format 下的合法性。
3. `samplerAnisotropy` feature 与 `maxAnisotropy` 的实际限制。
4. Descriptor indexing / bindless texture 在 Vulkan 1.2+ 中的启用与使用。
5. Android 特定设备对 `OPTIMAL` tiling 与 `LINEAR` tiling 的采样限制差异。

# Workflow: Add Texture Resource

## 0. 适用范围

### 适用

- 新增可被 shader 采样的 texture：color / normal / roughness / height / LUT / shadow map 等。
- 需要完整走通 image、image view、memory、sampler、upload、layout transition、descriptor update 与生命周期。
- 静态纹理、streamable 纹理、per-frame 动态更新纹理均可作为输入。

### 不适用

- 纯 color attachment / depth attachment 不采样输出（见 `add_offscreen_image.md`）。
- 不需要 GPU 采样、仅 CPU 可读的 staging buffer。
- 使用 external memory / AHardwareBuffer 导入的纹理（需要额外扩展）。

---

## 1. 任务目标

在 renderer 中新增一个可被 fragment/compute shader 采样的 texture 资源，完成：

```text
CPU 图像数据
→ Staging Buffer / Host-visible Image
→ vkCmdCopyBufferToImage / vkCmdCopyImage
→ Layout Transition (TRANSFER_DST → SHADER_READ_ONLY)
→ Descriptor Update (COMBINED_IMAGE_SAMPLER / SAMPLED_IMAGE)
→ Shader 采样
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux / 其他。
- Vulkan 版本：1.0 / 1.1 / 1.2 / 1.3。
- 图像源：文件、程序化生成、渲染目标、流式加载。
- 格式：`VK_FORMAT_R8G8B8A8_UNORM`、`VK_FORMAT_BC7_*`、`VK_FORMAT_R16G16B16A16_SFLOAT` 等。
- 尺寸、mip 层级、数组层、sample count。
- 用途：`SAMPLED`、`TRANSFER_DST`、`COLOR_ATTACHMENT`（如需要）等。
- 是否要求 tilable / linear tiling。
- 是否使用 dedicated allocation 或自定义 allocator（VMA）。
- 是否已存在 descriptor set / pipeline layout 可复用。
- 目标设备对 compressed format 的支持。

---

## 3. 前置检查

- [ ] Validation Layer 已启用并可输出到 logcat / console。
- [ ] 物理设备支持目标 `VkFormat` 的 `FORMAT_FEATURE_SAMPLED_IMAGE_BIT`。
- [ ] 若使用压缩格式，已检查 `vkGetPhysicalDeviceFormatProperties` 的 `optimalTilingFeatures`。
- [ ] 已确认 `maxImageDimension2D` / `maxSamplerAllocationCount` 不超限。
- [ ] Staging buffer / 上传队列可用。
- [ ] Descriptor pool 对 `COMBINED_IMAGE_SAMPLER` 或 `SAMPLED_IMAGE` 有足够容量。
- [ ] RenderDoc / AGI 可抓帧验证 texture 内容。
- [ ] Android 输出相关资源的 Surface 生命周期可追踪；普通离屏 texture 不要求 Surface。

---

## 4. Vulkan 对象链路

```text
CPU Pixel Data
→ VkBuffer (Staging / Host-visible)
→ VkCommandBuffer (copy + barrier)
→ VkImage
→ VkDeviceMemory (or VMA allocation)
→ VkImageView
→ VkSampler
→ VkDescriptorSetLayout
→ VkDescriptorSet
→ VkPipelineLayout
→ Shader (Fragment / Compute)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| staging buffer | `VkBuffer` | `TRANSFER_SRC` | 上传完成后可释放或复用 | 否 |
| texture image | `VkImage` | `TRANSFER_DST \| SAMPLED` [SPEC] | 资源生命周期 / 场景生命周期 | 否（通常） |
| texture memory | `VkDeviceMemory` | device-local | 跟随 image | 否 |
| texture image view | `VkImageView` | `VK_IMAGE_VIEW_TYPE_2D` | 跟随 image | 否 |
| sampler | `VkSampler` | 采样参数配置 | renderer 生命周期或按材质分组 | 否 |
| descriptor set | `VkDescriptorSet` | image binding | per-frame / per-material | 视更新策略而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` | image view + sampler | Fragment / Compute |
| set=0,binding=1 | `SAMPLED_IMAGE` + 独立 `SAMPLER`（若需分离） | image view / sampler | Fragment / Compute |

设计说明：

- 若同一张 texture 在不同 draw 中采样方式不同，使用分离 `SAMPLED_IMAGE + SAMPLER` 可减少 sampler 数量 [HEUR]。
- `COMBINED_IMAGE_SAMPLER` 在移动端驱动优化路径更成熟，优先用于常规材质 [ANDROID]。
- 描述符中 `imageLayout` 必须为 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 或 `VK_IMAGE_LAYOUT_GENERAL` 等所选描述符允许的 layout；compute 采样不强制 GENERAL [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| upload copy (`TRANSFER`) | texture image | `TRANSFER_WRITE` → `SHADER_READ` / `TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fragment shader sample |
| graphics/compute write | texture image | `COLOR_ATTACHMENT_WRITE` / `SHADER_WRITE` → `SHADER_READ` | fragment shader sample |

必须说明：

- producer stage：`VK_PIPELINE_STAGE_TRANSFER_BIT` 或 `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` / `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT`。
- producer access：`VK_ACCESS_TRANSFER_WRITE_BIT` / `VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT` / `VK_ACCESS_SHADER_WRITE_BIT`。
- oldLayout：`VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL` 或 `VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL` / `VK_IMAGE_LAYOUT_GENERAL`。
- newLayout：`VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`（包括 compute 只读采样）或 `VK_IMAGE_LAYOUT_GENERAL`（storage 读写，核对 usage）。
- consumer stage：`VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` 或 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT`。
- consumer access：`VK_ACCESS_SHADER_READ_BIT`。

---

## 8. 实现步骤

1. **确认格式支持**：调用 `vkGetPhysicalDeviceFormatProperties`，检查 `optimalTilingFeatures` 是否包含 `VK_FORMAT_FEATURE_SAMPLED_IMAGE_BIT`；压缩格式还需检查对应 `BC` / `ASTC` / `ETC` feature [SPEC]。
2. **创建 `VkImage`**：填写 `VkImageCreateInfo`，设置 `imageType=2D`、`extent`、`mipLevels`、`arrayLayers`、`format`、`usage=TRANSFER_DST | SAMPLED`、`samples=1`、`tiling=OPTIMAL`；调用 `vkCreateImage`。
3. **分配内存**：通过 `vkGetImageMemoryRequirements` 查询 size/alignment/typeBits，选择 device-local memory type；调用 `vkAllocateMemory` 并 `vkBindImageMemory`；若使用 VMA，调用 `vmaCreateImage` [ENGINE]。
4. **创建 staging buffer**：分配 host-visible buffer（`VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | HOST_COHERENT_BIT` 或手动 flush），`usage=TRANSFER_SRC`，大小 >= 图像数据总大小。
5. **上传数据**：`vkMapMemory` 将像素数据拷入 staging buffer；若内存非 coherent，调用 `vkFlushMappedMemoryRanges`。
6. **录制上传命令**：
   - 使用 `vkCmdPipelineBarrier` 将 image 从 `UNDEFINED` 转换到 `TRANSFER_DST_OPTIMAL`；
   - 使用 `vkCmdCopyBufferToImage` 从 staging buffer 复制到 image；
   - 若生成 mipmaps，先确认格式 blit/filter 能力；支持时逐层 blit+barrier，否则离线生成/选受支持替代；
   - 使用 `vkCmdPipelineBarrier` 从 `TRANSFER_DST_OPTIMAL` 转换到 `SHADER_READ_ONLY_OPTIMAL` [SPEC]。
7. **提交上传**：将命令缓冲提交到 graphics 或 transfer queue，使用 `VkFence` 或 `vkQueueWaitIdle` 等待完成。
8. **释放/复用 staging**：上传完成后 `vkDestroyBuffer` + `vkFreeMemory` 或回收到 upload ring buffer。
9. **创建 `VkImageView`**：填写 `VkImageViewCreateInfo`，`viewType=2D`、`aspectMask=COLOR_BIT`（depth texture 使用 `DEPTH_BIT`），调用 `vkCreateImageView`。
10. **创建 `VkSampler`**：根据过滤需求设置 `magFilter`、`minFilter`、`mipmapMode`、`addressModeUVW`、`anisotropyEnable`、`maxAnisotropy`、`compareOp` 等；检查 `samplerAnisotropy` feature [SPEC]。
11. **更新 descriptor**：填写 `VkDescriptorImageInfo`（image view + sampler + layout），调用 `vkUpdateDescriptorSets` 写入 `VkWriteDescriptorSet`。
12. **接入渲染命令**：在绘制前 `vkCmdBindDescriptorSets`，确保 image layout 与 descriptor 声明一致。
13. **接入生命周期/销毁**：在 renderer 销毁或资源卸载时按 `image view → image → memory → sampler` 顺序销毁；sampler 若为全局复用则按全局生命周期管理 [ENGINE]。
14. **接入 resize / recreate**：纯静态 texture 通常不随 swapchain 重建；若 texture 尺寸与 viewport 绑定，重建后更新 image view 和 descriptor。

---

## 9. Android 注意点

- 普通 texture 的创建/上传要求有效 Device、格式/usage 能力、内存与 queue，不要求先有 ANativeWindow、Surface 或 swapchain。项目若把 queue 初始化绑在窗口流程上，应标项目依赖；外部 AHB 与呈现 image 另有合同 [SPEC][ENGINE]。
- pause / resume 时 staging buffer 可能被释放；恢复后若 texture 未持久化到 device-local memory，需要重新上传。
- rotation / resize 导致 swapchain recreate 时，仅当 texture 尺寸/比例与 surface 相关时才重建。
- 移动端优先使用 `ASTC` / `ETC2` 压缩格式降低带宽 [ANDROID]；需调用 `vkGetPhysicalDeviceFormatProperties` 确认支持。
- Android 10+ 部分设备对 `LINEAR` tiling sampled image 支持有限，纹理默认使用 `OPTIMAL` tiling [SPEC]。
- AGI / logcat 验证：上传完成后检查 `adb logcat -s vulkan` 无 `VUID-vkCmdCopyBufferToImage-*` 错误。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCreateImage-*`、`VUID-vkCmdCopyBufferToImage-*`、`VUID-vkUpdateDescriptorSets-*`、`VUID-vkCmdDraw-*-None-02699` 等错误 [TOOL]。
- [ ] RenderDoc / AGI：Texture 查看器中可见 image 内容、format、尺寸、mip 层级正确 [TOOL]。
- [ ] 截图符合预期：fragment shader 采样结果颜色/纹理细节正确。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出自定义 tag 确认 upload fence 完成。
- [ ] 性能指标：
  - 单张 texture upload CPU 耗时 < 预期阈值（按分辨率/格式）；
  - GPU 采样阶段 bandwidth 在 AGI 中无异常峰值 [TOOL]；
  - 连续多帧运行稳定，无 `DEVICE_LOST`。
- [ ] resize / pause / resume 后 texture 仍正确绑定。
- [ ] 多帧运行稳定，无 flickering 或 descriptor 悬垂。

---

## 11. 常见失败模式

1. **格式不支持**：未检查 `vkGetPhysicalDeviceFormatProperties`，在 Mali/Adreno 上某些 `BC` 格式不可用 [ANDROID]。
2. **Image usage 缺失**：创建 image 时未加 `VK_IMAGE_USAGE_TRANSFER_DST_BIT`，导致 copy 命令 validation error [SPEC]。
3. **Layout transition 缺失/错误**：上传后仍处于 `TRANSFER_DST_OPTIMAL`，fragment shader 采样触发 `IMAGE_LAYOUT_ERROR` [TOOL]。
4. **Descriptor imageLayout 与实际 layout 不一致**：descriptor 写 `SHADER_READ_ONLY_OPTIMAL` 但 image 实际为 `GENERAL` [SPEC]。
5. **Staging buffer 未对齐**：内存绑定对齐与 buffer-to-image copy offset/压缩块对齐是不同规则，分别检查。
6. **Mip 层级不匹配**：`mipLevels > 1` 但未生成 mip，sampler `mipmapMode=LINEAR` 时画面闪烁 [HEUR]。
7. **Sampler 数量超限**：未检查 `maxSamplerAllocationCount`，大量材质时 `vkCreateSampler` 失败 [SPEC]。
8. **Android rotation 后 descriptor 悬垂**：texture 与 viewport 尺寸相关时，重建后未更新 descriptor set。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / GPU / Vulkan 版本。
- 目标 format 及 `vkGetPhysicalDeviceFormatProperties` 输出。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 image view / descriptor 绑定状态。
- `VkImageCreateInfo`、`VkSamplerCreateInfo` 参数。
- upload command buffer 的 barrier 参数。
- Android lifecycle 日志（surface create/destroy、pause/resume）。

<a id="texture-streaming-residency"></a>
## 15. 内容转码、部分 mip 与驻留（C3）

输入合同：asset hash/version、颜色语义（sRGB/linear/HDR/normal）、尺寸/层数/mip 范围、目标 usage/tiling/filter、Engine/Device/resource generation；输出 initialized/resident 子资源范围与完成点。[ENGINE]

KTX2 是容器，不等于 GPU ASTC/ETC2/BC 格式；Basis ETC1S/UASTC 是可转码内容，supercompression 与最终 GPU block compression 也是不同层。检查实际 payload/DFD/颜色语义；按设备 format properties、image format properties 和所需 feature/usage/tiling/filter 选择最终格式，再调用已固定工具链的转码接口。无目标压缩支持时选择验证过的未压缩替代或拒绝该内容，记录内存/画质变化，不按品牌猜能力。[REF][SPEC]

压缩 mip 要按各层尺寸/块大小/层数计算字节与 copy region，校验 offset、row length、image height 及边缘块例外；不能用 width×height×4 套所有格式。上传已有 mip 链优先；没有合法 BLIT_SRC/BLIT_DST/过滤支持时，不强行运行时 blit，用离线 mip 或受支持替代。compute/storage mip 也须独立能力校验。[SPEC][ENGINE]

```text
Request → CPU Decode/Transcode → Reserve budgets → Upload chunks
→ GPU completion + access visibility → Publish versioned descriptor/view
→ Last consumer retirement → Reuse staging / evict old resource
```

预算包含 CPU 时间、转码临时内存、上传字节、staging in-flight、GPU allocation、新旧版本并存峰值；预算不足暂停/降级，队列背压而非无限积压。跨 queue 的上传与采样建立 semaphore 依赖，exclusive 跨 family 加 ownership transfer；同 queue 按实际 copy→shader 访问 barrier，CPU 发布不替代 GPU 可见性。[SPEC][ENGINE]

只暴露已初始化且允许采样的 mip：首版使用 image view 子范围和安全 sampler LOD，发布新 descriptor 版本；baseMipLevel 改变同时校验 shader LOD 的相对语义，显式 LOD/梯度/邻层过滤都不得落入未初始化内容。不在 in-flight 普通 descriptor set 上任意改写，除非另证实对应 update-after-bind 等条件。[SPEC]

**限制 sampler LOD 不等于释放 image allocation；完整链 allocation 不等于每个 mip 内容已就绪。** 回收预算优先低分辨率替代、整体淘汰或重建小 image；sparse residency 另需 feature/绑定/page 生命周期，不是默认。目标 mip 未就绪保留合法粗 mip/替代纹理。[ENGINE]

取消前未提交的独占 CPU 数据可释放；已提交 copy 引用的 staging/image 等其 GPU 完成，取消迟到结果检查 generation 后拒绝发布。共享纹理由实际 owner/引用与退休协议回收，不随单 Surface/Engine 退出误释放。[ENGINE]

验证：压缩与未压缩、NPOT/最后小 mip、缺格式/过滤、色彩/alpha、预算下降、取消、并发双输出；每层 mip 图像及资源计数证据单列。参考固定 [Vulkan-Docs v1.4.328 resources](https://github.com/KhronosGroup/Vulkan-Docs/blob/d38733398a4bec673bd5d24c904d4739a45f020d/chapters/resources.adoc)、[copies](https://github.com/KhronosGroup/Vulkan-Docs/blob/d38733398a4bec673bd5d24c904d4739a45f020d/chapters/copies.adoc)、[KTX-Software v4.4.0 transcode](https://github.com/KhronosGroup/KTX-Software/blob/beef80159525d9fb7abb8645ea85f4c4f6842e8f/lib/basis_transcode.cpp)。2026-11-01 source-read，未运行转码/GPU。

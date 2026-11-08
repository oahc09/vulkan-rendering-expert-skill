# API Card: VkImage

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | `VkImage` |
| 常用 API | `vkCreateImage` / `vkDestroyImage` / `vkGetImageMemoryRequirements` / `vkBindImageMemory` / `vkCmdPipelineBarrier` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkImage` 是 Vulkan 中表示一维、二维或三维图像资源的对象，涵盖 color / depth / texture / attachment / storage 等多种用途；它的 `usage`、`format`、`layout` 和 `memory` 共同决定可被如何使用。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice
→ VkImage (Create)
→ VkDeviceMemory (Allocate / Bind)
→ VkImageView
→ Descriptor / Attachment / Storage / Transfer
→ Shader / Render Pass / Compute
```

### 上游依赖

- `VkDevice` 必须有效。[SPEC]
- 目标 format / usage / sample count 必须被 physical device 支持。[SPEC]
- 需要可用的 device memory 并满足 memory requirements。[SPEC]

### 下游影响

- `VkImageView` 基于 image 创建，决定 shader / attachment 如何看待 image。
- Descriptor / attachment 使用 image 时要求 image layout 匹配访问方式。[SPEC]
- Compute / graphics pass 通过 barrier 管理 image 状态转换。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImage`
- `VkImageCreateInfo`
- `VkMemoryRequirements`
- `VkDeviceMemory`
- `VkImageMemoryBarrier`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateImage` | 创建 image，不分配内存。[SPEC] |
| `vkDestroyImage` | 销毁 image；绑定 memory 不会自动释放。[SPEC] |
| `vkGetImageMemoryRequirements` | 查询 memory requirements（size / alignment / memoryTypeBits）。[SPEC] |
| `vkGetImageMemoryRequirements2` | 支持 dedicated allocation、device group 等查询。[SPEC] |
| `vkBindImageMemory` / `vkBindImageMemory2` | 绑定 image 到 device memory。[SPEC] |
| `vkCmdPipelineBarrier` | 转换 image layout / access。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_dedicated_allocation` / `VK_KHR_get_memory_requirements2`：优化 GPU 特定图像的内存分配。[GUIDE]
- `VK_EXT_image_drm_format_modifier`：Linux DRM 场景。
- Android 可用性：核心功能全部可用；外部格式（如相机输出）需 `VK_ANDROID_external_memory_android_hardware_buffer`。[ANDROID]

---

## 4. 标准使用流程

```text
vkCreateImage(..., &createInfo, ..., &image)
→ vkGetImageMemoryRequirements(device, image, &memReq)
→ 选择满足 memoryTypeBits 的 memory type
→ vkAllocateMemory(..., &allocInfo, ..., &memory)
→ vkBindImageMemory(device, image, memory, 0)
→ 创建 VkImageView
→ vkCmdPipelineBarrier 转换到目标 layout
→ 作为 attachment / sampled image / storage image / transfer 使用
→ 销毁时:
    等待 GPU idle
    → 销毁 image view
    → 销毁 image
    → 释放 memory
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `imageType` | `1D` / `2D` / `3D`，决定维度和 mipmap 行为。[SPEC] | 把 cube map 当作普通 2D array 创建。[SPEC] |
| `format` | 必须被 physical device 支持；color / depth / compressed format 用途不同。[SPEC] | 使用不支持的 format 导致创建失败。[TOOL] |
| `extent` | 宽度 / 高度 / 深度；为 0 非法。[SPEC] | 最小化或特殊状态下 extent 为 0 仍创建。[ANDROID] |
| `mipLevels` / `arrayLayers` | 决定 mipmap 和 array 层级；`1` 表示无 mipmap / 非 array。[SPEC] | 需要 mipmap 但设为 1。[ENGINE] |
| `samples` | 多采样设置；`VK_SAMPLE_COUNT_1_BIT` 为普通。[SPEC] | 创建 storage image 时误用多采样。[SPEC] |
| `tiling` | `OPTIMAL`（性能优先）或 `LINEAR`（CPU 可 map）；后者有诸多限制。[SPEC] | 需要 CPU 写入但未选 LINEAR，或 LINEAR 下使用不支持的 format。[TOOL] |
| `usage` | 必须覆盖实际用途：`TRANSFER_SRC` / `TRANSFER_DST` / `SAMPLED` / `STORAGE` / `COLOR_ATTACHMENT` / `DEPTH_STENCIL_ATTACHMENT` 等。[SPEC] | usage 缺少 `SAMPLED` 但 shader 要采样；缺少 `TRANSFER_DST` 但要做 upload。[TOOL] |
| `initialLayout` | 创建时 layout，通常为 `VK_IMAGE_LAYOUT_UNDEFINED` 或 `PREINITIALIZED`。[SPEC] | 设为 `SHADER_READ_ONLY_OPTIMAL` 等非法初始 layout。[SPEC] |
| `sharingMode` | `EXCLUSIVE`（单 queue family）或 `CONCURRENT`（多 queue family）；concurrent 有性能开销。[SPEC] | 多 queue 访问但未设 concurrent 或未完成 ownership transfer。[SPEC] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `format` 是否被 physical device 支持？是否查询了 `vkGetPhysicalDeviceFormatProperties`？
- [ ] `usage` 是否覆盖所有预期用途？
- [ ] `tiling` 是否与预期访问方式匹配？
- [ ] `samples` 是否与 usage 兼容？
- [ ] `extent` 是否大于 0？
- [ ] `sharingMode` 是否与 queue family 访问方式匹配？

### 使用阶段

- [ ] 每次访问前 image layout 是否匹配？
- [ ] Descriptor / attachment 中指定的 layout 是否与实际 layout 一致？
- [ ] Barrier 的 subresource range 是否覆盖实际使用区域？

### 销毁阶段

- [ ] 是否等待 GPU 不再访问该 image？
- [ ] 是否先销毁 image view 再销毁 image？
- [ ] Memory 是否单独释放？（image 销毁不释放 memory）[SPEC]

---

## 7. 高频错误

1. `usage` 未包含实际需要的 flag，如 `SAMPLED` / `STORAGE` / `TRANSFER_DST`。[SPEC]
2. `initialLayout` 设错，如直接设为目标使用 layout。[SPEC]
3. Image layout 未通过 barrier 转换就用于 draw / dispatch / copy。[TOOL]
4. Descriptor imageLayout 与实际 layout 不一致。[TOOL]
5. `tiling = OPTIMAL` 但 CPU 直接 map 写入。[SPEC]
6. 多 queue family 访问但未使用 `CONCURRENT` 或 ownership transfer。[SPEC]
7. 销毁 image 前未等待 GPU，导致 device lost。[SPEC]
8. `format` 不支持作为 depth attachment 但被用于 depth。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkImageCreateInfo-*`：format / usage / tiling / samples / extent 合法性。
- `VUID-vkCmdDraw-*` / `VUID-vkCmdDispatch-*`：image layout / descriptor imageLayout 匹配。
- `VUID-vkCmdPipelineBarrier-*`：barrier subresource range / oldLayout / newLayout。

### RenderDoc / AGI

- 查看 image 内容、format、尺寸。
- 查看每个 pass 前后 image layout。
- 查看 descriptor 中 imageLayout 设置。

### 日志 / 代码检查

- 检查 `vkCreateImage` 返回值。
- 检查 `usage` 与 shader / attachment 需求是否匹配。
- 检查 barrier 中 oldLayout / newLayout / stage / access。

---

## 9. 生命周期风险

### 创建时机

- Renderer 初始化时创建长期资源（depth、swapchain-size offscreen）。
- 运行时动态创建 texture / render target。

### 使用时机

- 作为 color / depth attachment。
- 作为 sampled image / storage image。
- 作为 transfer src / dst。

### 销毁时机

- 应用退出、swapchain recreate、资源卸载时。
- 必须等 GPU 完成访问。[SPEC]

### in-flight 风险

- Image 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]
- Swapchain recreate 时，swapchain-size image 必须重建，旧 image 可能仍被 in-flight command buffer 引用。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 上传数据到 image 后，需要 barrier 让 GPU 可见。[SPEC]
- CPU 读取 GPU 写入的 image 通常需要 `LINEAR` tiling 或 staging buffer。[SPEC]

### GPU-GPU 同步

- 跨 pass / 跨 queue 使用 image 必须通过 image memory barrier 同步。[SPEC]
- Producer / consumer 的 stage / access / layout 必须精确匹配。[SPEC]

### 资源访问同步

- `vkCmdPipelineBarrier` 或 render pass begin 中的 attachment layout 负责 image layout transition。[SPEC]
- Storage image 写入后如需读取，必须插入 barrier。[SPEC]

---

## 11. Android 注意点

- Android 上 swapchain-size image（depth / offscreen）在 rotation / resize 后必须重建。[ANDROID]
- 相机 / 视频外部输入 image 通常需要 `VK_ANDROID_external_memory_android_hardware_buffer`。[ANDROID]
- 移动端应避免创建过大尺寸或过多 mipmap 的 texture，受 bandwidth 和内存限制。[ENGINE]
- AGI 可查看 image 的 bandwidth 和 layout transition 开销。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- `vkCreateImage` + `vkAllocateMemory` 是重操作，应避免运行时频繁创建大 image。[ENGINE]
- 使用 memory pool / allocator 减少分配开销。[ENGINE]

### GPU 侧

- `OPTIMAL` tiling 通常性能最好；`LINEAR` tiling 可能降低 cache 效率。[SPEC]
- Image layout transition 和 format conversion 有 GPU 开销，应减少不必要的 barrier。[ENGINE]
- 多采样 image 增加 bandwidth 和存储，移动端慎用。[ENGINE]

### 移动端

- 优先使用压缩格式（ASTC / ETC2）减少带宽。[ENGINE]
- 避免创建大量小 image，合并到 atlas 可降低 descriptor 和 sampler 开销。[HEUR]
- Depth format 选择影响 bandwidth 和精度，需结合 GPU 特性。[ENGINE]

---

## 13. 专家经验

**经验**：
创建 image 时不要只关注 `extent` 和 `format`，必须同时确认 `usage`、`tiling`、`samples`、`sharingMode`；任何一项不匹配都会在后续阶段以难以排查的方式暴露（如 descriptor 更新成功但采样黑屏）。

**适用条件**：
所有使用 VkImage 的场景，尤其是多 pass / compute / storage image 场景。

**不适用情况**：
非常简单的一次性 upload / sampled texture，且使用固定已知 format 时风险较低。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `image_view.md`
- `buffer.md`
- `memory_allocation.md`
- `../08_synchronization/image_memory_barrier.md`
- `../08_synchronization/pipeline_barrier.md`
- `../05_descriptor/descriptor_set.md`
- `../06_pipeline/graphics_pipeline.md`

---

## 15. 需要回查官方文档的情况

1. 特定 format 在目标 physical device 上的 `formatProperties`。
2. `usage` 组合在 `tiling = OPTIMAL` 和 `LINEAR` 下的支持情况。
3. 多采样 image 作为 storage / sampled image 的限制。
4. Queue family ownership transfer 的规则。
5. Android 外部 memory 扩展的具体使用。


<a id="transparent-target-precision"></a>
## 透明中间目标精度

适用：多层 blend/WBOIT/体积/GS；输入为颜色动态范围、最大层数、alpha 最小量级、format/usage/sample count，输出为经能力与误差验证的附件组合。先查 [blend-format-capability](../06_pipeline/graphics_pipeline.md#blend-format-capability)，不可由 FP16 shader 算术支持推断 FP16 blend 或 storage image 支持。[SPEC][ENGINE]

RGBA8 UNORM 每次存储会量化且范围有限，低 alpha 累积可能丢失；FP16 提升范围/精度仍有舍入、下溢和溢出。WBOIT 加权颜色/权重和必须控制有限值、范围与层数；revealage 连乘另有下溢误差。清除值和存储含义见 [resolve](../../05_workflows/02_render_pass_effects/add_postprocess_pass.md#transparency-resolve)。不能简单要求 RGBA8/FP16 逐位相同后归咎驱动。

生命周期：尺寸/format/sample count 变化重建相关 view/descriptor/pipeline；旧代附件与 snapshot/history 等最后读者完成后回收。预算按 width×height×samples×每像素存储以及 frames-in-flight、OIT pool/scratch、新旧代并存计算，实际分配/压缩/带宽需工具证据。高精度不保证节带宽。

回退按误差与能力选择另一受支持格式、层数/效果质量档或排序路线，不能静默裁剪亮度。验证固定线性输入和 FP64 oracle，单独量化输入与逐层存储，输出颜色/alpha 热图和有限值检查；记录 GPU 实现而非假定硬件舍入。[ENGINE]

[SPEC] [Format properties](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceFormatProperties2.html)、[Image format properties](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceImageFormatProperties2.html)。


<a id="vulkan-video-contract"></a>
## Vulkan Video：session / profile / DPB 合同

**不是 MediaCodec 导入。** Vulkan Video 在 Vulkan queue 上执行 codec 命令；MediaCodec → AHB → Vulkan 只消费外部解码结果，见 [互操作边界](external_resource_interop.md#vulkan-video-boundary)。两者不共享“已支持解码”的证据。[SPEC]

**查询并拒绝不支持的组合。** 启用 `VK_KHR_video_queue`、decode 或 encode queue 扩展及选定 codec 扩展的完整依赖。由 `vkGetPhysicalDeviceQueueFamilyProperties2` 链 `VkQueueFamilyVideoPropertiesKHR` 确认 VIDEO_DECODE/VIDEO_ENCODE queue flag 与 codec operation；创建对应 queue。`VkVideoProfileInfoKHR` 指定 operation、chromaSubsampling、luma/chromaBitDepth，并链 codec-specific profile。调用 `vkGetPhysicalDeviceVideoCapabilitiesKHR` 与 `vkGetPhysicalDeviceVideoFormatPropertiesKHR`，同时核对 profile、usage、format、image type/tiling 与 extent，不能只看扩展名。资源 `VkVideoProfileListInfoKHR` 与 session profile 兼容；profile-independent resource 是额外 feature/创建条件，不是默认豁免。[SPEC]

**冻结 codec 范围。** H.264、H.265、AV1 各有 decode 和 encode 扩展；VP9 为 `VK_KHR_video_decode_vp9`，不能编造 VP9 encode。H.264/H.265 参数集分别遵守 SPS/PPS、VPS/SPS/PPS 及 codec operation VU；AV1 使用 sequence header 和 frame/reference 映射；VP9 按其 picture info/reference 定义。codec-specific profile、capabilities、session parameters、picture/DPB slot pNext 不能互换；头文件 StdVideo 版本必须受 session 支持。该入口不替代各 codec 的 bitstream 与参考图像语义审查。[SPEC]

**正常对象链。** profile/capabilities/formats → `vkCreateVideoSessionKHR`（queueFamilyIndex、maxCodedExtent、pictureFormat、referencePictureFormat、maxDpbSlots、maxActiveReferencePictures、pStdHeaderVersion）→ `vkGetVideoSessionMemoryRequirementsKHR` → 为每个 memoryBindIndex 按 size/alignment/memoryTypeBits 分配 → `vkBindVideoSessionMemoryKHR` 绑定全部要求 → 按 codec 创建 `VkVideoSessionParametersKHR`（VP9 不使用；AV1 不支持 update，见下表）→ profile 兼容的 bitstream buffer、picture/DPB image/view → `vkCmdBeginVideoCodingKHR` → 新 session 首次使用 `vkCmdControlVideoCodingKHR` / `VK_VIDEO_CODING_CONTROL_RESET_BIT_KHR` → decode/encode → `vkCmdEndVideoCodingKHR` → submit/completion。允许 update 的 codec 参数对象按 `updateSequenceCount` 递增及 codec 更新规则，不能原地任意改写已安装参数；提交使用结束前保留 session、parameters、全部绑定内存和图片资源。[SPEC]

**Decode 路径。** `vkCmdDecodeVideoKHR` 的 srcBufferOffset/srcBufferRange 满足 `minBitstreamBufferOffsetAlignment` / `minBitstreamBufferSizeAlignment` 和容量；bitstream 使用 VIDEO_DECODE_SRC。dstPictureResource 用 VIDEO_DECODE_DST layout/usage；reference/reconstructed DPB 用 VIDEO_DECODE_DPB。查询 `VkVideoDecodeCapabilitiesKHR.flags` 的 DPB_AND_OUTPUT_COINCIDE / DPB_AND_OUTPUT_DISTINCT 支持后决定输出与 DPB 是否共用，不能假定总是同一 image；AV1 film grain 强制不同输出/重建资源的特例见下表。`pSetupReferenceSlot` 更新重建参考，`pReferenceSlots` 声明本次实际参考；slotIndex、image subresource、codec picture identity 都要一致。[SPEC]

**Encode 路径。** `vkCmdEncodeVideoKHR` 从 VIDEO_ENCODE_SRC 图片读取，写 VIDEO_ENCODE_DST bitstream buffer 并更新 VIDEO_ENCODE_DPB 重建参考。按 capabilities 与 quality-level 查询选择 rate-control mode、layers、bitrate/virtual buffer；用控制命令更新状态，begin scope 描述需匹配持久 rate-control 状态。codec-specific GOP/参考图像合法性不由通用 rate control 修复。使用已支持的 `VK_QUERY_TYPE_VIDEO_ENCODE_FEEDBACK_KHR` 查询实际写入 offset/bytes 与 feedback，结果可用后才消费；不把整个分配容量当有效码流长度。参数导出按 `vkGetEncodedVideoSessionParametersKHR` 与 feedback 处理实现覆盖，不盲用输入参数集代替最终输出。[SPEC]

**同步与复用。** DPB slot 状态与 backing image 内容是两件事；某次提交完成不代表未来帧不再引用该 DPB。按 codec 引用关系退休/重绑 slot，禁止只用 frameIndex 循环覆写仍活跃参考。上传→VIDEO_DECODE/ENCODE READ、codec WRITE→采样/传输或下次 codec READ，使用对应 `VK_PIPELINE_STAGE_2_VIDEO_DECODE_BIT_KHR` / `VK_PIPELINE_STAGE_2_VIDEO_ENCODE_BIT_KHR` 与 VIDEO_*_READ/WRITE access；bitstream host 读取还需 completion 和非 coherent invalidate。独占资源跨 video/graphics family 使用匹配 release/acquire 与 semaphore，布局转换不是执行依赖的替代品。[SPEC]

**失败与回退。** profile/format/StdVideo 版本不支持、session 内存绑定失败时不录制 coding；释放仅实际创建的对象和仍自有分配。结果状态查询须先核对 queue 的 `queryResultStatusSupport` 与所用查询能力；失败 decode/encode 的图片/DPB 不当有效输出，依据 reset/rebuild 与 codec 随机访问点恢复参考链。容量不足不得消费截断输出。扩展或 queue 缺失时返回 UNSUPPORTED，选择独立的 MediaCodec/平台 codec 或软件 codec 路径；不得把 fallback 成功记录成 Vulkan Video 成功。[ENGINE]

验证先做 CPU profile/资源/DPB 状态负例，再用合法自制码流分别验证 H.264/H.265/AV1/VP9 实际能力、图片正确性、码流反馈和重置恢复。当前仅 source-read 与静态回归；各 codec 深层参数语义、量化图、intra refresh、RGB conversion 等稳定扩展仍须独立 L1/L2 评审，不能由这个共同流程宣称全部覆盖。

固定规范（Vulkan 1.4.368，source-read；不是设备验证）：[video-profiles / video-format-capabilities / video-session-memory-association / dpb-slot-states / video-session-uninitialized](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/videocoding.adoc)；[decode operations](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/decode.adoc)；[encode operations / encode-rate-control](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/encode.adoc)；[H264 decode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h264_decode.adoc)；[H264 encode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h264_encode.adoc)；[H265 decode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h265_decode.adoc)；[H265 encode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h265_encode.adoc)；[AV1 decode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/av1_decode.adoc)；[AV1 encode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/av1_encode.adoc)；[VP9 decode](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/vp9_decode.adoc)。


<a id="vulkan-video-codec-differences"></a>
### 冻结版本的七种 codec operation：不能跨 codec 套用合同

以下每行是已读规范的 **targeted L1/L2 合同**，不是完整 codec 规范、一致性测试或设备 PASS。冻结 Registry 只有七个已发布 codec 扩展：H.264/H.265/AV1 各 decode+encode，VP9 仅 decode。每个 profile 还包含 chroma/bit depths；不能把某 profile 的成功推广到同 codec 的其他 profile，更不能从 decode 推断 encode。

依赖与启用：七个 codec 扩展分别依赖 `VK_KHR_video_decode_queue` 或 `VK_KHR_video_encode_queue`，两者依赖 `VK_KHR_video_queue` 与 Sync2（`VK_KHR_synchronization2` 或 Vulkan 1.3）。video_queue 本身要求 `(Vulkan 1.1 + VK_KHR_synchronization2) 或 Vulkan 1.3`。此外 AV1 encode 必须启用 `VkPhysicalDeviceVideoEncodeAV1FeaturesKHR.videoEncodeAV1`（10269），VP9 decode 必须启用 `VkPhysicalDeviceVideoDecodeVP9FeaturesKHR.videoDecodeVP9`（10793）；不能把这两个 feature gate 省掉，也不能为其他 codec 臆造同名 feature。均未在本冻结版本晋升 core。正常/失败/回退共用上节 session、资源同步与状态恢复合同，再应用下表差异。[SPEC]

| 已发布扩展与查询差异 | Session / 参数合同 | Picture / DPB / 输出差异与拒绝条件 |
|---|---|---|
| `VK_KHR_video_decode_h264`：`VkVideoDecodeH264ProfileInfoKHR.stdProfileIdc` + `pictureLayout`；`VkVideoDecodeH264CapabilitiesKHR.maxLevelIdc`。BASELINE 标识 Constrained Baseline；progressive 值为 0，不能当“无 profile”。[C1] | `VkVideoDecodeH264SessionParametersCreateInfoKHR` 预设 maxStdSPSCount/maxStdPPSCount。SPS key=seq_parameter_set_id；PPS key=(seq_parameter_set_id,pic_parameter_set_id)。update 只能添加合法新 key；已有 key 内容改变创建新 parameters（可按合法模板复制），不以递增 sequence 覆写。[C1] | `VkVideoDecodeH264PictureInfoKHR.pSliceOffsets` 是本次 src bitstream range 内 slice offsets；`VkVideoDecodeH264DpbSlotInfoKHR` 标识 frame/top/bottom field。一个 slot 可贡献两个 active field references，故 maxActiveReferencePictures 不等于 slot 数。interleaved 同区域双 field 合一条 reference slot + 两 flag；separate planes 不同区域各写一条。`is_reference` 控制 setup/失效；layout、field 标志或参考不匹配就拒绝 decode，转支持的 progressive 源/独立 codec，不静默丢 field。[C1] |
| `VK_KHR_video_decode_h265`：`VkVideoDecodeH265ProfileInfoKHR.stdProfileIdc`；`VkVideoDecodeH265CapabilitiesKHR.maxLevelIdc`。[C2] | `VkVideoDecodeH265SessionParametersCreateInfoKHR` 容量含 VPS/SPS/PPS。VPS key=vps id，SPS key=(vps,sps)，PPS key=(vps,sps,pps)；不能只按 PPS id 全局查找。更新仍是新增，不覆写现有 key。[C2] | `VkVideoDecodeH265PictureInfoKHR.pSliceSegmentOffsets` 不是 H264 slice 字段。`RefPicSetStCurrBefore/After/LtCurr` 元素映射实际 DPB slot 或 `STD_VIDEO_H265_NO_REFERENCE_PICTURE`；`VkVideoDecodeH265DpbSlotInfoKHR` 提供参考信息，`flags.IsReference` 决定 setup/失效。缺参数层级或参考链不合法就停止，重新建立参数与随机访问点；不能重用 H264 DPB pNext。[C2] |
| `VK_KHR_video_decode_av1`：`VkVideoDecodeAV1ProfileInfoKHR.stdProfile` + `filmGrainSupport`；`VkVideoDecodeAV1CapabilitiesKHR.maxLevel`。film grain 支持是 profile 的一部分，可能增加 session/image 内存。[C3] | `VkVideoDecodeAV1SessionParametersCreateInfoKHR` 仅一个 sequence header；不允许 `vkUpdateVideoSessionParametersKHR`，新 header 创建新对象，template 必须 NULL（09258）。maintenance2 合法 inline 例外另见下段。[C3] | `VkVideoDecodeAV1PictureInfoKHR` 提供 frameHeaderOffset、pTileOffsets/pTileSizes；七个 referenceNameSlotIndices 对应 LAST_FRAME 起的七个名称，不是八个存储槽直接照抄。`refresh_frame_flags` 控制 setup/失效，`VkVideoDecodeAV1DpbSlotInfoKHR` 附参考信息。启用 apply_grain 时输出与重建资源必须不同，**即使未报告 DPB_AND_OUTPUT_DISTINCT**；应用给出有效 film grain 参数，实现不替应用执行 load_grain_params。缺 filmGrainSupport/参数/独立资源时拒绝此路径，选择明确支持的 decoder，不把去掉 grain 当等价输出。[C3] |
| `VK_KHR_video_decode_vp9`：`VkVideoDecodeVP9ProfileInfoKHR.stdProfile`、`VkVideoDecodeVP9CapabilitiesKHR.maxLevel`，还需 videoDecodeVP9 feature。[C4] | VP9 没有 session parameter sets，不能创建 VP9 `VkVideoSessionParametersKHR`（10794）；begin 不绑定虚构参数对象。不编造 VkVideoDecodeVP9SessionParametersCreateInfoKHR。[C4] | `VkVideoDecodeVP9PictureInfoKHR` 传 uncompressedHeaderOffset/compressedHeaderOffset/tilesOffset 与三个 referenceNameSlotIndices（LAST/GOLDEN/ALTREF）。`refresh_frame_flags` 控制 setup/失效；没有 VkVideoDecodeVP9DpbSlotInfoKHR，也没有 StdVideoDecodeVP9ReferenceInfo，不应链伪造结构体。loop-filter delta 未在本帧语法提供时应用保留前值。feature/profile/参考不满足则拒绝并回退独立 VP9 decoder；冻结版本没有 VK_KHR_video_encode_vp9。[C4] |
| `VK_KHR_video_encode_h264`：`VkVideoEncodeH264ProfileInfoKHR.stdProfileIdc`；`VkVideoEncodeH264CapabilitiesKHR` 查 maxLevelIdc/maxSliceCount、QP、temporal layers、stdSyntaxFlags 和 P/B 支持。[C5] | `VkVideoEncodeH264SessionCreateInfoKHR` 可限制 level；parameters 对象存 SPS/PPS。通过 `VkVideoEncodeH264SessionParametersGetInfoKHR` 的 writeStdSPS/writeStdPPS（至少一项）调用 `vkGetEncodedVideoSessionParametersKHR`，读取实际编码参数及 hasStdSPSOverrides/hasStdPPSOverrides，不能盲用输入 SPS/PPS。[C5] | `VkVideoEncodeH264PictureInfoKHR.pNaluSliceEntries` 每 slice 提供参数；对应 `VkVideoEncodeH264DpbSlotInfoKHR` 的参考与 is_reference 控制重建。maxPPictureL0ReferenceCount=0 不允许 P；两个 B/L1 上限皆 0 不允许 B，但这些实现参考数上限不是直接裁剪应用列表长度的通用规则，允许规范覆盖。QP/layer/GOP 与 requiresGopRemainingFrames 按查询值，超范围拒绝或选择显式合法配置；取实际 feedback bytes 后才输出码流。[C5] |
| `VK_KHR_video_encode_h265`：`VkVideoEncodeH265ProfileInfoKHR.stdProfileIdc`；`VkVideoEncodeH265CapabilitiesKHR` 另查 maxSliceSegmentCount、maxTiles、ctbSizes、transformBlockSizes、maxSubLayerCount。[C6] | `VkVideoEncodeH265SessionCreateInfoKHR` 可限制 level；parameters 为 VPS/SPS/PPS，GetInfo 至少请求一类，输出顺序 VPS→SPS→PPS，读取各 hasStd*Overrides。不能把 H264 两级参数 key/feedback 直接照搬。[C6] | `VkVideoEncodeH265PictureInfoKHR.pNaluSliceSegmentEntries` 与 `VkVideoEncodeH265DpbSlotInfoKHR`；slice segment/tile/CTB 各有条件限制。P 支持为 0 不自动排除 low-delay B，需单独查 B/L1 能力；reference list override 边界与 H264 同样不能误作硬裁剪。缺 slice/tile/sub-layer 能力时拒绝所选配置，选择查询过的合法配置或平台 encoder；feedback/完成前不消费输出。[C6] |
| `VK_KHR_video_encode_av1`：`VkVideoEncodeAV1ProfileInfoKHR.stdProfile` + videoEncodeAV1 feature；`VkVideoEncodeAV1CapabilitiesKHR` 查 prediction-mode reference counts/name masks、tiles/superblockSizes、layers/operating points、minQIndex/maxQIndex。[C7] | `VkVideoEncodeAV1SessionParametersCreateInfoKHR` 保存单 sequence header，可含 decoder model 与 operating points；不允许 update（10281），film_grain_params_present 必须 0（10288）。`vkGetEncodedVideoSessionParametersKHR` 返回实现实际 sequence header OBU，不能把 decode 的 grain 能力移到 encode。[C7] | `VkVideoEncodeAV1PictureInfoKHR` 使用 predictionMode/rateControlGroup/constantQIndex（rate control disabled 时），不是 H264 QP；七名称映射、primaryReferenceCdfOnly 与 refresh_frame_flags 分别处理。codedPictureAlignment 描述实现可能扩大编码分辨率，**不是额外 valid-usage 对齐约束**；需要保真尺寸时检查输出/容器裁剪策略，不把 padding 当原图。模式/name mask/QIndex 不支持就拒绝或选择已支持配置；没有 encode feature 不能用 decode feature 代替。[C7] |

**统一失败路径补充。** parser/bitstream 验证、profile 查询、资源容量、codec-specific pNext 与参考有效性任一失败，均在录制前拒绝；已提交 operation 失败后停止依赖其 DPB 的后续帧，按 session reset + codec 随机访问点恢复。decode 的 query status 不是 encode feedback；encode 的 BYTE_COUNT/override 成功也不证明解码图像正确。队列状态查询需支持，header 导出返回值/实际长度必须检查，buffer 不足按合法重查询/扩容流程处理，不能用旧 header 配新图片。参数对象替换后仍保留旧对象至提交使用结束。软件或 MediaCodec 回退单独记录，不自动 PASS Vulkan 路径。[SPEC][ENGINE]

### 六个辅助稳定扩展：查询条件与尚未关闭的边界

本小节明确登记全部六项；已核对下列差异，但没有将扩展全部 L1/L2 标成完成。dependency 均从冻结 Registry 获取。

- `VK_KHR_video_maintenance1`（依赖 video_queue）：启用 videoMaintenance1 后 profile-independent buffers、decode-output/encode-input images 与 inline queries 可用；image 仍要通过对应 profile 的 format/type/tiling/usage 检查，不能把 profile-independent 扩大成任意 DPB/format 可用。inline query 需 session `VK_VIDEO_SESSION_CREATE_INLINE_QUERIES_BIT_KHR`，不与普通 begin/end query 规则混用。仍待全面审查 inline query 各操作 VU。[C8]
- `VK_KHR_video_maintenance2`（依赖 video_queue）：启用 videoMaintenance2 后可在 decode 无参数对象时执行 control；session `VK_VIDEO_SESSION_CREATE_INLINE_SESSION_PARAMETERS_BIT_KHR` 允许 H264/H265/AV1 decode 链对应 InlineSessionParametersInfo。存在 inline 的 active parameter 优先用 inline，其余来自合法绑定 parameters；缺任一必需 active set 不得 decode。该能力不使 AV1 parameters 对象变成可 update，也不为 VP9 创造参数集。还要求对应 H264/H265/AV1 encode profiles 支持 DISABLED rate control，并增加不可覆盖语法保证；这些保证须按具体 StdVideo 字段继续核对，不能声称全参数不可覆盖。[C8]
- `VK_KHR_video_encode_feedback2`（依赖 video_encode_queue）：启用 videoEncodeFeedback2 仍须查询 profile 的 supportedEncodeFeedbackFlags 与 `VkVideoEncodeFeedback2CapabilitiesKHR` 的 per-partition flags/上限。H264/H265 quantization 是 signed QP，AV1 是 unsigned QIndex；平均值 rounding 未定义。per-partition 数据在全部 primary query 结果（含 availability/status）之后，按 partition-major、bit-order 排列，最多写 query pool 的 maxPerPartitionFeedbackEntries。消费者按实际 flags/32或64位结果宽度计算 stride，不固定三个整数。feature 缺失就只用查询过的基础 feedback，不伪造统计；各 codec skipped-pixel/partition 定义仍待专项验证。[C9]
- `VK_KHR_video_encode_quantization_map`（依赖 video_encode_queue +（format_feature_flags2 或 Vulkan 1.3））：delta map 直接调整每块相对 quantization，emphasis map 由 rate control 间接控制；emphasis 不适用于 DISABLED 或 DEFAULT mode，不能视为固定 QP map。必须进一步查询具体 map feature、profile format/texel size、session 与 image flags/usage、H264/H265 QP 或 AV1 QIndex 解释，未满足时关闭 map 回到合法普通 encode。该完整资源合同仍 OPEN，不凭扩展枚举启用。[C10]
- `VK_KHR_video_encode_intra_refresh`（依赖 video_encode_queue）：videoEncodeIntraRefresh feature 不保证每个 profile 支持；session 的 intraRefreshMode 需来自 `VkVideoEncodeIntraRefreshCapabilitiesKHR.intraRefreshModes`。按支持模式/周期/参考关系设置，不能把 intra refresh 当无参考 keyframe 的等价替代；缺失时选择合法 IDR/keyframe 策略。region/cycle/dirty-reference 完整约束仍 OPEN。[C10]
- `VK_VALVE_video_encode_rgb_conversion`（依赖 video_encode_queue +（sampler_ycbcr_conversion 或 Vulkan 1.1））：videoEncodeRgbConversion 与 `VkVideoEncodeProfileRgbConversionInfoVALVE` 让 encoder 接受支持的 RGB/RGBA 输入，不代表任意 RGB format 或色彩空间可用。必须查询 conversion profile/格式/模型/范围与 session 条件；未满足时在受支持路径显式转换为匹配的 YCbCr 图片并同步。矩阵、range/chroma 与颜色正确性完整合同仍 OPEN。[C10]

**定向验收。** 静态负例至少包含 H264 双 field 不误计 slot、H265 key 冲突、AV1 sequence update/film-grain output alias、VP9 伪造参数或 DPB 结构体、AV1 encode feature 缺失与 QP/QIndex 混用、feedback2 signedness/布局错误。实际 codec PASS 另需合法码流、解码像素或 round-trip 对照、header/feedback 核对、session reset 与参考链恢复；本轮这些 Device 项均 NOT_RUN，不能用 source-read/字符串回归替代。

固定规范证据（全部 1.4.368）：[C1](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h264_decode.adoc#L173)；[C1 参数 key](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h264_parameter_sets.adoc#L7)；[C2](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h265_decode.adoc#L121)；[C2 参数 key](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h265_parameter_sets.adoc#L7)；[C3](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/av1_decode.adoc#L164)；[C4](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/vp9_decode.adoc#L142)；[C4 无 parameters](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/videocoding.adoc#L2066)；[C5](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h264_encode.adoc#L273)；[C6](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/h265_encode.adoc#L310)；[C7](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/av1_encode.adoc#L435)；[C7 update VU](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/videocoding.adoc#L3280)；[C8 profile compatibility / inline / parameter controls](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/videocoding.adoc#L1881)；[C8 features](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/features.adoc#L4622)；[C9](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc#L3238)；[C9 result layout](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc#L1273)；[C10 quantization/intra/RGB](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/video/encode.adoc#L2336)。

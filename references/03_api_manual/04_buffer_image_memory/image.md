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

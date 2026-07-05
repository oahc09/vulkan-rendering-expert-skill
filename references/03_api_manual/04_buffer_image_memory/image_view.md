# API Card: VkImageView

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | `VkImageView` |
| 常用 API | `vkCreateImageView` / `vkDestroyImageView` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkImageView` 是 `VkImage` 的“视图”，决定 shader 或 attachment 如何解释 image 的 format、mipmap 范围、array layer 范围；它是 image 被 descriptor 或 framebuffer 引用的实际对象。[SPEC]

---

## 2. 所属对象链路

```text
VkImage
→ VkImageView
→ VkFramebuffer / Dynamic Rendering Attachment
→ VkDescriptorSet (sampled / storage)
→ Shader Access / Render Pass
```

### 上游依赖

- `VkImage` 必须已创建并绑定 memory。[SPEC]
- Image 的 `usage` 必须包含 view 的用途（如 `SAMPLED`、`COLOR_ATTACHMENT`、`STORAGE`）。[SPEC]
- `format` 必须与 image format 兼容（少数 format 可 reinterpret，但有严格限制）。[SPEC]

### 下游影响

- Framebuffer attachment 使用 image view 而非 image。[SPEC]
- Descriptor 中 image / combined image sampler 绑定的是 image view。[SPEC]
- Dynamic rendering 的 attachment info 直接引用 image view。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImageView`
- `VkImageViewCreateInfo`
- `VkImageSubresourceRange`
- `VkComponentMapping`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateImageView` | 基于 image 创建 view。[SPEC] |
| `vkDestroyImageView` | 销毁 view；不影响底层 image。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_imageless_framebuffer`：framebuffer 不直接存储 image view，但 attachment 仍需 view。
- `VK_EXT_image_view_min_lod`：可限制 view 的最小 mipmap。

---

## 4. 标准使用流程

```text
创建 VkImage
→ 绑定 memory
→ 准备 VkImageViewCreateInfo
    → image
    → viewType (1D / 2D / 3D / CUBE / 1D_ARRAY / 2D_ARRAY / CUBE_ARRAY)
    → format
    → components (component mapping)
    → subresourceRange (aspectMask / baseMipLevel / levelCount / baseArrayLayer / layerCount)
→ vkCreateImageView
→ 用于 framebuffer attachment 或 descriptor update
→ 销毁时:
    等待 GPU idle
    → vkDestroyImageView
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `image` | 必须有效且已绑定 memory。[SPEC] | image 已销毁但 view 仍在 descriptor 中。[SPEC] |
| `viewType` | 决定 shader 中 texture 类型：`texture2D` / `textureCube` / `texture2DArray` 等。[SPEC] | shader 用 `samplerCube` 但 viewType 为 `2D`。[TOOL] |
| `format` | 通常与 image format 一致；部分格式可兼容 reinterpret。[SPEC] | 使用不兼容 format 导致创建失败或采样异常。[TOOL] |
| `components` | 默认 `VK_COMPONENT_SWIZZLE_IDENTITY`；可重排通道。[SPEC] | 移动端对部分 swizzle 支持不佳或增加开销。[VENDOR] |
| `subresourceRange.aspectMask` | color image 用 `COLOR`；depth/stencil 用 `DEPTH` / `STENCIL` / `DEPTH\|STENCIL`。[SPEC] | depth image view 未加 `DEPTH_BIT`。[TOOL] |
| `subresourceRange.baseMipLevel` / `levelCount` | 指定 mipmap 范围。[SPEC] | levelCount 设为 0 导致创建失败。[SPEC] |
| `subresourceRange.baseArrayLayer` / `layerCount` | 指定 array layer 范围。[SPEC] | array layer 范围与 shader 预期不一致。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `image` 是否有效？
- [ ] `viewType` 是否与 shader 中的 texture 类型匹配？
- [ ] `format` 是否与 image format 兼容？
- [ ] `subresourceRange` 是否覆盖实际需要访问的范围？
- [ ] `aspectMask` 是否与 image 类型匹配？

### 使用阶段

- [ ] Framebuffer attachment 的 image view 是否与 render pass 的 format 一致？
- [ ] Descriptor 中 image view 的 `imageLayout` 是否与实际使用 layout 一致？
- [ ] Swapchain recreate 后是否更新了引用旧 swapchain image 的 image view？

### 销毁阶段

- [ ] 是否等待 GPU 不再使用？
- [ ] 是否先销毁 framebuffer / descriptor 引用再销毁 image view？
- [ ] Image view 销毁不影响 image，但 image 销毁前必须确保没有 image view 引用。[SPEC]

---

## 7. 高频错误

1. `viewType` 与 shader texture 类型不匹配，如 cube map 用 2D view。[TOOL]
2. `aspectMask` 错误，如 depth image 只填 `COLOR_BIT`。[TOOL]
3. `subresourceRange.levelCount` 为 0 或 `VK_REMAINING_MIP_LEVELS` 使用不当。[SPEC]
4. Swapchain recreate 后 image view 仍指向旧 swapchain image。[ENGINE]
5. Image 已销毁但 descriptor 仍引用其 image view。[SPEC]
6. Framebuffer attachment format 与 pipeline 的 color attachment format 不一致。[TOOL]
7. `format` 与 image format 不兼容导致创建失败。[TOOL]
8. 多 frame-in-flight 下 image view 被不同帧复用但资源未隔离。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkImageViewCreateInfo-*`：image / format / viewType / subresourceRange 合法性。
- `VUID-VkWriteDescriptorSet-*`：descriptor image view 是否有效。
- `VUID-vkCmdDraw-*`：descriptor image layout 与实际 layout 是否匹配。

### RenderDoc / AGI

- 查看 bound descriptor 中的 image view。
- 查看 framebuffer attachment 的 image view 和内容。
- 查看 image view 的 format 和 subresource range。

### 日志 / 代码检查

- 检查 `vkCreateImageView` 返回值。
- 检查 swapchain recreate 后 image view 是否重建。
- 检查 descriptor update 时使用的 image view handle。

---

## 9. 生命周期风险

### 创建时机

- Image 创建并绑定 memory 后。
- Swapchain image view 在 swapchain 创建后创建。

### 使用时机

- Framebuffer / dynamic rendering attachment。
- Descriptor update。

### 销毁时机

- 在 image 销毁前销毁。
- Swapchain recreate 时随旧 swapchain image 一起销毁。

### in-flight 风险

- Image view 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]
- Swapchain recreate 时，旧 swapchain image view 必须等 in-flight command buffer 完成后再销毁。[ENGINE]

---

## 10. 同步风险

- Image view 本身不引入额外同步；同步由底层 image 的 barrier / semaphore 管理。
- 不同 image view 指向同一 image 的不同 subresource range 时，barrier 的 subresource range 必须精确覆盖访问区域。[SPEC]

---

## 11. Android 注意点

- Android 上 swapchain image view 在 rotation / resize 后必须重建。[ANDROID]
- 移动端应避免创建大量 image view，可考虑复用或延迟创建。[ENGINE]
- AGI 可查看每个 draw 的 attachment 和 sampled image view。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- `vkCreateImageView` 开销通常较低，但频繁创建 / 销毁仍有成本。[ENGINE]
- Swapchain recreate 时批量重建 image view 是主要 CPU 开销之一。[ENGINE]

### GPU 侧

- Image view 本身基本无 GPU 开销；component swizzle 可能引入少量开销。[VENDOR]
- 使用 `VK_IMAGE_VIEW_TYPE_2D_ARRAY` 或 cube map view 时，确保 shader 类型匹配以避免驱动 fallback。[HEUR]

### 移动端

- 移动端对 component mapping 支持可能有限，尽量使用 identity mapping。[VENDOR]
- 减少每帧 image view 切换，合并使用同一 view 的 draw call。[HEUR]

---

## 13. 专家经验

**经验**：
当遇到“image 有内容但 shader 采样异常”或“attachment 没有输出”时，优先检查 image view 的 `viewType`、`format`、`aspectMask`、`subresourceRange` 四个字段，而不是先去改 shader。

**适用条件**：
所有使用 image view 的场景，尤其是 depth attachment、array texture、cube map、swapchain recreate 后。

**不适用情况**：
直接通过 buffer 访问数据，不使用 image view 的场景。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `image.md`
- `buffer.md`
- `memory_allocation.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_update.md`
- `../06_pipeline/graphics_pipeline.md`
- `../02_surface_swapchain/swapchain_recreate.md`

---

## 15. 需要回查官方文档的情况

1. 目标 format 作为 image view format 的兼容性规则。
2. `viewType` 与 image `imageType` / `arrayLayers` 的合法组合。
3. Depth / stencil image 的 `aspectMask` 使用规则。
4. Component mapping 在目标设备上的支持情况。

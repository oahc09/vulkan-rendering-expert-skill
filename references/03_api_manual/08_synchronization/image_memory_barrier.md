# API Card: VkImageMemoryBarrier

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkImageMemoryBarrier` |
| 常用 API | `vkCmdPipelineBarrier`（imageMemoryBarrierCount / pImageMemoryBarriers） |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkImageMemoryBarrier` 是 `vkCmdPipelineBarrier` 中专用于 image 的 barrier，既同步 image 的 memory access，也同步 image layout 状态，是处理 texture 读写切换、attachment layout transition 和 queue family ownership transfer 的核心结构。[SPEC]

---

## 2. 所属对象链路

```text
Image 生产阶段（如 COLOR_ATTACHMENT_OUTPUT + COLOR_ATTACHMENT_WRITE）
→ vkCmdPipelineBarrier(pImageMemoryBarriers = [VkImageMemoryBarrier])
→ Image 消费阶段（如 FRAGMENT_SHADER + SHADER_READ）
→ 或 Queue Family A release → Queue Family B acquire
```

### 上游依赖

- 已创建并绑定内存的 `VkImage`。[SPEC]
- 对于 attachment，需要已知 render pass / dynamic rendering 的格式与 usage。[SPEC]
- 对于 sampled image，需要已知 descriptor / shader 中的 image layout 要求。[SPEC]

### 下游影响

- 决定 image 在下一阶段的 layout 和可读/可写性。[SPEC]
- 影响 render pass attachment 的 load/store 行为以及 tile-based GPU 的 resolve 开销。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImageMemoryBarrier`
- `VkImageSubresourceRange`
- `VkImageLayout`
- `VkPipelineStageFlags` / `VkAccessFlags`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier` | 通过 `imageMemoryBarrierCount` / `pImageMemoryBarriers` 提交 image barrier。[SPEC] |
| `vkCmdPipelineBarrier2`（Vulkan 1.3 / synchronization2） | 使用 `VkImageMemoryBarrier2` 提供更细粒度控制。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供 `VkImageMemoryBarrier2` 与扩展 layout / stage / access flag。[SPEC]
- `VK_KHR_maintenance2` / 1.1 引入 `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` 等专用 layout。[SPEC]

---

## 4. 标准使用流程

```text
确定 image 当前 layout 与目标 layout
→ 确定 producer stage/access 与 consumer stage/access
→ 构造 VkImageSubresourceRange（aspect / baseMip / levelCount / baseArray / layerCount）
→ 构造 VkImageMemoryBarrier（oldLayout / newLayout / src/dst stage access / subresourceRange）
→ 在 producer 命令后、consumer 命令前调用 vkCmdPipelineBarrier
→ 后续命令使用 newLayout
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `oldLayout` | 必须与 image 当前实际 layout 一致，或 `VK_IMAGE_LAYOUT_UNDEFINED` 表示丢弃当前内容。[SPEC] | 填写错误的 oldLayout，导致 validation error 或数据损坏。[TOOL] |
| `newLayout` | Consumer 期望的 layout；常见如 `SHADER_READ_ONLY_OPTIMAL`、`COLOR_ATTACHMENT_OPTIMAL`、`TRANSFER_DST_OPTIMAL`、`PRESENT_SRC_KHR`。[SPEC] | sampled image 使用 `COLOR_ATTACHMENT_OPTIMAL` 或 attachment 使用 `SHADER_READ_ONLY_OPTIMAL`。[TOOL] |
| `srcStageMask` / `dstStageMask` | 控制 layout transition 前后的执行依赖。[SPEC] | 使用 `ALL_COMMANDS_BIT` 导致性能损失；或 stage 与 access 不匹配。[HEUR] |
| `srcAccessMask` / `dstAccessMask` | 控制 memory availability / visibility；layout transition 本身通常需要 src access 包含对应写入。[SPEC] | srcAccess 为空导致旧 layout 数据未 flush。[TOOL] |
| `subresourceRange` | 精确指定 mip level / array layer / aspect mask。[SPEC] | `aspectMask` 遗漏 `DEPTH_BIT` 或 `STENCIL_BIT`；mip level 范围未覆盖实际使用区域。[TOOL] |
| `srcQueueFamilyIndex` / `dstQueueFamilyIndex` | 用于 queue family ownership transfer；未 transfer 时通常设为 `QUEUE_FAMILY_IGNORED`。[SPEC] | 需要 ownership transfer 时设为 `QUEUE_FAMILY_IGNORED`，导致跨 queue 数据竞争。[TOOL] |
| `image` | 必须是已创建且绑定内存的 image handle。[SPEC] | image 已销毁或尚未绑定内存。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `oldLayout` 是否与实际 layout 一致？
- [ ] `newLayout` 是否符合 consumer 的使用方式？
- [ ] `subresourceRange` 是否覆盖目标 mip/array/aspect？
- [ ] 是否需要 queue family ownership transfer？

### 使用阶段

- [ ] Barrier 是否放在 producer 命令之后、consumer 命令之前？
- [ ] `srcAccessMask` 是否包含 producer 的写入 access？
- [ ] `dstAccessMask` 是否包含 consumer 的读取/写入 access？
- [ ] 同一 image 在 barrier 后是否使用了 `newLayout`？

### 销毁阶段

- 该命令本身无独立销毁阶段；image 销毁需等待 GPU 完成。[SPEC]

---

## 7. 高频错误

1. `oldLayout` 与 image 实际 layout 不符，或错误地使用 `UNDEFINED` 丢弃了仍需保留的内容。[TOOL]
2. `newLayout` 与后续 consumer 需要的 layout 不一致，例如 present 前未转换到 `PRESENT_SRC_KHR`。[TOOL]
3. `subresourceRange.aspectMask` 对 depth/stencil image 只填 `COLOR_BIT`。[TOOL]
4. `srcAccessMask` 为空就执行 layout transition，导致 transition 前的数据未正确 flush。[TOOL]
5. 在 render pass 内部对 attachment 做 layout transition，应使用 subpass description / dependency 中的 layout 字段。[TOOL]
6. 跨 queue family transfer 只做了 release 没做 acquire，或 family index 填反。[TOOL]
7. 对 swapchain image 做 barrier 时未等待 acquire semaphore。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkImageMemoryBarrier-oldLayout-01208`：oldLayout 必须与当前 layout 匹配（或为 UNDEFINED / PREINITIALIZED）。
- `VUID-VkImageMemoryBarrier-srcQueueFamilyIndex-01213` / `dstQueueFamilyIndex-01214`：queue family transfer 规则。
- `VUID-VkImageMemoryBarrier-subresourceRange-01486`：aspect mask 与 image format 一致性。
- `VUID-vkCmdPipelineBarrier-srcStageMask-4098` 等：stage / access / layout 组合合法性。

### RenderDoc / AGI

- RenderDoc 可展示每次 image barrier 的 old/new layout、stage/access、subresource range。[TOOL]
- AGI 可观察 layout transition 是否造成 GPU 气泡或额外 bandwidth。[TOOL]

### 日志 / 代码检查

- 检查 barrier 前后 image layout 的使用是否一致。
- 检查 `subresourceRange` 的 mip/array/aspect 是否遗漏。
- 检查 swapchain image 的 acquire/present semaphore 与 barrier 顺序。

---

## 9. 生命周期风险

### 创建时机

- 在 command buffer 录制时构造并提交；image 本身需预先创建。[SPEC]

### 使用时机

- 任何需要改变 image layout 或同步 image 读写的地方：render target → sampled texture、copy source/target、present 前等。[SPEC]

### 销毁时机

- 随 command buffer 生命周期；image 销毁需 fence 保证。[SPEC]

### in-flight 风险

- Barrier 只保证同 queue 内录制顺序；image 本身被跨 queue 使用时需 ownership transfer 或 semaphore。[SPEC]
- Swapchain image 在 acquire semaphore signal 前不应被写入。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Image barrier 不涉及 CPU 同步；需要 CPU 等待时使用 fence / timeline semaphore。[SPEC]

### GPU-GPU 同步

- 同 queue 内由 `srcStageMask` / `dstStageMask` 建立执行依赖。[SPEC]
- 跨 queue 需先 semaphore 同步，必要时再做 ownership transfer。[SPEC]

### 资源访问同步

- Layout transition 本身即是一种 memory dependency，需正确设置 src/dst access。[SPEC]
- Depth/stencil image 的 aspect 需要单独考虑；某些 layout 仅对 depth 或 stencil 有效。[SPEC]
- Multi-plane image 的 aspect mask 需按 format 规范填写。[SPEC]

---

## 11. Android 注意点

- Android 上 swapchain image 的 `PRESENT_SRC_KHR` layout transition 必须在 submit 前完成，并与 acquire semaphore 配对。[ANDROID]
- Tile-based GPU 对 render pass 外 layout transition 敏感；尽量把 attachment 的 transition 放在 subpass dependency 中，避免额外的 store/resolve。[ENGINE][ANDROID]
- 横竖屏切换后 swapchain image 已变化，旧 image 的 layout 状态不再相关，应按新 swapchain 重新处理。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Image barrier 录制开销低，但每个 barrier 都意味着一次 GPU 状态变更点。[ENGINE]

### GPU 侧

- Layout transition 可能引发 decompress / resolve / cache flush；全屏 image 的 transition 代价高。[ENGINE]
- 避免在同一帧内对同一张 image 反复切换 layout；尽量合并使用阶段。[HEUR]

### 移动端

- Tile-based GPU 上，render pass 结束时的 layout transition 会触发 tile memory 的 store/resolve；使用 `BY_REGION_BIT` 和 subpass dependency 可减少开销。[ENGINE][ANDROID]
- 尽量减少每帧对 backbuffer / depth texture 的 layout transition 次数。[ENGINE]

---

## 13. 专家经验

**经验**：
把 image layout 当作“该 image 在接下来一段使用周期内的状态”来管理，而不是“每次使用都转一次”。例如 shadow map 在渲染深度后可直接转为 `SHADER_READ_ONLY_OPTIMAL` 供 lighting pass 采样，中间避免转回 `UNDEFINED` 或 `GENERAL`。对于 transient attachment，考虑使用 `VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL`（1.3 / synchronization2）减少不必要的 layout 种类。

**适用条件**：
频繁在 attachment 和 sampled image 之间切换的 texture；需要 queue family transfer 的资源；multi-planar 或 depth/stencil image。

**不适用情况**：
Buffer 同步（用 `VkBufferMemoryBarrier`）；同 render pass 内 attachment 同步（用 subpass dependency）；跨设备共享（用 external memory / semaphore）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `pipeline_barrier.md`
- `synchronization2.md`
- `event.md`
- `semaphore.md`
- `fence.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`
- `../06_pipeline/graphics_pipeline.md`

---

## 15. 需要回查官方文档的情况

1. 具体 format 支持的 image layout 列表及 layout 转换限制。
2. Depth/stencil image 的 aspect mask 与 `VK_IMAGE_LAYOUT_DEPTH_ATTACHMENT_STENCIL_READ_ONLY_OPTIMAL` 等专用 layout 的合法组合。
3. Queue family ownership transfer 中 release barrier 与 acquire barrier 的精确匹配规则。
4. Swapchain image 在 `vkAcquireNextImageKHR` 和 `vkQueuePresentKHR` 之间的 layout 要求。
5. Multi-planar format 的 aspect mask 与 plane 映射关系。
6. Vulkan 1.3 / synchronization2 中新增 layout（如 `ATTACHMENT_OPTIMAL`、`READ_ONLY_OPTIMAL`）的兼容性。

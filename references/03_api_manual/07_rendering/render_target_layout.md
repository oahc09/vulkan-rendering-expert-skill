# API Card: Render Target Image Layout

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 |
| Vulkan 对象 | `VkImage` layout 状态 |
| 常用 API | `vkCmdPipelineBarrier` / `vkCmdBeginRenderPass` / `vkCmdEndRenderPass` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

Render target 的 image layout 是 Vulkan 对 image 在特定 pipeline stage 中访问方式的显式约定，错误的 layout 会导致验证错误、缓存不一致或渲染结果异常。[SPEC]

---

## 2. 所属对象链路

```text
VkImage
→ Image Layout（COLOR_ATTACHMENT_OPTIMAL / DEPTH_STENCIL_ATTACHMENT_OPTIMAL / PRESENT_SRC_KHR / SHADER_READ_ONLY_OPTIMAL / TRANSFER_SRC_OPTIMAL ...）
→ VkImageView
→ Render Pass / Dynamic Rendering / Sample / Present / Transfer
```

### 上游依赖

- Image 创建时指定的 usage flags（`COLOR_ATTACHMENT` / `DEPTH_STENCIL_ATTACHMENT` / `TRANSFER_SRC` / `SAMPLED`）。[SPEC]
- 之前的 command 将该 image transition 到合法 layout。[SPEC]

### 下游影响

- 决定该 image 能否被 render pass attachment、shader sample、present engine 或 transfer 命令合法访问。[SPEC]
- 影响驱动是否需要插入 layout transition 与 cache flush/invalidate。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImageMemoryBarrier`
- `VkAttachmentDescription.initialLayout` / `.finalLayout`
- `VkRenderingAttachmentInfo.imageLayout`
- `VkImageLayout` enum

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier` | 通过 image memory barrier 显式 transition layout。[SPEC] |
| `vkCmdBeginRenderPass` | 根据 `initialLayout` 隐式 transition attachment。[SPEC] |
| `vkCmdEndRenderPass` | 根据 `finalLayout` 隐式 transition attachment。[SPEC] |
| `vkCmdBeginRendering` | 要求 attachment 已处于 `COLOR_ATTACHMENT_OPTIMAL` 或 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供扩展 layout 与 access flag。

---

## 4. 标准使用流程

```text
创建 image 并指定 usage
→ 根据首次用途 transition 到初始 layout
→ 作为 render target 时使用 COLOR_ATTACHMENT_OPTIMAL / DEPTH_STENCIL_ATTACHMENT_OPTIMAL
→ 作为 sampled texture 时使用 SHADER_READ_ONLY_OPTIMAL
→ 作为 present image 时使用 PRESENT_SRC_KHR
→ 作为 transfer 源/目标时使用 TRANSFER_SRC_OPTIMAL / TRANSFER_DST_OPTIMAL
→ 不再需要时 transition 到 GENERAL 或合适 layout
```

---

## 5. 关键字段

| 字段 / Layout | 专家关注点 | 常见错误 |
|---|---|---|
| `COLOR_ATTACHMENT_OPTIMAL` | color attachment 读写；fragment output / color blend。[SPEC] | 在 sample 阶段仍保持此 layout。[TOOL] |
| `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | depth/stencil attachment 读写。[SPEC] | 仅深度测试但 image 同时被 sample 时未用 read-only layout。[TOOL] |
| `DEPTH_STENCIL_READ_ONLY_OPTIMAL` | depth test只读且允许 shader sample。[SPEC] | 在需要写入 depth 时误用。[TOOL] |
| `SHADER_READ_ONLY_OPTIMAL` | shader sample / input attachment read。[SPEC] | 作为 render target 时未 transition 出去。[TOOL] |
| `PRESENT_SRC_KHR` | 提交给 present engine。[SPEC] | present 前未从 COLOR_ATTACHMENT_OPTIMAL transition 过来。[TOOL] |
| `TRANSFER_SRC_OPTIMAL` / `TRANSFER_DST_OPTIMAL` | copy/blit/resolve。[SPEC] | 与 render target layout 混淆。[TOOL] |
| `GENERAL` | 通用但通常性能较差；用于 storage image 或特殊场景。[SPEC] | 滥用 GENERAL 替代专用 layout。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Image usage 是否覆盖目标 layout 所需的操作？
- [ ] Render pass 的 `initialLayout`/`finalLayout` 是否与 pipeline barrier 中的 old/new layout 一致？

### 使用阶段

- [ ] Render target 在 draw 前是否处于 `COLOR_ATTACHMENT_OPTIMAL` / `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`？
- [ ] Present image 在 queue present 前是否处于 `PRESENT_SRC_KHR`？
- [ ] Sampled image 在 shader 读取前是否处于 `SHADER_READ_ONLY_OPTIMAL`？
- [ ] Image barrier 的 stage/access 是否与 layout 匹配？

### 销毁阶段

- [ ] 无独立 layout 对象；销毁 image 前确保无 in-flight 使用。

---

## 7. 高频错误

1. Render pass 的 `initialLayout` 与实际 image layout 不一致。[TOOL]
2. Present 前未 transition swapchain image 到 `PRESENT_SRC_KHR`。[TOOL]
3. Depth attachment 在被 shader sample 时仍保持 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`。[TOOL]
4. 在 render pass 内部手动对 attachment 做 layout transition，与 render pass 自动 transition 冲突。[TOOL]
5. Image barrier 的 `oldLayout` 填 `UNDEFINED` 导致内容丢失。[TOOL]
6. 对同一 image 的 subresource range 出现重叠但冲突的 layout 要求。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdDraw-*-imageLayout-*`：layout 与使用场景不匹配。
- `VUID-VkImageMemoryBarrier-oldLayout-01213` 等：layout transition 合法性。
- `VUID-vkQueuePresentKHR-pImageIndices-01296`：present 前 layout 检查。

### RenderDoc / AGI

- 查看 image 在 barrier 前后的 layout。
- 检查 render pass attachment 的 initial/final layout。
- 分析 layout transition 造成的 GPU 气泡。

### 日志 / 代码检查

- 检查所有 `VkImageMemoryBarrier` 的 oldLayout/newLayout。
- 检查 render pass 的 initialLayout/finalLayout 与代码逻辑是否一致。
- 检查 swapchain image 的 present 前 barrier。

---

## 9. 生命周期风险

### 创建时机

- Layout 不是独立对象，随 image 创建而初始为 `UNDEFINED` 或 `PREINITIALIZED`。[SPEC]

### 使用时机

- 每次使用该 image 前必须处于对应 layout；可在 command buffer 录制时通过 barrier 或 render pass begin 切换。[SPEC]

### 销毁时机

- 无独立销毁；image 销毁后 layout 状态自然消失。

### in-flight 风险

- Layout transition 本身只影响后续命令；但 transition 前后的内容可见性需要 barrier 保证。不能对 in-flight image 做未同步的 layout 修改。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Layout transition 通过 command buffer 提交执行，CPU 无需直接干预。[SPEC]

### GPU-GPU 同步

- 同一 image 在 producer 与 consumer 之间切换 layout 时，必须使用包含 execution 与 memory dependency 的 barrier。[SPEC]

### 资源访问同步

- Layout transition 通常与 stage/access mask 一起出现在 image memory barrier 中。[SPEC]
- `oldLayout` 到 `newLayout` 的 transition 隐含一次 memory dependency，但 src/dst stage/access 仍需正确填写。[SPEC]

---

## 11. Android 注意点

- Tile-based GPU 对 attachment layout 高度敏感；`COLOR_ATTACHMENT_OPTIMAL` 与 `SHADER_READ_ONLY_OPTIMAL` 之间的 transition 可能触发 tile resolve 与内存回写。[ANDROID][ENGINE]
- Swapchain image 在 present 前必须 transition 到 `PRESENT_SRC_KHR`；否则验证层报错或呈现异常。[ANDROID]
- 部分低端 Android 设备对 `GENERAL` layout 的优化较差，应避免在渲染路径中长期使用。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 每个 image barrier 都会增加 command buffer 大小，但通常开销很小。[ENGINE]

### GPU 侧

- 专用 layout 允许驱动做更激进的缓存优化；滥用 `GENERAL` 会降低性能。[ENGINE]
- 不必要的 layout transition 会造成 cache flush/invalidate 气泡。[ENGINE]

### 移动端

- 尽量在 render pass 内完成 attachment 的 layout transition（通过 initial/final layout），减少额外 barrier。[ANDROID]
- Deferred shading 的 G-buffer 从 attachment 转为 sampled image 时，是移动端常见瓶颈点，需精确规划 transition 与 dependency。[ENGINE]

---

## 13. 专家经验

**经验**：
把 layout 理解为“image 当前被谁以什么方式访问”。不要追求最小化 barrier 数量，而要让每个 barrier 的语义精确。常见模式是：swapchain image 在 acquire 后从 `UNDEFINED` 到 `COLOR_ATTACHMENT_OPTIMAL`，draw 后再到 `PRESENT_SRC_KHR`；G-buffer 在 render pass 中保持 attachment layout，pass 结束后 transition 到 `SHADER_READ_ONLY_OPTIMAL` 供 lighting pass sample。

**适用条件**：
所有涉及 image 作为 render target、texture、present、transfer 的项目。

**不适用情况**：
Linear buffer 或 buffer 资源不经过 image layout 机制。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `render_pass.md`
- `dynamic_rendering.md`
- `attachment_load_store.md`
- `../04_buffer_image_memory/framebuffer.md`
- `../04_buffer_image_memory/image_layout.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`
- `../08_synchronization/image_memory_barrier.md`
- `../08_synchronization/pipeline_barrier.md`
- `../02_surface_swapchain/swapchain.md`

---

## 15. 需要回查官方文档的情况

1. 具体 format 是否支持作为 color / depth / stencil attachment 及对应 layout。
2. `VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL` 等 synchronization2 扩展 layout 的语义。
3. 同一 image 不同 subresource range 同时处于不同 layout 的合法性。
4. Swapchain image 在 acquire/present 时的隐式 layout 假设。
5. 驱动对 `GENERAL` layout 与专用 layout 的性能差异。

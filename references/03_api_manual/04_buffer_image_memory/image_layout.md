# API Card: Image Layout

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | `VkImageLayout` |
| 常用 API | `vkCmdPipelineBarrier` / `vkCmdBeginRenderPass` / `vkCmdEndRenderPass` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

Image layout 是 Vulkan 对 image 在特定时间点、被特定 pipeline stage 访问方式的显式状态约定，layout 转换是资源同步与缓存一致性的核心环节。[SPEC]

---

## 2. 所属对象链路

```text
VkImage
→ VkImageLayout（UNDEFINED / GENERAL / COLOR_ATTACHMENT_OPTIMAL / DEPTH_STENCIL_ATTACHMENT_OPTIMAL / SHADER_READ_ONLY_OPTIMAL / TRANSFER_*_OPTIMAL / PRESENT_SRC_KHR ...）
→ Image Memory Barrier / Render Pass / Dynamic Rendering
→ ImageView / Sample / Render Target / Present / Transfer
```

### 上游依赖

- Image 已创建并绑定内存。[SPEC]
- Image usage 允许目标操作。[SPEC]

### 下游影响

- 决定 image 能否被特定命令合法访问。
- 决定驱动是否需要插入 layout transition 与 cache flush/invalidate。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImageLayout`
- `VkImageMemoryBarrier`
- `VkImageMemoryBarrier2`（synchronization2）

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier` | 通过 image memory barrier 转换 layout。[SPEC] |
| `vkCmdBeginRenderPass` | 根据 `initialLayout` 隐式转换 attachment。[SPEC] |
| `vkCmdEndRenderPass` | 根据 `finalLayout` 隐式转换 attachment。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供扩展 layout。

---

## 4. 标准使用流程

```text
创建 image（layout = UNDEFINED）
→ 根据首次用途 transition（如 TRANSFER_DST_OPTIMAL 用于 upload）
→ 使用时保持对应 layout（COLOR_ATTACHMENT / DEPTH_STENCIL / SHADER_READ_ONLY / PRESENT_SRC）
→ 在 producer 与 consumer 之间通过 barrier 转换 layout
→ 销毁 image
```

---

## 5. 关键字段

| Layout | 用途 | 常见错误 |
|---|---|---|
| `UNDEFINED` | 初始状态；可作为 oldLayout 丢弃旧内容。[SPEC] | 把 UNDEFINED 当目标 layout 读取。[TOOL] |
| `GENERAL` | 通用；storage image / transfer / 特殊场景。[SPEC] | 滥用导致性能下降。[TOOL] |
| `COLOR_ATTACHMENT_OPTIMAL` | color attachment 读写。[SPEC] | sample 时仍保持此 layout。[TOOL] |
| `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | depth/stencil 读写。[SPEC] | 需要 sample 时未转 read-only。[TOOL] |
| `DEPTH_STENCIL_READ_ONLY_OPTIMAL` | depth test 只读 + shader sample。[SPEC] | 需要写入 depth 时误用。[TOOL] |
| `SHADER_READ_ONLY_OPTIMAL` | shader sample / input attachment read。[SPEC] | 作为 render target 时未转走。[TOOL] |
| `TRANSFER_SRC_OPTIMAL` / `TRANSFER_DST_OPTIMAL` | copy/blit/resolve/clear。[SPEC] | 与 render target layout 混淆。[TOOL] |
| `PRESENT_SRC_KHR` | swapchain present。[SPEC] | present 前未转换。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Image usage 是否覆盖所有目标 layout 的操作？
- [ ] 是否规划了从 UNDEFINED 到最终 layout 的 transition 路径？

### 使用阶段

- [ ] 当前命令使用的 layout 是否与 image 实际 layout 一致？
- [ ] Layout transition 的 src/dst stage/access 是否匹配 producer/consumer？
- [ ] 是否避免在同一 image 的 overlapping range 上出现冲突 layout？

### 销毁阶段

- [ ] 无独立 layout 对象；销毁 image 前确保无 in-flight 使用。

---

## 7. 高频错误

1. Render pass 的 `initialLayout` 与实际 image layout 不一致。[TOOL]
2. Present 前未 transition swapchain image 到 `PRESENT_SRC_KHR`。[TOOL]
3. Depth attachment 在被 shader sample 时仍保持 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`。[TOOL]
4. Image barrier 的 `oldLayout` 填 `UNDEFINED` 导致内容丢失。[TOOL]
5. Storage image 未使用 `GENERAL` layout。[TOOL]
6. 对同一 image 的 subresource range 出现重叠但冲突的 layout 要求。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdDraw-*-imageLayout-*`：layout 与使用场景不匹配。
- `VUID-VkImageMemoryBarrier-oldLayout-01213` 等：transition 合法性。
- `VUID-vkQueuePresentKHR-pImageIndices-01296`：present 前 layout。

### RenderDoc / AGI

- 查看 image 在 barrier 前后的 layout。
- 检查 render pass attachment 的 initial/final layout。

### 日志 / 代码检查

- 检查所有 image barrier 的 oldLayout/newLayout。
- 检查 render pass 的 initialLayout/finalLayout。
- 检查 swapchain image 的 present 前 barrier。

---

## 9. 生命周期风险

### 创建时机

- Layout 随 image 创建初始为 `UNDEFINED` 或 `PREINITIALIZED`。[SPEC]

### 使用时机

- 每次使用 image 前必须处于对应 layout；通过 barrier 或 render pass begin/end 切换。[SPEC]

### 销毁时机

- 无独立销毁；image 销毁后 layout 状态自然消失。

### in-flight 风险

- 不能对 in-flight image 做未同步的 layout 修改；transition 只影响后续命令。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Layout transition 通过 command buffer 提交执行，CPU 无需直接干预。[SPEC]

### GPU-GPU 同步

- 同一 image 在 producer 与 consumer 之间切换 layout 时，必须使用包含 execution 与 memory dependency 的 barrier。[SPEC]

### 资源访问同步

- Layout transition 通常与 stage/access mask 一起出现在 image memory barrier 中。[SPEC]
- `oldLayout` 到 `newLayout` 的 transition 隐含 memory dependency，但 src/dst stage/access 仍需正确填写。[SPEC]

---

## 11. Android 注意点

- Tile-based GPU 对 layout transition 敏感；`COLOR_ATTACHMENT_OPTIMAL` 与 `SHADER_READ_ONLY_OPTIMAL` 之间的 transition 可能触发 tile resolve。[ANDROID][ENGINE]
- Swapchain image 在 present 前必须 transition 到 `PRESENT_SRC_KHR`。[ANDROID]
- 部分低端设备对 `GENERAL` layout 优化较差，避免在渲染路径中长期使用。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 每个 image barrier 增加 command buffer 大小，但通常开销很小。[ENGINE]

### GPU 侧

- 专用 layout 允许驱动做更激进的缓存优化；滥用 `GENERAL` 会降低性能。[ENGINE]
- 不必要的 layout transition 会造成 cache flush/invalidate 气泡。[ENGINE]

### 移动端

- 尽量在 render pass 内完成 attachment 的 layout transition，减少额外 barrier。[ANDROID]
- Deferred shading 的 G-buffer 从 attachment 转为 sampled image 是常见瓶颈点。[ENGINE]

---

## 13. 专家经验

**经验**：
把 layout 当作 image 的“访问权限标签”。每个使用 image 的命令前都要问自己：这个 image 现在是什么 layout？这次操作需要什么 layout？中间是否需要 barrier？不要让 `GENERAL` 成为默认值，专用 layout 对 GPU 性能至关重要。对 swapchain image，养成“acquire 后 transition 到 COLOR_ATTACHMENT，present 前 transition 到 PRESENT_SRC”的固定模式。

**适用条件**：
所有使用 image 作为 render target、texture、present、transfer 的项目。

**不适用情况**：
Buffer 资源不经过 image layout 机制。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `image.md`
- `image_view.md`
- `sampler.md`
- `framebuffer.md`
- `../07_rendering/render_target_layout.md`
- `../08_synchronization/image_memory_barrier.md`
- `../08_synchronization/pipeline_barrier.md`
- `../02_surface_swapchain/swapchain.md`

---

## 15. 需要回查官方文档的情况

1. 具体 format 与 usage 支持的 layout 集合。
2. `VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL` 等 synchronization2 扩展 layout 语义。
3. 同一 image 不同 subresource range 同时处于不同 layout 的合法性。
4. Swapchain image 在 acquire/present 时的隐式 layout 假设。
5. 驱动对 `GENERAL` layout 与专用 layout 的性能差异。

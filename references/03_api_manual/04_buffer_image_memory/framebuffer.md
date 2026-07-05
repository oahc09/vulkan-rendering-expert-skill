# API Card: VkFramebuffer

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 / 资源链 |
| Vulkan 对象 | `VkFramebuffer` |
| 常用 API | `vkCreateFramebuffer` / `vkDestroyFramebuffer` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkFramebuffer` 是将一组 `VkImageView` 绑定到特定 `VkRenderPass` 的容器，描述一次 render pass instance 实际使用的 attachment 集合。[SPEC]

---

## 2. 所属对象链路

```text
VkRenderPass
→ VkImageView[]（color / depth / resolve）
→ vkCreateFramebuffer（VkFramebufferCreateInfo）
→ VkFramebuffer
→ vkCmdBeginRenderPass（VkRenderPassBeginInfo）
→ Draw Calls
→ vkCmdEndRenderPass
```

### 上游依赖

- 已创建的 `VkRenderPass`。[SPEC]
- 已创建的 `VkImageView`，其 format、sample count 与 render pass attachment 描述兼容。[SPEC]

### 下游影响

- 决定 render pass instance 实际写入哪些 image view。
- 尺寸与 layer 数量决定渲染范围。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkFramebuffer`
- `VkFramebufferCreateInfo`
- `VkRenderPassBeginInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateFramebuffer` | 创建 framebuffer。[SPEC] |
| `vkDestroyFramebuffer` | 销毁 framebuffer。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_imageless_framebuffer` 允许不预先指定 image view，在 begin render pass 时动态提供。
- `VK_KHR_dynamic_rendering` 允许完全不需要 framebuffer。

---

## 4. 标准使用流程

```text
创建 VkRenderPass
→ 为每个需要的 attachment 创建 VkImageView
→ 构造 VkFramebufferCreateInfo（renderPass / attachmentCount / pAttachments / width / height / layers）
→ vkCreateFramebuffer
→ vkCmdBeginRenderPass 时传入 framebuffer
→ 绘制
→ vkCmdEndRenderPass
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `renderPass` | framebuffer 必须与其 render pass 兼容。[SPEC] | 用错误的 render pass 创建 framebuffer。[TOOL] |
| `attachmentCount` / `pAttachments` | 数量与顺序必须与 render pass 的 attachment 描述一致。[SPEC] | 顺序或数量不匹配。[TOOL] |
| `width` / `height` | render area 不能超过 framebuffer 尺寸。[SPEC] | render area 大于 framebuffer 尺寸。[TOOL] |
| `layers` | framebuffer 的 layer 数量；用于 multiview / layered rendering。[SPEC] | 多层渲染时填 1。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `pAttachments` 的顺序是否与 render pass attachment 描述一致？
- [ ] 每个 image view 的 format、sample count 是否与 render pass 兼容？
- [ ] `width`/`height`/`layers` 是否满足渲染需求？

### 使用阶段

- [ ] `vkCmdBeginRenderPass` 传入的 framebuffer 是否与 render pass 兼容？
- [ ] `renderArea` 是否在 framebuffer 范围内？
- [ ] Clear value 数量是否与 attachment 数量匹配？

### 销毁阶段

- [ ] 是否等待 GPU 不再使用该 framebuffer？
- [ ] 销毁 framebuffer 不影响其引用的 image view，但需确保 image view 生命周期独立管理。[SPEC]

---

## 7. 高频错误

1. `pAttachments` 顺序与 render pass 不一致。[TOOL]
2. Image view format 与 render pass attachment format 不兼容。[TOOL]
3. Image view sample count 与 render pass 不一致。[TOOL]
4. `renderArea` 超出 framebuffer 尺寸。[TOOL]
5. 销毁 framebuffer 时仍被 in-flight command buffer 引用。[TOOL]
6. 为每个 swapchain image 分别创建 framebuffer 但 render pass 不兼容。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkFramebufferCreateInfo-*`：attachment 数量、顺序、兼容性。
- `VUID-vkCmdBeginRenderPass-renderPass-00904`：framebuffer 与 render pass 兼容。

### RenderDoc / AGI

- 查看 framebuffer 的 attachment 内容、尺寸、format。
- 检查 render pass 与 framebuffer 的匹配。

### 日志 / 代码检查

- 检查 framebuffer 创建参数与 render pass 的对应关系。
- 检查 resize 时 framebuffer 是否重建。
- 检查 attachment image view 生命周期。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段或 swapchain recreate 时创建；每个 render pass / attachment 组合通常对应一个 framebuffer。[ENGINE]

### 使用时机

- 在 `vkCmdBeginRenderPass` 时传入。[SPEC]

### 销毁时机

- 确认 GPU 不再执行引用该 framebuffer 的 command buffer 后销毁。[SPEC]

### in-flight 风险

- Framebuffer 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]
- Swapchain recreate 时旧 framebuffer 可能仍被 in-flight frame 使用，需延迟销毁或按 per-swapchain 管理。

---

## 10. 同步风险

### CPU-GPU 同步

- 销毁 framebuffer 前需等待 GPU 完成相关 render pass。[SPEC]

### GPU-GPU 同步

- 无；framebuffer 本身不提供同步，同步由 render pass dependency 或 barrier 处理。

### 资源访问同步

- Framebuffer 引用的 attachment image view 的 layout 与 access 由 render pass begin/end 或 barrier 管理。[SPEC]

---

## 11. Android 注意点

- 移动端 swapchain recreate 频繁（横竖屏、分屏），framebuffer 需要与 swapchain image 一起重建。[ANDROID]
- 尽量减少 framebuffer 数量；对固定 offscreen attachment 可复用 framebuffer。[ENGINE]
- `VK_KHR_imageless_framebuffer` 可减少 swapchain 相关 framebuffer 对象数量，但需确认设备支持。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Framebuffer 创建开销通常不大，但 swapchain recreate 时批量重建会消耗 CPU。[ENGINE]
- 使用 imageless framebuffer 可减少对象数量。[GUIDE]

### GPU 侧

- Framebuffer 本身不直接产生 GPU 开销。[ENGINE]

### 移动端

- 避免为每个微小状态差异创建 framebuffer；按 render pass + attachment 组合复用。[ENGINE]
- Swapchain image 对应的 framebuffer 通常在 recreate 时统一重建。[ANDROID]

---

## 13. 专家经验

**经验**：
Framebuffer 只是 render pass 与 image view 之间的“适配器”，不要把复杂的渲染状态也放到 framebuffer 层级管理。对 swapchain，通常为每个 swapchain image 创建一个 framebuffer（共享同一个 render pass）；对 offscreen render target，按 attachment 组合复用。如果目标设备支持 imageless framebuffer 或 dynamic rendering，可以进一步减少 framebuffer 对象数量。

**适用条件**：
使用传统 render pass 的渲染。

**不适用情况**：
使用 `VK_KHR_dynamic_rendering` 时不需要 framebuffer。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `../07_rendering/render_pass.md`
- `image_view.md`
- `image_layout.md`
- `../07_rendering/render_target_layout.md`
- `../07_rendering/attachment_load_store.md`
- `../02_surface_swapchain/swapchain.md`
- `../02_surface_swapchain/swapchain_recreate.md`

---

## 15. 需要回查官方文档的情况

1. Framebuffer 与 render pass 的兼容性规则（format、sample、attachment 数量）。
2. `VK_KHR_imageless_framebuffer` 的使用条件与限制。
3. Layered framebuffer 与 multiview 的交互。
4. Swapchain image view 作为 framebuffer attachment 的特殊要求。
5. 不同驱动对 framebuffer 对象数量与创建性能的影响。

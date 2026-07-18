# API Card: VK_KHR_dynamic_rendering

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 |
| Vulkan 对象 | `VkRenderingInfo` / `VkPipelineRenderingCreateInfo` |
| 常用 API | `vkCmdBeginRendering` / `vkCmdEndRendering` |
| 适用平台 | 通用（需设备支持） |
| 来源等级 | `[SPEC] [GUIDE] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.3 core / `VK_KHR_dynamic_rendering` |

---

## 1. 一句话定位

`VK_KHR_dynamic_rendering` 允许在不创建 `VkRenderPass` 和 `VkFramebuffer` 的情况下，通过 command buffer 中的 `VkRenderingInfo` 直接描述 rendering attachment，从而降低渲染通道对象的管理复杂度。[SPEC]

---

## 2. 所属对象链路

```text
VkImageView（color / depth / resolve）
→ VkRenderingInfo（attachment 描述 + rendering area）
→ vkCmdBeginRendering
→ Draw Calls
→ vkCmdEndRendering
```

### 上游依赖

- 已创建并 transition 到合适 layout 的 image view。[SPEC]
- Graphics pipeline 通过 `VkPipelineRenderingCreateInfo` 提供 color/depth format 与 view mask。[SPEC]
- 启用 dynamic rendering feature 或 `VK_KHR_dynamic_rendering` 扩展。[SPEC]

### 下游影响

- 直接替代 `vkCmdBeginRenderPass` + `VkFramebuffer` 的组合。
- 与 graphics pipeline 的 rendering format 信息必须匹配。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkRenderingInfo`
- `VkRenderingAttachmentInfo`
- `VkPipelineRenderingCreateInfo`
- `VkPhysicalDeviceDynamicRenderingFeatures`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdBeginRendering` | 在 command buffer 中开始 dynamic rendering instance。[SPEC] |
| `vkCmdEndRendering` | 结束 dynamic rendering instance。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.3 core。
- `VK_KHR_dynamic_rendering` 扩展。
- `VK_KHR_dynamic_rendering_local_read` 等扩展可进一步扩展 local attachment 读取能力。

---

## 4. 标准使用流程

```text
检查 dynamicRendering feature 是否启用
→ 创建 graphics pipeline 时通过 pNext 提供 VkPipelineRenderingCreateInfo（color/depth format / view mask）
→ 每帧构造 VkRenderingInfo，包含 color/depth attachment 的 VkRenderingAttachmentInfo
→ 确保 attachment image layout 合法
→ vkCmdBeginRendering
→ 绑定 pipeline、descriptor、vertex buffer
→ vkCmdDraw / vkCmdDrawIndexed
→ vkCmdEndRendering
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `colorAttachmentCount` / `pColorAttachments` | 与 pipeline 创建时的 `colorAttachmentCount` 一致。[SPEC] | 数量或 format 与 pipeline 不匹配。[TOOL] |
| `pDepthAttachment` / `pStencilAttachment` | depth/stencil image view 与 format；可分别指定或共用。[SPEC] | 只提供 depth 而 pipeline 期望 depth+stencil。[TOOL] |
| `imageView` / `imageLayout` | attachment 必须处于 `COLOR_ATTACHMENT_OPTIMAL` 或 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`。[SPEC] | layout 未 transition 或 transition 遗漏。[TOOL] |
| `loadOp` / `storeOp` / `clearValue` | 同 render pass 的 attachment load/store op。[SPEC] | CLEAR 时未填 clear value。[TOOL] |
| `resolveMode` / `resolveImageView` | MSAA resolve 配置。[SPEC] | resolve image 的 sample count 或 format 不兼容。[TOOL] |
| `renderArea` | 影响 load/store 范围，移动端尤为重要。[SPEC] | 设置过大导致不必要带宽。[TOOL] |
| `layerCount` / `viewMask` | multiview 相关。[SPEC] | 与 pipeline view mask 不一致。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否启用 `dynamicRendering` feature？
- [ ] Pipeline 创建时是否提供 `VkPipelineRenderingCreateInfo`？
- [ ] Pipeline 的 color/depth format 与运行时 attachment format 是否一致？

### 使用阶段

- [ ] Attachment image view 是否已 transition 到对应 layout？
- [ ] `colorAttachmentCount` 与 pipeline 一致？
- [ ] `loadOp`/`storeOp` 是否符合预期？
- [ ] 是否在 `vkCmdBeginRendering` 后、draw 前正确绑定 graphics pipeline？

### 销毁阶段

- [ ] Dynamic rendering 本身无独立对象销毁；只需保证 image view 生命周期覆盖录制与执行。[SPEC]

---

## 7. 高频错误

1. 未启用 `dynamicRendering` feature 就调用 `vkCmdBeginRendering`。[TOOL]
2. Pipeline 未提供 `VkPipelineRenderingCreateInfo`，导致 format 不匹配。[TOOL]
3. Attachment image layout 仍是 `SHADER_READ_ONLY_OPTIMAL` 等非法状态。[TOOL]
4. `colorAttachmentCount` 与 pipeline 创建时不一致。[TOOL]
5. 忘记 `vkCmdEndRendering` 或在不合适的 command buffer 状态结束。[TOOL]
6. Depth/stencil format 与 `pDepthAttachment`/`pStencilAttachment` 描述不一致。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdBeginRendering-*`：feature、attachment、layout 合法性。
- `VUID-VkPipelineRenderingCreateInfo-*`：pipeline 创建时 format 与 view mask 规则。

### RenderDoc / AGI

- 查看 dynamic rendering 的 attachment、load/store op、render area。
- 检查 pipeline 的 rendering format 是否与运行时匹配。

### 日志 / 代码检查

- 检查 feature 启用代码。
- 检查 pipeline 创建 info 的 pNext 链。
- 检查 attachment image layout transition 路径。

---

## 9. 生命周期风险

### 创建时机

- 无需创建 `VkRenderPass` / `VkFramebuffer`，但 pipeline 创建时需提供 rendering format 信息。[SPEC]

### 使用时机

- 在 command buffer 录制阶段动态构造 `VkRenderingInfo` 并调用 begin/end。[SPEC]

### 销毁时机

- 无独立对象销毁；依赖的 image view 仍需按生命周期管理。[SPEC]

### in-flight 风险

- 录制的 `VkRenderingInfo` 结构体只需在 `vkCmdBeginRendering` 调用期间有效；但引用的 image view 必须保持有效直到 command buffer 完成。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 同 render pass；dynamic rendering 本身不涉及 CPU 同步。[SPEC]

### GPU-GPU 同步

- Dynamic rendering 与外部命令的同步需使用 pipeline barrier 或 event，因为没有 render pass subpass dependency。[SPEC]

### 资源访问同步

- Attachment layout transition 需手动完成，或在 `vkCmdBeginRendering`/`vkCmdEndRendering` 前后插入 image barrier。[SPEC]
- Resolve 操作由 `vkCmdEndRendering` 触发，需保证 resolve target 已准备好接收写入。[SPEC]

---

## 11. Android 注意点

- Dynamic rendering 在 Android 上可减少 `VkRenderPass`/`VkFramebuffer` 对象数量，但需确认设备支持 Vulkan 1.3 或该扩展。[ANDROID]
- Tile-based GPU 仍受 load/store op 与 render area 影响；不要误以为 dynamic rendering 消除了这些约束。[ANDROID][ENGINE]
- 部分旧 Mali/Adreno 驱动对 dynamic rendering 的优化可能不如传统 render pass，建议通过 AGI 验证实际开销。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 减少 render pass / framebuffer 对象的创建与缓存管理，降低初始化复杂度。[ENGINE]
- 每帧构造 `VkRenderingInfo` 的开销通常很小，但仍可复用静态结构体。[HEUR]

### GPU 侧

- 与传统 render pass 在 GPU 侧行为类似；load/store op 仍是主要带宽杠杆。[ENGINE]
- 没有 subpass dependency，跨 pass 同步需要显式 barrier，设计不当容易引入气泡。[HEUR]

### 移动端

- 对只需单 pass 或简单后处理链的场景，dynamic rendering 能减少对象开销；复杂多 subpass 场景仍需评估是否 traditional render pass 更优。[ENGINE]
- 尽量合并 dynamic rendering 调用，减少 begin/end 切换。[HEUR]

---

## 13. 专家经验

**经验**：
Dynamic rendering 适合“attachment 组合多变、render pass 对象爆炸”的场景，例如每帧根据后处理链动态选择 color/depth target。它并不能替代 render pass 的同步与带宽语义，只是把这部分描述从对象创建移到 command buffer 录制。对移动端 tile-based GPU，仍需像对待 render pass 一样关注 load/store op 和 render area。

**适用条件**：
后处理链灵活、VR/多视图渲染、希望减少 render pass/framebuffer 对象数量的项目。

**不适用情况**：
需要大量 subpass 内部 input attachment 读取且驱动对传统 render pass 优化更好的场景；或目标设备不支持该扩展。

**来源**：`[ENGINE][GUIDE][SPEC]`

---

## 14. 相关 API 卡片

- `render_pass.md`
- `attachment_load_store.md`
- `render_target_layout.md`
- `../04_buffer_image_memory/framebuffer.md`
- `../06_pipeline/graphics_pipeline.md`
- `../04_buffer_image_memory/image_view.md`
- `../08_synchronization/pipeline_barrier.md`
- `../08_synchronization/image_memory_barrier.md`

---

## 14.5 Vulkan 1.4 变更

Vulkan 1.4 对 Dynamic Rendering 的主要变更：

### Dynamic Rendering Local Read promote 为 mandatory feature

Vulkan 1.4 将 `VK_KHR_dynamic_rendering_local_read` 的 API promote 进 core，并提升为 mandatory feature（保证被支持）。[SPEC]

- 1.4 设备保证支持 local read，无需运行时查询 feature 即可确认能力存在；但 **仍需在 `VkDeviceCreateInfo.pNext` 中通过 `VkPhysicalDeviceVulkan14Features.dynamicRenderingLocalRead = VK_TRUE` 显式启用** 后才能调用相关 API。[SPEC]
- 仅基础 color attachment local read 在所有 1.4 设备上保证可用；**depth/stencil aspect 与 MSAA attachment 的 local read 受独立 properties 限制** —— 两个能力字段位于 `VkPhysicalDeviceVulkan14Properties`：`dynamicRenderingLocalReadDepthStencilAttachments` 与 `dynamicRenderingLocalReadMultisampledAttachments`，需运行时查询。[SPEC]
- 允许在 dynamic rendering pass 内读取同 pass 的 attachment 作为 input attachment，无需创建 `VkFramebuffer` 或显式 `VkRenderPass`。[SPEC]
- shader 仍使用 `subpassInput` / `subpassLoad` 机制（非普通 texture read），并通过 `VkRenderingInputAttachmentIndexInfo` 建立 input attachment index 映射。[SPEC]

### 新增 API

| API / 结构体 | 说明 | 来源 |
|---|---|---|
| `VkRenderingAttachmentLocationInfo` | 控制 attachment 在 fragment shader 中的 location 映射 | [SPEC] |
| `VkRenderingInputAttachmentIndexInfo` | 为 input attachment 提供 index 映射 | [SPEC] |

### Local Read 使用流程

```text
Step 1: device 创建时启用 dynamicRenderingLocalRead feature
  -> VkPhysicalDeviceVulkan14Features.dynamicRenderingLocalRead = VK_TRUE
  -> 通过 pNext 加入 VkDeviceCreateInfo

Step 2: pipeline 创建
  -> VkPipelineRenderingCreateInfo 中声明 input attachment 的 format

Step 3: 录制 dynamic rendering pass
  -> vkCmdBeginRendering
  -> vkCmdSetRenderingAttachmentLocations / vkCmdSetRenderingInputAttachmentIndices（按需）
  -> fragment shader 通过 subpassInput + subpassLoad 读取同 pass attachment
  -> vkCmdEndRendering

Step 4: 同步
  -> attachment image 必须处于 VK_IMAGE_LAYOUT_RENDERING_LOCAL_READ_KHR
  -> 通过 by-region pipeline barrier（vkCmdPipelineBarrier2 + VkDependencyInfo）
     在 input-reading draw 与 writing draw 之间建立可见性
  -> depth/stencil 与 MSAA local read 需先查询 properties 确认可用
```

无需在 pipeline 创建时指定 render pass，`VkPipelineRenderingCreateInfo` 即可。[SPEC]

### 与 Vulkan 1.3 的兼容性

- 1.3 设备仍需查询并启用 `VK_KHR_dynamic_rendering` feature；如需 local read，还需查询并启用 `VK_KHR_dynamic_rendering_local_read` 扩展。[SPEC]
- 1.4 设备保证 dynamic rendering 与基础 local read 可用，但 **mandatory feature 仍需通过 `VkPhysicalDeviceVulkan14Features` 显式启用**；depth/stencil / MSAA local read 仍受 properties 限制。[SPEC]
- 旧代码无需修改即可在 1.4 上运行。[GUIDE]

---

## 15. 需要回查官方文档的情况

1. Dynamic rendering 与 multiview / fragment shading rate 的交互。
2. `VkPipelineRenderingCreateInfo` 中 `viewMask` 与 `VkRenderingInfo` 的匹配规则。
3. Secondary command buffer 中使用 dynamic rendering 的限制。
4. Local read 扩展（`VK_KHR_dynamic_rendering_local_read`）的引入条件。
5. 不同驱动对 dynamic rendering 的 tile memory 优化差异。

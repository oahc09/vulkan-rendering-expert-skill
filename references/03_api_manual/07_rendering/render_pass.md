# API Card: VkRenderPass

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 |
| Vulkan 对象 | `VkRenderPass` |
| 常用 API | `vkCreateRenderPass` / `vkDestroyRenderPass` / `vkCmdBeginRenderPass` / `vkCmdEndRenderPass` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkRenderPass` 是描述一次渲染操作中 attachment、subpass 以及 subpass 之间依赖关系的容器，决定了 framebuffer 中各 attachment 如何被加载、存储、解析以及同步。[SPEC]

---

## 2. 所属对象链路

```text
VkAttachmentDescription[]
→ VkSubpassDescription[]
→ VkSubpassDependency[]
→ vkCreateRenderPass
→ VkRenderPass
→ vkCmdBeginRenderPass(VkRenderPassBeginInfo + VkFramebuffer)
→ Draw Calls
→ vkCmdEndRenderPass
```

### 上游依赖

- Attachment 数量、format、sample count、load/store op。[SPEC]
- Subpass 对 attachment 的引用关系（color / depth / input / resolve）。[SPEC]
- Subpass dependency 定义的执行依赖与 memory dependency。[SPEC]

### 下游影响

- 决定 graphics pipeline 创建时使用的 `renderPass` 与 `subpass`。[SPEC]
- 决定 framebuffer 创建时的 attachment 数量与格式兼容性。[SPEC]
- 决定 render pass begin 时的 clear value 与 render area。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkRenderPass`
- `VkRenderPassCreateInfo`
- `VkAttachmentDescription`
- `VkAttachmentReference`
- `VkSubpassDescription`
- `VkSubpassDependency`
- `VkRenderPassBeginInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateRenderPass` | 根据 attachment/subpass/dependency 创建 render pass。[SPEC] |
| `vkDestroyRenderPass` | 销毁 render pass；需确保 GPU 不再使用。[SPEC] |
| `vkCmdBeginRenderPass` | 在 command buffer 中开始一个 render pass instance。[SPEC] |
| `vkCmdEndRenderPass` | 结束 render pass instance，触发 store op 与解析。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_dynamic_rendering` / Vulkan 1.3 提供无需 `VkRenderPass` 的替代路径。
- `VK_KHR_multiview` / `VK_EXT_fragment_density_map` 等扩展会修改 subpass 描述。

---

## 4. 标准使用流程

```text
定义 attachment 数组（format / sample / loadOp / storeOp / stencilOp / initialLayout / finalLayout）
→ 定义每个 subpass 的 attachment reference（input / color / depthStencil / resolve）
→ 定义 subpass dependency（srcSubpass / dstSubpass / stage / access）
→ vkCreateRenderPass
→ 创建兼容的 VkFramebuffer
→ vkCmdBeginRenderPass（指定 renderPass + framebuffer + clear values）
→ 录制 draw calls
→ vkCmdEndRenderPass
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `attachmentCount` / `pAttachments` | 顺序决定 framebuffer 中 `pAttachments` 的索引。[SPEC] | 索引与 framebuffer attachment 不一致。[TOOL] |
| `loadOp` / `storeOp` | 决定 tile 开始时是否清空、结束时是否写回 memory；对移动端带宽影响大。[ENGINE] | 该清空时用了 `LOAD`，该保留时用了 `DONT_CARE`。[TOOL] |
| `initialLayout` / `finalLayout` | render pass 开始/结束时的预期 layout，驱动据此插入 layout transition。[SPEC] | 与 pipeline barrier 中目标 layout 冲突。[TOOL] |
| `pSubpasses` | 每个 subpass 的 color/depth/input/resolve 引用。[SPEC] | attachment reference 填 `VK_ATTACHMENT_UNUSED` 时仍影响索引。[TOOL] |
| `pDependencies` | srcSubpass/dstSubpass、srcStageMask/dstStageMask、srcAccessMask/dstAccessMask。[SPEC] | 缺少 dependency 导致 read-before-write 或 layout transition 未同步。[TOOL] |
| `dependencyFlags` | `VK_DEPENDENCY_BY_REGION_BIT` 用于 attachment 的局部依赖。[SPEC] | 在全局资源同步上误用 `BY_REGION_BIT`。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Attachment format/sample 与 image view / framebuffer 兼容？
- [ ] `loadOp`/`storeOp` 与每帧是否需要保留历史 attachment 内容一致？
- [ ] Subpass dependency 是否覆盖所有跨 subpass 的 attachment 读写？
- [ ] Render pass 创建时使用的 format 与 pipeline 创建时一致？
- [ ] 是否启用了必要的 multiview / fragment shading rate 扩展？

### 使用阶段

- [ ] `vkCmdBeginRenderPass` 指定的 framebuffer 与 render pass 兼容？
- [ ] `renderArea` 是否合理？（过小不能裁剪所有渲染工作，过大增加 load/store 开销）[TOOL]
- [ ] Clear value 数量与 attachment 数量匹配？
- [ ] Draw 使用的 pipeline 与当前 subpass 的 attachment 数量/格式兼容？

### 销毁阶段

- [ ] 所有引用该 render pass 的 command buffer 已完成？
- [ ] Framebuffer 与 render pass 的销毁顺序是否安全？

---

## 7. 高频错误

1. `initialLayout` 与实际 image layout 不匹配，导致验证层报错或隐式 transition 缺失。[TOOL]
2. `pDependencies` 遗漏，导致相邻 subpass 之间 attachment 数据不可见。[TOOL]
3. Color attachment 数量与 pipeline 的 `pColorBlendState.attachmentCount` 不一致。[TOOL]
4. Multisample attachment 的 `samples` 与 framebuffer image 的 sample count 不一致。[TOOL]
5. `loadOp = CLEAR` 时未提供 clear value，或 clear value 索引错误。[TOOL]
6. 在 render pass 外部使用只兼容该 render pass 的 pipeline。[TOOL]
7. 忘记 `VK_SUBPASS_EXTERNAL` 与外部命令之间的 dependency。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkRenderPassCreateInfo-*`：attachment/subpass/dependency 的合法性。
- `VUID-vkCmdBeginRenderPass-renderPass-00904`：framebuffer 与 render pass 兼容。
- `VUID-vkCmdEndRenderPass-02608` 等：subpass 状态与 dependency 检查。

### RenderDoc / AGI

- 查看 render pass 的 attachment 内容、load/store op、clear color。
- 检查每个 subpass 的输入/输出 attachment 与 pipeline 状态。
- 分析移动端 tile memory 占用与 resolve/store 开销。

### 日志 / 代码检查

- 检查 render pass 与 framebuffer / pipeline 的创建参数是否一致。
- 检查 resize / recreate 时 render pass 是否被重建。
- 检查 clear values 数组长度。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建，通常按 material pass / 后处理阶段分类；swapchain 格式变化时可能需要重建。[ENGINE]

### 使用时机

- 在 command buffer 录制阶段通过 `vkCmdBeginRenderPass` 进入，draw 命令必须在其内部。[SPEC]

### 销毁时机

- 确认 GPU 不再执行引用该 render pass 的 command buffer 后销毁。[SPEC]

### in-flight 风险

- Render pass 被 command buffer 和 framebuffer 引用后，fence signal 前不能销毁。[SPEC]
- Swapchain recreate 时旧 render pass 可能仍被 in-flight frame 使用，需延迟销毁或按 per-swapchain 管理。

---

## 10. 同步风险

### CPU-GPU 同步

- Render pass 创建本身不需要 fence；但销毁旧 render pass 需要等待 GPU 完成。[SPEC]

### GPU-GPU 同步

- Subpass dependency 定义同一 render pass 内 subpass 之间的执行与 memory 依赖。[SPEC]
- 与 render pass 外部命令的同步需使用 `VK_SUBPASS_EXTERNAL` 的 dependency 或额外的 pipeline barrier。[SPEC]

### 资源访问同步

- Attachment 的 layout transition 通常由 render pass begin/end 自动处理，但仍需正确设置 `initialLayout` / `finalLayout`。[SPEC]
- Input attachment 的读取需要 `INPUT_ATTACHMENT_READ_BIT` 与对应 stage。[SPEC]

---

## 11. Android 注意点

- Tile-based GPU 上 render pass 的 load/store op 直接决定 tile memory 带宽；`LOAD_OP_CLEAR`/`STORE_OP_DONT_CARE` 比 `LOAD`/`STORE` 更省带宽。[ANDROID][ENGINE]
- 避免 render area 设置成全屏后再用小 scissor 裁剪，仍可能触发全屏 load/store。[ANDROID]
- 横竖屏切换导致 surface 尺寸变化时，framebuffer 需要重建，但 render pass 本身若 format/sample 不变通常可复用。[ANDROID]
- AGI 可分析每 render pass 的 tile 开销与 resolve 次数。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Render pass 对象数量应有限，避免为每帧或每个微小状态差异创建新对象。[ENGINE]
- 使用 `VK_KHR_dynamic_rendering` 可减少大量 render pass 对象的维护成本，但需权衡兼容性。[GUIDE]

### GPU 侧

- Load/store op 选择直接影响 bandwidth；尽量使用 `CLEAR` / `DONT_CARE` 而非 `LOAD` / `STORE`。[ENGINE]
- Subpass dependency 过宽（`ALL_COMMANDS_BIT`）会限制 GPU 并行。[HEUR]
- 过多 subpass 会增加 command processor 与 tile 切换开销。[ENGINE]

### 移动端

- 尽量减少每帧 render pass 切换次数；合并 subpass 或合并 draw call。[ENGINE]
- 注意 `STORE_OP_STORE` 会把 tile 数据写回 system memory，增加功耗；不需要保留的 attachment 用 `DONT_CARE`。[ANDROID]
- MSAA resolve 最好通过 subpass resolve attachment 完成，避免手动 resolve。[ENGINE]

---

## 13. 专家经验

**经验**：
把 render pass 当作“渲染阶段”而非“单个 draw call”的描述：一个主光 pass、一个后处理 pass、一个 UI pass 通常只需少量 render pass。通过 subpass 做 input attachment 读取或 MSAA resolve，比手动 barrier 更高效。对移动端，load/store op 的选择和 render area 大小是性能调优的首要杠杆。

**适用条件**：
多阶段渲染、MSAA、deferred shading、tile-based GPU 项目。

**不适用情况**：
极简单单 pass 渲染且目标设备支持 dynamic rendering 时，可考虑直接用 `VK_KHR_dynamic_rendering` 省略 render pass 对象。

**来源**：`[ENGINE][ANDROID][SPEC]`

---

## 14. 相关 API 卡片

- `dynamic_rendering.md`
- `attachment_load_store.md`
- `render_target_layout.md`
- `../04_buffer_image_memory/framebuffer.md`
- `../06_pipeline/graphics_pipeline.md`
- `../06_pipeline/pipeline_layout.md`
- `../08_synchronization/pipeline_barrier.md`
- `../08_synchronization/image_memory_barrier.md`
- `../04_buffer_image_memory/image_view.md`
- `../03_command_buffer/command_buffer.md`

---

## 15. 需要回查官方文档的情况

1. 具体 format 与 sample count 的组合是否被 render pass attachment 支持。
2. Multiview / fragment shading rate / fragment density map 与 subpass 描述的交互。
3. Self-dependency 与 `VK_DEPENDENCY_BY_REGION_BIT` 的精确限制。
4. Dynamic rendering 与 render pass 混合使用时的兼容性规则。
5. 特定驱动对 render area 的优化行为。

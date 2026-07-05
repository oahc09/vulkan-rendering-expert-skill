# API Card: VkCommandBuffer

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 |
| Vulkan 对象 | `VkCommandBuffer` |
| 常用 API | `vkAllocateCommandBuffers` / `vkFreeCommandBuffers` / `vkResetCommandBuffer` / `vkBeginCommandBuffer` / `vkEndCommandBuffer` / `vkCmd*` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkCommandBuffer` 是 CPU 录制、GPU 执行的命令队列，所有绘制、计算、资源状态转换、同步操作都必须先记录到 command buffer 中，再通过 `vkQueueSubmit` 提交给 GPU。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice
→ VkCommandPool
→ VkCommandBuffer
→ Record Commands (vkCmd*)
→ vkEndCommandBuffer
→ vkQueueSubmit
→ GPU Execution
```

### 上游依赖

- `VkDevice` 必须有效。[SPEC]
- `VkCommandPool` 必须属于正确的 queue family。[SPEC]
- 所需的 `VkPipeline`、`VkDescriptorSet`、`VkBuffer`、`VkImage` 等对象必须已创建。[SPEC]

### 下游影响

- `vkQueueSubmit` 接收 command buffer 并触发 GPU 执行。
- Command buffer 引用的所有资源在 GPU 执行完成前必须保持有效。[SPEC]
- Command buffer 状态（recording / executable / pending / invalid）决定能否 reset / submit。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkCommandBuffer`
- `VkCommandBufferAllocateInfo`
- `VkCommandBufferBeginInfo`
- `VkCommandBufferInheritanceInfo`（secondary command buffer 使用）
- `VkCommandPool`

### 常用 API

| API | 作用 |
|---|---|
| `vkAllocateCommandBuffers` | 从 command pool 分配 command buffer。[SPEC] |
| `vkFreeCommandBuffers` | 释放 command buffer，可在任何状态调用（但需确保 GPU 不再使用）。[SPEC] |
| `vkResetCommandBuffer` | 重置单个 command buffer，清除已录制的命令。[SPEC] |
| `vkResetCommandPool` | 重置整个 command pool，更高效但会重置池中所有 buffer。[SPEC] |
| `vkBeginCommandBuffer` | 开始录制，指定 usage flags。[SPEC] |
| `vkEndCommandBuffer` | 结束录制，进入 executable 状态。[SPEC] |
| `vkCmd*` | 各类录制命令：draw、dispatch、barrier、copy、pipeline bind 等。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_debug_utils`：可用于为 command buffer 设置 debug name / marker，便于 RenderDoc / Validation 识别。[TOOL]
- Secondary command buffer 通过 `VK_COMMAND_BUFFER_USAGE_RENDER_PASS_CONTINUE_BIT` 在 render pass 内继续执行。[SPEC]

---

## 4. 标准使用流程

```text
创建 VkCommandPool（属于目标 queue family）
→ vkAllocateCommandBuffers
→ vkBeginCommandBuffer（指定 ONE_TIME_SUBMIT 等 flag）
→ 录制 vkCmd* 命令
→ vkEndCommandBuffer
→ vkQueueSubmit
→ GPU 执行
→ Fence signal 后
→ vkResetCommandBuffer（或 vkResetCommandPool）
→ 重新 vkBeginCommandBuffer 录制下一帧
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `commandPool` | 必须属于将要 submit 的 queue family。[SPEC] | compute 工作分配到 graphics command pool。[SPEC] |
| `level` | `PRIMARY` 可直接 submit；`SECONDARY` 只能被 primary execute。[SPEC] | 误将 secondary 直接 submit。[SPEC] |
| `flags`（begin） | `ONE_TIME_SUBMIT_BIT`：每帧录制一次；`RENDER_PASS_CONTINUE_BIT`：secondary 在 render pass 内继续。[SPEC] | 未使用 `ONE_TIME_SUBMIT_BIT` 但每帧 reset，失去语义提示。[HEUR] |
| `pInheritanceInfo` | Secondary command buffer 必须提供 render pass / framebuffer / subpass / occlusion query 信息。[SPEC] | secondary 未指定 inheritance info 导致 validation 错误。[TOOL] |
| `pBeginInfo->flags` | 决定 command buffer 是否可二次 submit、是否在 render pass 内继续。[SPEC] | 同一 buffer 多次 submit 但未设 `SIMULTANEOUS_USE_BIT`。[SPEC] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VkCommandPool` 的 queue family 是否与 submit 目标 queue 一致？
- [ ] 分配的 command buffer level 是否符合用途（primary / secondary）？
- [ ] 是否为 frame-in-flight 分配足够数量的 command buffer？

### 使用阶段

- [ ] 是否在 `vkBeginCommandBuffer` 前调用了 `vkResetCommandBuffer`（除非 pool reset）？
- [ ] `vkBeginCommandBuffer` 与 `vkEndCommandBuffer` 是否配对？
- [ ] 录制的命令是否在当前 render pass / dynamic rendering 状态下合法？
- [ ] Pipeline、descriptor、vertex buffer 是否在 draw / dispatch 前已绑定？
- [ ] Image layout / barrier 是否满足当前 command 的要求？

### 销毁阶段

- [ ] 销毁或 reset 前，对应 fence 是否已 signal？
- [ ] 是否存在 command buffer 仍引用已销毁资源的风险？

---

## 7. 高频错误

1. 未等待 fence 就 reset 正在 GPU 执行的 command buffer。[SPEC]
2. `vkBeginCommandBuffer` 前未 reset，导致 `VK_ERROR_INITIALIZATION_FAILED` 或 validation 错误。[TOOL]
3. 将 secondary command buffer 直接 `vkQueueSubmit`。[SPEC]
4. Command buffer 录制完成后未调用 `vkEndCommandBuffer`。[SPEC]
5. Command buffer 引用了已销毁的 `VkFramebuffer`、`VkImageView` 或 `VkBuffer`。[SPEC]
6. 同一 frame resource 被多帧 command buffer 复用但 fence 管理错误。[ENGINE]
7. Compute 与 graphics command buffer 混用错误的 command pool。[SPEC]
8. 在 recording 状态的 command buffer 上调用除 `vkCmd*` / `vkEndCommandBuffer` 之外的 API。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkBeginCommandBuffer-*`：command buffer 状态、flags、inheritance info。
- `VUID-vkEndCommandBuffer-*`：recording 是否完整、render pass 是否结束。
- `VUID-vkQueueSubmit-*`：command buffer 是否处于 executable 状态。
- `VUID-vkResetCommandBuffer-*`：command buffer 不在 pending 状态。
- `VUID-vkCmdDraw-*` / `VUID-vkCmdDispatch-*`：pipeline / descriptor / vertex buffer / layout 状态。

### RenderDoc / AGI

- 确认是否存在 draw / dispatch call。
- 确认 command buffer 录制是否完整。
- 查看每个 command 的 pipeline state、descriptor binding、resource 内容。[TOOL]

### 日志 / 代码检查

- 检查 `vkAllocateCommandBuffers`、`vkBeginCommandBuffer`、`vkEndCommandBuffer`、`vkQueueSubmit` 返回值。
- 检查 frame-in-flight 的 fence 等待逻辑。
- 检查 reset / begin 顺序。

---

## 9. 生命周期风险

### 创建时机

- Renderer 初始化时，按 frame-in-flight 数量分配 per-frame command buffer。
- 长期存在的 command buffer（如初始化时的 upload buffer）可单独管理。

### 使用时机

- 每帧录制渲染命令。
- 初始化阶段录制资源上传命令。
- Compute pass 录制 dispatch 命令。

### 销毁时机

- 对应 command pool 销毁时自动释放；也可单独 `vkFreeCommandBuffers`。[SPEC]
- 必须确保 GPU 不再使用，否则 free 后仍被 pending submit 引用会导致 crash。[SPEC]

### in-flight 风险

- Command buffer 被 submit 后进入 pending 状态，在 fence signal 前不能 reset / free / reuse。[SPEC]
- Command buffer 引用的资源（image view、framebuffer、buffer、descriptor）在 GPU 完成前必须保持有效。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 通过 fence 等待 command buffer 执行完成，之后才能 reset / free。[SPEC]
- 不要在 `vkQueueSubmit` 返回后立即 reset，必须等待 fence。[SPEC]

### GPU-GPU 同步

- Command buffer 内部的 barrier、semaphore wait、event wait 控制 GPU 执行顺序。[SPEC]
- 多个 command buffer 提交到同一 queue 时按 submit 顺序执行；跨 queue 需要 semaphore。[SPEC]

### 资源访问同步

- 同一 command buffer 内可通过 `vkCmdPipelineBarrier` 安排资源状态转换。[SPEC]
- 跨 command buffer 的资源依赖必须通过 semaphore 或 fence 保证。[SPEC]

---

## 11. Android 注意点

- Android 上 command pool 通常按 queue family 创建，graphics / compute / transfer 需分开或确保 queue family 兼容。[ANDROID]
- Surface / swapchain recreate 后，旧的 command buffer 仍可能引用旧 framebuffer / image view，必须等待 idle 后再 reset。[ANDROID]
- 移动端应避免每帧 allocate / free command buffer，使用 reset + reuse。[ENGINE]
- AGI 可查看每帧 command buffer 录制内容与 GPU 执行时间线。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 每帧 allocate / free command buffer 会带来显著 CPU 开销；推荐 per-frame reset + reuse。[ENGINE]
- `vkResetCommandPool` 通常比逐个 `vkResetCommandBuffer` 更高效。[ENGINE]
- 减少 command buffer 分段，合并小的 copy / barrier 命令可降低录制开销。[HEUR]

### GPU 侧

- Command buffer 本身不直接决定 GPU 性能，但内部的 barrier、layout transition、render pass 边界会影响 GPU 并行度。[SPEC]
- Secondary command buffer 适合多线程录制，但 execute 时存在 overhead，不适合极短命令。[HEUR]

### 移动端

- 移动端 command buffer 录制开销对 CPU frame time 影响明显，应避免每帧动态分配。[ENGINE]
- 尽量减少每帧的 pipeline bind 和 descriptor bind 切换次数。[ENGINE]

---

## 13. 专家经验

**经验**：
为每个 frame-in-flight slot 分配独立的 command buffer（或独立的 command pool），配合 fence 使用。这样每帧只需 reset 当前 slot 的 buffer，无需等待所有 GPU 工作完成。

**适用条件**：
双缓冲 / 三缓冲渲染，CPU 需要提前准备下一帧。

**不适用情况**：
单缓冲或命令极少、CPU 不提前准备帧的场景。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `queue_submit.md`
- `command_buffer_lifetime.md`
- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`
- `../08_synchronization/pipeline_barrier.md`
- `../06_pipeline/graphics_pipeline.md`
- `../05_descriptor/descriptor_set.md`

---

## 15. 需要回查官方文档的情况

1. Secondary command buffer 的 inheritance info 具体要求。
2. `VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT` 的使用限制。
3. Command pool 与 queue family 的精确对应关系。
4. 多线程下 command buffer 录制与 pool 的线程安全规则。

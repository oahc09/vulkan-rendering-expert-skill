# API Card: vkQueueSubmit

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 / 同步链 |
| Vulkan 对象 | `VkQueue` / `VkCommandBuffer` / `VkSubmitInfo` / `VkTimelineSemaphoreSubmitInfo` |
| 常用 API | `vkQueueSubmit` / `vkQueueSubmit2` / `vkQueueWaitIdle` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0；`vkQueueSubmit2` 需 Vulkan 1.3 或 `VK_KHR_synchronization2` |

---

## 1. 一句话定位

`vkQueueSubmit` 是把已录制的 command buffer 提交给 GPU queue 执行的入口，同时负责插入 CPU-GPU 和 GPU-GPU 同步点（fence / semaphore / timeline semaphore）。[SPEC]

---

## 2. 所属对象链路

```text
VkCommandBuffer (executable)
→ VkSubmitInfo (wait semaphores / signal semaphores / command buffers / fence)
→ vkQueueSubmit
→ GPU Queue
→ GPU Execution
→ Signal Fence / Semaphores
```

### 上游依赖

- Command buffer 必须处于 executable 状态（已 `vkEndCommandBuffer`）。[SPEC]
- Command buffer 必须来自与 submit queue 兼容的 command pool（同一 queue family）。[SPEC]
- Wait semaphore 必须已被 signal 或处于 pending signal 状态。[SPEC]
- Timeline semaphore 值必须单调递增。[SPEC]

### 下游影响

- GPU 开始执行 command buffer 中的命令。
- Fence 在 GPU 完成后被 signal。[SPEC]
- Signal semaphore 在 GPU 完成后被 signal，可被后续 submit / present 等待。[SPEC]
- Present 通常依赖 graphics queue 的 signal semaphore。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkQueue`
- `VkSubmitInfo`
- `VkCommandBufferSubmitInfo`（synchronization2）
- `VkSemaphoreSubmitInfo`（synchronization2）
- `VkFence`
- `VkSemaphore`（binary / timeline）

### 常用 API

| API | 作用 |
|---|---|
| `vkQueueSubmit` | 传统 submit，支持 binary semaphore 和 fence。[SPEC] |
| `vkQueueSubmit2` / `vkQueueSubmit2KHR` | Synchronization2 路径，支持 timeline semaphore、更清晰的 stage mask。[SPEC] |
| `vkQueueWaitIdle` | 等待该 queue 所有工作完成。[SPEC] |
| `vkDeviceWaitIdle` | 等待所有 queue 所有工作完成。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_synchronization2`：提供更灵活的 stage / access mask，推荐在新项目中评估使用。[GUIDE]
- `VK_KHR_timeline_semaphore`：timeline semaphore 在 1.2 核心化，可用于跨帧依赖管理。[SPEC]

---

## 4. 标准使用流程

```text
录制 command buffer
→ 准备 VkSubmitInfo:
    pWaitSemaphores      = [imageAvailableSemaphore]
    pWaitDstStageMask    = [COLOR_ATTACHMENT_OUTPUT_BIT]  // 或 ALL_COMMANDS / TOP_OF_PIPE
    pCommandBuffers      = [cmd]
    pSignalSemaphores    = [renderFinishedSemaphore]
→ vkQueueSubmit(queue, 1, &submitInfo, inFlightFence)
→ GPU 执行
→ renderFinishedSemaphore signal 后 vkQueuePresentKHR 可执行
→ inFlightFence signal 后 CPU 可复用 frame resource
```

Synchronization2 流程：

```text
VkCommandBufferSubmitInfo cmdInfo{ cmd };
VkSemaphoreSubmitInfo waitInfo{ imageAvailableSemaphore, COLOR_ATTACHMENT_OUTPUT_BIT };
VkSemaphoreSubmitInfo signalInfo{ renderFinishedSemaphore, ALL_GRAPHICS_BIT };
VkSubmitInfo2 submitInfo{ ... };
vkQueueSubmit2(queue, 1, &submitInfo, inFlightFence);
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `waitSemaphoreCount` / `pWaitSemaphores` | 必须与 acquire / 前序 pass 的 signal semaphore 一一对应。[SPEC] | semaphore 数量或顺序与 `pWaitDstStageMask` 不匹配。[TOOL] |
| `pWaitDstStageMask` | 决定 GPU 在哪些 pipeline stage 等待 semaphore，应尽量精确。[SPEC] | 填 `ALL_COMMANDS` 导致过度同步；填错 stage 导致 hazard。[TOOL] |
| `commandBufferCount` / `pCommandBuffers` | 一次 submit 可包含多个 command buffer，按顺序执行。[SPEC] | 跨 frame 的 command buffer 混在一个 submit 中，fence 管理混乱。[ENGINE] |
| `signalSemaphoreCount` / `pSignalSemaphores` | 通常一个 renderFinishedSemaphore 供 present 等待。[SPEC] | signal 与 present 等待的 semaphore 不一致。[SPEC] |
| `fence` | 用于 CPU 等待 GPU 完成；可为 `VK_NULL_HANDLE`。[SPEC] | 同一 fence 被多个重叠 submit 使用。[SPEC] |
| `pNext` timeline info | Timeline semaphore 必须填写 `VkTimelineSemaphoreSubmitInfo` 指定 wait / signal value。[SPEC] | 值未单调递增或类型未使用 timeline semaphore。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Submit queue 是否与 command buffer 的 command pool queue family 一致？
- [ ] Wait semaphore 是否已创建且处于可用状态？
- [ ] Signal semaphore 是否与后续 consumer（present / 下一 submit）匹配？
- [ ] Fence 是否未被其他 pending submit 占用？

### 使用阶段

- [ ] 是否检查 `vkQueueSubmit` 返回值？
- [ ] Wait stage mask 是否与 producer 的 signal stage 匹配？
- [ ] 同一 frame 的 acquire / submit / present semaphore 是否一一对应？
- [ ] Timeline semaphore 值是否单调递增？

### 销毁阶段

- [ ] Fence signal 后才能释放或复用相关资源。
- [ ] 不要销毁仍在 pending submit 中使用的 semaphore。[SPEC]

---

## 7. 高频错误

1. `vkQueueSubmit` 的 wait semaphore 与 `vkAcquireNextImageKHR` 的 signal semaphore 不是同一个。[SPEC]
2. Wait stage mask 填 `TOP_OF_PIPE`，导致后续 color attachment 操作在 image 可用前开始。[SPEC]
3. 同一 fence 被连续两帧使用，前一帧 GPU 未完成时后一帧又 submit。[SPEC]
4. Command buffer 仍处于 recording 状态就 submit。[SPEC]
5. 多 queue 场景下 semaphore 跨 queue 传递但 stage mask 设置错误。[SPEC]
6. Timeline semaphore 的 wait value 大于 signal value，导致永久等待。[TOOL]
7. Submit 到错误 queue（如 compute queue 提交 graphics command buffer）。[SPEC]
8. Present 等待的 semaphore 不是该 frame 的 renderFinishedSemaphore。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkQueueSubmit-*`：command buffer 状态、semaphore 状态、fence 状态。
- `VUID-VkSubmitInfo-*`：wait / signal semaphore、stage mask 匹配。
- Synchronization hazard 提示：producer / consumer 缺少 barrier 或 semaphore。[TOOL]

### RenderDoc / AGI

- 查看 submit 后 draw / dispatch 是否实际执行。
- 查看 semaphore wait / signal 时间线。
- AGI 可查看 queue submit 与 present 的时序关系。[TOOL]

### 日志 / 代码检查

- 打印 `vkQueueSubmit` 返回值。
- 打印每个 frame 的 acquire / submit / present semaphore handle。
- 检查 fence wait / reset 顺序。
- 检查多 queue 时 semaphore 传递逻辑。

---

## 9. 生命周期风险

### 创建时机

- Queue 在 device 创建时获取。
- Submit 结构体每帧在栈上或 per-frame slot 中构建。

### 使用时机

- Command buffer 录制完成后立即 submit。
- 多 frame-in-flight 时，每帧 submit 到自己的 fence / semaphore 集合。

### 销毁阶段

- Fence 在 signal 后可 reset 或销毁。
- Semaphore 可复用，但不要在 pending 状态销毁。
- 应用退出时使用 `vkDeviceWaitIdle` 确保所有 submit 完成。[SPEC]

### in-flight 风险

- Submit 后 command buffer 进入 pending 状态，fence signal 前不能 reset。[SPEC]
- Semaphore 被 wait 前必须已经被 signal；重复使用 binary semaphore 需确保已完成 wait。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Fence 是 CPU 等待 GPU 的主要机制。[SPEC]
- `vkQueueSubmit` 返回不代表 GPU 执行完成，只有 fence signal 才代表完成。[SPEC]

### GPU-GPU 同步

- Binary semaphore：acquire → render → present 的标准链。[SPEC]
- Timeline semaphore：适合管理跨帧依赖、upload → render 依赖。[GUIDE]
- 同一 queue 内多个 command buffer 按 submit 顺序执行，无需额外 semaphore。[SPEC]
- 跨 queue 必须显式 semaphore 同步。[SPEC]

### 资源访问同步

- Submit 的 wait stage mask 必须与 producer 的 signal stage 匹配，否则 consumer 可能在资源就绪前访问。[SPEC]
- Image layout transition 通常在 command buffer 内通过 barrier 完成，不需要跨 submit。[SPEC]

---

## 11. Android 注意点

- Android 通常使用单一 graphics/present queue，semaphore 链路为：acquire semaphore → submit wait → submit signal → present wait。[ANDROID]
- `VK_SUBOPTIMAL_KHR` / `VK_ERROR_OUT_OF_DATE_KHR` 出现后，当前 frame 的 submit 可能已失败或需要 recreate，不能继续 present。[ANDROID]
- 某些 Android 设备对 `vkQueueSubmit` 的 CPU 开销敏感，应尽量减少 submit 批次。[ENGINE]
- AGI 可检查 queue submit 与 surface present 的时序，发现 latency 问题。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 减少每帧 `vkQueueSubmit` 调用次数，合并 command buffer 可降低 CPU overhead。[ENGINE]
- 但过度合并会损失 CPU-GPU 并行度，需权衡。[HEUR]

### GPU 侧

- Wait stage mask 应尽量精确，避免 `ALL_COMMANDS` 造成 GPU 空等。[ENGINE]
- Timeline semaphore 可减少每帧 allocate / 管理 binary semaphore 的开销。[GUIDE]

### 移动端

- 移动端 CPU 侧 submit overhead 明显，建议每帧一次 graphics submit + 必要时一次 compute submit。[ENGINE]
- 避免频繁 `vkQueueWaitIdle`，会阻塞 CPU 和 GPU 并行。[ENGINE]

---

## 13. 专家经验

**经验**：
标准双缓冲 / 三缓冲 frame loop 中，每帧使用独立的 imageAvailableSemaphore、renderFinishedSemaphore 和 inFlightFence。不要把同一 semaphore / fence 用于重叠的多帧。

**适用条件**：
常规 Android / 桌面渲染，存在多 frame-in-flight。

**不适用情况**：
单帧渲染、命令完全串行、或已使用 timeline semaphore 统一管理的场景。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `command_buffer.md`
- `command_buffer_lifetime.md`
- `../02_surface_swapchain/swapchain.md`
- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`
- `../08_synchronization/synchronization2.md`

---

## 15. 需要回查官方文档的情况

1. `VkPipelineStageFlags` 与 semaphore wait stage 的精确匹配规则。
2. Timeline semaphore 与 binary semaphore 的混合使用限制。
3. `VK_KHR_synchronization2` 中 `VkSubmitInfo2` 的 stage mask 语义变化。
4. Device group / multi-queue 场景下的 submit 规则。

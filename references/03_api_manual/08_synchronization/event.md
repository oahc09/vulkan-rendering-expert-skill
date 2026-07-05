# API Card: VkEvent

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkEvent` |
| 常用 API | `vkCreateEvent` / `vkDestroyEvent` / `vkCmdSetEvent` / `vkCmdResetEvent` / `vkCmdWaitEvents` / `vkGetEventStatus` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkEvent` 是一种轻量级的“ GPU 事件点”同步对象，允许在 command buffer 中设置与等待事件，实现比 pipeline barrier 更细粒度、更局部的执行与内存依赖控制。[SPEC]

---

## 2. 所属对象链路

```text
vkCreateEvent
→ VkEvent
→ vkCmdSetEvent（在 command buffer 中标记事件点）
→ vkCmdWaitEvents（在同一或其他 command buffer 中等待事件并插入 barrier）
→ vkCmdResetEvent（重置事件状态）
→ vkDestroyEvent
```

### 上游依赖

- 已创建的逻辑设备。[SPEC]
- 需要同步的 producer 与 consumer 命令已分别录制到 command buffer。[SPEC]

### 下游影响

- 控制 command buffer 内部或跨 command buffer 的局部同步，减少不必要的全局 barrier。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkEvent`
- `VkEventCreateInfo`
- `VkEventCreateFlags`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateEvent` | 创建 event 对象。[SPEC] |
| `vkDestroyEvent` | 销毁 event；需确保 GPU 不再使用。[SPEC] |
| `vkCmdSetEvent` | 在 command buffer 中设置 event。[SPEC] |
| `vkCmdResetEvent` | 在 command buffer 中重置 event。[SPEC] |
| `vkCmdWaitEvents` | 等待一个或多个 event，并插入 execution/memory dependency。[SPEC] |
| `vkGetEventStatus` | CPU 查询 event 状态（慎用，可能阻塞或轮询）。[SPEC] |
| `vkSetEvent` / `vkResetEvent` | CPU 端直接设置/重置 event。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供更细粒度的 `vkCmdWaitEvents2`。

---

## 4. 标准使用流程

```text
vkCreateEvent
→ 在 producer command buffer 末尾 vkCmdSetEvent
→ 提交 producer command buffer
→ 在 consumer command buffer 开头 vkCmdWaitEvents（并指定 stage/access）
→ 提交 consumer command buffer（需保证 consumer 在 producer 之后提交到同一 queue）
→ vkCmdResetEvent 在合适位置重置（如需复用）
→ vkDestroyEvent
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `pEvents` | 等待的 event 数组；每个 event 必须已被设置。[SPEC] | 等待未设置或已重置的 event。[TOOL] |
| `srcStageMask` / `dstStageMask` | wait events 的 execution dependency 范围。[SPEC] | stage 过宽或过窄。[TOOL] |
| `pMemoryBarriers` / `pBufferMemoryBarriers` / `pImageMemoryBarriers` | 与 wait events 关联的 memory dependency。[SPEC] | 只 wait 不 barrier，导致内存不可见。[TOOL] |
| `signal stage`（vkCmdSetEvent 的 stage mask） | event 在哪个 stage 完成后被设置。[SPEC] | signal stage 早于 producer 实际完成 stage。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否需要细粒度事件点同步？
- [ ] 是否计划了 set/reset/wait 的完整生命周期？

### 使用阶段

- [ ] `vkCmdWaitEvents` 是否位于 `vkCmdSetEvent` 之后提交？
- [ ] Wait 的 memory barrier 是否覆盖 consumer 需要访问的资源？
- [ ] Signal stage 是否晚于 producer 完成其工作的 stage？
- [ ] 是否处理了 event 的重置与复用？

### 销毁阶段

- [ ] 是否等待所有引用 event 的 command buffer 完成？

---

## 7. 高频错误

1. `vkCmdWaitEvents` 只等待 event 但忘记提供 memory barrier，导致数据不可见。[TOOL]
2. `vkCmdSetEvent` 的 stage mask 过早，producer 尚未完成就触发 event。[TOOL]
3. 在 `vkCmdWaitEvents` 之前 event 已被 `vkCmdResetEvent` 重置。[TOOL]
4. 跨 queue 使用 event 却没有 semaphore 保证提交顺序。[TOOL]
5. CPU 轮询 `vkGetEventStatus` 导致 CPU 开销。[TOOL]
6. 未重置 event 就再次 set，导致状态混乱。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdWaitEvents-*`：event 状态、stage/access、barrier 合法性。
- `VUID-vkCmdSetEvent-stageMask-01183`：stage mask 合法性。

### RenderDoc / AGI

- 查看 event set/wait/reset 在 command buffer 中的位置。
- 分析 wait events 是否造成 GPU 气泡。

### 日志 / 代码检查

- 检查 set/wait/reset 是否成对出现。
- 检查 event 是否被多个 command buffer 错误复用。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建，按需复用。[ENGINE]

### 使用时机

- 在 command buffer 录制阶段通过 set/wait/reset 控制同步。[SPEC]

### 销毁时机

- 确认 GPU 不再使用相关 command buffer 后销毁。[SPEC]

### in-flight 风险

- Event 被 command buffer 引用后，需等其完成才能销毁或复用。[SPEC]
- 复用 event 时必须确保上一次 wait 已完成并正确 reset。

---

## 10. 同步风险

### CPU-GPU 同步

- `vkGetEventStatus` 可用于 CPU 查询，但通常不建议轮询；CPU 等待应使用 fence。[SPEC]
- `vkSetEvent` 可从 CPU 触发 event，用于 CPU-GPU 协作场景。[SPEC]

### GPU-GPU 同步

- Event 只保证同一 queue 内的执行顺序；跨 queue 仍需 semaphore。[SPEC]
- `vkCmdWaitEvents` 建立 execution dependency，但 memory dependency 需要显式 barrier。[SPEC]

### 资源访问同步

- `vkCmdWaitEvents` 可同时携带 global / buffer / image memory barrier，实现局部资源同步。[SPEC]

---

## 11. Android 注意点

- Event 可减少 command buffer 中冗余的全局 barrier，对移动端 tile-based GPU 有益。[ANDROID][ENGINE]
- 但 event 使用不当容易引入 GPU 气泡，建议通过 AGI 验证实际效果。[TOOL]
- 避免在 render pass 内部频繁 set/wait event，可能破坏 tile 渲染优化。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Event 对象创建/销毁开销低，但管理 event 状态需要小心设计。[ENGINE]

### GPU 侧

- Event 可用于减少过度同步：只在真正需要时 wait，而不是在 pass 边界做全 barrier。[ENGINE]
- Wait events 会让 GPU 在特定点等待，若设计不当会形成气泡。[HEUR]

### 移动端

- 对 compute shader 之间的流水线式数据传递，event 比 pipeline barrier 更灵活。[ENGINE]
- 避免每帧创建/销毁 event，应池化复用。[ENGINE]

---

## 13. 专家经验

**经验**：
Event 适合“同一 queue 内、局部资源、可预测时序”的同步场景，例如 compute pass 内部的多个 dispatch 之间的数据流水线。不要为了替代 semaphore 而跨 queue 使用 event，也不要为了替代 pipeline barrier 而滥用 event——event 的优势在于减少不必要的全局同步，而不是让同步逻辑变得更复杂。

**适用条件**：
同 queue 内多个 producer-consumer 阶段、需要减少全局 barrier 的 compute/graphics 混合管线。

**不适用情况**：
跨 queue 同步（用 semaphore）；CPU 需要知道完成时机（用 fence）；简单的全局资源切换（用 pipeline barrier 更直接）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `pipeline_barrier.md`
- `buffer_memory_barrier.md`
- `image_memory_barrier.md`
- `semaphore.md`
- `fence.md`
- `synchronization2.md`
- `../03_command_buffer/command_buffer.md`
- `../03_command_buffer/queue_submit.md`

---

## 15. 需要回查官方文档的情况

1. `vkCmdWaitEvents` 与 `vkCmdPipelineBarrier` 在 stage mask 上的精确差异。
2. `VK_KHR_synchronization2` 中 `vkCmdWaitEvents2` 的扩展语义。
3. Event 在 secondary command buffer 中的使用限制。
4. `vkGetEventStatus` 在不同驱动上的阻塞行为。
5. Event 与 render pass 内部 subpass dependency 的交互规则。

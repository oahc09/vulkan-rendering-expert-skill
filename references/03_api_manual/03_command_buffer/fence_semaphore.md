# API Card: Fence 与 Semaphore 的选择与组合

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 / 同步链 |
| Vulkan 对象 | `VkFence` / `VkSemaphore` / `VkTimelineSemaphore` |
| 常用 API | `vkQueueSubmit` / `vkQueuePresentKHR` / `vkWaitForFences` / `vkResetFences` / `vkAcquireNextImageKHR` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0（Fence / Binary Semaphore）；Vulkan 1.2 / `VK_KHR_timeline_semaphore`（Timeline Semaphore） |

---

## 1. 一句话定位

`VkFence` 用于 CPU 等待 GPU 完成，`VkSemaphore` 用于 GPU 命令之间的跨阶段/跨队列信号传递；两者通常组合使用，分别解决 CPU-GPU 与 GPU-GPU 两类不同粒度的同步问题。[SPEC]

---

## 2. 所属对象链路

```text
CPU 侧帧调度
→ vkAcquireNextImageKHR (acquire semaphore)
→ 录制 command buffer
→ vkQueueSubmit (wait: acquire / signal: render complete semaphore + fence)
→ vkQueuePresentKHR (wait: render complete semaphore)
→ CPU vkWaitForFences (可选，等待本帧 GPU 完成)
→ vkResetFences / 复用 command buffer
```

### 上游依赖

- `VkQueue` 已创建并处于可用状态。[SPEC]
- 需要同步的 command buffer 已完成录制或已提交。[SPEC]
- Swapchain image 已通过 `vkAcquireNextImageKHR` 获取（present 链）。[SPEC]

### 下游影响

- Fence 决定 CPU 何时可以安全地复用 command buffer、buffer、image 等 in-flight 资源。[SPEC]
- Semaphore 决定 GPU 命令链中 acquire → render → present 的顺序，以及跨队列依赖。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkFence`
- `VkSemaphore`（binary semaphore）
- `VkSemaphore`（timeline semaphore，type `VK_SEMAPHORE_TYPE_TIMELINE`）
- `VkSubmitInfo` / `VkPresentInfoKHR` / `VkSemaphoreSignalInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateFence` / `vkDestroyFence` | 创建 / 销毁 fence。[SPEC] |
| `vkResetFences` | 将 fence 重置为 unsignaled，以便下一轮 submit 使用。[SPEC] |
| `vkWaitForFences` | CPU 阻塞等待 fence signaled。[SPEC] |
| `vkCreateSemaphore` / `vkDestroySemaphore` | 创建 / 销毁 semaphore。[SPEC] |
| `vkQueueSubmit` / `vkQueueSubmit2` | 指定 wait / signal semaphore 与 fence。[SPEC] |
| `vkQueuePresentKHR` | 指定 present 等待的 semaphore。[SPEC] |
| `vkSignalSemaphore` / `vkGetSemaphoreCounterValue` | timeline semaphore 的 CPU 侧信号与查询。[SPEC] |

### 相关扩展 / 版本

- Fence 与 binary semaphore 为 Vulkan 1.0 核心。[SPEC]
- Timeline semaphore 为 Vulkan 1.2 核心，或在 1.1 中通过 `VK_KHR_timeline_semaphore` 启用。[SPEC]
- `VK_KHR_synchronization2` 提供更细粒度的 `VkSubmitInfo2` / `VkSemaphoreSubmitInfo`。[SPEC]

---

## 4. 标准使用流程

### 典型帧渲染流程（ Fence + Binary Semaphore ）

```text
每帧准备 per-frame 资源（command buffer、fence 已 reset）
→ vkAcquireNextImageKHR(acquireSemaphore)
→ 录制渲染命令到 command buffer
→ vkQueueSubmit(
       waitSemaphore = acquireSemaphore,
       signalSemaphore = renderCompleteSemaphore,
       fence = frameFence)
→ vkQueuePresentKHR(waitSemaphore = renderCompleteSemaphore)
→ CPU 在需要时 vkWaitForFences(frameFence) 等待 GPU 完成
→ vkResetFences(frameFence) 后复用资源
```

### Timeline Semaphore 简化多队列/多帧依赖

```text
创建 timeline semaphore（初始值 0）
→ Queue A submit 时 signal value = N
→ Queue B submit 时 waitSemaphoreValue = N
→ CPU 可通过 vkGetSemaphoreCounterValue 查询进度，或用 vkWaitSemaphores 阻塞等待
```

---

## 5. 关键字段

### Fence

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `flags` | `VK_FENCE_CREATE_SIGNALED_BIT` 用于创建时即为 signaled，避免首次 wait 死锁。[SPEC] | 未 signaled 的 fence 直接 submit 后 CPU wait 永远等不到。[TOOL] |
| `pFence` | 每个 per-frame 资源池配一个 fence；不要多个 frame 共用一个未等待的 fence。[ENGINE] | 共用一个 fence 导致 CPU 无法判断哪一帧已完成。[TOOL] |
| `timeout` | `vkWaitForFences` 的超时建议设置合理值（如 1s），便于发现 GPU hang。[HEUR] | timeout = UINT64_MAX 时 GPU hang 将永久阻塞 CPU。[TOOL] |
| `waitAll` | `vkWaitForFences` 的 `waitAll` 决定等待全部还是任一 fence。[SPEC] | 只需要任一完成时误设为 true，降低 CPU 并行度。[HEUR] |

### Binary Semaphore

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `waitSemaphoreCount` / `pWaitSemaphores` | 必须保证 semaphore 在进入 wait 前已被 signal，否则提交非法。[SPEC] | 未 acquire image 就 submit render，导致 wait semaphore 未 signaled。[TOOL] |
| `pWaitDstStageMask` | 决定 GPU 在哪个 stage 开始等待，过宽会降低并行度。[SPEC] | 统一使用 `ALL_COMMANDS` 造成不必要流水线停顿。[HEUR] |
| `signalSemaphoreCount` / `pSignalSemaphores` | signal 与 wait 成对使用，一个 binary semaphore 每轮只能 signal 一次、wait 一次。[SPEC] | 同一 binary semaphore 在多个 submit 中重复 signal 未 reset。[TOOL] |

### Timeline Semaphore

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `semaphoreType` | 创建时指定 `VK_SEMAPHORE_TYPE_TIMELINE`。[SPEC] | 用 binary semaphore 的 API 处理 timeline value。[TOOL] |
| `initialValue` | 创建时指定初始 counter，后续 signal/wait 单调递增。[SPEC] | value 不单调递增或回退导致未定义行为。[TOOL] |
| `value` | submit / signal / wait 时传递目标 counter。[SPEC] | CPU 与 GPU 侧 value 不同步，导致等待失败。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否需要 CPU 等待？是 → 使用 fence。
- [ ] 是否需要 GPU 阶段间顺序？是 → 使用 semaphore。
- [ ] 是否需要跨队列/跨帧细粒度同步？是 → 优先 timeline semaphore。
- [ ] Fence 创建时是否按使用场景设置 `SIGNALED_BIT`？[SPEC]
- [ ] Timeline semaphore 是否在设备创建时启用 `timelineSemaphore` feature？[SPEC]

### 使用阶段

- [ ] Binary semaphore 是否在 wait 之前已被 signal？
- [ ] Submit 的 wait / signal 是否与录制顺序一致？
- [ ] Present 的 wait semaphore 是否是当前帧的 render complete semaphore？
- [ ] Fence 是否已 reset 后再用于新的 submit？

### 销毁阶段

- [ ] 销毁 fence / semaphore 前是否确认 GPU 不再使用？
- [ ] Swapchain recreate 时是否保留仍有效的 timeline semaphore？

---

## 7. 高频错误

1. CPU 直接等待 binary semaphore（应使用 fence 或 timeline semaphore 的 CPU wait）。[TOOL]
2. 同一个 binary semaphore 在多个 submit 中既 signal 又 wait，未形成清晰的一一对应关系。[TOOL]
3. Fence 未 reset 就再次 submit，导致 validation error 或 wait 行为异常。[TOOL]
4. Acquire semaphore 被用于多个 `vkQueueSubmit` 的 wait，违反 binary semaphore 使用规则。[TOOL]
5. Present 的 wait semaphore 不是当前帧渲染完成信号，导致画面撕裂或 validation error。[TOOL]
6. Timeline semaphore 的 value 没有单调递增，或 CPU/GPU 两侧值计算错误。[TOOL]
7. 使用 fence 做 GPU-GPU 同步，造成 CPU 不必要阻塞。[HEUR]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkQueueSubmit-pWaitSemaphores-00068`：wait semaphore 必须已 signaled 或可被 timeline 满足。[SPEC]
- `VUID-vkQueuePresentKHR-pWaitSemaphores-03267`：present wait semaphore 必须有效。[SPEC]
- `VUID-vkResetFences-pFences-01122`：reset 前 fence 必须不在 pending submit 中。[SPEC]
- `VUID-vkSignalSemaphore-value-03258`：timeline semaphore signal value 必须大于当前值。[SPEC]

### RenderDoc / AGI

- RenderDoc 可查看 submit 中 wait/signal 的 semaphore 与 fence 关系。[TOOL]
- AGI 可分析帧内 acquire / render / present 的 GPU 阶段时序，发现气泡或同步错误。[TOOL]

### 日志 / 代码检查

- 检查 `vkAcquireNextImageKHR` 返回值与 acquire semaphore 的配对。
- 检查 per-frame fence 是否每帧 reset / wait。
- 检查 timeline semaphore 的 value 是否单调递增。

---

## 9. 生命周期风险

### 创建时机

- Fence 与 semaphore 在初始化阶段创建，按最大 in-flight frame 数量预分配 per-frame fence。[ENGINE]
- Timeline semaphore 通常全局创建 1~2 个，用于跨队列/跨帧计数。[ENGINE]

### 使用时机

- Fence：submit 时传入，CPU 在需要同步点等待。[SPEC]
- Binary semaphore：acquire / render / present 链中传递 GPU 执行顺序。[SPEC]
- Timeline semaphore：submit 或 CPU 侧 signal，指定单调递增 value。[SPEC]

### 销毁时机

- 确认设备 idle 或相关 queue 完成后再销毁。[SPEC]
- Timeline semaphore 被多个 queue 引用时，需确保所有 wait 已完成。[SPEC]

### in-flight 风险

- Fence 被 pending submit 引用时，reset / destroy 均属非法。[SPEC]
- Binary semaphore 处于 signaled 但未 wait 状态时，再次 signal 非法。[SPEC]
- 销毁 semaphore 前必须确认没有 pending submit 或 present 在等它。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Fence 是 CPU 等待 GPU 的标准方式；`vkWaitForFences` 会阻塞 CPU，适合帧尾资源回收。[SPEC]
- Timeline semaphore 也支持 CPU 等待（`vkWaitSemaphores`），且可以非阻塞查询进度，适合细粒度调度。[SPEC]

### GPU-GPU 同步

- Binary semaphore 只能用于 GPU 内部顺序控制，不能用于 CPU 等待。[SPEC]
- Timeline semaphore 同时支持 GPU-GPU 与 CPU-GPU 同步。[SPEC]
- 跨 queue 依赖应使用 semaphore，而不是 pipeline barrier。[SPEC]

### 资源访问同步

- Fence 只标记 command buffer 执行完成，不保证 resource layout / visibility；layout transition 仍需 barrier。[SPEC]
- Semaphore 保证阶段顺序，但不代替 memory barrier；barrier 的 stage/access 仍需正确设置。[SPEC]

---

## 11. Android 注意点

- Android 上 `vkQueuePresentKHR` 必须等待 render complete semaphore，否则 presentation engine 行为未定义。[ANDROID][SPEC]
- Surface 重建（`VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`）时，fence 与 semaphore 本身通常无需重建，但需确认旧 swapchain image 已不再被 GPU 使用。[ANDROID]
- 移动端 CPU 等待 fence 时间过长会降低帧率；建议结合 triple buffering 与 timeline semaphore 降低 CPU 阻塞。[ENGINE][ANDROID]
- AGI 可捕获 frame 的 acquire / submit / present 同步事件，验证 semaphore 时序。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 每帧 `vkWaitForFences` 后 `vkResetFences` 是常见模式；CPU 等待时间应小于一帧预算。[ENGINE]
- Timeline semaphore 的 `vkWaitSemaphores` 可用于非阻塞轮询，减少 CPU 阻塞。[ENGINE]

### GPU 侧

- Semaphore 的 wait stage 越宽，GPU 并行度越低；尽量精确到 `COLOR_ATTACHMENT_OUTPUT_BIT` / `FRAGMENT_SHADER_BIT` 等实际阶段。[HEUR]
- 不必要的 fence 会引入 CPU-GPU 串行点；仅在必须回收资源时使用。[HEUR]

### 移动端

- Tile-based GPU 对 present 与 render 之间的同步敏感；避免在 submit 与 present 之间插入额外 CPU 等待。[ENGINE][ANDROID]
- Triple buffering 可提高并行度，但会增加 latency；需按项目目标选择 double/triple buffering。[HEUR]

---

## 13. 专家经验

**经验**：
把 fence 当作“CPU 回收资源的门票”，把 binary semaphore 当作“GPU 阶段之间的接力棒”，把 timeline semaphore 当作“跨帧/跨队列的计数器”。最稳的默认组合是：acquire semaphore（binary）+ render complete semaphore（binary）+ per-frame fence。当项目需要跨 queue 数据流、async compute、或 GPU-driven 渲染时，再用 timeline semaphore 替代 fence 做调度。

**适用条件**：
多帧 in-flight、present 链、CPU 需要知道何时复用资源、GPU 需要阶段顺序保证。

**不适用情况**：
同一条 queue 内 producer-consumer 资源可见性（用 pipeline barrier / event）；需要精确资源 layout transition（用 image memory barrier）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`
- `../08_synchronization/synchronization2.md`
- `queue_submit.md`
- `command_buffer_lifetime.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. Timeline semaphore 的具体 counter 操作规则与 feature 启用条件。
2. Binary semaphore 在 `vkAcquireNextImageKHR` / `vkQueueSubmit` / `vkQueuePresentKHR` 中的所有权与信号规则。
3. `vkQueueSubmit2` / `VK_KHR_synchronization2` 中 semaphore stage mask 的扩展语义。
4. 不同平台 presentation engine 对 semaphore 的特殊要求。
5. Fence 在 `vkDeviceWaitIdle` / `vkQueueWaitIdle` 下的行为与状态迁移。

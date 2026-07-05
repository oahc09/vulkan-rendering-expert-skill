# API Card: VkFence

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkFence` |
| 常用 API | `vkCreateFence` / `vkDestroyFence` / `vkResetFences` / `vkWaitForFences` / `vkGetFenceStatus` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkFence` 是 CPU 侧等待 GPU 完成已提交命令的同步原语，通常与 `vkQueueSubmit` 配对，用于在 CPU 上确认一帧或一次提交已执行完毕，从而安全复用资源或继续录制下一批命令。[SPEC]

---

## 2. 所属对象链路

```text
Command Buffer 录制完成
→ vkQueueSubmit (pFence = VkFence)
→ GPU 执行
→ Fence 被 signal
→ CPU 通过 vkWaitForFences / vkGetFenceStatus 探测
→ 复用 command buffer / buffer / image / descriptor set
→ vkResetFences 后进入下一轮
```

### 上游依赖

- 已创建的 `VkDevice` 和至少一个 `VkQueue`。[SPEC]
- 需要等待完成的 command buffer 已提交到 queue。[SPEC]

### 下游影响

- Fence signal 后，CPU 可回收该次提交引用的 in-flight 资源。[SPEC]
- Fence 状态决定下一帧是否可以复用 per-frame 资源池。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkFence`
- `VkFenceCreateInfo`
- `VkFenceCreateFlags`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateFence` | 创建 fence，可指定初始状态为 signaled。[SPEC] |
| `vkDestroyFence` | 销毁 fence；必须确保 GPU 不再使用且未被等待。[SPEC] |
| `vkResetFences` | 批量将 fence 置为 unsignaled；必须在 CPU 确认已 signal 后执行。[SPEC] |
| `vkWaitForFences` | CPU 阻塞等待一个或多个 fence 变为 signaled，可设超时。[SPEC] |
| `vkGetFenceStatus` | 非阻塞查询 fence 状态。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- Android 可用；无特殊平台扩展要求。[ANDROID]

---

## 4. 标准使用流程

```text
创建 signaled fence（可选 VK_FENCE_CREATE_SIGNALED_BIT）
→ 录制 command buffer
→ vkQueueSubmit(cmd, fence = unsignaled fence)
→ CPU 继续处理或调用 vkWaitForFences
→ fence signal 后，回收 command buffer / 资源
→ vkResetFences 重置为 unsignaled
→ 重新录制并提交
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `flags`（`VK_FENCE_CREATE_SIGNALED_BIT`） | 控制初始状态；per-frame fence 常初始为 signaled，避免第一帧等待特殊处理。[ENGINE] | 未设置 signaled bit 却在未提交前调用 `vkWaitForFences` 导致死锁。[TOOL] |
| `fenceCount`（`vkResetFences` / `vkWaitForFences`） | 可批量处理；注意数组中每个 fence 必须处于合法状态。[SPEC] | 对未 signal 的 fence 调用 `vkResetFences` 引发 validation error。[TOOL] |
| `waitAll`（`vkWaitForFences`） | `VK_TRUE` 等待全部；`VK_FALSE` 等待任意一个。[SPEC] | 需要等待全部完成却误设为 `VK_FALSE` 导致资源回收时机错误。[ENGINE] |
| `timeout`（`vkWaitForFences`） | 单位为纳秒；`UINT64_MAX` 为无限等待。[SPEC] | 超时时间过短在低端设备触发 `VK_TIMEOUT`，却未处理该返回值。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 初始状态是否匹配首次使用路径？
- [ ] 是否检查 `vkCreateFence` 返回值？

### 使用阶段

- [ ] `vkQueueSubmit` 是否正确传入 fence handle？
- [ ] 等待前是否确认 fence 已被提交？
- [ ] `vkWaitForFences` 是否处理了 `VK_TIMEOUT`？
- [ ] 批量 reset 前是否确认所有目标 fence 已 signal？

### 销毁阶段

- [ ] 是否等待 GPU 完成？
- [ ] 是否有其他线程正在 `vkWaitForFences` 上等待？

---

## 7. 高频错误

1. 对同一次提交同时使用 fence 和 semaphore，但 CPU 侧未等待 fence 就复用资源。[SPEC]
2. `vkResetFences` 在 fence 尚未 signal 时调用，或重置了仍被 `vkQueueSubmit` 引用的 fence。[TOOL]
3. 生产环境使用 `UINT64_MAX` 无限等待，导致 GPU 挂起时 CPU 同步卡死。[ENGINE]
4. 每帧创建/销毁 fence 而不是复用 per-frame fence pool。[ENGINE]
5. 多线程下不同线程同时操作同一个 fence 状态而未加锁。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkResetFences-pFences-01122`：reset 时 fence 不能处于未 signal 的 pending 状态。
- `VUID-vkDestroyFence-fence-01120`：销毁时 fence 不能仍被 pending queue 使用。
- `VUID-vkWaitForFences-fence-03283` 等：fence 必须有效且状态正确。

### RenderDoc / AGI

- 无法直接查看 fence 信号时机，但可通过 frame marker 和 queue submission 时间戳推断等待是否合理。[TOOL]
- AGI 可观察 CPU 等待点是否成为瓶颈。[TOOL]

### 日志 / 代码检查

- 检查 `vkWaitForFences` 返回值是否为 `VK_SUCCESS` 或 `VK_TIMEOUT`。
- 检查 reset 操作是否在 wait 成功后执行。
- 检查 per-frame fence 索引循环逻辑。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建 per-frame fence 池。[ENGINE]

### 使用时机

- 提交 command buffer 时传入；CPU 在需要同步点等待。[SPEC]

### 销毁时机

- 设备销毁前统一销毁；或资源池缩容时确认 fence 不再使用。[SPEC]

### in-flight 风险

- Fence 被 `vkQueueSubmit` 引用后，在其 signal 前不可 reset 或销毁。[SPEC]
- 即使 fence 已 signal，也要确保没有线程仍在等待它再销毁。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- `VkFence` 是 CPU-GPU 同步的主要手段；CPU 通过它判断 GPU 是否完成。[SPEC]

### GPU-GPU 同步

- Fence 不直接参与 GPU-GPU 同步；同一条 queue 内的依赖应使用 pipeline barrier / subpass dependency / event。[SPEC]

### 资源访问同步

- Fence signal 仅保证提交到 queue 的命令已执行完毕，不保证跨 queue 或跨设备的访问顺序；跨 queue 仍需 semaphore。[SPEC]

---

## 11. Android 注意点

- Android 上 `vkWaitForFences` 的合理超时值尤为重要；部分 GPU 在 thermal/power 限制下帧时间波动大，过短超时易导致 `VK_TIMEOUT`。[ANDROID]
- 横竖屏切换或应用 pause/resume 后，per-frame fence 池应随 swapchain recreate 重新对齐，避免旧 fence 状态与新的 frame index 错位。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 每帧 `vkCreateFence` / `vkDestroyFence` 开销明显；应使用固定大小的 per-frame fence 数组复用。[ENGINE]
- 频繁 `vkWaitForFences(timeout=0)` 轮询会浪费 CPU 周期；优先使用带合理超时或事件驱动设计。[HEUR]

### GPU 侧

- Fence 本身不增加 GPU 负载；它仅暴露 completion 信号。[SPEC]

### 移动端

- 移动端 CPU 核数少，`vkWaitForFences` 阻塞主线程会直接影响帧间隔；建议将等待放在独立线程或与渲染线程解耦。[ENGINE][ANDROID]

---

## 13. 专家经验

**经验**：
在 double/triple buffering 框架中，为每个 in-flight frame 维护一个 fence，提交时传入对应 fence，帧循环开始时 wait 该帧的 fence。不要为每次 `vkQueueSubmit` 都新建 fence，也不要在 wait 成功前 reset。

**适用条件**：
典型渲染循环、有 per-frame 资源池、需要 CPU 端知道 GPU 完成时机。

**不适用情况**：
纯 GPU-GPU 同步（应使用 semaphore 或 barrier）；不需要 CPU 感知的异步 compute chain。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `semaphore.md`
- `pipeline_barrier.md`
- `event.md`
- `../03_command_buffer/queue_submit.md`
- `../03_command_buffer/command_buffer_lifetime.md`

---

## 15. 需要回查官方文档的情况

1. `vkWaitForFences` 在 `timeout=0` 且已 signal 时的精确返回值。
2. 多线程并发调用 `vkGetFenceStatus`、`vkWaitForFences`、`vkResetFences` 的线程安全规则。
3. 与 external fence（`VK_KHR_external_fence`）交互时的导入/导出语义。
4. 特定驱动在 `VK_TIMEOUT` 后的恢复行为。

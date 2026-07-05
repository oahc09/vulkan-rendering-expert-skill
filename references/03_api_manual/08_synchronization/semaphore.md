# API Card: VkSemaphore

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkSemaphore` |
| 常用 API | `vkCreateSemaphore` / `vkDestroySemaphore` / `vkQueueSubmit`（signal / wait） / `vkQueuePresentKHR` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0（Binary Semaphore）；Timeline Semaphore 为 `VK_KHR_timeline_semaphore` / Vulkan 1.2 core |

---

## 1. 一句话定位

`VkSemaphore` 是 GPU-GPU 同步原语，用于在 queue submit、swapchain image acquire 与 present 之间建立执行依赖，确保下游队列/提交在 GPU 上可见地等待上游操作完成。[SPEC]

---

## 2. 所属对象链路

```text
上游 GPU 工作（Queue A submit 或 vkAcquireNextImageKHR）
→ Semaphore signal
→ 下游 GPU 工作（Queue B submit 或 vkQueueSubmit 的 wait stage）
→ 消费完成
→ （可选）vkQueuePresentKHR 使用 acquire semaphore
```

### 上游依赖

- 已创建的 `VkDevice` 和至少一个 `VkQueue`。[SPEC]
- 对于 swapchain acquire，需要 `vkAcquireNextImageKHR` 产生的 semaphore。[SPEC]
- Timeline semaphore 需要启用 `VK_KHR_timeline_semaphore` 或 Vulkan 1.2+ 以及 `VkPhysicalDeviceTimelineSemaphoreFeatures`。[SPEC]

### 下游影响

- 决定跨 queue、跨提交或 acquire→submit→present 的执行顺序。[SPEC]
- 错误使用会导致 GPU 并行执行本应先后的工作，引发 image layout / resource hazard。[TOOL]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSemaphore`
- `VkSemaphoreCreateInfo`
- `VkSemaphoreTypeCreateInfo`（Timeline Semaphore）
- `VkTimelineSemaphoreSubmitInfo`（submit 时指定 value）
- `VkSemaphoreSignalInfo`（`vkSignalSemaphore`）
- `VkSemaphoreWaitInfo`（`vkWaitSemaphores`）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateSemaphore` | 创建 binary 或 timeline semaphore。[SPEC] |
| `vkDestroySemaphore` | 销毁 semaphore；必须确保 GPU 不再使用。[SPEC] |
| `vkQueueSubmit` / `vkQueueSubmit2` | `pSignalSemaphores` / `pWaitSemaphores` 用于 GPU-GPU 同步。[SPEC] |
| `vkAcquireNextImageKHR` | 输出 acquire semaphore，标记 image 可被使用。[SPEC] |
| `vkQueuePresentKHR` | 使用 present semaphore 等待渲染完成后再上屏。[SPEC] |
| `vkSignalSemaphore` | CPU 侧直接 signal timeline semaphore 到指定 value。[SPEC] |
| `vkWaitSemaphores` | CPU 侧等待 timeline semaphore 达到指定 value。[SPEC] |
| `vkGetSemaphoreCounterValue` | 查询 timeline semaphore 当前 counter value。[SPEC] |

### 相关扩展 / 版本

- Binary semaphore：Vulkan 1.0 核心。
- Timeline semaphore：`VK_KHR_timeline_semaphore`（Vulkan 1.2 core）。[SPEC]
- Android 可用；timeline semaphore 需确认设备支持。[ANDROID]

---

## 4. 标准使用流程

### Binary Semaphore

```text
创建 binary semaphore
→ vkAcquireNextImageKHR(..., acquireSemaphore)
→ vkQueueSubmit(..., pWaitSemaphores = [acquireSemaphore], ..., pSignalSemaphores = [renderCompleteSemaphore])
→ vkQueuePresentKHR(..., pWaitSemaphores = [renderCompleteSemaphore])
```

### Timeline Semaphore

```text
启用 timelineSemaphore feature
→ 创建 VkSemaphoreType = TIMELINE 的 semaphore
→ submit 时通过 VkTimelineSemaphoreSubmitInfo 指定 signal/wait value
→ 下游 submit 等待更高 value
→ （可选）CPU 通过 vkWaitSemaphores 等待指定 value
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `semaphoreType` | `VK_SEMAPHORE_TYPE_BINARY` 或 `VK_SEMAPHORE_TYPE_TIMELINE`；创建后不可更改。[SPEC] | 把 binary semaphore 当 timeline 使用，或未启用 feature 就创建 timeline。[TOOL] |
| `initialValue` | Timeline semaphore 的初始 counter value。[SPEC] | 假设初始值为 0 但实际传入非 0，导致 wait 判断错误。[TOOL] |
| `pWaitDstStageMask` / `pWaitSemaphoreValues` | 控制等待 semaphore 时阻塞的 pipeline stage；timeline 需与 value 数组对齐。[SPEC] | Stage mask 设为 `TOP_OF_PIPE_BIT` 导致过早或不必要的阻塞；或 value 数组顺序与 semaphore 数组不匹配。[TOOL] |
| `signalValue` | Timeline submit 时递增的 value；必须单调递增。[SPEC] | 重复 signal 同一 value 或 value 回退。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否需要 timeline semaphore？是否启用了 feature / extension？
- [ ] Binary semaphore 是否仅用于单次 signal→wait 周期？
- [ ] Timeline semaphore 的初始 value 是否与后续 signal/wait 逻辑一致？

### 使用阶段

- [ ] Acquire semaphore 是否在 submit 前未被 signal 其他用途？
- [ ] Present semaphore 是否确实在渲染完成后 signal？
- [ ] Timeline semaphore 的 wait value 是否 ≤ 已 signal 的 value？
- [ ] 跨 queue 依赖是否使用了 semaphore 而不是 fence？

### 销毁阶段

- [ ] 是否确认 semaphore 不在任何 pending submit 中？
- [ ] Acquire semaphore 是否未在 image 仍被 GPU 使用时销毁？

---

## 7. 高频错误

1. 同一个 binary semaphore 在一次 acquire→submit→present 周期中被 signal 多次或等待多次。[TOOL]
2. Acquire semaphore 和 present semaphore 混用或顺序写反。[TOOL]
3. Timeline semaphore 的 value 未单调递增，或 wait value 超过最新 signal value。[TOOL]
4. 在 CPU 侧使用 binary semaphore 做同步（binary semaphore 无 CPU wait API）。[SPEC]
5. 销毁仍被 pending submit 引用的 semaphore。[TOOL]
6. 跨 queue 同步使用 fence 而不是 semaphore。[ENGINE]
7. 未启用 `timelineSemaphore` feature 却创建 timeline semaphore。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkQueueSubmit-pWaitSemaphores-00068`：wait semaphore 必须已被 signal 或处于 pending signal 状态。
- `VUID-vkQueuePresentKHR-pWaitSemaphores-03267`：present 等待的 semaphore 必须有效。
- `VUID-vkAcquireNextImageKHR-semaphore-01782`：acquire semaphore 必须 unsignaled。
- Timeline semaphore 相关 VUID：`VUID-VkSemaphoreTypeCreateInfo-semaphoreType-03279` 等。

### RenderDoc / AGI

- RenderDoc 可展示每次 submit 的 signal/wait semaphore 列表及 stage mask。[TOOL]
- AGI 可观察 timeline semaphore 的 counter 变化及跨 queue 依赖关系。[TOOL]

### 日志 / 代码检查

- 检查 `vkAcquireNextImageKHR`、`vkQueueSubmit`、`vkQueuePresentKHR` 的 semaphore 参数是否一一对应。
- 检查 timeline semaphore 的 value 是否严格递增。
- 检查 swapchain recreate 后旧的 acquire semaphore 是否仍被错误引用。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建 swapchain 相关的 acquire / render-complete semaphore 池。[ENGINE]
- Timeline semaphore 可作为全局计数器在初始化时创建。[ENGINE]

### 使用时机

- Swapchain acquire、queue submit signal/wait、present 等待。[SPEC]

### 销毁时机

- 设备销毁前；swapchain recreate 时如果 semaphore 池策略变化可销毁重建。[SPEC]

### in-flight 风险

- Binary semaphore 被 submit 引用后，在对应 signal 完成且被消费前不能复用或销毁。[SPEC]
- Timeline semaphore 的 value 被 wait 引用后，在 wait 完成前不能 reset 或销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Binary semaphore 不支持 CPU 等待；需要 CPU 感知完成时应使用 fence 或 timeline semaphore 的 `vkWaitSemaphores`。[SPEC]

### GPU-GPU 同步

- Semaphore 是跨 queue、跨 submit 的主要 GPU-GPU 同步手段。[SPEC]
- 同一条 queue 内的依赖通常用 pipeline barrier 更高效。[ENGINE]

### 资源访问同步

- Semaphore 保证执行顺序，但不保证 memory availability / visibility；跨 queue 资源访问仍需正确的 pipeline stage mask 和 access mask（或在 synchronization2 中使用 `VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT` 等语义）。[SPEC]

---

## 11. Android 注意点

- Android 上 swapchain acquire / present 的 semaphore 使用与 desktop 一致，但需特别处理 `VK_SUBOPTIMAL_KHR` / `VK_ERROR_OUT_OF_DATE_KHR` 后的 semaphore 池重建。[ANDROID]
- 部分 Android 设备对 timeline semaphore 支持情况需运行时查询；旧 Mali/Adreno 驱动可能仅支持 Vulkan 1.1 而不支持 1.2。[ANDROID]
- AGI 在 Android 上可捕获 timeline semaphore 的跨帧依赖，是诊断卡顿的有力工具。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 每帧创建/销毁 binary semaphore 开销明显；应使用 per-frame 复用池。[ENGINE]
- Timeline semaphore 可减少 semaphore 对象数量，但 CPU 端 wait 仍可能阻塞渲染线程。[ENGINE]

### GPU 侧

- Semaphore 本身不增加 GPU workload，但错误的 stage mask 会导致 pipeline 气泡。[HEUR]
- 同 queue 内过度使用 semaphore 替代 barrier 会增加提交复杂度。[ENGINE]

### 移动端

- 移动端 GPU 对跨 queue 同步敏感；尽量减少独立 compute/graphics queue 间的频繁同步。[ENGINE][ANDROID]
- Swapchain acquire semaphore 的等待 stage 设为 `COLOR_ATTACHMENT_OUTPUT_BIT` 即可，避免 `ALL_COMMANDS_BIT` 造成不必要阻塞。[HEUR]

---

## 13. 专家经验

**经验**：
优先使用 timeline semaphore 替代 per-frame binary semaphore 数组管理跨帧/跨队列依赖；通过单调递增的 counter value 可以精确表达“第 N 帧完成”、“第 M 次 compute dispatch 完成”等语义，简化资源生命周期管理。但 swapchain acquire/present 通常仍使用 binary semaphore，因为 WSI 规范要求如此。

**适用条件**：
多 in-flight frame、跨 graphics/compute queue、需要精确事件计数的长异步任务链。

**不适用情况**：
简单单 queue 渲染器；目标设备不支持 Vulkan 1.2 且未启用 `VK_KHR_timeline_semaphore`；swapchain acquire/present 阶段仍需 binary semaphore。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `fence.md`
- `pipeline_barrier.md`
- `event.md`
- `synchronization2.md`
- `../02_surface_swapchain/swapchain.md`
- `../03_command_buffer/queue_submit.md`

---

## 15. 需要回查官方文档的情况

1. Timeline semaphore 与 binary semaphore 在 `vkQueueSubmit2` / `VkSubmitInfo2` 中的混合使用规则。
2. `vkAcquireNextImageKHR` 返回 `VK_SUBOPTIMAL_KHR` 时 acquire semaphore 的合法状态。
3. 跨 queue 使用 semaphore 时，wait stage mask 与 consumer pipeline stage 的精确匹配。
4. Timeline semaphore 与 external semaphore（`VK_KHR_external_semaphore`）的交互。
5. Android WSI 对 semaphore 的特殊限制或扩展行为。

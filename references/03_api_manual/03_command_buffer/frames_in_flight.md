# API Card: Frames in Flight 资源模型

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 |
| Vulkan 对象 | Frames in Flight 资源模型 |
| 常用 API | `vkAcquireNextImageKHR` / `vkQueueSubmit` / `vkWaitForFences` / `vkResetFences` / `vkResetCommandBuffer` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE] [ANDROID]` |
| 适用 Vulkan 版本 | Vulkan 1.0 核心 |

---

## 1. 一句话定位

Frames in Flight 是一种"CPU 录制第 N+1 帧时 GPU 仍在执行第 N 帧"的并发资源模型：通过为每个 in-flight slot 复制一份被 GPU 引用的资源（command buffer / fence / semaphore / uniform buffer 等），用 fence 追踪每帧完成时机，避免 CPU 在录制时覆盖 GPU 仍在读取的数据。[SPEC][ENGINE]

---

## 2. 所属对象链路

```text
初始化阶段:
  按 MAX_FRAMES_IN_FLIGHT（通常 2）创建 per-frame:
    VkCommandPool / VkCommandBuffer
    VkFence（创建时 SIGNALED）
    VkSemaphore × 2（acquire / render complete）
    per-frame uniform buffer / descriptor set / staging buffer

每帧循环 (currentFrame = (currentFrame + 1) % MAX_FRAMES_IN_FLIGHT):
  vkWaitForFences(frameFence[currentFrame])        // 等待最老帧完成
  vkResetFences(frameFence[currentFrame])
  vkAcquireNextImageKHR(acquireSemaphore[currentFrame], &imageIndex)
  vkResetCommandBuffer(cmd[currentFrame]) 或 vkResetCommandPool(pool[currentFrame])
  vkBeginCommandBuffer → 录制 → vkEndCommandBuffer
  更新 uniform buffer[currentFrame]                // 仅在 fence signaled 后写入
  vkQueueSubmit(
      wait   = acquireSemaphore[currentFrame],
      signal = renderCompleteSemaphore[currentFrame],
      fence  = frameFence[currentFrame])
  vkQueuePresentKHR(wait = renderCompleteSemaphore[currentFrame])
```

### 上游依赖

- `VkDevice` / `VkQueue` / `VkSwapchainKHR` 已创建并处于可用状态。[SPEC]
- `MAX_FRAMES_IN_FLIGHT` 数量已确定（典型值 2，triple buffering 时为 3）。[ENGINE]
- 工程建议 `minImageCount` ≥ `MAX_FRAMES_IN_FLIGHT` 以降低 acquire 阻塞概率；并非规范硬规则，规范只要求 `minImageCount` 落在 `VkSurfaceCapabilitiesKHR` 的 [minImageCount, maxImageCount] 区间内。[SPEC][ENGINE]

### 下游影响

- 每帧被 GPU 写入的资源（command buffer、per-frame uniform、staging buffer 等）通常按 frame-in-flight slot 各持一份以避免数据竞争；这是常见实现策略，**不是规范硬规则** —— 也可采用 ring buffer + 动态 offset、不可变共享资源、suballoated chunk 等方案，只要同步关系正确即可。[SPEC][ENGINE]
- Fence 数组决定 CPU 回收资源的门票，错位会导致 reset 被使用中的 command buffer。[SPEC]
- Swapchain recreate 时必须等待所有 in-flight frame 完成才能销毁旧 swapchain 资源。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkFence`（per-frame，创建时 `VK_FENCE_CREATE_SIGNALED_BIT`）
- `VkSemaphore`（per-frame acquire + per-frame render complete）
- `VkCommandBuffer` / `VkCommandPool`（per-frame）
- `VkBuffer`（per-frame uniform / staging）
- `VkDescriptorSet`（per-frame，从 per-frame pool 分配）

### 常用 API

| API | 作用 |
|---|---|
| `vkAcquireNextImageKHR` | 获取下一个 swapchain image index；传入 per-frame acquire semaphore。[SPEC] |
| `vkQueueSubmit` | 提交本帧 command buffer；绑定 per-frame wait/signal semaphore 与 fence。[SPEC] |
| `vkQueueSubmit2` | `VK_KHR_synchronization2` 版本，支持 `VkSubmitInfo2` 更细粒度同步。[SPEC] |
| `vkWaitForFences` | CPU 阻塞等待 frame-in-flight fence signaled，确认最老帧 GPU 完成。[SPEC] |
| `vkResetFences` | fence signaled 后重置为 unsignaled，准备下一轮 submit。[SPEC] |
| `vkResetCommandBuffer` | 释放并复用 per-frame command buffer 的录制内容。[SPEC] |
| `vkResetCommandPool` | 整池重置，比逐个 reset 更高效。[ENGINE] |
| `vkQueuePresentKHR` | 提交 present，wait 当帧的 render complete semaphore。[SPEC] |

### 相关扩展 / 版本

- Frames in Flight 模型本身为 Vulkan 1.0 核心工程实践，非 API 扩展。[SPEC]
- `VK_KHR_timeline_semaphore`（Vulkan 1.2 核心）：可使用单 timeline semaphore + 单调递增 value 替代 per-frame binary semaphore + fence 数组。[SPEC]
- `VK_KHR_synchronization2`（Vulkan 1.3 核心）：`VkSubmitInfo2` 简化 wait/signal stage 配置。[SPEC]
- Mailbox / FIFO present mode 与 frame-in-flight 数量决定 latency 与 throughput 平衡。[SPEC]

---

## 4. 标准使用流程

### 4.1 双缓冲 (MAX_FRAMES_IN_FLIGHT = 2) 标准流程

```text
Init:
  for i in 0..2:
    create fence[i] with VK_FENCE_CREATE_SIGNALED_BIT  // 首次 wait 不阻塞
    create acquireSemaphore[i], renderCompleteSemaphore[i]
    allocate commandPool[i] (RESET_COMMAND_BUFFER_BIT)
    allocate commandBuffer[i]
    allocate uniformBuffer[i] (HOST_VISIBLE | HOST_COHERENT)
    allocate descriptorPool[i], descriptorSet[i]

Frame loop (currentFrame 指针轮转):
  1. vkWaitForFences(fence[currentFrame])            // 等最老帧完成
  2. vkResetFences(fence[currentFrame])
  3. vkAcquireNextImageKHR(swapchain, ..., acquireSemaphore[currentFrame], &imageIndex)
  4. vkResetCommandPool(commandPool[currentFrame])   // 或 vkResetCommandBuffer
  5. vkBeginCommandBuffer / 录制 / vkEndCommandBuffer
  6. memcpy 到 uniformBuffer[currentFrame].mapped     // fence 已 signal，写入安全
  7. vkQueueSubmit(
        waitSemaphore   = acquireSemaphore[currentFrame],
        waitDstStage    = COLOR_ATTACHMENT_OUTPUT_BIT,
        signalSemaphore = renderCompleteSemaphore[currentFrame],
        fence           = fence[currentFrame])
  8. vkQueuePresentKHR(wait = renderCompleteSemaphore[currentFrame])
  9. currentFrame = (currentFrame + 1) % 2
```

### 4.2 Timeline Semaphore 简化方案

```text
单 timeline semaphore，初始 value = 0
每帧 submit 时 signal value = frameID + 1
CPU 调度下一帧前 vkWaitSemaphores(waitValue = frameID - MAX_FRAMES_IN_FLIGHT + 1)
swapchain image index 与 timeline value 共同决定 per-frame 资源 slot
```

### 4.3 Swapchain recreate 流程

```text
vkDeviceWaitIdle()   // 或对所有 in-flight fence 调 vkWaitForFences
清理 swapchain-size 资源（framebuffer、image view、depth image 等）
vkDestroySwapchainKHR
重新创建 swapchain + image view + framebuffer
保留 per-frame fence / semaphore / command buffer / uniform buffer
注意：acquire semaphore 若在 acquire 失败后仍处于 unsignaled 状态，需替换或重建
```

---

## 5. 关键字段

### Fence 配置

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `flags`（create） | 推荐使用 `VK_FENCE_CREATE_SIGNALED_BIT` 让 fence 创建即为 signaled 状态，避免首次 `vkWaitForFences` 死锁；这是工程常用做法，**不是规范硬规则** —— 也可创建为 unsignaled 并通过首次 submit 前不 wait 的逻辑规避。[SPEC][ENGINE] | 创建时未 signaled 且首次逻辑直接 wait 导致永远等不到。[TOOL] |
| `pFences`（wait/reset） | 按 `currentFrame` 索引严格配对，不要跨帧使用同一 fence。[SPEC] | 共用 fence 导致无法判断哪一帧完成。[ENGINE] |
| `timeout` | 推荐 1s 级别，便于发现 GPU hang；调试期可缩短到 100ms。[ENGINE] | `UINT64_MAX` 让 GPU hang 永久阻塞 CPU。[TOOL] |
| `waitAll` | 单 fence 等待时无差别；多 fence 等待时按需求选择。[SPEC] | 误用 `waitAll=VK_TRUE` 等所有 fence，降低并行度。[HEUR] |

### Semaphore 配对

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `acquireSemaphore[currentFrame]` | 由 `vkAcquireNextImageKHR` signal，submit 中 wait。[SPEC] | acquire 返回 `VK_SUBOPTIMAL_KHR` / `OUT_OF_DATE_KHR` 后仍 submit 旧 semaphore，导致 wait 永远不满足。[ENGINE] |
| `renderCompleteSemaphore[currentFrame]` | submit signal，present wait。[SPEC] | 同一 binary semaphore 跨多 submit signal，违反一一对应。[SPEC] |
| `pWaitDstStageMask` | 推荐 `COLOR_ATTACHMENT_OUTPUT_BIT`，让 acquire 不阻塞整条流水线。[SPEC] | 用 `TOP_OF_PIPE` / `ALL_COMMANDS` 造成不必要停顿。[HEUR] |

### Command Buffer / Pool

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| per-frame `VkCommandPool` | 推荐 per-frame pool，每帧 `vkResetCommandPool` 比逐个 reset 高效。[ENGINE] | 全局单 pool 在多帧并发下 reset 危险。[ENGINE] |
| `vkResetCommandBuffer` 时机 | 必须在 `vkWaitForFences` 之后调用。[SPEC] | 未等 fence 就 reset，触发 `VUID-vkResetCommandBuffer-commandBuffer-00045`。[TOOL] |

### Uniform Buffer

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| per-frame `VkBuffer` | 工程上常见做法是为每个 in-flight slot 分配独立 uniform buffer；**不是规范硬规则** —— 也可使用单个大 buffer + per-frame 动态 offset（`vkCmdBindDescriptorSets` 的 `pDynamicOffsets`）或 ring buffer suballocation，只要同一 GPU 访问区间不被 CPU 并发覆盖即可。[SPEC][ENGINE] | 单 buffer 且无动态 offset 直接跨帧写入，导致 GPU 读到半成品数据。[TOOL] |
| 写入时机 | 必须在 `vkWaitForFences` 返回后写入。[SPEC] | 录制阶段先写入再 wait，可能覆盖 GPU 仍在读的数据。[ENGINE] |
| 内存 property | 推荐 `HOST_VISIBLE | HOST_COHERENT`；移动端大 buffer 可评估 `HOST_VISIBLE | DEVICE_LOCAL` 取舍。[ENGINE] | 用 `DEVICE_LOCAL` 但 CPU 仍 map，导致失败。[TOOL] |

---

## 6. 正确性检查点

### 资源复制策略

- [ ] 每个 in-flight slot 是否拥有独立的 command buffer / command pool？[ENGINE]
- [ ] 每个 slot 是否拥有独立的 fence（创建时 signaled）？[SPEC]
- [ ] 每个 slot 是否拥有独立的 acquire / render complete semaphore？[SPEC]
- [ ] 每个 slot 是否拥有独立的 uniform buffer / descriptor set / staging buffer？[SPEC]
- [ ] descriptor pool 是否 per-frame（避免跨帧 descriptor 写入冲突）？[ENGINE]

### Fence 追踪

- [ ] `vkWaitForFences` 是否在 `vkAcquireNextImageKHR` 之前调用？[ENGINE]
- [ ] `vkResetFences` 是否在 wait 成功后调用？[SPEC]
- [ ] Fence 是否严格按 `currentFrame` 索引配对，未跨帧共用？[ENGINE]
- [ ] Fence 创建时是否设置了 `SIGNALED_BIT`？[SPEC]

### Semaphore 配对

- [ ] acquire / render complete semaphore 是否按 per-frame 配对，未跨帧复用？[SPEC]
- [ ] Binary semaphore 是否在 wait 前已 signal？[SPEC]
- [ ] present wait semaphore 是否是本帧的 render complete semaphore？[SPEC]
- [ ] submit 的 wait stage 是否精确（如 `COLOR_ATTACHMENT_OUTPUT_BIT`）？[HEUR]

### Swapchain image index 关系

- [ ] `imageIndex`（swapchain 返回）与 `currentFrame`（in-flight slot）是否分开管理？[SPEC]
- [ ] 是否处理 `vkAcquireNextImageKHR` 返回 `VK_SUBOPTIMAL_KHR` / `OUT_OF_DATE_KHR`？[SPEC]
- [ ] swapchain recreate 时是否等待所有 in-flight fence signaled？[ENGINE]

### 资源更新时机

- [ ] uniform buffer 写入是否在 `vkWaitForFences` 之后？[SPEC]
- [ ] descriptor 更新是否在 fence signal 后，避免被 GPU 引用时改写？[SPEC]
- [ ] staging buffer 是否 per-frame 分配，避免覆盖未完成帧的数据？[ENGINE]

---

## 7. 高频错误

1. 单 fence / 单 semaphore 跨多帧共用，CPU 无法判断哪一帧完成。[ENGINE]
2. Fence 创建时未设 `SIGNALED_BIT`，首次 `vkWaitForFences` 永久阻塞。[TOOL]
3. 未 `vkWaitForFences` 就 `vkResetCommandBuffer`，触发 validation error 或 crash。[SPEC]
4. Uniform buffer 单实例跨帧写入，GPU 读到部分更新的数据导致抖动。[TOOL]
5. `imageIndex` 与 `currentFrame` 混用，导致资源 slot 错位。[ENGINE]
6. Swapchain recreate 时未等所有 in-flight frame，引用了已销毁的 swapchain image。[ENGINE]
7. Acquire 失败（`OUT_OF_DATE_KHR`）后仍 submit 旧 acquire semaphore，wait 永不满足。[SPEC]
8. Present wait semaphore 与本帧 render complete 不匹配，导致撕裂或 validation error。[TOOL]
9. `MAX_FRAMES_IN_FLIGHT` > swapchain `minImageCount`，acquire 频繁阻塞。[SPEC]
10. Timeline semaphore value 不单调递增，或 CPU/GPU 两侧计算不同步。[TOOL]
11. Android 切后台返回后未处理 unsignaled fence，导致后续 wait 死锁。[ANDROID]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkResetCommandBuffer-commandBuffer-00045`：command buffer 不能处于 PENDING 状态（说明 fence 未 wait）。[SPEC]
- `VUID-vkResetFences-pFences-01122`：reset 前 fence 不在 pending submit 中。[SPEC]
- `VUID-vkQueueSubmit-pWaitSemaphores-00068`：wait semaphore 必须 signaled 或 timeline 可满足。[SPEC]
- `VUID-vkQueuePresentKHR-pWaitSemaphores-03267`：present wait semaphore 必须有效。[SPEC]
- `VUID-vkAcquireNextImageKHR-semaphore-01282`：acquire semaphore 不能在 unsignaled 状态被复用。[SPEC]

### RenderDoc / AGI

- RenderDoc 可逐帧查看 submit / wait / signal / fence 的时序关系。[TOOL]
- AGI 可观测 CPU 录制与 GPU 执行的重叠度，发现 CPU 等 fence 的气泡。[TOOL]
- 检查 frame N 录制时是否复用了 frame N-1 仍在 GPU 上的资源。[ENGINE]

### 日志 / 代码检查

- 打印每帧 `currentFrame`、`imageIndex`、`vkWaitForFences` 返回值、`vkAcquireNextImageKHR` 返回值。
- 检查 fence 数组索引是否与 `currentFrame` 严格对应。
- 检查 uniform buffer 写入是否在 `vkWaitForFences` 之后。
- 检查 swapchain recreate 时是否调用了 `vkDeviceWaitIdle` 或对所有 fence `vkWaitForFences`。

---

## 9. 生命周期风险

### 创建时机

- Renderer 初始化时按 `MAX_FRAMES_IN_FLIGHT` 预分配所有 per-frame 资源。[ENGINE]
- Fence 创建时必须 signaled，避免首帧 wait 死锁。[SPEC]
- Swapchain-size 资源（framebuffer、depth image、view）按 swapchain image 数量创建，与 frame-in-flight 数量独立。[SPEC]

### 使用时机

- 每帧循环开始时 `vkWaitForFences` + `vkResetFences`。[SPEC]
- Command buffer reset / begin 必须在 fence signal 后。[SPEC]
- Uniform buffer / descriptor 写入必须在 fence signal 后。[SPEC]

### 销毁时机

- 应用退出、swapchain recreate 时销毁 per-frame 资源。[ENGINE]
- 必须先 `vkDeviceWaitIdle` 或 `vkWaitForFences` 所有 in-flight fence。[SPEC]
- Swapchain recreate 时保留仍有效的 fence / semaphore / command pool，仅重建 swapchain-size 资源。[ENGINE]

### in-flight 风险

- PENDING 状态的 command buffer 引用的所有资源必须保持有效，直到 fence signal。[SPEC]
- Swapchain recreate 时若不等待，旧 swapchain image 可能仍被 in-flight command buffer 引用，导致 `VK_ERROR_NATIVE_WINDOW_IN_USE_KHR`。[ANDROID]
- Acquire semaphore 在 acquire 失败后可能处于 unsignaled 状态，直接复用会触发 validation error；推荐每次 recreate 时新建一组 semaphore 或使用 timeline semaphore。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- Fence 是 CPU 等待 GPU 的标准方式，每帧 submit 配一个 per-frame fence，CPU 在下一轮 slot 复用前 wait。[SPEC]
- `vkDeviceWaitIdle` 是最保守的等待方式，仅用于 swapchain recreate / shutdown，不用于每帧。[SPEC]
- Timeline semaphore 替代方案：单 timeline semaphore + 单调 value 即可表达"等待第 N 帧"语义，无需 fence 数组。[SPEC]

### GPU-GPU 同步

- acquire → render → present 链由 binary semaphore 串联，per-frame 配对。[SPEC]
- Binary semaphore 只能 GPU-GPU 顺序控制，不能用于 CPU wait。[SPEC]
- 跨 queue 资源依赖（如 async compute / transfer queue）应使用 timeline semaphore 或 binary semaphore，而不是 pipeline barrier。[SPEC]

### 资源访问同步

- Fence signal 只表示 command buffer 完成，不保证 resource layout / visibility；layout transition 仍需 barrier。[SPEC]
- Uniform buffer 在 CPU 写入与 GPU 读取之间需通过 fence 隔离，避免读写竞争。[SPEC]
- HOST_COHERENT 内存可省 `vkFlushMappedMemoryRanges` / `vkInvalidateMappedMemoryRanges`，但跨帧写入仍需 fence 同步。[SPEC]

---

## 11. Android 注意点

- Android 上 `vkQueuePresentKHR` 必须等待 render complete semaphore，否则 presentation engine 行为未定义。[ANDROID][SPEC]
- Android Pause / Resume 后，fence 状态可能不稳定：若 pause 期间 GPU 完成，fence 已 signaled；若被强制 reset 或 surface 销毁，需重建 fence 或等待 idle。[ANDROID]
- `APP_CMD_TERM_WINDOW` 后应停止 submit，调 `vkDeviceWaitIdle` 再清理 swapchain 资源，避免 in-flight frame 引用已销毁 surface。[ANDROID]
- Surface 重建（`VK_ERROR_OUT_OF_DATE_KHR`）时，fence 与 semaphore 通常无需重建，但 acquire 失败时 acquire semaphore 处于 unsignaled 状态，需替换或用 timeline semaphore 规避。[ANDROID][ENGINE]
- 移动端 frame-in-flight 推荐 2 帧；triple buffering 提高 CPU 并行度但增加 latency，需按场景权衡。[ENGINE][ANDROID]
- AGI 可捕获 frame 的 acquire / submit / present 同步事件，验证 pause/resume 后 fence 时序是否正常。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- `vkWaitForFences` 应在帧首调用，让 CPU 与 GPU 重叠执行；等待时间应小于一帧预算。[ENGINE]
- `vkResetCommandPool` 比逐个 `vkResetCommandBuffer` 更高效，per-frame pool 推荐采用。[ENGINE]
- Timeline semaphore 可用 `vkGetSemaphoreCounterValue` 非阻塞查询进度，减少 CPU 阻塞。[ENGINE]

### GPU 侧

- `pWaitDstStageMask` 越精确（如 `COLOR_ATTACHMENT_OUTPUT_BIT`），GPU 流水线气泡越小。[HEUR]
- 不必要的 fence wait 会引入 CPU-GPU 串行点；仅在必须回收资源时 wait。[HEUR]
- Swapchain present mode 与 frame-in-flight 数量共同决定 throughput 与 latency。[SPEC]

### 移动端

- Tile-based GPU 对 present 与 render 之间的同步敏感，避免 submit 与 present 之间插入 CPU 等待。[ENGINE][ANDROID]
- Triple buffering 可提高并行度，但增加 latency；交互式应用建议 double buffering + mailbox 或 FIFO。[HEUR]
- 移动端内存紧张时，per-frame uniform buffer 大小应控制，优先 persistent mapped + ring buffer。[ENGINE]

---

## 13. 专家经验

**经验**：
Frames in Flight 模型的本质是"用空间换时间"：把 GPU 仍可能正在读取的资源复制 N 份，让 CPU 录制下一帧时不阻塞。最稳的默认结构是：
- `MAX_FRAMES_IN_FLIGHT = 2`
- per-frame `VkCommandPool` + `VkCommandBuffer`
- per-frame `VkFence`（创建时 SIGNALED）
- per-frame acquire + render complete binary semaphore
- per-frame uniform buffer（persistent mapped）
- `currentFrame` 与 `imageIndex` 分开管理：前者是 in-flight slot，后者是 swapchain image

当项目需要跨 queue 数据流、async compute、GPU-driven 渲染、或简化 fence 数组管理时，再用 timeline semaphore（单实例 + 单调 value）替代 per-frame fence + binary semaphore 数组。Swapchain recreate 时务必先 `vkDeviceWaitIdle` 或 wait 所有 in-flight fence，并替换 unsignaled 的 acquire semaphore。

**适用条件**：
所有需要持续渲染的 Vulkan 应用，尤其是实时图形 / 游戏 / AR / VR 场景。

**不适用情况**：
一次性计算任务（compute only）可不采用此模型；CPU 上传后立即 wait idle 的离线渲染或工具流可简化为单 fence + 单 buffer。

**来源**：`[ENGINE][SPEC][TOOL]`

---

## 14. 相关 API 卡片

- `fence_semaphore.md`
- `command_buffer_lifetime.md`
- `command_buffer.md`
- `queue_submit.md`
- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`
- `../02_surface_swapchain/swapchain_recreate.md`
- `../04_buffer_image_memory/buffer.md`

---

## 15. 需要回查官方文档的情况

1. `vkAcquireNextImageKHR` 在 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 返回时 semaphore 与 fence 的具体状态与所有权规则。
2. Binary semaphore 在 acquire 失败后是否能安全复用，以及不同驱动 / 平台的行为差异。
3. Timeline semaphore 替代 per-frame fence + binary semaphore 数组的具体 value 计算规则与死锁规避。
4. Swapchain `minImageCount` 与 `MAX_FRAMES_IN_FLIGHT` 在不同 present mode（IMMEDIATE / FIFO / MAILBOX）下的约束。
5. `vkQueueSubmit2` / `VK_KHR_synchronization2` 中 `VkSubmitInfo2` 的 wait/signal stage 与 per-frame 配对的最佳实践。
6. Android Pause / Resume / Surface 重建时 fence 与 semaphore 的状态迁移与平台特定行为。
7. Per-frame descriptor pool 与 descriptor set 更新在 frame-in-flight 下的合法时序。

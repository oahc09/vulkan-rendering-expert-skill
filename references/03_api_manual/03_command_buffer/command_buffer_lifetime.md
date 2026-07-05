# API Card: Command Buffer Lifetime

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 / 生命周期 |
| Vulkan 对象 | `VkCommandBuffer` / `VkCommandPool` / `VkFence` |
| 常用 API | `vkAllocateCommandBuffers` / `vkResetCommandBuffer` / `vkResetCommandPool` / `vkFreeCommandBuffers` / `vkBeginCommandBuffer` / `vkQueueSubmit` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

Command buffer lifetime 管理是 Vulkan 工程中最容易出错的环节之一：CPU 侧 reset / begin 的时机必须与 GPU 完成时间严格对齐，否则会导致命令被覆盖、资源被提前释放或 validation error。[SPEC][ENGINE]

---

## 2. 所属对象链路

```text
Allocate
→ Begin (RECORDING)
→ Record Commands
→ End (EXECUTABLE)
→ Submit (PENDING)
→ GPU Execute
→ Fence Signal (EXECUTABLE again, if resettable)
→ Reset (INITIAL)
→ Begin (RECORDING) ...
```

### 上游依赖

- `VkCommandPool` 提供内存。
- `VkFence` 提供 CPU-GPU 同步点。

### 下游影响

- Command buffer 被 submit 后，其引用的所有资源进入 in-flight 状态。
- 错误时机 reset / free 会导致 GPU 访问已释放资源或已覆盖命令。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkCommandBuffer`（状态机：INITIAL / RECORDING / EXECUTABLE / PENDING / INVALID）
- `VkCommandPool`
- `VkFence`

### 常用 API

| API | 作用 |
|---|---|
| `vkAllocateCommandBuffers` | 分配，状态为 INITIAL。[SPEC] |
| `vkBeginCommandBuffer` | INITIAL → RECORDING。[SPEC] |
| `vkEndCommandBuffer` | RECORDING → EXECUTABLE。[SPEC] |
| `vkQueueSubmit` | EXECUTABLE → PENDING。[SPEC] |
| `vkResetCommandBuffer` / `vkResetCommandPool` | EXECUTABLE / INITIAL → INITIAL；PENDING 状态不允许 reset。[SPEC] |
| `vkFreeCommandBuffers` | 释放，可在任何状态调用，但需确保 GPU 不再使用。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_debug_utils`：为 command buffer 命名，便于追踪 lifetime。[TOOL]

---

## 4. 标准使用流程

```text
Per-frame 模式（推荐）:
Frame N:
    wait inFlightFence[N]
    vkResetCommandBuffer(cmd[N]) 或 vkResetCommandPool(pool[N])
    vkBeginCommandBuffer(cmd[N])
    record commands
    vkEndCommandBuffer(cmd[N])
    vkQueueSubmit(cmd[N], fence = inFlightFence[N])

下一帧使用下一个 slot，循环。
```

一次性 command buffer 模式：

```text
vkAllocateCommandBuffers
→ begin / record / end / submit
→ wait fence
→ vkFreeCommandBuffers
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `commandBuffer` 状态 | 只有 EXECUTABLE 或 INITIAL 才能 reset / begin。[SPEC] | PENDING 状态 reset 导致 validation error 或 crash。[TOOL] |
| `flags`（reset） | `VK_COMMAND_BUFFER_RESET_RELEASE_RESOURCES_BIT` 可释放内存回 pool。[SPEC] | 频繁使用导致内存碎片或额外分配开销。[HEUR] |
| `flags`（pool reset） | `VK_COMMAND_POOL_RESET_RELEASE_RESOURCES_BIT`。[SPEC] | 重置时释放了仍在使用的资源。[SPEC] |
| `pCommandBuffers`（free） | 释放后 handle 变为不可用，但 pool 中内存可能保留。[SPEC] | free 后立即使用旧 handle。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否为每个 frame-in-flight slot 分配独立 command buffer 或独立 command pool？
- [ ] Command pool 的 queue family 是否正确？

### 使用阶段

- [ ] Reset / begin 前是否等待了对应 fence？
- [ ] 同一 command buffer 是否未在 PENDING 状态下被 submit 两次？
- [ ] 录制完成后是否调用了 `vkEndCommandBuffer`？

### 销毁阶段

- [ ] Free / reset 前 fence 是否已 signal？
- [ ] Command pool 销毁时是否已 free 或确保所有 buffer 不再被 GPU 使用？[SPEC]

---

## 7. 高频错误

1. 未等待 fence 就 reset，导致 GPU 仍在读取旧命令。[SPEC]
2. 同一 command buffer 被多帧复用，但 fence 只等最新一帧。[ENGINE]
3. `vkResetCommandPool` 时未等待，池中某些 buffer 仍处于 PENDING 状态。[SPEC]
4. 销毁 `VkCommandPool` 时仍有 pending command buffer。[SPEC]
5. 误以为 `vkQueueSubmit` 返回后 command buffer 已完成，立即 reset。[SPEC]
6. Frame-in-flight 数量不足，CPU 等待 fence 导致 frame time 升高。[ENGINE]
7. 多线程下不同线程同时操作同一 command buffer 的状态。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkResetCommandBuffer-commandBuffer-00045`：command buffer 不能处于 pending 状态。
- `VUID-vkFreeCommandBuffers-pCommandBuffers-00047`：free 的 command buffer 不能处于 pending 状态。
- `VUID-vkBeginCommandBuffer-commandBuffer-00049`：只能从 INITIAL 或 EXECUTABLE（若允许 reset）状态开始。
- `VUID-vkQueueSubmit-pCommandBuffers-00072`：command buffer 必须处于 executable 状态。

### RenderDoc / AGI

- 查看 command buffer 是否被正确录制和提交。
- 检查 frame N 是否复用了 frame N-1 仍在 GPU 上的资源。

### 日志 / 代码检查

- 打印每帧 reset / begin / submit / fence signal 的时序。
- 检查 frame-in-flight 的 fence 数组索引是否正确。
- 检查 `vkWaitForFences` 的 timeout 和返回值。

---

## 9. 生命周期风险

### 创建时机

- 初始化时按 frame-in-flight 数量分配。
- 临时上传 buffer 在需要时分配。

### 使用时机

- 每帧录制前 reset。
- 提交后进入 PENDING，直到 fence signal。

### 销毁时机

- 应用退出或 swapchain recreate 时。
- 必须确保 GPU 不再使用。

### in-flight 风险

- PENDING 状态的 command buffer 引用的所有资源都必须保持有效。
- 这包括 framebuffer、image view、buffer、descriptor set、pipeline layout 等。[SPEC]
- Swapchain recreate 时必须等待所有 in-flight command buffer 完成，否则可能引用旧 swapchain image。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- Fence 是判断 command buffer 是否可 reset / free 的唯一可靠依据。[SPEC]
- `vkDeviceWaitIdle` 是最保守的等待方式，但会阻塞并行。[SPEC]

### GPU-GPU 同步

- Command buffer 内部通过 barrier / event 管理资源状态。
- 跨 command buffer 通过 semaphore 同步。

### 资源访问同步

- Command buffer 录制时引用的资源，在 GPU 执行期间必须有效。
- 不要录制命令后、submit 前修改或销毁资源，除非通过 barrier 明确管理。[SPEC]

---

## 11. Android 注意点

- Android 切后台或 surface destroyed 时，必须等待所有 pending command buffer 完成后再销毁资源。[ANDROID]
- 移动端 frame-in-flight 通常 2~3 帧，过多会增加内存和 latency。[ENGINE]
- `APP_CMD_TERM_WINDOW` 后应停止 submit，并等待 idle 再清理 command buffer。[ANDROID]
- 某些低端设备对 `vkResetCommandPool` 开销敏感，可评估逐个 `vkResetCommandBuffer`。[HEUR]

---

## 12. 性能注意点

### CPU 侧

- `vkResetCommandPool` 通常比逐个 reset 快，但会重置池中所有 buffer。[ENGINE]
- 避免每帧 allocate / free，使用 reset + reuse。[ENGINE]

### GPU 侧

- Lifetime 管理本身不直接增加 GPU 开销，但 fence wait 过长会降低 CPU-GPU 并行度。[HEUR]

### 移动端

- 移动端内存紧张，per-frame command pool 可更精确控制内存占用。[ENGINE]
- 但 per-frame pool 数量增加会提高管理复杂度，需权衡。[HEUR]

---

## 13. 专家经验

**经验**：
为每个 frame-in-flight slot 分配独立的 `VkCommandPool`，每帧直接 `vkResetCommandPool`，可简化 lifetime 管理并降低 CPU overhead。只有在需要频繁部分 reset 时才使用 `vkResetCommandBuffer`。

**适用条件**：
每帧录制命令量较大、需要高效 reset、且每帧命令结构相对固定的场景。

**不适用情况**：
命令结构差异大、需要频繁只重置部分 command buffer 的场景；或内存极度受限、无法承担 per-frame pool 开销的情况。

**来源**：`[ENGINE]`

---

## 14. 相关 API 卡片

- `command_buffer.md`
- `queue_submit.md`
- `../08_synchronization/fence.md`
- `../02_surface_swapchain/swapchain_recreate.md`
- `../04_buffer_image_memory/image.md`

---

## 15. 需要回查官方文档的情况

1. Command buffer 状态机的完整转换规则。
2. `VK_COMMAND_BUFFER_RESET_RELEASE_RESOURCES_BIT` 的具体内存行为。
3. 多线程下 command pool 的线程安全限制。
4. Secondary command buffer 的 lifetime 与 primary command buffer 的关系。

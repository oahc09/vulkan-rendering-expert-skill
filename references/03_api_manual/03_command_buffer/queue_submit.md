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
- Binary wait 的匹配 signal 操作必须已提交；timeline 支持 wait-before-signal，但应用必须保证未来 signal 可达，不能形成依赖死锁。[SPEC]
- Timeline semaphore 值必须单调递增。[SPEC]

### 下游影响

- GPU 开始执行 command buffer 中的命令。
- Fence 在 GPU 完成后被 signal。[SPEC]
- Semaphore signal 的完成范围由提交 API 与同步 scope 决定；Submit2 的 signal stageMask 限定第一同步范围，不能一律解释为全部 GPU 工作完成。WSI present 等待 binary semaphore。[SPEC]
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
    pWaitDstStageMask    = [COLOR_ATTACHMENT_OUTPUT_BIT]  // 仅当 swapchain image 最早访问为 color attachment；否则按实际访问选择
    pCommandBuffers      = [cmd]
    pSignalSemaphores    = [renderFinishedSemaphore]
→ vkQueueSubmit(queue, 1, &submitInfo, inFlightFence)
→ GPU 执行
→ renderFinishedSemaphore signal 后 vkQueuePresentKHR 可执行
→ inFlightFence signal 后 CPU 可复用 frame resource
```

Synchronization2 概念流程（不是 C++ 聚合初始化；须设置正确 sType/pNext、计数与指针，并启用 synchronization2）：

```text
cmdInfo.commandBuffer = cmd
waitInfo.semaphore = imageAvailableSemaphore[frameIndex]
waitInfo.stageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT
    // 仅限最早访问为 color attachment 的路径（包括相应 layout transition）
signalInfo.semaphore = renderFinishedSemaphore[imageIndex]
signalInfo.stageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT
    // 本例使用保守的提交完成范围，不把 ALL_GRAPHICS 当作 compute/transfer 完成证明
submitInfo = waits[waitInfo] + commands[cmdInfo] + signals[signalInfo]
检查 vkResetFences；紧邻实际 vkQueueSubmit2
检查 vkQueueSubmit2 返回值；失败走恢复，不 present 或普通 fence wait
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `waitSemaphoreCount` / `pWaitSemaphores` | 必须与 acquire / 前序 pass 的 signal semaphore 一一对应。[SPEC] | semaphore 数量或顺序与 `pWaitDstStageMask` 不匹配。[TOOL] |
| `pWaitDstStageMask` | 决定 GPU 在哪些 pipeline stage 等待 semaphore，应尽量精确。[SPEC] | 填 `ALL_COMMANDS` 导致过度同步；填错 stage 导致 hazard。[TOOL] |
| `commandBufferCount` / `pCommandBuffers` | 一次 submit 可包含多个 command buffer；submission order 不等于执行完全串行或自动建立所有内存依赖。[SPEC] | 跨 frame 的 command buffer 混在一个 submit 中，fence 管理混乱。[ENGINE] |
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
- [ ] Wait stage 是否覆盖 consumer 最早访问，signal scope 是否覆盖 producer 写入及必要操作（不要求两个 mask 相等）？
- [ ] 同一 frame 的 acquire / submit / present semaphore 是否一一对应？
- [ ] Timeline semaphore 值是否单调递增？

### 销毁阶段

- [ ] Fence signal 后才能释放或复用相关资源。
- [ ] 不要销毁仍在 pending submit 中使用的 semaphore。[SPEC]

---

## 7. 高频错误

1. `vkQueueSubmit` 的 wait semaphore 与 `vkAcquireNextImageKHR` 的 signal semaphore 不是同一个。[SPEC]
2. Wait stage 未覆盖 swapchain image 的最早访问或相应 layout transition，导致 hazard；TOP_OF_PIPE 不是该错误的通用判据，过早等待可能降低并行度。[SPEC]
3. 同一 fence 被连续两帧使用，前一帧 GPU 未完成时后一帧又 submit。[SPEC]
4. Command buffer 仍处于 recording 状态就 submit。[SPEC]
5. 多 queue 场景下 semaphore 跨 queue 传递但 stage mask 设置错误。[SPEC]
6. Timeline wait 的目标值没有可达的后续 signal，或 signal 依赖该 wait 完成，导致永久等待；单纯 wait-before-signal 并非非法。[TOOL]
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
- Binary semaphore 的匹配 signal 操作须先提交；重用需证明前一次 wait 已完成。Timeline 可 wait-before-signal，不能套用 binary 状态规则。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Fence 是 CPU 等待 GPU 的主要机制。[SPEC]
- `vkQueueSubmit` 返回不代表 GPU 执行完成，只有 fence signal 才代表完成。[SPEC]

### GPU-GPU 同步

- Binary semaphore：acquire → render → present 的标准链。[SPEC]
- Timeline semaphore：适合管理跨帧依赖、upload → render 依赖。[GUIDE]
- 同一 queue 的 submission order 不自动建立所有执行/内存依赖；仍须按资源访问设置 barrier 等同步，通常无需为了同队列依赖额外使用 semaphore。[SPEC]
- 跨 queue 必须显式 semaphore 同步。[SPEC]

### 资源访问同步

- Wait stage 覆盖 consumer 的最早相关访问；signal scope 覆盖 producer。两者可以不同，不能以 mask 相等代替依赖分析。[SPEC]
- Image layout transition 通常在 command buffer 内通过 barrier 完成，不需要跨 submit。[SPEC]

---

## 11. Android 注意点

- Android 通常使用单一 graphics/present queue，semaphore 链路为：acquire semaphore → submit wait → submit signal → present wait。[ANDROID]
- 区分 acquire / submit / present 的返回值：acquire 的 SUBOPTIMAL 已取得 image，可完成当前帧后重建；OUT_OF_DATE 不继续本次提交。submit 失败独立进入恢复，不能把 acquire/present 状态当作 submit 返回值。[ANDROID]
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
标准 frame loop 中，imageAvailableSemaphore 与 inFlightFence 按 frame slot 管理，renderFinishedSemaphore 按 swapchain image 管理。submit fence 不证明 present 已消费 renderFinishedSemaphore；不可在旧使用仍 pending 时重新 signal。依据：[Swapchain Semaphore Reuse](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)。

**适用条件**：
常规 Android / 桌面渲染，存在多 frame-in-flight。

**不适用情况**：
纯离屏、无 WSI present 的场景。单帧或内部 timeline 管理不豁免 WSI binary semaphore 的复用与退役规则。

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

权威帧循环与失败路径：[frame-loop-contract](../../05_workflows/01_renderer_setup/setup_frame_loop.md#frame-loop-contract)。
规范依据：[vkQueueSubmit](https://docs.vulkan.org/refpages/latest/refpages/source/vkQueueSubmit.html)、
[VkSemaphoreSubmitInfo](https://docs.vulkan.org/refpages/latest/refpages/source/VkSemaphoreSubmitInfo.html)。

## 15. 需要回查官方文档的情况

1. `VkPipelineStageFlags` 与 semaphore wait stage 的精确匹配规则。
2. Timeline semaphore 与 binary semaphore 的混合使用限制。
3. `VK_KHR_synchronization2` 中 `VkSubmitInfo2` 的 stage mask 语义变化。
4. Device group / multi-queue 场景下的 submit 规则。

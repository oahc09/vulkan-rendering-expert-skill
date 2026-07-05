# API Card: VkBufferMemoryBarrier

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkBufferMemoryBarrier` / `VkBufferMemoryBarrier2` |
| 常用 API | `vkCmdPipelineBarrier` / `vkCmdPipelineBarrier2` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 / `VK_KHR_synchronization2` |

---

## 1. 一句话定位

`VkBufferMemoryBarrier` 是在同一条或不同 queue family 之间，对特定 buffer range 建立执行依赖与内存可见性的工具，常用于 buffer 的读写切换与 queue family ownership transfer。[SPEC]

---

## 2. 所属对象链路

```text
Producer 命令（如 vkCmdCopyBuffer / vkCmdDispatch 写入 buffer）
→ vkCmdPipelineBarrier(VkBufferMemoryBarrier)
→ Consumer 命令（如 vkCmdDraw / vkCmdDispatch 读取 buffer）
```

### 上游依赖

- 已创建并绑定内存的 `VkBuffer`。[SPEC]
- Producer 命令已录制到同一 queue 的先前位置。[SPEC]

### 下游影响

- Consumer 命令在 barrier 定义的 dst stage 才能看到 producer 写入的数据。[SPEC]
- 若涉及 queue family transfer，还需在目标 queue 上提交对应的 acquire barrier。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkBufferMemoryBarrier`
- `VkBufferMemoryBarrier2`（synchronization2 / Vulkan 1.3）
- `VkPipelineStageFlags` / `VkAccessFlags`
- `VkPipelineStageFlags2` / `VkAccessFlags2`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier` | 插入包含 buffer barrier 的同步点。[SPEC] |
| `vkCmdPipelineBarrier2` | synchronization2 版本，支持扩展 stage/access。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供 `VkBufferMemoryBarrier2`。

---

## 4. 标准使用流程

```text
确定 buffer 的 producer stage / access
→ 确定 consumer stage / access
→ 确定是否需要跨 queue family ownership transfer
→ 构造 VkBufferMemoryBarrier（buffer / offset / size / srcQueueFamilyIndex / dstQueueFamilyIndex）
→ 在 producer 命令之后、consumer 命令之前调用 vkCmdPipelineBarrier
→ 若跨 queue，在目标 queue 上提交 acquire barrier
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcAccessMask` / `dstAccessMask` | producer 写入类型与 consumer 读取/写入类型。[SPEC] | srcAccess 遗漏 `TRANSFER_WRITE` 或 `SHADER_WRITE`。[TOOL] |
| `srcQueueFamilyIndex` / `dstQueueFamilyIndex` | 跨 queue family 时分别填源与目标 family；否则填 `VK_QUEUE_FAMILY_IGNORED`。[SPEC] | 同 family 时误填具体 index 导致不必要的 ownership transfer。[TOOL] |
| `buffer` / `offset` / `size` | 同步范围；`VK_WHOLE_SIZE` 表示从 offset 到末尾。[SPEC] | offset/size 未按设备要求对齐。[TOOL] |
| `srcStageMask` / `dstStageMask`（在 vkCmdPipelineBarrier 中） | 决定 execution dependency 的范围。[SPEC] | stage 过宽导致气泡，过窄导致同步缺失。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否明确 producer 与 consumer 的 stage / access？
- [ ] 是否跨 queue family？若是，是否规划了 release + acquire 成对 barrier？
- [ ] `offset` / `size` 是否满足对齐要求？

### 使用阶段

- [ ] Barrier 是否位于 producer 命令之后、consumer 命令之前？
- [ ] 同 queue family 时是否将 queue family index 设为 `VK_QUEUE_FAMILY_IGNORED`？
- [ ] 跨 queue 时是否在目标 queue 的相同 buffer range 上提交了 acquire barrier？

### 销毁阶段

- [ ] 无独立对象销毁；barrier 随 command buffer 生命周期结束而失效。

---

## 7. 高频错误

1. `srcAccessMask` 未包含 producer 实际的写入 flag，导致 consumer 读脏数据。[TOOL]
2. 同 queue family 时误用 queue family ownership transfer，增加不必要的同步开销。[TOOL]
3. 跨 queue 时只发 release barrier 未发 acquire barrier，或 family index 填反。[TOOL]
4. `offset` / `size` 未对齐，触发 validation error。[TOOL]
5. 对 host-visible buffer 的 CPU 写入未使用 `VK_ACCESS_HOST_WRITE_BIT`。[TOOL]
6. `dstStageMask` 设为 `TOP_OF_PIPE_BIT`，consumer 过早开始执行。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkBufferMemoryBarrier-*`：offset/size 对齐、queue family index 规则。
- `VUID-vkCmdPipelineBarrier-bufferMemoryBarrierCount-01178`：family index 合法性。
- `VUID-VkBufferMemoryBarrier-size-01309`：size 与 offset 对齐。

### RenderDoc / AGI

- 查看 barrier 在 command buffer 中的位置与 stage/access mask。
- AGI 可分析 buffer barrier 是否造成 GPU 气泡。

### 日志 / 代码检查

- 检查 producer / consumer 的 stage / access 是否成对。
- 检查跨 queue family 的 release/acquire 是否成对出现。
- 检查 buffer 范围计算。

---

## 9. 生命周期风险

### 创建时机

- Barrier 不是独立对象，在 command buffer 录制时动态构造。[SPEC]

### 使用时机

- 在需要同步 buffer 读写切换的位置插入。[SPEC]

### 销毁时机

- 随 command buffer reset / free 失效；不持有 buffer 引用。[SPEC]

### in-flight 风险

- Barrier 只保证录制它的 command buffer 内部及同一 queue 的提交顺序；不能跨 queue 同步（跨 queue 需 semaphore + ownership transfer）。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Buffer barrier 不涉及 CPU 同步；CPU 等待应使用 fence 或 timeline semaphore。[SPEC]

### GPU-GPU 同步

- 同 queue 内建立 execution + memory dependency。[SPEC]
- 跨 queue 需使用 queue family ownership transfer：源 queue release，目标 queue acquire，并配合 semaphore 保证提交顺序。[SPEC]

### 资源访问同步

- 精确限定 buffer range，避免全局 memory barrier 的过度刷新。[ENGINE]
- Host-visible buffer 的 CPU 写入需使用 `HOST_WRITE` → `SHADER_READ` 等路径。[SPEC]

---

## 11. Android 注意点

- 移动端带宽受限，全局 memory barrier 会触发广泛 cache flush；优先使用 buffer barrier 精确限定范围。[ANDROID][ENGINE]
- 多 queue family（如 graphics + compute + transfer）在移动端可能共享物理单元，但仍需按 Vulkan 规则做 ownership transfer。[ANDROID]
- AGI 可显示 buffer barrier 导致的 GPU 空闲气泡，帮助优化。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 录制 barrier 开销低，但设计不良的 barrier 会限制 GPU 并行。[ENGINE]

### GPU 侧

- 精确的 stage/access 与 range 可减少 cache flush/invalidate 范围。[ENGINE]
- 避免对同一 buffer 频繁切换 tiny range；合并相邻 barrier 或按 pass 级别同步。[ENGINE]

### 移动端

- 减少每帧 buffer barrier 数量；对 per-frame uniform/storage buffer 可考虑使用 triple-buffering 而非每帧 barrier。[ENGINE]
- 不要对只读 buffer（如静态 vertex/index buffer）插入 barrier。[HEUR]

---

## 13. 专家经验

**经验**：
写 buffer barrier 前先回答四个问题：谁写、写什么范围、谁读、读什么范围。若 producer 与 consumer 在同一 queue family，直接用 `VK_QUEUE_FAMILY_IGNORED` 即可，不要炫技做 ownership transfer。若必须跨 queue，牢记 release 与 acquire 必须成对，并且目标 queue 的提交必须等待源 queue 的 semaphore signal。

**适用条件**：
同 queue buffer 读写切换、compute dispatch 之间的数据传递、跨 queue family 的 buffer 共享。

**不适用情况**：
CPU-GPU 同步（用 fence）；跨 queue 全局顺序（用 semaphore）；只需事件点同步（用 event）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `pipeline_barrier.md`
- `image_memory_barrier.md`
- `event.md`
- `semaphore.md`
- `fence.md`
- `synchronization2.md`
- `../04_buffer_image_memory/buffer.md`
- `../03_command_buffer/command_buffer.md`

---

## 15. 需要回查官方文档的情况

1. 具体 pipeline stage 与 access flag 的合法组合。
2. Queue family ownership transfer 的 release/acquire 顺序与 family index 规则。
3. `VK_WHOLE_SIZE` 与 offset 的对齐要求。
4. Synchronization2 中 `VkBufferMemoryBarrier2` 的扩展 access flag。
5. 不同驱动对 buffer barrier 的缓存行为差异。

# API Card: vkCmdPipelineBarrier

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkMemoryBarrier` / `VkBufferMemoryBarrier` |
| 常用 API | `vkCmdPipelineBarrier` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`vkCmdPipelineBarrier` 是同一条 queue 内建立执行依赖与 memory dependency 的命令，通过 source/destination stage mask 和 access mask 控制前后命令的可见性，是资源状态转换和读写顺序的核心工具。[SPEC]

---

## 2. 所属对象链路

```text
上游 GPU 命令（producer）
→ vkCmdPipelineBarrier (srcStage / srcAccess → dstStage / dstAccess)
→ 下游 GPU 命令（consumer）
```

### 上游依赖

- 已处于 recording 状态的 command buffer。[SPEC]
- Producer 命令已录制到同一 command buffer 或同一 queue 的先前提交中。[SPEC]
- 要同步的资源（buffer / image）已创建并绑定内存。[SPEC]

### 下游影响

- Consumer 命令在 barrier 定义的 stage 才能开始执行，并能看到 producer 写入的 memory。[SPEC]
- 影响同一条 queue 内后续命令的执行时序和缓存一致性。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkMemoryBarrier`
- `VkBufferMemoryBarrier`
- `VkPipelineStageFlags`
- `VkAccessFlags`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier` | 在 command buffer 中插入 execution + memory dependency。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供更细粒度的 `vkCmdPipelineBarrier2` 与 `VkPipelineStageFlags2` / `VkAccessFlags2`。[SPEC]

---

## 4. 标准使用流程

```text
确定 producer 阶段（如 COLOR_ATTACHMENT_OUTPUT）和 access（如 COLOR_ATTACHMENT_WRITE）
→ 确定 consumer 阶段（如 FRAGMENT_SHADER）和 access（如 SHADER_READ）
→ 确定是否需要 global memory barrier、buffer barrier 或 image barrier
→ 在 producer 与 consumer 命令之间调用 vkCmdPipelineBarrier
→ 继续录制 consumer 命令
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcStageMask` | Producer 完成其工作的 pipeline stage；barrier 只保证该 stage 之前的命令顺序。[SPEC] | 使用 `ALL_COMMANDS_BIT` 作为通用 src stage 导致过度同步。[HEUR] |
| `dstStageMask` | Consumer 开始其工作的 pipeline stage；barrier 只阻塞到该 stage。[SPEC] | Stage 过早导致性能下降，或过晚导致 consumer 看到旧数据。[TOOL] |
| `srcAccessMask` | Producer 对 memory 的写入类型；决定哪些写入需要 flush。[SPEC] | srcAccess 为空或遗漏 `MEMORY_WRITE_BIT`，导致写入对 consumer 不可见。[TOOL] |
| `dstAccessMask` | Consumer 对 memory 的读取/写入类型；决定哪些读取需要 invalidate。[SPEC] | dstAccess 与 consumer 实际 access 不一致，导致缓存未失效。[TOOL] |
| `dependencyFlags` | `VK_DEPENDENCY_BY_REGION_BIT` 允许 per-region 依赖，常用于 subpass/attachment 同步。[SPEC] | 在 buffer / 全局 barrier 中误用 `BY_REGION_BIT`，该 bit 对 non-attachment 资源无效。[TOOL] |
| `bufferMemoryBarrierCount` / `pBufferMemoryBarriers` | 针对特定 buffer range 的同步；包含 `srcQueueFamilyIndex` / `dstQueueFamilyIndex` 用于 queue family ownership transfer。[SPEC] | `size` 设为 `VK_WHOLE_SIZE` 时未注意 offset 对齐；或 queue family index 填写错误。[TOOL] |
| `memoryBarrierCount` / `pMemoryBarriers` | 全局 memory barrier，作用于所有受 src/dst access mask 影响的资源。[SPEC] | 滥用全局 barrier 导致不必要的缓存刷新，移动端性能下降。[ENGINE] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否明确 producer / consumer 的 pipeline stage？
- [ ] srcAccess / dstAccess 是否与实际读写匹配？
- [ ] 是否需要 image barrier（见 image_memory_barrier.md）？

### 使用阶段

- [ ] Barrier 是否放在 producer 命令之后、consumer 命令之前？
- [ ] 是否在 render pass 内部错误使用了 `vkCmdPipelineBarrier`？（render pass 内通常使用 subpass dependency）[SPEC]
- [ ] Queue family ownership transfer 是否成对出现？

### 销毁阶段

- 该命令本身无独立销毁阶段；依赖 command buffer 完成与 fence 保证资源生命周期。[SPEC]

---

## 7. 高频错误

1. `srcAccessMask` 不包含 producer 实际使用的 access flag，导致 consumer 读脏数据。[TOOL]
2. `dstStageMask` 设为 `TOP_OF_PIPE_BIT`，consumer 在该阶段之后立即读取，未等待 producer 完成。[TOOL]
3. 过度使用 `VK_PIPELINE_STAGE_ALL_COMMANDS_BIT` 和 `VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT` 作为通用配对，造成性能严重下降。[HEUR]
4. 在 render pass 内部用 pipeline barrier 替代 subpass dependency 处理 attachment 同步。[TOOL]
5. Buffer barrier 的 offset/size 未按 `minMemoryMapAlignment` / `nonCoherentAtomSize` 对齐。[TOOL]
6. 跨 queue family transfer 只发了 release barrier 未发 acquire barrier，或 family index 填错。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdPipelineBarrier-srcStageMask-04990` 等：stage / access 组合合法性。
- `VUID-vkCmdPipelineBarrier-dependencyFlags-01188`：`BY_REGION_BIT` 使用限制。
- `VUID-vkCmdPipelineBarrier-bufferMemoryBarrierCount-01178`：buffer barrier 的 queue family index 规则。
- `VUID-VkBufferMemoryBarrier-size-01309`：size 与 offset 对齐。

### RenderDoc / AGI

- RenderDoc 可展示 barrier 在 command buffer 中的位置及 stage/access mask。[TOOL]
- AGI 可分析 barrier 是否造成 GPU 空闲气泡（bubble）。[TOOL]

### 日志 / 代码检查

- 检查 producer 与 consumer 的 stage / access 是否一一对应。
- 检查 barrier 是否被重复插入（如每 draw call 一次）。
- 检查 buffer barrier 的 offset/size 计算。

---

## 9. 生命周期风险

### 创建时机

- 该命令在 command buffer 录制时动态插入；无独立创建开销。[SPEC]

### 使用时机

- 在需要同步两个 GPU 命令之间使用；通常是 resource producer→consumer 的边界。[SPEC]

### 销毁时机

- 随 command buffer reset / free 而失效；barrier 本身不持有对象引用。[SPEC]

### in-flight 风险

- Barrier 只作用于录制它的 command buffer 内部及同一 queue 的提交顺序；不改变其他 queue 的行为。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkCmdPipelineBarrier` 不涉及 CPU 同步；CPU 侧等待应使用 fence 或 timeline semaphore。[SPEC]

### GPU-GPU 同步

- 同 queue 内建立 execution dependency。[SPEC]
- 跨 queue 同步需配合 semaphore，pipeline barrier 无法跨越 queue。[SPEC]

### 资源访问同步

- Global memory barrier：影响所有 memory 访问。[SPEC]
- Buffer memory barrier：针对特定 buffer range。[SPEC]
- Image memory barrier：见 `image_memory_barrier.md`。[SPEC]
- Access mask 必须成对正确：`srcAccess` 描述 producer 写入，`dstAccess` 描述 consumer 读取/写入。[SPEC]

---

## 11. Android 注意点

- 移动端 Tile-based GPU 对 barrier 和 attachment layout transition 敏感；尽量减少每帧全屏 image 的 barrier 次数。[ANDROID][ENGINE]
- 全局 memory barrier 会触发广泛的缓存刷新，在带宽受限的移动设备上代价高；优先使用 buffer/image barrier 精确限定范围。[ENGINE][ANDROID]

---

## 12. 性能注意点

### CPU 侧

- `vkCmdPipelineBarrier` 录制本身开销较低，但设计不良的 barrier 会显著限制 GPU 并行度。[ENGINE]

### GPU 侧

- 过宽的 stage mask（如 `ALL_COMMANDS_BIT`）会让 GPU 流水线排空，形成气泡。[HEUR]
- 不必要的 `MEMORY_READ/WRITE` access mask 会增加 cache flush/invalidate 开销。[ENGINE]

### 移动端

- Tile-based GPU 上，render pass 外的 image layout transition 会触发 resolve/store，代价高；应尽量在 subpass dependency 中完成 attachment 同步。[ENGINE][ANDROID]
- 避免每帧对大量 buffer 做 barrier；合并同类 barrier 或改用 event 降低提交复杂度。[ENGINE]

---

## 13. 专家经验

**经验**：
写 barrier 时先回答四个问题：谁写（producer stage/access）、写什么资源、谁读（consumer stage/access）、读什么资源。不要把 `ALL_COMMANDS_BIT` 和 `MEMORY_READ/WRITE` 当作默认安全值；在性能敏感路径上，精确的 stage/access 是 GPU 并行度的关键。

**适用条件**：
同 queue 内 producer-consumer 资源依赖、buffer 读写切换、compute dispatch 之间的数据传递。

**不适用情况**：
跨 queue 同步（用 semaphore）；CPU 需要知道完成时机（用 fence/timeline semaphore）；只需要事件点同步且希望减少 command buffer 膨胀（用 event）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `image_memory_barrier.md`
- `event.md`
- `synchronization2.md`
- `semaphore.md`
- `fence.md`
- `../04_buffer_image_memory/buffer.md`
- `../04_buffer_image_memory/image.md`

---

## 14.5 Vulkan 1.4 变更

Vulkan 1.4 对 Pipeline Barrier 的主要变更：

### Synchronization2 promote 为 mandatory feature

1.4 设备保证支持 `vkCmdPipelineBarrier2` / `VkDependencyInfo`；但 mandatory feature 仍需通过 `VkPhysicalDeviceVulkan13Features.synchronization2 = VK_TRUE`（1.3 promote，**不在 Vulkan14Features**）显式启用后才能使用 sync2 API，启用后无需 fallback 到 `vkCmdPipelineBarrier`。[SPEC]

### maintenance6 简化

`VK_KHR_maintenance6`（1.4 核心）引入简化同步表达选项。[SPEC]

### 推荐 barrier 策略

- 1.4 设备统一使用 `vkCmdPipelineBarrier2`。[ENGINE]
- `VkMemoryBarrier2` 的 stage/access flag 比 1.0 版本更精确。[SPEC]
- 与 timeline semaphore 配合可实现跨帧依赖。[ENGINE]

---

## 15. 需要回查官方文档的情况

1. 具体 pipeline stage 与 access flag 的合法组合表。
2. `VK_DEPENDENCY_BY_REGION_BIT` 在 attachment 同步中的精确语义。
3. Queue family ownership transfer 的 release/acquire barrier 顺序及 family index 规则。
4. `VK_ACCESS_MEMORY_READ_BIT` / `VK_ACCESS_MEMORY_WRITE_BIT` 与具体 access flag 的等价关系。
5. Vulkan 1.3 / synchronization2 中 `VkMemoryBarrier2` / `VkBufferMemoryBarrier2` 的扩展 access flag 语义。

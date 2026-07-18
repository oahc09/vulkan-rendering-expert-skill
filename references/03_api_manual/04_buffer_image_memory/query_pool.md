# API Card: VkQueryPool

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 / 调试链 |
| Vulkan 对象 | `VkQueryPool` |
| 常用 API | `vkCreateQueryPool` / `vkDestroyQueryPool` / `vkCmdBeginQuery` / `vkCmdEndQuery` / `vkCmdWriteTimestamp` / `vkGetQueryPoolResults` / `vkResetQueryPool` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 核心；`vkResetQueryPool` 为 Vulkan 1.2+ |

---

## 1. 一句话定位

`VkQueryPool` 是 Vulkan 的 GPU 侧计数 / 时间戳采集对象，提供 occlusion（遮挡）、pipeline statistics（管线统计）与 timestamp（时间戳）三类查询；结果可由 host 端 `vkGetQueryPoolResults` 或 GPU 端 `vkCmdCopyQueryPoolResults` 取回。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice
→ VkQueryPool (Create，指定 queryType + queryCount)
→ 命令录制:
   ├─ vkCmdResetQueryPool (重置为可用)
   ├─ vkCmdBeginQuery / vkCmdEndQuery (occlusion / pipeline stats)
   ├─ vkCmdWriteTimestamp (timestamp)
   └─ vkCmdCopyQueryPoolResults (GPU 侧拷贝到 buffer)
→ vkGetQueryPoolResults (host 侧读取)
→ vkResetQueryPool (1.2+，host 侧批量重置)
→ vkDestroyQueryPool
```

### 上游依赖

- `VkDevice` 必须有效。[SPEC]
- `queryType` 必须被 physical device 支持；timestamp 需 `VkQueueFamilyProperties::timestampValidBits` > 0。[SPEC]
- pipeline statistics 需启用 `VkPhysicalDeviceFeatures::pipelineStatisticsQuery`。[SPEC]

### 下游影响

- query 结果需通过 fence / semaphore 或 `VK_QUERY_RESULT_WAIT_BIT` 同步才能被安全读取。[SPEC]
- 复用 query 前必须 reset（`vkCmdResetQueryPool` 或 `vkResetQueryPool`）。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkQueryPool` / `VkQueryPoolCreateInfo`
- `VkQueryResultFlags`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateQueryPool` | 创建 query pool，指定类型与数量。[SPEC] |
| `vkDestroyQueryPool` | 销毁 query pool；需 GPU 不再访问。[SPEC] |
| `vkCmdResetQueryPool` | 命令侧重置若干 query（Vulkan 1.0 起可用）。[SPEC] |
| `vkResetQueryPool` | host 侧批量重置（Vulkan 1.2+ / `VK_EXT_host_query_reset`）。[SPEC] |
| `vkCmdBeginQuery` | 开始 occlusion / pipeline stats 统计。[SPEC] |
| `vkCmdEndQuery` | 结束统计，结果写入对应 query index。[SPEC] |
| `vkCmdWriteTimestamp` | 在指定 pipeline stage 写入时间戳。[SPEC] |
| `vkGetQueryPoolResults` | host 侧读取结果，可选 wait / partial / 64-bit / availability。[SPEC] |
| `vkCmdCopyQueryPoolResults` | GPU 侧把结果拷贝到 buffer，配合 readback 使用。[SPEC] |

### 相关扩展 / 版本

- `VK_EXT_host_query_reset`（Vulkan 1.2 核心 `vkResetQueryPool`）：host 侧批量重置，避免占用 command buffer。[SPEC]
- `VK_KHR_performance_query` / `VK_EXT_performance_query`：性能计数器查询（厂商 / Counter-based profiling）。[SPEC]
- `VK_EXT_transform_feedback`：与 `VK_QUERY_TYPE_TRANSFORM_FEEDBACK_STREAM_EXT` 配合。
- Android 可用性：核心 occlusion / timestamp / pipeline stats 全部可用；`vkResetQueryPool` 在 Vulkan 1.2+ 设备可用；performance query 受驱动支持。[ANDROID]

---

## 4. 标准使用流程

### 4.1 Occlusion Query

```text
1. vkCreateQueryPool(queryType = OCCLUSION, queryCount = N)
2. 每帧录制:
   vkCmdResetQueryPool(cmd, pool, firstQuery = 0, queryCount = N)
   for i in draws:
       vkCmdBeginQuery(cmd, pool, queryIndex = i, flags = 0)
       vkCmdDraw... (draw call)
       vkCmdEndQuery(cmd, pool, queryIndex = i)
3. 提交 command buffer + fence
4. vkWaitForFences(fence)
5. vkGetQueryPoolResults(pool, firstQuery, queryCount, dataSize, pData,
                         stride, flags = VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT)
   - 返回值为通过 depth/stencil 测试的 sample 数（uint64）
```

### 4.2 Timestamp Query

```text
1. vkCreateQueryPool(queryType = TIMESTAMP, queryCount = N)
2. 每帧录制:
   vkCmdResetQueryPool(cmd, pool, 0, N)
   vkCmdWriteTimestamp(cmd, pipelineStage = TOP_OF_PIPE, pool, query = 0)
   ... 命令 ...
   vkCmdWriteTimestamp(cmd, pipelineStage = BOTTOM_OF_PIPE, pool, query = 1)
3. 提交 + wait fence
4. vkGetQueryPoolResults(..., flags = VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT)
5. 计算耗时 = (timestamps[1] - timestamps[0]) * timestampPeriod (ns)
   - timestampPeriod 来自 VkPhysicalDeviceLimits
```

### 4.3 Pipeline Statistics Query

```text
1. vkCreateQueryPool(queryType = PIPELINE_STATISTICS,
                     pipelineStatistics = INPUT_ASSEMBLY_VERTICES_BIT | VERTEX_SHADER_INVOCATIONS_BIT | ...)
2. vkCmdResetQueryPool → vkCmdBeginQuery(query, flags = 0)
   ... 涉及统计的命令 ...
   vkCmdEndQuery(query)
3. vkGetQueryPoolResults 返回每个 statistic 的 uint32/uint64（按 pipelineStatistics 顺序）
```

---

## 5. 关键字段

### 5.1 VkQueryPoolCreateInfo

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `queryType` | `OCCLUSION` / `PIPELINE_STATISTICS` / `TIMESTAMP`；扩展可启用 `PERFORMANCE_QUERY` / `TRANSFORM_FEEDBACK_STREAM_EXT`。[SPEC] | pool 类型与命令不匹配（如 occlusion pool 调用 `vkCmdWriteTimestamp`）。[SPEC] |
| `queryCount` | pool 中 query 数量；必须 > 0。[SPEC] | 越界 index 调用。[TOOL] |
| `pipelineStatistics` | 仅 `PIPELINE_STATISTICS` 类型有效；按位组合统计项。[SPEC] | 启用未被 feature 支持的统计项。[SPEC] |

### 5.2 VkQueryResultFlags

| Flag | 专家关注点 | 常见错误 |
|---|---|---|
| `VK_QUERY_RESULT_64_BIT` | 结果用 uint64；不带该 flag 时返回 uint32（规范允许，但 timestamp 可能截断 / wrap / saturate）。timestamp 工程上推荐用 64 位以避免精度损失。[SPEC] | timestamp 用 32 位结果导致截断 / wrap，影响测量精度。[ENGINE] |
| `VK_QUERY_RESULT_WAIT_BIT` | 阻塞直到结果可用；简化同步但可能 stall CPU。[SPEC] | 在主线程每帧 wait 大量 query 造成 jank。[ENGINE] |
| `VK_QUERY_RESULT_WITH_AVAILABILITY_BIT` | 每个结果后追加 availability 值（非 0 表示可用）；适合异步轮询。[SPEC] | 用 PARTIAL_BIT 但未配合 availability 判断有效性。[TOOL] |
| `VK_QUERY_RESULT_PARTIAL_BIT` | 允许返回部分结果；仅 occlusion / pipeline stats 有效，timestamp 不可用。[SPEC] | 对 timestamp 使用 PARTIAL_BIT 触发 VUID。[SPEC] |

### 5.3 vkCmdWriteTimestamp 的 pipelineStage

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `pipelineStage` | 时间戳在指定 stage 完成时写入；常选 `TOP_OF_PIPE`（命令开始）与 `BOTTOM_OF_PIPE`（命令结束）。[SPEC] | 用 host 阶段或不可用 stage 触发 VUID。[SPEC] |
| `query` | 必须落在 pool 范围内。[SPEC] | 越界。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `queryType` 是否被 physical device 支持？timestamp 是否有 `timestampValidBits`？
- [ ] 若使用 pipeline statistics，是否启用了 `pipelineStatisticsQuery` feature？
- [ ] `queryCount` 是否覆盖所有 in-flight 帧的需求？

### 使用阶段

- [ ] 每个 query 在使用前是否被 reset？[SPEC]
- [ ] `vkCmdBeginQuery` 与 `vkCmdEndQuery` 是否成对？index 是否一致？[SPEC]
- [ ] `vkCmdWriteTimestamp` 是否在合法 stage 上调用？[SPEC]
- [ ] 是否避免在 render pass 内 reset query pool？[SPEC]
- [ ] 是否避免在 `VkCommandBufferInheritanceInfo` 之外对 secondary command buffer 录制 query？[SPEC]

### 读取阶段

- [ ] host 读取前是否通过 fence / semaphore 或 `WAIT_BIT` 同步？
- [ ] stride 是否与 flags 匹配（64-bit / availability 会改变 stride）？[SPEC]
- [ ] 是否处理 `VK_NOT_READY` / `VK_ERROR_DEVICE_LOST` 返回值？[SPEC]

---

## 7. 高频错误

1. 未在每次使用前 reset query，导致结果累加或 `VK_NOT_READY`。[SPEC]
2. timestamp 未使用 `VK_QUERY_RESULT_64_BIT`，32 位结果可能截断 / wrap / saturate，影响测量精度（规范允许 32 位，但工程上不推荐）。[SPEC]
3. 对 timestamp 使用 `PARTIAL_BIT` 触发 VUID。[SPEC]
4. 在 host 读取 query 结果前未同步（fence / wait），导致读到未完成的数据。[SPEC]
5. pipeline statistics query 未启用 feature。[SPEC]
6. occlusion query 在 render pass 外调用 begin / end（部分场景合法但需注意 layout）。[ENGINE]
7. 同一 query index 被 in-flight 多帧并发使用，结果错乱。[ENGINE]
8. `stride` 与 flags 不一致，造成数据错位读取。[TOOL]
9. `vkGetQueryPoolResults` 在未 wait 时返回 `VK_NOT_READY` 被误判为错误。[ENGINE]
10. `vkResetQueryPool` 在 command buffer 引用 query 期间调用。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkQueryPoolCreateInfo-*`：queryType / queryCount / pipelineStatistics 合法性。
- `VUID-vkCmdBeginQuery-*` / `VUID-vkCmdEndQuery-*`：query 类型 / index / 是否在合法上下文。
- `VUID-vkCmdWriteTimestamp-*`：pipelineStage 是否合法。
- `VUID-vkCmdResetQueryPool-*`：是否在 render pass 内调用、index 范围。
- `VUID-vkGetQueryPoolResults-*`：flags / stride / dataSize 一致性。

### RenderDoc / AGI

- AGI Profiler 可直接显示 query 结果与时间戳区间，无需应用层 polling。[TOOL]
- AGI Timeline 中 timestamp query 对应的 GPU 时长可作为基准。[TOOL]
- RenderDoc 可在 draw call inspector 中查看 occlusion 结果（需应用正确录制 query）。[TOOL]

### 日志 / 代码检查

- 检查 `vkCreateQueryPool` 返回值。
- 检查 query index 分配是否 per-frame-in-flight 隔离。
- 检查 `vkGetQueryPoolResults` 的返回值是否为 `VK_SUCCESS` / `VK_NOT_READY`。
- 检查 `timestampPeriod` 是否参与时间换算。
- 检查 `pipelineStatisticsQuery` feature 是否在 `VkDeviceCreateInfo` 中启用。

---

## 9. 生命周期风险

### 创建时机

- Renderer 初始化时创建 occlusion / timestamp pool，按 in-flight 帧数 × 单帧 query 数分配 `queryCount`。[ENGINE]
- 运行时一般不动态创建 / 销毁 query pool，避免分配抖动。

### 使用时机

- 每帧 reset → begin / write → end → 提交。[SPEC]
- 同一 query index 在 in-flight 期间不可被多帧并发使用。[ENGINE]

### 销毁时机

- 必须等 GPU 不再访问该 pool（fence signal）。[SPEC]
- 应用退出或 renderer 重建时销毁。

### in-flight 风险

- Query pool 不存在 per-frame 引用问题，但 query index 必须按 frame-in-flight 分槽，否则上一帧未完成时下一帧 reset 会污染结果。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkGetQueryPoolResults` 不带 `WAIT_BIT` 时，结果可能 `VK_NOT_READY`；需通过 fence 等待 command buffer 完成后再读取。[SPEC]
- 带 `WAIT_BIT` 时阻塞 CPU 直到结果可用；适合调试，生产环境慎用。[ENGINE]
- `WITH_AVAILABILITY_BIT` + 轮询：避免阻塞，适合 per-frame 异步采集。[ENGINE]

### GPU-GPU 同步

- `vkCmdCopyQueryPoolResults` 把结果写入 buffer，下游读取该 buffer 必须通过 `vkCmdPipelineBarrier`（`srcStage = TRANSFER`，`srcAccess = TRANSFER_WRITE`）。[SPEC]
- 同一 command buffer 内 query 之间无需额外 barrier；跨 command buffer / 跨 submit 需 fence / semaphore 同步。[SPEC]

### Stage 选择

- `vkCmdWriteTimestamp` 的 pipelineStage 决定时间戳记录的语义位置：
  - `TOP_OF_PIPE`：命令开始执行时刻。
  - `BOTTOM_OF_PIPE`：命令完成时刻。
  - `VERTEX_SHADER` / `FRAGMENT_SHADER` / `COMPUTE_SHADER` / `TRANSFER` / `COLOR_ATTACHMENT_OUTPUT` 等：对应 stage 完成。[SPEC]
- 配对 stage 必须能正确包络被测量的 GPU 工作。[ENGINE]

---

## 11. Android 注意点

- Android 移动端 timestamp query 受 `timestampValidBits` 限制（部分设备为 32 / 36 / 64 位）。[ANDROID]
- `timestampPeriod` 在移动端可能为非整数 ns/周期，需用 double 累积。[ENGINE]
- occlusion query 在 tile-based renderer（TBDR）上可能不直观：硬件可能合并 / 丢弃 query，建议结合厂商文档。[TOOL]
- `pipelineStatisticsQuery` 在部分移动 GPU 不被 feature 支持，需查询 `VkPhysicalDeviceFeatures`。[ANDROID]
- `vkResetQueryPool`（1.2+）在主流 Android Vulkan 1.2+ 设备可用；旧设备需 `VK_EXT_host_query_reset` 或回退到 `vkCmdResetQueryPool`。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 避免每帧 `vkGetQueryPoolResults` 带 `WAIT_BIT`，会 stall 主线程。[ENGINE]
- 使用 ring 分配 query index，配合 `WITH_AVAILABILITY_BIT` 轮询，避免阻塞。[ENGINE]
- query pool 大小按 `framesInFlight × queriesPerFrame` 预分配。[ENGINE]

### GPU 侧

- occlusion query 在 tile-based GPU 上有额外开销（需 flush tile）；避免对每个 draw 启用。[ENGINE]
- timestamp query 数量本身无显著开销，但读取时机影响 CPU 路径。[ENGINE]
- pipeline statistics query 通常无显著 GPU 开销，可用于调试期统计。[ENGINE]

### 移动端

- 减少每帧 query 数量；按需开启 occlusion（如粒子 / 遮挡剔除验证）。[ENGINE]
- 用 AGI Profiler 替代手写 timestamp 测量 GPU 段耗时，避免应用层 polling。[TOOL]
- 性能 counter query（`VK_KHR_performance_query`）受厂商驱动支持，使用前需确认可用的 counter 与 pass 数。[ANDROID]

---

## 13. 专家经验

**经验**：
Query pool 是 Vulkan 中少有的“GPU 写、host 读”对象，最容易出错的不是 API 调用本身，而是同步语义：
- 默认情况下 `vkGetQueryPoolResults` 不会等待 GPU 完成；不带 `WAIT_BIT` 时返回 `VK_NOT_READY` 是合法状态，不是错误。
- in-flight 多帧时，必须按 frame index 分配 query 槽，否则下一帧 reset 会污染上一帧尚未读取的结果。
- timestamp query 工程上推荐用 64 位结果（规范允许 32 位但可能截断 / wrap / saturate）；`timestampPeriod` 是 ns-per-tick，需用浮点 / double 换算。[SPEC]
- `vkResetQueryPool`（1.2+）相比 `vkCmdResetQueryPool` 的优势在于不占用 command buffer，可在 host 完成批量重置，简化录制路径。
- occlusion query 在 TBDR 移动 GPU 上的语义可能与桌面 IMR 不同：某些驱动会在 resolve 时合并，需结合 AGI / 厂商文档验证。
- 与 AGI / Profiler 集成时，应用层 query 与 profiler timeline 应对齐，便于交叉验证 GPU 段耗时。

**适用条件**：
所有需要 GPU 侧计数 / 时间戳测量的场景，包括性能分析、遮挡剔除反馈、调试 GPU 段耗时。

**不适用情况**：
- 实时高频性能监控：应使用 profiler 工具或厂商 counter，避免应用层 query polling 影响。
- 移动端 TBDR 的精确遮挡判断：硬件可能延迟 / 合并 occlusion 结果，需配合厂商 best practice。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `buffer.md`（用于 `vkCmdCopyQueryPoolResults` 目标 buffer）
- `../03_command_buffer/command_buffer.md`
- `../08_synchronization/pipeline_barrier.md`
- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`（如有）

---

## 15. 需要回查官方文档的情况

1. `VkPhysicalDeviceLimits::timestampPeriod` 与 `timestampValidBits` 在目标设备的具体值。
2. `VK_KHR_performance_query` 的 pass 数、counter 列表与厂商特定用法。
3. `vkCmdWriteTimestamp` 在不同 stage 上的精确语义（特别是 sync2 引入的 stage mask 扩展）。
4. `VK_QUERY_RESULT_PARTIAL_BIT` 在 occlusion / pipeline stats 上的具体返回语义。
5. `vkResetQueryPool` 与 `vkCmdResetQueryPool` 在 command buffer 录制顺序上的约束。
6. Pipeline statistics query 各统计项的具体含义与计数单位。
7. occlusion query 在 render pass 内 / 外的合法路径，以及 `PRECISE_BIT`（`VK_EXT_conservative_rasterization`）的支持情况。
8. `vkCmdCopyQueryPoolResults` 与 `vkCmdCopyBuffer` 的同步 stage 差异。

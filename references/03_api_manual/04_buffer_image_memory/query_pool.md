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
   ├─ vkCmdResetQueryPool (重置为 unavailable，等待后续写入)
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

- query 可在确认本轮 reset 已执行后非阻塞读取，并检查 `VK_NOT_READY` / availability；完成等待是另一种路径，不是每次 host 读取的强制前提。[SPEC]
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
- `VK_KHR_performance_query`：性能计数器查询（厂商 / Counter-based profiling）。[SPEC]
- `VK_EXT_transform_feedback`：与 `VK_QUERY_TYPE_TRANSFORM_FEEDBACK_STREAM_EXT` 配合。
- Android 可用性必须按设备与队列查询：timestamp 需该队列非零 validBits，pipeline statistics 需支持并启用 feature；host reset 需对应版本/扩展及 hostQueryReset 启用；performance query 另查扩展、counter 与 pass。[ANDROID]

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
   - flags=0 不保证精确样本计数；精确结果另需 occlusionQueryPrecise feature 支持并启用，且 query 设置 PRECISE flag
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
5. 同一计时域、同一代且结果已就绪，确认区间短于可消歧回绕周期后：
   ticks = (timestamps[1] - timestamps[0]) mod 2^timestampValidBits
   duration_ns = ticks * timestampPeriod
   - validBits 来自所用 queue family；period 来自 VkPhysicalDeviceLimits
   - 64_BIT 只决定读取位宽，不扩展硬件计数器；未知回绕/时钟关系不输出时长
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
| `pipelineStage` | 时间戳按指定 stage 的执行作用域写入；`TOP_OF_PIPE` / `BOTTOM_OF_PIPE` 用于包络工作，但不等于单条命令的精确开始/结束时间。[SPEC] | 用 host 阶段或不可用 stage 触发 VUID。[SPEC] |
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
- [ ] secondary command buffer 的自身 query 与继承中的 active query 是否分别满足继承 feature、类型和冲突规则？[SPEC]

### 读取阶段

- [ ] host 是否确认本轮 reset 已执行，并选择完成等待或正确处理 `VK_NOT_READY` / availability 的非阻塞轮询？
- [ ] stride 是否与 flags 匹配（64-bit / availability 会改变 stride）？[SPEC]
- [ ] 是否处理 `VK_NOT_READY` / `VK_ERROR_DEVICE_LOST` 返回值？[SPEC]

---

## 7. 高频错误

1. 未将普通 timestamp query 重置到 unavailable 就再次写入，违反使用约束；不能把非法使用解释成合法累加或保证返回 NOT_READY。[SPEC]
2. timestamp 未使用 `VK_QUERY_RESULT_64_BIT`，32 位结果可能截断 / wrap / saturate，影响测量精度（规范允许 32 位，但工程上不推荐）。[SPEC]
3. 对 timestamp 使用 `PARTIAL_BIT` 触发 VUID。[SPEC]
4. 非阻塞读取时未检查 `VK_NOT_READY` / availability，或把上一轮 availability 当成本轮结果。[SPEC]
5. pipeline statistics query 未启用 feature。[SPEC]
6. 将 occlusion 查询作用域误当作 image layout 问题；应按 query 类型、render-pass/subpass 与 begin/end 对应关系逐项检查。[ENGINE]
7. 同一 query index 被 in-flight 多帧并发使用，结果错乱。[ENGINE]
8. `stride` 与 flags 不一致，造成数据错位读取。[TOOL]
9. `vkGetQueryPoolResults` 在未 wait 时返回 `VK_NOT_READY` 被误判为错误。[ENGINE]
10. `vkResetQueryPool` 在已提交且未完成的命令仍引用该范围时调用，或并发 get/reset 同一范围而未满足 host 同步。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkQueryPoolCreateInfo-*`：queryType / queryCount / pipelineStatistics 合法性。
- `VUID-vkCmdBeginQuery-*` / `VUID-vkCmdEndQuery-*`：query 类型 / index / 是否在合法上下文。
- `VUID-vkCmdWriteTimestamp-*`：pipelineStage 是否合法。
- `VUID-vkCmdResetQueryPool-*`：是否在 render pass 内调用、index 范围。
- `VUID-vkGetQueryPoolResults-*`：flags / stride / dataSize 一致性。

### RenderDoc / AGI

- 先核验目标版本、平台与采集模式是否实际提供 query/timing 数据；没有采集记录时不保证工具视图或可用指标。[TOOL]
- 工具时间线不是天然基准；区分采集扰动、CPU/设备计时域及校准误差，不把不同域直接相减。[TOOL]

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

- Query pool 本身也受已提交引用的生命周期约束；query index 必须保护代际与引用完成；按 frame-in-flight 分槽是可选实现，不能覆盖未完成的引用。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkGetQueryPoolResults` 不带 `WAIT_BIT` 可合法轮询，结果可能 `VK_NOT_READY`；不要求每次先等 fence，但必须确认本轮 reset 并检查结果可用性。[SPEC]
- 带 `WAIT_BIT` 时阻塞 CPU 直到结果可用；适合调试，生产环境慎用。[ENGINE]
- `WITH_AVAILABILITY_BIT` + 轮询：避免阻塞，适合 per-frame 异步采集。[ENGINE]

### GPU-GPU 同步

- `vkCmdCopyQueryPoolResults` 把结果写入 buffer，下游读取该 buffer 必须通过 `vkCmdPipelineBarrier`（`srcStage = TRANSFER`，`srcAccess = TRANSFER_WRITE`）。[SPEC]
- Query reset、产生结果、复制及槽复用必须满足各自顺序规则，不能仅凭位于同一 command buffer 就推断全部同步；跨 queue 使用相应 semaphore，host 回收使用完成点。[SPEC]

### Stage 选择

- `vkCmdWriteTimestamp` 的 pipelineStage 决定时间戳记录的语义位置：
  - `TOP_OF_PIPE`：顶部执行作用域边界，非单条命令精确开始时刻。
  - `BOTTOM_OF_PIPE`：底部执行作用域边界，非单条命令精确结束时刻。
  - `VERTEX_SHADER` / `FRAGMENT_SHADER` / `COMPUTE_SHADER` / `TRANSFER` / `COLOR_ATTACHMENT_OUTPUT` 等：对应 stage 完成。[SPEC]
- 配对 stage 必须能正确包络被测量的 GPU 工作。[ENGINE]

---

## 11. Android 注意点

- Android 移动端 timestamp query 受 `timestampValidBits` 限制（部分设备为 32 / 36 / 64 位）。[ANDROID]
- `timestampPeriod` 在移动端可能为非整数 ns/周期，需用 double 累积。[ENGINE]
- occlusion query 在 TBDR 上仍须遵守 query 规范；PRECISE 与非精确计数保证不同，开销和实现方式需结合厂商工具验证。[TOOL]
- `pipelineStatisticsQuery` 在部分移动 GPU 不被 feature 支持，需查询 `VkPhysicalDeviceFeatures`。[ANDROID]
- `vkResetQueryPool`（1.2+）在主流 Android Vulkan 1.2+ 设备可用；旧设备需 `VK_EXT_host_query_reset` 或回退到 `vkCmdResetQueryPool`。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 避免每帧 `vkGetQueryPoolResults` 带 `WAIT_BIT`，会 stall 主线程。[ENGINE]
- 使用 ring 分配 query index，配合 `WITH_AVAILABILITY_BIT` 轮询，避免阻塞。[ENGINE]
- query pool 大小按 `framesInFlight × queriesPerFrame` 预分配。[ENGINE]

### GPU 侧

- occlusion query 可能扰动 tile-based GPU 的执行；是否导致额外 tile 工作及其成本需目标实现实测，按采样需要选择频率。[ENGINE]
- timestamp query、同步和读取都可能扰动工作负载；不预设开销可忽略，需同条件对照启用/禁用测量。[ENGINE]
- pipeline statistics 的开销随实现与统计项变化；仅在实测后报告，不做普适低开销保证。[ENGINE]

### 移动端

- 减少每帧 query 数量；按需开启 occlusion（如粒子 / 遮挡剔除验证）。[ENGINE]
- 可比较平台工具与应用内计时路径，但先确认实际支持、时钟关联及测量扰动；不默认工具可替代全部应用查询。[TOOL]
- 性能 counter query（`VK_KHR_performance_query`）受厂商驱动支持，使用前需确认可用的 counter 与 pass 数。[ANDROID]

---

## 13. 专家经验

**经验**：
Query pool 是 Vulkan 中少有的“GPU 写、host 读”对象，最容易出错的不是 API 调用本身，而是同步语义：
- 默认情况下 `vkGetQueryPoolResults` 不会等待 GPU 完成；不带 `WAIT_BIT` 时返回 `VK_NOT_READY` 是合法状态，不是错误。
- in-flight 多帧时，槽分配必须保护 generation 与所有引用的完成点；按 frame index 分区是可选方案，不是规范唯一方案。
- timestamp query 工程上推荐用 64 位结果（规范允许 32 位但可能截断 / wrap / saturate）；`timestampPeriod` 是 ns-per-tick，需用浮点 / double 换算。[SPEC]
- `vkResetQueryPool`（1.2+）相比 `vkCmdResetQueryPool` 的优势在于不占用 command buffer，可在 host 完成批量重置，简化录制路径。
- occlusion query 的 Vulkan 保证不会因 TBDR/IMR 而失效；按是否启用 occlusionQueryPrecise 和 PRECISE flag 区分精确计数要求与保守结果。
- 与 profiler timeline 关联前先证明计时域关系并保留校准不确定度；没有校准/关联证据，不声称 CPU、GPU 或不同队列时间线已对齐。

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
7. occlusion query 在 render pass 内 / 外的合法路径，以及 `VK_QUERY_CONTROL_PRECISE_BIT`（`occlusionQueryPrecise` feature）的支持情况。
8. `vkCmdCopyQueryPoolResults` 与 `vkCmdCopyBuffer` 的同步 stage 差异。


<a id="query-generation-contract"></a>

## 16. Query generation、完成与测量合同

**条件**：timestampValidBits 必须非零，按 queue family 判定；pipelineStatisticsQuery、occlusionQueryPrecise、hostQueryReset 是不同 feature。timestamp 不用 begin/end，也不允许 PARTIAL_BIT。普通 query pool 初建需 reset；仅满足专门扩展条件的 QUERY_POOL_CREATE_RESET_BIT_KHR 路径例外，不能套到普通创建。[SPEC]

**正常路径**：每槽记录 generation 和覆盖所有引用的完成点：reset → begin/end 或 timestamp write → available → 获取/复制结果 → 消费结束 → 再 reset。vkResetQueryPool 要启用 hostQueryReset，所有引用该范围的已提交命令已完成，且不与其他线程 get/reset 同一范围重叠。vkCmdResetQueryPool 需正确设备顺序并在 render pass 外。池销毁等待所有已提交引用，而不是仅等待一个 query available。[SPEC]

**失败**：新一轮 GPU reset 尚未执行时，host 读到的 availability 可能来自上一轮；WAIT_BIT 也不能区分 generation。先证明 reset 已执行，再轮询本轮结果。VK_NOT_READY 是未就绪，不复用槽、不当作零时长；等待不可达结果可能永久阻塞。槽耗尽时延后采样/扩大合法容量，不覆盖 in-flight query。[SPEC][ENGINE]

**结果与单位**：按类型、统计项数量、64_BIT 和 WITH_AVAILABILITY_BIT 计算 dataSize/stride；availability 字段与所选结果位宽一致。普通 timestamp 差值按 timestampValidBits 做模差并乘 timestampPeriod（ns/tick），64-bit 结果不增加硬件 validBits；必须确保测量间隔短于可消歧回绕周期，不跨无校准时钟域直接相减。[SPEC]

**专项路径**：校准时间先枚举可用 time domains，调用 vkGetCalibratedTimestampsKHR/EXT 并记录 maxDeviation，CPU/GPU 对齐需包含不确定度。performance query 另枚举 counters、counter scope 与 pass count，获取 profiling lock 后才 begin command buffer；lock 在相关 CB 的 recording/executable/pending 状态都须持有，完成所有要求的 passes 后才解读结果。[SPEC]

**回退与验证**：不支持 timestamp/counter 时禁用该项或标记 CPU wall-time 为 CPU 测量，不伪称 GPU 时间。测试 reset 前旧 availability、延迟写入、两帧竞争、validBits 回绕、缺少 feature 和 profiling-lock timeout；对照有/无测量开销，工具捕获本身可能扰动结果。

固定依据：Vulkan 1.4.368，commit `fa30d4e312e843193601be7cb926c7e25d9ec885`；[queries#queries-operation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc#queries-operation)；[queries#queries-timestamps](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc#queries-timestamps)；[queries#profiling-lock](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc#profiling-lock)；[synchronization#calibrated-timestamps](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#calibrated-timestamps)。[SPEC]

<a id="delivery19-timestamp-query-family"></a>

## 17. Delivery19 普通 timestamp 查询族：有界 L1/L2

本合同覆盖普通 `VK_QUERY_TYPE_TIMESTAMP`、单设备单队列、command reset 与
host `vkGetQueryPoolResults`。不把 performance query、calibrated timestamp、
Video status、多队列时钟关联或 Vulkan SC 当作已完成。上节 1.4.368 范围合同
与本节实际工具 **1.4.309** 队列必须分开，不混合规范快照分母。

### 能力、状态与可执行决策

1. 先查询实际 queue family 的 `timestampValidBits` 和设备 `timestampPeriod`。
   validBits 为零即该队列不支持，不能借其他队列或品牌推定；缺失能力事实为
   UNKNOWN。验证 stage 对该队列合法；本族仅使用已检查队列上的 TOP/BOTTOM。
2. 普通新建 query 不能直接当成有结果。先录制并执行 reset，证明 reset 完成，
   再做不带 WAIT 的查询；本轮 unavailable 应作为 NOT_READY/availability=0
   处理，不读取结果占位值为耗时，也不视为错误修复成功。
3. 写入两 query、提交、完成等待后，读取同轮结果与 availability。读取成功和
   非零 availability 仍不能单独证明属于期望 generation；应用维护槽代际、
   reset 执行证明和所有引用完成点。旧 available + 新 reset 尚未执行即拒绝消费。
4. 普通 timestamp 只含一个结果整数。设元素宽度 W=4 或 8，带 availability
   时每 query 占 2W，否则 W；多 query 首址间距为 stride。本族只接收 count>=1，dataSize 至少覆盖
   `(queryCount-1)*stride + 单query字节数`。另查指针/stride对齐、池范围、
   availability空间、queryCount>1时非零stride，不能仅用 count*W 判断。
5. timestamp 禁止 PARTIAL；本族不静默忽略未知 flag。支持状态与 device API
   调用许可、查询结果就绪以及统计解释资格分别返回，不用一个 PASS 混淆。

| 1.4.309 规范义务 | 精确依据 / 边界 |
|---|---|
| firstQuery 在池内、firstQuery+count 不越界 | `VUID-vkGetQueryPoolResults-firstQuery-09436` / `09437` |
| count>1 的 stride 非零 | `VUID-vkGetQueryPoolResults-queryCount-09438` |
| timestamp 不允许 PARTIAL | `VUID-vkGetQueryPoolResults-queryType-09439` |
| 被读取 query 不得 uninitialized | `VUID-vkGetQueryPoolResults-None-09401` |
| 32/64 位数据指针及 stride 对齐 | `VUID-vkGetQueryPoolResults-flags-02828` / `00815` |
| availability 也必须容纳 | `VUID-vkGetQueryPoolResults-stride-08993` |
| 输出存储覆盖最后一项 | `VUID-vkGetQueryPoolResults-dataSize-00817` |
| 写入队列支持 timestamp、索引有效、query unavailable | `VUID-vkCmdWriteTimestamp-timestampValidBits-00829` / `query-04904` / `None-00830` |

代际一致、测量可解释性和短于回绕周期是明确的消费策略，不伪造额外 VUID。
该表是所列 API 的受限规则，不声称覆盖所有 query 类型或扩展 valid usage。

### 时间解释与证据

本族只对 64_BIT 结果进行时长换算；32 位结果仅验证布局/就绪，不假定截断或饱和行为可逆。
只有两端属于同一已证明计时域、同代且可用，并有独立区间上界证明其短于
`2^validBits * timestampPeriod`，才将模差换算为纳秒。缺少这些条件返回
UNKNOWN / NOT_READY / STALE，而不是输出零、负数或未经证明的百分比收益。
32 位读取不能保留超过其位宽的信息；64 位读取也不能扩大硬件 validBits。
TOP/BOTTOM 包络区间不等于某条 fill/dispatch 的独占执行时间。

配对测试执行 reset 完成→未写 query 读取→两 timestamp 包络 fill→fence→结果
与内容 readback，并独立检测非法 stride、dataSize、PARTIAL 的真实 Validation
拒绝。故障调用由 callback 中止；缺少期望诊断不能算负控通过。CPU 规则还应
拒绝旧代、缺失 reset 完成、不同计时域、回绕不明与未知 feature。CPU ICD 的
时间戳仅为该软件实现的 API 行为证据，不能称作物理 GPU 耗时或性能优化收益。

### 来源与兼容修正

- 正文：[Vulkan-Docs v1.4.309 queries](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/queries.adoc)，
  Git blob `fb4d544cba26c0bbbe982c1a82dbf45fc06d28fb`；重点为 query operation、
  results、wait-bit-not-set 与 timestamps 段。来源为 Khronos，CC-BY-4.0；本节为释义。
- 实际 VUID：SDK/Headers 的 `validusage.json` API 1.4.309，SHA256
  `f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7`。
  其中源 revision `43d153dd7f9f5e8b9f79d26d868c82a82b9ef80b` 不是本页正文的
  Vulkan-Docs commit，不能构造错误链接或宣称同一仓库 revision。
- 本次同步修正旧卡片中的 reset可用、所有Android功能可用、flags0精确计数、
  必须等待才能读取、无显著开销与直接时钟对齐等过度表述。保留合法非阻塞读取，
  将平台与测量成本改为查询/实测条件，不改变 Vulkan API，只收紧错误推断。

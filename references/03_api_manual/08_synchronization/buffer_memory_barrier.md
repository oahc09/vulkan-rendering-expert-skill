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
| `srcQueueFamilyIndex` / `dstQueueFamilyIndex` | 仅需要显式 ownership transfer 时填源与目标 family；普通不转移路径可填 `VK_QUEUE_FAMILY_IGNORED`。[SPEC] | 相等的有效 family index 不定义 ownership transfer；不能把不同 queue 误认成不同 family。[TOOL] |
| `buffer` / `offset` / `size` | 同步范围；`VK_WHOLE_SIZE` 表示从 offset 到末尾。[SPEC] | offset/size 越界或显式 size 为 0；不存在一般 barrier range 对齐要求。[TOOL] |
| `srcStageMask` / `dstStageMask`（在 vkCmdPipelineBarrier 中） | 决定 execution dependency 的范围。[SPEC] | stage 过宽导致气泡，过窄导致同步缺失。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否明确 producer 与 consumer 的 stage / access？
- [ ] 普通 EXCLUSIVE 跨 family 且需保留内容时，是否规划了匹配 release + acquire？CONCURRENT 与已启用 maintenance9 的精确例外另审。
- [ ] offset 是否小于 buffer size，size 是否为 VK_WHOLE_SIZE 或在剩余范围内且大于 0？

### 使用阶段

- [ ] Barrier 是否位于 producer 命令之后、consumer 命令之前？
- [ ] 无 ownership transfer 时是否使用 IGNORED 或满足规则的相等 family index？
- [ ] 不同 queue 的访问是否同步；仅需显式 family transfer 时，目标 acquire 是否匹配源 release 范围？

### 销毁阶段

- [ ] 无独立对象销毁；barrier 随 command buffer 生命周期结束而失效。

---

## 7. 高频错误

1. `srcAccessMask` 未包含 producer 实际的写入 flag，导致 consumer 读脏数据。[TOOL]
2. 把同 family 的不同 queue 当作必须进行 family ownership transfer；两 queue 的访问同步仍需单独满足。[TOOL]
3. 需要显式跨 family transfer 时只有 release 没有匹配 acquire，或 family index 填反。[TOOL]
4. `offset` / `size` 越界或显式 size 为 0，触发范围 validation error；不要套用 flush/invalidate 的 atom 对齐规则。[TOOL]
5. Host 写未 happens-before queue submit，或 non-coherent 写未正确 flush，或覆盖 in-flight 访问；不能仅因缺显式 HOST_WRITE barrier 就认定错误。[TOOL]
6. `dstStageMask` 设为 `TOP_OF_PIPE_BIT`，通常过度阻塞执行，且不能用该无访问阶段表达 consumer 的内存访问；按真实消费者设置 stage/access。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkBufferMemoryBarrier-offset-01187`、`size-01188`、`size-01189`：offset/size 范围；queue family index 另核其适用条款。
- `VUID-vkCmdPipelineBarrier-bufferMemoryBarrierCount-01178`：在使用 VkRenderPass 对象的 render pass instance 内调用时，不能包含 buffer memory barriers。 [官方 vkCmdPipelineBarrier 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdPipelineBarrier.html)。[SPEC]
- offset 必须小于 buffer 大小；size 为 VK_WHOLE_SIZE 或大于 0 且不超过 buffer 大小减去 offset。这里不是一条通用 offset/size 对齐规则。 [官方 VkBufferMemoryBarrier 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkBufferMemoryBarrier.html)。[SPEC]

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

- Barrier 只保证录制它的 command buffer 内部及同一 queue 的提交顺序；不能跨 queue 同步（跨 queue 需 semaphore；仅在跨 family 且该资源需要显式ownership时另做transfer）。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Buffer barrier 可包含 HOST access 内存依赖，但不让 CPU 阻塞等待完成；CPU 退休等待应使用覆盖相关工作的 fence 或 timeline semaphore。[SPEC]

### GPU-GPU 同步

- 同 queue 内建立 execution + memory dependency。[SPEC]
- 跨 queue 需满足执行/内存依赖；同 family 不需要 family ownership transfer。普通 EXCLUSIVE 跨 family 保留内容时另需 release/acquire；CONCURRENT 不需此 transfer，maintenance9 例外按精确 feature/property/usage 合同判断。[SPEC]

### 资源访问同步

- 精确限定 buffer range，避免全局 memory barrier 的过度刷新。[ENGINE]
- 已对 host domain available 且 happens-before queue submit 的 host 写，由提交建立到 device 的内存依赖，通常无需额外 HOST_WRITE barrier。Non-coherent 写仍需先 flush；特殊 non-temporal 写须满足 host 排序；不能覆盖尚未退休的 GPU 访问。没有该提交关系时另行建立所需依赖。[SPEC]

---

## 11. Android 注意点

- 移动端带宽受限，全局 memory barrier 会触发广泛 cache flush；优先使用 buffer barrier 精确限定范围。[ANDROID][ENGINE]
- 多 queue family 即使共享物理单元也不能免除适用的 ownership 合同；是否需要显式 transfer 由 sharing mode、保留内容及已启用的精确扩展例外决定。[ANDROID]
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
- 连续只读访问通常无需额外内存依赖；静态vertex/index buffer首次上传写→读仍需正确同步。[HEUR]

---

## 13. 专家经验

**经验**：
写 buffer barrier 前先回答四个问题：谁写、写什么范围、谁读、读什么范围。若 producer 与 consumer 在同一 queue family，直接用 `VK_QUEUE_FAMILY_IGNORED` 即可，不要炫技做 ownership transfer。若跨 queue 但同 family，不做ownership transfer；若跨 family 且需保留内容、没有maintenance9例外，release 与 acquire 必须成对，并且目标 queue 的提交必须等待源 queue 的 semaphore signal。

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


<a id="buffer-range-sync-contract"></a>

## 18. Buffer 范围与queue/family分离合同

**条件/正常路径**：buffer barrier offset相对buffer，不是allocation；offset小于buffer size，size为非零合法范围或WHOLE_SIZE。它不继承nonCoherentAtomSize的host flush对齐约束。producer TRANSFER_WRITE→consumer VERTEX_ATTRIBUTE_READ/INDEX_READ/SHADER_READ分别选真实stage/access，不能因最终用途只读而漏掉首次上传依赖。[SPEC]

**失败**：不同queue但同family需要semaphore访问同步，不需要ownership release/acquire。不同family的EXCLUSIVE保内容基线才需成对transfer；CONCURRENT仍需访问同步；maintenance9按 [ownership合同](synchronization2.md#maintenance-ownership-contract) 判断。buffer handle范围barrier不是所有底层alias的通用内存依赖。

**回退**：范围分析不充分时使用覆盖实际共享访问的global memory barrier并保持正确stage/access，或隔离alias；不能把host fence当device消费者的自动可见性保证。stage语义遵循 [barrier合同](pipeline_barrier.md#barrier-scope-contract)。

**验证**：测试非零bindOffset、子buffer范围边界、首次静态上传、同family两queue、跨family功能开关与alias；每种路径分别记录同步和所有权条件。

固定依据：Vulkan 1.4.368，commit fa30d4e312e843193601be7cb926c7e25d9ec885；[synchronization#synchronization-buffer-memory-barriers](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#synchronization-buffer-memory-barriers)；[resources#resources-sharing](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/resources.adoc#resources-sharing)。[SPEC]

## delivery19-transfer-contract: bounded L1/L2 fill/copy/readback

Scope: standard Vulkan, one transfer-capable queue, two non-overlapping bound
buffers, 256 bytes, coherent host-visible allocations. Companion cases19/transfer
is original deliberate fault injection, NOT an external production bug.

### Support, enablement, resources and ownership
Legacy vkCmdPipelineBarrier/fill/copy/fences need no synchronization2 feature.
A device API version alone does not enable synchronization2; its separate path
must query/enable the feature and resolve matching entry points. Command pool
and queue family must match and support transfers. Buffer usage, complete memory
binding, memoryTypeBits, alignment and fill four-byte restrictions still apply.

Command recording order alone does not establish transfer RAW visibility.
The fill writes source memory; copy reads it. Scope TRANSFER WRITE to TRANSFER
READ over the full source range, with TRANSFER stages for both operations.
A stage-only barrier is not a RAW memory dependency. An omitted access mask or
wrong range can leave a hazard despite the presence of a barrier.
Both family indices are IGNORED in this same-family path. This is NOT an
ownership release/acquire recipe: other families/queues require separately
scoped semaphore dependencies and ownership operations when applicable.

After copying, destination TRANSFER WRITE must be visible to HOST READ and the
submission fence must complete successfully before CPU access or destruction.
HOST_COHERENT removes explicit invalidate/flush needs, not execution/lifetime
dependencies. A noncoherent variant needs mapped-range invalidation after
completion, atom-size/allocation-boundary handling, and corresponding flush
rules for CPU writes. Do not merely relax the coherent allocation predicate.
The sample is single-threaded. Production host ownership must serialize
externally synchronized command pools, queue access and memory operations.
Fence completion here says nothing about presentation retirement or other queues.

### Implement, repair, reject and verify
1. Record real device/layer identity; enable SyncVal. Missing tools are BLOCKED.
2. Freeze baseline and run. Expect SYNC-HAZARD-READ-AFTER-WRITE. The callback
   returns VK_TRUE to abort the invalid copy. Zero output is therefore NOT
   evidence of actual undefined driver execution or a measured timing race.
3. Apply fix.patch, enabling the already-written precise source barrier. On the
   same runtime require no error callbacks and 64/64 words equal 0x12345678 after
   actual submission/fence completion.
4. Retain the barrier but erase its destination access mask: the independent
   mutant must restore the RAW hazard and fail the patched output gate.
5. Preserve source/patch/binary hashes and runtime identity. Compile, initialize,
   allocate, submit or wait failure stops acceptance. Never inherit old PASS.
6. Prefer the explicit dependency over global device-idle insertion. No speedup
   was measured. Broader barriers are diagnostic options, not proven production
   optimizations. Keep the known single-queue fallback when other scopes are
   unsupported or not established.

Timeout is not completion; device loss is not a successful wait. Do not recycle
resources or blindly retry stale work. This small repro exits on API failure;
production bounded cleanup/recovery and fault reporting remain unimplemented.
SyncVal does not prove all shader/host races or driver correctness, and the
software ICD does not certify physical GPUs. No timing/performance acceptance.

### Vulkan SC boundary
Shared synchronization concepts do not authorize copying this dynamic allocation,
creation and validation startup into SC. Resource reservation, offline pipelines,
allowed call phases and safety process require a separate scoped design. SC is
UNVERIFIED here, not supported or certified. The overall synchronization domain
also remains partially reviewed, despite this bounded L1/L2 contract.

Normative: [Execution and Memory Dependencies](https://docs.vulkan.org/spec/latest/chapters/synchronization.html#synchronization-dependencies)
and [Host Access](https://docs.vulkan.org/spec/latest/chapters/memory.html#memory-device-hostaccess).
Engineering cross-check: [Khronos examples](https://docs.vulkan.org/guide/latest/synchronization_examples.html).
Sources checked 2026-11-15. Local VVL1.4.309 cannot certify full coverage of the
frozen 1.4.368 registry.

<a id="delivery19-buffer-barrier-source-boundaries"></a>

### delivery19-buffer-barrier-source-boundaries

上述 host submission 与 family ownership 解释绑定 Vulkan-Docs 固定提交
`fa30d4e312e843193601be7cb926c7e25d9ec885`（Registry API 1.4.368），
`chapters/synchronization.adoc` SHA256
`7748c88e48007820179681ef4f82c1d2244afc5482b5bc0c13d370ef64821909`：
`[[synchronization-host-access-types]]`、`[[synchronization-submission-host-writes]]`、
`[[buffer-memory-barrier-ownership-transfer]]`。这是固定正文解释，不是 GPU 实测。

范围另由 API 1.4.309 的 validusage SHA256
`f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7`
中 `VUID-VkBufferMemoryBarrier-offset-01187`、
`VUID-VkBufferMemoryBarrier-size-01188`、
`VUID-VkBufferMemoryBarrier-size-01189`核对。
两个版本为分别绑定的来源，不能合称同一版本完整规范验收；
range 合法也不代表 stage/access、对象寿命、sharing 或完整同步全部合法。

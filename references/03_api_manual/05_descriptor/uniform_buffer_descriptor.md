# API Card: Uniform Buffer Descriptor

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorBufferInfo`（`UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC`） |
| 常用 API | `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

Uniform buffer descriptor 将 `VkBuffer` 的一段内存绑定到 shader 的 uniform 接口，用于传递变换矩阵、光照参数、材质常量等每帧或每 draw call 变化的数据。[SPEC]

---

## 2. 所属对象链路

```text
VkBuffer（VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT）
→ VkDescriptorBufferInfo（buffer / offset / range）
→ vkUpdateDescriptorSets（UNIFORM_BUFFER 或 UNIFORM_BUFFER_DYNAMIC）
→ vkCmdBindDescriptorSets（dynamic offset 可选）
→ Shader Uniform Block
```

### 上游依赖

- 已创建并绑定内存的 `VkBuffer`，usage 包含 `UNIFORM_BUFFER_BIT`。[SPEC]
- Descriptor set layout 声明了 `UNIFORM_BUFFER` 或 `UNIFORM_BUFFER_DYNAMIC`。[SPEC]

### 下游影响

- Shader 通过 uniform block 读取常量数据。
- `UNIFORM_BUFFER_DYNAMIC` 允许在 bind 时通过 `pDynamicOffsets` 改变 offset。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDescriptorBufferInfo`
- `VkWriteDescriptorSet`
- `VkBuffer`

### 常用 API

| API | 作用 |
|---|---|
| `vkUpdateDescriptorSets` | 将 buffer range 写入 descriptor set。[SPEC] |
| `vkCmdBindDescriptorSets` | 绑定 descriptor set；对 dynamic UBO 需额外提供 dynamic offset。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_push_descriptor` 允许不经过 descriptor set 直接推送 buffer descriptor。
- `VK_EXT_inline_uniform_block` 允许小量 uniform 直接内嵌在 pipeline layout 中。

---

## 4. 标准使用流程

```text
创建 VkBuffer 并指定 UNIFORM_BUFFER_BIT
→ 分配/映射/写入 uniform 数据
→ 构造 VkDescriptorBufferInfo（buffer / offset / range）
→ 构造 VkWriteDescriptorSet（descriptorType = UNIFORM_BUFFER 或 UNIFORM_BUFFER_DYNAMIC）
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ 若为 DYNAMIC，提供 pDynamicOffsets
→ Shader 读取 uniform block
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `buffer` | 必须是 uniform buffer。[SPEC] | 用普通 buffer 或未设置 usage 的 buffer。[TOOL] |
| `offset` | 必须按 `minUniformBufferOffsetAlignment` 对齐。[SPEC] | 偏移未对齐导致验证错误。[TOOL] |
| `range` | 必须大于 0 且不超过限制；`VK_WHOLE_SIZE` 可用但受对齐约束。[SPEC] | range 为 0 或超过 `maxUniformBufferRange`。[TOOL] |
| `descriptorType` | `UNIFORM_BUFFER` 固定 offset；`UNIFORM_BUFFER_DYNAMIC` 可在 bind 时改 offset。[SPEC] | 类型与 layout 声明不一致。[TOOL] |
| `pDynamicOffsets` | 与 dynamic descriptor 的 binding 顺序对应。[SPEC] | dynamic offset 数量或顺序错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Buffer usage 是否包含 `UNIFORM_BUFFER_BIT`？
- [ ] Offset 是否满足 `minUniformBufferOffsetAlignment`？
- [ ] Range 是否满足 `maxUniformBufferRange`？
- [ ] Layout 中的 type 与更新类型是否一致？

### 使用阶段

- [ ] 对 DYNAMIC UBO，是否提供了正确数量的 dynamic offset？
- [ ] Shader uniform block 的 set/binding 是否与 descriptor 一致？
- [ ] Uniform 数据在 GPU 读取前是否已写入并对 CPU 写入做 flush？

### 销毁阶段

- [ ] Buffer 在 GPU 使用完毕前不能销毁。[SPEC]

---

## 7. 高频错误

1. Buffer offset 未按 `minUniformBufferOffsetAlignment` 对齐。[TOOL]
2. `UNIFORM_BUFFER_DYNAMIC` 绑定但未提供 dynamic offset。[TOOL]
3. Dynamic offset 数量与 descriptor set 中 dynamic binding 数量不匹配。[TOOL]
4. Uniform buffer 的 range 超过 `maxUniformBufferRange`。[TOOL]
5. CPU 更新 host-visible buffer 后未 flush，GPU 读到旧数据。[TOOL]
6. 每对象创建一个独立 UBO buffer，导致分配碎片化。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorBufferInfo-offset-*`：offset 对齐。
- `VUID-VkDescriptorBufferInfo-range-*`：range 限制。
- `VUID-vkCmdBindDescriptorSets-pDynamicOffsets-*`：dynamic offset 数量与顺序。

### RenderDoc / AGI

- 查看当前绑定的 UBO 内容与 range。
- 检查 shader uniform block 的取值。

### 日志 / 代码检查

- 检查 `VkDescriptorBufferInfo` 字段。
- 检查 dynamic offset 数组构造。
- 检查 uniform buffer 的内存对齐与 flush。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建 uniform buffer 池；运行时从池中取 range 更新。[ENGINE]

### 使用时机

- 渲染时绑定 descriptor set，对 dynamic UBO 还需设置 offset。[SPEC]

### 销毁时机

- 确认 GPU 不再读取该 buffer 后销毁或复用。[SPEC]

### in-flight 风险

- Uniform buffer 被 command buffer 引用后，fence signal 前不能复用或销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 更新 host-visible uniform buffer 后，若 buffer 非 coherent，需 `vkFlushMappedMemoryRanges`。[SPEC]
- GPU 读取前，CPU 写入必须可见；通常通过 submit 顺序保证。

### GPU-GPU 同步

- Uniform buffer 通常只读；若同一 buffer被 GPU 写入后再作为 UBO 读取，需要 buffer barrier。[SPEC]

### 资源访问同步

- UBO 作为 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER` 使用，不需要 image layout，但需要 buffer 内存可见。[SPEC]

---

## 11. Android 注意点

- 移动端 `maxUniformBufferRange` 与 `minUniformBufferOffsetAlignment` 可能比 desktop 更严格，需运行时查询。[ANDROID]
- `UNIFORM_BUFFER_DYNAMIC` 可减少 descriptor set 数量，但 dynamic offset 必须在 bind 时提供，CPU 侧管理需小心。[ENGINE]
- 避免每 draw call 更新整个 descriptor set；优先使用 dynamic offset 或 push constant 传递少量变化数据。[ANDROID][ENGINE]

---

## 12. 性能注意点

### CPU 侧

- `vkUpdateDescriptorSets` 与 `vkCmdBindDescriptorSets` 是 CPU 常见热点；应批量更新、减少绑定切换。[ENGINE]
- 使用 `UNIFORM_BUFFER_DYNAMIC` 可在 bind 时切换 offset，减少 update 调用。[ENGINE]

### GPU 侧

- Uniform buffer 读取通常 cache 友好；过大的 uniform block 会增加 register pressure。[ENGINE]

### 移动端

- 尽量合并 per-draw 数据到统一 UBO 并用 dynamic offset 索引。[ENGINE]
- 对极少变化的数据使用 push constant 而非 UBO。[HEUR]

---

## 13. 专家经验

**经验**：
对每帧变化的 camera/light 参数，用单个大的 uniform buffer + `UNIFORM_BUFFER_DYNAMIC` 或 per-frame buffer ring；对 per-draw 的 transform/material 参数，也用类似策略。不要把每个对象都做成独立 buffer，否则分配与 descriptor 更新会成为 CPU 瓶颈。对齐要求一定要按 `minUniformBufferOffsetAlignment` 处理，不要硬编码。

**适用条件**：
需要向 shader 传递常量数据的场景。

**不适用情况**：
极少量变化数据可优先使用 push constant；大量结构化数据可考虑 storage buffer。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_set_layout.md`
- `descriptor_update.md`
- `descriptor_pool.md`
- `sampled_image_descriptor.md`
- `storage_buffer_image_descriptor.md`
- `../04_buffer_image_memory/buffer.md`
- `../04_buffer_image_memory/memory_allocation.md`
- `../06_pipeline/pipeline_layout.md`

---

## 15. 需要回查官方文档的情况

1. `minUniformBufferOffsetAlignment` 与 `maxUniformBufferRange` 的具体限制。
2. `UNIFORM_BUFFER_DYNAMIC` 的 dynamic offset 对齐与 binding 顺序规则。
3. Push descriptor 与 inline uniform block 的替代方案限制。
4. Host-visible coherent buffer 的 flush/invalidate 要求。
5. 不同驱动对大量 small UBO 分配的性能差异。

## delivery19-ordinary-ubo: consolidated bounded L1/L2 contract

**Scope:** ordinary non-null, non-sparse UNIFORM_BUFFER descriptor updates,
explicit range or WHOLE_SIZE, fixed single binding/set. Not dynamic descriptors,
indexing, update-after-bind, inline uniform blocks or descriptor-buffer API.
Those paths retain separate feature/layout/lifetime contracts, not implicit support.

### L1 invariants and sources
Ordinary UBO descriptors are core functionality; query the actual device limits,
not a vendor table. Match buffer UNIFORM_BUFFER usage and complete contiguous
memory binding. An offset must address inside the buffer and meet uniform-offset
alignment. Explicit range is nonzero and within remaining bytes; WHOLE_SIZE
means the remaining bytes, not unlimited access. Both forms must satisfy the
uniform-range limit. Recreating a device invalidates an old limits profile.

The destination layout type, shader stage visibility, pool descriptor/set budgets
and write count must match the actual binding. Consecutive-binding writes have
additional compatibility rules; the executable checker intentionally does not
claim them. Bind the matching layout at draw time and validate the shader's
interface separately. A successful descriptor update does not prove readable
memory, synchronization, matrix layout, dynamic-index bounds or correct pixels.

Do not rewrite an ordinary set while prohibited by command-buffer/pending use.
Separate per-frame sets or retire their consumers before reuse; serialize host
access where required. Preserve referenced resources through their GPU use.
Host-coherent allocation does not remove execution dependencies. Descriptor
metadata updates do not upload buffer content or flush noncoherent CPU writes.

### L2 implementation, diagnosis and fallback
1. Establish ownership and actual queried limits, buffer size/usage/binding,
   pool/set layout, shader interface and update-safe lifetime before publication.
2. Run the bounded descriptor19 checker. Missing facts stay UNKNOWN; rejected
   ranges are not silently clamped. Use explicit subranges when whole-buffer
   range exceeds the limit. Align suballocations with checked arithmetic.
3. Pair with cases19/descriptor: two positive updates and three negative updates
   must produce exactly matching rule/VVL diagnostic sets on one fixed runtime.
4. Keep source/binary hashes and actual layer/device metadata. Missing tools,
   changed identity or diagnostic disagreement stop the gate for investigation.
5. Keep ordinary per-frame descriptor sets as the simple fallback until a more
   complex binding path has separately enabled features and measured benefit.
6. Test the real renderer's shader/readback and in-flight retirement before
   shipping. The current tool pair only checks updates; no shader was executed.

**Completed matrix for this scope:** range/offset/effective-range rules and
positive/negative CPU tests; queried-limit real VVL update pairing; explicit
ownership/failure/fallback guidance. **Still open:** general layout/pool counts,
shader interface and access, in-flight integration, dynamic offsets and advanced
binding paths, device matrix, SC and external engineering acceptance. Therefore
this does not mark the entire descriptor family complete.

[Descriptor buffer ranges](https://docs.vulkan.org/refpages/latest/refpages/source/VkDescriptorBufferInfo.html)
and [write conditions](https://docs.vulkan.org/refpages/latest/refpages/source/VkWriteDescriptorSet.html),
checked 2026-11-15. Rule IDs 00340–00342, 00327, 00329–00330 and00332 are retained
for traceability. Local Validation1.4.309 and latest reference pages are recorded
as different versioned evidence, not one fully validated normative snapshot.

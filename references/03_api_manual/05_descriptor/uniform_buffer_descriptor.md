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
| `pDynamicOffsets` | 按所绑定 set 顺序、binding 编号、binding 内数组元素顺序展开。[SPEC] | dynamic offset 数量或顺序错误。[TOOL] |

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
3. Dynamic offset 数量与本次绑定 sets 中 dynamic descriptor 数组元素总数不匹配。[TOOL]
4. Uniform buffer 的 range 超过 `maxUniformBufferRange`。[TOOL]
5. CPU 更新 host-visible buffer 后未 flush，GPU 读到旧数据。[TOOL]
6. 每对象创建一个独立 UBO buffer，导致分配碎片化。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorBufferInfo-offset-*`：offset 对齐。
- `VUID-VkDescriptorBufferInfo-range-*`：range 限制。
- `VUID-vkCmdBindDescriptorSets-dynamicOffsetCount-00359`：数量；`pDynamicOffsets-01971`：UBO 对齐。合法偏移的语义顺序交换可能没有 VUID，必须由实际输出参考检测。

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

### delivery19-ordinary-ubo-lifetime: retirement is not reusable recording
An ordinary binding used by a pending command buffer cannot be updated
(VUID03047). The same descriptor value is not an exemption. A fence that actually
covers that submission can establish retirement; a stale generation or unrelated
queue's fence cannot. Track every referencing command buffer and serialize host
updates. Unknown reference inventory is not safe-to-update evidence.

After retirement, updating a set referenced by a recording/executable command
buffer can invalidate that command buffer. Reset/re-record the affected commands
before submission; merely observing a signaled fence does not restore their
recorded validity. Retain referenced resource lifetime and memory dependencies
separately. Advanced binding flags require their own enabled-feature and usage
contracts; this ordinary-binding planner deliberately refuses that scope.

The companion lifecycle planner distinguishes WAIT_RETIREMENT from
UPDATE_REQUIRES_RERECORD, and marks incomplete/stale scopes UNKNOWN. It consumes
caller-observed states; it does not discover queue completion or authorize raw
GPU operations by itself.

Normative: [update lifetime, recording invalidation and host synchronization](https://docs.vulkan.org/refpages/latest/refpages/source/vkUpdateDescriptorSets.html).

The opt-in descriptor_lifetime experiment now checks one concrete joint path:
compile/validate a compute shader reading a UBO into an SSBO, hold its submission
behind an unsignaled timeline wait, observe NOT_READY, and try the forbidden
ordinary update. Validation must report03047 before the callback aborts it.
Host signaling releases the wait; fence retirement and mapped output42 establish
that the first submission actually executed. A legal subsequent descriptor
replacement requires reset/re-record before the second submission returns99.
A wrong-output oracle must fail even with no validation diagnostic. Timeline
support is queried and explicitly enabled; absent capability blocks this test.

This measures one authored compute path on a CPU ICD, not generic multiqueue
retirement, production renderer integration, image quality or physical GPU
performance. No old “no shader executed” statement about the earlier update-only
probe should be interpreted as applying to this separate lifecycle experiment.

<a id="delivery19-dynamic-ubo-ring"></a>
## v1.0.19：动态 UBO 数组与退休槽位的三帧修复合同

配对 tests 的动态 UBO ring 场景连接实际 descriptor array、graphics shader、
dynamic offset 顺序和 fence 退休后重用，不再只验证 descriptor update 参数。
本合同限定一个普通 descriptor set、一个含两个 UNIFORM_BUFFER_DYNAMIC
元素的 binding，shader 用常量数组下标；不隐含 descriptor indexing、
update-after-bind、descriptor buffer 或并发更新支持。

### 字节布局、顺序与可见性必须分别证明

- `pDynamicOffsets` 按本次 set 顺序、每个 set 的 binding 编号、每个 binding
  的数组元素顺序展开。总数是动态 descriptor **元素** 数，不是 binding 数。
  两个合法对齐 offset 被交换仍可能符合 API，有效输出却错误；Validation
  零错误不能证明 offset 数组的业务语义正确。
- 每个有效起点是 descriptor base offset 加对应 dynamic offset；range
  不随偏移移动而缩小。实际 minUniformBufferOffsetAlignment、maxUniformBufferRange
  以及所需 dynamic/per-stage descriptor 限制先查询。ring stride 由对齐要求
  和已验证的 shader block 布局共同确定，不把 std140 或 CPU struct 大小猜成
  所有设备通用的槽位间距。
- 00359 对应 dynamic offset 数量；01971 对应 UBO dynamic offset 对齐；
  01979 对应有效起点加 range 不超过 buffer；WHOLE_SIZE 的动态偏移还受到
  06715 限制。uint32 dynamic offset 与 VkDeviceSize 算术宽度分别检查，
  缺配置或算术溢出不能默认为有效。
- shader SPIR-V 的 block 成员 offset 与实际上传参数配对，两个数组元素由
  独立 CPU 参考分别使用；参考不能直接复制实际回读像素或交换后的 offsets。

### A、B、退休后复用 A

帧 A 读取第一组槽位，帧 B 读取第二组；第三帧仅在 A 所有消费者的 fence
完成之后改写并复用 A 槽位。保留 frame/slot/generation、绑定 offset、上传
参数、完成事实与逐像素输出，不能用一个最后的 DeviceWaitIdle 将未证明的
槽位复用伪装成已退休。此受限顺序路径不代表真正多帧并行已测。

coherent 内存不免除宿主写入与 GPU 使用的生命周期约束。已提交且未完成的
槽位不得覆写；旧 generation 的观察不能批准新一代资源。这里的 pending/
stale-generation 策略负控是 CPU 合同测试，不冒充已安全执行了 GPU 数据竞争。

### 原创缺陷、最小补丁与反证

固定的合法 offset 顺序交换作为仓内原创语义缺陷；在同一实际工具 cohort 下
保留错误前的输出和无 Validation 错误事实，应用最小顺序补丁后重新编译并
核验三帧输出。补丁作用范围、前后源码与工具 hash 必须明确，不能将外部项目
缺陷、未测平台或性能收益附会到该实验。

API 负控另选单独的对齐或有效范围错误。只有实际 alignment 大于1时，offset1
才可作为对齐违规；构造足够 buffer 避免同时越界。callback 中止无效 bind
后丢弃 command buffer，不继续提交。错误 CPU 参考也必须失败。明确区分
合法但语义错误、API 违规、未知能力与真正通过，禁止合并成一个笼统 PASS。

来源：[Khronos Vulkan-Docs descriptorsets v1.4.309](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/descriptorsets.adoc)，
Git blob `3cad5740ff176cbef473b1c4914d56c7810281d0`，CC-BY-4.0，本节为释义。
VUID 来自独立 1.4.309 validusage SHA256
`f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7`。
仅 CPU ICD/coherent、普通数组与顺序退休正确性；noncoherent、真实多队列竞争、
全部绑定模型、物理/移动性能、SC、外部工程及 Live/盲测仍未验。

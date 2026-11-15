# API Card: Memory Allocation

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | `VkDeviceMemory` |
| 常用 API | `vkAllocateMemory` / `vkFreeMemory` / `vkMapMemory` / `vkUnmapMemory` / `vkFlushMappedMemoryRanges` / `vkInvalidateMappedMemoryRanges` / `vkGet*MemoryRequirements` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkDeviceMemory` 是 Vulkan 中实际持有 GPU 内存的对象；`VkImage` / `VkBuffer` 必须先绑定到 `VkDeviceMemory` 才能被 GPU 访问，而选择合适的 memory type 是性能与正确性的关键。[SPEC]

---

## 2. 所属对象链路

```text
VkImage / VkBuffer
→ vkGet*MemoryRequirements
→ vkAllocateMemory (选择 memoryTypeIndex)
→ vkBind*Memory
→ GPU Access
→ vkFreeMemory (GPU idle 后)
```

### 上游依赖

- 已创建 `VkImage` 或 `VkBuffer`。[SPEC]
- 已查询 `VkMemoryRequirements`（size / alignment / memoryTypeBits）。[SPEC]
- 已查询 physical device memory properties 获取 memory type flags。[SPEC]

### 下游影响

- Image / buffer 能否被 CPU map、是否 device-local、是否 cached 都由 memory type 决定。
- 内存分配粒度影响 sub-allocation / aliasing 策略。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDeviceMemory`
- `VkMemoryRequirements` / `VkMemoryRequirements2`
- `VkPhysicalDeviceMemoryProperties`
- `VkMemoryAllocateInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkGetPhysicalDeviceMemoryProperties` | 查询设备支持的 memory type / heap。[SPEC] |
| `vkGetBufferMemoryRequirements` / `vkGetImageMemoryRequirements` | 查询资源内存需求。[SPEC] |
| `vkAllocateMemory` | 分配 device memory。[SPEC] |
| `vkFreeMemory` | 释放 memory。[SPEC] |
| `vkMapMemory` / `vkUnmapMemory` | CPU 映射 / 解除映射 host-visible memory。[SPEC] |
| `vkFlushMappedMemoryRanges` | 非 coherent memory 写入后 flush 到 device。[SPEC] |
| `vkInvalidateMappedMemoryRanges` | 非 coherent memory 读取前 invalidate cache。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_dedicated_allocation`：为特定 image / buffer 申请 dedicated memory，某些 GPU 性能更好。[GUIDE]
- `VK_EXT_memory_budget`：查询 heap 预算，避免 OOM。[TOOL]
- Android 可用性：核心功能全部可用；budget 扩展视设备支持。[ANDROID]

---

## 4. 标准使用流程

```text
创建 VkImage 或 VkBuffer
→ vkGet*MemoryRequirements(resource, &memReq)
→ vkGetPhysicalDeviceMemoryProperties(physicalDevice, &memProps)
→ 根据 memoryTypeBits 和需求选择 memoryTypeIndex:
    需要 CPU 写入: HOST_VISIBLE
    需要 CPU 无需 flush: HOST_COHERENT
    需要 GPU 最优: DEVICE_LOCAL
    需要 CPU 读取: HOST_VISIBLE (可能还需 HOST_CACHED)
→ vkAllocateMemory(..., &allocInfo, ..., &memory)
→ vkBind*Memory(resource, memory, offset)
→ 使用资源
→ 销毁时:
    等待 GPU idle
    → 解绑 / 销毁 image 或 buffer
    → vkFreeMemory
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `size` | 绑定范围须容纳 requirements.size；绑定 offset 按 requirements.alignment 对齐，不据此要求 allocationSize 为该 alignment 的整数倍。[SPEC] | allocationSize − offset 小于 requirements.size。[TOOL] |
| `alignment` | 绑定 offset 必须是 alignment 的倍数。[SPEC] | offset 未对齐导致 validation error 或崩溃。[TOOL] |
| `memoryTypeBits` | 32 位掩码，表示该资源可使用的 memory type index。[SPEC] | 选择不在掩码中的 memory type。[TOOL] |
| `propertyFlags` | `DEVICE_LOCAL` / `HOST_VISIBLE` / `HOST_COHERENT` / `HOST_CACHED` / `LAZILY_ALLOCATED`。[SPEC] | 需要 CPU map 但选非 HOST_VISIBLE；需要 GPU 性能但选非 DEVICE_LOCAL。[TOOL] |
| `allocationSize` | 可分配多个资源到同一块 memory 的不同 offset，普通子分配须满足alignment与范围隔离；显式alias需遵循单独的alias合同。[SPEC] | sub-allocation 未对齐或重叠。[SPEC] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否查询了 resource 的 memory requirements？
- [ ] 选择的 memory type index 是否在 `memoryTypeBits` 中？
- [ ] 分配的 size 是否满足 requirement？
- [ ] 绑定 offset 是否满足 alignment？

### 使用阶段

- [ ] CPU 写入 host-visible memory 后是否需要 flush？
- [ ] CPU 读取前是否需要 invalidate？
- [ ] 同一块 memory 被多个 resource 绑定时是否不重叠？

### 销毁阶段

- [ ] 是否等待 GPU idle 后再 free memory？
- [ ] 是否先销毁 resource 再 free memory？（resource 销毁不释放 memory）[SPEC]

---

## 7. 高频错误

1. 选择不满足 `memoryTypeBits` 的 memory type。[SPEC]
2. 需要 CPU 写入但选择非 `HOST_VISIBLE` memory。[TOOL]
3. 非 coherent memory 写入后未 flush，GPU 读到旧数据。[TOOL]
4. 绑定 offset 未按 alignment 对齐。[TOOL]
5. 同一块 memory sub-allocate 时发生重叠。[SPEC]
6. memory 仍被设备使用就 free，或 free 后继续使用仍绑定的 image / buffer。[SPEC]
7. 分配大量小 memory 对象导致分配失败或开销高。[ENGINE]
8. 未处理 `VK_ERROR_OUT_OF_DEVICE_MEMORY`。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkBindBufferMemory-*` / `VUID-vkBindImageMemory-*`：memory type、offset、alignment。
- `VUID-vkMapMemory-*`：memory 是否 HOST_VISIBLE。
- `VUID-vkFreeMemory-memory-00677`：memory 仍被 resource 使用。

### RenderDoc / AGI

- 查看 resource 的 memory type 和 heap。
- AGI 可查看内存预算和 heap 使用情况。

### 日志 / 代码检查

- 检查 `vkAllocateMemory` 返回值。
- 检查 `memoryTypeBits` 与选择的 index。
- 检查 map / flush / invalidate 调用。

---

## 9. 生命周期风险

### 创建时机

- Image / buffer 创建后。
- 使用 memory allocator 时，大内存块预先分配，运行时再 sub-allocate。

### 使用时机

- Image / buffer 被 GPU 访问期间 memory 必须有效。
- CPU 通过 mapped pointer 访问 host-visible memory。

### 销毁时机

- 工程上可选择先销毁所有绑定 resource 再 free，便于管理；这是保守策略，不是规范强制顺序。[ENGINE]
- free 前必须确认全部设备访问已结束；允许 memory 仍绑定资源，但这些资源之后不得再使用。[SPEC]

### in-flight 风险

- Memory 的所有已提交引用必须完成；覆盖这些使用的 fence/timeline/idle 可提供完成证明，不要求某个特定 fence 必须 signal。[SPEC]
- 即使 resource 已销毁，若 memory 仍被 pending command buffer 引用，free 也会出问题。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Host-visible coherent memory：省去显式 flush/invalidate，不省去 host/device 执行同步；CPU 写入须 happens-before 正确提交，且不得覆写 GPU 仍在使用的区域。[SPEC]
- Host-visible non-coherent memory：需要 `vkFlushMappedMemoryRanges`。[SPEC]
- CPU 读取 GPU 写入：通常需要 barrier + invalidate。[SPEC]

### GPU-GPU 同步

- Memory 绑定本身不涉及同步；同步由 barrier / semaphore 管理。
- 同一 memory 内不同 resource 的访问也需要 barrier 同步。[SPEC]

---

## 11. Android 注意点

- Android 设备通常有 device-local 和 host-visible 两个主要 heap。[ANDROID]
- 移动端 OOM 风险高，应使用 `VK_EXT_memory_budget` 监控 heap 使用。[ANDROID]
- 大纹理上传应使用 staging buffer（host-visible）→ device-local image。[ENGINE]

---

## 12. 性能注意点

### CPU 侧

- `vkAllocateMemory` 次数应尽量减少；推荐使用 Vulkan Memory Allocator (VMA) 或自定义 sub-allocator。[ENGINE]
- 大量小 allocation 会增加驱动开销和内存碎片。[ENGINE]

### GPU 侧

- Device-local memory 通常 GPU 访问最快。[ENGINE]
- Host-visible memory 可能通过 PCIe / 统一内存访问，带宽较低。[HEUR]

### 移动端

- 移动端通常为统一内存架构，但 `DEVICE_LOCAL` 仍可能表示 GPU 侧更优 cache / tiling。[ENGINE]
- `LAZILY_ALLOCATED` 可用于瞬态 attachment 节省内存，但支持情况有限。[VENDOR]

---

## 13. 专家经验

**经验**：
生产环境不要直接为每个 image / buffer 调用 `vkAllocateMemory`。应使用 VMA 或自定义 allocator 管理内存池，根据 `DEVICE_LOCAL` / `HOST_VISIBLE` / `HOST_COHERENT` 等 flag 分类管理 heap。

**适用条件**：
任何非玩具级 Vulkan 项目，资源数量超过几十个或需要动态加载资源。

**不适用情况**：
教学示例、资源极少且生命周期固定的简单 demo。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `image.md`
- `image_view.md`
- `buffer.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. 目标 physical device 的 memory type / heap 分布。
2. Dedicated allocation 在目标 GPU 上的收益。
3. `LAZILY_ALLOCATED` 在目标设备上的支持情况。
4. Non-coherent memory 的 alignment 和 flush 规则。

<a id="acceleration-structure-resource-contract"></a>
## Acceleration Structure 资源与退休合同

复用 allocator、generation、驻留/取消与完成点，不创建第二套资源管理器。[ENGINE]

1. 固定 geometry/index/instance 格式、范围、地址、owner 和 generation；调用 `vkGetAccelerationStructureBuildSizesKHR`，分别预算 AS、buildScratchSize、updateScratchSize、几何输入及 compaction 新旧并存峰值。[SPEC]
2. AS backing buffer 使用 `ACCELERATION_STRUCTURE_STORAGE`；build input 使用 `ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY` 与需要的 `SHADER_DEVICE_ADDRESS`，scratch 使用 `STORAGE_BUFFER` / device address。按实际 device-address 分配路径启用 allocation 标志，不能把所有 AS backing buffer 的 buffer address 与 AS address 混为一谈。[SPEC]
3. `vkCreateAccelerationStructureKHR` 后取得 AS device address；scratch **地址**按 `minAccelerationStructureScratchOffsetAlignment` 对齐，整个所需范围有效，不能只对齐 buffer offset。并行 build 的 scratch 区间不得重叠；串行复用必须建立 AS build 读写依赖。[SPEC]
4. 一次 `vkCmdBuildAccelerationStructuresKHR` 内多项 build 不隐含排序。BLAS→依赖该 BLAS 的 TLAS 分开并显式同步；TLAS instance buffer 与引用 BLAS 分别有效。[SPEC]
5. UPDATE 要求原 build 的 ALLOW_UPDATE 与规范约束。刚体变化常只更新 TLAS instance transform；几何变化须检查 geometry type/count、primitive count、格式、flags、active/inactive 与 topology 等完整约束，不满足就 BUILD。不把允许 update 等同于一定快。[SPEC][ENGINE]
6. compaction 仅对允许压缩的 build 查询大小；build→property query→读结果→新目标分配→compact copy→依赖→发布新 BLAS 地址→更新 TLAS。旧 AS/descriptor/TLAS 保留到全部 in-flight 引用完成；压缩不是原地改地址。[SPEC]
7. build 完成后按规范释放/复用输入和 scratch；query hit-shading 仍读的顶点/索引/材质/纹理单独保持驻留。活跃 TLAS 仍引用的 BLAS 不因主相机剔除、取消加载或单个 Engine 退出而销毁。[SPEC][ENGINE]
8. 新代构建失败/预算超限时不发布半成品；保留旧合法代或切换基础档。完整退休跟踪所有 queue 的消费者，CPU 回调返回不是 GPU 完成。[ENGINE]

[同步表](../08_synchronization/pipeline_barrier.md#as-build-query-dependencies)。最小验证含 scratch 重叠拒绝、无 ALLOW_UPDATE 拒绝、拓扑变化 rebuild、compaction 后 pending TLAS 保留旧地址，以及共享 BLAS 的两个 View 先后销毁。[ENGINE]

依据：[固定 AS 规范](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/accelstructures.adoc)。上限/更新约束随选用扩展变化，以上清单不是完整 VUID 替代品。


<a id="memory-host-alias-contract"></a>

## 16. Host cache、alias 与退役合同

**条件**：先求 requirements 的 size/alignment/memoryTypeBits，再筛内存属性；coherent 与 device-local 是独立属性。dedicated allocation 要求优先于子分配策略，bufferImageGranularity 与 nonCoherentAtomSize 是不同约束。[SPEC]

**正常路径**：上传要求 host 写 happens-before 提交：host 写 → 非 coherent flush → queue submission → device 读；提交建立所需 host→device domain operation，普通提交前写无需仅为上传额外插入 HOST barrier。回读为 device 写 → 对 HOST_READ 的内存依赖 → fence/timeline 等待覆盖该工作 → 非 coherent invalidate → host 读。映射/解除映射本身不等待 GPU，也不隐式 flush。每个 mapped range 的 offset 相对 VkDeviceMemory，不是 buffer 子分配起点。[SPEC]

**边界与失败**：flush/invalidate offset 必须按 nonCoherentAtomSize 对齐；size 为 atom 整数倍，或范围到 allocation 末尾；还须落在已映射区间，VK_WHOLE_SIZE 同样遵守映射末端条件。向外取整不能越出映射区。共享同一个 atom 的子分配要作为同步单元管理，不能在另一线程/设备仍写该 atom 时 invalidate；coherent 不消除数据竞争。[SPEC]

**Alias 正常路径**：检查每个别名资源各自 requirements、memory type、dedicated/alias image flags；混合 linear/non-linear 还需考虑 bufferImageGranularity 扩展后的重叠。切换 A→B 时等待 A 的最后访问并建立覆盖底层共享内存的依赖；image 另处理 layout 和内容有效性，不能把仅指定 A handle 的 buffer barrier 当作对所有别名的万能依赖。重新绑定普通 non-sparse 资源不是 alias 技巧。[SPEC]

**回退**：无法证明 alias 内容一致或独占时使用独立 allocation/不重叠子分配；OOM 先回收已退役缓存、缩减可选资源，再报告失败，不释放 pending 分配。预算查询是估计，不保证分配成功。[ENGINE]

**验证**：测试原子大小边界（offset=atom−1、末尾非整 atom、局部映射）、两个邻接子分配竞争、A/B 重叠切换及延迟 GPU 完成；记录 validation 与字节校验结果。仅有文本检查不是 GPU 验证。

固定依据：Vulkan 1.4.368，commit `fa30d4e312e843193601be7cb926c7e25d9ec885`；[memory#memory-device-hostaccess](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory.adoc#memory-device-hostaccess)；[resources#resources-memory-aliasing](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/resources.adoc#resources-memory-aliasing)；[synchronization#synchronization-submission-host-writes](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#synchronization-submission-host-writes)。[SPEC]


<a id="sparse-residency-contract"></a>

## 16. Sparse binding / residency / mip tail 合同

**条件**：sparseBinding 允许非连续绑定与重绑定，不自动允许非驻留访问。部分驻留另需 sparseResidencyBuffer / sparseResidencyImage2D / sparseResidencyImage3D 和相应 sample-count feature；aliased sparse bindings 另查 sparseResidencyAliased。先查精确 image format/type/samples/usage/tiling 的 sparse properties，再以实际资源查询 sparse memory requirements。队列必须含 VK_QUEUE_SPARSE_BINDING_BIT。[SPEC]

**正常路径**：创建带 SPARSE_BINDING_BIT（需要部分驻留时加 SPARSE_RESIDENCY_BIT）的资源 → 查询普通及 sparse requirements → 分配页面 → vkQueueBindSparse → semaphore 等待绑定完成 → 上传/访问。即使同一个 queue，sparse binding 与 command buffer 执行也不自动排序。重绑/解绑要先等待所有旧访问结束，再让新使用等待 bind 完成；vkFreeMemory 不会自动解绑。[SPEC]

**Mip tail**：按 aspect 处理 imageMipTailFirstLod、imageMipTailSize、imageMipTailOffset、imageMipTailStride。尾部只能走 VkSparseImageOpaqueMemoryBindInfo，不能当普通 tile 交给 VkSparseImageMemoryBind。SINGLE_MIPTAIL_BIT 表示全 array 共用一尾；否则 layer 偏移为 imageMipTailOffset + layer * imageMipTailStride。metadata aspect 也走 opaque bind，并加 VK_SPARSE_MEMORY_BIND_METADATA_BIT。[SPEC]

**失败与回退**：只有 sparse binding 而没有 residency 时，不允许把未绑定洞当成可读零页；residencyNonResidentStrict 决定非驻留访问的严格行为，不能把未驻留读值泛化为零。缺少格式支持、粒度不合或页面分配失败时使用完整常驻普通资源/降分辨率；不可把 feature 不支持计为成功稀疏运行。[SPEC][ENGINE]

**验证**：覆盖单尾/逐层尾/metadata、边缘 tile 粒度、同队列 bind→使用、跨队列重绑、全部消费者退役后回收。保存 feature/property、bind 参数、分配与完成点日志；无相应设备时 Device=UNVERIFIED。

固定依据：Vulkan 1.4.368，commit `fa30d4e312e843193601be7cb926c7e25d9ec885`；[sparsemem#sparsememory-resource-binding](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/sparsemem.adoc#sparsememory-resource-binding)；[sparsemem#sparsememory-memory-partially-resident](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/sparsemem.adoc#sparsememory-memory-partially-resident)；[sparsemem#sparsememory-physicalprops](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/sparsemem.adoc#sparsememory-physicalprops)。[SPEC]


<a id="mapped-range-edge-contract"></a>

## 18. 局部映射、atom共享与alias边界

**条件**：分别保存 allocationSize、mapOffset/mapSize、resource bindOffset 和 suballocation offset；VkMappedMemoryRange.offset 相对整个allocation。VK_WHOLE_SIZE 在flush/invalidate中到当前mapping末端，不必是allocation末端。[SPEC]

**正常路径**：先把dirty范围换算为allocation坐标，再向nonCoherentAtomSize对齐；必须完全落入当前mapping。有限size为atom倍数，或offset+size恰到allocation末端；WHOLE_SIZE要求mapping末端为atom边界或allocation末端。例：atom=128，allocation=1000，map=[128,1000)，offset=896,size=104合法末尾；map=[128,950)的WHOLE_SIZE末端不满足边界，不能逃避约束。[SPEC]

**失败边界**：flush一个字节会使所在完整atom按host写访问参与同步，即使相邻字节值未改也可能与device访问race。invalidate前存在未flush的host写会使内容undefined；不得把invalidate当flush替代。map/unmap/flush/invalidate不自动等待device工作。[SPEC]

**Alias**：重叠绑定不保证两个不同image有可互读表示。只有符合规范alias consistency条件时才保留内容；其他切换视内容为未定义并初始化新资源，image需各自合法layout。混合linear/nonlinear按bufferImageGranularity扩展范围判断潜在alias；dedicated allocation条件仍独立检查。[SPEC]

**回退**：扩大到合法完整mapping或重新选择atom对齐子分配；无法协调同atom多owner时隔离分配。不能把向外取整后超出mapping的range提交给API。

**验证**：测试allocation末尾非整atom、map末尾非整atom、负向/溢出范围、WHOLE_SIZE与局部mapping、邻接两个owner、alias失效后重新初始化；记录精确offset/size，不只记录buffer局部偏移。

固定依据：Vulkan 1.4.368，commit fa30d4e312e843193601be7cb926c7e25d9ec885；[memory#memory-device-hostaccess](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory.adoc#memory-device-hostaccess)；[memory#memory-device-unmap-does-not-flush](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory.adoc#memory-device-unmap-does-not-flush)；[resources#resources-memory-aliasing-consistency](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/resources.adoc#resources-memory-aliasing-consistency)。[SPEC]

## Delivery19 mapped-memory visibility contract (bounded L1/L2)

**Capability first.** Query actual memory properties and intersect memory type
indices with each resource's `memoryTypeBits`. A host-visible type without
HOST_COHERENT is required to claim noncoherent visibility execution. Headers,
CPU arithmetic, or coherent flush calls cannot establish that capability. If no
compatible type exists, report `UNAVAILABLE_NOT_RUN` for that path; do not change
memory flags in evidence or substitute a coherent success.

**Ranges.** `VkMappedMemoryRange.offset` is allocation-relative, not buffer-local.
Account for the binding/suballocation offset first. The allocation must be mapped.
The offset must align to nonCoherentAtomSize (00687); explicit ranges must remain
inside the mapping (00685). Explicit size must be atom-aligned unless the range
ends at allocation end (01390). WHOLE_SIZE ends at the current mapping end, not
unconditionally allocation end; its offset must be in that mapping (00686), and
mapping end must be atom-aligned or equal allocation end (01389). Check arithmetic
before narrowing to VkDeviceSize. Expanding a dirty span to atoms may require a
larger mapping; never clamp to an arbitrary unaligned partial mapping boundary.
A valid numerical range alone is not synchronization permission.

**Upload.** Serialize relevant host accesses and retire conflicting device uses.
Flush noncoherent writes before the consuming submission's dependency chain.
Unmap is not a replacement for flush. Atom expansion affects neighboring bytes
for synchronization purposes, so sharing one atom between unrelated live
suballocations requires ownership coordination, not merely byte-disjoint writes.
Coherence removes the explicit cache-maintenance requirement, not execution
ordering or lifetime obligations.

**Readback.** Establish the device-write to host-read memory dependency, wait for
the associated completion, then invalidate noncoherent ranges before host reads.
Invalidation is not a device wait. Do not invalidate over unflushed host writes;
keep upload and readback ownership explicit. Mapping alone is not invalidation.
Fence evidence must cover the actual uses and object generations, not another
queue or a reused handle. Device loss or failed flush/invalidate/wait fails the
path; do not consume a stale readback as success.

Paired `tools/mapped_memory19.py` returns bounded numerical/ownership obligations,
not proof of GPU state. `cases19/mapped_memory` records queried capabilities and
actual tested branches separately. External/sparse memory, device groups,
concurrent atom sharing, mobile hardware, full SC and external-engine acceptance
remain outside this slice.

Sources: [mapped-range VUIDs](https://docs.vulkan.org/refpages/latest/refpages/source/VkMappedMemoryRange.html),
[flush semantics](https://docs.vulkan.org/refpages/latest/refpages/source/vkFlushMappedMemoryRanges.html),
[invalidate dependency chain](https://docs.vulkan.org/refpages/latest/refpages/source/vkInvalidateMappedMemoryRanges.html).
These live normative pages are distinct from the frozen registry snapshot and
from the actual Validation layer version recorded by the probe.


<a id="delivery19-ordinary-memory-binding"></a>

### delivery19-ordinary-memory-binding

普通 non-sparse、非 external/protected/disjoint/tile-memory 绑定先核资源自身查询到的
requirements：memoryTypeIndex 对应位必须位于 memoryTypeBits，memoryOffset 小于
allocationSize 且为 alignment 的整数倍，requirements.size <= allocationSize − memoryOffset。
不能用 buffer 创建 size 或 texture 像素字节估计代替 requirements.size，
不能从 offset alignment 推导 allocationSize 必须同样对齐。
非 sparse 资源一旦绑定过 memory 不可用再次 bind 来重定位，free 原 memory 也不恢复可绑定资格。

requiresDedicatedAllocation 为真时必须使用该资源专属分配；仅 prefersDedicatedAllocation
不等同强制要求。普通 dedicated 绑定还须核对分配记录中的目标对象一致、memoryOffset=0。
dedicated image alias 等扩展例外另行证明，不能从此普通合同默认放行。
专属 allocationSize 还须按版本单独核验：普通 dedicated 的02964/02965在固定368
要求 >= requirements.size，而独立309同编号要求等于 requirements.size；
不能把368允许的额外字节分配直接下推到309合同。

普通非 alias 子分配不能仅检查字节范围不重叠：同 allocation 中同时使用的相邻
linear/non-linear 资源还须检查 bufferImageGranularity 页隔离。此值不是
nonCoherentAtomSize，也不是每个 allocationSize 的通用对齐单位；同类资源或
不同时使用的受控 alias 路径条件不同，需分别证明。

free 前所有已提交、经 buffer/image 引用 memory 的命令必须完成（00677）。
规范允许 memory 仍绑定资源时 free，但之后不得继续使用那些资源；实现可延迟实际
payload 释放到全部绑定对象销毁。先销毁对象再 free 是可选保守工程策略，不是唯一合法顺序。
这也不批准销毁正在使用的资源、保留失效 mapped pointer 或伪造完成证明。

固定 Vulkan-Docs1.4.368 commit `fa30d4e312e843193601be7cb926c7e25d9ec885`：
`chapters/resources.adoc` SHA256 `de7c50943e022c508b369a605ce05b20cc7376274d1e4ecb1d67234698732a7a`，
Resource Memory Association / bufferImageGranularity 原文及 commonvalidity/bind_buffer_common.adoc、
bind_image_common.adoc；`chapters/memory.adoc` SHA256
`a7f291992b45e3c783afd7f379361a1b20471c0d0675267b841e24395c3c593d` 的 vkFreeMemory。
另独立1.4.309 validusage SHA256
`f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7` 中
vkBindBufferMemory 的07459/01031/01035/01036/01037/01444/01508及
vkFreeMemory-memory-00677；368 alignment/bounds 条款已随 tile-memory 分支改号，
两版本不能混用编号或推断全部条款等价。此处不是实际分配成功、内存驻留或整族验收证明。

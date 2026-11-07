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
| `size` | 必须满足 resource 的 memory requirements size，且按 alignment 对齐。[SPEC] | 分配 size 小于 requirement。[TOOL] |
| `alignment` | 绑定 offset 必须是 alignment 的倍数。[SPEC] | offset 未对齐导致 validation error 或崩溃。[TOOL] |
| `memoryTypeBits` | 32 位掩码，表示该资源可使用的 memory type index。[SPEC] | 选择不在掩码中的 memory type。[TOOL] |
| `propertyFlags` | `DEVICE_LOCAL` / `HOST_VISIBLE` / `HOST_COHERENT` / `HOST_CACHED` / `LAZILY_ALLOCATED`。[SPEC] | 需要 CPU map 但选非 HOST_VISIBLE；需要 GPU 性能但选非 DEVICE_LOCAL。[TOOL] |
| `allocationSize` | 可分配多个资源到同一块 memory 的不同 offset，但需满足 alignment 和非重叠。[SPEC] | sub-allocation 未对齐或重叠。[SPEC] |

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
6. 销毁 memory 前未销毁绑定的 image / buffer。[SPEC]
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

- 所有绑定 resource 销毁后。
- 必须等 GPU 完成访问。[SPEC]

### in-flight 风险

- Memory 被 command buffer 引用后，fence signal 前不能 free。[SPEC]
- 即使 resource 已销毁，若 memory 仍被 pending command buffer 引用，free 也会出问题。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Host-visible coherent memory：CPU 写入后 GPU 立即可见。[SPEC]
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

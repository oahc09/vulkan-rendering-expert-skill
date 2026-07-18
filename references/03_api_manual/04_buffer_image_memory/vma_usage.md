# API Card: VMA (Vulkan Memory Allocator)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | VMA (Vulkan Memory Allocator) |
| 常用 API | `vmaCreateAllocator` / `vmaCreateBuffer` / `vmaCreateImage` / `vmaMapMemory` / `vmaUnmapMemory` / `vmaDestroyBuffer` / `vmaDestroyImage` / `vmaDefragment` |
| 适用平台 | 通用 |
| 来源等级 | `[GUIDE] [ENGINE] [TOOL] [HEUR]` |
| 适用 Vulkan 版本 | VMA 库，支持 Vulkan 1.0+ |

---

## 1. 一句话定位

VMA（Vulkan Memory Allocator）是 AMD 维护、GPUOpen 开源的事实标准 Vulkan 内存分配库，封装了 memory requirements 查询、memory type 选择、sub-allocation、defragmentation 与统计，把“为 `VkBuffer` / `VkImage` 选 memory type + 分配 + 绑定”三步合并为一次 `vmaCreateBuffer` / `vmaCreateImage` 调用。[GUIDE]

---

## 2. 所属对象链路

```text
VkInstance / VkPhysicalDevice / VkDevice
→ vmaCreateAllocator (VmaAllocator)
→ vmaCreateBuffer / vmaCreateImage (VkBuffer/VkImage + VmaAllocation 一次产出)
→ vmaMapMemory (CPU 写入) / vmaUnmapMemory
→ vkCmdBind* / shader access
→ vmaDestroyBuffer / vmaDestroyImage (同时销毁资源与 allocation)
→ vmaDestroyAllocator (最后)
```

### 上游依赖

- 已创建 `VkInstance` / `VkPhysicalDevice` / `VkDevice`。[SPEC]
- 已获取 physical device memory properties（VMA 内部查询）。[GUIDE]
- 推荐：启用 `VK_KHR_get_memory_requirements2`、`VK_KHR_dedicated_allocation`、`VK_EXT_memory_budget`、`VK_KHR_bind_memory2` 等扩展并传入 `VmaAllocatorCreateInfo`。[GUIDE]

### 下游影响

- VMA 接管 memory type 选择与 sub-allocation，决定资源位于 device-local / host-visible 哪个 heap。[GUIDE]
- 资源销毁必须走 `vmaDestroyBuffer` / `vmaDestroyImage`，不能只用 `vkDestroyBuffer` / `vkDestroyImage`（会泄漏 allocation）。[GUIDE]

---

## 3. 核心对象与 API

### 核心 VMA 对象

- `VmaAllocator`
- `VmaAllocatorCreateInfo`
- `VmaAllocation`
- `VmaAllocationCreateInfo`
- `VmaAllocationInfo`（查询结果）
- `VmaBudget` / `VmaStatistics` / `VmaTotalStatistics`
- `VmaPool` / `VmaPoolCreateInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vmaCreateAllocator` | 创建 allocator，绑定 device 与扩展。[GUIDE] |
| `vmaDestroyAllocator` | 销毁 allocator；必须先销毁所有 allocation。[GUIDE] |
| `vmaCreateBuffer` | 一次性完成 `vkCreateBuffer` + 查询 mem req + 分配 + `vkBindBufferMemory`。[GUIDE] |
| `vmaCreateImage` | 同上，针对 `VkImage`。[GUIDE] |
| `vmaDestroyBuffer` | 同时销毁 `VkBuffer` 与 `VmaAllocation`。[GUIDE] |
| `vmaDestroyImage` | 同上，针对 `VkImage`。[GUIDE] |
| `vmaMapMemory` | 映射 allocation 整体到 CPU 指针。[GUIDE] |
| `vmaUnmapMemory` | 解除映射。[GUIDE] |
| `vmaFlushAllocation` / `vmaInvalidateAllocation` | non-coherent memory 的 flush / invalidate 包装。[GUIDE] |
| `vmaGetAllocationInfo` | 查询 allocation 的 offset / size / memory type。[GUIDE] |
| `vmaDefragment` / `vmaDefragmentationBegin` / `vmaDefragmentationEnd` | 内存碎片整理。 |
| `vmaGetBudget` / `vmaGetHeapBudgets` / `vmaCalculateStatistics` / `vmaCalculatePoolStatistics` | 预算与统计。 |
| `vmaCreatePool` / `vmaDestroyPool` | 自定义内存池。 |
| `vmaCreateBufferWithAlignment` / `vmaAllocateMemory` / `vmaAllocateMemoryPages` | 进阶用法。 |

### 相关扩展 / 版本

- VMA 2.x：`VMA_MEMORY_USAGE_GPU_ONLY` / `CPU_ONLY` / `CPU_TO_GPU` / `GPU_TO_CPU` 枚举式用法。[GUIDE]
- VMA 3.x：引入 `VMA_MEMORY_USAGE_AUTO` + `VMA_ALLOCATION_CREATE_HOST_ACCESS_*_BIT` flag 组合式用法，取代旧枚举；推荐新代码使用 `AUTO`。[GUIDE]
- VMA 内部按需启用 `VK_KHR_dedicated_allocation`、`VK_KHR_bind_memory2`、`VK_EXT_memory_budget`、`VK_AMD_device_coherent_memory`、`VK_KHR_maintenance4` 等。[GUIDE]
- `vmaDefragment`（2.x）在 3.x 中被 `vmaDefragmentationBegin` + `vmaDefragmentationEnd` 取代；使用前需确认 VMA 版本。[GUIDE]
- Android 可用性：完全可用；推荐配合 `VK_EXT_memory_budget` 监控移动端 OOM。[ANDROID]

---

## 4. 标准使用流程

```text
1. 创建 VkInstance / VkDevice（启用 VMA 推荐扩展，可选）
2. vmaCreateAllocator(&createInfo, &allocator)
   - createInfo.physicalDevice / device / instance
   - createInfo.pVulkanFunctions（动态链接传 NULL 即可，静态链接需提供）
   - createInfo.flags（如 VMA_ALLOCATOR_CREATE_KHR_DEDICATED_ALLOCATION_BIT /
     VMA_ALLOCATOR_CREATE_EXT_MEMORY_BUDGET_BIT）
3. 创建 buffer / image:
   vmaCreateBuffer(allocator, &vkBufferCreateInfo, &vmaAllocCreateInfo,
                   &buffer, &allocation, &allocInfo)
   - vmaAllocCreateInfo.usage = VMA_MEMORY_USAGE_AUTO（3.x）或 GPU_ONLY / CPU_TO_GPU（2.x）
   - 需要 CPU 访问: 加 VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT /
                          HOST_ACCESS_RANDOM_BIT
   - 需要 dedicated: VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT
4. CPU 写入（如 uniform / staging）:
   vmaMapMemory(allocator, allocation, &pData)
   memcpy(pData, ...)
   vmaUnmapMemory(allocator, allocation)
   （non-coherent 由 VMA 自动 flush，HOST_ACCESS_RANDOM 需手动 invalidate）
5. GPU 使用: vkCmdBindVertexBuffers / vkCmdBindDescriptorSets / shader 访问
6. 销毁: vmaDestroyBuffer(allocator, buffer, allocation)
         vmaDestroyImage (allocator, image, allocation)
7. 最后: vmaDestroyAllocator(allocator)
   - 必须等 GPU idle 且所有 allocation 已销毁
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VmaAllocatorCreateInfo::flags` | 启用 dedicated allocation / memory budget 等优化。[GUIDE] | 启用了 budget flag 但 device 未启用 `VK_EXT_memory_budget`。[TOOL] |
| `VmaAllocatorCreateInfo::pVulkanFunctions` | 动态链接传 NULL；静态链接或自定义 loader 需提供函数表。[GUIDE] | 静态链接时传 NULL 导致符号未解析。 |
| `VmaAllocationCreateInfo::usage` | 3.x 用 `VMA_MEMORY_USAGE_AUTO`；2.x 用 `GPU_ONLY` / `CPU_TO_GPU` 等。[GUIDE] | 混用 2.x 枚举与 3.x flag；选错导致 GPU 资源落在 host-visible heap。[ENGINE] |
| `VmaAllocationCreateInfo::flags` | `HOST_ACCESS_SEQUENTIAL_WRITE_BIT`（顺序写，如 upload）/ `HOST_ACCESS_RANDOM_BIT`（读写，需 cached）/ `DEDICATED_MEMORY_BIT` / `MAPPED_BIT`（持久映射）。[GUIDE] | 需要随机读却只给 `SEQUENTIAL_WRITE`（non-cached 读慢）；用 `MAPPED_BIT` 但忽略 invalidate 时机。[TOOL] |
| `VmaAllocationCreateInfo::preferredFlags` | 优先 `DEVICE_LOCAL` 等，best-effort。[GUIDE] | requiredFlags 与 preferredFlags 误用导致分配失败。 |
| `VmaAllocationCreateInfo::memoryTypeBits` | 限制可选 memory type 掩码。[GUIDE] | 误把 buffer 的 mem req bits 套到 image 上。 |
| `VmaAllocationInfo::memoryType` | 实际选中的 memory type index；可校验是否落 device-local。[GUIDE] | 不校验导致资源意外落在 host-visible heap。 |
| `VmaAllocationInfo::pMappedData` | 启用 `MAPPED_BIT` 时返回持久映射指针。[GUIDE] | 误用持久映射指针在 non-coherent memory 上不 flush。 |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VmaAllocatorCreateInfo` 的 instance / physicalDevice / device / vulkanApiVersion 是否一致？[GUIDE]
- [ ] 启用的 VMA flag 对应的 device extension 是否已启用？[GUIDE]
- [ ] `vmaCreateBuffer` / `vmaCreateImage` 的 `VkBufferCreateInfo` / `VkImageCreateInfo` 字段是否合法（VMA 不校验，透传给 `vkCreate*`）？[SPEC]
- [ ] `usage` + `flags` 组合是否匹配实际访问模式？[GUIDE]
- [ ] 是否检查返回值（`VkResult`）？

### 使用阶段

- [ ] `vmaMapMemory` 后是否对应 `vmaUnmapMemory`？（可重复 map / unmap，但需配对）[GUIDE]
- [ ] non-coherent memory + `HOST_ACCESS_RANDOM` 读取前是否 invalidate？[SPEC][GUIDE]
- [ ] 同一 allocation 是否在 GPU 仍访问时被 CPU 写入（无同步）？[SPEC]
- [ ] `MAPPED_BIT` 持久映射的 allocation 是否在 GPU 写入后正确 barrier？[SPEC]

### 销毁阶段

- [ ] 是否用 `vmaDestroyBuffer` / `vmaDestroyImage` 而非裸 `vkDestroy*`？[GUIDE]
- [ ] 销毁前是否等 GPU idle / fence signal？[SPEC]
- [ ] `vmaDestroyAllocator` 是否在所有 allocation 销毁后？[GUIDE]
- [ ] defragmentation 是否在 GPU 仍访问目标资源时执行？[GUIDE]

---

## 7. 高频错误

1. 用 `vkDestroyBuffer` 销毁 VMA 创建的 buffer，泄漏 `VmaAllocation`（VMA 无法回收）。[GUIDE][TOOL]
2. 需要 CPU 写入但未加 `HOST_ACCESS_*` flag，VMA 选了 device-only memory，`vmaMapMemory` 返回 `VK_ERROR_MEMORY_MAP_FAILED`。[TOOL]
3. `HOST_ACCESS_RANDOM` 资源未 invalidate 就读，读到旧数据（non-coherent）。[SPEC]
4. 3.x 项目误用 2.x 的 `VMA_MEMORY_USAGE_GPU_ONLY` 枚举（3.x 仍兼容但被 deprecated）。[GUIDE]
5. 启用 `VMA_ALLOCATOR_CREATE_EXT_MEMORY_BUDGET_BIT` 但 device 未启用 `VK_EXT_memory_budget` 扩展，初始化失败。[TOOL]
6. `vmaDefragment` 在 VMA 3.x 中被废弃，调用旧 API 编译报错或行为不同。[GUIDE]
7. 大量小 allocation 未启用 dedicated allocation / pool，导致 sub-allocation 碎片或 metadata 开销高。[ENGINE]
8. 在 GPU 仍访问 allocation 时调用 `vmaDestroyBuffer`，与裸 Vulkan 同样会 device-lost。[SPEC]
9. 移动端把高频 GPU 读写的资源放在 host-visible heap（误用 `CPU_TO_GPU`），带宽与功耗受损。[ANDROID][ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- VMA 透传 `vkCreateBuffer` / `vkCreateImage` / `vkAllocateMemory` / `vkBind*Memory`，所有相关 VUID 仍生效。[TOOL]
- `VUID-vkBindBufferMemory-*` / `VUID-vkBindImageMemory-*`：memory type / offset / alignment（VMA 自动满足，但 custom pool 配置错误时仍可能触发）。
- `VUID-vkMapMemory-memory-00683`：map 非 host-visible memory（VMA 通常先返回错误，但若绕过仍会触发）。

### RenderDoc / AGI

- RenderDoc 显示 `VkDeviceMemory` 与绑定资源；VMA 的 sub-allocation 表不可见，需配合 `vmaGetAllocationInfo`。
- AGI 可查看 memory heap 占用、budget；用于定位移动端 OOM 与带宽热点。[AGI]
- VMA 内置 `vmaBuildStatsString` 可导出 JSON 统计，配合工具可视化碎片。[TOOL]

### 日志 / 代码检查

- 检查 `vmaCreateBuffer` / `vmaCreateImage` 返回值。
- 调用 `vmaGetAllocationInfo` 校验 `memoryType` 是否符合预期（device-local / host-visible）。
- 启用 VMA 的 `VMA_RECORDING_ENABLED` 可回放分配序列定位泄漏。[TOOL]
- 定期调用 `vmaCalculateStatistics` 监控 total allocated / block count 是否持续增长（泄漏信号）。[ENGINE]

---

## 9. 生命周期风险

### 创建时机

- allocator 在 device 创建后即可创建。[GUIDE]
- buffer / image allocation 按需创建；推荐使用 `VmaPool` 管理同类资源。[GUIDE]

### 使用时机

- allocation 被 GPU 访问期间必须存活；CPU 通过 mapped pointer 访问 host-visible allocation。[SPEC]

### 销毁时机

- 必须等 GPU 不再访问（fence signal）。[SPEC]
- 必须用 `vmaDestroyBuffer` / `vmaDestroyImage` 成对销毁资源与 allocation。[GUIDE]
- `vmaDestroyAllocator` 必须在所有 allocation 销毁后。[GUIDE]

### in-flight 风险

- allocation 被 command buffer 引用（通过其绑定的 buffer / image）后，fence signal 前不能销毁。[SPEC]
- defragmentation 移动 allocation 数据期间，原资源必须不被 GPU 访问。[GUIDE]

---

## 10. 同步风险

### CPU-GPU 同步

- VMA 不提供同步；CPU 写入 mapped memory 后，GPU 读取仍需 barrier / semaphore / fence。[SPEC]
- coherent memory（VMA `AUTO` + `HOST_ACCESS_SEQUENTIAL_WRITE` 通常选 coherent）CPU 写入后 GPU 立即可见，但 GPU 完成写入后 CPU 读取仍需 invalidate / barrier。[SPEC]
- non-coherent memory：VMA 在 `vmaUnmapMemory` 时自动 flush（2.x）；3.x `HOST_ACCESS_SEQUENTIAL_WRITE` 自动 flush，`HOST_ACCESS_RANDOM` 需手动 `vmaInvalidateAllocation`。[GUIDE]

### GPU-GPU 同步

- 与裸 Vulkan 相同；VMA 不干预资源访问同步。[SPEC]
- 同一 allocation 内多个 sub-allocated 资源的访问仍需 barrier。[SPEC]

### 资源访问同步

- `vmaMapMemory` 本身不同步；CPU 与 GPU 并发访问 mapped memory 是数据竞争，需 fence / barrier。[SPEC]
- defragmentation 内部使用 staging + barrier，但仍要求调用方确保 GPU 不访问目标资源。[GUIDE]

---

## 11. Android 注意点

- 移动端通常为统一内存架构，但 `DEVICE_LOCAL` 仍代表 GPU 侧更优 cache / tiling；VMA `AUTO` 默认会把 GPU 资源放 device-local。[ANDROID][ENGINE]
- 大纹理上传：staging allocation（`AUTO` + `HOST_ACCESS_SEQUENTIAL_WRITE_BIT`）→ device-local image → `vmaDestroyBuffer` 释放 staging，是标准模式。[ENGINE]
- 移动端 OOM 风险高：启用 `VMA_ALLOCATOR_CREATE_EXT_MEMORY_BUDGET_BIT` + `VK_EXT_memory_budget`，定期 `vmaGetBudget` 监控。[ANDROID]
- 部分 Android 设备 `vkAllocateMemory` 单次大块（>256 MB）可能失败；VMA 默认 256 MB block 大小可调，必要时自定义 `VmaPool`。[VENDOR][ANDROID]
- pause / resume 后无需重建 allocator（device 存活）；若 device lost 则必须销毁 allocator 重建。[ANDROID]
- AGI 可关联 VMA stats string 与 trace，定位 allocation 来源。[AGI]

---

## 12. 性能注意点

### CPU 侧

- VMA sub-allocation 显著减少 `vkAllocateMemory` 次数，是相对裸 Vulkan 的最大 CPU 收益。[ENGINE]
- `vmaCreateBuffer` / `vmaCreateImage` 一次调用完成多步，减少用户代码错误。[GUIDE]
- 高频创建 / 销毁应使用 `VmaPool` 预分配块，避免 metadata 锁竞争。[ENGINE]
- `vmaMapMemory` / `vmaUnmapMemory` 每次 map 都有开销；频繁更新的 uniform 推荐 `MAPPED_BIT` 持久映射 + ring buffer。[ENGINE]

### GPU 侧

- 资源落在 device-local heap 是 GPU 性能关键；用 `vmaGetAllocationInfo` 校验 `memoryType`。[ENGINE]
- dedicated allocation 对大纹理 / attachment 可能更优（`VK_KHR_dedicated_allocation`）。[GUIDE]
- defragmentation 本身有 GPU 拷贝开销，仅在长时间运行后碎片严重时执行。[ENGINE]

### 移动端

- 统一内存架构下，host-visible + device-local 可能不可兼得；按访问模式选择。[ANDROID]
- Tile-based GPU 上，attachment 应优先 device-local + `LAZILY_ALLOCATED`（若支持）。[VENDOR]
- 避免把 GPU 频繁读写资源放 host-visible heap，否则功耗与带宽受损。[ANDROID][ENGINE]

---

## 13. 专家经验

**经验**：
生产项目应默认使用 VMA 而非裸 `vkAllocateMemory`。新代码（VMA 3.x）统一用 `VMA_MEMORY_USAGE_AUTO` + flag 组合：GPU 资源 `AUTO`；CPU 上传 `AUTO` + `HOST_ACCESS_SEQUENTIAL_WRITE_BIT`；CPU 读写 `AUTO` + `HOST_ACCESS_RANDOM_BIT`；持久映射 uniform `AUTO` + `SEQUENTIAL_WRITE` + `MAPPED_BIT`。把高频更新资源用 `VmaPool` + ring buffer 管理。定期 `vmaCalculateStatistics` 监控泄漏，长跑场景（如编辑器）按需 `vmaDefragmentationBegin` / `End`。staging buffer 模式：上传完立即 `vmaDestroyBuffer` 释放 staging。Android 必须启用 memory budget 监控。

**适用条件**：
任何非教学级 Vulkan 项目；资源数量大、动态加载、需要内存监控与碎片整理。

**不适用情况**：
极简 demo（一两个资源）；需要完全控制 memory layout 的特殊场景（如已有自定义 sub-allocator）；Vulkan 1.0 无任何推荐扩展且驱动 buggy。

**来源**：`[GUIDE][ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `memory_allocation.md`
- `buffer.md`
- `image.md`
- `image_view.md`
- `copy_blit_resolve.md`
- `host_image_copy.md`
- `../08_synchronization/pipeline_barrier.md`
- `../03_command_buffer/command_buffer.md`

---

## 15. 需要回查官方文档的情况

1. VMA 版本（2.x vs 3.x）的具体 API 差异，尤其 `vmaDefragment` → `vmaDefragmentationBegin` / `End` 的迁移路径与废弃版本号。
2. `VMA_MEMORY_USAGE_AUTO` 在 3.x 中选择 memory type 的具体算法（优先级表）。
3. 各 `VMA_ALLOCATION_CREATE_HOST_ACCESS_*` flag 对应的 memory property（coherent / cached）选择规则。
4. `VmaPool` 自定义 block size / memory type index 在目标 GPU 的最优配置。
5. `VK_EXT_memory_budget` 在目标 Android 设备的返回值含义与 budget 估算算法。
6. `vmaDefragmentationBegin` 的 flag（`VMA_DEFRAGMENTATION_FLAG_*`）与 GPU 拷贝语义。
7. `VK_AMD_device_coherent_memory` / `VK_KHR_maintenance4` 在 VMA 内部的启用条件与收益。
8. VMA 对 `VK_KHR_external_memory` / Android hardware buffer（`AHardwareBuffer`）的集成边界。

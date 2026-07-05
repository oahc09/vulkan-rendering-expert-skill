# API Card: VkBuffer

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | `VkBuffer` |
| 常用 API | `vkCreateBuffer` / `vkDestroyBuffer` / `vkGetBufferMemoryRequirements` / `vkBindBufferMemory` / `vkCmdCopyBuffer` / `vkCmdUpdateBuffer` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkBuffer` 是 Vulkan 中表示线性内存资源的对象，用于顶点、索引、uniform、storage、transfer、indirect draw 等场景；它不像 image 有 layout 概念，但仍有 usage、memory property 和 alignment 要求。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice
→ VkBuffer (Create)
→ VkDeviceMemory (Allocate / Bind)
→ VkBufferView (optional, for texel buffer)
→ Descriptor / Vertex Input / Index Input / Transfer / Indirect
→ Shader / Draw / Compute
```

### 上游依赖

- `VkDevice` 必须有效。[SPEC]
- 目标 usage 必须被 device 支持。[SPEC]
- 需要可用的 device memory 并满足 memory requirements。[SPEC]

### 下游影响

- Vertex / index buffer 通过 `vkCmdBindVertexBuffers` / `vkCmdBindIndexBuffer` 绑定。[SPEC]
- Uniform / storage buffer 通过 descriptor set 绑定到 shader。[SPEC]
- Transfer / staging 操作通过 `vkCmdCopyBuffer` 完成。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkBuffer`
- `VkBufferCreateInfo`
- `VkMemoryRequirements`
- `VkDeviceMemory`
- `VkBufferView`（texel buffer 使用）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateBuffer` | 创建 buffer，不分配内存。[SPEC] |
| `vkDestroyBuffer` | 销毁 buffer。[SPEC] |
| `vkGetBufferMemoryRequirements` / `vkGetBufferMemoryRequirements2` | 查询 memory requirements。[SPEC] |
| `vkBindBufferMemory` / `vkBindBufferMemory2` | 绑定 buffer 到 memory。[SPEC] |
| `vkCmdCopyBuffer` | GPU 侧 buffer 拷贝。[SPEC] |
| `vkCmdUpdateBuffer` | 小数据直接更新 buffer（有大小限制）。[SPEC] |
| `vkCmdFillBuffer` | 填充 buffer。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_buffer_device_address`：buffer device address，用于光追、mesh shader 等。[SPEC]
- `VK_EXT_descriptor_buffer`：用 buffer 存储 descriptor，减少 descriptor set 分配开销。
- Android 可用性：核心功能全部可用；buffer device address 需设备支持。[ANDROID]

---

## 4. 标准使用流程

```text
vkCreateBuffer(..., &createInfo, ..., &buffer)
→ vkGetBufferMemoryRequirements(device, buffer, &memReq)
→ 选择满足 memoryTypeBits 的 memory type
→ vkAllocateMemory(..., &allocInfo, ..., &memory)
→ vkBindBufferMemory(device, buffer, memory, 0)
→ 若需 CPU 写入:
    vkMapMemory → memcpy → vkUnmapMemory
    或 vkCmdCopyBuffer / vkCmdUpdateBuffer
→ 用于 vertex / index / uniform / storage / transfer
→ 销毁时:
    等待 GPU idle
    → 销毁 buffer
    → 释放 memory
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `size` | buffer 字节大小；为 0 非法。[SPEC] | 分配的 size 小于实际数据。[TOOL] |
| `usage` | 必须覆盖实际用途：`TRANSFER_SRC` / `TRANSFER_DST` / `UNIFORM_BUFFER` / `STORAGE_BUFFER` / `INDEX_BUFFER` / `VERTEX_BUFFER` / `INDIRECT_BUFFER` 等。[SPEC] | usage 缺少 `TRANSFER_DST` 但做 upload；缺少 `STORAGE_BUFFER` 但 compute 要写。[TOOL] |
| `sharingMode` | `EXCLUSIVE` 或 `CONCURRENT`。[SPEC] | 多 queue 访问但未正确处理 ownership。[SPEC] |
| `flags` | 通常为 0；`SPARSE_BINDING` / `BUFFER_DEVICE_ADDRESS` 等需特殊处理。[SPEC] | 使用 device address 但未在 usage 中加 `BUFFER_DEVICE_ADDRESS`。[TOOL] |
| `memoryTypeBits` | 决定可用 memory type index。[SPEC] | 选择不满足需求的 memory type（如需 CPU visible 但选 DEVICE_LOCAL）。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `usage` 是否覆盖所有预期用途？
- [ ] `size` 是否大于 0 且满足数据需求？
- [ ] `sharingMode` 是否与 queue family 访问方式匹配？
- [ ] 是否需要 `BUFFER_DEVICE_ADDRESS` 等 flag？

### 使用阶段

- [ ] Uniform buffer dynamic offset 是否满足 `minUniformBufferOffsetAlignment`？[SPEC]
- [ ] Storage buffer 的 access 是否通过 barrier / memory dependency 同步？[SPEC]
- [ ] Vertex buffer 的 stride / offset 是否与 pipeline 的 vertex input 匹配？[SPEC]
- [ ] Index buffer 的 index type 是否与 draw call 一致？[SPEC]

### 销毁阶段

- [ ] 是否等待 GPU 不再访问？
- [ ] Memory 是否单独释放？（buffer 销毁不释放 memory）[SPEC]

---

## 7. 高频错误

1. `usage` 缺少实际需要的 flag。[SPEC]
2. Uniform buffer offset 不满足 alignment。[TOOL]
3. CPU 写入 buffer 后未 flush（非 coherent memory）或缺少 barrier。[SPEC]
4. Storage buffer 写入后 graphics 读取缺少 barrier。[TOOL]
5. Buffer 被 GPU 使用期间 CPU 覆盖数据。[ENGINE]
6. Vertex / index buffer 的 offset / stride 与 pipeline 不匹配。[TOOL]
7. `size` 为 0 或小于实际数据。[SPEC]
8. 销毁 buffer 前未等待 GPU。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkBufferCreateInfo-*`：size / usage / sharing mode 合法性。
- `VUID-vkCmdBindVertexBuffers-*` / `VUID-vkCmdBindIndexBuffer-*`：buffer 与 pipeline 匹配。
- `VUID-vkCmdDraw-*` / `VUID-vkCmdDispatch-*`：descriptor buffer 与 shader 匹配。

### RenderDoc / AGI

- 查看 vertex / index / uniform / storage buffer 内容。
- 查看 descriptor 绑定的 buffer 范围。
- 查看 draw call 的 vertex input 状态。

### 日志 / 代码检查

- 检查 `vkCreateBuffer` 返回值。
- 检查 memory property 是否满足 CPU/GPU 访问需求。
- 检查 uniform / storage offset alignment。

---

## 9. 生命周期风险

### 创建时机

- 初始化时创建长期 buffer（uniform ring buffer、vertex/index buffer）。
- 运行时动态创建 staging buffer / storage buffer。

### 使用时机

- 每帧绑定 vertex / index / uniform / storage buffer。
- 初始化时上传数据。

### 销毁时机

- 应用退出或资源卸载时。
- 必须等 GPU 完成访问。[SPEC]

### in-flight 风险

- Buffer 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]
- Per-frame uniform buffer 需按 frame-in-flight 分 slot，避免 CPU 覆盖 GPU 正在读取的数据。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 写入 coherent memory 后 GPU 立即可见；非 coherent memory 需 `vkFlushMappedMemoryRanges`。[SPEC]
- CPU 读取 GPU 写入的 buffer 通常需要 barrier 或 coherent memory + invalidate。[SPEC]

### GPU-GPU 同步

- Storage buffer 跨 pass / 跨 queue 使用需要 buffer memory barrier。[SPEC]
- Uniform buffer 更新通常每帧独立 slot，不需要跨帧 barrier。[ENGINE]

### 资源访问同步

- `vkCmdPipelineBarrier` 中 buffer memory barrier 的 `srcAccessMask` / `dstAccessMask` / `srcStageMask` / `dstStageMask` 必须匹配 producer / consumer。[SPEC]

---

## 11. Android 注意点

- 移动端内存紧张，uniform buffer 通常使用 coherent host-visible memory。[ENGINE]
- 大 texture upload 应使用 staging buffer 而非每帧 map image。[ENGINE]
- Android 设备对 storage buffer 的 alignment 要求需严格检查。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 避免频繁创建 / 销毁大 buffer，使用 ring buffer 或 pool。[ENGINE]
- 小数据更新可用 `vkCmdUpdateBuffer`，大数据用 staging buffer + copy。[ENGINE]

### GPU 侧

- Vertex / index buffer 使用 device-local memory 性能最好。[ENGINE]
- Uniform buffer 通常 host-visible + coherent 以减少 CPU 同步开销。[ENGINE]

### 移动端

- 移动端 storage buffer 的 bandwidth 和 latency 与 UBO 不同，需结合 shader 访问模式选择。[ENGINE]
- 减少每帧 map / unmap 次数，使用 persistent mapped coherent buffer。[ENGINE]

---

## 13. 专家经验

**经验**：
Uniform buffer 的 dynamic offset 必须按 `minUniformBufferOffsetAlignment` 对齐；如果项目需要频繁更新 per-object uniform，优先使用 push constant 或 dynamic uniform buffer，而不是每帧重新 allocate descriptor set。

**适用条件**：
需要频繁更新 uniform 的渲染场景，尤其是有大量 draw call 的场景。

**不适用情况**：
Uniform 数据极少或完全不变化的场景。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `image.md`
- `image_view.md`
- `memory_allocation.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_update.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. 特定 usage 组合在目标设备上的支持情况。
2. `minUniformBufferOffsetAlignment` 和 `minStorageBufferOffsetAlignment` 的具体值。
3. `VK_KHR_buffer_device_address` 的启用与使用规则。
4. Coherent / non-coherent memory 的 flush / invalidate 规则。

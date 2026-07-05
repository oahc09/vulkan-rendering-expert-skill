# Case: Storage Buffer Not Visible

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Storage Buffer / Synchronization / Memory Visibility |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Compute shader 写入 storage buffer（SSBO）后，后续 graphics pass 读取时内容全零、旧值或未定义。常见表现：

- Compute culling / skinning / particle 输出在 graphics vertex shader 中读不到。
- 偶尔能读到，但帧间不稳定；某些 GPU 必现，另一些 GPU 正常。
- CPU 直接写入的 SSBO，GPU compute 或 graphics 读不到；或 compute 写入后 CPU 回读不到。
- App 不 crash，但依赖 SSBO 的渲染效果完全丢失。

需要区分两类场景：

1. **Host-visible buffer**：CPU 通过 `vkMapMemory` 写入，GPU 读取时看不到新数据；或 GPU 写入后 CPU 回读不到。
2. **Device-local buffer**：compute 写入后，graphics pipeline 在同一 device 上读不到；跨 queue 时更明显。

---

## 2. 初始上下文

- 使用 compute pipeline 写入 `VK_DESCRIPTOR_TYPE_STORAGE_BUFFER`。
- 后续 graphics pipeline 通过 SSBO 或间接绘制 buffer 读取。
- 可能使用 host-visible `VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT` buffer。
- 可能使用 device-local `VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT` buffer。
- 可能涉及同一 queue 内的 compute → graphics，也可能涉及 async compute queue → graphics queue。
- 多 frame-in-flight，每帧复用同一 buffer 或 ping-pong buffer。

---

## 3. 初始误判

最初容易怀疑：

```text
compute shader 没执行；
dispatch 数量为零；
descriptor set 没绑定；
buffer 大小不够；
数据写到了错误的 offset；
GPU driver bug。
```

但 RenderDoc 中 compute dispatch 已执行，buffer 绑定也正确；进一步查看 buffer 内容时发现：

- 若是 host-visible buffer，GPU 看到的仍是 map 区域内的旧数据 `[SPEC]`。
- 若是 device-local buffer，compute write 后缺少 barrier，graphics read 发生在 write 完成前 `[SPEC]`。

---

## 4. 排查路径

1. 确认 buffer memory type：host-visible / device-local / host-coherent `[ENGINE]`。
2. 检查 Validation Layer 是否报 synchronization hazard `[TOOL]`。
3. 在 RenderDoc / AGI 中查看 compute dispatch 后的 buffer 内容 `[TOOL]`。
4. 检查 compute write 与 graphics read 之间是否有 `vkCmdPipelineBarrier` `[ENGINE]`。
5. 检查 barrier 的 stage/access：
   - `srcStage = COMPUTE_SHADER`，`srcAccess = SHADER_STORAGE_WRITE` `[SPEC]`。
   - `dstStage` 为 consumer stage（`VERTEX_SHADER` / `FRAGMENT_SHADER` / `COMPUTE_SHADER`），`dstAccess = SHADER_STORAGE_READ` `[SPEC]`。
6. 若 CPU 写入 host-visible buffer：
   - 检查是否调用了 `vkFlushMappedMemoryRanges`（若 memory 不是 `HOST_COHERENT`） `[SPEC]`。
   - 检查 CPU 回读前是否调用了 `vkInvalidateMappedMemoryRanges`（若 memory 不是 `HOST_COHERENT`） `[SPEC]`。
   - 检查 map 后写入范围是否在 allocation size 内 `[SPEC]`。
7. 若使用 async compute queue，检查 queue submit 之间是否有 semaphore / fence `[SPEC]`。
8. 检查 frame-in-flight 资源是否每帧独立，避免读写重叠 `[ENGINE]`。

---

## 5. 关键证据

### Validation Layer

可能出现：

- `SYNC-HAZARD-READ-AFTER-WRITE`：graphics read 发生在 compute write 完成前 `[TOOL]`。
- `VUID-vkFlushMappedMemoryRanges-Memory-01328`：flush 范围未对齐 `nonCoherentAtomSize`。
- `VUID-vkMapMemory-memory-00682`：map offset 或 size 越界。
- 部分 host-visible non-coherent 场景 validation 不会报错，但 RenderDoc 中数据不一致 `[TOOL]`。

### RenderDoc / AGI

观察到：

- Compute dispatch 已执行，但 storage buffer 在 dispatch 后仍保持旧值。
- 或 compute 写入后 buffer 内容正确，但 graphics pass 中 bound SSBO 显示旧值。
- 在 host-visible non-coherent 场景下，CPU map 视图与 GPU 视图内容不同步。
- 跨 queue 场景下，graphics queue 的 submit 时间早于 compute queue 的 signal。

### Log / Code

返回值：

- `vkQueueSubmit` 返回 `VK_SUCCESS`。
- `vkMapMemory` 成功，但 `vkFlushMappedMemoryRanges` 被遗漏或范围错误。

关键代码：

```text
// 错误示例 1：device-local SSBO 缺少 compute → graphics barrier
vkCmdDispatch(cmd, x, y, z);   // compute 写入 SSBO
// 缺少 pipeline barrier
vkCmdDrawIndexed(cmd, idxCount, 1, 0, 0, 0); // vertex shader 读 SSBO

// 错误示例 2：host-visible non-coherent buffer 未 flush
void* data;
vkMapMemory(device, memory, 0, size, 0, &data);
memcpy(data, &ssboData, size);
// 未调用 vkFlushMappedMemoryRanges（若 memory 不是 HOST_COHERENT）
vkUnmapMemory(device, memory);
```

---

## 6. 根因

根因：compute shader 对 storage buffer 的写入结果未被后续 consumer 正确可见，原因分为两类：

1. **Device-local / 同 device 跨 pipeline 场景**：缺少 buffer memory barrier，导致 graphics read 在 compute write 完成前发生，或写入结果未从 compute cache flush 到 memory `[SPEC]`。
2. **Host-visible non-coherent 场景**：CPU 写入 mapped memory 后未 `vkFlushMappedMemoryRanges`，或 GPU 写入后 CPU 回读前未 `vkInvalidateMappedMemoryRanges`，导致 host 与 device cache 视图不一致 `[SPEC]`。

---

## 7. 修复方案

### 最小修复

**Device-local / 同 queue compute → graphics：**

在 compute dispatch 后、graphics draw 前插入 buffer memory barrier：

```text
srcStage  = COMPUTE_SHADER
srcAccess = SHADER_STORAGE_WRITE
dstStage  = VERTEX_SHADER / FRAGMENT_SHADER / COMPUTE_SHADER
dstAccess = SHADER_STORAGE_READ
buffer    = storageBuffer
offset    = 0
size      = VK_WHOLE_SIZE
```

**Host-visible non-coherent buffer：**

CPU 写入后 flush：

```text
vkFlushMappedMemoryRanges(device, 1, &range);
```

CPU 回读前 invalidate：

```text
vkInvalidateMappedMemoryRanges(device, 1, &range);
```

flush / invalidate 的 offset 和 size 必须按 `nonCoherentAtomSize` 对齐 `[SPEC]`。

**跨 async compute queue → graphics queue：**

使用 semaphore 或 timeline semaphore 保证 compute submit signal 后再执行 graphics submit `[SPEC]`。

### 稳定修复

- 封装 SSBO 资源类，根据 memory type 自动处理 flush / invalidate。
- 在 command buffer recorder 中自动推导 compute write → graphics read 的 barrier。
- 对 host-visible coherent buffer 优先使用 `HOST_COHERENT` flag，减少手动 flush；对性能敏感的大 buffer 仍用 device-local + explicit barrier。
- 对 frame-in-flight SSBO 采用多缓冲，避免读写重叠。

### 工程化修复

- 建立 RenderGraph，自动推导 storage buffer 的 producer / consumer 并生成 barrier。
- 使用 `VK_KHR_synchronization2` 明确 stage / access，降低 barrier 误配。
- 对 async compute 引入 timeline semaphore 依赖图，自动 signal / wait。
- 在 CI 中跑多 GPU 验证，专门测试 host-visible non-coherent 和 device-local 两种 SSBO 路径。
- 增加运行时 assert：对 non-coherent host-visible buffer，检测 `vkFlushMappedMemoryRanges` / `vkInvalidateMappedMemoryRanges` 是否被调用。

---

## 8. 修复后验证

- [ ] Validation clean，无 synchronization hazard。
- [ ] RenderDoc / AGI 中 compute 写入后 buffer 内容正确。
- [ ] Graphics pass 读取 SSBO 得到预期值。
- [ ] Host-visible non-coherent buffer 的 CPU 写入对 GPU 可见。
- [ ] GPU 写入后的 host-visible buffer 可被 CPU 正确回读。
- [ ] Async compute queue → graphics queue 结果一致。
- [ ] 多帧运行稳定，无数据串帧。
- [ ] 不同 GPU（不同 cache / coherent 行为）上验证通过。

---

## 9. 经验抽象

Storage buffer 的“可见性”分两层：

```text
1. Execution dependency：producer 是否完成执行。
   → 用 pipeline barrier / event / semaphore 保证。
2. Memory visibility：写入结果是否对 consumer 可见。
   → device-local 用 access mask + barrier；
   → host-visible non-coherent 用 flush / invalidate。
```

`HOST_COHERENT` 只解决 host cache 与 device cache 之间的一致性问题，并不替代 device-local buffer 的 pipeline barrier。反之，pipeline barrier 也不解决 host-visible non-coherent memory 的 flush / invalidate 需求。

---

## 10. 预防规则

1. 任何 compute shader 写入 SSBO 后，被同 queue graphics 读取前必须插入 buffer memory barrier。
2. Barrier 的 `srcStage` 必须包含 `COMPUTE_SHADER`，`srcAccess` 必须包含 `SHADER_STORAGE_WRITE`。
3. Barrier 的 `dstStage` / `dstAccess` 必须精确覆盖后续 consumer。
4. Host-visible non-coherent buffer：CPU 写入后必须 `vkFlushMappedMemoryRanges`，CPU 回读前必须 `vkInvalidateMappedMemoryRanges`。
5. Flush / invalidate 范围必须按 `nonCoherentAtomSize` 对齐，建议直接用 `VK_WHOLE_SIZE` 简化。
6. Async compute queue 与 graphics queue 之间必须使用 semaphore / timeline semaphore 同步。
7. 每 frame-in-flight 的 SSBO 必须独立，避免上一帧覆盖当前帧。
8. 新增 SSBO 时必须明确标注 producer、consumer 和 memory type，由工具自动推导 barrier 或 flush。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_buffer.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`
- `../../05_workflows/05_resource_management/add_storage_buffer.md`

# Cases: Compute

> 合并自 4 个原 case 文件。关键词: compute, dispatch, storage-image, storage-buffer, output-overwrite

---

## Case: Compute Dispatch Zero

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Dispatch |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Compute pass 执行后 storage image / storage buffer 内容没有变化，但程序无 crash、无 Validation Layer 报错。Shader 逻辑看起来正确，dispatch 调用也存在，只是没有任何输出。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 compute pipeline 写入 storage image 或 storage buffer。
- Dispatch group count 由 CPU 根据资源尺寸动态计算。
- 可能刚修改了 compute shader 的 `local_size_x` / `local_size_y` / `local_size_z`。
- 资源尺寸较小（例如 1×1、2×2、小于 workgroup 大小）。

---

### 3. 初始误判

最初容易怀疑：

```text
compute shader 写错坐标或条件分支导致无写入；
descriptor 没绑定或 binding 不匹配；
storage image layout 不是 GENERAL；
compute 与 graphics 之间缺少 barrier；
storage buffer 不可见或没 flush。
```

但 RenderDoc 中 shader 绑定正常，dispatch 调用可见，没有 barrier 错误。最终发现 `vkCmdDispatch` 的 group count 为 0，导致 GPU 不启动任何 workgroup。

---

### 4. 排查路径

1. 在 `vkCmdDispatch` 调用处打印 `groupCountX`、`groupCountY`、`groupCountZ`。
2. 检查 compute shader 中的 `layout(local_size_x = N, ...)` 数值。
3. 确认 group count 计算是否使用了整数除法且没有向上取整。
4. 检查资源尺寸小于 workgroup 大小时的结果。
5. 在 RenderDoc / AGI 中查看 dispatch 调用的 thread group 数量。
6. 检查是否有分支在资源尺寸为 0 或 1 时直接返回，导致跳过 dispatch。

---

### 5. 关键证据

### Validation Layer

- 通常无直接报错（`[ENGINE]`），因为 dispatch group count 为 0 是合法的 Vulkan 行为。
- 若 storage image layout 或 descriptor 类型不匹配，可能报相关 VUID，但这类错误与本案例无关。

### RenderDoc / AGI

- 观察到：
  - Dispatch 调用存在，但 Thread Groups 显示为 `0, 0, 0` 或某一维为 0。
  - 或 Dispatch 的 group count 计算为 0，导致 no threads launched。
  - Storage image / buffer 在 dispatch 前后内容完全一致。
- 关键 resource：compute pipeline、`vkCmdDispatch` 参数、storage resource。

### Log / Code

- 返回值：
  - `vkCmdDispatch` 是录制命令，无返回值。
  - `vkQueueSubmit` 返回 `VK_SUCCESS`。
- 关键代码：

```text
// 错误示例：整数除法导致 group count 为 0
uint32_t groupCountX = imageWidth / localSizeX; // 若 imageWidth < localSizeX，结果为 0
uint32_t groupCountY = imageHeight / localSizeY;
vkCmdDispatch(cmd, groupCountX, groupCountY, 1);
```

或：

```text
// 错误示例：分支跳过 dispatch
if (imageWidth == 0 || imageHeight == 0) return; // 可能条件判断错误
vkCmdDispatch(cmd, imageWidth, imageHeight, 1);   // 错误：直接以像素尺寸作为 group count
```

---

### 6. 根因

根因：`vkCmdDispatch` 的 group count 计算错误，某一维为 0，导致 GPU 没有启动任何 compute workgroup，storage resource 保持原样。

---

### 7. 修复方案

### 最小修复

- 使用向上取整计算 group count：

```text
groupCountX = (width + localSizeX - 1) / localSizeX;
groupCountY = (height + localSizeY - 1) / localSizeY;
groupCountZ = (depth + localSizeZ - 1) / localSizeZ;
```

- 在调用 `vkCmdDispatch` 前断言 `groupCountX > 0 && groupCountY > 0 && groupCountZ > 0`。
- 当资源尺寸为 0 时，跳过 dispatch 而不是传入 0。

### 稳定修复

- 封装 `DispatchCompute(width, height, depth, localSizeX, localSizeY, localSizeZ)` 辅助函数，内部自动处理向上取整和零尺寸保护。
- 在 shader 编译或反射阶段读取 `local_size`，确保 CPU 侧 group count 计算与 shader 一致。
- 对 1D / 2D / 3D dispatch 分别提供类型安全的封装。

### 工程化修复

- 在 compute pass 描述中声明 `local_size` 和 dispatch domain，由 RenderGraph / pass system 自动计算 group count。
- CI 中加入小尺寸资源（1×1、2×2）的 compute 测试，确保 edge case 下有输出。
- 在 RenderDoc / AGI capture 中自动检查 dispatch group count 是否为 0。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 dispatch 的 Thread Groups 大于 0。
- [ ] Compute shader 写入 storage image / buffer 后内容发生变化。
- [ ] 资源尺寸为 1×1、2×2 等小于 workgroup 大小时仍有正确输出。
- [ ] 多帧运行稳定，无输出被覆盖或延迟。
- [ ] 修改 `local_size` 后 group count 自动重新计算。

---

### 9. 经验抽象

Dispatch group count 是“像素 / 纹素数量”除以“local size”后的向上取整，不是直接除法：

```text
groupCount = ceil(workSize / localSize)
```

只要资源尺寸小于 workgroup 尺寸，普通整数除法就会得到 0。更隐蔽的是，dispatch 0 是合法调用，不会触发 validation error，因此最容易被忽略。

---

### 10. 预防规则

1. 所有 compute dispatch 必须使用向上取整公式计算 group count。
2. 调用 `vkCmdDispatch` 前必须断言所有维度 group count > 0。
3. CPU 侧 `localSize` 必须与 shader `layout(local_size_x, ...)` 保持一致。
4. 资源尺寸为 0 时应跳过 dispatch，而不是传入 0。
5. 新增 compute pass 时必须包含 1×1、边界尺寸等 edge case 测试。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

### 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_image.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_buffer.md`


---

## Case: Compute Output Overwritten

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Synchronization / Resource Hazard |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Compute shader 写入 storage image / storage buffer 后，后续读取时发现内容为空、部分缺失或被后续 dispatch / graphics pass 覆盖。表现为后处理效果丢失、粒子模拟结果归零、culling 结果错误、compute skinning 失效等。

- 单独 capture compute pass 时输出正确，但整帧捕获时输出被覆盖。
- 多 dispatch 链路上，后续 dispatch 的结果“串”到前一次结果中。
- 某些 GPU 上表现为旧数据残留，另一些 GPU 上表现为新数据覆盖过快。

---

### 2. 初始上下文

- 使用 compute pipeline，输出到 storage image 或 storage buffer。
- 同一 command buffer 或 queue 上存在多个 dispatch，或 compute 之后紧跟 graphics pass。
- Compute 输出资源同时被其他 pass 读取或复用。
- 可能使用异步 compute queue，或 compute 与 graphics 并行提交。
- 多 frame-in-flight，每帧复用同一 buffer / image。

---

### 3. 初始误判

最初容易怀疑：

```text
compute shader 算法写错；
dispatch group 数量不够；
descriptor 没绑定到正确资源；
storage buffer 没清零；
数据类型不匹配导致写入被截断；
GPU 不支持某种 storage format。
```

但 RenderDoc 中单独查看 compute dispatch 时输出正确；后续 dispatch 或 graphics pass 也能看到资源被绑定。最终发现两个 producer/consumer 之间缺少 execution dependency 和 memory barrier，或 descriptor 在 barrier 之前被重新绑定到另一资源，导致后续 pass 在 compute 写入完成前就开始执行并覆盖结果。

---

### 4. 排查路径

1. 检查 Validation Layer 是否报 synchronization hazard `[TOOL]`。
2. 在 RenderDoc / AGI 中逐 event 查看 compute dispatch 输出 `[TOOL]`。
3. 确认 dispatch 之间是否有 `vkCmdPipelineBarrier` 或 event / semaphore `[ENGINE]`。
4. 检查 barrier 的 `srcStageMask` 是否包含 `COMPUTE_SHADER` `[SPEC]`。
5. 检查 barrier 的 `srcAccessMask` 是否包含 `SHADER_WRITE` / `SHADER_STORAGE_WRITE` `[SPEC]`。
6. 检查 barrier 的 `dstStageMask` / `dstAccessMask` 是否覆盖后续 consumer `[SPEC]`。
7. 检查 descriptor set 是否在 barrier 之后重新绑定，避免旧绑定被覆盖 `[ENGINE]`。
8. 若使用 async compute queue，检查 queue submit 之间的 semaphore / fence `[SPEC]`。
9. 检查 frame-in-flight 资源是否每帧独立，避免上一帧覆盖当前帧 `[ENGINE]`。

---

### 5. 关键证据

### Validation Layer

可能出现：

- `SYNC-HAZARD-WRITE-AFTER-WRITE`：两次 shader write 之间缺少 barrier `[TOOL]`。
- `SYNC-HAZARD-WRITE-AFTER-READ` / `READ-AFTER-WRITE`：compute write 与 graphics read 之间缺少同步 `[TOOL]`。
- `VUID-vkCmdDispatch-None-02699`：compute pipeline 绑定后 descriptor 状态不一致（若同时伴随 descriptor 绑定错误）。

### RenderDoc / AGI

观察到：

- 第一个 dispatch 后的 storage image / buffer 内容正确。
- 第二个 dispatch 或 graphics pass 开始前没有 barrier。
- 后续 pass 的 bound resource 与 compute 输出为同一 handle，但内容已被覆盖或尚未写入完成。
- 在 async compute 场景下，graphics pass 的 timeline 与 compute pass 重叠。

### Log / Code

返回值：

- `vkQueueSubmit` 返回 `VK_SUCCESS`。
- Fence / semaphore 正常 signal，但顺序未保证。

关键代码：

```text
// 错误示例：两次 dispatch 间缺少 barrier
vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipelineA);
vkCmdDispatch(cmd, x, y, z);            // 写入 storage image A
vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, pipelineB);
vkCmdDispatch(cmd, x, y, z);            // 直接读取/覆盖 A，未等待前一次完成

// 错误示例：compute 后直接开始 render pass，未 transition storage image
vkCmdDispatch(cmd, x, y, z);
vkCmdBeginRenderPass(cmd, &rpBegin, ...); // fragment shader 采样 A，缺少 barrier
```

---

### 6. 根因

根因：compute shader 对 storage image / storage buffer 的写入完成后，没有通过 pipeline barrier 或 event / semaphore 与后续 dispatch / graphics pass 建立执行依赖和内存可见性，导致后续 consumer 在写入完成前访问或覆盖资源，或 producer 写入被后续操作提前覆盖。

---

### 7. 修复方案

### 最小修复

在 compute write 与后续 read / write 之间插入 `vkCmdPipelineBarrier`：

```text
srcStage  = COMPUTE_SHADER
srcAccess = SHADER_STORAGE_WRITE / SHADER_WRITE

dstStage  = COMPUTE_SHADER 或 FRAGMENT_SHADER / VERTEX_SHADER
dstAccess = SHADER_STORAGE_READ / SHADER_SAMPLED_READ / SHADER_READ
```

若资源为 image，还需同步转换 layout：

```text
oldLayout = GENERAL
newLayout = GENERAL 或 SHADER_READ_ONLY_OPTIMAL（取决于后续用途）
```

### 稳定修复

- 每个 compute pass 显式声明输出资源及后续 consumer。
- 在 command buffer recorder 中按 producer/consumer 关系自动推导并插入 barrier。
- 对 storage image 使用专用 layout 状态机，确保 GENERAL → shader read 转换完整。
- 对 frame-in-flight 资源采用 ping-pong 或多 buffering，避免读写重叠。

### 工程化修复

- 建立 RenderGraph，自动推导 dispatch 间和 compute-graphics 间的 dependency，并生成 barrier。
- 使用 `VK_KHR_synchronization2` 的 explicit sync，减少 stage/access 组合误配。
- 对 async compute 引入 timeline semaphore，按 dependency 图自动 signal / wait。
- 在 CI 中跑 RenderDoc capture，检测 write-after-write / read-after-write hazard。

---

### 8. 修复后验证

- [ ] Validation clean，无 synchronization hazard。
- [ ] RenderDoc / AGI 中每个 dispatch 输出稳定，不被后续操作覆盖。
- [ ] Compute 输出在后续 graphics pass 中读取正确。
- [ ] 多 dispatch 链路结果按顺序累积。
- [ ] Async compute queue 与 graphics queue 结果一致。
- [ ] 多帧运行稳定，无 flicker 或数据串帧。
- [ ] 高负载下性能符合预期，无过度 barrier。

---

### 9. 经验抽象

Compute 输出被覆盖的本质是“看起来提交顺序正确，但 GPU 执行是异步且可能并行的”。必须显式声明：

```text
谁写入 (producer stage/access)
谁读取 (consumer stage/access)
写入是否完成 (execution dependency)
写入结果是否可见 (memory dependency)
资源 layout 是否匹配 (layout transition)
```

缺少任意一项，都会出现“单步调试正确、整帧错误”的现象。

---

### 10. 预防规则

1. 任何 compute write 之后若被同 queue 后续操作读取，必须插入 pipeline barrier。
2. Compute write 与 graphics read 之间必须同时保证 execution dependency 和 memory dependency。
3. Storage image 跨 compute / graphics 使用时必须正确转换 layout，常用 `GENERAL` ↔ `SHADER_READ_ONLY_OPTIMAL`。
4. 多 dispatch 写入同一资源时，dispatch 之间必须有 write-after-write barrier。
5. Async compute queue 与 graphics queue 之间必须使用 semaphore 或 fence 同步。
6. 每帧复用的 storage buffer / image 必须多缓冲或严格按帧 fence 等待。
7. Descriptor 重新绑定必须在 barrier 之后，确保 consumer 看到正确资源。
8. 新增 compute pass 时必须明确声明所有输出资源的 consumer。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_buffer.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_image.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`


---

## Case: Storage Buffer Not Visible

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Storage Buffer / Synchronization / Memory Visibility |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Compute shader 写入 storage buffer（SSBO）后，后续 graphics pass 读取时内容全零、旧值或未定义。常见表现：

- Compute culling / skinning / particle 输出在 graphics vertex shader 中读不到。
- 偶尔能读到，但帧间不稳定；某些 GPU 必现，另一些 GPU 正常。
- CPU 直接写入的 SSBO，GPU compute 或 graphics 读不到；或 compute 写入后 CPU 回读不到。
- App 不 crash，但依赖 SSBO 的渲染效果完全丢失。

需要区分两类场景：

1. **Host-visible buffer**：CPU 通过 `vkMapMemory` 写入，GPU 读取时看不到新数据；或 GPU 写入后 CPU 回读不到。
2. **Device-local buffer**：compute 写入后，graphics pipeline 在同一 device 上读不到；跨 queue 时更明显。

---

### 2. 初始上下文

- 使用 compute pipeline 写入 `VK_DESCRIPTOR_TYPE_STORAGE_BUFFER`。
- 后续 graphics pipeline 通过 SSBO 或间接绘制 buffer 读取。
- 可能使用 host-visible `VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT` buffer。
- 可能使用 device-local `VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT` buffer。
- 可能涉及同一 queue 内的 compute → graphics，也可能涉及 async compute queue → graphics queue。
- 多 frame-in-flight，每帧复用同一 buffer 或 ping-pong buffer。

---

### 3. 初始误判

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

### 4. 排查路径

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

### 5. 关键证据

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

### 6. 根因

根因：compute shader 对 storage buffer 的写入结果未被后续 consumer 正确可见，原因分为两类：

1. **Device-local / 同 device 跨 pipeline 场景**：缺少 buffer memory barrier，导致 graphics read 在 compute write 完成前发生，或写入结果未从 compute cache flush 到 memory `[SPEC]`。
2. **Host-visible non-coherent 场景**：CPU 写入 mapped memory 后未 `vkFlushMappedMemoryRanges`，或 GPU 写入后 CPU 回读前未 `vkInvalidateMappedMemoryRanges`，导致 host 与 device cache 视图不一致 `[SPEC]`。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean，无 synchronization hazard。
- [ ] RenderDoc / AGI 中 compute 写入后 buffer 内容正确。
- [ ] Graphics pass 读取 SSBO 得到预期值。
- [ ] Host-visible non-coherent buffer 的 CPU 写入对 GPU 可见。
- [ ] GPU 写入后的 host-visible buffer 可被 CPU 正确回读。
- [ ] Async compute queue → graphics queue 结果一致。
- [ ] 多帧运行稳定，无数据串帧。
- [ ] 不同 GPU（不同 cache / coherent 行为）上验证通过。

---

### 9. 经验抽象

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

### 10. 预防规则

1. 任何 compute shader 写入 SSBO 后，被同 queue graphics 读取前必须插入 buffer memory barrier。
2. Barrier 的 `srcStage` 必须包含 `COMPUTE_SHADER`，`srcAccess` 必须包含 `SHADER_STORAGE_WRITE`。
3. Barrier 的 `dstStage` / `dstAccess` 必须精确覆盖后续 consumer。
4. Host-visible non-coherent buffer：CPU 写入后必须 `vkFlushMappedMemoryRanges`，CPU 回读前必须 `vkInvalidateMappedMemoryRanges`。
5. Flush / invalidate 范围必须按 `nonCoherentAtomSize` 对齐，建议直接用 `VK_WHOLE_SIZE` 简化。
6. Async compute queue 与 graphics queue 之间必须使用 semaphore / timeline semaphore 同步。
7. 每 frame-in-flight 的 SSBO 必须独立，避免上一帧覆盖当前帧。
8. 新增 SSBO 时必须明确标注 producer、consumer 和 memory type，由工具自动推导 barrier 或 flush。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_buffer.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`
- `../../05_workflows/05_resource_management/add_storage_buffer.md`


---

## Case: Storage Image Layout Wrong

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Storage Image / Layout |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Compute shader 对 storage image 进行读写后，内容没有变化、出现黑色、颜色错乱，或 Validation Layer 报错提示 descriptor image layout 与实际 layout 不匹配。问题只在 compute pass 访问 storage image 时出现，普通 sampled image 正常。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 compute pipeline 写入或读取 storage image。
- Storage image 的 usage 包含 `VK_IMAGE_USAGE_STORAGE_BIT`。
- Descriptor 类型为 `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE`。
- 可能从 graphics pass 输出的 image 直接作为 compute 输入，或 compute 输出后由 graphics 采样。

---

### 3. 初始误判

最初容易怀疑：

```text
compute shader 坐标转换错误；
descriptor binding 或 image view 错误；
storage image 的 format 不支持 compute 读写；
compute 与 graphics 之间缺少 barrier；
image 没有 `VK_IMAGE_USAGE_STORAGE_BIT`。
```

但 usage 和 descriptor 都正确，barrier 也存在。最终发现 storage image 在 dispatch 时仍处于 `SHADER_READ_ONLY_OPTIMAL` 或 `COLOR_ATTACHMENT_OPTIMAL`，而 compute 读写 storage image 要求 `VK_IMAGE_LAYOUT_GENERAL`（或 implementation-defined 的 storage 兼容 layout）。

---

### 4. 排查路径

1. 检查 descriptor update 中 `VkDescriptorImageInfo.imageLayout` 是否设置为 `VK_IMAGE_LAYOUT_GENERAL`。
2. 检查 compute dispatch 前是否插入了将 storage image transition 到 `GENERAL` 的 image memory barrier。
3. 检查 barrier 的 `srcAccess` / `dstAccess` / `srcStage` / `dstStage` 是否覆盖 compute shader 的读写。
4. 在 RenderDoc 中查看 storage image 在 dispatch 时刻的实际 layout。
5. 检查 graphics pass 输出到 compute 输入的 layout transition 是否完整。
6. 检查同一 image 在被 graphics 采样前是否已从 `GENERAL` transition 回 `SHADER_READ_ONLY_OPTIMAL`。

---

### 5. 关键证据

### Validation Layer

- 典型 VUID（`[SPEC]`）：
  - `VUID-vkCmdDispatch-None-02699`：descriptor image layout 必须与 image 当前实际 layout 一致。
  - `VUID-VkDescriptorImageInfo-imageLayout-00344`：`STORAGE_IMAGE` descriptor 的 `imageLayout` 必须是 `VK_IMAGE_LAYOUT_GENERAL` 或 `VK_IMAGE_LAYOUT_SHARED_PRESENT_KHR`。
  - `VUID-vkCmdDispatch-None-02697`：storage image 的 image layout 不兼容其 descriptor type。

### RenderDoc / AGI

- 观察到：
  - Bound Resources 中 storage image descriptor 的 layout 显示为 `SHADER_READ_ONLY_OPTIMAL` 或 `COLOR_ATTACHMENT_OPTIMAL`。
  - Texture Viewer 中 storage image 在 dispatch 前后的内容无变化。
  - Image layout 时间线显示 dispatch 时 image 未进入 `GENERAL`。
- 关键 resource：storage image、`VkDescriptorImageInfo`、image memory barrier。

### Log / Code

- 返回值：
  - `vkUpdateDescriptorSets` 和 `vkQueueSubmit` 通常返回 `VK_SUCCESS`。
  - Validation Layer 会报告 layout mismatch 相关消息。
- 关键代码：

```text
// 错误示例 1：descriptor imageLayout 未设为 GENERAL
VkDescriptorImageInfo imageInfo{};
imageInfo.imageView = storageImageView;
imageInfo.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL; // 错误：storage image 需要 GENERAL
imageInfo.sampler = VK_NULL_HANDLE;

// 错误示例 2：缺少 transition 到 GENERAL 的 barrier
vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, computePipeline);
vkCmdDispatch(cmd, groupsX, groupsY, 1); // 此时 image 仍是 COLOR_ATTACHMENT_OPTIMAL
```

---

### 6. 根因

根因：storage image 在 compute shader 访问前没有 transition 到 `VK_IMAGE_LAYOUT_GENERAL`，或 descriptor 更新时 `imageLayout` 未设置为 `VK_IMAGE_LAYOUT_GENERAL`，导致 compute 读写行为未定义或被验证层拦截。

---

### 7. 修复方案

### 最小修复

- 在 compute dispatch 前插入 image memory barrier，将 storage image 从当前 layout transition 到 `VK_IMAGE_LAYOUT_GENERAL`：

```text
oldLayout = COLOR_ATTACHMENT_OPTIMAL / SHADER_READ_ONLY_OPTIMAL
newLayout = GENERAL
srcStage  = COLOR_ATTACHMENT_OUTPUT / FRAGMENT_SHADER
srcAccess = COLOR_ATTACHMENT_WRITE / SHADER_SAMPLED_READ
dstStage  = COMPUTE_SHADER
dstAccess = SHADER_STORAGE_READ / SHADER_STORAGE_WRITE
```

- 更新 descriptor 时，将 `VkDescriptorImageInfo.imageLayout` 显式设为 `VK_IMAGE_LAYOUT_GENERAL`。
- compute 写完后如需被 graphics 采样，再 transition 回 `SHADER_READ_ONLY_OPTIMAL`。

### 稳定修复

- 为 storage image 维护当前 layout 状态机；compute pass 使用前自动 transition 到 `GENERAL`。
- descriptor update 辅助函数根据 descriptor type 自动填充 `imageLayout`，避免手动填写错误。
- 在 compute pass 描述中声明 input / output layout，由系统生成 barrier。

### 工程化修复

- 使用 RenderGraph / FrameGraph 自动推导 storage image 的 layout 和 barrier。
- 在 debug build 中增加断言：storage image descriptor 的 imageLayout 必须为 `GENERAL`。
- CI 中加入 compute-graphics 互操作测试，验证 layout transition 链完整。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 storage image descriptor layout 为 `GENERAL`。
- [ ] Compute dispatch 后 storage image 内容按 shader 逻辑更新。
- [ ] Compute 输出被 graphics pass 采样时，layout 已 transition 回 `SHADER_READ_ONLY_OPTIMAL`。
- [ ] 多帧运行稳定，无撕裂或内容错乱。
- [ ] resize / swapchain recreate 后 storage image layout 状态正确。

---

### 9. 经验抽象

Storage image 是特殊的 image 使用方式，其 descriptor imageLayout 和实际 image layout 都必须是 `VK_IMAGE_LAYOUT_GENERAL`（或驱动允许的 storage 兼容 layout）：

```text
storage image descriptor imageLayout = GENERAL
actual image layout before dispatch = GENERAL
barrier dstStage = COMPUTE_SHADER
barrier dstAccess = SHADER_STORAGE_READ | SHADER_STORAGE_WRITE
```

不要把它当作普通 sampled image 处理；也不要认为 barrier 只存在于 compute 和 graphics 之间，compute 使用前的 layout transition 同样关键。

---

### 10. 预防规则

1. `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` 的 descriptor imageLayout 必须设置为 `VK_IMAGE_LAYOUT_GENERAL`。
2. Compute dispatch 前必须将 storage image 通过 barrier transition 到 `VK_IMAGE_LAYOUT_GENERAL`。
3. Compute 写完后若被 graphics 采样，必须再 transition 回 `SHADER_READ_ONLY_OPTIMAL`。
4. 不要对 storage image 使用 `COLOR_ATTACHMENT_OPTIMAL` 或 `SHADER_READ_ONLY_OPTIMAL` 作为 compute 读写时的 layout。
5. 在 descriptor update 和 dispatch 前增加 debug 断言，检查 storage image layout 是否为 `GENERAL`。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/compute_write_storage_image.md`
- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`


---

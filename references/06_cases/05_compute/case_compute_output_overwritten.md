# Case: Compute Output Overwritten

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Synchronization / Resource Hazard |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Compute shader 写入 storage image / storage buffer 后，后续读取时发现内容为空、部分缺失或被后续 dispatch / graphics pass 覆盖。表现为后处理效果丢失、粒子模拟结果归零、culling 结果错误、compute skinning 失效等。

- 单独 capture compute pass 时输出正确，但整帧捕获时输出被覆盖。
- 多 dispatch 链路上，后续 dispatch 的结果“串”到前一次结果中。
- 某些 GPU 上表现为旧数据残留，另一些 GPU 上表现为新数据覆盖过快。

---

## 2. 初始上下文

- 使用 compute pipeline，输出到 storage image 或 storage buffer。
- 同一 command buffer 或 queue 上存在多个 dispatch，或 compute 之后紧跟 graphics pass。
- Compute 输出资源同时被其他 pass 读取或复用。
- 可能使用异步 compute queue，或 compute 与 graphics 并行提交。
- 多 frame-in-flight，每帧复用同一 buffer / image。

---

## 3. 初始误判

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

## 4. 排查路径

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

## 5. 关键证据

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

## 6. 根因

根因：compute shader 对 storage image / storage buffer 的写入完成后，没有通过 pipeline barrier 或 event / semaphore 与后续 dispatch / graphics pass 建立执行依赖和内存可见性，导致后续 consumer 在写入完成前访问或覆盖资源，或 producer 写入被后续操作提前覆盖。

---

## 7. 修复方案

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

## 8. 修复后验证

- [ ] Validation clean，无 synchronization hazard。
- [ ] RenderDoc / AGI 中每个 dispatch 输出稳定，不被后续操作覆盖。
- [ ] Compute 输出在后续 graphics pass 中读取正确。
- [ ] 多 dispatch 链路结果按顺序累积。
- [ ] Async compute queue 与 graphics queue 结果一致。
- [ ] 多帧运行稳定，无 flicker 或数据串帧。
- [ ] 高负载下性能符合预期，无过度 barrier。

---

## 9. 经验抽象

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

## 10. 预防规则

1. 任何 compute write 之后若被同 queue 后续操作读取，必须插入 pipeline barrier。
2. Compute write 与 graphics read 之间必须同时保证 execution dependency 和 memory dependency。
3. Storage image 跨 compute / graphics 使用时必须正确转换 layout，常用 `GENERAL` ↔ `SHADER_READ_ONLY_OPTIMAL`。
4. 多 dispatch 写入同一资源时，dispatch 之间必须有 write-after-write barrier。
5. Async compute queue 与 graphics queue 之间必须使用 semaphore 或 fence 同步。
6. 每帧复用的 storage buffer / image 必须多缓冲或严格按帧 fence 等待。
7. Descriptor 重新绑定必须在 barrier 之后，确保 consumer 看到正确资源。
8. 新增 compute pass 时必须明确声明所有输出资源的 consumer。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_buffer.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_image.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`

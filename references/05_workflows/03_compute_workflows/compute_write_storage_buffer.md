# Workflow: Compute Write Storage Buffer

> 文件建议路径：`compute_write_storage_buffer.md`

---

## 0. 适用范围

### 适用

- compute shader 生成结构化数据并写入 SSBO，供后续 graphics pass 或 CPU 读取。
- GPU culling 结果、粒子系统状态、indirect draw 参数、skinning 输出、物理模拟结果等。
- 数据需要随机读写、可变长度数组、跨 workgroup 聚合。

### 不适用

- 小量只读常量（优先 UBO，cache 更友好）。
- 数据需要保证跨 workgroup 原子全局序（需额外 coherent / memory barrier 设计，本工作流不深入）。
- 数据写入后需立即被同一 compute dispatch 的 consumer workgroup 读取（需 shader 内 `barrier()` + `memoryBarrier()` 同步）。

---

## 1. 任务目标

新增一个 compute pass，将结果写入 storage buffer，完成以下数据流：

```text
CPU params / previous GPU output
→ Compute Descriptor (SSBO write)
→ Compute Pipeline (dispatch)
→ VkBuffer (VK_BUFFER_USAGE_STORAGE_BUFFER_BIT)
→ Barrier (SHADER_WRITE → SHADER_READ / TRANSFER_READ / INDIRECT_COMMAND_READ)
→ Graphics Shader / DrawIndirect / CPU Readback
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- SSBO 用途：compute-only、compute → graphics、compute → indirect draw、compute → CPU readback。
- 数据大小、元素结构体、对齐要求（std430）。
- 是否需要 atomic 操作、counter buffer（append/consume）。
- 是否需要 per-frame ping-pong（双缓冲）以避免读写竞争。
- `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`、`storageBuffer16BitAccess` 等特性。
- 是否使用专用 compute queue 或复用 graphics queue。

---

## 3. 前置检查

- [ ] Validation Layer 可用，建议启用 synchronization validation。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`。
- [ ] compute pipeline 已支持 storage buffer descriptor。
- [ ] descriptor pool 对 `STORAGE_BUFFER` 有余量。
- [ ] 若 compute 写入后 graphics 读取，已设计 `VkBufferMemoryBarrier`。
- [ ] 若 compute 写入后 CPU 读取，已规划 host-visible staging buffer 或 `vkCmdCopyBuffer` 回读路径。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
CPU Data / Previous Compute Output
→ VkBuffer (VK_BUFFER_USAGE_STORAGE_BUFFER_BIT)
→ VkDeviceMemory / VMA Allocation
→ VkDescriptorSetLayout (STORAGE_BUFFER, COMPUTE stage)
→ VkDescriptorSet
→ vkCmdBindDescriptorSets(COMPUTE)
→ VkComputePipeline
→ vkCmdDispatch
→ VkBufferMemoryBarrier (ACCESS_SHADER_WRITE_BIT → ACCESS_SHADER_READ_BIT)
→ Next Consumer (Graphics Shader / DrawIndirect / CPU Readback)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| output SSBO | `VkBuffer` | `STORAGE_BUFFER_BIT` | scene / frame | 否（通常） |
| SSBO memory | `VkDeviceMemory` | device-local（性能）或 host-visible（调试） | 跟随 buffer | 否 |
| staging buffer（可选，CPU 上传） | `VkBuffer` | `TRANSFER_SRC` | 上传后释放 | 否 |
| readback buffer（可选，CPU 回读） | `VkBuffer` | `TRANSFER_DST` + host-visible | per-frame | 否 |
| descriptor set | `VkDescriptorSet` | SSBO binding | per-frame / per-pass | 视策略而定 |
| counter buffer（可选） | `VkBuffer` | `STORAGE_BUFFER_BIT` | append/consume 场景 | 否 |

设计说明：

- device-local SSBO 性能最优；host-visible 仅用于调试或 CPU 每帧更新小量参数 [ENGINE]。
- 若 compute 每帧覆盖写入同一 buffer，建议使用 ring buffer 或 ping-pong 双缓冲，避免上一帧 consumer 读到未完成的旧数据 [HEUR]。
- indirect draw buffer 必须额外加 `VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT` [SPEC]。

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `STORAGE_BUFFER` | output SSBO（compute 写入） | Compute |
| set=0,binding=1 | `STORAGE_BUFFER` / `UNIFORM_BUFFER` | input data / params | Compute |
| set=0,binding=0 | `STORAGE_BUFFER` | compute 输出的 SSBO（graphics 读取） | Vertex / Fragment |
| set=0,binding=0 | `STORAGE_BUFFER` | indirect draw buffer | Vertex（间接消费） |

设计说明：

- compute shader 中 GLSL `layout(std430, binding=0) buffer Output { ... };` 对应 Vulkan `VK_DESCRIPTOR_TYPE_STORAGE_BUFFER` [SPEC]。
- 若需要每帧切换 buffer 而不重建 descriptor set，使用 `STORAGE_BUFFER_DYNAMIC` 并通过 `vkCmdBindDescriptorSets` 传入 dynamic offset，offset 对齐到 `minStorageBufferOffsetAlignment` [SPEC]。
- compute shader 内 workgroup 间同步使用 `memoryBarrier()` + `barrier()`；跨 dispatch 或跨 queue 必须使用 Vulkan buffer memory barrier [SPEC]。
- atomic 操作前需在 device creation 启用 `shaderStorageBufferArrayDynamicIndexing` 等所需 feature，并确保 buffer memory 支持 device-local [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU upload / transfer copy | SSBO | `TRANSFER_WRITE` → `SHADER_READ` / `SHADER_WRITE` | compute shader |
| compute shader write | SSBO | `SHADER_WRITE` → `SHADER_READ` / `INDIRECT_COMMAND_READ` | graphics shader / draw indirect |
| compute shader write | SSBO | `SHADER_WRITE` → `TRANSFER_READ` | `vkCmdCopyBuffer` → host readback |
| graphics shader write | SSBO | `SHADER_WRITE` → `SHADER_READ` | compute shader |

必须说明：

- producer stage / access：`VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` + `VK_ACCESS_SHADER_WRITE_BIT`。
- consumer stage / access：graphics shader 读取为 `VK_PIPELINE_STAGE_VERTEX_SHADER_BIT | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` + `VK_ACCESS_SHADER_READ_BIT`；indirect draw 为 `VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT` + `VK_ACCESS_INDIRECT_COMMAND_READ_BIT` [SPEC]。
- storage buffer 没有 image layout，只需 `VkBufferMemoryBarrier` 或 global memory barrier 同步 access [SPEC]。
- 同 command buffer 内 compute dispatch 后立即 graphics draw，必须插入 barrier；即便在同一 queue，Vulkan 也不保证跨 stage 的隐式有序可见性 [SPEC]。
- 若 compute 写入后同一 dispatch 内的其他 workgroup 需要读取，必须在 shader 中插入 `memoryBarrier()` + `barrier()`，并在 GLSL 中使用 `coherent` 或 `volatile` 修饰 buffer [SPEC]。

---

## 8. 实现步骤

1. **确认特性与限制**：查询 `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`；启用 `storageBuffer16BitAccess` 等若需要 [SPEC]。
2. **定义数据结构**：按 std430 布局，注意数组元素对齐；GLSL 中 `layout(std430, binding=0) buffer Output { Element data[]; };` [SPEC]。
3. **创建 output buffer**：`VkBufferCreateInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT`；若作为 indirect draw buffer 加 `INDIRECT_BUFFER_BIT`；若需 CPU 回读加 `TRANSFER_SRC_BIT` [SPEC]。
4. **分配内存**：device-local 用于性能；host-visible 仅用于调试 [ENGINE]。
5. **创建 descriptor set layout**：`descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER`，`stageFlags = VK_SHADER_STAGE_COMPUTE_BIT`（compute 写入）或包含 `VERTEX/FRAGMENT`（graphics 读取）[SPEC]。
6. **分配并更新 descriptor set**：填写 `VkDescriptorBufferInfo`（buffer、offset、range），调用 `vkUpdateDescriptorSets`。range 可设为 `VK_WHOLE_SIZE` 或具体字节数 [SPEC]。
7. **录制 compute command buffer**：
   - 若 input 来自 CPU，先 staging copy 并插入 `TRANSFER_WRITE → SHADER_READ` barrier。
   - `vkCmdBindPipeline(COMPUTE)`、`vkCmdBindDescriptorSets`。
   - `vkCmdDispatch(workgroupX, workgroupY, workgroupZ)`。
   - 插入 `VkBufferMemoryBarrier`：`srcStage = COMPUTE_SHADER`，`srcAccess = SHADER_WRITE`，`dstStage = VERTEX_SHADER | FRAGMENT_SHADER | DRAW_INDIRECT`，`dstAccess = SHADER_READ | INDIRECT_COMMAND_READ`。
8. **graphics 消费**：在 draw / dispatch indirect 前确保 barrier 已完成；绑定 descriptor set 到 graphics pipeline。
9. **CPU 回读（可选）**：
   - compute dispatch 后插入 `SHADER_WRITE → TRANSFER_READ` barrier；
   - `vkCmdCopyBuffer` 到 host-visible readback buffer；
   - 等待 fence 后 `vkMapMemory` 读取 [SPEC]。
10. **动态 offset（可选）**：同一 buffer 分 slot 给多个 object，绑定命令传入 dynamic offset，对齐到 `minStorageBufferOffsetAlignment` [SPEC]。
11. **边界处理**：shader 中通过 `length()` 获取数组元素数量，避免越界；CPU 侧确保 buffer size >= `stride * count`。
12. **接入销毁路径**：按 `descriptor set → buffer → memory` 顺序释放；VMA 用户统一 `vmaDestroyBuffer`。
13. **接入 recreate**：SSBO 通常不随 swapchain 重建；若 SSBO 与 viewport 相关，resize 后更新数据内容。

---

## 9. Android 注意点

- 创建 SSBO 的 device 必须在 `ANativeWindow` 绑定到 surface 后获取，queue 才稳定 [ANDROID]。
- pause / resume 时，若 SSBO 由 compute 每帧生成，需确保 surface recreate 期间 compute queue 不提交未初始化的命令 [ANDROID]。
- rotation / resize 触发 swapchain recreate，通常不影响 SSBO；但若 SSBO 保存 screen-space 数据（如 tile 列表、可见性列表），需按新 extent 重建 [ANDROID]。
- 移动端 Adreno / Mali 对 storage buffer 的 cache 一致性策略不同：compute 写后 graphics 读必须显式 barrier，不可依赖隐式同步 [ANDROID]。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkCmdDispatch-*-None-04XXX`、`VUID-vkCmdDraw-*-None-02721` 等 storage buffer 相关错误 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 storage buffer descriptor、barrier、alignment 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：Buffer Viewer 中可见 SSBO 内容、size、offset 正确；compute dispatch 可见 [TOOL]。
- [ ] 截图 / 数值验证：compute 输出在 graphics 中正确体现（如 culling 后物体不再绘制、粒子位置正确）。
- [ ] logcat（Android）：无 validation error；可输出 SSBO 内容 hash 或关键字段用于一致性校验。
- [ ] 性能指标：
  - compute dispatch 耗时稳定；
  - graphics 读取 SSBO 阶段无异常 latency；
  - AGI 中无 redundant barrier，无跨 stage 长 stall [TOOL]。
- [ ] resize / pause / resume 后 SSBO 数据仍有效。
- [ ] 多帧运行稳定，无 flickering 或数据竞争。

---

## 11. 常见失败模式

1. **未加 `STORAGE_BUFFER_BIT`**：buffer usage 缺失导致 descriptor update 失败 [SPEC]。
2. **Compute / graphics 同步缺失**：compute 写后未 barrier，graphics 读到旧数据或触发 hazard [TOOL]。
3. **Descriptor type 与 shader 不匹配**：GLSL `buffer` 对应 `STORAGE_BUFFER`，不是 `UNIFORM_BUFFER` [SPEC]。
4. **Offset 未对齐**：dynamic offset 不是 `minStorageBufferOffsetAlignment` 整数倍 [SPEC]。
5. **数组越界**：CPU 分配的 buffer 小于 shader 中 `length()` 期望，导致 out-of-bounds 读写。
6. **atomic 操作未启用 feature**：使用 16-bit storage / atomic 前未在 device creation 启用对应 feature [SPEC]。
7. **间接绘制 buffer 未加 `INDIRECT_BUFFER_BIT`**：`vkCmdDrawIndirect` 读取 SSBO 时 validation error [SPEC]。
8. **同 dispatch 内跨 workgroup 读取未同步**：shader 中缺少 `memoryBarrier()` + `barrier()`，导致数据不一致 [SPEC]。
9. **Android surface recreate 期间提交 compute**：queue 关联的 surface 已 destroy，导致 device lost [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- `maxStorageBufferRange`、`minStorageBufferOffsetAlignment` 数值。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 SSBO 绑定状态与内容。
- Compute / graphics 命令顺序与 barrier 参数。
- GLSL buffer block 定义与 `std430` 布局。
- Android lifecycle 日志。

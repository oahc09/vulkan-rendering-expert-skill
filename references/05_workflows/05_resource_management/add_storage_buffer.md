# Workflow: Add Storage Buffer

## 0. 适用范围

### 适用

- 新增 storage buffer（SSBO）用于 compute shader 读写或 graphics shader 读取。
- 数据量超过 UBO 限制、需要 shader 写入、需要结构化数组访问。
- 粒子系统、skinning 输出、间接绘制参数、GPU culling 结果等场景。

### 不适用

- 小量只读常量（优先 UBO，cache 更友好）。
- 需要原子操作跨 workgroup 强一致性的场景（需额外 memory barrier 与 coherent 设计）。
- 需要使用 image 读写而非 buffer 的场景。

---

## 1. 任务目标

新增一个 storage buffer，完成：

```text
CPU 数据 / 上一阶段 GPU 输出
→ VkBuffer (STORAGE_BUFFER_BIT)
→ Barrier / Layout / Access 同步
→ Descriptor Update (STORAGE_BUFFER / STORAGE_BUFFER_DYNAMIC)
→ Compute / Graphics Shader 读写
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 用途：compute read/write、graphics read、indirect draw buffer。
- 数据大小、元素结构体、对齐要求（std430）。
- 是否需要 atomic 操作。
- Producer / consumer 关系：CPU → GPU、compute → graphics、graphics → compute。
- 是否需要 per-frame ping-pong 或 ring buffer。
- `storageBufferDynamic` / `storageBuffer16BitAccess` 等特性是否启用。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`、`maxStorageBufferRange`。
- [ ] compute pipeline 或 graphics pipeline 已支持 storage buffer descriptor。
- [ ] descriptor pool 对 `STORAGE_BUFFER` / `STORAGE_BUFFER_DYNAMIC` 有余量。
- [ ] 若 compute 写入后 graphics 读取，已设计 barrier。
- [ ] Android 端 `ANativeWindow` / surface 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
CPU Data / Compute Output
→ VkBuffer (VK_BUFFER_USAGE_STORAGE_BUFFER_BIT | TRANSFER_DST)
→ VkDeviceMemory / VMA Allocation
→ VkDescriptorSetLayout (STORAGE_BUFFER)
→ VkDescriptorSet
→ vkCmdBindDescriptorSets
→ Compute Pipeline 或 Graphics Pipeline
→ Barrier / Memory Barrier
→ Next Consumer (Graphics / Compute / Indirect Draw)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| storage buffer | `VkBuffer` | `STORAGE_BUFFER_BIT`（必要时加 `TRANSFER_DST` / `INDIRECT_BUFFER_BIT`） | scene / frame | 否（通常） |
| storage memory | `VkDeviceMemory` | device-local（读写）或 host-visible（调试） | 跟随 buffer | 否 |
| staging buffer | `VkBuffer` | `TRANSFER_SRC` | 上传后释放 | 否 |
| descriptor set | `VkDescriptorSet` | SSBO binding | per-frame / per-pass | 视策略而定 |
| counter buffer（可选） | `VkBuffer` | `STORAGE_BUFFER_BIT` | append/consume 场景 | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `STORAGE_BUFFER` | SSBO 整个 buffer | Compute / Vertex / Fragment |
| set=0,binding=0 | `STORAGE_BUFFER_DYNAMIC` | SSBO + dynamic offset | Compute / Vertex / Fragment |
| set=1,binding=0 | `STORAGE_BUFFER` | indirect draw buffer | Vertex（间接消费） |

设计说明：

- compute shader 写 SSBO 后，同 queue 内通常需要 `memoryBarrier()` + `barrier()` 在 GLSL 中同步；跨 queue 需要 Vulkan buffer memory barrier [SPEC]。
- graphics 读取 compute 输出的 SSBO，必须插入 `VkBufferMemoryBarrier`：`ACCESS_SHADER_WRITE_BIT` → `ACCESS_SHADER_READ_BIT` / `ACCESS_INDIRECT_COMMAND_READ_BIT` [SPEC]。
- 若 shader 中使用 `atomicAdd` 等，buffer memory 必须支持 `DEVICE_LOCAL` 且 descriptor 类型正确 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU upload / transfer copy | SSBO | `TRANSFER_WRITE` → `SHADER_READ` / `SHADER_WRITE` | compute / graphics shader |
| compute shader write | SSBO | `SHADER_WRITE` → `SHADER_READ` / `INDIRECT_COMMAND_READ` | graphics shader / draw indirect |
| graphics shader write | SSBO | `SHADER_WRITE` → `SHADER_READ` / `TRANSFER_READ` | compute / transfer copy |
| CPU readback（调试） | SSBO | `SHADER_WRITE` → `TRANSFER_READ` → host map | CPU |

必须说明：

- producer stage / access：根据实际 producer 设置，如 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` + `VK_ACCESS_SHADER_WRITE_BIT`。
- consumer stage / access：如 `VK_PIPELINE_STAGE_VERTEX_SHADER_BIT | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` + `VK_ACCESS_SHADER_READ_BIT`；间接绘制时为 `VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT` + `VK_ACCESS_INDIRECT_COMMAND_READ_BIT` [SPEC]。
- 同 pipeline 内 workgroup 间同步需 `memoryBarrier()` / `barrier()`；跨 command 或 queue 必须 Vulkan barrier [SPEC]。
- storage buffer 没有 image layout，仅需 `VkBufferMemoryBarrier` 或 global memory barrier。

---

## 8. 实现步骤

1. **确认特性与限制**：查询 `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`、`maxComputeSharedMemorySize`（如使用 shared memory）；启用 `VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES::storageBuffer16BitAccess` 等若需要 [SPEC]。
2. **定义数据结构**：按 std430 布局，注意数组元素对齐；GLSL 中 `layout(std430, binding=0) buffer` [SPEC]。
3. **创建 buffer**：`VkBufferCreateInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT`；若需 CPU 上传加 `TRANSFER_DST_BIT`；若作为 indirect draw buffer 加 `INDIRECT_BUFFER_BIT`。
4. **分配内存**：device-local 用于性能；host-visible 仅用于调试或 CPU 流式写入 [ENGINE]。
5. **上传数据（如需要）**：staging buffer → `vkCmdCopyBuffer` → buffer memory barrier `TRANSFER_WRITE → SHADER_READ|WRITE`。
6. **创建 descriptor set layout**：`descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER` 或 `VK_DESCRIPTOR_TYPE_STORAGE_BUFFER_DYNAMIC`，`stageFlags` 包含 `COMPUTE` / `VERTEX` / `FRAGMENT` [SPEC]。
7. **分配并更新 descriptor set**：填写 `VkDescriptorBufferInfo`（buffer、offset、range），调用 `vkUpdateDescriptorSets`。
8. **compute shader 写入**：dispatch 后视需要插入 GLSL `memoryBarrier()` + `barrier()`；跨 command 或 queue 时插入 `VkBufferMemoryBarrier`。
9. **graphics 消费**：在 draw 前插入 buffer barrier，producer access `SHADER_WRITE` → consumer access `SHADER_READ` / `INDIRECT_COMMAND_READ`。
10. **动态 offset（可选）**：同一 buffer 分 slot 给多个 object，绑定命令传入 dynamic offset，对齐到 `minStorageBufferOffsetAlignment` [SPEC]。
11. **边界处理**：shader 中通过 `length()` 获取数组元素数量，避免越界；CPU 侧确保 buffer size >= `stride * count`。
12. **接入销毁**：按 `descriptor set → buffer → memory` 顺序释放；若使用 VMA，统一 `vmaDestroyBuffer`。
13. **接入 recreate**：SSBO 通常不随 swapchain 重建；若 SSBO 与 viewport 相关，resize 后更新数据内容。

---

## 9. Android 注意点

- 创建 storage buffer 的 device 必须在 `ANativeWindow` 绑定到 surface 后获取，queue 才稳定 [ANDROID]。
- pause / resume 时，若 SSBO 由 compute 每帧生成，需确保 surface recreate 期间 compute queue 不提交未初始化的命令。
- rotation / resize 触发 swapchain recreate，通常不影响 SSBO；但若 SSBO 保存 screen-space 数据（如 tile 列表），需重建。
- 移动端 Adreno / Mali 对 storage buffer 的 cache 一致性策略不同：compute 写后 graphics 读必须显式 barrier，不可依赖隐式同步 [ANDROID]。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkCmdDispatch-*-None-04XXX`、`VUID-vkCmdDraw-*-None-02721` 等 storage buffer 相关错误。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 storage buffer descriptor、barrier、alignment 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：Buffer Viewer 中可见 SSBO 内容、size、offset 正确 [TOOL]。
- [ ] 截图 / 数值验证：compute 输出在 graphics 中正确体现。
- [ ] logcat（Android）：无 validation error；可输出 SSBO 内容 hash 用于一致性校验。
- [ ] 性能指标：
  - compute dispatch 耗时稳定；
  - graphics 读取 SSBO 阶段无异常 latency；
  - AGI 中无 redundant barrier [TOOL]。
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
7. **间接绘制 buffer 未加 `INDIRECT_BUFFER_BIT`**：vkCmdDrawIndirect 读取 SSBO 时 validation error [SPEC]。
8. **Android surface recreate 期间提交 compute**：queue 关联的 surface 已 destroy，导致 device lost [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

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

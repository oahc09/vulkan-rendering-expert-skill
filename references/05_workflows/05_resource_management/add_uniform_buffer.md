# Workflow: Add Uniform Buffer

## 0. 适用范围

### 适用

- 新增 per-frame / per-object / per-material 的 uniform buffer（UBO）。
- 需要处理 `minUniformBufferOffsetAlignment`、per-frame ring buffer、dynamic offset。
- 场景常量、相机矩阵、光照参数、材质参数等通过 UBO 传递给 shader。

### 不适用

- 数据量超过 `maxUniformBufferRange`（通常 64 KB），应考虑 storage buffer [SPEC]。
- 需要 shader 写入的数据，应使用 storage buffer / storage image。
- 同一 draw 中需要频繁变更大段数据且无法通过 dynamic offset 复用 descriptor。

---

## 1. 任务目标

新增一个 uniform buffer 资源，完成：

```text
CPU 常量数据（按 alignment 填充）
→ Host-visible / Device-local Uniform Buffer
→ vkUpdateDescriptorSets / Dynamic Offset
→ vkCmdBindDescriptorSets
→ Shader uniform block
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 常量结构体大小与字段对齐（std140 / std430）。
- 更新频率：per-frame、per-object、per-material。
- Frame-in-flight 数量（通常 2~3）。
- 是否需要 dynamic offset 减少 descriptor set 数量。
- 当前 descriptor set layout 是否支持 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC`。
- 是否使用 VMA 或自定义 allocator。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `minUniformBufferOffsetAlignment` 与 `maxUniformBufferRange`。
- [ ] 已确认常量结构体满足 `minUniformBufferOffsetAlignment`（dynamic offset 时）和 `minStorageBufferOffsetAlignment`（如混用 SSBO）。
- [ ] descriptor pool 对 `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` 有余量。
- [ ] frame-in-flight 机制稳定（fence / semaphore）。
- [ ] shader 编译链路可用且能生成 uniform block reflection。

---

## 4. Vulkan 对象链路

```text
CPU Constant Struct
→ Aligned CPU Copy
→ VkBuffer (Uniform, HOST_VISIBLE / DEVICE_LOCAL)
→ VkDeviceMemory / VMA Allocation
→ VkDescriptorSetLayout (UNIFORM_BUFFER / UNIFORM_BUFFER_DYNAMIC)
→ VkDescriptorSet
→ vkCmdBindDescriptorSets (+ dynamicOffset)
→ VkPipelineLayout
→ Shader Uniform Block
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| uniform buffer | `VkBuffer` | `UNIFORM_BUFFER_BIT` | per-frame / per-scene | 否 |
| uniform memory | `VkDeviceMemory` | host-visible（动态更新）或 device-local（上传） | 跟随 buffer | 否 |
| staging buffer（可选） | `VkBuffer` | `TRANSFER_SRC` | 上传完成后释放 | 否 |
| descriptor set | `VkDescriptorSet` | UBO binding | per-frame / per-pass | 视策略而定 |
| dynamic offset 数组 | `uint32_t[]` | 偏移索引 | 每帧计算 | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` | whole per-frame buffer | Vertex / Fragment / Compute |
| set=0,binding=0 | `UNIFORM_BUFFER_DYNAMIC` | same buffer，按 object 使用 dynamic offset | Vertex / Fragment / Compute |
| set=1,binding=0 | `UNIFORM_BUFFER` | per-material constants | Fragment |

设计说明：

- per-frame 全局数据（view / proj）使用固定 `UNIFORM_BUFFER` [HEUR]。
- per-object 数据（model matrix）使用 `UNIFORM_BUFFER_DYNAMIC` + ring buffer，避免每 object 分配 descriptor set [HEUR]。
- dynamic offset 必须对齐到 `minUniformBufferOffsetAlignment` [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU map/write | uniform buffer | host memory flush / invalidate | GPU shader read |
| transfer copy（device-local UBO） | staging buffer → UBO | `TRANSFER_WRITE` → `UNIFORM_READ` | vertex / fragment shader |
| previous frame read | per-frame UBO ring slot | `HOST_WRITE` / `TRANSFER_WRITE` 与 `UNIFORM_READ` 跨帧 fence 同步 | 下一帧 shader read |

必须说明：

- 对 host-visible UBO，CPU 写入后若内存非 `HOST_COHERENT`，需 `vkFlushMappedMemoryRanges`；读取前（若 CPU 读回）需 `vkInvalidateMappedMemoryRanges` [SPEC]。
- device-local UBO 需通过 transfer queue 或 graphics queue 上传，并插入 `VkBufferMemoryBarrier`：producer stage=`TRANSFER`，access=`TRANSFER_WRITE`；consumer stage=`VERTEX_SHADER | FRAGMENT_SHADER`，access=`UNIFORM_READ` [SPEC]。
- per-frame ring buffer通过 `vkWaitForFences(frameFence)` 保证 CPU 不覆盖 GPU 正在读取的帧 slot [ENGINE]。

---

## 8. 实现步骤

1. **定义常量结构体**：按 std140 / std430 布局，使用 `alignas` 或手动 padding 保证字段对齐 [SPEC]。
2. **查询限制**：调用 `vkGetPhysicalDeviceProperties` 获取 `minUniformBufferOffsetAlignment`、`maxUniformBufferRange`、`limits.nonCoherentAtomSize` [SPEC]。
3. **计算 aligned size**：`alignedSize = ((rawSize + alignment - 1) / alignment) * alignment`；ring buffer 总大小 = `alignedSize * frameInFlight`（动态 offset 时还需乘 object 数量）。
4. **创建 buffer**：`VkBufferCreateInfo.usage = VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT`；若 device-local 还需 `TRANSFER_DST_BIT`。
5. **分配内存**：host-visible 选择 `HOST_VISIBLE | HOST_COHERENT`（方便每帧 map）；device-local 选择 `DEVICE_LOCAL` 并准备 staging buffer [ENGINE]。
6. **创建 descriptor set layout**：对每个 UBO binding，填写 `VkDescriptorSetLayoutBinding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER` 或 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`，`stageFlags` 按实际 shader stage 设置 [SPEC]。
7. **分配 descriptor set**：从对应 pool 分配，确保 pool size 中 `type` 和 `descriptorCount` 足够。
8. **更新 descriptor（静态数据）**：填写 `VkDescriptorBufferInfo`（buffer + offset + range），调用 `vkUpdateDescriptorSets`。
9. **更新 descriptor（dynamic 数据）**：`VkDescriptorBufferInfo.offset = 0`、`range = alignedSize`；绑定命令 `vkCmdBindDescriptorSets` 时传入 `pDynamicOffsets` [SPEC]。
10. **CPU 更新（host-visible）**：每帧 `vkMapMemory` 对应 slot 偏移，写入数据；非 coherent 时 `vkFlushMappedMemoryRanges`。
11. **上传（device-local）**：staging buffer 写入 → `vkCmdCopyBuffer` → buffer barrier `TRANSFER_WRITE → UNIFORM_READ` → 提交。
12. **绑定渲染**：`vkCmdBindDescriptorSets` 前确保当前 frame 的 fence 已 signaled（ring buffer）。
13. **接入销毁**：frame-in-flight UBO 在 renderer 销毁时统一释放；per-object dynamic offset 不额外分配 buffer。
14. **接入 recreate**：UBO 通常不随 swapchain 重建；若 UBO 中包含 viewport 相关数据，在 resize callback 中更新。

---

## 9. Android 注意点

- `ANativeWindow` / `VkSurfaceKHR` 创建后获取的 device queue 才稳定，确保 UBO 上传命令提交到有效 queue [ANDROID]。
- pause / resume 时 frame-in-flight ring buffer 的 fence 可能因 surface destroy 被重置；恢复后重新创建 swapchain 前不要写入新的 UBO slot [ANDROID]。
- Android 部分 Mali GPU 对 host-visible UBO 的读取性能敏感；大数据量建议使用 device-local + staging 或 SSBO [ANDROID]。
- rotation / resize 触发 swapchain recreate 时，仅当 UBO 包含 surface extent / aspect 数据时才需要更新；buffer 本身通常保留。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkBindBufferMemory2-*`、`VUID-vkCmdBindDescriptorSets-*-dynamicOffsets` 等错误。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCreateBuffer-*`、`VUID-vkUpdateDescriptorSets-*`、`VUID-vkCmdBindDescriptorSets-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：在 Pipeline State → Descriptor 中可见 UBO 绑定、offset、range 正确 [TOOL]。
- [ ] 截图 / 数值验证：uniform 中的矩阵、颜色参数在渲染结果中正确体现。
- [ ] logcat（Android）：无 validation error；可添加自定义 log 输出每帧 ring buffer index。
- [ ] 性能指标：
  - CPU 更新 UBO 耗时稳定，无 map/unmap 抖动；
  - GPU frame time 无异常；
  - dynamic offset 减少 descriptor set 切换后，draw call 开销下降 [HEUR]。
- [ ] resize / pause / resume 后 UBO 数据仍正确。
- [ ] 多帧运行稳定，无 flickering（ring buffer index 未错位）。

---

## 11. 常见失败模式

1. **Offset 未对齐**：dynamic offset 不是 `minUniformBufferOffsetAlignment` 整数倍，触发 validation error [SPEC]。
2. **Range 超限**：UBO 大小超过 `maxUniformBufferRange`，部分数据读不到 [SPEC]。
3. **结构体 padding 错误**：std140 下 vec3 后未补 pad，导致 GPU 读取字段错位 [SPEC]。
4. **Ring buffer 覆盖**：未等 frame fence 就写入下一帧同 slot，出现 flickering [ENGINE]。
5. **Descriptor type 不匹配**：layout 声明 `UNIFORM_BUFFER_DYNAMIC` 但更新时用 `UNIFORM_BUFFER`，或反之 [SPEC]。
6. **未 flush host-visible 内存**：非 coherent 内存写入后未 `vkFlushMappedMemoryRanges`，GPU 读到旧数据 [SPEC]。
7. **Binding stage 错误**：`stageFlags` 未包含实际使用 uniform 的 shader stage，导致 shader 读到零值 [SPEC]。
8. **Android pause 后 UBO 数据失效**：surface destroy 后 fence 状态异常，恢复时未重置 ring buffer index。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- `minUniformBufferOffsetAlignment`、`maxUniformBufferRange` 数值。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 descriptor binding、offset、range。
- 常量结构体定义与对齐计算。
- frame-in-flight 数量与 fence 等待逻辑。
- Android lifecycle 日志。

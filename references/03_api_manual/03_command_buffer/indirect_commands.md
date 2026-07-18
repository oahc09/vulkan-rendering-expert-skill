# API Card: Indirect Commands

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 |
| Vulkan 对象 | Indirect Command Buffer |
| 常用 API | `vkCmdDrawIndirect` / `vkCmdDrawIndexedIndirect` / `vkCmdDispatchIndirect` / `vkCmdDrawMeshTasksIndirectEXT` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 核心；mesh shader 间接命令为 `VK_EXT_mesh_shader` 扩展 |

---

## 1. 一句话定位

Indirect Commands 是把 draw / dispatch 的参数从 CPU 端的 `vkCmd*` 调用搬到 GPU 端的 buffer 读取，是 GPU-driven rendering 的核心机制——draw count、vertex count、instance count、index offset、dispatch 维度等参数由 GPU 在执行期间从 `VkBuffer` 中读取，从而让 compute shader 在 GPU 上动态生成绘制命令。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice
→ VkBuffer（usage=VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT，存 VkDrawIndirectCommand / VkDrawIndexedIndirectCommand / VkDispatchIndirectCommand）
→ VkDeviceMemory（绑定）
（GPU 路径）Compute Pass 写入 command buffer
→ vkCmdPipelineBarrier（COMPUTE_SHADER → DRAW_INDIRECT / DISPATCH_INDIRECT）
→ vkCmdBindPipeline（graphics / compute / mesh）
→ vkCmdBindDescriptorSets
→ vkCmdDrawIndirect / vkCmdDrawIndexedIndirect / vkCmdDispatchIndirect / vkCmdDrawMeshTasksIndirectEXT
→ GPU 读取 buffer 解析参数并执行
```

### 上游依赖

- 已创建 `VkBuffer`，且 `usage` 包含 `VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT`。[SPEC]
- buffer 已绑定 valid memory。[SPEC]
- 若采用 GPU-driven 模式，上游包含一个 compute pass 写入 indirect buffer；若 CPU 上传，则上游是 staging copy。[ENGINE]
- `VkPipeline` 与 `VkDescriptorSet` 已正确绑定。[SPEC]
- 启用了 `multiDrawIndirect` feature 才能让 `drawCount > 1`；启用 `drawIndirectFirstInstance` 才能让 `firstInstance != 0`。[SPEC]

### 下游影响

- GPU 执行期间读取 buffer 内容并触发实际 draw / dispatch；CPU 不再逐 draw 提交命令。[SPEC]
- 间接命令数量受 `maxDrawIndirectCount` 限制。[SPEC]
- 跨 queue 的 indirect buffer 写入与读取必须配合 ownership transfer / barrier。[SPEC]
- Indirect buffer 内容在 GPU 读取期间必须保持有效（in-flight 风险）。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkBuffer`（`usage` 含 `VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT`）
- `VkDrawIndirectCommand`
- `VkDrawIndexedIndirectCommand`
- `VkDispatchIndirectCommand`
- `VkDrawMeshTasksIndirectCommandEXT`（`VK_EXT_mesh_shader`）
- `VkDrawMeshTasksIndirectCountEXT`（`VK_EXT_mesh_shader`，count 也来自 GPU）

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdDrawIndirect` | 从 buffer 读取 `VkDrawIndirectCommand` 数组执行非 indexed indirect draw。[SPEC] |
| `vkCmdDrawIndexedIndirect` | 从 buffer 读取 `VkDrawIndexedIndirectCommand` 数组执行 indexed indirect draw。[SPEC] |
| `vkCmdDispatchIndirect` | 从 buffer 读取单个 `VkDispatchIndirectCommand` 执行 indirect compute dispatch。[SPEC] |
| `vkCmdDrawMeshTasksIndirectEXT` | `VK_EXT_mesh_shader`：间接 mesh shader draw，参数从 buffer 读取。[SPEC] |
| `vkCmdDrawMeshTasksIndirectCountEXT` | `VK_EXT_mesh_shader`：count 也来自 GPU buffer 的变体，类似 `VK_KHR_draw_indirect_count`。[SPEC] |
| `vkCmdDrawIndirectCount` / `vkCmdDrawIndexedIndirectCount` | Vulkan 1.2 核心（原 `VK_KHR_draw_indirect_count`）：drawCount 来自 GPU buffer。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心：`vkCmdDrawIndirect` / `vkCmdDrawIndexedIndirect` / `vkCmdDispatchIndirect`。
- Vulkan 1.1+：需要 `VkPhysicalDeviceFeatures.multiDrawIndirect` 与 `drawIndirectFirstInstance` 才能 `drawCount > 1` 与 `firstInstance != 0`。[SPEC]
- `VK_KHR_draw_indirect_count`（1.2 核心）：drawCount 由 GPU buffer 决定。
- `VK_EXT_mesh_shader`：mesh shader 间接命令；需启用 `VkPhysicalDeviceMeshShaderFeaturesEXT.meshShader`。
- `VK_NV_device_generated_commands`：替代方案，将更完整的命令序列（bind pipeline / set / vertex buffer）通过 GPU 生成，避免多次 indirect draw 调用开销。[VENDOR]
- `VK_EXT_multi_draw`：扩展形态的批量 draw，可作为 indirect draw 的轻量替代。

### 结构体定义

```text
VkDrawIndirectCommand {
    uint32_t vertexCount;
    uint32_t instanceCount;
    uint32_t firstVertex;
    uint32_t firstInstance;   // 需 drawIndirectFirstInstance feature
}

VkDrawIndexedIndirectCommand {
    uint32_t indexCount;
    uint32_t instanceCount;
    uint32_t firstIndex;
    int32_t  vertexOffset;
    uint32_t firstInstance;   // 需 drawIndirectFirstInstance feature
}

VkDispatchIndirectCommand {
    uint32_t x;
    uint32_t y;
    uint32_t z;
}
```

字段含义与 `vkCmdDraw` / `vkCmdDrawIndexed` / `vkCmdDispatch` 的同名参数完全一致；只是数据来源从 CPU 即时参数变为 buffer 读取。[SPEC]

---

## 4. 标准使用流程

### CPU 上传参数模式（简单场景）

```text
创建 VkBuffer（usage=INDIRECT_BUFFER_BIT | TRANSFER_DST_BIT）
→ 分配 / map memory
→ CPU 写入 VkDrawIndirectCommand[]
→ unmap
→ 录制 command buffer：
   vkCmdBindPipeline
   vkCmdBindDescriptorSets
   vkCmdBindVertexBuffers / vkCmdBindIndexBuffer（indexed 场景）
   vkCmdDrawIndirect / vkCmdDrawIndexedIndirect（offset / drawCount / stride）
→ vkQueueSubmit
```

### GPU-driven 模式（典型工程路径）

```text
创建 indirect buffer（usage=INDIRECT_BUFFER_BIT | STORAGE_BUFFER_BIT | TRANSFER_DST_BIT）
创建 count buffer（如使用 indirect count 变体）
录制 command buffer：
  1. Culling compute pass：
     vkCmdBindPipeline（compute pipeline）
     vkCmdBindDescriptorSets（输入: mesh list / instance buffer / camera frustum）
     vkCmdDispatch（执行 culling + 可见性写入）
  2. Generate draw commands compute pass：
     vkCmdBindPipeline（compute pipeline，输出 indirect buffer）
     vkCmdDispatch（写入 VkDrawIndirectCommand[]）
  3. vkCmdPipelineBarrier：
     srcStageMask = COMPUTE_SHADER
     dstStageMask = DRAW_INDIRECT_BIT (graphics) / DISPATCH_INDIRECT_BIT (compute)
     buffer memory barrier：indirect buffer（offset 0，size WHOLE_SIZE）
       srcAccessMask = SHADER_WRITE_BIT
       dstAccessMask = INDIRECT_COMMAND_READ_BIT
  4. Render pass / dynamic rendering：
     vkCmdBindPipeline（graphics）
     vkCmdBindDescriptorSets
     vkCmdBindVertexBuffers / vkCmdBindIndexBuffer
     vkCmdDrawIndirect / vkCmdDrawIndexedIndirect（drawCount 可固定或来自 count buffer）
→ vkQueueSubmit
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `buffer` | 必须以 `VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT` 创建。[SPEC] | 漏标 usage，validation error 或 GPU 读取失败。[TOOL] |
| `offset` | `VkDeviceSize`，必须 4 字节对齐。[SPEC] | 错误对齐，触发 `VUID-vkCmdDrawIndirect-offset-02710` 类错误。[TOOL] |
| `drawCount` | 要执行的 draw 数量；`> 1` 需启用 `multiDrawIndirect` feature；上限受 `maxDrawIndirectCount` 限制。[SPEC] | 未启用 `multiDrawIndirect` 就传 `drawCount > 1`。[TOOL] |
| `stride` | 每条命令之间的字节距离；必须 ≥ `sizeof(VkDrawIndirectCommand)` 且为 4 的倍数。[SPEC] | stride 写成 `sizeof(float)` 或未对齐。[TOOL] |
| `VkDrawIndirectCommand.firstInstance` | 非 0 需 `drawIndirectFirstInstance` feature；用于实例化 attribute / instanced buffer 索引起点。[SPEC] | 未启用 feature 就传非 0，validation error 或 undefined behavior。[TOOL] |
| `VkDrawIndexedIndirectCommand.vertexOffset` | 加到 index 查找的 base vertex；可为负值。[SPEC] | 误以为无符号字段导致溢出截断。[ENGINE] |
| `VkDispatchIndirectCommand.x/y/z` | 每个 dimension 的 group 数；`x*y*z` 不得超过 `maxComputeWorkGroupCount`。[SPEC] | compute pass 中写入超出 limit 的值导致 dispatch 失败。[TOOL] |
| `countBuffer` / `countBufferOffset`（indirect count 变体） | 实际 drawCount 从该 buffer 的 `uint32_t` 读取；上限 `maxCount` 参数。[SPEC] | count buffer 未在 barrier 中保护，CPU 与 GPU 竞争。[ENGINE] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VkBuffer.usage` 是否包含 `INDIRECT_BUFFER_BIT`？[SPEC]
- [ ] 若采用 GPU-driven，buffer 是否同时含 `STORAGE_BUFFER_BIT`？[ENGINE]
- [ ] buffer 大小是否满足 `offset + drawCount * stride`？[SPEC]
- [ ] 是否启用了 `multiDrawIndirect` 与 `drawIndirectFirstInstance` feature？[SPEC]
- [ ] mesh shader 间接命令是否启用了 `VK_EXT_mesh_shader` 与对应 feature？[SPEC]

### 使用阶段

- [ ] `offset` 是否 4 字节对齐？[SPEC]
- [ ] `stride` 是否 ≥ 对应结构体 size 且为 4 的倍数？[SPEC]
- [ ] `drawCount` 是否 ≤ `maxDrawIndirectCount`？[SPEC]
- [ ] 若 `firstInstance != 0`，是否启用了 `drawIndirectFirstInstance`？[SPEC]
- [ ] pipeline / descriptor / vertex buffer / index buffer 是否在 indirect draw 前绑定？[SPEC]
- [ ] indexed indirect draw 前是否调用了 `vkCmdBindIndexBuffer`？[SPEC]
- [ ] `VkDrawMeshTasksIndirectCommandEXT` 的 `groupCountX/Y/Z` 是否 ≤ `maxMeshWorkGroupCount`？[SPEC]

### 同步阶段

- [ ] GPU 写入 indirect buffer 与读取之间是否插入了 `vkCmdPipelineBarrier`？[SPEC]
- [ ] barrier 的 `srcStageMask` 是否覆盖 producer（通常 `COMPUTE_SHADER`）？[SPEC]
- [ ] barrier 的 `dstStageMask` 是否为 `DRAW_INDIRECT_BIT` / `DISPATCH_INDIRECT_BIT`？[SPEC]
- [ ] `srcAccessMask = SHADER_WRITE_BIT`，`dstAccessMask = INDIRECT_COMMAND_READ_BIT`？[SPEC]
- [ ] indirect buffer 在 GPU 读取完成前是否未被 reset / overwrite？[SPEC]

### in-flight 风险

- [ ] per-frame indirect buffer 是否按 frame-in-flight 分配，避免 GPU 写入与读取冲突？[ENGINE]
- [ ] 若复用 indirect buffer，是否等到对应 fence signal 后才 reset / 重写？[SPEC]

---

## 7. 高频错误

1. `VkBuffer.usage` 漏写 `INDIRECT_BUFFER_BIT`，validation 报 `VUID-vkCmdDrawIndirect-buffer-02708`。[TOOL]
2. 未启用 `multiDrawIndirect` 就传 `drawCount > 1`。[TOOL]
3. 未启用 `drawIndirectFirstInstance` 就在 `VkDrawIndirectCommand.firstInstance` 写非 0。[TOOL]
4. compute pass 写入 indirect buffer 后未插入 barrier，GPU 读取到未完成写入或 cache 不一致的内容。[SPEC]
5. barrier stage mask 错误：把 `dstStageMask` 写成 `VERTEX_SHADER_BIT` / `FRAGMENT_SHADER_BIT`，正确应为 `DRAW_INDIRECT_BIT` / `DISPATCH_INDIRECT_BIT`。[TOOL]
6. `stride` 写成 `sizeof(VkDrawIndirectCommand)` 但 buffer 是 `std430` 数组（数组元素有 padding），导致读偏移错位。[ENGINE]
7. indirect buffer 与 draw 用的 vertex/index buffer 混淆，绘制无图元或越界。[ENGINE]
8. CPU 写入 indirect buffer 后未做 host-to-device 同步（`HOST_COHERENT` 可省，否则需 flush / barrier）。[SPEC]
9. GPU-driven 模式中 `drawCount` 仍由 CPU 决定，无法真正动态调整可见 draw 数量；应改用 `vkCmdDrawIndirectCount` / `vkCmdDrawMeshTasksIndirectCountEXT`。[ENGINE]
10. 跨 queue family 使用 indirect buffer（如 compute queue 写入、graphics queue 读取）未做 ownership transfer barrier。[SPEC]
11. 误用 `vkCmdDrawIndirectByteCountEXT`（`VK_EXT_multi_draw`），它与 `vkCmdDrawIndirect` 语义不同，是按字节总数推 draw count。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdDrawIndirect-buffer-02708`：buffer 缺少 `INDIRECT_BUFFER_BIT`。
- `VUID-vkCmdDrawIndirect-offset-02710`：offset 对齐错误。
- `VUID-vkCmdDrawIndirect-drawCount-02718` / `02719`：`multiDrawIndirect` 未启用。
- `VUID-vkCmdDrawIndirect-stride-02715` / `02716`：stride 不合法。
- `VUID-vkCmdDrawIndirectFirstInstance-*`：`drawIndirectFirstInstance` 未启用。
- `VUID-vkCmdDispatchIndirect-x-00417`：dispatch 维度超限。
- `VUID-vkCmdDrawMeshTasksIndirectEXT-*`：mesh shader 间接命令相关。

### RenderDoc / AGI

- 在 GPU Pipeline / Texture Viewer 中查看 indirect buffer 的实际内容（draw count、vertexCount、instanceCount、firstInstance）。[TOOL]
- 确认 barrier 顺序：compute pass → barrier → draw pass，时间线上不可缺失。[TOOL]
- 检查实际 draw call 数量是否与预期一致；若 drawCount=0 检查 GPU 写入逻辑。[TOOL]
- AGI System Profiler 查看 GPU utilization 与 compute / draw pass 重叠情况。[TOOL]
- 在 Mesh Viewer 中验证 vertex buffer 内容，排除 indirect draw 之外的渲染管线问题。[TOOL]

### 日志 / 代码检查

- 打印 indirect buffer 读写时机，确认 fence 同步正确。
- 在 CPU 上传模式下打印 `VkDrawIndirectCommand[]` 内容验证。
- GPU-driven 模式下，临时 dump indirect buffer 到 host 做 post-mortem 分析。
- 检查 `drawCount` 与实际 compute pass 写入的可见数量是否一致。

---

## 9. 生命周期风险

### 创建时机

- Renderer 初始化时按 frame-in-flight 数量预分配 indirect buffer；通常 per-frame 一块以避免竞争。[ENGINE]

### 使用时机

- 每帧录制：CPU 上传参数 / GPU compute pass 生成参数 → barrier → indirect draw / dispatch。[SPEC]

### 销毁时机

- 应用退出时销毁；与 frame-in-flight 的 command buffer 配合，必须在 GPU 完成后才能 free。[SPEC]

### in-flight 风险

- indirect buffer 在 GPU 执行 indirect draw / dispatch 期间必须保持有效，不能被 CPU overwrite 或 unmap。[SPEC]
- per-frame 复用时必须等对应 fence signal 才能 reset / 重写。[ENGINE]
- 多 frame-in-flight 共用同一 buffer 会导致数据竞争与渲染错误（典型症状：闪烁、几何错乱）。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 写入 indirect buffer 后，若 buffer 非 `HOST_COHERENT`，需 `vkFlushMappedMemoryRanges` 保证可见性。[SPEC]
- CPU 等待 GPU 完成后再 reset / overwrite indirect buffer，通过 fence 同步。[SPEC]
- CPU 写入后到 GPU 读取之间，若不跨 queue 通常无需 host-to-device barrier（coherent memory）；显式 barrier 用于非 coherent 或需要严格 ordering 时。[SPEC]

### GPU-GPU 同步

- compute pass 写入 indirect buffer → draw pass 读取，必须 `vkCmdPipelineBarrier`：
  - `srcStageMask = PIPELINE_STAGE_2_COMPUTE_SHADER_BIT`
  - `dstStageMask = PIPELINE_STAGE_2_DRAW_INDIRECT_BIT`（draw）/ `PIPELINE_STAGE_2_DISPATCH_INDIRECT_BIT`（dispatch）
  - `srcAccessMask = ACCESS_2_SHADER_WRITE_BIT`
  - `dstAccessMask = ACCESS_2_INDIRECT_COMMAND_READ_BIT`
  - 范围：indirect buffer 的 [offset, offset + drawCount * stride)，或 `WHOLE_SIZE`。[SPEC]
- 跨 queue（compute queue 写入 + graphics queue 读取）需要 queue ownership transfer barrier。[SPEC]
- mesh shader indirect draw 的 producer-comsumer 模型同样按上述 stage / access 配置。[SPEC]

### 资源访问同步

- vertex buffer / index buffer / descriptor 与 indirect buffer 是并行资源，各自的访问同步独立；不能省略 indirect buffer 的 barrier。[SPEC]
- count buffer（indirect count 变体）同样需要 `INDIRECT_COMMAND_READ_BIT` 可见性。[SPEC]

---

## 11. Android 注意点

- 移动端 GPU 对 `multiDrawIndirect` 支持普遍，但对 `drawIndirectFirstInstance` 支持度不一，部分老驱动 `firstInstance != 0` 触发未定义行为或 fallback 性能差；需查询并 fallback 到 CPU 重组 instance buffer。[ANDROID]
- `VK_EXT_mesh_shader` 在 Android 上仅部分桌面级 GPU 与新 Adreno / Mali 支持；移动 mesh shader 间接命令需运行时查询。[ANDROID]
- indirect buffer 应优先使用 `DEVICE_LOCAL_BIT` memory type 以获得最佳读取带宽；CPU 上传场景可用 staging buffer 一次性 copy。[ANDROID]
- 移动端 GPU-driven culling 性能收益需结合 AGI counter 验证：culling 计算开销 vs draw call 节省的 vertex shader 开销；过小场景可能反向劣化。[ANDROID]
- Adreno 部分驱动对 `vkCmdDrawIndirectCount` 行为有差异，需在目标设备实测 drawCount 读取是否正确。[ANDROID]
- 移动端建议避免每帧重新分配 indirect buffer；采用 per-frame ring buffer + fence 同步。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- indirect draw 显著降低 CPU draw call 提交开销，从 N 次 `vkCmdDraw` 降为 1 次 `vkCmdDrawIndirect`。[ENGINE]
- CPU 侧参数上传应 batch 化，避免多次 `vkCmdUpdateBuffer` / staging copy。[ENGINE]
- GPU-driven 模式下 CPU 不再遍历可见物体列表，CPU frame time 与场景物体数量解耦。[ENGINE]

### GPU 侧

- indirect draw 本身的 GPU 提交开销与 `vkCmdDraw` 相近；性能收益主要来自 CPU 侧与 GPU-driven culling。[ENGINE]
- GPU-driven culling 可减少无效 vertex shader 调用，但对小场景或简单几何，culling 计算开销可能抵消收益；需结合 GPU counter 验证。[HEUR]
- `multiDrawIndirect` 的 `drawCount` 较大时（如数千），GPU 提交管线可能成为瓶颈；考虑 `VK_NV_device_generated_commands` 替代。[VENDOR]
- mesh shader indirect draw 在适合 mesh shader pipeline 的场景（高几何密度、cluster culling）下可显著优于 vertex shader indirect draw。[HEUR]

### 移动端

- 移动端 tile-based GPU 上 indirect draw 不会增加 tile 中转开销，但 draw count 过多可能影响 tile binning。[ANDROID]
- GPU-driven culling 在移动端常见收益场景：开放世界、大量植被、粒子；小室内场景收益有限。[ANDROID]
- indirect buffer 应避免 `HOST_VISIBLE` 与 GPU 高频读取竞争；CPU 上传后用 `DEVICE_LOCAL` 副本供 GPU 读取。[ANDROID]
- compute pass 与 draw pass 之间的 barrier 在移动端尽量合并到同一 command buffer 内，避免多次 submit。[ANDROID]

---

## 13. 专家经验

**经验**：
GPU-driven rendering 的关键不是"用了 indirect draw"，而是"indirect draw 之前的 culling + command 生成 compute pass 设计正确"。常见工程路径：

1. 维护一个 GPU-resident 的 mesh instance buffer（每实例 world matrix、mesh ID、LOD 信息）。
2. Frustum + occlusion culling compute shader 输出 visible instance list。
3. 第二个 compute pass 把 visible list 转换为 `VkDrawIndirectCommand[]`（按 mesh ID 分组、计算 firstInstance）。
4. `vkCmdPipelineBarrier` 切换 indirect buffer 从 `SHADER_WRITE` 到 `INDIRECT_COMMAND_READ`。
5. 主渲染 pass 用 `vkCmdDrawIndexedIndirect` 一次性提交所有 draw。

若要彻底动态化 drawCount，使用 `vkCmdDrawIndirectCount` / `vkCmdDrawMeshTasksIndirectCountEXT`，count buffer 同样需 barrier 保护。

注意 `stride` 字段：若 indirect buffer 是 `std430` 数组且元素之间有 padding，stride 必须等于 padded size 而非 `sizeof(VkDrawIndirectCommand)`。Compute shader 写入时也要按 padded stride 偏移。

**适用条件**：
- 场景物体数量大（数千以上）。
- 需要 GPU 端动态可见性筛选。
- mesh shader pipeline 优化高密度几何。
- CPU draw call 提交成为瓶颈。

**不适用情况**：
- 场景物体数量极少（几十个 draw），CPU 直接 `vkCmdDraw` 更简单。
- 移动端小场景且 compute culling 开销高于 draw 节省。
- 项目尚处于早期、未建立 GPU-resident mesh pipeline。
- 目标设备不支持 `multiDrawIndirect` 且 draw count 必须为 1。

**来源**：`[ENGINE][SPEC][TOOL]`

---

## 14. 相关 API 卡片

- `command_buffer.md`
- `queue_submit.md`
- `../06_pipeline/compute_pipeline.md`
- `../06_pipeline/graphics_pipeline.md`
- `../05_descriptor/storage_buffer_image_descriptor.md`
- `../04_buffer_image_memory/buffer.md`
- `../08_synchronization/pipeline_barrier.md`
- `../08_synchronization/buffer_memory_barrier.md`
- `../08_synchronization/synchronization2.md`

---

## 15. 需要回查官方文档的情况

1. `VkDrawIndirectCommand` / `VkDrawIndexedIndirectCommand` / `VkDispatchIndirectCommand` 字段的精确合法范围与 feature 依赖（`firstInstance`、`vertexOffset` 是否允许负值等）。
2. `multiDrawIndirect` / `drawIndirectFirstInstance` feature 的精确语义：未启用时哪些字段必须为 0。
3. `vkCmdDrawIndirectCount` / `vkCmdDrawMeshTasksIndirectCountEXT` 的 `countBuffer` 与 `maxCount` 参数语义与 validation 规则。
4. `VK_EXT_mesh_shader` 中 `VkDrawMeshTasksIndirectCommandEXT` / `VkDrawMeshTasksIndirectCountEXT` 结构与 `groupCountX/Y/Z` 上限。
5. `vkCmdPipelineBarrier` 中 `DRAW_INDIRECT_BIT` / `DISPATCH_INDIRECT_BIT` stage 与 `INDIRECT_COMMAND_READ_BIT` access 的精确匹配规则。
6. 跨 queue family 的 indirect buffer ownership transfer barrier 写法。
7. `maxDrawIndirectCount` limit 在不同 vendor / 设备上的实际值。
8. `VK_NV_device_generated_commands` 与 `VK_EXT_multi_draw` 替代方案的差异与适用场景。
9. `VK_KHR_draw_indirect_count` 升为 Vulkan 1.2 核心后的版本兼容性。
10. 各 vendor 对 indirect count buffer 读取时序的优化建议（NVIDIA / AMD / Qualcomm / ARM 文档）。

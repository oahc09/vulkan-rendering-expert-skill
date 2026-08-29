# API Card: Mesh Shader / Task Shader

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPhysicalDeviceMeshShaderFeaturesEXT`（feature）、`VkGraphicsPipelineCreateInfo`（task/mesh stage） |
| 常用 API | `vkCmdDrawMeshTasksEXT` / `vkCmdDrawMeshTasksIndirectEXT` / `vkCmdDrawMeshTasksIndirectCountEXT` |
| 适用平台 | Desktop（NVIDIA/AMD/Intel 桌面 GPU）为主；Android 移动端支持有限，需按设备查询 |
| 来源等级 | `[SPEC] [REGISTRY] [GUIDE] [ENGINE] [HEUR]` |
| 适用 Vulkan 版本 | `VK_EXT_mesh_shader`（Vulkan 1.1+，依赖 `VK_KHR_spirv_1_4`）；`VK_NV_mesh_shader` 为早期私有扩展 |

---

## 1. 一句话定位

用计算式 stage（task → mesh）替代传统 vertex/geometry 组装，配合 meshlet 化资产实现 GPU-driven 剔除与提交，减少 CPU draw call 与顶点冗余处理。[SPEC]

---

## 2. 所属对象链路

```text
VkPhysicalDeviceFeatures2（meshShader / taskShader feature 查询）
→ VkShaderModule（task / mesh / fragment）
→ VkGraphicsPipelineCreateInfo（task + mesh stage 填入，无 vertex stage）
→ vkCmdBindPipeline（VK_PIPELINE_BIND_POINT_GRAPHICS）
→ vkCmdDrawMeshTasksEXT
→ mesh shader 输出 → rasterization → fragment shader
```

### 上游依赖

- 设备 feature：`meshShader` / `taskShader`（`VkPhysicalDeviceMeshShaderFeaturesEXT`）。[SPEC]
- SPIR-V 1.4+（GLSL `GL_EXT_mesh_shader`）。[SPEC]
- meshlet 化网格资产（顶点/索引按 meshlet 重排，经 storage buffer 供 shader 读取）。[ENGINE]

### 下游影响

- mesh 输出 primitives 直接送光栅化；与 fragment 后续链路兼容。[SPEC]
- 与 `03_api_manual/03_command_buffer/indirect_commands.md` 的 indirect draw 共享 GPU-driven 提交思想；间接变体的 count buffer 同样来自 GPU。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPhysicalDeviceMeshShaderFeaturesEXT`
- `VkPhysicalDeviceMeshShaderPropertiesEXT`（`maxMeshWorkGroupCount` / `maxMeshWorkGroupTotalCount` / `maxMeshOutputVertices` / `maxMeshOutputPrimitives` 等 limit）
- `VkGraphicsPipelineCreateInfo`（pStages 含 task/mesh stage）

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdDrawMeshTasksEXT(groupCountX, groupCountY, groupCountZ)` | 直接提交 task 分组数（groupCount 即 meshlet 分组维度）。[SPEC] |
| `vkCmdDrawMeshTasksIndirectEXT` | 参数从 GPU buffer 读取（`VkDrawMeshTasksIndirectCommandEXT`）。[SPEC] |
| `vkCmdDrawMeshTasksIndirectCountEXT` | count 也来自 GPU buffer 的变体，GPU-driven culling 的最终形态。[SPEC] |

### 相关扩展 / 版本

- `VK_EXT_mesh_shader`（跨厂商）；`VK_NV_mesh_shader`（NVIDIA 早期）。[REGISTRY]
- Vulkan 1.1+ 且依赖 `VK_KHR_spirv_1_4`（promoted 后随环境解析）。[SPEC]
- Android 是否可用：需查询设备能力；当前主流移动 GPU 支持不普遍，**必须运行时查询 feature 后再启用**。`[ANDROID]`

---

## 4. 标准使用流程

```text
查询 meshShader/taskShader feature
→ 启用 VK_EXT_mesh_shader 扩展与 feature
→ 编译 task/mesh SPIR-V（SPV_VERSION 1.4+）
→ 创建 pipeline：task(可选) + mesh + fragment，不填 vertex stage
→ meshlet 化网格资产（顶点/索引重排为 meshlet，常 64 顶点/124 三角形量级 [HEUR]）
→ vkCmdDrawMeshTasksEXT（taskCount = meshlet 分组数）
→ mesh shader 内输出最终三角形
```

GPU-driven 变体：culling pass（task shader 或 compute）写出可见 meshlet 计数 / indirect 参数 → barrier → `vkCmdDrawMeshTasksIndirectCountEXT` 一次提交，与 `03_api_manual/03_command_buffer/indirect_commands.md` 的 GPU-driven 模式同构。[ENGINE]

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| taskCount（draw 参数） | 与 mesh shader 的 local size 及 meshlet 数量匹配 | 按"三角形数"而非"task 分组数"传入 |
| `setMeshOutputsEXT` | 每次调用声明本组输出顶点/图元数 | 未调用即写输出数组 |
| mesh stage 无 vertex input | 顶点数据经 storage buffer / descriptor 读取 | 仍配置 vertex input state 导致创建失败 |
| primitive topology | mesh 输出拓扑在 shader 内声明，pipeline 填 `VK_PRIMITIVE_TOPOLOGY_...` 需与扩展要求一致（通常 mesh pipeline 忽略该字段，但部分校验器仍检查 [HEUR]） | 沿用 vertex pipeline 的 topology 语义理解 |
| `groupCountX/Y/Z` | 每个 dimension 上限受 `maxMeshWorkGroupCount` 限制，总量受 `maxMeshWorkGroupTotalCount` 限制。[SPEC] | 间接变体由 GPU 写入超限值导致 draw 失败。[TOOL] |
| mesh local size | mesh work group invocations 上限受 `maxMeshWorkGroupInvocations` 限制；输出上限受 `maxMeshOutputVertices` / `maxMeshOutputPrimitives` 限制。[SPEC] | 声明输出数组尺寸超过 limit，pipeline 创建失败。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 运行时是否通过 `VkPhysicalDeviceMeshShaderFeaturesEXT` 查询 `meshShader` / `taskShader` 均为 VK_TRUE？[SPEC]
- [ ] 设备是否启用了 `VK_EXT_mesh_shader` 扩展并勾选对应 feature？[SPEC]
- [ ] task/mesh SPIR-V 是否以 1.4+ 编译（扩展依赖 `VK_KHR_spirv_1_4`）？[SPEC]
- [ ] `VkGraphicsPipelineCreateInfo.pStages` 是否包含 mesh stage（task 可选）且不含 vertex stage？[SPEC]
- [ ] vertex input state 是否清空（无 bindings / attributes）？[SPEC]
- [ ] mesh shader 声明的输出顶点/图元上限是否 ≤ `maxMeshOutputVertices` / `maxMeshOutputPrimitives`？[SPEC]
- [ ] pipeline layout 是否覆盖 task/mesh shader 的 descriptor 布局（meshlet buffer 等以 storage buffer 绑定，参见 `03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`）？[SPEC]

### 使用阶段

- [ ] `groupCountX/Y/Z` 是否 ≤ `maxMeshWorkGroupCount`，总量 ≤ `maxMeshWorkGroupTotalCount`？[SPEC]
- [ ] taskCount 是否等于 meshlet 分组数（每组对应一个 mesh work group），而非三角形数？[ENGINE]
- [ ] mesh shader 是否在写 `gl_MeshVerticesEXT` / `gl_PrimitivesEXT` 前调用 `setMeshOutputsEXT`？[SPEC]
- [ ] meshlet buffer 的顶点/索引布局与 shader 读取 stride 是否一致（注意 `std430` padding）？[ENGINE]
- [ ] 间接变体的 count buffer / parameter buffer 是否有效（同 `03_api_manual/03_command_buffer/indirect_commands.md` 的检查点）？[SPEC]

### 同步阶段

- [ ] GPU-driven culling 写入 indirect 参数 / count buffer 后，是否插入 barrier 再执行 mesh draw？[SPEC]
- [ ] barrier 是否为 compute 风格：`SHADER_WRITE` → `INDIRECT_COMMAND_READ`，stage 覆盖 producer？[SPEC]

### in-flight 风险

- [ ] meshlet / indirect / count buffer 是否 per-frame 分配或 fence 同步，避免 GPU 写入与读取竞争？[ENGINE]

---

## 7. 高频错误

1. feature 未启用即创建 mesh pipeline（扩展与 `VkPhysicalDeviceMeshShaderFeaturesEXT` 缺一不可）。[TOOL]
2. pipeline 仍填 vertex stage：task/mesh pipeline 不允许 vertex stage 共存。[SPEC]
3. 仍配置 vertex input bindings/attributes，pipeline 创建失败或 validation 报错。[TOOL]
4. meshlet 数据布局与 shader 读取 stride 不符（`std430` 数组 padding、顶点与索引交错偏移错位），输出几何错乱。[ENGINE]
5. taskCount=0：同 compute `groupCount=0` 问题，draw 无图元输出，排查路径见 `04_debug_playbooks/04_resource_sync/compute_no_output.md`。[ENGINE]
6. 间接 draw 的 count buffer 未同步（culling pass 写入尚未可见即被读取），draw 数量随机错误。[SPEC]
7. 未调用 `setMeshOutputsEXT` 就写输出数组，输出未定义。[SPEC]
8. 间接变体由 GPU 写入超出 `maxMeshWorkGroupCount` / `maxMeshWorkGroupTotalCount` 的 groupCount，draw 失败。[TOOL]
9. 按 vertex pipeline 语义理解 primitive topology / vertexCount，把 taskCount 当三角形数传入。[HEUR]
10. SPIR-V 版本低于 1.4，shader module 创建或 pipeline 链接失败。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkGraphicsPipelineCreateInfo-pStages-*`：stage 组合非法（含 vertex stage 与 mesh stage 共存等）。
- `VUID-vkCmdDrawMeshTasksEXT-*`：groupCount 超限 / feature 未启用。
- `VUID-vkCmdDrawMeshTasksIndirectEXT-*` / `VUID-vkCmdDrawMeshTasksIndirectCountEXT-*`：间接命令 buffer usage / stride / 对齐问题（同 indirect draw 规则）。
- feature 相关 VUID：`meshShader` / `taskShader` 未启用即使用对应 stage。

### RenderDoc / AGI

- 在 GPU Pipeline 中确认 draw 类型为 mesh draw 且 pipeline 绑定正确。[TOOL]
- 查看 meshlet / vertex data buffer 的实际内容与 stride（Mesh Viewer + buffer viewer）。[TOOL]
- pipeline statistics 中对比 mesh 输出 primitive 数与预期（验证 culling 与 `setMeshOutputsEXT`）。[TOOL]
- AGI System Profiler 查看 task/mesh stage 占用率与 wave 效率，判断 meshlet 尺寸是否合理。[TOOL]
- 时间线确认 culling pass → barrier → mesh draw 的顺序与 barrier 是否存在。[TOOL]

### 日志 / 代码检查

- 打印 feature 查询结果（`meshShader` / `taskShader`），确认设备支持路径。
- 打印 taskCount 与 meshlet 分组数，确认两者匹配而非三角形数。
- 临时 dump indirect / count buffer 到 host，验证 GPU 写入值与同步时序。
- 检查 meshlet 化工具的顶点/索引布局常量与 shader 内 stride 声明是否一致。

---

## 9. 生命周期风险

### 创建时机

- meshlet 化资产在离线工具阶段生成（顶点/索引重排）；mesh pipeline 在 renderer 初始化时创建。[ENGINE]

### 使用时机

- 每帧录制：`vkCmdBindPipeline` → bind descriptor（meshlet buffer）→ `vkCmdDrawMeshTasksEXT` / 间接变体。[SPEC]

### 销毁时机

- meshlet buffer 与 pipeline 常驻整个应用生命周期；销毁前必须等待 GPU 完成（fence signal）。[SPEC]

### in-flight 风险

- GPU-driven culling 模式下，indirect / count buffer 被 in-flight command buffer 引用，在对应 fence signal 前不能 reset / overwrite；per-frame ring buffer 是常见解法。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 上传 meshlet / indirect 参数后，若 memory 非 `HOST_COHERENT` 需 `vkFlushMappedMemoryRanges`。[SPEC]
- CPU 修改 buffer 前必须等 GPU 完成（fence）。[SPEC]

### GPU-GPU 同步

- GPU-driven culling（task shader 内剔除后写 indirect 参数，或独立 compute 剔除 pass）需要 compute 风格的 memory barrier 覆盖：`srcStageMask = COMPUTE_SHADER`（或 task/mesh 输出写入 stage），`dstStageMask = DRAW_INDIRECT_BIT`，`srcAccessMask = SHADER_WRITE_BIT`，`dstAccessMask = INDIRECT_COMMAND_READ_BIT`；跨 draw 依赖同 `03_api_manual/08_synchronization/pipeline_barrier.md`。[SPEC]
- culling 结果同时被后续 mesh draw 的 storage buffer 读取时，还需覆盖 `SHADER_READ` 可见性。[SPEC]
- 跨 queue（compute queue 剔除 + graphics queue 绘制）需 ownership transfer barrier。[SPEC]

### 资源访问同步

- meshlet buffer 为 storage buffer 读取（无 vertex input），多 pass 复用时按普通 storage buffer 的访问同步处理，参见 `03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`。[ENGINE]

---

## 11. Android 注意点

- `VK_EXT_mesh_shader` 在 Android 上支持有限：主流移动 GPU 支持不普遍，部分新 Adreno / Mali 驱动与桌面级 SoC 才具备；**必须运行时查询 `VkPhysicalDeviceMeshShaderFeaturesEXT` 后再启用**，不得按品牌/型号假设。[ANDROID]
- 不支持时的回退路径：传统 vertex pipeline + multi-draw indirect（GPU-driven 收益仍可保留大半），参见 `03_api_manual/03_command_buffer/indirect_commands.md`。[ANDROID]
- 移动端若支持，meshlet 尺寸与 task local size 需按移动 GPU 的 wave/子组粒度实测（桌面经验值直接迁移常劣化）。[ANDROID]
- 用 AGI System Profiler 验证 task/mesh 占用率与剔除收益，小场景可能出现 culling 开销大于收益的反向劣化。[ANDROID]
- 回退路径在移动端的 `multiDrawIndirect` / `drawIndirectFirstInstance` 支持差异同样需运行时查询。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- mesh shader 把 draw call 提交从 CPU 每物体一次降为整场景一次（配合 indirect count），CPU frame time 与物体数量解耦。[ENGINE]
- meshlet 化为离线成本，运行时 CPU 无额外组装开销。[ENGINE]

### GPU 侧

- meshlet 大小影响顶点复用率与 task 占用率 [HEUR]（适用条件：桌面 GPU；移动端需实测，常用起点为 64 顶点 / 124 三角形量级 [HEUR]）。
- 收益主要来自 GPU-driven culling 剔除不可见 meshlet（省掉顶点着色开销）与 CPU draw call 卸载，而不是单三角形吞吐提升；小场景或简单几何可能无收益。[ENGINE]
- task shader 层级剔除（粗粒度）+ mesh shader 内精细剔除的两级结构在密集几何场景收益明显 [HEUR]（适用条件：桌面 GPU，高几何密度资产）。
- 输出顶点/图元超出组内实际需求会浪费 invocation；`setMeshOutputsEXT` 应按实际输出声明。[ENGINE]

### 移动端

- 移动端支持设备少，性能数据稀缺；启用前必须按设备实测，且保留 vertex pipeline 回退路径（见 §11）。[ANDROID]
- 移动 tile-based GPU 上 mesh shader 对 binning 的收益与桌面不同，需 AGI counter 验证后再决策。[ANDROID]

---

## 13. 专家经验

```text
经验：
mesh shader 的收益主要来自 GPU-driven culling 与 CPU draw call 卸载，而不是单三角形吞吐提升。

适用条件：
场景 draw call 数量大、CPU 提交成瓶颈、资产可离线 meshlet 化、目标平台支持扩展。

不适用情况：
目标平台不支持（多数当前 Android 设备）；资产无法 meshlet 化（程序化几何频繁变化）；draw call 数量本身不多。
```

工程路径通常为：离线 meshlet 化 → storage buffer 存 meshlet 数据 → task shader 剔除（或独立 compute culling pass）→ indirect count buffer → `vkCmdDrawMeshTasksIndirectCountEXT` 一次提交；不支持的平台回退 vertex pipeline + multi-draw indirect（`03_api_manual/03_command_buffer/indirect_commands.md`）。[ENGINE]

**来源**：`[ENGINE][SPEC][HEUR]`

---

## 14. 相关 API 卡片

- `03_api_manual/03_command_buffer/indirect_commands.md`
- `03_api_manual/06_pipeline/graphics_pipeline.md`
- `03_api_manual/06_pipeline/shader_module.md`
- `03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`

---

## 15. 需要回查官方文档的情况

1. `VK_EXT_mesh_shader` 在目标设备的支持情况。
2. taskCount / meshlet 输出上限（`maxMeshWorkGroupTotalCount` 等 limit）。
3. 与其他 stage/feature 的交互限制。
4. `VK_NV_mesh_shader` 与 `VK_EXT_mesh_shader` 的语义差异（NV 版无 task stage 输出上限细节差异等）。
5. `setMeshOutputsEXT` / 输出数组的 validation 规则与未定义行为边界。
6. Android 目标设备（Adreno / Mali / PowerVR）驱动对扩展的实际支持与已知缺陷。

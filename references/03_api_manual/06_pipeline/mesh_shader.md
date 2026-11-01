# API Card: Mesh Shader / Task Shader

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPhysicalDeviceMeshShaderFeaturesEXT`（feature）、`VkGraphicsPipelineCreateInfo`（task/mesh stage） |
| 常用 API | `vkCmdDrawMeshTasksEXT` / `vkCmdDrawMeshTasksIndirectEXT` / `vkCmdDrawMeshTasksIndirectCountEXT` |
| 适用平台 | 逐设备查询 feature / properties；保留传统 vertex 路径 |
| 来源等级 | `[SPEC] [REGISTRY] [ENGINE] [HEUR]` |
| 适用 Vulkan 版本 | `VK_EXT_mesh_shader`（依赖 `VK_KHR_spirv_1_4` 或 Vulkan 1.2）；`VK_NV_mesh_shader` 为早期私有扩展 |

---

## 1. 一句话定位

用计算式 stage（task → mesh）替代传统 vertex/geometry 组装，配合 meshlet 化资产实现 GPU-driven 剔除与提交，有机会减少 CPU 提交与顶点冗余；收益须实测。[SPEC]

---

## 2. 所属对象链路

```text
VkPhysicalDeviceFeatures2（meshShader / taskShader feature 查询）
→ VkShaderModule（task / mesh / fragment）
→ VkGraphicsPipelineCreateInfo（mesh stage 与可选 task stage，无 vertex stage）
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
- `VkPhysicalDeviceMeshShaderPropertiesEXT`（`maxTaskWorkGroupCount` / `maxTaskWorkGroupTotalCount` / `maxMeshWorkGroupCount` / `maxMeshWorkGroupTotalCount` / `maxMeshOutputVertices` / `maxMeshOutputPrimitives` 等 limit）
- `VkGraphicsPipelineCreateInfo`（pStages 含 task/mesh stage）

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdDrawMeshTasksEXT(groupCountX, groupCountY, groupCountZ)` | 有 task stage 时提交 task workgroups，否则提交 mesh workgroups；不等于自动一组一个 meshlet。[SPEC] |
| `vkCmdDrawMeshTasksIndirectEXT` | 参数从 GPU buffer 读取（`VkDrawMeshTasksIndirectCommandEXT`）。[SPEC] |
| `vkCmdDrawMeshTasksIndirectCountEXT` | count 也来自 GPU buffer 的可选变体，不是 GPU-driven 的必要条件。[SPEC] |

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
→ vkCmdDrawMeshTasksEXT（taskCount = meshlet 分组数，即 EXT 的 groupCountX/Y/Z draw 参数）
→ mesh shader 内输出最终三角形
```

GPU-driven 变体：culling pass（task shader 或 compute）写出可见 meshlet 计数 / indirect 参数 → barrier → `vkCmdDrawMeshTasksIndirectCountEXT` 一次提交，与 `03_api_manual/03_command_buffer/indirect_commands.md` 的 GPU-driven 模式同构。[ENGINE]

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| taskCount（draw 参数，对应 EXT 的 groupCountX/Y/Z） | 与 mesh shader 的 local size 及 meshlet 数量匹配 | 按"三角形数"而非"task 分组数"传入 |
| `SetMeshOutputsEXT` | 每次调用声明本组输出顶点/图元数 | 未调用即写输出数组 |
| mesh stage 无 vertex input | 顶点数据经 storage buffer / descriptor 读取；`pVertexInputState` 在含 mesh stage 的 pipeline 中被规范忽略，官方示例置 NULL [SPEC][ENGINE] | 顶点数据仍按 vertex input 路径（bindings/attributes）提供而非 storage buffer 读取 |
| primitive topology | input assembly state（含 topology）在 mesh pipeline 中被规范忽略，拓扑由 mesh shader 内 `OpExecutionMode` 声明。[SPEC] | 沿用 vertex pipeline 的 topology 语义理解 |
| `groupCountX/Y/Z` | 带 task stage 时 draw 参数受 task 侧 limit 约束（每维 ≤ `maxTaskWorkGroupCount`，总量 ≤ `maxTaskWorkGroupTotalCount`）；task shader 内 `OpEmitMeshTasksEXT` 参数受 mesh 侧 limit 约束（每维 ≤ `maxMeshWorkGroupCount`，总量 ≤ `maxMeshWorkGroupTotalCount`）；无 task stage 时 draw 参数直接受 mesh 侧 limit 约束。[SPEC] | 间接变体由 GPU 写入超限值导致 draw 失败。[TOOL] |
| mesh local size | mesh work group invocations 上限受 `maxMeshWorkGroupInvocations` 限制；输出上限受 `maxMeshOutputVertices` / `maxMeshOutputPrimitives` 限制。[SPEC] | 声明输出数组尺寸超过 limit，pipeline 创建失败。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 运行时查询且创建设备启用了 meshShader？仅使用 task stage 时另需 taskShader；无 task 的 mesh 路径合法。[SPEC]
- [ ] 设备是否启用了 `VK_EXT_mesh_shader` 扩展并勾选对应 feature？[SPEC]
- [ ] task/mesh SPIR-V 是否以 1.4+ 编译（扩展依赖 `VK_KHR_spirv_1_4`）？[SPEC]
- [ ] `VkGraphicsPipelineCreateInfo.pStages` 是否包含 mesh stage（task 可选）且不含 vertex stage？[SPEC]
- [ ] 顶点数据是否改经 storage buffer 提供（`pVertexInputState` 在含 mesh stage 的 pipeline 中被规范忽略，官方示例置 NULL [ENGINE]）？[SPEC]
- [ ] mesh shader 声明的输出顶点/图元上限是否 ≤ `maxMeshOutputVertices` / `maxMeshOutputPrimitives`？[SPEC]
- [ ] pipeline layout 是否覆盖 task/mesh shader 的 descriptor 布局（meshlet buffer 等以 storage buffer 绑定，参见 `03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`）？[SPEC]

### 使用阶段

- [ ] `groupCountX/Y/Z` 上限按 stage 归属核对：带 task stage 时 draw 参数是否 ≤ `maxTaskWorkGroupCount`（每维）且总量 ≤ `maxTaskWorkGroupTotalCount`；task 内 `OpEmitMeshTasksEXT` 参数与无 task stage 时的 draw 参数是否 ≤ mesh 侧 `maxMeshWorkGroupCount` / `maxMeshWorkGroupTotalCount`？[SPEC]
- [ ] task/mesh group count 是否符合资产与 shader 映射和各轴/total limits（不要求一一对应），而非三角形数？[ENGINE]
- [ ] mesh shader 是否在写 `gl_MeshVerticesEXT` / `gl_PrimitivesEXT` 前调用 `SetMeshOutputsEXT`？[SPEC]
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
3. 顶点数据仍按 vertex input 路径提供：`pVertexInputState` 在含 mesh stage 的 pipeline 中被规范忽略（bindings/attributes 不生效，官方示例置 NULL [ENGINE]），应改经 storage buffer 读取。[SPEC][ENGINE]
4. meshlet 数据布局与 shader 读取 stride 不符（`std430` 数组 padding、顶点与索引交错偏移错位），输出几何错乱。[ENGINE]
5. taskCount=0：同 compute `groupCount=0` 问题，draw 无图元输出，排查路径见 `04_debug_playbooks/04_resource_sync/compute_no_output.md`。[ENGINE]
6. 间接 draw 的 count buffer 未同步（culling pass 写入尚未可见即被读取），draw 数量随机错误。[SPEC]
7. 未调用 `SetMeshOutputsEXT` 就写输出数组，输出未定义。[SPEC]
8. 间接变体由 GPU 写入超限 groupCount，draw 失败：带 task stage 时 draw 参数超 task 侧 `maxTaskWorkGroupCount` / `maxTaskWorkGroupTotalCount`；task 内 `OpEmitMeshTasksEXT` 参数与无 task stage 时的 draw 参数超 mesh 侧 `maxMeshWorkGroupCount` / `maxMeshWorkGroupTotalCount`。[TOOL]
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
- pipeline statistics 中对比 mesh 输出 primitive 数与预期（验证 culling 与 `SetMeshOutputsEXT`）。[TOOL]
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

- GPU-driven culling（独立 compute 剔除 pass，或确实写入下一次 draw 参数的 shader）需要 compute 风格的 memory barrier 覆盖：`srcStageMask = COMPUTE_SHADER`（或 task/mesh 输出写入 stage），`dstStageMask = DRAW_INDIRECT_BIT`，`srcAccessMask = SHADER_WRITE_BIT`，`dstAccessMask = INDIRECT_COMMAND_READ_BIT`；跨 draw 依赖同 `03_api_manual/08_synchronization/pipeline_barrier.md`。[SPEC]
- culling 结果同时被后续 mesh draw 的 storage buffer 读取时，还需覆盖 `SHADER_READ` 可见性。[SPEC]
- 跨 queue 需 semaphore；仅跨 family 的 exclusive 资源还需匹配 ownership release/acquire。[SPEC]

### 资源访问同步

- meshlet buffer 为 storage buffer 读取（无 vertex input），多 pass 复用时按普通 storage buffer 的访问同步处理，参见 `03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`。[ENGINE]

---

## 11. Android 注意点

- `VK_EXT_mesh_shader` 必须运行时查询/启用所用 feature 与 properties，不能按品牌或型号假设支持。[ANDROID]
- 不支持时的回退路径：传统 vertex pipeline + multi-draw indirect（收益比例未知，需实测），参见 `03_api_manual/03_command_buffer/indirect_commands.md`。[ANDROID]
- 移动端若支持，meshlet 尺寸与 task local size 需按移动 GPU 的 wave/子组粒度实测（桌面经验值直接迁移常劣化）。[ANDROID]
- 用 AGI System Profiler 验证 task/mesh 占用率与剔除收益，小场景可能出现 culling 开销大于收益的反向劣化。[ANDROID]
- 回退路径在移动端的 `multiDrawIndirect` / `drawIndirectFirstInstance` 支持差异同样需运行时查询。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- mesh draw 仍按相容 pipeline/material/resource bins 提交；与 CPU 合批及传统 GPU-driven 基线比较，不保证整场景一次或 CPU 成本与规模无关。[ENGINE]
- meshlet 可离线生成；程序化/动态几何需另外计入构建、上传、重排和内存成本。[ENGINE]

### GPU 侧

- meshlet 大小影响顶点复用率与 task 占用率 [HEUR]（适用条件：桌面 GPU；移动端需实测，常用起点为 64 顶点 / 124 三角形量级 [HEUR]）。
- 收益主要来自 GPU-driven culling 剔除不可见 meshlet（省掉顶点着色开销）与 CPU draw call 卸载，而不是单三角形吞吐提升；小场景或简单几何可能无收益。[ENGINE]
- task shader 层级剔除（粗粒度）+ mesh shader 内精细剔除的两级结构在密集几何场景收益明显 [HEUR]（适用条件：桌面 GPU，高几何密度资产）。
- 输出顶点/图元超出组内实际需求会浪费 invocation；`SetMeshOutputsEXT` 应按实际输出声明。[ENGINE]

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

<a id="mesh-path-fallback"></a>
### mesh-path-fallback

meshShader 与 taskShader 分别查询/启用；task stage 可省略，不能把两者当单一布尔值。查询 maxTask/meshWorkGroupCount 各轴与 total、workgroup invocations、payload/shared memory、output vertex/primitive/components 等限制；meshlet 离线尺寸与 shader local size 取设备支持范围内的策略，不把 64/124 作为跨 GPU 标准。[SPEC][ENGINE]

EXT 路径使用 GLSL `SetMeshOutputsEXT`、`EmitMeshTasksEXT` 与对应 EXT SPIR-V execution model；NV 路径不是改函数名即可互换。资产 meshlet bounds 必须含变形/缩放后的保守范围。无 task 可直接 mesh；无 mesh 回退传统 vertex + fixed-slot indirect / 可选 Count；无 MDI 可逐命令 indirect 或 CPU 合批。fallback 保留相同 scene IDs、LOD/residency、材质和视图，不偷减画质宣称加速。[ENGINE]

只在真实支持设备运行后记录 mesh/task、pipeline binary/GPL 或 async queue 的性能；软件实现缺扩展可标 conditional-not-run，不用 CPU 合约测试替代 GPU 执行。固定规范：[VK_EXT_mesh_shader](https://github.com/KhronosGroup/Vulkan-Docs/blob/b94f8bd2d004d2949469d8a5071ee10eb7d23566/appendices/VK_EXT_mesh_shader.adoc)。GLSL 接口核对 [Khronos GLSL extension](https://github.com/KhronosGroup/GLSL/blob/main/extensions/ext/GLSL_EXT_mesh_shader.txt)，编译工具及 SPIR-V target environment 单独记录。

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
5. `SetMeshOutputsEXT` / 输出数组的 validation 规则与未定义行为边界。
6. Android 目标设备（Adreno / Mali / PowerVR）驱动对扩展的实际支持与已知缺陷。

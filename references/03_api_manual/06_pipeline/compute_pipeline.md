# API Card: VkPipeline (Compute)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipeline` |
| 常用 API | `vkCreateComputePipelines` / `vkDestroyPipeline` / `vkCmdBindPipeline` / `vkCmdDispatch` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipeline`（compute）封装 compute shader 执行状态，绑定到 compute bind point 后通过 `vkCmdDispatch` 启动线程格；它是 graphics pipeline 的简化形态，只包含单一 compute stage 与 pipeline layout。[SPEC]

---

## 2. 所属对象链路

```text
Compute Shader (SPIR-V)
→ VkShaderModule
→ VkPipelineShaderStageCreateInfo (stage = COMPUTE)
→ VkPipelineLayout
→ vkCreateComputePipelines
→ VkPipeline
→ vkCmdBindPipeline(VK_PIPELINE_BIND_POINT_COMPUTE)
→ vkCmdDispatch / vkCmdDispatchIndirect
→ Compute Shader writes/reads resources
```

### 上游依赖

- Compute shader module 已创建，且入口点为 compute stage。[SPEC]
- Pipeline layout 与 shader 的 descriptor set / push constant 接口匹配。[SPEC]
- 目标 queue family 支持 compute 操作。[SPEC]

### 下游影响

- Compute pipeline 决定 dispatch 的 shader 代码与资源接口。[SPEC]
- Dispatch 后的结果通常需要 barrier 才能被 graphics / transfer 使用。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipeline`
- `VkComputePipelineCreateInfo`
- `VkPipelineShaderStageCreateInfo`
- `VkPipelineLayout`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateComputePipelines` | 创建 compute pipeline。[SPEC] |
| `vkDestroyPipeline` | 销毁 pipeline；必须等待 GPU 完成。[SPEC] |
| `vkCmdBindPipeline` | 在 command buffer 中绑定 compute pipeline。[SPEC] |
| `vkCmdDispatch` | 启动三维线程格。[SPEC] |
| `vkCmdDispatchIndirect` | 从 buffer 读取 dispatch 参数。[SPEC] |
| `vkCmdDispatchBase` | 指定 base group 的 dispatch。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_device_group` 相关的 `vkCmdDispatchBase` 用法需查文档。

---

## 4. 标准使用流程

```text
准备 compute SPIR-V
→ vkCreateShaderModule
→ 填写 VkPipelineShaderStageCreateInfo
    → stage = VK_SHADER_STAGE_COMPUTE_BIT
    → module
    → pName
    → pSpecializationInfo (可选)
→ 确认 pipeline layout 与 shader 接口一致
→ vkCreateComputePipelines
→ vkCmdBindPipeline(COMPUTE)
→ vkCmdBindDescriptorSets(COMPUTE)
→ 设置 push constants（如有）
→ 插入必要 barrier（如读取前一次结果）
→ vkCmdDispatch(groupCountX, groupCountY, groupCountZ)
→ 若结果供后续 graphics 使用，插入 barrier
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `stage.stage` | 必须是 `VK_SHADER_STAGE_COMPUTE_BIT`。[SPEC] | 填成 VERTEX 或 FRAGMENT。[TOOL] |
| `stage.module` | compute shader module。[SPEC] | 复用 graphics shader module。[TOOL] |
| `stage.pName` | 入口点名称，与 SPIR-V 一致。[SPEC] | 入口点写错导致 pipeline 创建失败。[TOOL] |
| `stage.pSpecializationInfo` | 覆盖 compute shader 中的 specialization constants。[SPEC] | constantID / offset 不匹配。[TOOL] |
| `layout` | 必须是包含 compute shader 所需 descriptor set / push constant 的 pipeline layout。[SPEC] | layout 缺少 storage buffer/image 的 set。[TOOL] |
| `basePipelineHandle` / `basePipelineIndex` | pipeline derivative 的 base，不常用。[SPEC] | 误用导致创建失败或不可预期行为。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Shader module 是 compute stage？
- [ ] Pipeline layout 覆盖所有 descriptor set 与 push constant？
- [ ] Specialization constants 是否正确映射？

### 使用阶段

- [ ] 是否在 compute bind point 绑定？
- [ ] 是否绑定了正确的 descriptor set（compute bind point）？
- [ ] Dispatch 前是否对资源做了合适 barrier？
- [ ] `groupCountX/Y/Z` 是否非零？（零 dispatch 无输出）[TOOL]
- [ ] 是否在 compute queue 或支持 compute 的 universal queue 上提交？[SPEC]

### 销毁阶段

- [ ] 等待 fence 确保 GPU 不再使用。
- [ ] 若 pipeline cache 使用，注意 cache 与 pipeline 的销毁顺序。

---

## 7. 高频错误

1. `stage` 未填 `VK_SHADER_STAGE_COMPUTE_BIT`。[TOOL]
2. Pipeline layout 未包含 storage image / storage buffer 的 descriptor set layout。[TOOL]
3. Dispatch 前未对输入资源做 availability / layout transition barrier。[TOOL]
4. Dispatch 后未对输出资源做 barrier，导致 graphics pass 读到旧数据。[TOOL]
5. `groupCountX/Y/Z` 任意维度为 0，导致 dispatch 无输出。[TOOL]
6. 在 graphics queue 上提交 compute work 但 queue 不支持 compute。[TOOL]
7. Storage image layout 不是 `GENERAL`。[TOOL]
8. Compute shader 中 local work group size 与 dispatch size 不匹配导致边界处理错误。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkComputePipelineCreateInfo-*`：stage、layout 合法性。
- `VUID-vkCmdBindPipeline-*`：bind point 与 pipeline 类型匹配。
- `VUID-vkCmdDispatch-*`：group count 上限、descriptor与执行作用域合法；零group无工作，不自动构成违规。
- `VUID-vkCmdDraw-*` / dispatch hazard：synchronization hazard 提示。

### RenderDoc / AGI

- 查看 compute pipeline 的 shader、descriptor binding、push constant。
- 查看 dispatch 参数。
- 查看 storage buffer / image 在 dispatch 前后的内容。

### 日志 / 代码检查

- 检查 `vkCreateComputePipelines` 返回值与 shader 编译日志。
- 检查 dispatch 参数是否非零。
- 检查 barrier 的 srcStage/dstStage、srcAccess/dstAccess。
- 检查 storage image 的 layout 是否为 `VK_IMAGE_LAYOUT_GENERAL`。

---

## 9. 生命周期风险

### 创建时机

- 初始化或首次使用 compute pass 前；建议配合 pipeline cache。[ENGINE]

### 使用时机

- 普通 `vkCmdDispatch` 在 render pass instance 外执行；secondary command buffer 不豁免作用域。扩展专用路径须另查其规则。[SPEC]

### 销毁时机

- 确认 GPU 完成后销毁。[SPEC]

### in-flight 风险

- Pipeline 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Pipeline 创建后立即可用；dispatch 提交后通过 fence 等待结果。[SPEC]

### GPU-GPU 同步

- Compute 写入 storage buffer/image 后，如需被 graphics/transfer 消费，必须插入 pipeline barrier，常见：
  ```text
  srcStage = COMPUTE_SHADER, srcAccess = SHADER_WRITE
  dstStage = FRAGMENT_SHADER / VERTEX_SHADER / TRANSFER, dstAccess = SHADER_READ / TRANSFER_READ
  ```
  [SPEC]
- 跨 queue 时需要 semaphore。[SPEC]

### 资源访问同步

- Storage image 在 compute 读写时 layout 通常为 `GENERAL`。[SPEC]
- Storage buffer 写入后需要 availability / visibility barrier。[SPEC]

---

## 11. Android 注意点

- Android 上 compute queue 可能是独立的，也可能与 graphics 共享 universal queue；需检查 `vkGetPhysicalDeviceQueueFamilyProperties`。[ANDROID]
- 移动端 compute 功耗高，谨慎用于高频全屏 pass。[ENGINE]
- `local_size_x/y/z` 建议取 wave size 倍数（如 8/16）以提升占用率，但具体最优值随 GPU 变化。[HEUR]
- AGI 可分析 compute dispatch 耗时与资源依赖。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Compute pipeline 创建成本低于 graphics pipeline，但仍建议启用 pipeline cache。[ENGINE]
- 大量小 dispatch 会增加 CPU 与 command processor 开销；尽量合并或间接 dispatch。[ENGINE]

### GPU 侧

- Compute shader 占用率受 local work group size 与寄存器压力影响。[HEUR]
- 避免 compute 与 graphics 频繁来回切换；尽量把 compute work 集中在一端。[ENGINE]

### 移动端

- 移动端 bandwidth 敏感，compute 读写 large storage image/buffer 容易成为瓶颈。[ENGINE]
- Shared memory / workgroup memory 使用需权衡 bank conflict。[HEUR]
- 避免在 fragment pass 中间插入 compute barrier 导致 tile flush。[ENGINE]

---

## 13. 专家经验

**经验**：
把 compute pass 视为“异步 GPU 任务”：明确 producer/consumer，显式插入 barrier。不要让 compute 隐式假设 graphics 已经写完，也不要让 graphics 隐式假设 compute 已经算完。用 event 或 barrier 把依赖显式化。

**适用条件**：
compute 与 graphics 混合的后处理、粒子、剔除、GPU culling 等场景。

**不适用情况**：
纯 compute 离线任务，可用单一 queue 与 fence 简单同步。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `shader_module.md`
- `pipeline_layout.md`
- `graphics_pipeline.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../05_descriptor/descriptor_update.md`
- `../04_buffer_image_memory/buffer.md`
- `../04_buffer_image_memory/image.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. Compute shader 中 `LocalSize` 与 `vkCmdDispatch` 的精确关系。
2. Storage image / storage buffer 的 layout 与 access flag 要求。
3. Compute 与 graphics 在同一 queue 与不同 queue 的同步语义差异。
4. `vkCmdDispatchIndirect` 的 buffer usage 与 alignment 要求。
5. 普通 `vkCmdDispatch` 必须在 render pass instance 外执行；如使用 tile shading 等扩展的特殊执行路径，应逐项核对该扩展的命令作用域，不能把普通 compute dispatch 当作通用 subpass 操作。[SPEC]

<a id="ray-query-capability-contract"></a>
## Ray Query 独立能力合同

Query 可在现有 graphics（如 fragment）或 compute shader 中执行；本卡位置不限制为 compute。查询 `vkEnumerateDeviceExtensionProperties`、`vkGetPhysicalDeviceFeatures2` 与所用 limits，依据固定 Registry 解析完整依赖并在 `vkCreateDevice` 启用所需 feature：[REGISTRY][SPEC]

- `VK_KHR_ray_query` / `VkPhysicalDeviceRayQueryFeaturesKHR.rayQuery`。
- `VK_KHR_acceleration_structure` / `VkPhysicalDeviceAccelerationStructureFeaturesKHR.accelerationStructure`，所选 API 版本对应的 deferred host operations 等依赖。
- buffer device address 的 core/extension 路径及 `bufferDeviceAddress`，输入/scratch 的正确 usage、地址和内存分配标志。
- 查询 AS properties（含 scratch 对齐、geometry/instance/primitive 上限），shader target / SPIR-V RayQuery 能力与设备一致。

固定 Registry 的最小依赖展开：Vulkan 1.2 路径为 ray_query + acceleration_structure + deferred_host_operations（BDA 的 core feature 仍须启用）；Vulkan 1.1 路径另需 EXT_descriptor_indexing、KHR_buffer_device_address、KHR_spirv_1_4 及其 KHR_shader_float_controls。这里 descriptor_indexing 是扩展依赖，不强制启用非均匀索引/update-after-bind 等未使用特性，也不要求 bindless 架构。继续按所用符号/feature 检查传递依赖。[REGISTRY]

Query-only **不需要** Ray Tracing Pipeline、SBT、`vkCmdTraceRaysKHR` 或 `RAY_TRACING_SHADER` stage。其 descriptor 使用 `VK_DESCRIPTOR_TYPE_ACCELERATION_STRUCTURE_KHR`，`VkWriteDescriptorSetAccelerationStructureKHR` 挂到写入链，stageFlags 是实际 compute/fragment 消费阶段。Bindless、Mesh Shader、独立 compute queue 与 OMM 各自独立门控。[SPEC]

正例：支持 query/AS/BDA，RT pipeline 不支持，仍可验证 fragment query。反例：只发现扩展字符串、未启用 feature，或缺任一必要依赖就创建 query pipeline；应关闭此变体并选 shadow-map/probe 基线，不反复初始化失败。[ENGINE]

AS 生命周期见 [资源合同](../04_buffer_image_memory/memory_allocation.md#acceleration-structure-resource-contract)，同步见 [AS 依赖表](../08_synchronization/pipeline_barrier.md#as-build-query-dependencies)。

依据：[Ray Query](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_KHR_ray_query.adoc)、[Registry](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/xml/vk.xml)。文档/编译成功不证明目标驱动或 Android 设备可执行。

<a id="simulation-kernel-portability"></a>
## 仿真 kernel 可移植性（C4）

输入：SPIR-V目标/能力、local size/dispatch维度、shared字节数、每kernel读写集合、设备features/limits与queue能力。输出：已选择的合法pipeline变体、逐阶段依赖和明确禁用/回退原因；不以GPU品牌、API版本或桌面运行成功推断支持。[SPEC][ENGINE]

四个范围分别验证：invocation独占写、workgroup内shared通信、dispatch间依赖、queue间信号/必要ownership。GLSL barrier()只能协调要求范围内的workgroup，不是全dispatch barrier；memoryBarrier/coherent/volatile也不会使所有workgroup集合等待。全局阶段拆成vkCmdDispatch并用Vulkan barrier连接，禁止busy-wait全局计数器作为通用全局barrier。Validation clean不证明无race。[SPEC]

尾线程：无协同barrier时可bounds-check后return；后续存在统一barrier时用active mask，所有要求参与的invocation先初始化各自shared槽（中性值或明确halo边界值），共同到达barrier，再只让active线程写有效输出。不能让部分线程提前返回而其他线程等待。分别检查maxComputeWorkGroupSize各维、maxComputeWorkGroupInvocations乘积、maxComputeWorkGroupCount、maxComputeSharedMemorySize、buffer range和所有索引乘法溢出；N=0可跳过dispatch，零group无工作并非自动非法。local size/specialization与编译产物实际一致。

| 能力 | 必查支持与启用 | 基线/不支持处理 |
|---|---|---|
| Compute + SSBO | compute queue、limits、layout/descriptor与编译target | 缺失则禁用GPU模拟，或项目已有小规模CPU状态生产+Vulkan绘制/静态姿态；不换渲染后端 |
| float atomic add | VK_EXT_shader_atomic_float及依赖，VkPhysicalDeviceShaderAtomicFloatFeaturesEXT的shaderBufferFloat32AtomicAdd、shaderSharedFloat32AtomicAdd或shaderImageFloat32AtomicAdd按实际域选择；64位另查对应buffer/shared字段，image另查format原子能力 | graph coloring或contribution→gather；整数atomic、Float32Atomics字段不等于Float32AtomicAdd |
| subgroup | VkPhysicalDeviceSubgroupProperties的supportedStages、supportedOperations和subgroupSize；size-control另查feature/property | workgroup或多dispatch归约，不固定32/64，不混淆subgroup与workgroup |
| FP16 | shaderFloat16算术与storageBuffer16BitAccess等存储/IO特性分别查询启用，目标SPIR-V匹配 | 默认积分/约束/残差FP32；只有误差评估通过字段才降精度，不强制FP64 |
| storage image | 实际format/tiling/usage及shader访问feature | SSBO状态/合法输出转换 |
| Sync2 / 独立queue / Ray Query | 三种独立条件，不捆绑启用 | legacy正确映射/单queue/传统绘制与阴影 |

结构化流水线：查询vkGetPhysicalDeviceFeatures2/properties/queue/format→仅启用选择路径的feature→编译并验证SPIR-V→创建descriptor/pipeline→受限dispatch→同算法CPU/GPU读回。支持、启用、编译、运行、收益分别报告。负向测试优先host配置拒绝、着色写集合检查或SPIR-V验证，不在真实设备运行已知死锁/OOB shader。关联hard_rules 2/3/9/17，单queue [交接](../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md#simulation-render-handoff) 为正确性基线。

规范：[Compute/Workgroup](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/shaders.adoc)、[features](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/features.adoc)、[Registry](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/xml/vk.xml)；辅助解释 [Subgroups Guide](https://docs.vulkan.org/guide/latest/subgroups.html)、[Android reduced precision](https://developer.android.com/games/optimize/vulkan-reduced-precision)。固定规范revision为API依据，动态官方页面不当作90天新特性。

<a id="special-compute-contract"></a>
## 专用计算入口与证据边界（VK16）

这里补充条件化 L1/L2 合同，不把普通 compute pipeline 误当作所有专用计算的对象模型。输入是具体 extension owner、API/SPIR-V target、queue/engine、元素类型/维度/格式、资源和消费者；输出是可创建的变体、拒绝原因及项目允许的回退。**API 版本不等于 feature；extension advertised 不等于 enabled；编译成功不等于执行成功；软件模拟不等于硬件验收。** [SPEC][ENGINE]

统一次序：枚举扩展 → 按固定 Registry 的 depends AND/OR 和符号 owner 展开依赖 → `vkGetPhysicalDeviceFeatures2` / properties / 专用枚举 → 在 `vkCreateDevice` 仅启用实际支持且使用的字段 → 验证 SPIR-V capability/类型及资源合同 → 创建与提交 → 独立数值/格式 oracle。计数式枚举遇 `VK_INCOMPLETE` 重新取数量/分配/查询，不能把截断数组当完整能力。缺能力时标为 UNSUPPORTED，未查询为 NOT_QUERIED，未执行为 UNVERIFIED；不能制造成功的硬件样本。[SPEC][ENGINE]

下列流程共享：所有被提交引用的 pipeline/session/view/buffer/tensor/memory 和 device address 在完成前保持有效；跨 queue 用 semaphore 和必要的 ownership transfer，同 queue 仍检查执行及内存依赖；fence 只解决完成，不自动替代读写依赖。创建失败处理返回码并清理已成功的对象，不把未初始化 handle 送入销毁；受保护数据禁止回读到普通 staging。验证层无错误不证明数值正确或恶意输入安全。[SPEC][ENGINE]

<a id="cooperative-compute-contract"></a>
### Cooperative matrix / vector：按 tuple 匹配而非看名称

- **KHR vs NV matrix**：分别查询 `VkPhysicalDeviceCooperativeMatrixFeaturesKHR` / `VkPhysicalDeviceCooperativeMatrixFeaturesNV` 的 `cooperativeMatrix`，及对应 properties 的 `cooperativeMatrixSupportedStages`；分别用 `vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR` / `vkGetPhysicalDeviceCooperativeMatrixPropertiesNV` 枚举。shader 的 scope、M/N/K、A/B/C/Result 类型必须匹配所选返回 tuple；KHR 还匹配 saturatingAccumulation 及 signed-components operands，不能独立拼接不同 tuple 的字段。NV `OpTypeCooperativeMatrixNV` 与 KHR `OpTypeCooperativeMatrixKHR` 的类型/use 模型不同，不靠后缀替换移植。按实际 scope 保证参与 invocation 的一致控制流；load/store 的 stride、alignment、范围与 SPIR-V 规则逐条检查，robustBufferAccess 不自动覆盖 cooperative matrix，另查 `cooperativeMatrixRobustBufferAccess`。[SPEC]
- **`VK_NV_cooperative_matrix2` 依赖 `VK_KHR_cooperative_matrix`，不是 NV matrix 基础扩展**。按所用操作逐项启用 `VkPhysicalDeviceCooperativeMatrix2FeaturesNV` 的 workgroup-scope、flexible-dimensions、reductions、conversions、per-element、tensor-addressing、block-load 字段，不存在一个万能 matrix2 feature。用 `vkGetPhysicalDeviceCooperativeMatrixFlexibleDimensionsPropertiesNV` 匹配 MGranularity/NGranularity/KGranularity、类型、scope、workgroupInvocations，检查 `cooperativeMatrixFlexibleDimensionsMaxDimension`、`cooperativeMatrixWorkgroupScopeMaxWorkgroupSize` 和 `cooperativeMatrixWorkgroupScopeReservedSharedMemory`；flexible 不等于任意维度。不要把 tensor addressing 与 `VkTensorARM` 对象支持等同。[SPEC]
- **`VK_NV_cooperative_vector` 独立门控**：查询/启用 `VkPhysicalDeviceCooperativeVectorFeaturesNV.cooperativeVector`，训练再要求 `cooperativeVectorTraining`；查询 `vkGetPhysicalDeviceCooperativeVectorPropertiesNV` 的 inputType/inputInterpretation/matrixInterpretation/biasInterpretation/resultType/transpose 组合及 `cooperativeVectorSupportedStages`、`maxCooperativeVectorComponents`、训练累积类型支持。opaque matrix layout 不是普通 row-major 字节：先 `vkConvertCooperativeVectorMatrixNV` 以 dstData=NULL 查询 `pDstSize`，再分配足够空间并转换，空间不足的 `VK_INCOMPLETE` 不是成功。host 版使用 hostAddress，`vkCmdConvertCooperativeVectorMatrixNV` 使用 deviceAddress，不能互换；输入输出不得重叠，device conversion 的 buffer/地址及有效期另查。[SPEC]
- **同步与回退**：matrix/vector shader 用真实 shader stage 的读写依赖，协作操作不是全 dispatch barrier。device vector conversion 用 `VK_PIPELINE_STAGE_2_CONVERT_COOPERATIVE_VECTOR_MATRIX_BIT_NV`；保守可用匹配该 stage 的 MEMORY_READ/MEMORY_WRITE，再交给实际 shader consumer，不能把 conversion 当普通 compute dispatch。尺寸/类型/阶段不匹配时选择已验证的普通 compute matrix/vector kernel，报告精度/性能未知；padding 必须重新定义边界与误差，不能伪造 tuple。[SPEC][ENGINE]

正例：KHR tuple 匹配且 feature 已启用，普通 compute queue 上建立合法 pipeline；不要求独立 AI queue。反例：仅发现 NV matrix 就编译 matrix2 指令，或将 subgroup=32 写死；在 host 配置阶段拒绝，不能用真实 GPU OOB/deadlock 做负测。

<a id="optical-flow-contract"></a>
### Optical flow：NV session 与 ARM data graph 是两条合同

| 路径 | 查询/启用与创建 | 执行、同步、退役 |
|---|---|---|
| `VK_NV_optical_flow` | `VkPhysicalDeviceOpticalFlowFeaturesNV.opticalFlow`、`VkPhysicalDeviceOpticalFlowPropertiesNV` 的 min/max dimensions、grid sizes、hint/cost 等支持；queue family 须有 `VK_QUEUE_OPTICAL_FLOW_BIT_NV`。按 input/output/hint/cost usage 调 `vkGetPhysicalDeviceOpticalFlowImageFormatsNV`，再用 format/image-format 查询验证完整 tiling/usage/extent 组合；`vkCreateOpticalFlowSessionNV` 的 formats/grid/flags 必须来自这些查询 | `vkBindOpticalFlowSessionImageNV` 绑定合法 image view 和执行时 layout；`vkCmdOpticalFlowExecuteNV` 用 NV session，不是 `vkCmdDispatch`。producer→`VK_PIPELINE_STAGE_2_OPTICAL_FLOW_BIT_NV` + `VK_ACCESS_2_OPTICAL_FLOW_READ_BIT_NV`，输出 WRITE→实际 consumer；bind 调用不是 layout transition。history 自动 hints 与禁用 hints 的 execute flag 是算法输入，切镜头/重建 session 后不能误沿用历史；等提交完成才销毁 session/view/image |
| `VK_ARM_data_graph_optical_flow` | 先 `VK_ARM_data_graph` / `dataGraph`，再 `VkPhysicalDeviceDataGraphOpticalFlowFeaturesARM.dataGraphOpticalFlow`；按 queue family 枚举 `vkGetPhysicalDeviceQueueFamilyDataGraphPropertiesARM`，选择返回的 OpticalFlow engine/operation，再查询 `VkQueueFamilyDataGraphOpticalFlowPropertiesARM` 的 dimensions/grid/hint/cost。图节点使用 `VkDataGraphPipelineOpticalFlowCreateInfoARM`；image-format 查询/创建中的 `VkDataGraphOpticalFlowImageFormatInfoARM` 等参数必须与 graph 路径一致 | 创建 graph pipeline 和匹配 session，使用 `VkDataGraphPipelineOpticalFlowDispatchInfoARM` / `vkCmdDispatchDataGraphARM`；走 `VK_PIPELINE_STAGE_2_DATA_GRAPH_BIT_ARM` + `VK_ACCESS_2_DATA_GRAPH_READ_BIT_ARM` / WRITE，而非 NV stage/access。cache bind point 的内存与 history 行为纳入 session 合同；节点 connection point、输入/参考/输出格式与 grid 尺寸匹配，不能绑定 NV session 代替 |

两者不是别名：不能把 NV queue flag、format 枚举、session 或 history flag 直接移给 ARM。ARM engine-operation properties 查询必须传入同一 device、同一 queue family 返回的 engine/operation 记录，非任意自造字符串。缺格式/queue/engine 时禁用该路径；若产品允许，选择单独验证的普通 compute optical-flow 算法，明确质量/时间/历史行为不同，不能说“回退证明硬件光流通过”。测试用已知位移图对+遮挡/切镜头案例核对方向、grid、单位及误差，验证层 clean 不能证明 flow 正确。[SPEC][ENGINE]

<a id="tensor-data-graph-contract"></a>
### ARM tensors、data graph、TOSA 与 QCOM model

1. **Tensor 是资源而非任意 buffer 别名**。`VK_ARM_tensors` 在固定 Registry 依赖 Vulkan 1.3，但 Vulkan 1.3 本身不保证 tensors。查询 `VkPhysicalDeviceTensorFeaturesARM.tensors`；shader 访问另查 `shaderTensorAccess`，descriptor indexing/update-after-bind 等按实际用法分别门控。查询 `VkPhysicalDeviceTensorPropertiesARM` 的 maxTensorDimensionCount/maxTensorElements/maxPerDimensionTensorElements/maxTensorStride/maxTensorSize；维度乘法和字节大小先防溢出。通过 `vkGetPhysicalDeviceFormatProperties2` 的 `VkTensorFormatPropertiesARM` 匹配 tiling/usage，optimal tiling 的 `pStrides` 必须 NULL。`vkCreateTensorARM` → `vkGetTensorMemoryRequirementsARM` → 按 size/alignment/memoryTypeBits 分配 → `vkBindTensorMemoryARM` → tensor view/descriptor；不能猜 optimal layout 或把普通 image layout 填给 tensor。[SPEC]
2. **Shader 接口合同**：`VK_DESCRIPTOR_TYPE_TENSOR_ARM` 所指 view 的 element type/format、rank、可选 shape 必须与 SPIR-V 匹配。rank/shape mismatch 的读取可能是 poison，不是自动广播/reshape。`VkTensorMemoryBarrierARM` 通过相应 dependency-info 扩展表达 tensor 的 stage/access/ownership；shader 写→graph 读选择真实 shader stage/SHADER_WRITE → DATA_GRAPH/DATA_GRAPH_READ，graph 输出→shader/transfer 则按实际消费者。共享 backing allocation 不免除同步或对象 lifetime。[SPEC]
3. **Data graph 是另一 bind point**。查询/启用 `VkPhysicalDeviceDataGraphFeaturesARM.dataGraph`；shader-module 输入需要 `dataGraphShaderModule`，specialization/update-after-bind/descriptor-buffer 按字段另查。解析 `VK_ARM_data_graph` 的 Vulkan 1.3、extended_flags 或 maintenance5、deferred_host_operations 依赖。要求 `VK_QUEUE_DATA_GRAPH_BIT_ARM`，按 queue family 枚举 processing engine 与 operation name/version，使用 `vkGetPhysicalDeviceQueueFamilyDataGraphProcessingEnginePropertiesARM` 查询 engine 约束；不能把 compute queue 支持等同 graph operation 支持。`vkCreateDataGraphPipelinesARM` 后创建 `vkCreateDataGraphPipelineSessionARM`，查询 `vkGetDataGraphPipelineSessionBindPointRequirementsARM`，对每个 bind point/object index 调 `vkGetDataGraphPipelineSessionMemoryRequirementsARM`，满足 size/alignment/memoryTypeBits 并 `vkBindDataGraphPipelineSessionMemoryARM`。scratch/cache 不得在 in-flight dispatch 中复用覆写。[SPEC]
4. **执行身份与内存**：`VK_PIPELINE_BIND_POINT_DATA_GRAPH_ARM` 上绑定的 pipeline 必须与创建 session 的 pipeline **相同对象**，不只是 layout 兼容；要求的每个 bind point 的 numObjects 都已绑定。访问的 tensor 要有 `VK_TENSOR_USAGE_DATA_GRAPH_BIT_ARM`；foreign processing engine 的 tensor/session memory 还须匹配查询到的 foreignMemoryHandleTypes，不因都是 device memory 就可共享。`vkCmdDispatchDataGraphARM` 只能使用该 command pool queue family 实际支持的所有 operations。记录输入→DATA_GRAPH_READ、输出 DATA_GRAPH_WRITE→消费者依赖；完成后才退役 session 及其绑定内存。固定规范 `VUID-vkCreateDataGraphPipelinesARM-deferredOperation-09761` 要求 deferredOperation=VK_NULL_HANDLE，不能因依赖 deferred_host_operations 就假定该入口允许 deferred 创建；检查创建返回码和每个 pipeline handle，不可执行半成品。[SPEC]
5. **TOSA 是 engine-operation 合同**。`VK_ARM_data_graph_instruction_set_tosa` 依赖 data_graph，不自动授予所有 TOSA 版本/profile/operator/形状。先枚举支持的 TOSA operation name/version，再用 `vkGetPhysicalDeviceQueueFamilyDataGraphEngineOperationPropertiesARM` 查询 `VkQueueFamilyDataGraphTOSAPropertiesARM`，匹配模型的 profile/extension quality、level、operation version 和实际 operand constraints；固定规范中相关保证条件为 dataGraphShaderModule 支持及 extension revision 对应 `TOSA.001000.1` / operation version 0，不能推广到任意 TOSA 模型。[SPEC]
6. **`VK_QCOM_data_graph_model`** 另查/启用 `VkPhysicalDeviceDataGraphModelFeaturesQCOM.dataGraphModel`，选择枚举的 neural-model 或 built-in-model operation、engine/name/version。built-in 使用 `VkDataGraphPipelineBuiltinModelCreateInfoQCOM`，模型来源/兼容性由 provider 定义，Vulkan 不承诺任意 ONNX/TOSA/厂商权重互通。pipeline available-properties/properties 查询结果及 descriptor contract 应记录；不能将 provider 模型 ID 当 portable shader。[SPEC]

反例：仅开启 dataGraph 却使用 shaderTensorAccess、把 session 绑定到“另一个等价 pipeline”、向 TOSA engine 投入未公布的版本。应在 host 能力/资源计划阶段拒绝；缺支持时可禁用功能或选择已有普通 compute/CPU 模型实现，但须单独验证数值、精度、量化和输出语义，不能报作 graph/NPU 执行通过。[ENGINE]

<a id="decompression-indirect-copy-contract"></a>
### Decompression / indirect copy：地址、ABI 与同步不可混用

- **NV → EXT decompression 不是命令别名**。分别启用扩展及 `VkPhysicalDeviceMemoryDecompressionFeaturesNV/EXT.memoryDecompression`，查询 `decompressionMethods` 与 `maxDecompressionIndirectCount`，BDA 的功能/usage/分配标志独立满足。NV 的 `VkDecompressMemoryRegionNV` 每 region 带 method，EXT 的 `VkDecompressMemoryInfoEXT` 将 method 置于 batch，region 为 `VkDecompressMemoryRegionEXT`；两个 indirect region stride 不能复用。GDeflate 1.0 每 region decompressedSize ≤ 65536，但还必须容纳 bitstream 的真实解压长度；过小可能 undefined，验证层不一定能解析压缩格式并发现错误。[SPEC]
- **数据与命令范围**：source/destination 不得重叠，地址须在应用有效分配的 buffer 范围；完整 compressed/decompressed byte range、防溢出、method 支持和压缩块有效性先验校验。EXT source/destination buffer 要有 `VK_BUFFER_USAGE_2_MEMORY_DECOMPRESSION_BIT_EXT`。indirectCommandsAddress/countAddress 来自 INDIRECT_BUFFER buffer 且 4-byte aligned，stride ≥ 对应 struct 大小且为 4 的倍数，count 不超过 maxDecompressionIndirectCount，整个 stride×count 地址区间在同一 buffer 范围。EXT 命令另有 maxDecompressionCount（实际执行取 min），**这不豁免 count buffer 本身的规范上限**。[SPEC]
- **同步**：EXT compressed data / decompressed data 使用 `VK_PIPELINE_STAGE_2_MEMORY_DECOMPRESSION_BIT_EXT` + `VK_ACCESS_2_MEMORY_DECOMPRESSION_READ_BIT_EXT` / WRITE，再衔接真实 consumer；indirect 参数/count 的生产也必须可见，不要只同步输出。NV-only 不能擅用未启用的 EXT stage/access；可先用合法的 ALL_COMMANDS + MEMORY_READ/MEMORY_WRITE 保守依赖保证正确性，再按该 owner 的规范细化，不能拿 EXT 的细化规则证明 NV 测试通过。[SPEC][ENGINE]
- **KHR vs NV indirect copy**：`VK_NV_copy_memory_indirect` 的 `VkPhysicalDeviceCopyMemoryIndirectFeaturesNV.indirectCopy`，不等于 `VK_KHR_copy_memory_indirect` 的两个独立字段 `indirectMemoryCopy` / `indirectMemoryToImageCopy`。查询 `VkPhysicalDeviceCopyMemoryIndirectPropertiesKHR/NV.supportedQueues` 并选择匹配 command pool。KHR `vkCmdCopyMemoryIndirectKHR` 接受 `VkCopyMemoryIndirectInfoKHR` 的 address range，NV 命令使用独立 address/count/stride 参数，不能当同 ABI alias 调用。[SPEC]
- **KHR range 检查**：copyAddressRange.address 4-byte aligned，stride ≥ sizeof(VkCopyMemoryIndirectCommandKHR) 且为 4 的倍数，copyCount ≤ size/stride，参数 buffer 有 INDIRECT_BUFFER usage；源/目标重叠和不同 destination 重叠都须拒绝，零 copyCount 无工作。sparse flags 不免除实际 residency，protected command buffer 与 PROTECTED copy flags 不允许用于此 KHR command。to-image 路径还需独立 feature、目标 image usage/layout、subresource/extent/offset 与格式块对齐，不能从 memory-copy 成功推断 image-copy 合法。[SPEC]
- **参数读取不等于 payload copy**：支持 KHR 路径时参数生产→`VK_PIPELINE_STAGE_2_COPY_INDIRECT_BIT_KHR` / `VK_ACCESS_2_INDIRECT_COMMAND_READ_BIT`，payload 使用 COPY / TRANSFER_READ、TRANSFER_WRITE 及真实 consumer；不要把 COPY_INDIRECT stage 当 payload 写入 stage。NV-only 同样不能借用未启用的 KHR stage，可保守 ALL_COMMANDS/MEMORY 依赖。地址指向的 allocation、参数/count buffer、目标 image 必须活到所有引用完成；raw device address 没有自动延长 lifetime。[SPEC]

失败与回退：对不可信压缩输入先验验证尺寸/格式，拒绝越界地址/重叠/超限 count，不在设备上执行负向恶意包。缺支持时采用独立验证的 CPU/普通 compute 解压，或在参数已知时录制 `vkCmdCopyBuffer` 等普通 copy；若需 GPU 参数读回，明确额外等待与开销。不可把这些回退标为专用硬件解压/间接拷贝执行通过。[ENGINE]

### 固定依据与仍开放范围

上述源读依据为 Vulkan-Docs **fa30d4e312e843193601be7cb926c7e25d9ec885 / 1.4.368**：
- [Registry owner/depends/feature](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/xml/vk.xml)。
- [Cooperative matrix/vector 与 layout conversion](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/shaders.adoc#L4196)。
- [NV optical flow](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/VK_NV_optical_flow/optical_flow.adoc)、[ARM graph/session/operations](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/VK_ARM_data_graph/graphs.adoc)。
- [Tensor resource creation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/resources.adoc#L13588)、[Tensor instruction/coordinate validation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/VK_ARM_tensors/tensorops.adoc)。
- [Memory decompression](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory_decompression.adoc)、[indirect count common VUs](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/commonvalidity/decompress_memory_indirect_common.adoc)、[indirect copies](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/copies.adoc#L1963)、[synchronization stage/access](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc)。

仍开放：`VK_QCOM_cooperative_matrix_conversion`、`VK_EXT_cooperative_matrix_maintenance1`、`VK_ARM_cooperative_matrix_layouts`、`VK_NV_cooperative_matrix_decode_vector`、`VK_ARM_tensor_controls`、`VK_ARM_data_graph_neural_accelerator_statistics` 的完整扩展特有 L1/L2 语义；主族的全量 VU/SPIR-V capability/精度规则与 foreign-engine 互操作细节也未声称闭合。`VK_NV_external_compute_queue` 在外部互操作域，不据本卡关闭。这里是条件化文档合同与静态回归，不是 20 族完整验收；GPU/Android/live-model 均未执行，现有 llvmpipe buffer probe 不覆盖上述可选路径。

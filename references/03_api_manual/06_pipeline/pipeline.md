# API Card: VkPipeline

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipeline` |
| 常用 API | `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` / `vkDestroyPipeline` / `vkCmdBindPipeline` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipeline` 是 Vulkan 中描述“执行状态”的不可变对象，graphics pipeline 决定绘制状态，compute pipeline 决定 dispatch 状态；创建后除动态状态外不可变更。[SPEC]

---

## 2. 所属对象链路

```text
VkPipelineShaderStageCreateInfo[]
→ VkPipelineLayout
→ vkCreateGraphicsPipelines / vkCreateComputePipelines
→ VkPipeline
→ vkCmdBindPipeline（GRAPHICS / COMPUTE）
→ Draw / Dispatch
```

### 上游依赖

- Shader modules 与 stage 信息（graphics / compute）。[SPEC]
- Pipeline layout。[SPEC]
- Graphics pipeline 还需要 render pass / dynamic rendering 格式、顶点输入、光栅化、混合等状态。[SPEC]

### 下游影响

- 决定 draw / dispatch 的执行状态。
- 影响 descriptor set 绑定、动态状态设置、资源访问方式。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipeline`
- `VkGraphicsPipelineCreateInfo`
- `VkComputePipelineCreateInfo`
- `VkPipelineShaderStageCreateInfo`
- `VkPipelineLayout`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateGraphicsPipelines` | 创建 graphics pipeline。[SPEC] |
| `vkCreateComputePipelines` | 创建 compute pipeline。[SPEC] |
| `vkDestroyPipeline` | 销毁 pipeline。[SPEC] |
| `vkCmdBindPipeline` | 在 command buffer 中绑定 pipeline。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_graphics_pipeline_library`、`VK_KHR_ray_tracing_pipeline` 等扩展扩展了 pipeline 概念。

---

## 4. 标准使用流程

```text
准备 shader modules 与 stage 信息
→ 创建 pipeline layout
→ 配置 graphics/compute 状态
→ 指定 render pass / dynamic rendering 格式（graphics）
→ vkCreate*Pipelines（传入 pipeline cache）
→ vkCmdBindPipeline
→ 设置动态状态（如有）
→ vkCmdDraw / vkCmdDispatch
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `stageCount` / `pStages` | 传统顶点路径需要 vertex；mesh 路径按 mesh 能力；fragment 是否需要取决于 rasterization 等条件，不是无条件 vertex+fragment。compute 使用 compute stage。[SPEC] | 缺少必要 stage。[TOOL] |
| `layout` | 必须是已创建的 pipeline layout。[SPEC] | layout 与 shader 接口不匹配。[TOOL] |
| `pipelineCache` | cache 可为 VK_NULL_HANDLE；性能收益需测量。[SPEC] | 把未使用 cache 当合法性错误。[TOOL] |
| `basePipelineHandle` / `basePipelineIndex` | 用于 pipeline derivative，可加速相似 pipeline 创建。[SPEC] | 误用导致依赖错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Shader stage 与 module 是否匹配？
- [ ] Pipeline layout 是否与 shader 的 set/binding 一致？
- [ ] Graphics pipeline 的 render pass / dynamic rendering 格式是否与实际 attachment 一致？
- [ ] 是否传入了 pipeline cache？

### 使用阶段

- [ ] 是否在正确的 command buffer 状态下绑定？（vkCmdBindPipeline 可在 render pass 内或外录制；draw 的 render scope 另查）
- [ ] 动态状态是否在 draw 前设置？
- [ ] Descriptor set layout 是否与 pipeline layout 兼容？

### 销毁阶段

- [ ] 是否等待 GPU 不再使用该 pipeline？

---

## 7. 高频错误

1. Pipeline layout 与 shader 的 set/binding 不匹配。[TOOL]
2. Graphics pipeline 的 attachment format 与实际 render pass 不一致。[TOOL]
3. 忘记设置动态状态或动态状态未在 `pDynamicState` 中声明。[TOOL]
4. Compute pipeline 绑定到 graphics bind point 或反之。[TOOL]
5. 将绑定与执行混淆：vkCmdBindPipeline 可在 render pass 外录制，draw 仍需满足对应 render scope。[SPEC]
6. 销毁 pipeline 时它仍被 in-flight command buffer 引用。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkGraphicsPipelineCreateInfo-*` / `VUID-VkComputePipelineCreateInfo-*`：创建参数合法性。
- `VUID-vkCmdBindPipeline-*`：bind point 与 pipeline 类型匹配。
- `VUID-vkCmdDraw-*`：pipeline 状态、scissor、dynamic state。

### RenderDoc / AGI

- 查看当前绑定的 pipeline 与完整状态。
- 检查 shader stage、descriptor、顶点输入、光栅化、混合状态。

### 日志 / 代码检查

- 检查 pipeline 创建返回值。
- 检查 pipeline cache 是否启用。
- 检查动态状态设置命令。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段或按需延迟创建；建议配合 pipeline cache。[ENGINE]

### 使用时机

- 在 command buffer 中绑定后用于 draw / dispatch。[SPEC]

### 销毁时机

- 确认所有引用它的 command buffer 已完成后销毁。[SPEC]

### in-flight 风险

- Pipeline 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Pipeline 创建本身不需要 fence；销毁需要等待 GPU 完成。[SPEC]

### GPU-GPU 同步

- 切换 pipeline 属于 command buffer 内部顺序执行，无需额外同步。
- Pipeline 写入的 resource 被后续命令读取时需要 barrier。[SPEC]

### 资源访问同步

- Pipeline 本身不直接同步资源；资源同步通过 barrier / subpass dependency 完成。[SPEC]

---

## 11. Android 注意点

- Android 上 pipeline 创建耗时高，建议测量 pipeline cache 与持久化收益。[ANDROID][ENGINE]
- 避免在启动时一次性创建大量 pipeline，应分帧预热。[ENGINE]
- 横竖屏切换通常不需要重建 pipeline，除非 dynamic rendering 的 image 格式变化。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Pipeline 创建是常见 CPU 瓶颈；使用 cache、library、specialization constants 可减少开销。[ENGINE]
- 减少 pipeline 变体数量：使用动态状态、通用 vertex layout。[ENGINE]

### GPU 侧

- 过度切换 pipeline 会增加 command processor 开销；按 pipeline 排序 draw call。[ENGINE]
- Early-Z / Hi-Z 受 depth state 影响。[HEUR]

### 移动端

- Tile-based GPU 上，blending、MSAA、MRT 会增加 tile memory 带宽。[ENGINE]
- 尽量避免每帧创建 pipeline；启动时预热。[ENGINE]

---

## 13. 专家经验

**经验**：
把 `VkPipeline` 看作“完全烘焙的执行状态”。在设计阶段就把可变因素（viewport、scissor、blend constants、stencil reference 等）移到动态状态，把编译期分支（feature on/off、quality level）移到 specialization constants，从而把 pipeline 变体数量控制在可缓存、可预热的范围。绘制时按 material/pass 排序，减少 bind 切换。

**适用条件**：
所有 Vulkan 图形与计算渲染。

**不适用情况**：
启用并正确使用 VK_EXT_shader_object 的 draw/dispatch 路径不需要 VkPipeline，见 [Shader Object](shader_module.md#shader-object-contract)。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `graphics_pipeline.md`
- `compute_pipeline.md`
- `pipeline_layout.md`
- `pipeline_cache.md`
- `specialization_constants.md`
- `graphics_pipeline_library.md`
- `shader_module.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../03_command_buffer/command_buffer.md`

---

## 15. 需要回查官方文档的情况

1. Graphics pipeline 与 compute pipeline 在创建参数上的完整差异。
2. Pipeline derivative 与 base pipeline 的使用规则。
3. Dynamic state 扩展与核心动态状态的交互。
4. Pipeline 与 render pass / dynamic rendering 的兼容性规则。
5. 具体驱动对 pipeline cache 持久化与预热的限制。


<a id="ray-tracing-pipeline-contract"></a>
## 16. Ray Tracing Pipeline / SBT 合同

**能力边界。** `VK_KHR_ray_tracing_pipeline` 与 `rayTracingPipeline`、AS 所需 `VK_KHR_acceleration_structure` / `accelerationStructure`、BDA 能力及 Registry 依赖逐项查询并启用；查询 `VkPhysicalDeviceRayTracingPipelinePropertiesKHR`。Ray Query 是现有 graphics/compute shader 内的查询，只需其自身 `rayQuery` 与 AS 依赖，不要求 RT Pipeline、SBT 或专用 ray-generation stage。仅有 rayQuery 不能调用 `vkCmdTraceRaysKHR`。[SPEC]

**正常对象链。** 建立合法 BLAS/TLAS → descriptor/layout → raygen/miss/hit/callable shader stages 与 `VkRayTracingShaderGroupCreateInfoKHR` → `vkCreateRayTracingPipelinesKHR` → `vkGetRayTracingShaderGroupHandlesKHR` → SBT buffer → bind `VK_PIPELINE_BIND_POINT_RAY_TRACING_KHR` 与兼容 descriptors → `vkCmdTraceRaysKHR`。GENERAL group 用于 raygen/miss/callable；TRIANGLES_HIT_GROUP 不带 intersection；PROCEDURAL_HIT_GROUP 为 AABB 路径提供 intersection。未使用索引为 `VK_SHADER_UNUSED_KHR`，不能把所有 group 都当 GENERAL。[SPEC]

**SBT 地址合同。** 为 SBT buffer 声明 `VK_BUFFER_USAGE_SHADER_BINDING_TABLE_BIT_KHR` 与设备地址用途，分配满足 BDA 合同的内存。每条记录以 `shaderGroupHandleSize` 字节的该 pipeline group handle 开头，之后才是应用 payload；不能把 group index 当 handle。非空 region 起址满足 `shaderGroupBaseAlignment`，miss/hit/callable stride 满足 `shaderGroupHandleAlignment` 且不超过 `maxShaderGroupStride`；记录必须容纳 handle 与 payload，按实际索引检查范围与溢出。`pRaygenShaderBindingTable.size == stride`（04023），不是 raygenCount×stride。未使用表用零 size 并确保 shader 不访问；不凭零 size 掩盖被访问记录越界。`VkStridedDeviceAddressRegionKHR` 的 size/stride/address 及当前命令 VU 要一起校验。[SPEC]

**同步与寿命。** SBT 上传写 → `VK_PIPELINE_STAGE_RAY_TRACING_SHADER_BIT_KHR` / `VK_ACCESS_SHADER_READ_BIT`；AS build 写 → trace 的 acceleration-structure read；shader 输出 → 后续消费者各自设置依赖。跨 queue-family 的独占资源还需 release/acquire 与 semaphore。SBT、AS、pipeline、descriptors 与被引用资源保留到全部提交使用结束；不在 in-flight 中覆写 SBT 或压缩后立即释放仍被引用旧 AS。[SPEC]

**递归与 stack。** 创建时 `maxPipelineRayRecursionDepth` 不超过查询上限，shader 调用深度也不得越界。默认 stack 由规范保守公式确定；若选择 `VK_DYNAMIC_STATE_RAY_TRACING_PIPELINE_STACK_SIZE_KHR`，用 `vkGetRayTracingShaderGroupStackSizeKHR` 汇总所有可能调用链（含 callable），并在 trace 前 `vkCmdSetRayTracingPipelineStackSizeKHR`。不能只取最大单 shader stack，也不能靠增加 stack 修复递归越界。trace 尺寸乘积检查 `maxRayDispatchInvocationCount`；indirect trace 另查对应 feature 与参数 buffer 同步。[SPEC]

**失败与回退。** 创建/handle 查询失败不消费未定义输出；partial pipeline 输出按实际非空 handle 回收。使用 deferred host operation 时，保留创建输入到操作完成并读取最终结果，不把 deferred 状态当成功。能力缺失、SBT 校验失败或内存不足时停止 trace，回到单独验证的 Ray Query 或 raster 路径；没有 rayQuery 时不能假造 query 回退。device lost 走设备恢复，不继续排队依赖未提交的信号。[ENGINE]

**验证边界。** CPU 测试地址/stride/乘法溢出、group 类型、query-only 拒绝 trace；GPU 验证须另记录 raygen/miss/triangle/procedural、递归边界和同步验证结果。micromap、cluster AS、motion blur、capture/replay、所有间接变体尚需分别审查，不由本节自动获得 L1/L2 PASS。

固定规范（Vulkan 1.4.368，source-read；不是设备验证）：[ray-tracing-commands / shader-binding-table / ray-tracing-pipeline-stack](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/raytracing.adoc)；[SBT VU](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/commonvalidity/trace_rays_binding_table.adoc)；[raygen size 04023](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/commonvalidity/trace_rays_binding_table_raygen_stride.adoc)；[pipeline creation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/pipelines.adoc)。


<a id="acceleration-structure-lifetime-contract"></a>
## AS build / update / compact / 地址寿命

`VK_KHR_acceleration_structure` 的完整 Registry 依赖为 `((Vulkan 1.1 + VK_EXT_descriptor_indexing + VK_KHR_buffer_device_address) 或 Vulkan 1.2) + VK_KHR_deferred_host_operations`；支持/启用 accelerationStructure、bufferDeviceAddress 与所需可选能力分别检查。`VK_KHR_ray_query` 与 `VK_KHR_ray_tracing_pipeline` 都依赖 AS 和 `(VK_KHR_spirv_1_4 或 Vulkan 1.2)`，它们不是互相依赖。host build、indirect build、capture/replay 各有自己的 feature，不因拥有 AS 就默认开启。[SPEC]

**Build 正常链。** 根据 geometry type/flags、primitive counts、build type 调用 `vkGetAccelerationStructureBuildSizesKHR` → 分配 AS storage buffer/内存并创建 BLAS/TLAS → input buffer 使用 `VK_BUFFER_USAGE_ACCELERATION_STRUCTURE_BUILD_INPUT_READ_ONLY_BIT_KHR` 与所需 BDA → scratch 使用 STORAGE_BUFFER 和 BDA，地址满足 `minAccelerationStructureScratchOffsetAlignment`，为 buildScratchSize 留足同一 buffer 内连续范围 → build BLAS → AS_BUILD write→AS_BUILD read 依赖 → 写含 BLAS 地址的 instances 并 build TLAS → 对实际 Ray Query stage 或 RT_SHADER stage 建立 AS read 依赖。多个 pInfos 之间**没有隐含排序**，不能在同一次 `vkCmdBuildAccelerationStructuresKHR` 同时构建相互依赖 BLAS/TLAS，也不能同批 alias scratch/AS；KHR micromap→BLAS 亦然。raw geometry/instance inputs 与 scratch 至少保留到 build 执行完成，之后可同步复用；TLAS 引用的 BLAS 必须继续存活。[SPEC]

**地址不是 handle 或 buffer 起址。** device build 的 `VkAccelerationStructureInstanceKHR.accelerationStructureReference` 使用 `vkGetAccelerationStructureDeviceAddressKHR` 返回的 BLAS AS 地址，不能直接填 VkAccelerationStructureKHR handle 或任意 `vkGetBufferDeviceAddress`。host build 使用对象引用合同，不能与 device 地址混用。instanceCustomIndex / instanceShaderBindingTableRecordOffset 为 24 位、mask/flags 为 8 位，host packing 要验证实际 ABI。[SPEC]

**Update 不是拓扑重建。** 原 build 必须有 `VK_BUILD_ACCELERATION_STRUCTURE_ALLOW_UPDATE_BIT_KHR`，UPDATE 指定有效 source、足够 updateScratchSize 与兼容 destination；除明确允许的 instance definitions、变换、vertex/AABB positions 及对应扩展例外外，保持原 build 合同。geometry/instance/primitive 数、geometry flags、vertexFormat/indexType、triangle index 值、transformData 的 NULL/非 NULL 状态不能改变；不能把 active↔inactive 当普通 update。违反任一条件用完整 BUILD，不能因为 allocation 足够大就强制 UPDATE。in-place update 不允许与读取旧 AS 的 traversal 并发；串行化或使用独立版本并退休旧引用。[SPEC]

**Compact 正常链。** 原 build 声明 `VK_BUILD_ACCELERATION_STRUCTURE_ALLOW_COMPACTION_BIT_KHR` → build 完成并建立查询读取依赖 → 重置并写 `VK_QUERY_TYPE_ACCELERATION_STRUCTURE_COMPACTED_SIZE_KHR` 查询 → 等结果可用并读取实际 size → 创建足够容量的新 AS → `vkCmdCopyAccelerationStructureKHR` / `VK_COPY_ACCELERATION_STRUCTURE_MODE_COMPACT_KHR` → copy 完成后查询新 AS address、重写 instances 并合法重建/更新 TLAS → 所有旧 TLAS/traversal 使用结束后释放旧 BLAS。compaction 不会自动修补已有 TLAS 引用；CLONE/COMPACT 若复制含引用的 AS，目标仍引用原下层 AS，不深拷贝对象图。不可直接 memcpy opaque AS bytes 替代 AS copy。[SPEC]

**失败与验证。** size/query/allocate/build-input 校验失败就停止后续 build/trace；只清理成功创建对象，保留被旧提交引用的版本。compaction 无法分配可继续使用仍有效原 AS；update 不合法回 full build；无 AS 支持回 raster/software 方案，而不是伪造 Ray Query。CPU 检查地址来源、range/overflow、更新签名与引用退休；真实 GPU 要分开验证 BLAS→TLAS、update、compact 后地址重绑定和跨 queue 同步。本节只定向审查通用 AS 流程，host/deferred、serialization/capture-replay、sparse/protected 等全部组合仍待专项验证。

固定 1.4.368 规范证据：[AS update/build/scratch](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/accelstructures.adoc#L147)；[update exact VUs](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/commonvalidity/build_acceleration_structure_common.adoc#L112)；[scratch/input ranges](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/commonvalidity/build_acceleration_structure_device_common.adoc#L4)；[instance reference](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/accelstructures.adoc#L1818)；[copy/query](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/accelstructures.adoc#L2676)。


<a id="ray-tracing-extension-differences"></a>
## 光追扩展差异：索引、遍历与 micromap 不可混用

**SBT 索引。** Hit record 地址 = hitRegion.deviceAddress + hitRegion.stride ×（instanceShaderBindingTableRecordOffset + geometryIndex × sbtRecordStride + sbtRecordOffset）。region.stride 是字节，shader 的 sbtRecordStride 是记录索引步长，不能混为同一值；完整 record payload 必须落在 region.size 内。raygen 一次只执行一个 group，missIndex 与 callable index 各按自身 region 计算。handle 来自最终使用的合法 pipeline/group 查询，不能以 shader module hash 或跨不保证兼容的 pipeline handle 替代。具体 library handle 保证需相应扩展/feature，不假设相同源码就兼容。[SPEC]

**Ray Query 与 Pipeline。** Ray Query 在调用 shader 内 initialize/proceed 循环处理候选，不调用 any-hit/closest-hit/miss/intersection shader，也没有 SBT。candidate 仅在 `OpRayQueryProceedKHR` 返回 true 时有效；triangle candidate 用 `OpRayQueryConfirmIntersectionKHR`，AABB 由应用求实际交点再 `OpRayQueryGenerateIntersectionKHR`，不能把 AABB bounds 命中当表面命中。confirm/generate 不自动结束遍历，committed 是当前最近已确认命中，后续更近命中可以替换；proceed 返回 false 或合法 terminate 后再按最终状态消费。Pipeline 则通过 SBT 与 shader call 链处理对应阶段；query feature 不授权 trace command。[SPEC]

| 扩展 / 条件 | 实际差异、正常路径与拒绝/回退 |
|---|---|
| `VK_KHR_ray_tracing_maintenance1`，依赖 AS | `rayTracingMaintenance1` 提供 CullMaskKHR、AS_SIZE/serialization bottom-level pointer queries、Sync2 AS_COPY stage 与 SBT_READ access。`rayTracingPipelineTraceRaysIndirect2` 是另一个可选 feature；`vkCmdTraceRaysIndirect2KHR` 从 `VkTraceRaysIndirectCommand2KHR` 读取 SBT 参数和尺寸，而原 indirect 命令只间接读取尺寸。producer 写→DRAW_INDIRECT/INDIRECT_COMMAND_READ，SBT 数据读取另同步；GPU 写入的地址/stride/尺寸仍满足 trace VU。没有 indirect2 feature 回 direct 或已支持原 indirect，不把同名维护 feature 当授权。[SPEC] |
| `VK_KHR_ray_tracing_position_fetch`，依赖 AS | 启用 rayTracingPositionFetch，AS build 加 `VK_BUILD_ACCELERATION_STRUCTURE_ALLOW_DATA_ACCESS_BIT_KHR`，shader 使用对应 SPIR-V capability；仅命中的 triangle 可读取存储在 AS 的三个 object-space 顶点位置。pipeline any-hit/closest-hit 与 ray query 分别用其内建/指令，不是 world-space、更不是任意 vertex attributes。未按 flag build 或没有 feature 时，回应用自有 vertex/index buffer 的合法索引访问；保持其数据寿命，不在 AS build 完成后错误释放仍供 shader 使用的源数据。[SPEC] |
| `VK_EXT_opacity_micromap`，依赖 AS +（Sync2 或 Vulkan 1.3），promotedto=`VK_KHR_opacity_micromap` | 启用 `VkPhysicalDeviceOpacityMicromapFeaturesEXT.micromap`；`VkMicromapEXT` 存储、`vkGetMicromapBuildSizesEXT` 查询、`vkCmdBuildMicromapsEXT` build，使用 micromap 专属 build stage/access，再让 BLAS 引用。结构体与 triangle mapping、2/4-state format、subdivision limits 必须匹配，不能把它当任意 alpha 纹理。micromapHostCommands 只在 EXT 暴露，未进入 KHR；缺 feature 拒绝 host 路径，不替换成未经支持的同名 KHR host 函数。[SPEC] |
| `VK_KHR_opacity_micromap`，依赖 AS + `VK_KHR_device_address_commands` | 启用 `VkPhysicalDeviceOpacityMicromapFeaturesKHR.micromap`；以 `VkAccelerationStructureKHR` 和 MICROMAP geometry 使用 AS build/copy/query 路径（`VkAccelerationStructureGeometryMicromapDataKHR`），不是凭 promotion 把 EXT 流程机械换后缀；MICROMAP geometry 的 build range info 为 NULL。先完成 micromap build 再同步 BLAS 读取；batch 中相互依赖 build 不自动排序。使用相同信息查询容量、scratch、format/subdivision，与 BLAS triangle 映射一致；失败时不绑定未建成 micromap，回普通 triangle + 正确 any-hit/query alpha test。[SPEC] |
| KHR-only / EXT-enabled 遍历声明差异 | pipeline trace 在两条路径均需 `VK_PIPELINE_CREATE_RAY_TRACING_OPACITY_MICROMAP_BIT_KHR`（EXT alias）。只有 KHR 启用时，ray query shader 要声明 `OpacityMicromapIdKHR` 且 specialization operand=true；EXT 启用时（包括 EXT+KHR 同开）query 总是消费 OMM，不要求该声明。遗漏所需声明是 undefined，不是忽略 OMM 的合法回退；要禁用用 instance `VK_GEOMETRY_INSTANCE_DISABLE_OPACITY_MICROMAPS_BIT_KHR` 并满足其条件。RT shader 自身再执行 query 时两种声明各管自己的 traversal。[SPEC] |
| Micromap 更新与引用寿命 | 原 AS 的 `ALLOW_OPACITY_MICROMAP_UPDATE` 允许改引用的 micromap；EXT 的 `ALLOW_OPACITY_MICROMAP_DATA_UPDATE` 只准结构相同、仅 opacity 值变化，不能改变 subdivision/format/特殊索引与显式三角形模式。两种更新均未允许时必须提供原 micromap，不能擅换。update 转移引用，新旧 micromap 按最后引用退休；EXT discardable 特例只依实际查询处理，不能无条件 build 后销毁。更新条件失败就重建，序列化后的引用另遵循精确原始序列化数据规则。[SPEC] |
| `VK_ARM_pipeline_opacity_micromap`，依赖 EXT opacity | 查询/启用 pipelineOpacityMicromap feature；`VK_PIPELINE_CREATE_2_DISALLOW_OPACITY_MICROMAP_BIT_ARM` 是“不用含 OMM 的 AS”承诺以允许优化，不是“支持 OMM”开关。实际 query 会访问含 OMM 的 AS 就不设置此标志；不要用它替代 KHR shader 声明或 instance disable。性能无保证，需要独立对照测量。[SPEC] |

**冻结范围警戒。** `VK_NV_displacement_micromap` 在本 Registry 为 provisional=true、platform=provisional 且 deprecatedby=VK_NV_cluster_acceleration_structure；不计入稳定扩展语义已完成项。其 displacement 改变几何位置，与 opacity 控制透明性不同；cluster AS 不是一对一替代，迁移需重新设计 build/地址/数据生命周期。不得因为文件存在或宏可编译就称稳定已发布。`VK_NV_ray_tracing` 旧对象/handle ABI、motion blur、linear swept spheres、NV/EXT invocation reorder、cluster/partitioned AS、validation 等稳定域仍 OPEN；本表不替它们获得 L1/L2。

**验收。** 固定输入先检查 SBT 字节/索引、candidate/committed、indirect2 gate、position-fetch build flag、EXT/KHR/Both OMM 声明和更新引用负例。设备验证分别跑 opaque/transparent/unknown OMM、any-hit/query、compact/update、同步与 fallback 对照；本轮仅 source-read/static，全部 Device NOT_RUN。

固定 1.4.368 规范证据：[SBT indexing](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/raytracing.adoc#L717)；[query candidate/committed](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/raytraversal.adoc#L678)；[OMM traversal declaration](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/raytraversal.adoc#L516)；[maintenance features](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/features.adoc#L4456)；[position fetch](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_KHR_ray_tracing_position_fetch.adoc#L32)；[EXT promotion differences](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_EXT_opacity_micromap.adoc#L60)；[KHR OMM model](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_KHR_opacity_micromap.adoc#L37)；[micromap update constraints](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/accelstructures.adoc#L179)；[ARM disallow](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_ARM_pipeline_opacity_micromap.adoc#L20)；[displacement deprecation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_NV_displacement_micromap.adoc#L40)。

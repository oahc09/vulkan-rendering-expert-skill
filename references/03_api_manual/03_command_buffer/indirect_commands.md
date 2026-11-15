# API Card: Indirect Commands

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 |
| Vulkan 对象 | `VkBuffer`（indirect 参数，不是 `VkCommandBuffer`） |
| 常用 API | `vkCmdDrawIndirect` / `vkCmdDrawIndexedIndirect` / `vkCmdDispatchIndirect` / `vkCmdDrawIndexedIndirectCount` |
| 适用平台 | 通用，逐设备查询 feature / limit |
| 来源等级 | `[SPEC] [REGISTRY] [ENGINE]` |
| 适用 Vulkan 版本 | 基础 indirect 为 Vulkan 1.0；Count 为 Vulkan 1.2 或 `VK_KHR_draw_indirect_count` 路径 |

## 1. 一句话定位

间接命令从 buffer 读取绘制或 dispatch 参数；参数可由 CPU 或 GPU 生成。GPU 决定可见实例就是 GPU-driven，不要求 Count、bindless、BDA 或 mesh shader 全部存在。[SPEC][ENGINE]

## 2. 所属对象链路

```text
场景 / resident geometry → reset → compute cull → optional compact/finalize
→ memory dependency → indirect buffer + independent count buffer + visible IDs
→ 已绑定的 pipeline / descriptor / vertex / index 状态 → draw
```

### 上游依赖

具备已绑定内存、正确 usage 和范围的 buffer；GPU 写入需 storage usage，CPU 上传满足 flush 与提交依赖。

### 下游影响

Indirect 参数不会自动切换 pipeline、材质 descriptor 或 index buffer；按相容状态分 bin，每个 bin 先绑定状态再绘制。跨 queue 需要 semaphore；仅跨 family 的 exclusive 资源还需要 ownership release/acquire。[SPEC]

## 3. 核心对象与 API

### 核心 Vulkan 对象

VkBuffer / memory、三种 indirect command 结构体、可选独立 count buffer；不是 VkCommandBuffer。

### 常用 API

基础 draw/indexed draw/dispatch，Count 与 mesh 间接路径按以下条件选择。

### 相关扩展 / 版本

见能力表，API核心化不等于可选 feature 自动启用。

<a id="indirect-capability-fallback"></a>
### indirect-capability-fallback

| 路径 | 独立条件 | 退路 |
|---|---|---|
| CPU 合批 / instancing | 普通 graphics | 公平正确性与性能基线，不是故意每物体一个 draw |
| 固定槽 GPU culling | 每槽命令完整，隐藏槽 `instanceCount=0` | 无 `multiDrawIndirect` 时每次 `drawCount=1`；可用 instancing 做另一种合批 |
| non-Count MDI | `multiDrawIndirect` 已启用且 drawCount 在 limit 内 | 多次单命令 indirect |
| 紧凑有效前缀 + Count | 核心 1.2 路径查询/启用 `drawIndirectCount`，或合法 KHR 扩展路径及入口 | 固定槽；不能只因为 API 版本高就默认 feature 开启 |
| 非零 `firstInstance` | `drawIndirectFirstInstance` 已启用 | firstInstance=0，单 draw push base、实例属性或合法 SSBO 索引方案 |
| shader `DrawIndex` / `gl_DrawID` | shader draw parameters 的独立版本/feature 路径 | CPU 分 draw 设置 base；不可假设每次单 draw 的 DrawID 仍跨调用累加 |
| BDA / descriptor indexing | 分别查询、启用所用子 feature | 普通 SSBO / descriptor 分 bin |

Count API 与 non-Count API 的有效用法分开检查；不要把 non-Count 的 `drawCount > 1` 条件机械当作 Count API 的同名参数。引擎可以选更保守策略，但须标为策略而非规范。[SPEC][ENGINE]

`vkCmdDrawIndirectByteCountEXT` 属于 `VK_EXT_transform_feedback`，从字节计数推导一次非索引绘制的 vertex count，不是数组 draw-count 的替代。[SPEC]

## 4. 标准使用流程

### CPU 上传参数模式（简单场景）

先验证命令字段/大小，再等 slot 完成、写入/flush，并提交合法 draw；使用相同能力和范围检查。

### GPU-driven 模式（典型工程路径）

1. 等待该 frame slot 所有消费者真正完成，选择 scene/view/residency generation。
2. 重置计数、overflow 标志和所有固定槽（或保证本帧每槽完整覆盖）。
3. reset→compute dependency；cull 输出 bounds 内命令/ID。
4. compact/finalize 之间建立 compute write→compute read/write dependency。
5. finalize count、command、ID 分别同步到真实消费者，绑定状态 bin 后 draw。
6. 本帧完成前不得覆写、释放或取消已经被 submit 引用的资源。[ENGINE]

## 5. 关键字段

### 结构体定义

`VkDrawIndirectCommand`：四个 uint32（vertexCount, instanceCount, firstVertex, firstInstance），紧密标量布局 16 bytes。
`VkDrawIndexedIndirectCommand`：uint32 indexCount, instanceCount, firstIndex；**int32 vertexOffset**；uint32 firstInstance，20 bytes；offsets=0/4/8/12/16。
`VkDispatchIndirectCommand`：uint32 x/y/z，12 bytes。C++ 使用 `sizeof/offsetof/static_assert`，GLSL/SPIR-V 验证实际 ArrayStride/Offset；不要随意把 indexed stride padding 成 16，也不要把 shader 对齐假设当 ABI。[SPEC][ENGINE]

- offset 为 4-byte aligned；有 INDIRECT_BUFFER usage，绑定有效内存，读范围合法。
- non-Count drawCount=0 合法；drawCount≤1 时 stride 被忽略；drawCount>1 时 stride 是 4 的倍数且≥命令尺寸。
- non-Count count=1 校验 offset+sizeof；count>1 校验 `offset + stride*(count-1) + sizeof`，算术先防溢出。
- Count 的 stride 始终为 4 的倍数且≥命令尺寸；maxDrawCount≥1 时按该上限检查同一范围公式。
- countBuffer 是独立 INDIRECT_BUFFER，countBufferOffset 对齐4且有完整 uint32；实际读出的 count 本身也必须≤maxDrawIndirectCount，不能靠 maxDrawCount 截断超设备 limit 的坏计数。
- dispatch 分别检查 x≤maxComputeWorkGroupCount[0]、y≤[1]、z≤[2]；不是检查三维乘积。零维无工作；shader local size 与总 local invocation 另查限制。[SPEC]

## 6. 正确性检查点

### 创建阶段

存储写命令还需 STORAGE_BUFFER；fill reset 还需 TRANSFER_DST。

### 使用阶段

录制时满足 graphics/compute queue 能力、render pass/dynamic rendering 范围、pipeline 与资源绑定约束。基于 index/vertex 最大访问范围校验生成命令，vertexOffset 负值可能合法，但最终索引访问不得越界。[SPEC]

### 同步阶段

逐资源检查 §10 的 producer/consumer；不能让 count 或 ID 列表遗漏依赖。

### in-flight 风险

命令引用的全部 buffer/descriptor/geometry generation 都活到最后 consumer 完成。

## 7. 高频错误

<a id="indirect-capacity-safety"></a>
### indirect-capacity-safety

命令 ABI 同时验证 sizeof/offsetof/ArrayStride、stride、offset 与 signed vertexOffset；具体 non-Count/Count 零值与范围条件必须补读本卡 §5，不能只按槽数检查。

固定槽策略在每帧写全有效命令，包括不可见对象的 instanceCount=0；不能保留前帧可见状态。紧凑策略对每次 atomic 返回位置 **先验证 slot<capacity 再写**；总候选数/分批计数须证明 uint32 不溢出，或用饱和/分段算法。finalize 在所有写入后发布 `validPrefixCount=min(accepted,capacity,deviceLimit)`，且这个前缀确实每项完整初始化；只有 clamp counter、留下前缀洞或先写再检查都不安全。[ENGINE]

capacity=0、无可见、全可见、恰好满、超容量、尾 workgroup、非法 bounds 与 reset 中断都必须测试。资源分配容量、dispatch 候选数与 draw count 是三个不同边界。溢出计数仅诊断，不得让越界写发生后再报警。[ENGINE]

## 8. Debug 检查路径

### Validation Layer

启用目标 SDK 支持的核心与 synchronization validation，保留实际运行日志；无 layer 不标 clean。

### RenderDoc / AGI

可用时检查命令/计数/IDs与绑定状态，不能仅凭画面正常排除越界。

### 日志 / 代码检查

可见 ID 列表常由 vertex shader 的 SSBO 读取，不是 indirect parser 读取；其 barrier 目标是实际 shader stage/SHADER_READ。firstInstance、DrawID、instance index 到源对象 ID 的映射需在 fallback 路径保持等价。descriptor generation 与 resident geometry generation 一起发布；不得读取已回收纹理或 LOD。[ENGINE]

## 9. 生命周期风险

### 创建时机

按容量与帧/view/bin分配，失败回滚未提交资源。

### 使用时机

每 frame slot / view / bin 的 commands、count、IDs 与 upload staging 跟随最后 consumer completion 退休。CPU 写 HOST_VISIBLE 内存前避免与 GPU 冲突；非 HOST_COHERENT 要按 nonCoherentAtomSize 规则 flush。HOST_COHERENT 仅免 flush，不免竞争；正确 host write→queue submit 的域操作与 GPU barrier 不是同一件事。GPU→CPU readback 需完成等待和非 coherent invalidate。unmap 本身不代替以上同步。[SPEC]

### 销毁时机

最后 GPU consumer 完成后才释放；device lost 走单独全局恢复路径。

### in-flight 风险

取消 CPU任务不取消已经提交的 GPU引用。

## 10. 同步风险

### CPU-GPU 同步

遵守 §9 的完成等待、flush/invalidate 与提交依赖。

### GPU-GPU 同步

- compute→indirect 参数/独立 count：COMPUTE_SHADER/SHADER_WRITE → DRAW_INDIRECT/INDIRECT_COMMAND_READ。
- **dispatch indirect 参数读取也属于 DRAW_INDIRECT**；不存在专用 dispatch-indirect stage 标志。
- fill reset 在 Sync2 使用 CLEAR/TRANSFER_WRITE（ALL_TRANSFER 也覆盖），不能用仅 COPY 漏掉 fill；legacy 使用 TRANSFER。
- compute→可见 ID SSBO：实际 VERTEX_SHADER（或 mesh/task 等）/SHADER_READ；生成 vertex/index 数据分别覆盖 VERTEX_ATTRIBUTE_INPUT/VERTEX_ATTRIBUTE_READ 与 INDEX_INPUT/INDEX_READ。
- 同 queue 用 memory dependency；不同 queue 同 family 用 semaphore；跨 family exclusive 再配 ownership；concurrent sharing 不免 semaphore 与内存依赖。

### 资源访问同步

完整范围与阶段表见 `05_workflows/03_compute_workflows/compute_to_graphics_sync.md#gpu-produced-draw-sync`。[SPEC][ENGINE]

## 11. Android 注意点

逐设备查询每项 feature/limit，保留固定槽、单 indirect 与 CPU 合批路径。不能从 GPU 品牌推导 Count、firstInstance、mesh、async 收益。软件 Vulkan 可检验 API/图像，但不是移动 GPU 性能与能耗证据。[ENGINE]

## 12. 性能注意点

### CPU 侧

测量 CPU update/record/submit，与合理合批基线比较。

### GPU 侧

计入 reset+cull+compact+barrier+draw 全 GPU 成本与内存峰值；低对象数或低剔除率可能更慢。

### 移动端

同场景、分辨率、材质、LOD、可见集与 CPU 合批基线对比，记录热状态/driver，才能归因。[ENGINE]

## 13. 专家经验

先固定槽和 CPU 参考建立正确性，再按设备启用 Count；每个优化单独 A/B。GPU-driven 不等于“一个 draw 画所有状态”，也不等于“异步 queue 一定并行”。LOD/Hi-Z/多视图入口：`05_workflows/03_compute_workflows/add_compute_pass.md#gpu-driven-rendering`。[ENGINE]

## 14. 相关 API 卡片

- `03_api_manual/03_command_buffer/command_buffer.md`
- `03_api_manual/06_pipeline/mesh_shader.md`
- `03_api_manual/08_synchronization/pipeline_barrier.md`
- `02_core_mental_model/compute_graphics_relationship.md#gpu-scene-contract`

## 15. 需要回查官方文档的情况

固定规范源：[Vulkan-Docs drawing](https://github.com/KhronosGroup/Vulkan-Docs/blob/b94f8bd2d004d2949469d8a5071ee10eb7d23566/chapters/drawing.adoc)、[dispatch](https://github.com/KhronosGroup/Vulkan-Docs/blob/b94f8bd2d004d2949469d8a5071ee10eb7d23566/chapters/dispatch.adoc)、[synchronization](https://github.com/KhronosGroup/Vulkan-Docs/blob/b94f8bd2d004d2949469d8a5071ee10eb7d23566/chapters/synchronization.adoc)。回查目标 API 的最新 VUID、扩展到核心的 feature 链、limits、任务/网格差异及 draw count/stride 的条件，不复制另一 API 的条件。实验代码与实际 SDK 版本另外记录。[SPEC]


<a id="device-generated-commands-contract"></a>
## EXT Device Generated Commands：不能套普通 indirect ABI

`VK_EXT_device_generated_commands` / `deviceGeneratedCommands` 与完整依赖需显式启用；查询 `VkPhysicalDeviceDeviceGeneratedCommandsPropertiesEXT` 的 supported stages、supported token inputs、sequence/token/count/stride limits。EXT 与 NV DGC 是不同接口族，不能混用结构体、layout 或 feature；普通 multiDrawIndirect/indirectCount 也不自动授予 DGC。[SPEC]

正常路径：定义 `VkIndirectCommandsLayoutEXT` 的 token 类型/offset/stride 与 shaderStages → 必要时创建 `VkIndirectExecutionSetEXT` 并登记符合 indirect-bindable 条件的 pipelines/shader objects → `vkGetGeneratedCommandsMemoryRequirementsEXT` → 按返回 memoryTypeBits/size/alignment 准备 preprocess buffer 与设备地址 → producer 写 token/count buffers → 满足对应 stage/access 依赖 → implicit preprocess 的 `vkCmdExecuteGeneratedCommandsEXT` 或显式 preprocess → execute。GPU 生成 sequence count 仍须受 maxSequenceCount、容量、index 与地址范围约束，不能信任 shader 写入值。[SPEC]

显式路径要求 layout 的 `VK_INDIRECT_COMMANDS_LAYOUT_USAGE_EXPLICIT_PREPROCESS_BIT_EXT`；`vkCmdPreprocessGeneratedCommandsEXT` 的 stateCommandBuffer 处于 recording，同 queue family，已绑定参与快照的 pipeline/shaders、descriptor 与 push constants。execute 时相关状态必须匹配，token 的输入、execution-set 与 preprocess 内容按 VU 保持有效；改变会影响预处理的数据就重新 preprocess。host 不得并发不安全地修改 stateCommandBuffer。`isPreprocessed=VK_TRUE` 不能用于跳过未做的工作。[SPEC]

producer writes → COMMAND_PREPROCESS / COMMAND_PREPROCESS_READ；preprocess write → DRAW_INDIRECT / INDIRECT_COMMAND_READ 使用规范要求的依赖（EXT 的 COMMAND_PREPROCESS stage/access aliases）；execute 即使预处理也可能写 preprocess buffer，不能将其当永久只读共享资源。资源读取/输出仍需各自 shader、transfer 等依赖与跨 family ownership。执行后检查状态失效表，后续显式 draw/dispatch 重新绑定被扰动状态；不从“同一命令缓冲”推断依赖已满足。[SPEC]

失败：不支持 token/stage、memory requirements 不满足、地址越界、过期预处理均拒绝 execute，回退普通 indirect/count 或 CPU 显式 draw/dispatch。回退仍遵守本卡 ABI/容量合同。所有 layout/execution-set/pipeline/shader/preprocess/token 资源直到最后提交完成才销毁/覆写；性能优势需实测。测试分别记录 CPU 负例与真实 DGC GPU 结果，不能用 ordinary indirect 的 PASS 代替 DGC。

固定规范（Vulkan 1.4.368，source-read；不是设备验证）：[device-generated-commands / EXT layout, execution, preprocessing](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/device_generated_commands/generatedcommands.adoc)；[preprocess synchronization access](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc)。


<a id="generated-commands-family-differences"></a>
## NV 与 EXT DGC：接口与预处理语义差异

此处是定向迁移合同，不代表所有 token/stage/feature 组合已验证。先按实际 extension、feature 和 limits 选一条族，再构建其布局；不要通过改函数后缀复用另一族的 token stream。[SPEC]

| 族与启用 | 对象 / 输入 / shader binding | 预处理、count 与失败边界 |
|---|---|---|
| `VK_NV_device_generated_commands`：依赖 `(Vulkan 1.1 + buffer_device_address) 或 Vulkan 1.2`；`VkPhysicalDeviceDeviceGeneratedCommandsFeaturesNV.deviceGeneratedCommands` | `VkIndirectCommandsLayoutNV` 有 pipelineBindPoint、多个 pStreams/各自 streamStride；`VkGeneratedCommandsInfoNV` 传 pipeline、preprocessBuffer/Offset/Size、sequencesCountBuffer、sequencesIndexBuffer。graphics shader group token 走 NV graphics shader-group 合同，不是 EXT execution-set index；pipeline 必须匹配执行时实际绑定。[SPEC] | `vkGetGeneratedCommandsMemoryRequirementsNV` 用实际 pipeline/layout/max count 查容量。`isPreprocessed=true` 要显式 preprocess 已在设备执行、同 GeneratedCommandsInfo 与相同输入内容（preprocessBuffer 除外），并有 EXPLICIT_PREPROCESS layout flag。NV 此时 preprocess buffer **不被修改**，但其 opaque 内容不许应用修改或复制到另一 buffer 复用。sequencesCount 为预留上限，count buffer 是 uint32，实际 count 受上限约束；indexed sequence 的索引范围另校验，不靠 count clamp 修复越界 stream。UNORDERED draw 不保证顺序，不能依 sequence 序号处理有依赖结果。transform feedback 不得 active；不支持则回普通 indirect。[SPEC] |
| `VK_NV_device_generated_commands_compute`：依赖 NV DGC | `deviceGeneratedCompute` 授权 dispatch/push constants；`deviceGeneratedComputePipelines` 另授权 pipeline binding；capture/replay 又是独立 feature。变 pipeline 路径需 `VK_PIPELINE_CREATE_INDIRECT_BINDABLE_BIT_NV`、`VkComputePipelineIndirectBufferInfoNV`、`vkGetPipelineIndirectMemoryRequirementsNV` 与 `vkGetPipelineIndirectDeviceAddressNV`，不是 Vulkan 对象 handle 塞进 token。[SPEC] | `vkCmdUpdatePipelineIndirectBufferNV` 在 render pass 外写 metadata，COPY/MEMORY_WRITE → COMMAND_PREPROCESS/COMMAND_PREPROCESS_READ barrier 后才可 preprocess；其 metadata allocation 与 pipeline 保留至最后使用结束。preprocess 前 descriptor/push constants 已指定且保持到执行提交，token 可按规则覆盖 push constants。NV compute dispatch 可任意顺序，不能把 command list 顺序当跨 dispatch barrier。缺 compute-pipeline feature 可固定已支持 pipeline 或回 CPU dispatch，不继承普通 NV graphics 支持。[SPEC] |
| `VK_EXT_device_generated_commands`：依赖 `((BDA 或 Vulkan 1.2) + (extended_flags 或 maintenance5)) 或 Vulkan 1.3`；EXT deviceGeneratedCommands | `VkIndirectCommandsLayoutEXT` 用 shaderStages + token/offset + 单 indirectStride；`VkGeneratedCommandsInfoEXT` 使用 indirectAddress、preprocessAddress、sequenceCountAddress。可选 `VkIndirectExecutionSetEXT` 保存 pipelines 或 shader objects：分别查询 supportedIndirectCommandsShaderStagesPipelineBinding / ShaderBinding；对象分别需要 `VK_PIPELINE_CREATE_2_INDIRECT_BINDABLE_BIT_EXT` / `VK_SHADER_CREATE_INDIRECT_BINDABLE_BIT_EXT`，两种 execution set 不能混装。更新只能写有效 index 和兼容接口，未初始化条目不能由 GPU 选中。[SPEC] | maxSequenceCount 与 count address 计算实际数，不授权越界 token/index/address。explicit preprocess 的 stateCommandBuffer 必须 recording、同 family、状态匹配，见上节；EXT execute 即使 `isPreprocessed=true` **仍可能写 preprocess buffer**，不能沿用 NV 只读假设。execute 后用规范 state invalidation 表决定重绑，不假设 selected pipeline/shader 留作下一次普通 draw。更新 execution set/输入或相关状态使预处理失效时重新 preprocess，不能把旧结果继续执行。[SPEC] |

三族都需 producer→preprocess/indirect-read 与 shader 资源依赖；独占资源跨 family 另处理 ownership，preprocess/execute 失败不提交依赖不存在输出的后续命令。所有引用 layout、execution-set、pipeline/shader、streams/count/index/metadata/preprocess 分配必须有效到最后已提交使用结束；不在 pending 使用期间更新/销毁。capacity、地址、状态不合法时 fail closed，回普通 indirect/count 或显式 CPU 录制并保留相同同步要求。无 GPU 测试不声称 DGC 性能或正确性 PASS。[SPEC][ENGINE]

<a id="transform-feedback-contract"></a>
## Transform Feedback：捕获流与 byte counter

`VK_EXT_transform_feedback` 依赖 properties2 或 Vulkan 1.1；启用 transformFeedback，geometryStreams 等另查，读取 maxTransformFeedbackBuffers/BufferSize/Streams 与各数据大小/stride 限制。它捕获最后 pre-rasterization shader stage 的输出，需要 SPIR-V `Xfb` execution mode 与 XfbBuffer/Offset/XfbStride 装饰；不是把普通 storage-buffer 写入换一个 usage 就成立。[SPEC]

正常路径：准备 TRANSFORM_FEEDBACK_BUFFER usage 的输出与 TRANSFORM_FEEDBACK_COUNTER_BUFFER usage 的 counter → `vkCmdBindTransformFeedbackBuffersEXT` → `vkCmdBeginTransformFeedbackEXT` → 合法 graphics draw → `vkCmdEndTransformFeedbackEXT`（可写 counter）→ 建立真实消费者依赖。begin 为空 counter 从 binding 起点开始；有 counter 从先前捕获的字节位置恢复。end 的 counter 为 4-byte **字节偏移**，不是 vertex count，也不是 GPU append 的原子计数器。[SPEC]

恢复捕获时 TRANSFORM_FEEDBACK / COUNTER_WRITE → TRANSFORM_FEEDBACK / COUNTER_READ；输出作为 vertex buffer 时 TRANSFORM_FEEDBACK_WRITE → VERTEX_ATTRIBUTE_READ；counter 用 `vkCmdDrawIndirectByteCountEXT` 时目标为 DRAW_INDIRECT / TRANSFORM_FEEDBACK_COUNTER_READ。`transformFeedbackDraw` 是额外 property，确认后才按 floor(max(0, byteCount-counterOffset)/vertexStride) 推导 vertexCount（firstVertex=0），不能把 byteCount 直接传普通 indirect draw。`transformFeedbackQueries` 与 stream query 支持独立于 transformFeedback feature；查询区分实际写入与所需 primitive 数，不能将溢出时写入数当需求量。[SPEC]

容量/装饰/feature/query 支持不满足时停止该路径，改用经过验证的 storage-buffer compute capture 或 CPU 路径并记录输出语义差别；不能把 buffer overflow 当自动扩容，也不能在 active capture 中随意切换不兼容 pipeline。所有 buffer/counter 保留至最后提交完成，重用须同步。mesh、multi-stream、rasterization-stream 与 device-address 新命令的完整交互仍待审查；本节只覆盖传统 EXT 捕获与 byte-count 路径，Device NOT_RUN。

固定 1.4.368 规范证据：[NV layout](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/device_generated_commands/generatedcommands.adoc#L380)；[NV execute/preprocess immutability](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/device_generated_commands/generatedcommands.adoc#L2679)；[NV compute address](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/device_generated_commands/generatedcommands.adoc#L2036)；[NV metadata synchronization](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/pipelines.adoc#L1951)；[EXT execution sets](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/device_generated_commands/generatedcommands.adoc#L2131)；[EXT preprocess writes](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/device_generated_commands/generatedcommands.adoc#L3504)；[transform feedback](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/vertexpostproc.adoc#L41)；[counter synchronization](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/vertexpostproc.adoc#L432)；[byte-count draw](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/drawing.adoc#L2027)。

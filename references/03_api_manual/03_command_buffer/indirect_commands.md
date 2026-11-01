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

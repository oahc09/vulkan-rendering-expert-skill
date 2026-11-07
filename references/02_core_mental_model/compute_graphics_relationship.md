# Compute 与 Graphics 关系

## 核心思想

Compute pipeline 和 graphics pipeline 可以共享 buffer / image，但不会自动同步。

一旦 compute 写入的资源被 graphics 读取，就必须建立明确的 producer / consumer 关系。

## 基本链路

```text
Compute Pipeline
→ Descriptor / Storage Buffer / Storage Image
→ vkCmdDispatch
→ Barrier
→ Graphics Pipeline Consumer
→ vkCmdDraw
```

## 典型场景

### Compute 写 Storage Buffer，Graphics 读取

```text
Compute Shader Write Storage Buffer
→ Buffer Barrier
→ Vertex Shader / Vertex Input / Fragment Shader Read
```

用途：

1. 粒子模拟。
2. GPU culling。
3. instance 数据生成。
4. indirect draw 参数生成。

### Compute 写 Storage Image，Fragment 采样

```text
Compute Shader Write Storage Image
→ Image Barrier
→ Fragment Shader Sampled Read
```

用途：

1. Compute blur。
2. Procedural texture。
3. Reaction diffusion。
4. Image processing。

### Compute 生成 Indirect Draw 参数

```text
Compute Shader Write Indirect Buffer
→ Buffer Barrier
→ vkCmdDrawIndirect / vkCmdDrawIndexedIndirect
```

关注点：

1. buffer usage 需要包含 STORAGE_BUFFER 和 INDIRECT_BUFFER。
2. barrier dstAccess 需要覆盖 indirect command read。
3. stage 要覆盖 draw indirect 阶段。

## 资源要求

Compute 常用资源：

```text
Storage Buffer
Storage Image
Uniform Buffer
Sampled Image
Sampler
```

Graphics 常用读取：

```text
Vertex Buffer
Index Buffer
Uniform Buffer
Sampled Image
Storage Buffer
Indirect Buffer
```

跨 pipeline 共享资源时，必须确保：

1. usage flag 覆盖双方用途。
2. descriptor 类型匹配。
3. image layout 匹配当前访问方式。
4. barrier 覆盖 producer / consumer。
5. command buffer 顺序和 queue 同步正确。

## 高频错误

1. compute 写 storage image 后，没有 barrier 就采样。
2. storage image 仍处于 GENERAL，但 descriptor 按 SHADER_READ_ONLY_OPTIMAL 填写。
3. image usage 缺少 STORAGE 或 SAMPLED。
4. compute 和 graphics 在不同 queue 缺少 semaphore；跨 family 的 exclusive 资源还缺少 ownership transfer。
5. compute 写 indirect buffer 后，没有同步 indirect command read。
6. dispatch group 数量错误导致部分区域未写入。
7. workgroup size 与图像尺寸没有正确边界处理。

## 专家规则

```text
Compute 和 Graphics 之间的关键不是“两个 pipeline 都能绑定资源”，而是资源状态、访问权限和同步关系必须完整。
```

<a id="gpu-scene-contract"></a>
## gpu-scene-contract

GPU Scene 是带版本与寿命的数据契约，不是把所有对象塞进一个 buffer 就完成。[ENGINE]

| 字段 / 资源 | 契约 |
|---|---|
| object ID + transform + world bounds | 稳定 ID；负缩放/非均匀缩放/动画后的保守 bounds；非有限值保守可见并诊断 |
| material / mesh / LOD ID | state bin 与 descriptor / pipeline 相容；LOD 仅指向 resident generation |
| geometry ranges | vertex/index offset、signed baseVertex、长度、usage 与容量可验证 |
| scene / residency generation | CPU 更新、GPU snapshot 与描述符同一代发布；旧代等最后使用者完成 |
| per-view visible IDs / commands / count / Hi-Z | 每 view 独立容量、reset、projection/depth convention 与完成标记 |
| shared geometry / textures | 多视图只读共享；最后一个消费者完成才释放，不以主相机完成代替 |

实例 transform 用最大奇异值的上界放大球半径（一般 affine 可用 Frobenius 范数上界，含 shear）；AABB 可用 abs(linearMatrix)*extent。不可只取有符号最大 scale。平面测试包含 epsilon 与半径；near-plane 相交或无可靠投影 bounds 的对象保守保留。CPU/GPU ID 可见集逐项对照，同时渲染比较，不能仅比较数量。[ENGINE]

入口：`05_workflows/03_compute_workflows/add_compute_pass.md#gpu-driven-rendering`；参数 ABI 与 fallback：`03_api_manual/03_command_buffer/indirect_commands.md#indirect-capability-fallback`。

<a id="simulation-state-contract"></a>
## 仿真状态合同（C1，v1.0.16 candidate）

适用：把绳索、规则布料、受限高度场和交互粒子作为已有 Vulkan renderer 的数据生产者；不建立通用物理引擎。输入为带时间戳/单位/坐标空间的事件、模型配置和资源代际；输出为已完成的不可变 snapshot。以下字段是应用合同，不是 Vulkan API 字段。[ENGINE]

| 状态 | 必须定义的语义 |
|---|---|
| simulationTick / simulationTime | 实际完成的离散更新进度；提交但未完成的 tick 单独记账 |
| fixedStep / substeps / solverIterations | 外层 tick 时间、每 tick 的时间细分、每子步的约束迭代次数；不可互换 |
| accumulator / droppedTime | 待推进时间与主动丢弃时间；长暂停不可默默吞时间或无限追赶 |
| inputTimestamp / eventId | 映射到 simulation time 的输入时刻与本 world generation 内唯一事件身份 |
| worldGeneration / topologyGeneration | 世界重置、约束拓扑改变时递增；过期事件/回调/输出拒绝发布 |
| snapshotId / completion | 同一 tick 的 position/normal/bounds、拓扑/LOD与资源代际，以及 GPU 完成证据 |

共享世界只有一个调度 owner；第二 view、shadow、预览或壁纸只是 consumer，不按 callback 数推进。Surface 暂停不等于世界暂停：可见性策略决定是否计算，停止一个输出不能销毁其他输出仍引用的 state。模拟 A/B、不可变 render snapshot 和每输出 previous-render snapshot 是不同寿命，不因都叫“双缓冲”就可复用。[ENGINE]

持续 force（力或明确标为 acceleration）与一次 impulse（动量增量）分开；驱动固定点同时给上一/当前子步目标位置和速度规则，inverseMass=0 本身不足以定义运动。输入单位、坐标空间、插值方式、迟到事件政策和容量必须明确。拒绝非正 dt、负/非有限 inverse mass、NaN/Inf、异常幅度及容量越界，计数诊断；故障时冻结最后有效 snapshot 或受控 reset，不用无界速度裁剪掩盖问题。

确定性只声明固定输入的算法可复现、同实现容差重复或跨设备容差可接受中的实际验证层；固定 seed、消除写竞争不证明跨 GPU 逐位一致。验收比较相同 ticks/事件在30/60/120Hz呈现、长暂停及双 view 下的进度/事件消费；数值、Shader编译、Vulkan执行、Live和Android持续性能分别报告。v1.0.15透明外观尚未集成时，用不透明wireframe/高度可视化验证，不宣称前置能力存在。[ENGINE]

关联规则：hard_rules 2/3/17–19，修改时保留 Evidence Map、Architecture Map、R1–R5 与适用 G1–G6。按需继续读 [调度](../05_workflows/03_compute_workflows/add_compute_pass.md#simulation-scheduling)、[渲染交接](../05_workflows/03_compute_workflows/compute_to_graphics_sync.md#simulation-render-handoff)、[退休](../05_workflows/05_resource_management/manage_frame_resources.md#simulation-snapshot-retirement)。时间细分的数值边界依据 [Small Steps, 2019](https://matthias-research.github.io/pages/publications/smallsteps.pdf)，不是新近 API 特性。

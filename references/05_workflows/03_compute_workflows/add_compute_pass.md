# Workflow: Add Compute Pass

## 0. 适用范围

### 适用

- 新增 compute shader pass。
- 用 compute 写 storage buffer / storage image。
- 实现粒子、blur、simulation、culling、image processing。
- Compute 输出被后续 graphics / compute pass 使用。

### 不适用

- 只新增 fragment shader 后处理。
- 不涉及 compute pipeline。
- 只做 CPU 计算。

---

## 1. 任务目标

新增一个 Vulkan compute pass：

```text
Storage Resource
→ DescriptorSet
→ Compute Pipeline
→ vkCmdDispatch
→ Barrier
→ Consumer Pass
```

---

## 2. 输入条件

需要确认：

- compute shader 输入 / 输出资源。
- storage buffer / storage image 类型。
- workgroup size。
- dispatch group count。
- 是否与 graphics 共用 queue。
- compute 输出由谁消费。
- 是否需要跨 queue synchronization。

---

## 3. 前置检查

- [ ] compute queue / graphics queue 可用。
- [ ] shader 编译链路支持 compute。
- [ ] descriptor 管理可用。
- [ ] storage buffer / image usage 正确。
- [ ] barrier 机制可用。
- [ ] RenderDoc / AGI 可看到 dispatch。

---

## 4. Vulkan 对象链路

```text
Compute Shader
→ DescriptorSetLayout
→ PipelineLayout
→ Compute Pipeline
→ Storage Buffer / Storage Image
→ vkCmdBindPipeline
→ vkCmdBindDescriptorSets
→ vkCmdDispatch
→ Barrier
→ Consumer
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| input buffer | `VkBuffer` | `STORAGE_BUFFER` / `UNIFORM_BUFFER` | pass input | 否 |
| output buffer | `VkBuffer` | `STORAGE_BUFFER` | pass output | 否 |
| output image | `VkImage` | `STORAGE | SAMPLED` | pass output | 视尺寸而定 |
| descriptor set | `VkDescriptorSet` | compute resource binding | per-pass / per-frame | 视资源而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | Storage Buffer | input / output buffer | Compute |
| set=0,binding=1 | Storage Image | output image | Compute |

注意：

- `vkCmdBindDescriptorSets` 的 bind point 必须是 `COMPUTE`。
- `stageFlags` 必须包含 compute。
- storage image layout 通常需要正确处理，常见为 `GENERAL`。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| compute shader write | storage buffer | compute shader write → vertex/fragment/compute read | next pass |
| compute shader write | storage image | `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` 或后续 layout | graphics pass |

关键点：

- producer stage：`COMPUTE_SHADER`
- producer access：`SHADER_WRITE`
- consumer stage：根据后续用途选择
- consumer access：根据后续用途选择
- graphics 采样前需 memory dependency；仅当前 layout 不适合 consumer 时 transition，合法 GENERAL 采样可保持 layout。

---

## 7.5 架构决策（Architecture Decision）

需求 → 约束 → Candidate Architecture → Trade-off → Decision。[ENGINE]

| 阶段 | 决策问题 |
|---|---|
| 需求 | producer 数据并行与真实 consumer 的语义，是否需要 raster/depth/blend |
| 约束 | queue 能力、依赖图、资源共享模式、目标平台、测量误差与内存预算 |
| Candidate | A 同 queue + 精确 barrier；B 独立 queue + binary/timeline semaphore；C 合适时由 graphics pass 实现 |
| Trade-off | queue 不等于硬件独立执行单元；同 queue 不保证所有 stage 串行，跨 queue 不保证 overlap。B 增加提交/等待和可能的跨 family ownership 成本；图像 layout 改变与 tile 成本须测量，不声称每次 barrier 都 flush tile |
| Decision | 默认先实现易验证的 A；仅依赖图允许独立工作且实测全帧收益时启用 B。记录为何不选另一边、可接受的正确性/功耗/延迟边界与回退条件。没有通用 20%/30% 阈值 |

binary semaphore 的 signal/wait 配对与 timeline 的合法递增值、完成归属都要验证；timeline 不自动转移 queue family ownership。复评依据为同负载全帧时间、等待空泡、内存峰值与稳定性，不以单个 compute pass 时间代替收益。验证门见 `../../00_expert_entry/verification_gate.md`。

---

## 8. 实现步骤

1. 编写 compute shader。
2. 创建 storage buffer / storage image。
3. 创建 descriptor set layout。
4. 创建 pipeline layout。
5. 创建 compute pipeline。
6. 分配并更新 descriptor set。
7. command buffer 中 bind compute pipeline。
8. bind compute descriptor set。
9. 计算 dispatch group count。
10. 调用 `vkCmdDispatch`。
11. 插入 compute output barrier。
12. 接入后续 graphics / compute consumer。
13. 接入 destroy / recreate。

---

<a id="gpu-driven-rendering"></a>
### gpu-driven-rendering

先建立同 seed、同材质/几何/分辨率的 CPU culling + instancing 合批参考，然后 GPU 固定槽（隐藏槽 instanceCount=0），最后可选 compact + Count。GPU Scene 的 transform/bounds/mesh/material/residency generation 见 `02_core_mental_model/compute_graphics_relationship.md#gpu-scene-contract`；能力与 command ABI 见 `03_api_manual/03_command_buffer/indirect_commands.md#indirect-capability-fallback`。[ENGINE]

每次 dispatch 的尾线程 bounds check；使用与 CPU 一致的 world-space sphere/AABB 和归一化平面（或显式平面长度系数）。非均匀/负 scale、shear、动画变形的 bounds 必须保守；near-plane 相交、多视图或 NaN/Inf 不能激进剔除，保留并计数诊断。FP16 arithmetic 不等于 storage/IO 支持；临界剔除 FP32 或保守误差膨胀，不以精度降低造成漏物体。[ENGINE]

实现顺序：合法资源与 bin → reset所有槽/计数 → cull → 可选 compact → finalize 有效前缀 → 分别同步 commands/count/IDs → 按 bin 绑定绘制。CPU参考与GPU可见ID集合及图像都比较；顺序可不一致，重复/丢失不可忽略。Count、firstInstance、DrawID、BDA、bindless 是各自独立能力，不作为一个大开关。[ENGINE]

<a id="gpu-lod-residency"></a>
### gpu-lod-residency

LOD 决策使用 view-space projected size/error 与上下不同的阈值形成 hysteresis；相机跳变重置历史。目标 LOD 未 resident 时选已 resident 的更粗层或明确占位 mesh，不能引用仍在 upload / canceled / 旧 generation 的地址。选择和描画 snapshot 共享 residency generation；旧 geometry、descriptor、commands 等最后 consumer 完成后退休。几何容量、indices 范围与 signed vertexOffset 分别验证。[ENGINE]

每帧记录 requested/resident/selected LOD、fallback 次数、上传字节和峰值内存；无 resident LOD 的对象不能被静默当成 occluded。资源生产与预算见 `05_workflows/05_resource_management/manage_resource_lifetime.md#geometry-streaming-retirement`。[ENGINE]

<a id="hiz-occlusion"></a>
### hiz-occlusion

最低可验证路径是 **当前帧**：可靠不透明 occluder depth prepass → 构建 farthest-depth pyramid → conservative bounds test → 主绘制。传统 Z（near=0/far=1）用 **max reduction**，reversed Z（near=1/far=0）用 **min reduction**；未覆盖像素/孔洞保持 far clear，令测试偏向可见。对象最近深度只有严格落在整个投影 footprint 的最远遮挡深度之后（含保守 epsilon）才可剔除。[ENGINE]

覆盖 footprint 的所有 pyramid texel，而非随便一个中心点；NPOT 边缘 reduction 覆盖全部原像素，clamp 范围不能遗漏最后一行/列。跨 near plane、w≤0、不可靠 clip bounds、相机/viewport/projection 不匹配直接可见。MSAA 要保守处理每个 sample 的 uncovered 情况；alpha-test occluder 必须与主 pass 的 coverage 一致，透明物体默认不作 occluder；动态或变形 occluder 必须用本帧匹配姿态。不要将硬件 depth resolve 的默认模式误当保守 Hi-Z。[ENGINE]

每级 pyramid 写→读 dependency、depth attachment 写→采样 dependency、layout/format feature、image usage 都必须正确；Hi-Z 节省的 draw 与 prepass+pyramid+barrier 成本一起计时。分别测试 conventional/reversed、NPOT、孔洞、近面、空场景、全可见与遮挡场景，与无 occlusion CPU/GPU参考图像对比。[ENGINE]

前帧 Hi-Z 仅为独立可选优化，默认关闭；相机切换/瞬移、projection/viewport/depth convention 变化、occluder 移动/消失、分辨率或 generation 变化使历史无效。仅上一帧“被挡住”不能证明本帧被挡住；无可证明保守 reprojection/扩大 bounds 与 disocclusion 处理时退回当前帧或无 occlusion。[ENGINE]

<a id="multi-view-culling"></a>
### multi-view-culling

每个 view 独立 frustum、LOD、visible IDs、counter、commands、Hi-Z、projection/depth history 与 completion；不把主相机列表拿给反射/阴影/第二相机。共享只读几何与纹理可减少驻留成本，但 retirement 必须汇合所有 view consumer。多 view 执行不等于启用 Vulkan multiview feature；后者是另一能力与渲染模式。view 是相机/阴影/反射等渲染视图，不等于 Android Surface/Engine；一个 Surface 可有多 view，多个 Surface 也不能共享可变 command/count 完成状态。[ENGINE]

<a id="gpu-particles"></a>
### gpu-particles

粒子 ping-pong state、alive flags、compact IDs、indirect draw arguments 使用有界 capacity；spawn、alive append、overflow guard 与尾线程检查和场景 culling 一样不可省。reset→simulate→compact→draw 每阶段依赖明确。加法混合可用无序 alive 列表作为受限实验；普通 alpha 混合需排序/合适的透明方案，不能把加法图像正确性推广到所有粒子。统计 active/retired/overflow，并测试0、满容量和高速 churn。[ENGINE]

对应实际实验在 tests 仓库 `tests/fixtures/engine_scale_lab/`：软件 Vulkan 的编译/运行和真实 Android MobileScale 属于不同证据层；没有设备数据不得给出 60 FPS 或跨 GPU 的性能结论。[ENGINE]

## 9. Android 注意点

- 检查目标 GPU 对 storage image format 的支持。
- workgroup size 不宜盲目过大。
- 移动端 compute + graphics 共享带宽，需用 AGI 验证。
- 如果 output image 随屏幕尺寸变化，rotation 后必须重建。
- pause / resume 后 compute resource 生命周期要稳定。

---

## 10. 验证方式

- [ ] Validation clean。
- [ ] RenderDoc / AGI 能看到 dispatch。
- [ ] storage buffer / image 有输出。
- [ ] 后续 graphics 能读取 compute 输出。
- [ ] 多帧运行稳定。
- [ ] workgroup 数量非 0 且覆盖目标范围。

---

## 11. 常见失败模式

1. 意外的 dispatch group count 为 0 导致没有工作。
2. descriptor 绑定到 graphics bind point。
3. storage image 缺少 `STORAGE` usage。
4. compute 写后 graphics 读缺少 barrier。
5. shader global invocation id 越界。
6. output 被后续 pass 覆盖。
7. Android GPU 不支持目标 storage image format。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`

<a id="hybrid-ray-query-workflow"></a>
## 可选混合 Ray Query 工作流

先读 [独立能力](../../03_api_manual/06_pipeline/compute_pipeline.md#ray-query-capability-contract)、[AS 资源](../../03_api_manual/04_buffer_image_memory/memory_allocation.md#acceleration-structure-resource-contract)、[依赖表](../../03_api_manual/08_synchronization/pipeline_barrier.md#as-build-query-dependencies)。复用现有 Pipeline/Descriptor/Queue/ResourceManager。[ENGINE]

链路：驻留 geometry / skinning→BLAS→barrier→TLAS→barrier→绑定 AS descriptor 与必要材质数据→普通 compute dispatch 或 graphics fragment query→明确语义的结果→时域/合成→跨帧退休。缺能力时先选 shadow-map/probe，不能先创建非法 pipeline 再捕获错误当回退。[SPEC][ENGINE]

| 信号 | 查询/输出合同 | 失败/缺失处理 |
|---|---|---|
| 阴影 visibility | 在合法内容条件下 terminate-on-first-hit；区分 blocked/visible 与 radiance | 合法 shadow-map 或明确保守策略 |
| 单次反射 radiance | 遍历并确认合法 candidate，最终 committed 最近命中；返回 hit distance/normal/confidence | miss 或无驻留材质回退 probe；非完整 GI |
| SSR | 屏幕空间深度厚度与命中置信度 | 屏外/遮挡不匹配回退 probe，不补造数据 |

opaque 可以走快速路径。alpha-cutout 需以相同 UV/texture/cutoff 检查 candidate 并确认或继续；二值 cutout 不能当普通 alpha blending，反射不能用“第一个 candidate”替代最近有效命中。ray origin offset、tMin/tMax、法线空间与 transform 由尺度决定；用接触、薄片和大小场景测试自交/漏光。[ENGINE]

<a id="opacity-micromap-fallback"></a>
## OMM 条件增强与失效

能力矩阵分别记录 `VK_KHR_opacity_micromap` 与 `VK_EXT_opacity_micromap` 的 Registry 依赖、feature/property、对象/命令/结构/shader 控制。KHR/EXT 不是可随意替换后缀的 ABI。在本次固定 Registry，EXT 依赖 AS + (synchronization2 或 Vulkan1.3)，使用 VkMicromapEXT 及专用 build/copy/query；KHR 依赖 AS + VK_KHR_device_address_commands，以 VkAccelerationStructureKHR 和 AS 命令承载 micromap。KHR 不包含 EXT 的 hostMicromapCommands。query-only 仅启用 KHR 时，shader 需 SPV_KHR_opacity_micromap 的 OpacityMicromapIdKHR execution mode 且 specialization operand=true；启用 EXT 时 micromap 数据总被消费，两者同时启用遵循 EXT。实际分支未核对就关闭 OMM，保留材质 candidate alpha test。[SPEC][ENGINE]

关闭 OMM 必须真正禁用其遍历：在原 build 允许 `VK_BUILD_ACCELERATION_STRUCTURE_ALLOW_DISABLE_OPACITY_MICROMAPS_BIT_KHR`（对应 EXT 路径按其符号核对）时，用 instance 的 `VK_GEOMETRY_INSTANCE_DISABLE_OPACITY_MICROMAPS_BIT_KHR`，否则重建无 OMM 的 AS，并保证 cutout 使用 non-opaque candidate 路径。不能仅省略 KHR shader execution mode 后遍历仍带 OMM 的 AS；该路径行为未定义，旧 opaque/transparent 分类也不能靠后续 alpha test 补救。[SPEC]

烘焙 key 至少含 mesh/index/UV/alpha texture/cutoff/材质表达与版本。静态 alpha-mask 适合研究；alpha/UV/拓扑改变使 key 失效，须重建或回退。unknown-opacity 必须走对应 query/material 判定，不能一律当透明，OMM 不是通用半透明混合/折射算法。baker 来源、许可与输入 hash 保留，不打包厂商引擎分支。[ENGINE]

对照固定内容、ray 工作负载、构建偏好和质量；分别统计 OMM 构建、内存、query 与更新成本。无设备时状态 UNSUPPORTED/UNVERIFIED，不外推 Arm Mali G2 的公开数字。[VENDOR][ENGINE]

依据：[Query traversal](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/raytraversal.adoc)、[KHR OMM](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_KHR_opacity_micromap.adoc)、[EXT OMM](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/appendices/VK_EXT_opacity_micromap.adoc)。精简实验与真实编译/GPU结果存 tests 仓；CPU 状态机不是 AS GPU 执行。


<a id="gaussian-preproject-sort"></a>
## Gaussian 数据、投影与排序合同（C3）

适用原生 Vulkan raster 3DGS 与 mesh 混合；训练/4D重建不是本链职责。复用 GPU Scene、资源驻留、排序与 instance/indirect 管理，不默认全 Compute、Mesh Shader、RT、interlock 或独立 compute queue。输入 profile、资源 hash/许可、view/instance transform/time/generation；输出可见列表、投影椭圆、排序键、稳定 ID 与诊断。[ENGINE]

### 导入 profile 必须明确

| 字段 | 必须验证/规范化 |
|---|---|
| position | 有限 xyz、坐标轴/手性、世界单位、局部或世界空间 |
| scale/covariance | 线性或 log scale；covariance 表示与有效性；指数溢出/非有限拒绝 |
| rotation | quaternion 的 xyzw/wxyz 与旋转方向；有限、非零范数后归一化 |
| opacity | 已归一化概率或 logit；显式稳定 sigmoid，仅转换一次；范围检查 |
| SH/color | degree、系数排列/基底、DC offset/scale、view direction 空间、线性或编码颜色 |
| stable ID | (setID,localID,generation)，不以临时 compact/sort 索引作持久身份 |

PLY 只是容器，字段同名不保证语义。最低自有合成 profile 可声明 xyz 世界单位、scale_x/y/z 为正线性标准差、qx/qy/qz/qw 为 xyzw、opacity 为[0,1]、red/green/blue 为线性浮点 RGB（SH degree 0、直接颜色，不套训练 SH DC 公式）。解析 header 类型/endianness/计数、字节长度、索引容量；未知 profile 拒绝或显式要求转换，不猜测 log/logit/SH。另一个训练导出 profile 必须逐项写转换，不能沿用这个例子。SPZ/glTF/4D 只作条件适配。训练 radiance 通常已含光照，没有可靠 normal/BRDF 不重复加 PBR 或承诺物理重照明。

### 投影和绘制

验证→规范化→上传/驻留→视空间深度/covariance→投影 ellipse→保守可见列表/keys→稳定排序→instanced quad raster blend→mesh/背景合成→诊断/退休。小规模 CPU 排序是正确性和缺功能回退，不保证大规模更快。[ENGINE]

正 scale 与归一化 rotation 可构造 `Sigma=R diag(s²) Rᵀ`，经实例线性变换 A 后 `A Sigma Aᵀ`，再到 view。选择正定或允许半正定的 profile 并验证有限性/对称性/eigenvalue；退化不能盲目求逆。透视局部近似 `Sigma2=J Sigma_view Jᵀ`，J 是当前相机实际投影 Jacobian，含 viewport 缩放/Y方向；条件不良时拒绝/受控正则化并计数，不传播 NaN。fragment 以相应 inverse conic 计算 Gaussian 权重和 opacity，按 [合成合同](../../02_core_mental_model/render_target_model.md#transparent-composition-contract) 输出预乘线性色。

near-plane/极小 z/跨 near 的大 covariance 不适合无条件中心 Jacobian；采用明确保守 clipping/特殊投影路径或拒绝该质量档并诊断。不能只因中心在屏外剔除仍覆盖屏内的 ellipse，也不能任意缩小全部 splats。有限 sigma 截断与 alpha cutoff 是质量选择；计算 bbox 后裁到 viewport，检查尺寸/整数乘法/分配上限。截断、近裁面策略和超大点预算应冻结后用极端视点验证。

屏幕 covariance 加 AA filter 时，opacity 补偿需配对验证，例如在选定二维 Gaussian 积分模型下用 sqrt(det(old)/det(new)) 保持积分；它不是所有截断/采样器的普适保证。分别记录 projected-size buckets、clipped quad area、ellipse area、tile coverage，不能互换或当硬件 fragment invocations。[REF][ENGINE]

### 顺序、身份与复用

默认按声明的 view-space 深度 back-to-front，与相同深度稳定 ID tie-break；多集合一起排序或使用明确近似算法，逐 set 独立画完通常无法解决跨集合交错。Gaussian 中心深度只近似连续密度次序。mesh opaque depth 可测试遮挡，但中心/阈值 depth proxy 不等于不透明硬表面，不能用任意 splat depth 写成 opaque Hi-Z 挡住透射内容。

| 状态变化 | 缓存处理 |
|---|---|
| camera/view/projection/viewport | 重算受影响投影/可见列表；排序键变化则重排 |
| instance transform、动画时间、Gaussian position/covariance/opacity | 检查投影、可见性和顺序相关字段；动态场景不能因相机不动就复用 |
| LOD/residency/visible set/index construction | 使相关列表/ID映射/keys失效 |
| resource/set generation、第二View、独立实例 | key逐View/instance/generation绑定；旧异步结果不发布到新代 |
| 完整输入与顺序证明均不变 | 可复用；误差容忍复用另列阈值/失效证书，不固定N帧无条件跳排 |

颜色混合与 picked ID/material/depth proxy 必须声明一致的选择策略，例如选“最靠前且 alpha 超阈值的贡献者”并用其完整 tuple 查询对应材质/深度；不要声称混合色只属于一个物体。用专门可验证的 selection pass/存储算法实现，整数 attachment 没有自动 alpha blend 选择语义。多集合局部 ID 必须映射成全局身份，资源卸载/重载防止旧 ID 指向新数据。

同步另读 [消费者依赖](compute_to_graphics_sync.md#gaussian-consumer-dependencies)，全部 scratch/list/属性/绘制/pick 消费完成才复用/退休。单 Surface 销毁只废弃其 view/history/sort，不能无证据重建共享 device。

验证原创合成数据及显式 PLY profile、未知编码拒绝、非有限/非正尺度、near-plane/屏外中心但屏内 footprint、多集合交错材质/ID、相机静止而点移动、第二View变化、generation重载与容量超限。颜色/透射误差和移动相机 pop 一起测，不以单帧截图或 CPU oracle 当 Vulkan 运行。

[REF] [Rasterization deep dive](https://nvpro-samples.github.io/vk_gaussian_splatting/deep-dives/rasterization_of_3d_gaussian_splatting/)、[NVIDIA 2026.2.9](https://github.com/nvpro-samples/vk_gaussian_splatting/blob/2026.2.9/README.md)、[Mobile-4DGS paper](https://arxiv.org/abs/2610.05289)。桌面 Vulkan / 移动 WebGL 的算法证据不证明 Android Vulkan 后端；Mobile-4DGS 排序复用前提不能泛化到任意 PLY。

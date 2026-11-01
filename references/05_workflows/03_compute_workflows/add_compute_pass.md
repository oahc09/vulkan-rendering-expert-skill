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

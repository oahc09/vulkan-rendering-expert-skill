# Workflow: Optimize Frame Time

## 0. 适用范围

### 适用

- 需要降低单帧总耗时（CPU + GPU），提升 frame rate。
- 需要定位 CPU/GPU 瓶颈并针对性优化。
- 需要优化 draw call、pipeline state 切换、barrier、bandwidth、shader 开销。
- 目标平台包括 Android（移动 GPU）与桌面端。

### 不适用

- 渲染正确性尚未保证的工程（先解决 validation / sync）。
- 纯 compute / headless 无 graphics frame 的场景（部分 CPU/GPU 同步思路可参考）。
- 完全受显示器刷新率限制且已稳定 v-sync 的情况（优化空间在 latency 而非 frame time）。

---

## 1. 任务目标

降低并稳定 frame time：

```text
CPU Record + Submit
→ GPU Execution
→ Present
→ Analyze Bottleneck
→ Optimize (draws/state/barrier/bandwidth/shader)
→ Repeat
```

---

## 2. 输入条件

需要确认：

- 目标平台：Android / Windows / Linux。
- 目标 frame rate 与 frame time 预算（如 60 FPS → 16.67 ms）。
- 当前 CPU/GPU frame time 基线。
- GPU 架构：IMR（NVIDIA/AMD）或 TBDR（Adreno/Mali/PowerVR）。
- 当前 draw call 数量、pass 数量、barrier 数量、fullscreen pass 数量。
- 是否使用 instancing、indirect draw、multi-draw。
- AGI / RenderDoc / Snapdragon Profiler / Nsight / PIX 是否可用。

---

## 3. 前置检查

- [ ] Validation Layer clean（优化前确保无错误）。
- [ ] 已确定可用的 profiler / trace / timestamp / 日志；能力缺失明确标注，不编造 counter。
- [ ] 已记录基线 frame time、CPU time、GPU time、present time。
- [ ] 已确认 bottleneck 在 CPU 还是 GPU。
- [ ] 已确认 swapchain 当前 present mode（FIFO / MAILBOX / IMMEDIATE）。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
CPU Record
→ VkCommandBuffer (primary/secondary)
→ vkQueueSubmit (fence/semaphore)
→ GPU Vertex/Fragment/Compute Stages
→ VkSwapchainKHR → vkQueuePresentKHR
→ Frame Time = max(CPU, GPU) + synchronization overhead
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| command buffer | `VkCommandBuffer` | 录制命令 | per-frame | 否 |
| command pool | `VkCommandPool` | 分配 command buffer | per-frame | 否 |
| query pool | `VkQueryPool` | timestamp / pipeline statistics | per-frame / global | 否 |
| per-frame UBO | `VkBuffer` | 每帧常量 | per-frame | 否 |
| indirect buffer | `VkBuffer` | multi-draw / draw indirect | scene | 否 |
| merged vertex/index buffer | `VkBuffer` | 减少 bind 调用 | scene | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER_DYNAMIC` | per-frame / per-view constants | Vertex / Fragment / Compute |
| set=1,binding=0 | `STORAGE_BUFFER` | instance data / draw commands | Vertex / Compute |
| set=2,binding=0..N | `COMBINED_IMAGE_SAMPLER` | material textures | Fragment |
| push constant | `VkPushConstantRange` | per-draw params | Vertex / Fragment |

Pipeline 状态：

- 减少 pipeline 切换：按 state 排序 draw calls（depth / blend / cull / shader），合并使用相同 pipeline 的物体 [HEUR]。
- 使用 dynamic state（`VK_DYNAMIC_STATE_VIEWPORT`、`SCISSOR` 等）减少 pipeline 数量 [SPEC]。
- 对材质变体很多的场景，使用 specialization constants 替代宏 shader，减少 pipeline 数量 [HEUR]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU record | command buffer | `vkEndCommandBuffer` | queue submit |
| queue submit | fence | `vkQueueSubmit` | CPU `vkWaitForFences` |
| previous GPU pass | color/depth image | pipeline barrier / subpass dependency | next pass |
| compute dispatch | SSBO / image | memory barrier | graphics consume |
| acquire semaphore | swapchain image | `COLOR_ATTACHMENT_OUTPUT_BIT` wait | render begin |

必须说明：

- 同步应精确到所需 stage 和 access，避免 `TOP_OF_PIPE` / `BOTTOM_OF_PIPE` 过度同步 [SPEC]。
- 使用 `VK_ACCESS_MEMORY_READ_BIT/WRITE_BIT` 全量 barrier 会引入不必要的 stall，应使用具体 access flag [HEUR]。
- TBDR GPU 上尽量减少 image layout 跳转与显式 barrier，利用 subpass dependency 将数据保留在 tile memory [ANDROID]。
- CPU/GPU 分帧：若 CPU > GPU，优化 record 线程、使用 secondary command buffer / multi-threading；若 GPU > CPU，优化 shader、draw call、bandwidth [HEUR]。

---

## 7.5 架构决策（Architecture Decision）

> 进入 §8 实现步骤前先完成本节决策链。决策方法与六要素见 `../../02_core_mental_model/engine_architecture.md` §10。

决策链：

```text
需求 → 约束 → Candidate Architecture → Trade-off → Decision
```

| 阶段 | 本 workflow 的关键决策问题 | 参考 |
|---|---|---|
| 需求 | 降低并稳定 frame time（§1）；架构上先定优化投入的层级：局部优化还是架构级重排，async compute 在本场景是否有收益 [ENGINE] | — |
| 约束 | §8 步骤 1-2 的瓶颈定位结论（CPU record / GPU active / fence 等待）、帧预算与 99th percentile 要求（§10）、GPU 架构（IMR / TBDR，§2）、平台、可接受的改动风险窗口（架构级改动需重跑 §10 全套验证） | — |
| Candidate | A：局部优化——draw call 合并、barrier 精确化、pass 合并、format / bandwidth 调整（§8 步骤 3-9 主路径）；B：架构级重排——pass 结构 / 渲染顺序 / 资源生命周期重组，不换技术栈；C：引入 async compute queue——把与 graphics 互补的 compute 负载 overlap | D4 |
| Trade-off | A 风险低、可增量验证，但不改结构收益有上限；B 一次投入大、需重跑全套 §10 验证，pass 重排引发手写 barrier 重写时与 D5 的托管边界耦合；C 的 overlap 收益上限为串行路径中 compute 段时长，同步开销（ownership transfer + timeline）可能反噬，移动端部分驱动多 queue 退化（D4）[ANDROID][VENDOR]；async compute 不是默认优化手段——AGI 显示 graphics 与 compute 互不重叠且合计 >30% frame time 才值得评估（D4 重新评估条件） | D4/D5 |
| Decision | 写明：当前瓶颈归属层级的测量证据、为什么先做该级以及"为什么不选另一边"；若不引入 async compute，写明理由（overlap 余量不足 / 驱动退化 / 同步开销大于收益）。重新评估条件：局部优化后 frame time 仍超预算且手写 barrier 蔓延 → 重开 D5；AGI 出现 overlap 信号 → 重开 D4；选 C 后 frame time 反升或 timeline 空泡 → 回退（保留代码路径，先关开关） | — |

决策规则：

- 不默认选择新技术方案；每个 Decision 必须写明"为什么不选另一边"。
- Decision 必须包含重新评估条件（什么信号出现时重开决策）。
- 决策完成后进入 §8；验证仍走 §10 验证方式与 Verification Gate（`../../00_expert_entry/verification_gate.md`）。

---

## 8. 实现步骤

1. **测量基线**：
   - CPU：record 时间、`vkQueueSubmit` 耗时、`vkWaitForFences` 等待时间；
   - GPU：vertex / raster / fragment / compute active time；
   - Present：CPU 等待 present 的时间、swapchain latency [TOOL]。
2. **定位瓶颈**：
   - 若 CPU record 长 → 优化 draw call 数量、command buffer 录制效率；
   - 若 GPU active 长 → 优化 shader、bandwidth、overdraw；
   - 若 CPU 等待 GPU fence 长 → 检查 GPU工作、提交时序与呈现节奏，不能单凭等待归因 GPU bound；
   - 若 GPU 等待 CPU submit → CPU bound，优化 record / submit [HEUR]。
3. **减少 draw call**：
   - 静态 batching、dynamic batching、instancing（`vkCmdDrawIndexedIndirect` / `vkCmdDrawIndexedIndirectCount`）[HEUR]；
   - 合并材质与 mesh，减少 per-draw descriptor bind 和 pipeline bind [HEUR]。
4. **优化 pipeline state 切换**：
   - 按 pipeline / material / depth 排序 render queue；
   - 使用 dynamic state 减少 pipeline 变体；
   - 对 opaque 物体 front-to-back 渲染，减少 overdraw [HEUR]。
5. **优化 barrier**：
   - 用 subpass dependency 替代显式 barrier（TBDR 上尤其重要）[ANDROID]；
   - barrier 范围精确到 image subresource range，避免全 image barrier [SPEC]；
   - 合并相邻 barrier 到同一个 `vkCmdPipelineBarrier` 调用 [HEUR]。
6. **优化 bandwidth**：
   - 降低 attachment format bit depth；
   - 使用 transient MSAA；
   - 压缩纹理；
   - 减少 fullscreen pass 数量（详见 `optimize_mobile_bandwidth.md`）[ANDROID]。
7. **优化 shader**：
   - 用 Mali Offline Compiler / Nsight 分析 arithmetic / texture / register pressure；
   - 减少 branch divergence、texture sample 次数、复杂数学函数 [HEUR]。
8. **CPU 多线程录制**：
   - 使用 secondary command buffer 多线程录制，主线程只 execute；
   - 注意 secondary buffer 的 inheritance info 与 state consistency [SPEC]。
9. **优化 submit**：
   - 合并每帧多次 submit 为一次（除非需要 CPU/GPU 交错）；
   - 减少 semaphore 数量，避免 unnecessary signal/wait [HEUR]。
10. **接入 resize / recreate**：
    - recreate 后重新评估 resolution scale、MSAA、format 选择；
    - 保证新 extent 下 frame time 仍满足预算 [ANDROID]。
11. **验证优化效果**：
    - 对比优化前后 CPU/GPU frame time、draw call、barrier、bandwidth [TOOL]。

---

## 9. Android 注意点

- `ANativeWindow` / surface 创建后才能确定真实渲染分辨率与刷新率；target frame time 与 optimization budget 必须基于实际 surface extent 计算 [ANDROID]。
- rotation / resize 改变 extent 后，overdraw、bandwidth、fragment shader 开销都会变化；需动态调整 resolution scale、LOD、MSAA [ANDROID]。
- `extent.width == 0 || extent.height == 0` 时暂停渲染循环，避免 CPU 空转 submit [ANDROID]。
- TBDR GPU 上，barrier 与 layout transition 会导致 tile memory flush 到 system memory，显著增加 frame time；优先使用 subpass dependency 与 `BY_REGION_BIT` [ANDROID]。
- 移动端 CPU 核数与性能差异大，避免在 render thread 做 heavy work；使用 worker thread 录制 secondary command buffer [ANDROID]。
- AGI / logcat 验证：关注 `GPU Frame Time`、`CPU Frame Time`、`External Memory Bandwidth`、`Fragment Shaded Count`。

---

## 10. 验证方式

- [ ] Validation Layer clean：优化后无新增 validation error [TOOL]。
- [ ] RenderDoc / AGI / Nsight / PIX：
  - 优化前后 CPU/GPU frame time 对比；
  - draw call 数量、pipeline state 切换次数；
  - barrier / layout transition 数量与位置；
  - bandwidth / overdraw / occupancy 指标 [TOOL]。
- [ ] 截图 / 画质评估：优化后画面正确，无 artifact。
- [ ] logcat（Android）：无 validation error；可输出 CPU record time、GPU frame time、draw call count、barrier count。
- [ ] 性能指标：
  - frame time 下降到目标预算内；
  - CPU/GPU 分帧均衡，无一方长时间等待；
  - 99th percentile frame time 稳定；
  - 无 redundant pipeline bind / barrier / layout transition [HEUR]。
- [ ] resize / pause / resume / rotation 后性能优化策略仍生效。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或掉帧。

---

## 11. 常见失败模式

1. **未定位瓶颈就优化**：在 CPU bound 时优化 shader，或在 GPU bound 时优化 draw call 排序，收益低 [HEUR]。
2. **过度同步**：滥用 `vkDeviceWaitIdle` 或全量 memory barrier，导致 CPU/GPU 串行 [TOOL]。
3. **忽略 TBDR 特性**：在 Adreno/Mali 上使用大量显式 barrier 与 layout transition，tile memory 反复 flush [ANDROID]。
4. **draw call 合并过度**：batch 过大导致 culling 粒度粗，增加 overdraw [HEUR]。
5. **dynamic state 使用不当**：频繁修改 viewport/scissor 仍导致 state 变动，收益有限 [HEUR]。
6. **未考虑 present mode**：FIFO 下 frame time 受显示器刷新率限制，无法突破；需要降低 latency 时应考虑 MAILBOX / IMMEDIATE（需防 tearing）[SPEC]。
7. **Android rotation 后未重调 budget**：新 extent 下仍用旧 resolution scale 导致掉帧 [ANDROID]。
8. **secondary command buffer 状态泄漏**：inheritance 设置错误导致 dynamic state / render pass 状态不一致 [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / GPU 型号 / Vulkan 版本。
- 当前 CPU/GPU frame time 拆分。
- AGI / Profiler 抓帧数据（draw call、barrier、bandwidth、shader occupancy）。
- Present mode 与 v-sync 设置。
- Render pass / subpass 结构。
- 当前 batching / instancing 策略。
- Android lifecycle 日志。


<a id="sustained-mobile-performance"></a>
## 15. 持续移动性能、热状态与帧节奏

短测更快不等于持续体验改善。固定设备/driver、场景、分辨率、画质、刷新率、运行时长、供电与初始热状态，
先区分 CPU调度、GPU工作、呈现等待与热降频，再决定 shader / pass / pacing / 动态质量改动。[ENGINE]

| 指标 | 口径与边界 |
|---|---|
| 游戏逻辑帧 / 真实渲染帧 | 分别记录 CPU/GPU工作和输入采样；不能用插值帧补足逻辑更新率 |
| 生成帧 / 最终呈现帧 | 单列生成比例、重复帧及missed-vsync；displayed FPS提高不能证明输入延迟、画质或功耗改善 |
| 帧耗时 | 同条件报告 P50/P95/P99、CPU/GPU时间、首用卡顿和峰值内存；无timestamp能力标未知 |
| 热状态与持续表现 | 可选15–20分钟负载，尊重系统热保护；预先规定过热/错误/用户中止条件，不绕开限温 |
| 带宽/功耗/输入到显示延迟 | 仅报告可靠工具实际采集结果、单位与方法；不可从FPS猜测 |

ADPF 是既有热状态/性能交互能力，Swappy 是既有帧节奏库，不是2026-10新发布特性。
按目标支持和已有引擎接口评估，不强加依赖。指定唯一的 pacing / present owner：引擎、Swappy或SDK
swapchain包装层谁负责等待/呈现须写清，不能未经验证叠加多个管理层。[ANDROID][ENGINE]

A/B保持视觉标准与输入一致，分别记录工具开启的诊断运行和关闭高开销检测的性能运行。
若插帧提高呈现FPS却增加交互延迟，应报告权衡并允许关闭插帧、保留真实渲染/传统缩放路径。
工具不足时先给最小采集方案，不声称已经优化。

来源：[ADPF](https://developer.android.com/games/optimize/adpf)、
[Frame Pacing / Swappy](https://developer.android.com/games/sdk/frame-pacing)。

<a id="scaled-rendering-ab"></a>
### scaled-rendering-ab

规模实验固定 seed、视角、物体1k/10k/100k、目标可见率10/50/100%、分辨率、材质、灯光和 resident LOD；记录实际可见率，不把配置值假称结果。CPU参考必须包含合理 instancing/batching。比较 CPU参考 → GPU固定槽 → compact+Count，再分别切 LOD、当前帧Hi-Z、粒子与多 view；禁止一次改完后把差异都归因 GPU-driven。[ENGINE]

记录 CPU update/cull/record/submit、GPU reset+cull+compact+Hi-Z+draw 与全帧时间、VRAM/host/staging/old-new峰值、upload bytes、overflow/fallback 和可见ID/图像一致性。GPU query 先验证 queue timestampValidBits、timestampPeriod、availability/完成与 wrap；不支持则明确缺失，不用 CPU wall time 冒充 GPU 时间。排除 warmup、报告样本数/分位数/误差和测量开销。[ENGINE]

软件 Vulkan 的 source/build/validation/图像结果，与真实 Android MobileScale 的 GPU型号/driver/API/features、热状态、功耗/带宽、分辨率、持续时长分别报告。桌面或 llvmpipe 不证明移动端60FPS。没有授权设备则 MobileScale BLOCKED，保留可运行命令和所缺证据；不得填入估算成绩。mesh/task、Binary/GPL、async queue、前帧Hi-Z 为独立条件路径；未支持或未测不算通过。[ENGINE]

<a id="quality-budget-tiers"></a>
## 画质预算与持续分档

沿用 [持续热性能](#sustained-mobile-performance)。Baseline/Hybrid/Enhanced 选择见 [架构决策](../../02_core_mental_model/engine_architecture.md#hybrid-lighting-decisions)。分别计 CPU、AS build/update/compact、query、filter、带宽和新旧驻留峰值；降采样/降低更新频率/减少 ray 范围是明确质量取舍，不悄悄删除投影者。[ENGINE]

降档由预设阈值、优先级、滞回和冷却期决定，恢复需连续稳定窗口。新代资源准备好再切换，失效 history 重置，旧代延迟退休；不要温度一变就重建 Device 或反复开关所有效果。

A/B 预注册 scene seed、camera/light/animation 轨迹、分辨率/render scale、质量、driver/tool、预热、采样窗口及可比热状态。冷创建/稳态/压力恢复分别报告；保存输入/产物/输出 hash 与最终 Skill/tests SHA。[ENGINE]

至少记录 frame/pass median 与 P95/P99、AS/trace/filter 成本、内存峰值、native-rendered/generated/presented frames 和可取得的真实延迟。ROI 覆盖阴影边缘、薄片、反射轮廓、disocclusion、运动/高亮，HDR 在固定域/容差比较。PSNR/SSIM 不替代时序观察或物理正确；看完结果不改阈值。[TOOL]

必须拒绝悬垂 AS、非法 query-only stage、过期 history 和缺投影者，即使平均 FPS 更高。温度/FPS 不能换算节电比例；没有可靠能量测量来源就不报功耗收益，桌面或软件 Vulkan 不等于 Android 性能。原12题 token 30% 是独立冻结指标，VIS14 无新30%目标。

<a id="simulation-cost-quality-budget"></a>
## 仿真成本、质量与移动预算（C4）

输入：固定算法/输入轨迹、h/substeps/iterations、colors或gather策略、规模/碰撞器、输出质量、设备driver/features、热状态与采样窗口。输出：数值误差、分项/全帧成本、内存、回退及各验证层状态；不能只给FPS或粒子数量。[ENGINE]

分别记录积分/constraint、normal/bounds、事件处理、上传/回读、同步等待、可选AS、draw和全帧；同时记录substeps × iterations × colors/dispatches与scratch/snapshot新旧驻留峰值。Jacobi贡献/邻接带宽和color串行dispatch成本独立测量；增加substeps不能由CPU等待延迟直接驱动。

GPU timestamp按实际queue的timestampValidBits、设备timestampPeriod、timestampComputeAndGraphics及命令约束核查；合法时用VkQueryPool与vkCmdWriteTimestamp2或legacy入口，异步获取availability/结果，处理有效位wrap与query slot退休，不用每帧WAIT阻塞制造“GPU时间”。CPU fence等待wall time含排队/调度，不是纯kernel耗时；缺timestamp就明确未知，读 [query卡](../../03_api_manual/04_buffer_image_memory/query_pool.md)。[SPEC]

质量档先降低链/网格规模、碰撞器复杂度、独立增强或非必要输出频率；不省略正确性依赖，不把dt/substeps降到已知不稳定范围。改h需复验XPBD α/h²、damping、固定点速度、impulse和高度场稳定界；规模变化还要更新dx/dy、代际、normal/bounds/history。采用预设阈值、滞回、恢复窗口和显式回退，输出数值质量与视觉差异。[ENGINE]

A/B顺序：同算法CPU小oracle→软件/桌面Vulkan正确性→目标手机基线→单项优化→持续负载。预注册模型单位误差/残差/穿透、图像序列、P50/P95/P99、样本量、预热/测量开销、热中止条件；保持场景、步长、solver/collider/视觉负载一致，不在看到结果后改容差。Adreno/Mali分别记录型号、OS/API、driver、features、workgroup/subgroup、格式、APK/Shader hash、温度与时长；软件Vulkan不代表Android性能，没能量测量不报功耗收益。

分层验收：Static/Host合同、Numerical Host、Shader编译/SPIR-V、真实Vulkan dispatch/draw/readback、Live/宿主、Android持续质量分开。缺设备、能力或授权标BLOCKED/UNSUPPORTED/UNVERIFIED；可选atomic/FP16/async/软体不测就不算通过。文档完成不等于移动仿真完整验收，SIM16独立计量不新增原12题token目标。关联hard_rules 8/10/17与G1–G6；[持续性能](#sustained-mobile-performance) 继续适用。

来源：[规范查询与timestamp](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/queries.adoc)、[Small Steps精度限制](https://matthias-research.github.io/pages/publications/smallsteps.pdf)、[Arm shader profiling](https://support.arm.com/documentation/102693/2026-5/Analyze-your-frames/Analyze-shader-programs)。社区复盘中的等待时间/性能数字只能提出测量假设，不替代目标设备数据。

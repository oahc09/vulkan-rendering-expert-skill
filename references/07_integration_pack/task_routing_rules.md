# Task Routing Rules

<a id="routing-entry"></a>
## 0. 唯一路由入口

这是任务类型、症状直达、首轮资料选择的唯一权威。其他文件只提供分类例子、检索协议或输出格式，不新增平行路由。启动只读本节（到下一个锚点前），然后读取命中锚点；下文“使用模块”表示可选资料范围，不表示整模块必读。

| 类型 / 意图 | 本文件段落 | 输出模板锚点（response_formats.md） |
|---|---|---|
| 概念 + 对象链路 | #route-concept | #format-concept |
| API / 字段 / VUID | #route-api | #format-api |
| 黑屏 / 闪烁 / 花屏 / 崩溃 / hang / Validation / 无输出 | #route-debug，再查 #symptom-shortcuts | #format-debug |
| 正向实现 / 迁移 / 新增 pass | #route-implementation，再查 #symptom-shortcuts | #format-implementation |
| 帧耗时 / 卡顿 / 带宽 / CPU 开销 | #route-performance，再查 #symptom-shortcuts | #format-performance |
| 架构设计 / 技术选型 | #route-architecture | #format-architecture |
| 案例 / 复盘 | #route-case | #format-case |
| Android Surface / Swapchain / 生命周期 | #route-android | #format-android |
| 真实仓库 / 升级 / 源码影响面 | #route-project（叠加任何主类型） | #format-project |
| 简短回答 | #route-compact（保留主类型约束） | #format-compact |
| 第三方库 / Vulkan backend / 模型加载 / PBR | #route-third-party | 主类型模板 |

跨类型先按 `../00_expert_entry/progressive_retrieval.md#r1-decompose` 分解再逐项路由；不可拆分时主类型优先级：调试 > 性能 > Android > 项目诊断 > 正向开发 > 架构 > API > 案例 > 概念 > 简短。第三方集成是叠加规则，真实仓库约束也不得被主类型覆盖。

必读条件：调试加载 `../00_expert_entry/debug_priority.md`；性能加载 `../00_expert_entry/performance_priority.md`；第三方 API 加载 `../00_expert_entry/accuracy_check.md#third-party-api`；引用来源 / API 合法性读取该文件 #accuracy-requirements。复杂 / 信息不足 / 低置信进入 progressive_retrieval 的 R1-R5；简单信息完整任务单轮路由即可。

回答前只读 `../00_expert_entry/response_formats.md` 命中模板；结论性判断或修改方案还读本文件 #route-verification，按其要求执行 G1-G6。详细段落读取与预算见 `retrieval_policy.md#section-read-contract`。


<a id="route-concept"></a>
## 1. 概念+链路类

首轮读取：`../02_core_mental_model/` 中与对象相关的文件，必要时 1 张 API 卡。

用户问：Vulkan / Descriptor / Pipeline / Barrier / Swapchain 是什么？某个概念如何工作？

> 注意：概念解释仍需遵守 `00_expert_entry/hard_rules.md` 第 11 条——不能只输出概念解释，必须附带可执行的 Vulkan 对象链路、API 调用、资源变更和验证路径。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. 必要时引用 `03_api_manual`

不使用：

- `04_debug_playbooks`
- `05_workflows`
- `06_cases`

<a id="route-api"></a>
## 2. API 细节类

首轮读取：`../01_source_map_and_api_manual_strategy/source_tags.md` 与 `../03_api_manual/api_index.md`，再读匹配 API 卡。

用户问：`vkCreateImage`、`VkDescriptorSetLayoutBinding`、`vkCmdPipelineBarrier2`、`VkSwapchainCreateInfoKHR` 等 API 或字段。

使用模块：

1. `00_expert_entry`
2. `01_source_map_and_api_manual_strategy`
3. `02_core_mental_model`
4. `03_api_manual`

<a id="route-debug"></a>
## 3. 故障调试类

首轮读取：先查 #symptom-shortcuts；未命中读 `../04_debug_playbooks/debug_priority_index.md`，再读 1 个 playbook。

用户问：黑屏、Validation Error、Android 横竖屏 crash、compute 没输出、texture 黑、GPU hang、device lost。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `04_debug_playbooks`
4. 必要时引用 `03_api_manual`
5. 必要时引用 `06_cases`

<a id="route-implementation"></a>
## 4. 正向开发类

首轮读取：先查 #symptom-shortcuts；未命中读 `../05_workflows/workflow_index.md`，再读 1 个 workflow。

用户问：新增 fullscreen pass、compute pass、SurfaceView 接入、swapchain recreate、offscreen pass、后处理优化、OpenGL / Shadertoy 迁移。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows`
4. 必要时引用 `03_api_manual`
5. 必要时引用 `04_debug_playbooks`

<a id="route-performance"></a>
## 5. 性能优化类

首轮读取：先查 #symptom-shortcuts，读取匹配性能 playbook / 优化 workflow；案例只在需要经验支持时加载。

用户问：GPU frame time 高、fullscreen pass 很重、bandwidth 高、移动端发热、descriptor 更新开销高、barrier 是否过重。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows`
4. `04_debug_playbooks`
5. `06_cases`
6. 必要时引用 `03_api_manual`

<a id="route-architecture"></a>
## 6. 架构设计类

首轮读取：`../02_core_mental_model/engine_architecture.md` 的子系统模型与 §10 决策框架。

用户问：Render Graph、RHI 抽象、Resource Lifetime、Pipeline Cache、Frames-in-flight、Descriptor 管理策略。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`（首站 `../02_core_mental_model/engine_architecture.md`）
3. `05_workflows`（如涉及具体实现）
4. `06_cases`（如需要参考真实案例）
5. 必要时引用 `03_api_manual`

<a id="route-case"></a>
## 7. 经验案例类

首轮读取：`../06_cases/case_index.md`，再读匹配案例段。

用户问：有没有类似案例、为什么容易误判、真实工程怎么踩坑。

使用模块：

1. `00_expert_entry`
2. `06_cases`
3. 必要时引用 `04_debug_playbooks`
4. 必要时引用 `03_api_manual`

<a id="route-android"></a>
## 8. Android 专项类

首轮读取：`../02_core_mental_model/android_surface_swapchain_lifecycle.md`，按故障 / 实现选择 Android playbook / workflow；案例按需。

用户问：SurfaceView 接 Vulkan、`ANativeWindow` 生命周期、pause/resume、rotation crash、Surface destroyed 后 present crash。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows/04_android_integration`
4. `04_debug_playbooks/05_android_specific`
5. `06_cases/04_swapchain_android`
6. 必要时引用 `03_api_manual/02_surface_swapchain` 与 `03_api_manual/08_synchronization` 相关卡片

<a id="route-project"></a>
## 9. 项目诊断类

首轮读取：`../05_workflows/01_renderer_setup/project_diagnosis.md`，先建立 Evidence Map + Architecture Map。

用户提供真实 Vulkan / 图形引擎仓库，要求理解当前架构、评估版本升级 / 重构影响面、把 Debug Playbook 映射到源码，或生成 coding-agent 实施计划。

使用模块：

1. `00_expert_entry`
2. `05_workflows/01_renderer_setup/project_diagnosis.md`
3. `02_core_mental_model/engine_architecture.md`
4. `02_core_mental_model/regression_reasoning.md`
5. 按具体子问题补载 playbook / API card / case

处理规则：

1. 先建立 `[CODE]` Evidence Map，再建立 Architecture Map；不根据文件名 / 类名猜项目事实。
2. 修改影响面分为 Must Change / Should Change / Can Defer / Do Not Change。
3. Debug 任务必须把通用假设映射到具体文件 / 类 / 函数。
4. 实现任务输出 Files To Modify、Dependency Order、Rollback、Definition of Done。
5. `[CODE]` 不能覆盖 `[SPEC]`；冲突时报告实现风险。

<a id="route-compact"></a>
## 10. 简短回答类

用户明确要求简短、只要重点、问题较小时使用。

处理规则：

1. 先判断主类型（参考本文件前述 9 类）。
2. 使用该主类型的输出结构，但每节压缩为 bullet 或一句话。
3. 必须保留：结论、关键链路、最高优先级检查项、最小验证方式。

使用模块：与判断出的主类型一致。

<a id="route-third-party"></a>
## 11. 第三方库集成类

首轮读取：先核对库与 Vulkan 版本，再按主类型选 workflow / API 卡；移动神经SDK、QHWI/Filament和跨API互操作命中时先查 #mobile-topics；缺少专用 workflow 时使用相关 API 与 debug 检查项。

用户问：如何集成 ImGui / glfw / glm / tinygltf / stb / Assimp 等第三方库到 Vulkan 工程；ImGui + Vulkan backend 初始化、glTF 模型加载、PBR 渲染管线搭建。

使用模块：

1. `00_expert_entry`（含 `../00_expert_entry/accuracy_check.md` 的第三方库 API 准确性规则）
2. `02_core_mental_model`
3. `05_workflows`（按任务类型加载对应 workflow；若无对应文件，提示用户参考相关 API card 与 debug playbook）
4. 必要时引用 `03_api_manual`（如 `../03_api_manual/06_pipeline/graphics_pipeline.md`、`../03_api_manual/05_descriptor/descriptor_set.md`、`../05_workflows/05_resource_management/manage_resource_lifetime.md`）

处理规则：

1. **必须先核对版本**：引用第三方库 API 前必须按 `../00_expert_entry/accuracy_check.md` 的"Third-Party Library API Accuracy"规则标注版本号，超过 6 个月的版本必须回查最新稳定版 API 变更说明。
2. **Vulkan backend 双重标注**：若涉及第三方库的 Vulkan backend（如 `ImGui_ImplVulkan_*`），必须同时标注第三方库版本与适配的 Vulkan API 版本。
3. **API 版本变更点显式列出**：若某 API 在不同版本间存在签名 / 参数 / 行为变更，必须显式列出，避免用户使用过时签名。
4. **不确定时不编造**：若无法确认 API 签名的版本归属，明确说明并提示用户核对所用版本，**不允许编造 API 签名**。

<a id="route-verification"></a>
## 12. 统一出口：Verification Gate

适用于实际实现 / 修复 / 性能改善的完成声明；纯知识问答与未实施设计按 verification_gate.md §1 选择证据范围。

处理规则：

1. 给出最终结论（已完成 / 已解决 / 根因已修复 / 性能已优化）前，读取 `../00_expert_entry/verification_gate.md`，按 G1-G6 关卡检查。
2. 涉及代码 / 资源修改的任务，先读取 `../02_core_mental_model/regression_reasoning.md` 推导影响面，再给出方案。
3. 回归验证范围按 `../07_integration_pack/regression_checklist.md` 选择受影响类别执行。
4. 实际实现 / 修复 / 性能改善的结论附 G1-G6 状态（已验证 / 未验证 / 不适用）；纯知识问答不展开关卡表，设计审查给出验证计划。无法验证的适用关卡不得默认通过。
5. 修复类结论必须区分 Workaround（临时绕过）/ Minimal Fix（根因修复）/ Structural Fix（结构性修复），禁止把现象消失等同于根因修复。

<a id="symptom-shortcuts"></a>
## 症状 / 意图直达

命中直接读取对应文件，免读索引；未命中回到 #routing-entry 的主类型。以下迁自 v1.0.8 SKILL.md，原有入口全部保留。

| 症状 / 意图 | 直达文件 |
|---|---|
| 黑屏 | `../04_debug_playbooks/01_visual_issues/black_screen.md` |
| 闪烁 / 画面抖动 | `../04_debug_playbooks/01_visual_issues/flickering.md` |
| 深度错误 / 画面被裁 | `../04_debug_playbooks/01_visual_issues/depth_test_wrong.md` |
| 崩溃 / device lost | `../04_debug_playbooks/02_crash_hang/device_lost.md` |
| GPU hang / 卡死 | `../04_debug_playbooks/02_crash_hang/gpu_hang.md` |
| resize / 旋转后崩溃 | `../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md` |
| Validation Error / VUID 解码 | `../04_debug_playbooks/03_validation_errors/validation_error_decode.md` |
| descriptor / pipeline layout 报错 | `../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md` |
| image layout / sync hazard 报错 | `../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md` |
| 显存 / 内存泄漏 | `../04_debug_playbooks/03_validation_errors/memory_leak.md` |
| compute 无输出 | `../04_debug_playbooks/04_resource_sync/compute_no_output.md` |
| 仿真世界 / 时间单位 / 状态代际合同 | `../02_core_mental_model/compute_graphics_relationship.md#simulation-state-contract` |
| 仿真时钟 / 多view重复推进 / 输入脉冲 / 暂停追赶 | `../05_workflows/03_compute_workflows/add_compute_pass.md#simulation-scheduling` |
| XPBD / 绳索 / 布料 / λ / graph coloring / Jacobi gather | `../05_workflows/03_compute_workflows/compute_write_storage_buffer.md#xpbd-deformation-contract` |
| 高度场 / 涟漪 / 波动稳定性 / 雨滴事件 | `../05_workflows/03_compute_workflows/compute_write_storage_image.md#heightfield-simulation-contract` |
| 仿真kernel / 尾线程barrier / float atomic能力 | `../03_api_manual/06_pipeline/compute_pipeline.md#simulation-kernel-portability` |
| 动态几何 / 仿真snapshot / normal bounds history交接 | `../05_workflows/03_compute_workflows/compute_to_graphics_sync.md#simulation-render-handoff` |
| 仿真多消费者 / 快照提前复用 / 共享世界退休 | `../05_workflows/05_resource_management/manage_frame_resources.md#simulation-snapshot-retirement` |
| 仿真substep成本 / 移动数值质量预算 | `../05_workflows/07_optimization/optimize_frame_time.md#simulation-cost-quality-budget` |
| compute ↔ graphics 同步错误 | `../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md` |
| Android surface 生命周期 / 前后台切换 | `../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md` |
| GPU 帧耗时高 | `../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md` |
| 带宽 / 全屏 pass 成本高 | `../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md` |
| barrier / draw call stall | `../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md` |
| CPU 侧开销高 | `../04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md` |
| pipeline 创建卡顿 / 首帧卡顿 | `../04_debug_playbooks/06_performance_symptoms/pipeline_startup_stutter.md` |
| 从零搭建 renderer | `../05_workflows/01_renderer_setup/create_renderer_from_scratch.md` |
| 分析陌生 Vulkan 仓库 / 源码影响面 | `../05_workflows/01_renderer_setup/project_diagnosis.md` |
| 架构选型 / 迁移决策 | `../02_core_mental_model/engine_architecture.md`（§10 决策框架） |
| 查找相似案例 | `../06_cases/case_index.md` |
| Android CLI / APA / GPU counter不可用 | `../04_debug_playbooks/tool_usage.md#mobile-profiler-contract` |
| 持续掉帧 / 热状态 / 插帧FPS与延迟 | `../05_workflows/07_optimization/optimize_frame_time.md#sustained-mobile-performance` |
| fault地址 / 绑定代际 / EXT与KHR诊断 | `../04_debug_playbooks/02_crash_hang/device_lost.md#mobile-fault-evidence` |
| tile / local read / QCOM fast path | `../03_api_manual/07_rendering/mobile_tile_rendering.md#tile-capability-matrix` |
| external memory / AHB / opaque FD / sync FD | `../03_api_manual/04_buffer_image_memory/external_resource_interop.md#interop-capability-contract` |
| Vulkan/OpenCL 往返集成 | `../05_workflows/04_android_integration/vulkan_opencl_interop.md#interop-workflow` |
| NSS / NFRU / 神经SDK多Engine | `../05_workflows/02_render_pass_effects/mobile_neural_graphics.md#neural-capability-contract` |
| QHWI / Filament句柄材质 / SDK版本迁移 | `../06_cases/07_engine_architecture/case_engine_architecture.md#mobile-sdk-framework-contracts` |
| 多Engine / 预览关闭影响其他输出 / owner | `../02_core_mental_model/android_surface_swapchain_lifecycle.md#multi-instance-ownership` |
| 旧Surface回调 / 销毁确认 / shared device故障 | `../05_workflows/04_android_integration/handle_android_lifecycle.md#multi-surface-lifecycle` |
| Wallpaper / AppWidget / SurfaceView宿主接入 | `../05_workflows/04_android_integration/integrate_surfaceview_anativewindow.md#android-host-contract` |
| Android Surface有效访问/逐输出呈现支持 | `../03_api_manual/10_android_platform/android_surface.md#surface-host-boundaries` |
| Camera/MediaCodec AHB / 双消费者 / 帧归还 | `../03_api_manual/04_buffer_image_memory/external_resource_interop.md#android-media-frame-contract` |
| externalFormat / YCbCr媒体采样 | `../03_api_manual/05_descriptor/sampled_image_descriptor.md#android-media-ycbcr` |
| producer到采样/输入切换与背压 | `../05_workflows/02_render_pass_effects/add_texture_sampling_pass.md#android-media-sampling` |
| P3 / HDR / 输入工作输出颜色合同 | `../02_core_mental_model/render_target_model.md#color-output-contract` |
| 每Surface HDR feature / metadata / compositeAlpha | `../03_api_manual/02_surface_swapchain/swapchain.md#android-color-presentation` |
| tone mapping owner / 半透明黑边 / 输出转换 | `../05_workflows/02_render_pass_effects/add_postprocess_pass.md#color-output-workflow` |
| specialization / 变体爆炸 | `../03_api_manual/06_pipeline/specialization_constants.md#variant-cost-boundary` |
| Pipeline Binary条件路径 | `../03_api_manual/06_pipeline/pipeline_cache.md#pipeline-binary-path` |
| Shader manifest / SPIR-V / reflection / FP16 | `../03_api_manual/06_pipeline/shader_module.md#shader-artifact-contract` |
| Shader ABI / dynamic UBO / 热重载 | `../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md#shader-interface-validation` |
| 热重载代际 / 旧pipeline退休 | `../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md#shader-hot-reload` |
| Pipeline key / cache / Binary / GPL | `../03_api_manual/06_pipeline/pipeline_cache.md#cache-compatibility` |
| 异步pipeline编译/取消/发布 | `../05_workflows/07_optimization/reduce_pipeline_creation_stutter.md#pipeline-build-scheduler` |
| KTX2 / Basis / mip驻留 / 纹理流式 | `../05_workflows/05_resource_management/add_texture_resource.md#texture-streaming-residency` |
| Geometry streaming / LOD资源退休 | `../05_workflows/05_resource_management/manage_resource_lifetime.md#geometry-streaming-retirement` |
| VMA / 流式预算 / OOM背压 | `../03_api_manual/04_buffer_image_memory/vma_usage.md#streaming-budget-policy` |
| GPU Scene / bounds / generation | `../02_core_mental_model/compute_graphics_relationship.md#gpu-scene-contract` |
| GPU-driven / fixed-slot / MDI / Count | `../05_workflows/03_compute_workflows/add_compute_pass.md#gpu-driven-rendering` |
| Indirect能力回退 / firstInstance / DrawID | `../03_api_manual/03_command_buffer/indirect_commands.md#indirect-capability-fallback` |
| Indirect count溢出/command ABI | `../03_api_manual/03_command_buffer/indirect_commands.md#indirect-capacity-safety` |
| GPU命令/IDs/count同步 | `../05_workflows/03_compute_workflows/compute_to_graphics_sync.md#gpu-produced-draw-sync` |
| GPU LOD / resident fallback | `../05_workflows/03_compute_workflows/add_compute_pass.md#gpu-lod-residency` |
| Hi-Z / 遮挡剔除 / reversed Z | `../05_workflows/03_compute_workflows/add_compute_pass.md#hiz-occlusion` |
| 多视图剔除/独立HiZ与完成点 | `../05_workflows/03_compute_workflows/add_compute_pass.md#multi-view-culling` |
| GPU particles / alive compact | `../05_workflows/03_compute_workflows/add_compute_pass.md#gpu-particles` |
| Mesh/task / meshlet / 传统fallback | `../03_api_manual/06_pipeline/mesh_shader.md#mesh-path-fallback` |
| 规模渲染A/B / 软件Vulkan与MobileScale | `../05_workflows/07_optimization/optimize_frame_time.md#scaled-rendering-ab` |
| 混合光照 / 不同可见集合 | `../02_core_mental_model/engine_architecture.md#hybrid-lighting-decisions` |
| MV / depth / jitter / exposure / normal | `../02_core_mental_model/render_target_model.md#lighting-temporal-data-contract` |
| Ray Query / query-only / SBT误用 | `../03_api_manual/06_pipeline/compute_pipeline.md#ray-query-capability-contract` |
| BLAS / TLAS / scratch / compaction退休 | `../03_api_manual/04_buffer_image_memory/memory_allocation.md#acceleration-structure-resource-contract` |
| AS build / fragment query 同步 | `../03_api_manual/08_synchronization/pipeline_barrier.md#as-build-query-dependencies` |
| Shadow Map / CSM / bias / atlas | `../05_workflows/02_render_pass_effects/add_depth_pass.md#stable-shadow-workflow` |
| query阴影 / 单次反射 / alpha candidate | `../05_workflows/03_compute_workflows/add_compute_pass.md#hybrid-ray-query-workflow` |
| OMM / KHR与EXT / alpha失效 | `../05_workflows/03_compute_workflows/add_compute_pass.md#opacity-micromap-fallback` |
| 重投影 / history / 去噪 / disocclusion | `../05_workflows/02_render_pass_effects/add_postprocess_pass.md#temporal-quality-workflow` |
| SR / FG输入尺寸与UI | `../05_workflows/02_render_pass_effects/mobile_neural_graphics.md#temporal-sdk-adapters` |
| 阴影抖动 / 曝光残影 / 多View串影 | `../04_debug_playbooks/01_visual_issues/flickering.md#hybrid-temporal-diagnostics` |
| Hybrid分档 / 画质ROI / AS成本 | `../05_workflows/07_optimization/optimize_frame_time.md#quality-budget-tiers` |
| OMM/BVH公开案例证据 | `../06_cases/06_performance/case_performance.md#hybrid-quality-evidence` |
| 透明 / straight / premultiplied / opacity / transmittance | `../02_core_mental_model/render_target_model.md#transparent-composition-contract` |
| independentBlend / MRT blend / MSAA透明 | `../03_api_manual/06_pipeline/graphics_pipeline.md#blend-format-capability` |
| 低alpha多层 / RGBA8与FP16精度 | `../03_api_manual/04_buffer_image_memory/image.md#transparent-target-precision` |
| WBOIT / revealage / OIT溢出 | `../05_workflows/02_render_pass_effects/add_postprocess_pass.md#transparency-resolve` |
| 折射feedback / scene-color读写 | `../03_api_manual/07_rendering/render_target_layout.md#refraction-read-write-boundary` |
| 水 / 玻璃 / screen-space refraction / 厚度 | `../05_workflows/02_render_pass_effects/add_texture_sampling_pass.md#screen-space-refraction` |
| 局部雾 / 体积 / 雨雪软交界 | `../05_workflows/02_render_pass_effects/add_postprocess_pass.md#local-volume-composite` |
| 3DGS / Gaussian / PLY / splat排序 / 多集合ID | `../05_workflows/03_compute_workflows/add_compute_pass.md#gaussian-preproject-sort` |
| Gaussian indirect与属性同步 | `../05_workflows/03_compute_workflows/compute_to_graphics_sync.md#gaussian-consumer-dependencies` |
| footprint / coverage / 背景LOD / 透明层数预算 | `../05_workflows/07_optimization/optimize_mobile_bandwidth.md#coverage-budget` |
| 透明/GS方案选择 | `../02_core_mental_model/engine_architecture.md#transparent-gaussian-budget-decision` |
| 透明高覆盖/排序/精度分流 | `../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md#transparent-coverage-diagnostics` |
| 多splat set材质ID公开案例 | `../06_cases/02_descriptor_pipeline/case_descriptor_pipeline.md#gaussian-multi-set-id-case` |


<a id="mobile-topics"></a>
## 移动端主题（既有主类型的按需分支）

不是新启动集合，也不改变模型/宿主路由或触发条件。先确定 debug / performance / API / implementation / architecture主类型，
再从上表只读命中主题；真实项目仍叠加 #route-project，第三方库叠加 #route-third-party。

- 性能采集：tool_usage 的 mobile-profiler-contract；已有trace再读 Android workflow 的 mobile-capture-loop。
- 持续性能：optimize_frame_time 的 sustained-mobile-performance，区分真实/生成/呈现帧和热状态。
- 故障诊断：device_lost 的 mobile-fault-evidence，先核对能力与证据，不排除未覆盖原因。
- Tile选择：mobile_tile_rendering 的 tile-capability-matrix，算法依赖再读 tile-access-patterns。
- 外部资源：external_resource_interop 的 interop-capability-contract；导入失败再读 interop-lifetime-contract，
  实施时读 vulkan_opencl_interop 的 interop-workflow 与 interop-failure-recovery。
- 神经集成：mobile_neural_graphics 的 neural-capability-contract，按输入/history、多Device或回退问题
  再读 neural-input-history / neural-engine-lifetime / neural-fallback-decisions，不预加载全部SDK资料。
- 框架迁移：case_engine_architecture 的 mobile-sdk-framework-contracts，不把上游README/CI当目标GPU实测。

若宿主不支持段落读取，读目标全文并如实记录token；不要跳过硬规则，也不要为省token隐藏能力限制。


<a id="android-system-topics"></a>
## Android系统渲染主题（仍属既有主类型）

只在多实例、媒体输入或颜色/透明合成意图命中时使用上表新锚点；不改变固定启动三项、模型/宿主配置或原触发词。Android/API/debug/workflow/architecture按原类型输出；真实仓库仍叠加Evidence/Architecture Map与修改影响面。
先读一个权威合同，再按待解决问题定向补workflow；不要为非媒体问题预加载全部AHB/HDR章节。对每次实际读取保存path/anchor/hash与provider usage，新SYS题单独计量，不并入原12题30% token指标。
设计案例按需查 `../06_cases/04_swapchain_android/case_swapchain_android.md#multi-output-generation-case`、`../06_cases/03_sync_layout/case_sync_layout.md#android-media-early-return`、`../06_cases/01_black_screen/case_black_screen.md#android-alpha-color-case`，不能把设计案例当事故复现或Live答案。

<a id="engine-scale-topics"></a>
## Shader / 资源 / GPU-driven 规模化主题

仍按原 API/debug/performance/implementation/architecture 主类型，只命中加载上表对应锚点。先读一个权威合同，再按缺口补 workflow；真实项目叠加 Evidence Map、Architecture Map 与回归影响面，不把此主题变成全库启动包。C1/C2/C3/C4/C5 的 shader、pipeline、streaming、GPU-driven、LOD/Hi-Z/particles/multi-view 同属本版本，不把 GPU-driven 延后。

ENG13 新24题按 primary/contrast 成对输入评估，实际 path/anchor/hash/read trace/provider usage 单列；旧40题不变，原12题 v1.0.8 token分母与30%目标不被新题稀释。Source/build/HostShaderUnit/Static/Snapshot/Live/VulkanIntegration/MobileScale 分层报告，未运行保留 BLOCKED，不以关键词或软件GPU代替真实模型/移动设备验收。

<a id="hybrid-quality-topics"></a>
## 移动混合光照与时域画质（VIS14）

仍按既有 API/debug/performance/implementation/architecture 主类型，只按命中症状读一个权威合同，再补缺口。真实项目叠加 Evidence/Architecture Map、R1–R5、影响面及适用 G1–G6；本专题不加入强制启动集合。
旧64题 prompt bytes 冻结，VIS14-01..20 独立计分，总84；原12题 v1.0.8 provider input-token 分母不变，无新增30%目标。Static/Snapshot/Host Unit/Shader Unit/Vulkan Integration/Live/Android Device/Visual Quality 独立报告；未运行不继承旧 SHA PASS。


<a id="transparency-gaussian-topics"></a>
## 移动透明、体积与 Gaussian（TRAN15）

仍按既有主类型/触发/宿主与模型规则；只读取命中权威锚点，不加入最小启动。优先合成或数据合同，再按缺口补能力、同步、效果或覆盖预算。真实项目仍先 Evidence/Architecture Map，保持影响面、R1–R5 和适用 G1–G6。

旧84题与原12题token基线不变；TRAN15-01..20成对条件独立登记/计分，实际总数和运行状态以tests registry为准，不把计划104题当执行结果。逐任务记录相对最终v1.0.14的path/anchor/hash/读取量；文件净增0不等于token零增长。Static/host_unit/shader_unit/vulkan_integration/Live/Host/mobile_visual/mobile_performance/Package各自报告；缺设备/模型不继承历史PASS。

<a id="simulation-dynamic-geometry-topics"></a>
## GPU 仿真与动态几何（SIM16）

沿用既有主类型、硬规则与最小启动集合。只命中加载上表一个合同，再按缺口补充；不把仿真文档整组预加载。旧104题与原12题token基线冻结，SIM16-01..16成对条件单列；新总数120是registry规模，不是已执行Live结果。数值Host、Shader、Vulkan、Live/Host、移动持续质量各自报告。Skill v1.0.15已合并不代表配套tests证据已发布，也不代表水面透明集成已验收。


<a id="vulkan-coverage-topics"></a>
## 全域 API 合同审计（CORE17）

仍按原 API/debug/performance/implementation/architecture 主类型，不增加默认加载文件。具体版本、稀有能力、平台、Video、完整RT/SBT、cooperative/tensor等命中时，仅查 [18域索引](../03_api_manual/api_index.md#vulkan-domain-map)，读取一个对应合同，再按剩余缺口补载官方来源。不要将整份Registry/所有领域作为启动上下文；也不能因省token跳过19硬规则、错误分支或feature/生命周期条件。实现/真实项目仍叠加原Evidence/Architecture Map、R1–R5与适用G1–G6。

全域完成声明以 [K/B/P边界](README.md#vulkan-coverage-scope) 为准。当前稳定域语义审计仍有缺口，只有候选状态；未执行Live/实际宿主或目标设备不得写PASS。旧120个prompt不改，CORE17复用图只说明验收任务归属，不是模型答对证明。

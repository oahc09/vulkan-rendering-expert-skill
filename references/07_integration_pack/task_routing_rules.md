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

首轮读取：先核对库与 Vulkan 版本，再按主类型选 workflow / API 卡；缺少专用 workflow 时使用相关 API 与 debug 检查项。

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

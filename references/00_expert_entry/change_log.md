# Change Log

## v0.1

- 建立专家行为控制模块。
- 拆分 role、hard rules、task classifier、response formats、debug priority、performance priority、accuracy check。
- 控制根目录 `../../SKILL.md` 只作为入口，不承载大段知识。
- 引入准确性分级：12 标签体系（详见 `01_source_map_and_api_manual_strategy/source_tags.md`）。

## v0.1 决策（已解决）

- 默认使用 Vulkan 1.3+，但保留 1.0/1.1/1.2 兼容说明。[GUIDE][ENGINE]
- 新项目默认推荐 Dynamic Rendering，复杂多 subpass 场景保留 RenderPass。[GUIDE][ENGINE]
- Android 默认以 SurfaceView + ANativeWindow 为主，其他方案（如 TextureView）需说明限制。[ANDROID]
- 不强制要求 RenderDoc / AGI，但 Debug 结论必须提供可验证路径；有工具时应优先使用。[TOOL][ENGINE]
- 增加“禁止只输出概念解释”规则，已写入 `hard_rules.md`。[ENGINE]
- 项目级文件修改模板暂缓到 v0.2，当前通过 `hard_rules.md` 第 6 条覆盖核心修改要求。

## 待调整

- v0.2 是否加入项目级文件修改模板。（已解决：当前通过 `hard_rules.md` 第 6 条覆盖核心修改要求，v0.2 不再单独加入模板。）

## v1.0.1

### Vulkan 1.4 知识库补充

- 补充核心化扩展、强制功能、最低限制提升。[GUIDE][SPEC]
- 新增 15 张卡片（vulkan_1_4_overview、timeline_semaphore、descriptor_indexing 等）。
- 增量补充 5 张已有卡片（dynamic_rendering、synchronization2 等）。
- 版本基线从 Vulkan 1.3+ 升级为 Vulkan 1.3+/1.4。

### 新增硬规则（hard_rules.md #12-#15）

- **#12 Vertex Attribute 布局校验**：核对 format / offset / stride 与实际数据布局；原有等宽要求及错误 VUID 引用已在 v1.0.6 审查修订中纠正。[SPEC][ENGINE]
- **#13 相机参数基于模型 bbox**：`target/distance/farP` 必须基于 AABB 计算，禁止硬编码。[ENGINE]
- **#14 PBR 光源按尺度缩放**：`1/d²` 衰减下 `intensity = targetRadiance × distance²`。[ENGINE][HEUR]
- **#15 Vulkan 销毁幂等**：handle 置空 + `vkDeviceWaitIdle` 可重复 + `vkDestroy*` 容忍 NULL_HANDLE。[SPEC]

### 第三方库 API 准确性规则（accuracy_check.md）

- 新增 "Third-Party Library API Accuracy" 小节，6 条规则：标注版本号、6 个月回查、不编造签名、Vulkan backend 双重标注、API 变更点显式列出、检索优先最新 release notes。

### 任务路由与检索策略

- `../07_integration_pack/task_routing_rules.md` 新增第 10 类任务"第三方库集成类"。
- `../07_integration_pack/retrieval_policy.md` 新增 §5 第三方库 API 检索规则。

### 资源生命周期与幂等销毁设计

- `../05_workflows/05_resource_management/manage_resource_lifetime.md` 新增"幂等销毁设计"与"常见多次调用场景"小节（含 SafeDestroy wrapper + 5 类组合调用：main+析构、异常+正常、窗口关闭+析构、swapchain recreate+shutdown、device lost+析构）。
- `../02_core_mental_model/resource_lifecycle.md` 新增"幂等销毁"心智模型小节。

### 行尾规范化

- `../05_workflows/workflow_index.md`、`../07_integration_pack/retrieval_policy.md` 由 CRLF 转 LF。

## v1.0.3

### 文件数量精简（248 → 196，满足 ClawHub ≤200 限制）

为满足 ClawHub 提交的 200 文件上限，分三阶段精简文件数量，总计减少 52 个文件。所有合并文件保留原内容，仅做层级调整以保持向量检索命中率。

#### Phase 1：排除测试输入数据（248 → 236，-12）

- `.gitignore` 新增 `tests/prompts/*.txt` 规则，TC9 提示词 fixture 本地保留但不跟踪。

#### Phase 2a：合并 `06_cases/`（236 → 214，-22）

- 7 个子目录各合并为 1 个文件，33 → 11 文件。
- 合并文件 H1 使用 `# Cases: <Category>`，原 case 降级为 `## Case: <原 case 名>` 锚点，原 `##` 段落降级为 `###`。
- 涉及文件：`01_black_screen`、`02_descriptor_pipeline`、`03_sync_layout`、`04_swapchain_android`、`05_compute`、`06_performance`、`07_engine_architecture`。
- 同步更新 `06_cases/case_index.md`、`06_cases/README.md`、`MODULE_SUMMARY.md`（33→11）和 3 个交叉引用文件。

#### Phase 2b：合并 `04_debug_playbooks/`（214 → 196，-6）

- 6 组合并，28 → 22 文件。
- 合并文件以 `## Debug Playbook: <原 playbook 名>` 作为锚点，原 `##` 段落降级为 `###`。
- 涉及合并组：
  - `03_validation_errors/`：`descriptor_binding_error` + `pipeline_layout_error` → `04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`；`image_layout_error` + `synchronization_hazard` → `04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`。
  - `06_performance_symptoms/`：`bandwidth_high` + `fullscreen_pass_cost` → `04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`；`barrier_overuse` + `draw_call_bottleneck` → `04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`；`cpu_frame_time_high` + `descriptor_update_overhead` → `04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md`；`pipeline_creation_stutter` + `startup_time_high` → `04_debug_playbooks/06_performance_symptoms/pipeline_startup_stutter.md`。
- `tests/test_templates.py` 增加 `## Debug Playbook:` 前缀检测，合并文件使用 `###` 段落校验。
- 同步更新 `04_debug_playbooks/README.md`、`04_debug_playbooks/debug_priority_index.md`、`MODULE_SUMMARY.md`（28→22）和 52 个交叉引用文件。

### 行尾规范化（Phase 2b 副产物）

- `_fix_pb_refs.py` 批量替换留下的 CRLF 行尾统一为 LF，涉及 43 个文件。
- `git diff --check` 全部干净。

## v1.0.7 — Onboarding

针对 SkillHub 评测（T 4.8 / R 4.5 / A 4.4 / C 4.8 / E 4.8）的上手体验优化，不改动知识主体（API 卡片 / playbook / workflow / case 内容不变），无新增文件（保持 198/200）。

- **适用性（A）**：README ×2 新增"安装与调用"章节（Claude Code / TraeCode / 其他 Agent Skills 宿主的放置路径与降级模式）与 8 条可复制提问示例（每条标注触发模块）；`../../SKILL.md` description 补充触发场景句式，提高宿主自动命中率。
- **可靠性（R）**：`progressive_retrieval.md` R2 新增分任务类型最小提问模板（9 类任务 × 标准三项信息），信息收集从临时发挥变为固定协议；用户提供齐全时跳过 R2 直接路由。
- **规范性（C）**：README 新增"上手路径"（直接提问 / 知识地图 / 深入学习三条路线）。
- **有效性（E）**：`../../SKILL.md` 任务路由段新增"症状 / 意图 → 直达速查表"（20 行症状直达 playbook / workflow / case / 决策框架），免读索引直接加载。
- **可信任度（T）**：`01_source_map_and_api_manual_strategy/trusted_sources.md` 新增中文辅助阅读资源节，显式标注非官方、冲突以英文官方 Spec 为准、引用等级不高于 [HEUR]。

## v1.0.6 — Rendering Engine Architect

### 审查修订（2026-09-12）

- `metadata.keywords` 改为字符串，符合 Agent Skills 的 metadata 类型约束。
- 顶点属性规则按实际布局校验，补充 padding 反例与可追溯的格式支持、portability subset VUID。
- 架构模型与 Fence/Semaphore API 卡统一使用 timeline 类型的 `VkSemaphore`，补充 feature 与创建链。
- Dynamic Rendering 决策补充 local read 扩展路径、Vulkan 1.4 附件支持边界与官方来源。
- 澄清流程先检查已有证据，仅对影响路由或结论的剩余缺口提问；入口与输出模板同步，日志条件限定故障诊断。

### 架构能力与文件整理

- 新增引擎架构心智模型：RHI / Frame Context / Resource Manager / Render Graph / Descriptor Model / Pipeline Manager / Queue Model 七子系统与影响链。
- 新增架构决策框架：D1-D7 七组 trade-off，六要素结构（适用/不适用/收益/复杂度/性能风险/重新评估条件），不默认新技术。
- 六个关键 workflow 增加架构决策阶段（需求→约束→Candidate→Trade-off→Decision），Verification Gate 与 Progressive Retrieval 不变。
- 新增四个架构迁移决策案例：bindless 迁移判断、RenderGraph 引入拐点、资源生命周期拆分、async compute 反噬。
- 入口与路由接线：SKILL.md、task_classifier、task_routing_rules、README×2。
- MODULE_SUMMARY（02_core_mental_model 15→16）。文件数 199→200（达 ClawHub 上限）。
- 修正存量内容的 3 个编造 VUID 编号（`VUID-VkDescriptorSetAllocateInfo-pSetLayouts-03044` / `VUID-vkUpdateDescriptorSets-None-03047` / `VUID-VkImageMemoryBarrier-oldLayout-01197`，波及 4 文件 8 处，均经官方规范验证）与 acquire/present semaphore 必须为 binary 的歧义表述。
- 文件数量优化：`07_integration_pack` 的 maintenance_plan / release_checklist / token_budget_policy（三者均为零引用孤儿文件）合并为 `07_integration_pack/maintenance_release_token_policy.md`，git 跟踪文件 200 → 198，恢复 ClawHub ≤200 限额余量。

## v1.0.5

### Intelligent Retrieval：检索循环 + 证据驱动决策树 + 领域补白

新增 `00_expert_entry/progressive_retrieval.md`：五阶段检索循环（R1 查询分解 / R2 意图澄清 / R3 首轮路由 / R4 证据评估 / R5 二轮定向检索）；复杂跨类任务先分解再路由，模糊提问先给 ≤3 项最小提问清单，低置信子问题强制二轮补载；循环输出作为 Verification Gate 输入。

Debug Playbook §3 全量决策表化（18 个 playbook 文件 / 24 个小节）：快速验证路径从线性步骤改为"检查（成本升序）→ 结果分支 → 剪枝（引用 §2 假设编号）"的证据驱动决策表；模板与 README 同步新规范。

新增 API 卡片：`03_api_manual/06_pipeline/mesh_shader.md`（VK_EXT_mesh_shader、meshlet、GPU-driven，Android 支持边界显式标注）与 `03_api_manual/02_surface_swapchain/desktop_windowing.md`（SDL/GLFW/Win32、最小化/resize/DPI 与 swapchain 生命周期）。

入口与路由接入：`../../SKILL.md` 启动加载第 7 项与回答规则；`00_expert_entry/task_classifier.md` 跨类型先分解；`07_integration_pack/retrieval_policy.md` §2 降级为首轮路由；`00_expert_entry/response_formats.md` 新增 §0.5 意图澄清格式；`00_expert_entry/verification_gate.md` 交叉引用。索引同步：api_index、MODULE_SUMMARY（00_expert_entry 10→11、03_api_manual 66→68）。

## v1.0.4

### Production Expert：可靠性、根因判断、回归验证

不扩展新的 Vulkan API 大类，不新增顶层知识模块（仅新增 3 个文件、无删除，git 跟踪文件 192 → 195，仍满足 ClawHub ≤200 限制）。本版本聚焦真实工程任务的可靠性：结论出口统一过验证关卡，修改前先推影响面，修复结论区分分级，修复后按清单回归。

#### 新增统一验证关卡（Verification Gate，G1-G6）

- 新增 `00_expert_entry/verification_gate.md`：任何"完成 / 解决 / 根因已修 / 性能已优化"类结论，出口前依次过 G1 API 合法性 → G2 生命周期 → G3 同步 → G4 Validation Layer → G5 RenderDoc / AGI → G6 平台回归；每关标注已验证 / 未验证 / 不适用，不可验证的关卡默认不通过。
- G4 明确 Validation clean 只是必要条件而非成功标准；G6 覆盖 Android rotation / pause / resume / Surface-Swapchain recreate。

#### 新增修改影响面推理（`02_core_mental_model/regression_reasoning.md`）

- 依赖传播规则：DescriptorSetLayout → PipelineLayout → Pipeline → DescriptorSet 重分配与重绑定；Image → ImageView → RenderTarget / Framebuffer；Swapchain 尺寸 → depth / offscreen / RenderArea / viewport / 特殊分辨率特效；Frames-in-flight → per-frame 资源隔离与生命周期；Barrier → producer / consumer / stage / access / layout / queue ownership。
- 修改前先推影响面，影响类别决定回归验证范围。

#### 新增回归验证清单（`07_integration_pack/regression_checklist.md`）

- 六类回归：correctness / rendering / resource lifecycle / synchronization / Android lifecycle / performance。
- 供 Verification Gate G6 与 Debug Playbook §7 选用。

#### Debug Playbook 统一推理链与修复分级（22 文件全量审查）

- 统一推理链写入模板与 README：Symptom → Hypothesis → Evidence → Root Cause → Workaround → Minimal Fix → Structural Fix → Regression Verification；禁止把"现象消失"等同于"找到根因"。
- 修复分级全量更名并统一语义：最小修复 → Workaround（临时绕过）、稳定修复 → Minimal Fix（根因最小修复）、工程化修复 → Structural Fix（结构性 / 防复发）；涉及 `04_debug_playbooks/debug_playbook_template.md`、README 及全部带修复分级的 playbook。
- `06_cases/case_template.md` 与全部 7 个 case 文件（29 个案例）同步修复分级：case 侧旧"最小修复"内容为根因修复，语义映射为 Minimal Fix；旧"稳定修复 / 工程化修复"合并为 Structural Fix；`06_cases/01_black_screen/case_black_screen.md` 的临时 cullMode 条目单独提取为 Workaround 小节。
- `00_expert_entry/debug_priority.md`、`04_debug_playbooks/debug_priority_index.md`、`01_source_map_and_api_manual_strategy/api_card_template.md` 的"给出最小修复"步骤统一改为"给出 Workaround / Minimal Fix / Structural Fix"。
- 06_cases 模块行尾规范化：7 个 case 文件与 `06_cases/case_tags.md` CRLF → LF，并清除历史行尾空白；至此 references 下全部 Markdown 文件为 LF 行尾，`git diff --check` 干净。

#### 入口规则与路由更新

- `../../SKILL.md`：版本 1.0.4；启动加载顺序增加第 6 项 `verification_gate.md`；回答规则第 6 条"Verification Gate 状态（G1-G6 逐关标注）"；禁止行为新增"现象消失 ≠ 根因修复"与"Validation clean 不是唯一成功标准"。
- `hard_rules.md` 新增 #16（修复必须区分三级，Workaround 后须继续定位根因或显式标注残留风险）与 #17（Validation clean 非唯一成功标准，结论前过 G1-G6）。
- `response_formats.md` 新增 §0"统一出口段：Verification Gate"，故障调试类输出结构增加修复分级与 Verification Gate 状态。
- `../07_integration_pack/task_routing_rules.md` 新增第 11 类任务"统一出口：Verification Gate"，适用于设计 / 实现 / Debug / 优化等一切输出结论性判断的任务。

#### 索引同步

- `MODULE_SUMMARY.md`：00_expert_entry 9 → 10、02_core_mental_model 14 → 15、07_integration_pack 8 → 9。
- `00_expert_entry/README.md`、`02_core_mental_model/README.md` 文件列表同步。

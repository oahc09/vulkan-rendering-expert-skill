# 07_integration_pack：Vulkan Expert Skill 集成与总装模块

## 模块定位

`07_integration_pack` 是 Vulkan Expert Skill 的最终集成模块。

它不新增 Vulkan API 知识，不新增 Debug 案例，也不新增 Workflow。它负责把已有模块组织成一个稳定、低冗余、可维护、可检索、可发布的 Vulkan Expert Skill。

## 核心目标

1. 定义最终目录结构。
2. 定义模块依赖关系。
3. 定义任务路由规则。
4. 定义回答模式。
5. 定义检索策略。
6. 定义 token 控制策略。
7. 定义维护计划。
8. 定义发布检查流程。
9. 定义集成测试计划。

## 当前纳入总装的模块

```text
vulkan-rendering-expert-skill/
├── 00_expert_entry/
├── 01_source_map_and_api_manual_strategy/
├── 02_core_mental_model/
├── 03_api_manual/
├── 04_debug_playbooks/
├── 05_workflows/
├── 06_cases/
└── 07_integration_pack/
```

暂不纳入：

```text
07_code_templates/
08_eval_tasks/
09_tooling_and_verification/
```

## 集成原则

1. 不默认加载全部模块。
2. 所有任务默认遵守 `00_expert_entry`。
3. 所有 Vulkan 工程分析默认依赖 `02_core_mental_model`。
4. API 细节查 `03_api_manual`。
5. 故障现象查 `04_debug_playbooks`。
6. 正向开发任务查 `05_workflows`。
7. 真实经验和相似问题查 `06_cases`。
8. 真实仓库诊断任务先查 `05_workflows/01_renderer_setup/project_diagnosis.md`，关键项目事实必须有 `[CODE]` 证据。
9. API 事实、性能建议、Android 平台细节必须遵守 `01_source_map_and_api_manual_strategy` 的可信等级规则。
10. 输出必须有验证闭环。
11. 不确定时不编造，应提示回查 Spec / Reference Page / Android 官方文档 / 工具证据。

## 仓库验证

在仓库根目录运行 `node scripts/check-skill.mjs`。该检查器统计全部源码文件（当前212），不是运行时包白名单。发布200文件预算由 `python scripts/agensi_audit_and_pack.py <repo> --out <outside-output>` 在清洁提交上单独验证；不能把源码统计误作包超限。检查器只依赖 Node.js 内置模块和 Git，包含已跟踪文件及未被忽略的新文件，不读取本地 reports / tests 等被忽略目录，也不写文件。

它检查 UTF-8、代码围栏、普通 Markdown 本地文件链接、SKILL 入口路径和模块文件数；不代替完整 YAML schema 校验、Markdown 锚点检查、官方 API 核对、模型行为评估或 Vulkan 运行验收。行为评估的输入与判据见 [integration_test_plan.md](integration_test_plan.md)，执行证据见 [behavior_evaluation.md](behavior_evaluation.md)。


## v1.0.15 定向知识

- [TRAN15按需路由](task_routing_rules.md#transparency-gaussian-topics)


<a id="vulkan-coverage-scope"></a>
## v1.0.17 全域覆盖候选与分层门禁

范围为冻结的标准 Vulkan1.0–1.4、1.4.368 Registry 公开稳定 KHR/EXT/vendor/platform 扩展。Vulkan SC 是独立变体；preview/disabled/其他API条目在测试清单中单列，不从稳定分母隐藏稀有能力。冻结源为 [Vulkan-Docs fa30d4e](https://github.com/KhronosGroup/Vulkan-Docs/tree/fa30d4e312e843193601be7cb926c7e25d9ec885)。具体领域从 [18域导航](../03_api_manual/api_index.md#vulkan-domain-map) 按需定位。

当前是候选，尚未达到全域覆盖目标。K：稳定范围每项必须有经过审查的 L0定位、L1语义和L2正常/失败/回退流程，高风险错误/冲突归零；全量 XML 清单不能代替语义。B：最终候选的真实模型输出、provider usage、语义评审和至少一个实际宿主读取轨迹独立验收；Static/Snapshot/CPU模拟不得替代。P：两仓精确SHA、发布合同、同候选可重现包、八模块/MIT/200文件预算与未验证设备矩阵一致。不得用设备不支持豁免知识，也不得用知识覆盖声称设备认证。

既有19硬规则、最小启动、R1–R5、Evidence/Architecture Map、G1–G6和模型/宿主选择规则不变；文字/矢量/2D–3D融合专题仍属于v1.0.18。旧120题逐字冻结，24个CORE17能力任务先复用6组、只为缺口登记18个新成对任务，总registry138不是Live已执行138。原12题token基线和目标不变，新任务读取量/轮次/provider输入token独立报告，不能拿文件数量替代token。


<a id="text18-candidate-status"></a>
## v1.0.18 文字专题候选与继承缺口

基于已合入 #13 的 Skill main `068a967038ce92a0d4f7c28e4dcdc70a1a3c7c4c`，不是宣称 v1.0.17 全域验收完成。原 K/B/P 未完成事项保留。TEXT18按四条主线在原文件加锚点，运行时知识文件净增0。配套 tests 的前版基线/精确候选与状态报告独立登记，不能把主仓合并或历史测试数当成完整跨仓回归。

本候选可以审阅知识与可执行 Host 材料，但 Platform/Shader/Vulkan/Live/实际Host/Visual/Device必须以各层实际执行记录为准；缺少记录保持 UNVERIFIED。未运行模型不得称20题通过；未查看真实渲染不得称视觉达标。

<a id="v20-current-candidate"></a>
## v1.0.20 当前候选

冻结实施起点：Skill main [c475084](https://github.com/oahc09/vulkan-rendering-expert-skill/commit/c475084fa720596f1c0fddf82e7a0a820b7bfd95)，tests main [f8cadd3](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/commit/f8cadd3614f998b042b77293618323120bcb6d28) 仍配历史 v1.0.14；tests [PR #12](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/12) 的候选头 [770bfdf](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/commit/770bfdf5bcc5497e8490432d315604242adda23d) 是 v1.0.19 证据入口，不是本候选精确配对。不要直接用任何一个 tests 分支的旧 PASS 证明 v1.0.20。

| tests 路径 | 已核对关系与保留范围 |
|---|---|
| [#8](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/8) | 合并提交 `b40bfb2` 的目标是较早的 v1.0.15 分支；进入 source-review 祖先图的是本 PR 的源头 `528ba9e`，不能把两者视为同一 provenance。 |
| [#9](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/9)、[#10](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/10) | TEXT18 和 CORE17 合入的是 source-review 分支（`ee1e42e` → `90b2df2`），不是 tests main。保留该分支成果，不用 main 的 v1.0.14 合同替代。 |
| [#11](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/11)、[#12](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/12) | 两个草稿在 `90b2df2` 分岔；#11 Scene B 的 12 个变化路径在 #12 中未相对共同基线变化。这个分岔仅用于解释历史素材与出处，不是当前草稿队列。两份差量由后续整合流程分别保留，不假设 #12 自身已包含 #11。原 #12 执行的 Skill pin 是 `6eafab53`，3042 PASS / 228 skip / 9 deselect 仅为历史配对范围。 |

- V20-01/02 当前行动：双仓整理与当前配对入口已落地。Tests [#17](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/17) 补齐精确配对取证，[#18](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/pull/18) 补充有界 Video 审查。使用 [current-v1.0.20 配对清单](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/blob/main/coverage/v1.0.20/current-pair.json) 和 [当前回执入口](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/blob/main/docs/v1.0.20-postmerge-pair.md)，逐次核对实际 Skill/Tests SHA、tree、原始 JUnit、失败/跳过与候选包身份；既有回执不能证明后续修订。下一步继续原任务验收与实际设备、宿主、模型证据，不将离线配对合格等同发布封板。
- V20-05/07 局部源码审查见 [WSI 失败分支](../03_api_manual/02_surface_swapchain/swapchain_recreate.md#v20-acquire-generation-contract)、[Fence 分支](../03_api_manual/08_synchronization/fence.md#fence-completion-contract)、[Descriptor 更新与失效](../03_api_manual/05_descriptor/descriptor_update.md#v20-descriptor-command-validity)、[旧代命令](../03_api_manual/03_command_buffer/command_buffer_lifetime.md#command-retirement-contract)。来源、适用条件、反例和剩余缺口在权威段，状态仅为部分审查，无新增执行证据。
- V20-22 当前计数：旧默认 runner 的 120 个逻辑输入保持不变，重建的 CORE17 24 个逻辑输入从独立入口运行。合计 144 不是单 runner 分母，也不是 Live 通过数。上文 138 是旧登记口径。原 24 个 ALL19 成对任务组及 12 个 E2E19 工程任务仍为独立验收分母，本修订不升级状态。
- v1.0.20 定向知识以 1.4.368 冻结规范为依据。全域 L1/L2、官方 369 差分的完整审查、实际模型/宿主、Android、第二设备或驱动及发布封板分别跟踪，未满足保持未验证。运行时知识文件净增 0。

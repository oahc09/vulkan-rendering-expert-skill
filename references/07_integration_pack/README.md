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

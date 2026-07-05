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
8. API 事实、性能建议、Android 平台细节必须遵守 `01_source_map_and_api_manual_strategy` 的可信等级规则。
9. 输出必须有验证闭环。
10. 不确定时不编造，应提示回查 Spec / Reference Page / Android 官方文档 / 工具证据。

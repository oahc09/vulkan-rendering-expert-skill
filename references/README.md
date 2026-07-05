# Vulkan Rendering Expert Skill

本包是本轮讨论整理后的 Vulkan 高级专家 Skill 完整模块源码包。

## 目录结构

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

## 模块说明

| 模块 | 作用 |
|---|---|
| `00_expert_entry` | 专家行为控制：角色、硬规则、任务分类、输出格式、调试/性能优先级 |
| `01_source_map_and_api_manual_strategy` | 来源地图与 API 手册策略：可信来源、来源等级、API 卡片设计、更新策略 |
| `02_core_mental_model` | Vulkan 核心心智模型：对象链路、帧生命周期、资源生命周期、同步模型、Android Surface/Swapchain 生命周期 |
| `03_api_manual` | API 专家手册：API Card 模板、写作规则，以及后续 API 卡片扩展入口 |
| `04_debug_playbooks` | 调试专家手册：黑屏、闪烁、Validation Error、Descriptor、Image Layout、Swapchain、Compute 等问题排查 |
| `05_workflows` | 专家工作流：正向工程任务流程，包括 Renderer、Fullscreen Pass、Compute、Android 集成、优化 |
| `06_cases` | 真实案例库：真实问题复盘、初始误判、关键证据、根因、修复和经验抽象 |
| `07_integration_pack` | 集成与总装：最终结构、依赖关系、任务路由、检索策略、回答模式、token 控制、维护与发布检查 |

## 使用建议

1. 默认先读取 `00_expert_entry/SKILL.md`。
2. 根据任务类型查 `07_integration_pack/task_routing_rules.md`。
3. API 细节查 `03_api_manual`。
4. 故障调试查 `04_debug_playbooks`。
5. 正向开发查 `05_workflows`。
6. 类似经验查 `06_cases`。
7. 复杂任务先参考 `02_core_mental_model` 建立对象链路，再进入 API / Workflow / Debug。

## 当前状态

这是结构化初版，可直接放入 skill 仓库继续迭代。
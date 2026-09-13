# Vulkan 渲染专家技能

[English](README_EN.md) | 中文

![Vulkan 渲染专家技能介绍图](assets/vulkan-rendering-expert-banner.png)

这是一个 Vulkan 渲染工程专家技能包。它不是 Vulkan 入门教程，而是为真实渲染工程任务准备的运行时知识库：用于在处理 Vulkan 设计、实现、调试、优化和验证问题时，按工程链路组织判断、引用规则、API 细节、调试路径和回归验证。

## 适用场景

- 设计 Vulkan 渲染管线、Render Pass、Dynamic Rendering、Render Graph 或 RHI 抽象。
- 实现或修改 Descriptor、Pipeline、Command Buffer、Buffer/Image、Swapchain、同步和资源生命周期代码。
- 排查黑屏、闪烁、崩溃、GPU hang、device lost、Validation Error、image layout、descriptor binding 等问题。
- 分析移动端 Vulkan 性能瓶颈，包括 bandwidth、fullscreen pass、barrier、descriptor 更新和 pipeline 创建卡顿。
- 处理 Android Vulkan 的 `ANativeWindow`、Surface 生命周期、pause/resume、横竖屏和 swapchain recreate。
- 在不确定 API 细节时，区分规范来源、经验判断和需要回查的内容。

## 技能结构

```text
.
├── SKILL.md                 # 技能入口，定义触发、加载顺序和输出规则
├── agents/                  # 可选的工具或平台集成配置
├── assets/                  # README 和发布页使用的图片资产
└── references/              # Vulkan 专家知识库，按任务渐进加载
```

`references/` 按职责拆分为 8 个模块：

| 模块 | 作用 |
|---|---|
| `00_expert_entry` | 角色、硬规则、任务分类、输出格式、调试/性能优先级 |
| `01_source_map_and_api_manual_strategy` | 来源等级、引用规则、API 卡片写作策略 |
| `02_core_mental_model` | Vulkan 对象链路、帧生命周期、资源生命周期、同步模型、引擎子系统架构与架构决策 |
| `03_api_manual` | API 卡片、生命周期索引、错误索引和 Vulkan API 细节 |
| `04_debug_playbooks` | 黑屏、闪烁、崩溃、Validation Error、同步和性能排查手册 |
| `05_workflows` | Renderer、Pass、Compute、Android 集成、资源管理和优化工作流 |
| `06_cases` | 真实工程案例、误判复盘、根因、修复和经验抽象 |
| `07_integration_pack` | 模块依赖、任务路由、检索策略和 token 使用规则 |

## 核心能力

这个技能要求输出始终给出可执行的 Vulkan 路径，而不是停留在概念解释：

1. 先给结论和最高优先级判断。
2. 给出 Vulkan 对象链路、关键 API、资源状态、layout 或同步关系。
3. 标出 descriptor、pipeline、command buffer、image layout、lifetime、Android lifecycle 等高风险点。
4. 给出最小验证方式，例如 Validation Layer、RenderDoc、AGI、logcat、trace、counter 或 targeted assert。
5. 对不确定 API 细节明确要求回查 Vulkan Spec、Registry、官方示例或平台文档。

## 安装与调用

本技能遵循 Agent Skills 规范：仓库根目录即技能目录，`SKILL.md` 是入口，`references/` 按需加载。

**Claude Code**

```bash
git clone https://github.com/oahc09/vulkan-rendering-expert-skill ~/.claude/skills/vulkan-rendering-expert-skill
```

放入技能目录后，描述 Vulkan 问题即可自动触发；也可显式说"使用 vulkan-rendering-expert-skill"。

**TraeCode / Trae**

在技能管理中添加本仓库目录作为本地技能，或从技能市场搜索安装。

**其他支持 Agent Skills 的宿主**（Cursor、VS Code 插件等）

凡能读取 `SKILL.md` frontmatter 并按其指令加载 `references/` 文件的宿主均可使用。宿主不支持技能机制时，可把 `SKILL.md` 全文粘贴为系统提示词，技能以降级模式工作（路由与回答规则仍生效，自动加载失效）。

## 提问示例库

以下提问可直接复制使用，括号内为会触发的模块：

1. `Android Vulkan 前后台切换后黑屏，给出对象链路、最可能原因和验证步骤。`（debug playbook + Android case）
2. `vkCreateGraphicsPipelines 报 VUID 错误，帮我解码这条 Validation 消息：<贴原文>`（validation 解码 playbook）
3. `小米 13 上 GPU 帧耗时 22ms，全屏后处理占大头，怎么优化？`（性能 playbook + 优化 workflow）
4. `从零搭建一个最小 Vulkan renderer，要求 Validation clean、能 resize。`（renderer workflow + 架构决策）
5. `材质数量上千，descriptor set 创建很慢，要不要上 bindless？给我决策分析。`（架构决策框架 + bindless 案例）
6. `现有 8 个 pass 的手写 barrier 维护不动了，评估是否引入 RenderGraph。`（架构决策 + RenderGraph 案例）
7. `vkCmdPipelineBarrier2 的 srcStageMask 怎么选？`（API 卡片）
8. `有没有 swapchain recreate 导致崩溃的真实案例？`（case 索引）

提问时附带关键信息可获得最准回答，各类任务的信息清单见 `references/00_expert_entry/progressive_retrieval.md` R2 节的分任务类型提问模板。

## 上手路径

- **直接提问（推荐）**：无需先读任何文件，技能按症状/意图自动路由到对应 playbook、workflow 或案例。
- **看知识地图**：读 `references/README.md` 和 `references/MODULE_SUMMARY.md`，了解 8 个模块的分工与规模。
- **深入学习**：按模块编号 `00` → `07` 顺序阅读；调试优先读 `04_debug_playbooks/`，实现优先读 `05_workflows/`，架构优先读 `02_core_mental_model/engine_architecture.md`。

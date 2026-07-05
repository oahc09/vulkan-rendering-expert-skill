# 00_expert_entry：专家入口模块

## 1. 模块定位

`00_expert_entry` 是 Vulkan 渲染专家 Skill 的入口模块。它定义了助手在处理 Vulkan 工程任务时的角色、硬约束、任务分类、响应格式和准确性规则。

任何 Vulkan 相关任务都应先加载本模块中的规则文件，再进入具体模块。

## 2. 包含文件

```text
00_expert_entry/
├── SKILL.md                 # Skill YAML frontmatter 与总体说明
├── README.md                # 本文件
├── role.md                  # 专家角色定义
├── hard_rules.md            # 必须遵守的硬规则
├── task_classifier.md       # 任务分类器
├── response_formats.md      # 统一输出结构
├── accuracy_check.md        # 准确性检查规则
├── debug_priority.md        # 调试问题优先级
├── performance_priority.md  # 性能问题优先级
└── change_log.md            # 版本变更记录
```

## 3. 使用顺序

处理任务时按以下顺序引用：

```text
1. SKILL.md
2. role.md
3. hard_rules.md
4. task_classifier.md
5. response_formats.md
6. accuracy_check.md
```

调试任务额外加载：

- `debug_priority.md`

性能任务额外加载：

- `performance_priority.md`

## 4. 与其他模块关系

```text
00_expert_entry          # 角色、规则、格式
01_source_map_and_api_manual_strategy  # 来源等级、引用规则
02_core_mental_model     # Vulkan 对象链路、生命周期、同步模型
03_api_manual            # Vulkan API 专家卡片
04_debug_playbooks       # 故障排查手册
05_workflows             # 正向开发工作流
06_cases                 # 真实工程案例
07_integration_pack      # 集成与测试
```

## 5. 核心原则

- 不输出 Vulkan 入门教程式回答。
- 每个回答必须包含可执行的 Vulkan 对象链路、API 调用或验证路径。
- 硬规则必须来源于 `[SPEC]`、`[REGISTRY]`、`[REF]` 或平台限定的 `[ANDROID]`。

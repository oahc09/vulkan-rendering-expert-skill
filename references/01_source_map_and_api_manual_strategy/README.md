# 模块 2：来源地图与 API 手册策略

## 模块定位

本模块用于约束 Vulkan Expert Skill 的知识来源、可信等级、引用规则、API 手册组织方式和更新策略。

它解决的问题是：

```text
Vulkan 细节从哪里获取？
哪些来源可信？
哪些内容可以写成硬规则？
哪些只能作为经验建议？
API 手册是否必须？应该怎么组织？
如何避免 AI 编造 Vulkan API 细节？
```

## 模块目标

1. 建立 Vulkan Skill 的事实来源体系。
2. 区分规范事实、官方建议、平台规则、工具验证、工程经验和启发式判断。
3. 定义 API Manual 的组织方式：不复制官方文档，而是转写为 API Card + Usage Pattern + Failure Mode。
4. 定义引用和更新策略，避免过时内容污染 skill。
5. 为后续 `03_api_manual`、`04_debug_playbooks`、`05_workflows` 提供可信基础。

## 文件说明

```text
README.md                 # 模块说明
source_priority.md        # 来源优先级
source_tags.md            # 来源标签与可信等级
trusted_sources.md        # 推荐官方/半官方来源清单
api_manual_design.md      # API 手册设计方式
api_card_template.md      # API 卡片模板
citation_rules.md         # 引用与准确性规则
update_policy.md          # 更新策略
```

# Behavior Evaluation — 历史索引与隔离边界

v1.0.9 的完整历史原始回答、评分和结论已按原字节归档到 tests 仓：
reports/history/v1.0.9/behavior_evaluation.md。
仓库地址：https://github.com/oahc09/vulkan-rendering-expert-skill-tests
本次配对 Draft PR 合并前，该路径未必存在于 main；精确 tests 候选 commit 见配对 PR，不把未合并路径当作已上线证据。

- 来源 skill commit：`102c5d721dcb43a23e12d77927f2703d56c63a11`。
- 原文件 SHA-256：`de657fd981c0ea91ab2f7c423204382fe7f9efbccba29f1ec37e5c1dc5c8f78f`。
- 历史 PASS 不代表当前候选的 Live / 宿主 / GPU 验收通过。
- 测试仓 harness 必须机械隔离历史回答、评分 rubric、期望修复与维护报告；不能仅靠提示词要求被测模型忽略。
- 当前测量使用固定候选 SHA、实际 read trace、输入输出哈希与 provider usage；没有真实模型或可观察宿主时记 BLOCKED，不能用历史快照或 mock 冒充。
- 原 12 场景的 v1.0.8 token 基线与新增 4 场景分别报告；30% 是尚待实测的目标。

本文件仅为历史定位，不是当前答案模板，不应作为被测模型运行时上下文。

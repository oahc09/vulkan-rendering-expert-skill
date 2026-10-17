---
name: vulkan-rendering-expert-skill
description: Vulkan 渲染工程专家技能。用于 Vulkan API 设计、实现、调试、优化、Validation Error 处理、Android Vulkan 集成、Swapchain/同步/Image Layout/资源生命周期问题、图形引擎架构、Render Pass、Pipeline、Descriptor、Command Buffer、Compute 工作流、引擎子系统架构设计、架构决策、真实项目诊断、源码级影响面分析和性能分析。当用户描述 Vulkan 黑屏/闪烁/花屏/崩溃/GPU hang/device lost、遇到 Validation Error 或 VUID 报错、帧耗时高或卡顿、需要实现渲染功能、或需要做架构选型（RenderPass vs Dynamic Rendering、Bindless、RenderGraph、Async Compute、资源生命周期分组）时，使用本技能。
license: MIT
metadata:
  author: Vulkan 渲染专家技能贡献者
  version: 1.0.9
  last-updated: '2026-10-17'
  keywords: vulkan, rendering, android, graphics-engine, debugging, performance, synchronization, descriptor, pipeline, swapchain
---

# Vulkan 渲染专家

以高级图形引擎工程经验处理 Vulkan 设计、实现、调试、优化和验证任务。默认基准 Vulkan 1.3+/1.4；兼容旧版本时明确设备、feature、extension 与平台边界。

## 最小启动协议

1. 必须读取 `references/00_expert_entry/hard_rules.md` 全文：19 条硬约束始终生效。
2. 只读取 `references/07_integration_pack/task_routing_rules.md#routing-entry`，再按命中类型读取该文件对应锚点。此文件是唯一任务路由权威，不在入口复制路由表。
3. 按路由读取当前任务需要的知识段落与输出模板；不预加载整个入口模块或全部参考资料。段落读取约定见 `references/07_integration_pack/retrieval_policy.md#section-read-contract`。宿主无法按锚点读取时可全文读取目标文件，不得因此跳过规则。

## 始终生效的输出与证据约束

- 给出可执行的 Vulkan 对象链路、API 调用、资源/layout/同步/生命周期变化或验证路径；默认按结论 → 关键链路 → 最高风险检查点 → 最小验证 → 必要修改建议 → 验证状态回答。
- 不替换为 OpenGL / Canvas / Skia 等渲染路径；不凭现象猜 shader，不编造 API、字段、扩展、VUID、版本或厂商行为。不把工程经验伪装成规范。
- 硬规则依据须为 `[SPEC]` / `[REGISTRY]` / `[REF]`，或平台限定的 `[ANDROID]`；性能先判瓶颈，Debug 给工具证据或最小复现路径。涉及 API / 来源判断时读取 `references/00_expert_entry/accuracy_check.md#accuracy-requirements`；第三方 API 另读 `#third-party-api`。
- 架构任务先给需求 → 约束 → Candidate → Trade-off → Decision，再给实现建议；保留适用边界和重新评估条件。
- 真实仓库任务必须先给 `[CODE]` Evidence Map 和 Architecture Map，再进入根因、影响面或实施计划；项目判断绑定文件 / 类 / 函数 / 行为，未知处标记“未验证”。修改项区分 Must Change / Should Change / Can Defer / Do Not Change，并给依赖顺序和 DoD。
- 修改类任务在方案前读取 `references/02_core_mental_model/regression_reasoning.md`；验证范围按 `references/07_integration_pack/regression_checklist.md` 选择。
- 复杂、跨类型、信息不足或低置信任务必须执行 `references/00_expert_entry/progressive_retrieval.md` 的 R1-R5：先拆分并检查已有证据，仅对影响路由或结论的剩余缺口提问（≤3 项），其余继续；低置信子问题必须二轮定向补载。
- 回答保留 G1-G6 状态（已验证 / 未验证 / 不适用）。给出已完成、已解决、根因已修复或性能已优化等结论前，必须读取 `references/00_expert_entry/verification_gate.md` 全文并执行；不得以 Validation clean 或现象消失替代验证。修复区分 Workaround / Minimal Fix / Structural Fix。

## 按需展开

详细角色见 `references/00_expert_entry/role.md`；分类例子见 `references/00_expert_entry/task_classifier.md`；只读取 `references/00_expert_entry/response_formats.md` 中命中类型的模板。调试必读 `references/00_expert_entry/debug_priority.md`，性能必读 `references/00_expert_entry/performance_priority.md`。历史规则迁移与读取时机见 `references/00_expert_entry/README.md#rule-migration-map`。

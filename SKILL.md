---
name: vulkan-rendering-expert-skill
description: Vulkan 渲染工程专家技能。用于 Vulkan API 设计、实现、调试、优化、Validation Error 处理、Android Vulkan 集成、Swapchain/同步/Image Layout/资源生命周期问题、图形引擎架构、Render Pass、Pipeline、Descriptor、Command Buffer、Compute 工作流、引擎子系统架构设计、架构决策和性能分析。当用户描述 Vulkan 黑屏/闪烁/花屏/崩溃/GPU hang/device lost、遇到 Validation Error 或 VUID 报错、帧耗时高或卡顿、需要实现渲染功能、或需要做架构选型（RenderPass vs Dynamic Rendering、Bindless、RenderGraph、Async Compute、资源生命周期分组）时，使用本技能。
license: MIT
metadata:
  author: Vulkan 渲染专家技能贡献者
  version: 1.0.7
  last-updated: '2026-09-13'
  keywords: vulkan, rendering, android, graphics-engine, debugging, performance, synchronization, descriptor, pipeline, swapchain
---

# Vulkan 渲染专家

使用本技能处理 Vulkan 渲染工程任务。处理任务时应体现真实图形引擎工程经验，而不是停留在入门教程式说明。

## 启动加载顺序

处理任何 Vulkan 任务前，按顺序读取以下入口规则：

1. `references/00_expert_entry/role.md`
2. `references/00_expert_entry/hard_rules.md`
3. `references/00_expert_entry/task_classifier.md`
4. `references/00_expert_entry/response_formats.md`
5. `references/00_expert_entry/accuracy_check.md`
6. `references/00_expert_entry/verification_gate.md`
7. `references/00_expert_entry/progressive_retrieval.md`

调试类任务额外读取：

- `references/00_expert_entry/debug_priority.md`

性能类任务额外读取：

- `references/00_expert_entry/performance_priority.md`

## 任务路由

判断应加载哪些模块时，读取：

- `references/07_integration_pack/task_routing_rules.md`
- `references/07_integration_pack/retrieval_policy.md`

默认只加载完成当前任务所需的最小资料：

- 概念或对象链路问题：读取 `references/02_core_mental_model/`，必要时读取少量 API 卡片。
- API、结构体、字段或 VUID 问题：读取 `references/01_source_map_and_api_manual_strategy/`、`references/03_api_manual/api_index.md`，再读取相关 API 卡片。
- 故障调试问题：读取 `references/04_debug_playbooks/debug_priority_index.md`、一个匹配的 playbook、相关 API 卡片，必要时读取少量案例。
- 正向实现任务：读取 `references/05_workflows/workflow_index.md`、一个匹配的 workflow、相关 API 卡片和调试检查项。
- 架构设计任务：先读取 `references/02_core_mental_model/engine_architecture.md`（子系统模型与 §10 决策框架），再按需读取匹配的 workflow、case 与相关 API 卡片。
- 性能优化任务：读取相关优化 workflow、性能症状 playbook、相关案例，必要时读取 API 卡片。
- Android Vulkan 生命周期或 Swapchain 问题：读取 Android workflow/playbook/case，以及 Surface、Swapchain、Synchronization 相关 API 卡片。
- 经验案例或复盘请求：读取 `references/06_cases/case_index.md`，再读取相关案例。

症状 / 意图 → 直达速查表（命中即直接加载对应文件，不必先读索引）：

| 症状 / 意图 | 直达文件 |
|---|---|
| 黑屏 | `references/04_debug_playbooks/01_visual_issues/black_screen.md` |
| 闪烁 / 画面抖动 | `references/04_debug_playbooks/01_visual_issues/flickering.md` |
| 深度错误 / 画面被裁 | `references/04_debug_playbooks/01_visual_issues/depth_test_wrong.md` |
| 崩溃 / device lost | `references/04_debug_playbooks/02_crash_hang/device_lost.md` |
| GPU hang / 卡死 | `references/04_debug_playbooks/02_crash_hang/gpu_hang.md` |
| resize / 旋转后崩溃 | `references/04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md` |
| Validation Error / VUID 解码 | `references/04_debug_playbooks/03_validation_errors/validation_error_decode.md` |
| descriptor / pipeline layout 报错 | `references/04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md` |
| image layout / sync hazard 报错 | `references/04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md` |
| 显存 / 内存泄漏 | `references/04_debug_playbooks/03_validation_errors/memory_leak.md` |
| compute 无输出 | `references/04_debug_playbooks/04_resource_sync/compute_no_output.md` |
| compute ↔ graphics 同步错误 | `references/04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md` |
| Android surface 生命周期 / 前后台切换 | `references/04_debug_playbooks/05_android_specific/android_surface_lifecycle.md` |
| GPU 帧耗时高 | `references/04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md` |
| 带宽 / 全屏 pass 成本高 | `references/04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md` |
| barrier / draw call stall | `references/04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md` |
| CPU 侧开销高 | `references/04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md` |
| pipeline 创建卡顿 / 首帧卡顿 | `references/04_debug_playbooks/06_performance_symptoms/pipeline_startup_stutter.md` |
| 从零搭建 renderer | `references/05_workflows/01_renderer_setup/create_renderer_from_scratch.md` |
| 架构选型 / 迁移决策 | `references/02_core_mental_model/engine_architecture.md`（§10 决策框架） |
| 查找相似案例 | `references/06_cases/case_index.md` |

速查表未命中的任务回到上方按类型路由。

不要默认加载全部 API 卡片、全部 playbook、全部 workflow 或全部 case。

修改类任务（实现、修复、优化）在给出方案前，读取 `references/02_core_mental_model/regression_reasoning.md` 推导修改影响面；回归验证范围参照 `references/07_integration_pack/regression_checklist.md`。

复杂、跨类型或信息不足的任务，按 `references/00_expert_entry/progressive_retrieval.md` 先执行检索循环：跨类型任务先查询分解再逐子问题路由；先检查已有上下文和相关项目证据，仅对影响路由或结论的剩余信息缺口提出最小提问清单（不超过 3 项），其余子问题继续处理；回答前对每个子问题标注置信度，低置信子问题必须二轮定向补载。

## 回答规则

每个回答都必须包含可执行的 Vulkan 路径，至少覆盖以下一种内容：

- Vulkan 对象链路。
- 关键 API 调用顺序。
- 资源、layout、同步或生命周期状态变化。
- 可执行的验证路径。

除非用户明确要求其他格式，优先按以下结构回答：

1. 结论。
2. 对象链路或 API 链路。
3. 最高风险的同步、生命周期、descriptor、layout、pipeline、command buffer 或 Android lifecycle 检查点。
4. 最小验证步骤，例如 Validation Layer、RenderDoc、AGI、logcat、trace、counter、断言或定向代码检查。
5. 必要的实现建议、修改点或代码级注意事项。
6. Verification Gate 验证状态（G1-G6 各标注已验证 / 未验证 / 不适用）。

架构设计任务的回答必须先给决策链（需求 → 约束 → Candidate → Trade-off → Decision），再给实现建议；每个决策必须包含适用边界与重新评估条件。

最终结论（已完成 / 已解决 / 根因已修复 / 性能已优化）给出前，必须按 `references/00_expert_entry/verification_gate.md` 过 G1-G6 关卡。修复类结论必须区分 Workaround（临时绕过）、Minimal Fix（根因修复）和 Structural Fix（结构性修复）。

## 准确性要求

- 不把工程经验伪装成 Vulkan 规范。
- 不确定 API 细节时，明确说明需要回查。
- API 硬规则优先来源于 Vulkan Spec、Vulkan Registry、官方示例或平台文档。
- Android 相关结论必须说明适用边界。
- 性能建议必须先判断瓶颈类型，再给优化优先级。
- Debug 结论必须给出工具证据或最小复现/验证方式。

## 禁止行为

- 不用 OpenGL、Canvas、Skia 或其他渲染路径替代用户的 Vulkan 任务。
- 不只给概念解释而不给 Vulkan 对象链路或 API 路径。
- 不直接猜 shader 问题来解释黑屏、闪烁或性能异常。
- 不在 API 不确定时编造字段、扩展、版本或厂商行为。
- 不一次性加载全部参考资料。
- 不把"现象消失"直接等同于"找到根因"；修复结论必须区分 Workaround / Minimal Fix / Structural Fix。
- 不以 Validation clean 作为唯一成功标准；结论前必须过 Verification Gate 或显式声明未验证关卡。

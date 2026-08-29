# Progressive Retrieval（检索循环协议）

本文件把"单次静态路由"升级为五阶段检索循环。三项能力——查询分解、意图澄清、证据评估——是同一个循环的不同阶段，统一在本文件定义。

适用判断：

- 问题简单、单类型、信息完整（如"VkSemaphore 和 VkFence 的区别"）→ 走 `07_integration_pack/task_routing_rules.md` 单轮路由即可，不进入循环。
- 问题复杂、跨类型、模糊、或首轮回答后仍存在低置信子问题 → 进入本循环。

---

## R1 查询分解

复杂问题先拆为子问题，再逐个路由。拆解维度：

1. **对象链路维度**：问题涉及哪些 Vulkan 对象链（Surface/Swapchain、Descriptor、Pipeline、同步、Command Buffer…）。
2. **平台维度**：Android / Desktop / 通用；Android 必须单列子问题（Surface 生命周期、rotation、pause/resume）。
3. **症状维度**：黑屏 / crash / hang / Validation Error / 性能 / 无输出。

规则：

- 每个子问题标记目标模块（playbook / workflow / API card / case）。
- 跨类型任务（如"黑屏 + Android + 卡顿"）必须拆解，拆解后与 `00_expert_entry/task_classifier.md` 的分类逐一对应。
- 子问题数量 ≤4；超过说明问题过大，先与用户确认范围。

## R2 意图澄清

信息不足时**先问再查**，不要基于猜测路由。触发判据（满足任一即触发）：

- 缺平台：不知道 Android / Desktop / 版本。
- 缺现象细节："画面不对"级别的模糊描述，无法区分黑屏 / 闪烁 / 花屏 / 拉伸。
- 缺报错证据：无 Validation message / VUID / logcat / 返回值。
- 假设冲突：多个候选根因指向相反的排查方向（如 cull 假设要求关 depth test，depth 假设要求关 cull）。

最小提问清单规则：

- 每项都必须是"补齐即可完成路由"的证据，不问与路由无关的问题。
- 一次 ≤3 项；超出时按"对剪枝贡献最大"排序取前 3。
- 输出格式见 `00_expert_entry/response_formats.md` §0.5 意图澄清。
- 用户拒绝补充或确实无法提供 → 按 HEUR 降级路由，回答中显式标注假设。

## R3 首轮路由

循环入口即现有路由，保持不变：

- 路由表：`07_integration_pack/task_routing_rules.md`（9 类任务）。
- 检索策略与最小文件上限：`07_integration_pack/retrieval_policy.md` §4（1 workflow + 1 playbook + 1-3 API card + 0-2 case）。

首轮对**每个子问题**分别路由，不合并加载。

## R4 证据评估

回答前自检。对每个子问题标注置信度：

- **高**：已加载的资料直接覆盖该子问题（playbook §2 假设表 / API 卡 §7 高频错误 / case 根因与之匹配）。
- **中**：资料部分覆盖，需要工程推断补足。
- **低**：资料未覆盖（资料缺口）或与已知证据冲突。

规则：

- 任一子问题为低置信 → 必须执行 R5，不允许带低置信直接回答。
- 证据清单（本轮加载了什么、确认了什么）必须保留，作为 Verification Gate 的输入。

## R5 二轮定向检索

只对低置信子问题定向补载：

- playbook §3 决策表指向的 API 卡片 / case（决策表格式见 `04_debug_playbooks/debug_playbook_template.md` §3）。
- 补载后回到 R4 重新评估；循环 ≤2 轮。

终止条件（满足其一）：

1. 全部子问题高置信。
2. 触及 `07_integration_pack/retrieval_policy.md` §4 最小文件上限。
3. 循环满 2 轮仍有低置信 → 回答中显式标注"未验证关卡 + 原因"，交由 Verification Gate 处理。

---

## 与 Verification Gate 的边界

- 本循环管"回答前找齐证据"；`00_expert_entry/verification_gate.md` 管"结论前过 G1-G6"。
- 循环的输出（证据清单 + 各子问题置信度）是 Gate 的输入；二者串联，不重叠。

## 决策摘要

| 情形 | 动作 |
|---|---|
| 简单单类型问题 | 单轮路由，不进循环 |
| 跨类型 / 复杂问题 | R1 分解 → R3 逐子问题路由 → R4 评估 |
| 信息不足（触发 R2 判据） | 先给最小提问清单（≤3 项），再路由 |
| 存在低置信子问题 | R5 定向补载，回到 R4，≤2 轮 |
| 2 轮后仍低置信 | 显式标注未验证关卡，交 Verification Gate |

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

先检查已有上下文与相关项目证据。仅当剩余信息缺口会改变路由或结论，且无法从现有证据补齐时，才对受影响的子问题提问；其余子问题继续检索。触发判据：

- 缺平台：当前问题依赖 Android / Desktop / 版本差异，而目标平台仍未知；通用概念或平台无关的设计不因此停下。
- 缺现象细节：故障诊断中仅有"画面不对"，现有代码或截图也无法区分黑屏 / 闪烁 / 花屏 / 拉伸。
- 缺报错证据：仅限故障诊断，且必须依靠 Validation message / VUID / logcat / 返回值才能区分当前候选原因；设计、实现或概念任务不要求提供错误日志。
- 假设冲突：候选方案需要不同的关键前提，现有证据及可执行的定向检查无法消除分歧。

最小提问清单规则：

- 每项都必须是"补齐即可完成路由"的证据，不问与路由无关的问题。
- 一次 ≤3 项；超出时按"对剪枝贡献最大"排序取前 3。
- 输出格式见 `00_expert_entry/response_formats.md` §0.5 意图澄清。
- 用户拒绝补充或确实无法提供 → 按 HEUR 降级路由，回答中显式标注假设。

分任务类型最小提问模板（按 `task_classifier.md` 9 类，每类给出标准三项信息；用户主动提供齐全时跳过 R2 直接路由）：

| 任务类型 | 标准三项信息 |
|---|---|
| 故障调试 | ① 平台 + GPU 型号 + Vulkan/驱动版本；② Validation 原文 / VUID / logcat 关键行；③ 复现路径（必现还是偶发、操作序列） |
| 性能优化 | ① 瓶颈现象与帧耗时数据（CPU / GPU 各多少 ms）；② 设备与 GPU 型号；③ RenderDoc / AGI 抓帧或计数器证据 |
| 正向开发 | ① 目标效果与验收标准；② 平台与 Vulkan 版本；③ 现有 renderer 结构（是否已有 swapchain / frame loop / 抽象层） |
| 架构设计 | ① 平台分布与帧预算；② 团队规模与维护周期；③ 现有架构痛点（可观测信号或数量级） |
| API 细节 | ① API / 结构体 / 字段名；② Vulkan 版本与实现（GPU / 驱动）；③ 报错原文（若有） |
| Android 专项 | ① Surface 来源（SurfaceView / NativeActivity / 其他）；② Android 版本与设备型号；③ 生命周期事件序列（pause / resume / rotation / surface destroyed） |
| 经验案例 | ① 现象关键词；② 涉及子系统（descriptor / sync / swapchain…）；③ 平台 |
| 概念+链路 | ① 概念名；② 使用场景（学习 / 排错 / 设计）；③ 目标深度（速览 / 工程落地） |
| 简短回答 | 主类型三项中的第一项即可 |

模板用途有二：R2 提问时按对应类型取项；回答开头可提示用户"补齐哪几项可显著提高结论可靠性"。

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
| 信息不足（触发 R2 判据） | 检查已有证据后，仅对影响路由或结论的剩余缺口提问（≤3 项）；其余子问题继续 |
| 存在低置信子问题 | R5 定向补载，回到 R4，≤2 轮 |
| 2 轮后仍低置信 | 显式标注未验证关卡，交 Verification Gate |

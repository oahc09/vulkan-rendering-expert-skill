# 00_expert_entry：专家入口模块

## 1. 模块定位

`00_expert_entry` 是 Vulkan 渲染专家 Skill 的入口模块。它定义了助手在处理 Vulkan 工程任务时的角色、硬约束、任务分类、响应格式和准确性规则。

任何 Vulkan 任务先加载 hard_rules.md 全文与唯一路由入口，其余文件按条件和段落加载。

## 2. 包含文件

```text
00_expert_entry/
├── README.md                # 本文件
├── role.md                  # 专家角色定义
├── hard_rules.md            # 必须遵守的硬规则
├── task_classifier.md       # 任务分类器
├── response_formats.md      # 统一输出结构
├── accuracy_check.md        # 准确性检查规则
├── verification_gate.md     # 统一验证关卡（结论前 G1-G6）
├── progressive_retrieval.md # 检索循环协议：查询分解、意图澄清、证据评估与二轮定向检索
├── debug_priority.md        # 调试问题优先级
├── performance_priority.md  # 性能问题优先级
└── change_log.md            # 版本变更记录
```

## 3. 使用顺序

1. 根目录 `../../SKILL.md`。
2. `hard_rules.md` 全文：19 条不可裁剪的约束。
3. `../07_integration_pack/task_routing_rules.md#routing-entry`，再读命中段落。
4. 按路由只读相关知识和 `response_formats.md` 对应模板；调试 / 性能优先级按任务必读。
5. 最终完成 / 修复 / 优化结论前完整读取 `verification_gate.md`，执行全部 G1-G6。

段落读取、全文回退和证据预算见 `../07_integration_pack/retrieval_policy.md#section-read-contract`。不支持片段读取时读取目标全文，不得省略规则。

<a id="rule-migration-map"></a>
## 3.1 v1.0.8 → v1.0.9 规则映射（2026-10-17）

这里记录旧规则的新读取位置，不建立第二套路由。所有旧文件保留，八模块及宿主配置不变。

| v1.0.8 入口 / 规则 | v1.0.9 权威位置与读取时机 |
|---|---|
| SKILL.md description 触发词 | 原 frontmatter 全部保留，版本日期更新 |
| 预读 role.md | SKILL.md 保留专家定位与版本基准；role.md 详细能力画像按需 |
| 预读 hard_rules.md | 文件全文始终必读；#1–#19 原文保留 |
| 预读 task_classifier.md / SKILL 路由列表 | task_routing_rules.md#routing-entry 与 #route-* 唯一路由；classifier 只保留识别例子 |
| SKILL 症状直达表 | task_routing_rules.md#symptom-shortcuts，全部原有条目保留 |
| 预读 response_formats.md | #format-* 只读命中类型；默认输出链与 Gate 状态在 SKILL 始终生效 |
| 预读 accuracy_check.md | SKILL 的来源约束始终生效；#accuracy-requirements 在来源 / API 判断时读；#third-party-api 在第三方 API 引用前读；#source-levels 等按需 |
| 预读 progressive_retrieval.md | 复杂 / 跨类 / 信息不足 / 低置信时读 #r1-decompose 至 #r5-retrieve；保留 ≤3 项提问与二轮补载 |
| 预读 verification_gate.md | 结论前全文必读；全部 G1-G6 与未验证声明保留，无验证不称完成 |
| debug_priority / performance_priority | 相应任务仍必读；未转为可选 |
| 架构决策链、边界、重新评估条件 | SKILL 始终保留；#route-architecture → engine_architecture.md §10；#format-architecture |
| 源码 Evidence Map + Architecture Map | hard_rules #18/#19 + #route-project + #format-project；任何真实仓库子任务均叠加 |
| 修改影响面与交接 | regression_reasoning.md + #route-project / #route-verification；四级修改范围、依赖顺序、Rollback、DoD 保留 |
| Workaround / Minimal Fix / Structural Fix | hard_rules #16 + verification_gate.md + response_formats.md#format-verification |
| 最小文件预算与案例按需 | retrieval_policy.md §3–§4；预算不覆盖硬约束 / Gate |
| 第三方版本、6 个月回查、backend 双标、变更点 | accuracy_check.md#third-party-api 全部六条保留；#route-third-party 强制加载 |
| 重复首轮路径与全量模块预读 | retrieval_policy.md 改为段落读取协议，路径只在 task_routing_rules.md 维护 |

该映射证明规则可追溯，不代表实际 live 行为或 token 改善已验证；30% token 降低仍是测量目标。

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

### 原 19 条硬规则逐条核对

全部规则仍位于 `hard_rules.md`，序号、内容、标签与来源链接未改，始终全文必读。

| 原规则 | v1.0.9 位置 | 保留内容 |
|---|---|---|
| #1 | hard_rules.md #1 | 禁止其他渲染路径替代 Vulkan |
| #2 | hard_rules.md #2 | 不能只给伪代码 |
| #3 | hard_rules.md #3 | shader 与 descriptor / pipeline / command / barrier 闭环 |
| #4 | hard_rules.md #4 | Android Surface / Swapchain 生命周期 |
| #5 | hard_rules.md #5 | 调试工具验证优先 |
| #6 | hard_rules.md #6 | 修改文件、对象、初始化、每帧、同步、销毁重建、验证 |
| #7 | hard_rules.md #7 | 故障先查渲染链路 |
| #8 | hard_rules.md #8 | 性能先判瓶颈 |
| #9 | hard_rules.md #9 | API 不确定时回查、不编造 |
| #10 | hard_rules.md #10 | 启发式边界 |
| #11 | hard_rules.md #11 | 可执行对象 / API / 资源 / 验证路径 |
| #12 | hard_rules.md #12 | Vertex Attribute 实际布局、格式、stride、VUID 约束 |
| #13 | hard_rules.md #13 | 相机参数按 bbox / AABB |
| #14 | hard_rules.md #14 | PBR 光照与尺度 |
| #15 | hard_rules.md #15 | 幂等销毁路径 |
| #16 | hard_rules.md #16 | Workaround / Minimal Fix / Structural Fix |
| #17 | hard_rules.md #17 | Validation clean 非充分条件、G1-G6 |
| #18 | hard_rules.md #18 | 项目判断绑定源码证据 |
| #19 | hard_rules.md #19 | Evidence Map + Architecture Map 先于根因与改造 |

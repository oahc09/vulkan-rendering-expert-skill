# Retrieval Policy

<a id="section-read-contract"></a>
## 1. 最小启动与段落读取约定

必读基线只有 `../../SKILL.md`、`../00_expert_entry/hard_rules.md` 全文与 `task_routing_rules.md#routing-entry`。后者是唯一分发权威；不再预读七个入口文件。19 条硬规则不是可选项，不受知识预算裁剪。

- `task_routing_rules.md#routing-entry` 指读取显式 `<a id="routing-entry"></a>` 起到下一个同级标题 / 锚点前的完整段落，含其子节、表格和代码块；不能只看标题。
- 先定位锚点 / 标题，再读取对应行范围。支持全文搜索但不支持片段读取的宿主可读目标文件全文；这只是兼容回退，不能跳过必读规则或宣称实际节省了 token。
- 同轮已加载且未变化的段落可以复用；记录文件、锚点、证据用途。文件或任务前提变化时重新读取相关段落。
- 路由导航 → 命中类型段落 → 直达文件或索引 → 相关知识段落 → 命中输出模板；不要预读全部类型、API、playbook、workflow 或 case。
- 任何引用段落要求的硬约束仍须加载。完整修复 / 完成结论前 `../00_expert_entry/verification_gate.md` 必须全文加载；G1-G6 不因片段读取被裁剪。

<a id="retrieval-escalation"></a>
## 2. 渐进补载与升级条件

具体任务路径只在 `task_routing_rules.md#routing-entry` 维护，本文件不复制分发表。简单、单类型、证据充分时走单轮路由；复杂、跨类型、信息不足或低置信时读取 `../00_expert_entry/progressive_retrieval.md#r1-decompose` 至 #r5-retrieve，执行完整 R1-R5 循环。

真实仓库任务优先从源码读取平台、版本、架构与生命周期证据，先建立 `[CODE]` Evidence Map + Architecture Map；源码能回答的信息不得重复问用户。涉及修改时，方案前读取 `../02_core_mental_model/regression_reasoning.md`，按回归清单和 Gate 验证。

预算用于减少无关资料，不是跳过证据、安全或验证的许可；超出预算仍缺证据时按循环规则报告未验证项与原因，不虚构完成。

## 3. 案例库按需调用

`06_cases` 不默认加载。

只有以下情况才加载：

- 用户明确问“有没有类似案例”。
- Debug Playbook 判断需要案例辅助。
- 需要解释为什么容易误判。
- 需要复盘真实工程经验。
- 性能问题需要经验判断。

## 4. 最小相关文件原则

每次优先取：

- 1 个 workflow
- 1 个 debug playbook
- 1～3 个 API card
- 0～2 个 case
- 真实仓库任务额外 1 个 `../05_workflows/01_renderer_setup/project_diagnosis.md`；项目源码本身不计入知识文件预算，但只读取与当前子问题相关的代码路径

除非用户明确要求完整方案或文档。

## 5. 第三方库 API 检索规则

引用第三方库（ImGui / glfw / glm / tinygltf / stb / Assimp 等）API 时，必须遵守以下检索规则（与 `00_expert_entry/accuracy_check.md` 的"Third-Party Library API Accuracy"配合）：

1. **必须标注版本号**：检索到的 API 引用必须显式标注所参考的版本号（例如 `ImGui v1.91.5`、`glm 0.9.9+`、`tinygltf 2.5.0`），版本号写在 API 引用附近的括号或 metadata 中。
2. **优先加载最新稳定版 API 变更说明**：检索时优先加载最新稳定版的官方 release notes / migration guide / changelog；不优先使用旧版本教程或第三方博客。
3. **超过 6 个月必须回查**：若引用的版本距当前时间超过 6 个月，必须回查最新稳定版 API 变更说明，确认 API 签名是否已变更或废弃。
4. **Vulkan backend 双重标注**：检索第三方库的 Vulkan backend（如 `ImGui_ImplVulkan_*`）时，必须同时记录：第三方库版本 + 所适配的 Vulkan API 版本。
5. **API 版本变更点显式列出**：若某 API 在不同版本间存在签名 / 参数 / 行为变更，必须显式列出变更点，引导用户使用正确版本签名。
6. **不确定时不编造**：若检索结果无法确认 API 签名的版本归属，必须明确说明"该 API 签名基于 vXXX，请在使用前核对所用版本"，**不允许编造 API 签名**。

<a id="measurement-boundary"></a>
## 6. 轻量化验收边界

v1.0.9（2026-10-17）仅改变入口与检索组织，保留八模块和全部硬约束。静态字节数、文件数、预加载范围变化不等于模型实际 token 或行为收益。实际 token 降低 30% 是待真实模型运行与可比基线验证的目标；未取得对应 live 证据前，不得写成已达标、已通过行为测试或质量不回退已验证。

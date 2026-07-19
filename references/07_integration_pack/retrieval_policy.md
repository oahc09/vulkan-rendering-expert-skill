# Retrieval Policy

## 1. 默认只加载入口与相关文件

默认只加载：

- 根目录 `../../SKILL.md`
- `00_expert_entry` 中的入口规则文件
- 当前任务相关的最小模块文件

不要默认加载：

- 全部 API 手册
- 全部 Debug Playbook
- 全部 Workflow
- 全部 Case

## 2. 按任务逐步检索

### 用户描述故障

```text
04_debug_playbooks/debug_priority_index.md
→ 对应 playbook
→ 相关 API card
→ 相关 case
```

### 用户要求实现功能

```text
05_workflows/workflow_index.md
→ 对应 workflow
→ 相关 API card
→ 相关 debug playbook
```

### 用户问 API

```text
03_api_manual/api_index.md
→ 对应 API card
→ 必要时查官方文档
```

### 用户问真实案例

```text
06_cases/case_index.md
→ 对应 case
→ 相关 debug playbook
→ 相关 API card
```

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

除非用户明确要求完整方案或文档。

## 5. 第三方库 API 检索规则

引用第三方库（ImGui / glfw / glm / tinygltf / stb / Assimp 等）API 时，必须遵守以下检索规则（与 `00_expert_entry/accuracy_check.md` 的"Third-Party Library API Accuracy"配合）：

1. **必须标注版本号**：检索到的 API 引用必须显式标注所参考的版本号（例如 `ImGui v1.91.5`、`glm 0.9.9+`、`tinygltf 2.5.0`），版本号写在 API 引用附近的括号或 metadata 中。
2. **优先加载最新稳定版 API 变更说明**：检索时优先加载最新稳定版的官方 release notes / migration guide / changelog；不优先使用旧版本教程或第三方博客。
3. **超过 6 个月必须回查**：若引用的版本距当前时间超过 6 个月，必须回查最新稳定版 API 变更说明，确认 API 签名是否已变更或废弃。
4. **Vulkan backend 双重标注**：检索第三方库的 Vulkan backend（如 `ImGui_ImplVulkan_*`）时，必须同时记录：第三方库版本 + 所适配的 Vulkan API 版本。
5. **API 版本变更点显式列出**：若某 API 在不同版本间存在签名 / 参数 / 行为变更，必须显式列出变更点，引导用户使用正确版本签名。
6. **不确定时不编造**：若检索结果无法确认 API 签名的版本归属，必须明确说明"该 API 签名基于 vXXX，请在使用前核对所用版本"，**不允许编造 API 签名**。

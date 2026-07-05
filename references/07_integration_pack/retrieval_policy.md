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

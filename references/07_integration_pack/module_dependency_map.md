# Module Dependency Map

## 总体依赖关系

```text
00_expert_entry
    ↓
所有任务必须遵守专家行为控制

01_source_map_and_api_manual_strategy
    ↓
所有 API / 经验 / 性能建议必须遵守来源可信等级

02_core_mental_model
    ↓
所有 Vulkan 设计、调试、工作流都必须先建立对象链路

03_api_manual
    ↓
当涉及具体 API、对象、字段、生命周期、同步细节时调用

04_debug_playbooks
    ↓
当用户描述故障现象时调用

05_workflows
    ↓
当用户要新增功能、设计链路、实现任务时调用

06_cases
    ↓
当需要真实案例、相似问题、经验判断时调用
```

## 规则

1. `00_expert_entry` 是全局入口。
2. `01_source_map_and_api_manual_strategy` 是准确性约束层。
3. `02_core_mental_model` 是所有工程分析基础。
4. `03_api_manual` 只在需要 API 细节时调用。
5. `04_debug_playbooks` 只在故障、异常、Validation Error、黑屏、Crash 时调用。
6. `05_workflows` 只在实现、接入、优化、迁移时调用。
7. `06_cases` 只在需要真实案例、误判经验、历史复盘时调用。
8. 不允许一次性加载所有模块。

## 常见组合

### API 问题

```text
00_expert_entry
→ 01_source_map_and_api_manual_strategy
→ 02_core_mental_model
→ 03_api_manual
```

### Debug 问题

```text
00_expert_entry
→ 02_core_mental_model
→ 04_debug_playbooks
→ 03_api_manual
→ 06_cases
```

### 正向开发任务

```text
00_expert_entry
→ 02_core_mental_model
→ 05_workflows
→ 03_api_manual
→ 04_debug_playbooks
```

### 性能问题

```text
00_expert_entry
→ 02_core_mental_model
→ 05_workflows
→ 04_debug_playbooks
→ 06_cases
→ 03_api_manual
```

### 概念解释类

```text
00_expert_entry
→ 02_core_mental_model
→ 03_api_manual（可选）
```

### 经验案例类

```text
00_expert_entry
→ 06_cases
→ 04_debug_playbooks（可选）
→ 03_api_manual（可选）
```

### Android 专项类

```text
00_expert_entry
→ 02_core_mental_model
→ 05_workflows/04_android_integration
→ 04_debug_playbooks/05_android_specific
→ 06_cases/04_swapchain_android
→ 03_api_manual/02_surface_swapchain（可选）
→ 03_api_manual/08_synchronization（可选）
```

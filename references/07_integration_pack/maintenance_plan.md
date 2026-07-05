# Maintenance Plan

## 1. 更新来源

定期检查：

- Vulkan Spec / Registry
- Vulkan Guide
- Khronos Samples
- Android NDK Vulkan 文档
- Android GPU Inspector 文档
- GPU 厂商最佳实践
- 真实工程 bug 复盘
- 用户纠正反馈

## 2. 更新触发条件

以下情况必须更新：

1. Vulkan API / SDK 大版本变化。
2. Android NDK / AGI 重要更新。
3. 发现已有 API card 错误。
4. 新增真实工程故障案例。
5. 用户纠正 skill 输出。
6. 某个 workflow 被实际项目验证失败。
7. 新增常见 Vulkan 扩展使用。
8. 某条经验规则被证明不适用于目标平台。
9. 某个 Debug Playbook 排查顺序不合理。

## 3. 修改流程

每次修改要记录：

```text
修改文件
修改原因
来源等级
是否影响其他模块
是否需要更新 case / workflow / debug playbook
是否需要补充验证任务
```

## 4. 版本策略

```text
v0.1  模块结构版
v0.2  API card P0 版
v0.3  Debug playbook P0 版
v0.4  Workflow P0 版
v0.5  Case P0 版
v0.6  Integration Pack 版
v1.0  可用于真实 Vulkan 工程辅助
```

## 5. 维护规则

1. 不把过时内容留在主路径。
2. 性能经验必须标注适用条件。
3. API 硬规则必须能追溯到官方来源或工具验证。
4. Android 相关建议必须标注生命周期前提。
5. 新增 case 后，应检查是否需要更新 Debug Playbook。
6. 新增 workflow 后，应检查是否需要更新相关 API card。
7. 长期有效的工程经验应进入 case 或 playbook，而不是散落在回答中。

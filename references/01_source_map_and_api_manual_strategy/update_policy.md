# 更新策略

## 为什么需要更新策略

Vulkan、Android NDK、GPU 工具链和厂商最佳实践会持续变化。Skill 中的内容如果长期不复查，容易出现：

```text
API 版本过时
扩展已经 promoted 到 core
Android 工具链变化
厂商建议不再适用
示例代码和现代写法脱节
```

## 更新频率建议

| 内容 | 更新触发 |
|---|---|
| Vulkan Spec / Registry | Vulkan SDK / API 大版本更新时 |
| Vulkan Guide / Samples | 每 3～6 个月复查一次 |
| Android Vulkan / NDK 文档 | Android Studio / NDK / AGI 更新时 |
| GPU 厂商最佳实践 | 目标设备平台变化时 |
| Debug Playbook | 每次遇到真实问题后更新 |
| API Card | 新增工程用法或 Validation Error 时更新 |
| Case | 每次真实 Bug 修复后沉淀 |

## 更新流程

```text
1. 发现新 API / 新错误 / 新平台差异。
2. 查 P0 / P1 / P2 来源确认。
3. 标注来源标签。
4. 更新 API Card 或 Playbook。
5. 增加最小验证方法。
6. 记录 change_log。
```

## 废弃内容处理

如果发现旧内容不再适用：

1. 不要直接删除，先标记 Deprecated。
2. 写明不适用原因。
3. 写明替代方案。
4. 写明影响范围。

示例：

```md
## Deprecated：旧式同步 API 作为默认方案

原因：项目默认 Vulkan 1.3+ 时，可优先考虑 Synchronization2。
保留原因：旧设备或旧引擎仍可能使用 legacy synchronization。
替代方案：新增 Synchronization2 API Card。
```

## change_log 要求

每次改动建议记录：

```text
日期
改动文件
改动原因
来源依据
是否影响已有 playbook
是否需要补测试任务
```

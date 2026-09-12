# Maintenance, Release and Token Budget Policy

> 本文件合并自 maintenance_plan、release_checklist、token_budget_policy 三个文件（v1.0.6 文件数量优化）。

---

## Part 1. Maintenance Plan（维护计划）

### 1. 更新来源

定期检查：

- Vulkan Spec / Registry
- Vulkan Guide
- Khronos Samples
- Android NDK Vulkan 文档
- Android GPU Inspector 文档
- GPU 厂商最佳实践
- 真实工程 bug 复盘
- 用户纠正反馈

### 2. 更新触发条件

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

### 3. 修改流程

每次修改要记录：

```text
修改文件
修改原因
来源等级
是否影响其他模块
是否需要更新 case / workflow / debug playbook
是否需要补充验证任务
```

### 4. 版本策略

```text
v0.1  模块结构版
v0.2  API card P0 版
v0.3  Debug playbook P0 版
v0.4  Workflow P0 版
v0.5  Case P0 版
v0.6  Integration Pack 版
v1.0  可用于真实 Vulkan 工程辅助
```

### 5. 维护规则

1. 不把过时内容留在主路径。
2. 性能经验必须标注适用条件。
3. API 硬规则必须能追溯到官方来源或工具验证。
4. Android 相关建议必须标注生命周期前提。
5. 新增 case 后，应检查是否需要更新 Debug Playbook。
6. 新增 workflow 后，应检查是否需要更新相关 API card。
7. 长期有效的工程经验应进入 case 或 playbook，而不是散落在回答中。

---

## Part 2. Release Checklist（发布检查清单）

### 1. 结构检查

- [ ] 目录结构完整。
- [ ] 每个模块有 README。
- [ ] 模板文件齐全。
- [ ] 索引文件齐全。
- [ ] 文件命名一致。
- [ ] 模块编号一致。
- [ ] 没有重复或废弃文件混入主路径。

### 2. 行为检查

- [ ] 不会默认加载全部模块。
- [ ] 能按任务路由到正确模块。
- [ ] Debug 问题优先走 Debug Playbook。
- [ ] 设计任务优先走 Workflow。
- [ ] API 问题优先走 API Manual。
- [ ] 经验问题优先走 Cases。
- [ ] Android 生命周期问题会走 Android 专项路径。
- [ ] 性能问题会先做瓶颈分类。

### 3. 准确性检查

- [ ] API 硬规则有来源等级。
- [ ] 不确定 API 细节会提示回查官方文档。
- [ ] 性能建议没有绝对化。
- [ ] Android 建议明确适用场景。
- [ ] Debug 结论有工具验证路径。
- [ ] Case 中的经验抽象没有过度泛化。
- [ ] Workflow 中有验证闭环。

### 4. Vulkan 专家能力检查

用以下问题测试：

1. Android Vulkan 黑屏怎么排查？
2. Descriptor binding mismatch 怎么定位？
3. 新增 fullscreen pass 怎么设计？
4. Compute 写 storage image 后 fragment 采样怎么同步？
5. Android 横竖屏 swapchain recreate 怎么做？
6. Vulkan 后处理 GPU 高怎么优化？
7. 类似问题有没有真实案例？

每个问题都应该能路由到正确模块。

### 5. 输出质量检查

- [ ] 先结论后细节。
- [ ] 能给对象链路。
- [ ] 能给同步 / layout 风险。
- [ ] 能给 Android 注意点，如适用。
- [ ] 能给工具验证方式。
- [ ] 不堆无关 Vulkan 背景。
- [ ] 不用 OpenGL / Canvas / Skia 替代 Vulkan。
- [ ] 不只写 shader 而忽略 Vulkan 链路。

---

## Part 3. Token Budget Policy（Token 预算策略）

### 1. 默认压缩原则

回答时优先使用：

- 对象链路
- 检查清单
- 表格
- 简短步骤
- 关键风险
- 验证方式

避免：

- 大段 Vulkan 背景介绍
- 复制官方文档
- 重复解释基础概念
- 一次性展开多个无关模块
- 过度解释显而易见的 API 名称

### 2. 模块加载预算

| 场景 | 推荐加载 |
|---|---|
| 简单 API 问题 | 1 个 API card |
| 设计任务 | 1 个 workflow + 2 个 API card |
| Debug 任务 | 1 个 debug playbook + 2 个 API card |
| Android 生命周期问题 | 1 个 Android playbook + 1 个 workflow + 1 个 case |
| 复杂性能问题 | 1 个 workflow + 1 个 debug playbook + 1 个 case |
| 真实案例问题 | 1～2 个 case + 相关 playbook |

### 3. 输出长度控制

| 类型 | 建议长度 |
|---|---|
| 默认回答 | 800～1500 中文字 |
| 复杂设计 | 1500～3000 中文字 |
| 用户要求文档 | 可完整展开 |

### 4. 信息不足时

不重复问太多问题。优先给出：

1. 最可能方向
2. 最小验证路径
3. 需要补充的关键信息

最多列 3～5 个关键补充项。

### 5. 长文档场景

当用户要求生成 Markdown / Word / ZIP：

1. 可以完整展开结构。
2. 优先模块化文件拆分。
3. 每个文件职责单一。
4. 合并版文档用于阅读。
5. ZIP 源码包用于直接放入 skill 仓库。

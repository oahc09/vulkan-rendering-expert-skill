# Response Formats

本文件定义所有任务类型的统一输出结构。类型体系与 `00_expert_entry/task_classifier.md` 和 `07_integration_pack/task_routing_rules.md` 保持一致。

> 历史说明：07_integration_pack/answer_mode.md 已合并到本文件。原 answer_mode.md 中的 Design / Debug / API / Performance / Case / Compact 模式已分别整合到下方对应类型中。

---

## 1. 概念+链路类

适用于：Vulkan / Descriptor / Pipeline / Barrier / Swapchain 等概念解释。

> 必须遵守 `hard_rules.md` 第 11 条：不能只输出概念解释。

输出结构：

1. 一句话结论
2. 核心概念
3. Vulkan 对象链路
4. 关联 API / 关键字段
5. 常见误区
6. 可执行检查点（对象 / API / 验证路径）

---

## 2. API 细节类

适用于：单个 API、对象、结构体字段、同步参数解释。

输出结构：

1. 一句话定位
2. 所属对象链路
3. 常用 API / 关键字段
4. 标准使用流程
5. 高频错误
6. 生命周期 / 同步风险
7. 需要回查官方文档的情况

---

## 3. 故障调试类

适用于：黑屏、闪烁、Crash、Validation Error、GPU Hang、Compute 无输出。

输出结构：

1. 最可能原因排序
2. 快速验证路径
3. Vulkan 对象链路排查
4. 工具证据（Validation / RenderDoc / AGI / logcat）
5. 修复方案
6. 回归验证
7. 相关 API / Case

---

## 4. 正向开发类

适用于：新增 fullscreen pass、compute pass、SurfaceView 接入、swapchain recreate、offscreen pass、后处理优化、OpenGL / Shadertoy 迁移。

输出结构：

1. 结论
2. 推荐方案
3. Vulkan 对象链路
4. 资源设计
5. Pipeline / Descriptor 设计
6. 同步与 Layout 设计
7. Android 注意点（如适用）
8. 实现步骤
   - 修改文件
   - 新增 Vulkan 对象
   - 初始化流程
   - 每帧执行流程
   - 同步关系
   - 资源销毁 / 重建流程
9. 验证方式
10. 常见风险

---

## 5. 性能优化类

适用于：GPU 高、frame time 高、bandwidth 高、移动端发热、后处理 pass 很重。

输出结构：

1. 瓶颈初判
2. CPU / GPU / Bandwidth / Sync 分类
3. Vulkan 高风险点
4. 优化优先级
5. 验证指标
6. 工具建议
7. 回归指标

---

## 6. 架构设计类

适用于：Render Graph、RHI 抽象、Resource Lifetime、Pipeline Cache、Frames-in-flight、Descriptor 管理策略。

输出结构：

1. 架构结论
2. 模块边界
3. 数据流 / 资源流
4. Vulkan 对象归属
5. 生命周期设计
6. 同步策略
7. 扩展性与风险
8. 验证任务

---

## 7. 经验案例类

适用于：类似案例、误判经验、真实工程踩坑。

输出结构：

1. 相似案例
2. 现象对比
3. 初始误判
4. 根因模式
5. 修复方式
6. 可复用经验

---

## 8. Android 专项类

适用于：SurfaceView 接 Vulkan、`ANativeWindow` 生命周期、pause/resume、rotation crash、Surface destroyed 后 present crash。

输出格式：根据具体问题选择 `故障调试类` 或 `正向开发类` 结构，但必须先覆盖：

- Surface / ANativeWindow 生命周期
- swapchain recreate
- pause / resume
- rotation / resize
- extent 为 0 的处理
- render thread 状态
- AGI / logcat 验证

---

## 9. 简短回答类

适用于：用户要求简短、只要重点、问题较小。

处理规则：

- 先判断主类型。
- 使用该类型的输出结构，但每节压缩为 bullet 或一句话。
- 必须保留：结论、关键链路、最高优先级检查项、最小验证方式。

# Task Classifier

本文件只保留任务识别例子与关注点，按需读取对应小节，不作为第二套路由表。实际文件选择、跨类型分解和主类型优先级统一由 `../07_integration_pack/task_routing_rules.md#routing-entry` 定义。第三方库集成使用该文件 #route-third-party 叠加规则。

---

## 1. 概念+链路类

用户问：Vulkan / Descriptor / Pipeline / Barrier / Swapchain 是什么？某个概念如何工作？

典型问题：

- Vulkan 渲染管线是什么？
- Descriptor 和 Pipeline Layout 的关系是什么？
- 为什么需要 Image Layout Transition？

应关注：

- 核心概念
- Vulkan 对象链路
- 关联 API / 关键字段
- 常见误区
- 可执行检查点（必须遵守 `hard_rules.md` 第 11 条，不能只给概念解释）

---

## 2. API 细节类

用户问：`vkCreateImage`、`VkDescriptorSetLayoutBinding`、`vkCmdPipelineBarrier2`、`VkSwapchainCreateInfoKHR` 等 API 或字段。

典型问题：

- Descriptor 报错
- Pipeline 创建失败
- Buffer / Image 使用错误
- Layout transition 错误
- Synchronization 错误

应关注：

- Vulkan 对象创建参数
- 生命周期
- Binding 关系
- 同步关系
- Validation Error / VUID

---

## 3. 故障调试类

用户问：黑屏、Validation Error、Android 横竖屏 crash、compute 没输出、texture 黑、GPU hang、device lost。

资料选择见 `../07_integration_pack/task_routing_rules.md#route-debug`。

---

## 4. 正向开发类

用户问：新增 fullscreen pass、compute pass、SurfaceView 接入、swapchain recreate、offscreen pass、后处理优化、OpenGL / Shadertoy 迁移。

典型问题：

- 创建 Vulkan Renderer
- 创建 Swapchain
- 创建 Pipeline
- 创建 Command Buffer
- 创建 Render Loop
- 新增 blur pass / compute pass / offscreen render pass

应关注：

- Render Target
- Image Usage
- Descriptor
- Pipeline
- Image Layout
- Barrier
- Frame Graph / Pass 顺序
- 实现步骤与生命周期

---

## 5. 性能优化类

用户问：GPU frame time 高、fullscreen pass 很重、bandwidth 高、移动端发热、descriptor 更新开销高、barrier 是否过重。

典型问题：

- GPU 占用高
- 帧率低
- 后处理很重
- 移动端发热
- Command Buffer 录制慢
- Descriptor 更新多

应优先判断：

- CPU bound
- GPU fragment bound
- Bandwidth bound
- Synchronization bound
- Mobile tile resolve / overdraw / full-screen pass 问题

---

## 6. 架构设计类

用户问：Render Graph、RHI 抽象、Resource Lifetime、Pipeline Cache、Frames-in-flight、Descriptor 管理策略。

应关注：

- 抽象层是否泄露 Vulkan 复杂度
- 资源生命周期是否可追踪
- 多 Pass 依赖是否显式
- 同步是否可验证
- 扩展性与风险
- 先走架构决策链（`../02_core_mental_model/engine_architecture.md` §10 六要素），再进具体 workflow

---

## 7. 经验案例类

用户问：有没有类似案例、为什么容易误判、真实工程怎么踩坑。

资料选择见 `../07_integration_pack/task_routing_rules.md#route-case`。

---

## 8. Android 专项类

用户问：SurfaceView 接 Vulkan、`ANativeWindow` 生命周期、pause/resume、rotation crash、Surface destroyed 后 present crash。

资料选择见 `../07_integration_pack/task_routing_rules.md#route-android`。

输出格式根据具体问题选择 `故障调试类` 或 `正向开发类`，但必须先覆盖 Android 生命周期要点。

---

## 9. 项目诊断类

用户提供真实代码仓库，要求理解 Vulkan 架构、评估升级 / 重构影响面、把 Debug Playbook 映射到项目源码，或输出可直接交给 coding agent 的实施计划。

资料选择见 `../07_integration_pack/task_routing_rules.md#route-project`。

应关注：

- `[CODE]` Evidence Map：文件 / 类 / 函数 / 关键行为。
- Architecture Map：Device / Frame / Rendering / Resource / Descriptor / Pipeline / Sync / Present。
- 修改影响面：Must Change / Should Change / Can Defer / Do Not Change。
- 实施依赖顺序、风险、Rollback、DoD 与 Verification Gate。
- 禁止只凭目录名 / 类名推断项目事实。

---

## 10. 简短回答类

用户明确要求简短、只要重点、问题较小时使用。

处理规则：

- 先判断主类型。
- 使用该类型的输出结构，但每节压缩为 bullet 或一句话。
- 必须保留：结论、关键链路、最高优先级检查项、最小验证方式。

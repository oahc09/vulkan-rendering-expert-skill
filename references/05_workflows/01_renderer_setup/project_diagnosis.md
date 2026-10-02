# Workflow: Project Diagnosis

## 0. 适用范围

### 适用

- 用户提供真实 Vulkan / 图形引擎代码仓库，要求先理解现状再给方案。
- Vulkan 版本升级、Renderer 重构、RenderGraph / Bindless / Async Compute 等架构改造前的源码体检。
- Debug / 性能问题需要把通用 Playbook 映射到项目具体文件、类和函数。
- 需要生成可直接交给 coding agent 的实施计划。

### 不适用

- 单个 Vulkan API 的概念解释。
- 没有项目源码且只需要通用方案。
- 已经明确到单一函数、单一 VUID 的局部修复。

---

## 1. 任务目标

建立完整证据链：

~~~text
Repository Evidence
→ Architecture Map
→ Requirement / Problem
→ Impact Surface
→ Decision
→ Implementation Handoff
→ Verification Gate
~~~

项目诊断阶段不假设项目使用某种架构；所有“当前项目如何实现”的判断必须由源码证据支持。

## 2. 输入条件

优先从仓库直接读取；只有影响路由或结论且源码无法回答时才补问：

- 目标平台与构建入口。
- Vulkan 最低 / 目标版本。
- 本次需求或故障现象。
- 是否允许改架构，还是仅允许局部修复。
- 验收目标：正确性 / 性能 / 兼容性 / Android 生命周期。

仓库已能提供的信息不得重复询问。

## 3. Project Reconnaissance

按以下顺序建立项目 Vulkan 地图。禁止仅按文件名或类名猜测，必须打开实现确认。

### 3.1 Build / Platform

确认构建入口、平台矩阵、Vulkan loader / NDK / 主要第三方依赖。

### 3.2 Vulkan Entry

定位：

- VkInstance 创建位置。
- VkPhysicalDevice 选择逻辑。
- VkDevice / feature / extension negotiation。
- graphics / present / compute / transfer queue family。

### 3.3 Frame Loop

定位：

~~~text
Acquire
→ Frame resource wait/reset
→ Command recording
→ Submit
→ Present
~~~

记录 frame index 与 swapchain image index 的管理方式。

### 3.4 Rendering Model

确认项目实际使用：

- Traditional VkRenderPass / VkFramebuffer
- Dynamic Rendering
- RenderGraph / FrameGraph
- 混合模式

必须提供对应函数或创建路径的 [CODE] 证据。

### 3.5 Resource Model

识别 Buffer / Image 创建入口、Memory allocator、Persistent / Per-frame / Transient / Swapchain-dependent 资源，以及 deferred destruction / retire queue。

### 3.6 Descriptor / Binding Model

识别 per-draw / per-material / per-frame descriptor、descriptor indexing / bindless、pool/cache/update 策略，以及 shader reflection / binding schema。

### 3.7 Pipeline Model

识别 pipeline creation / cache、PipelineLayout ownership、dynamic state、pipeline rebuild trigger。

### 3.8 Synchronization / Submission Model

识别 binary / timeline semaphore、fence / frames-in-flight、vkQueueSubmit / vkQueueSubmit2、barrier / Sync2、multi-queue / ownership transfer。

### 3.9 Android Lifecycle（如适用）

沿真实代码确认：

~~~text
Java/Kotlin Surface
→ JNI / Native event
→ ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Render thread
~~~

覆盖 pause / resume / rotation / surface destroyed / extent=0。

## 4. Evidence Map

关键判断统一记录：

| 结论 | 文件 / 类 / 函数 | 关键行为 | 证据等级 | 置信度 |
|---|---|---|---|---|
| 项目使用传统 RenderPass | Renderer.cpp::createPass | 调用 vkCreateRenderPass，pipeline creation 持有 renderPass handle | [CODE] | 高 |
| 同步仍使用 legacy submit | Queue.cpp::submit | 构造 VkSubmitInfo 并调用 vkQueueSubmit | [CODE] | 高 |

规则：

1. [CODE] 只证明“当前项目如何实现”，不能覆盖 [SPEC]。
2. 只有类名 / 文件名、没有读到实现时，标记“未验证”，不能写成项目事实。
3. 项目代码与 [SPEC] 冲突时，应报告项目实现存在风险，而不是用项目实现反推规范。
4. 关键架构结论至少需要一条直接源码证据；跨模块结论优先给两条相互印证的证据。

## 5. Architecture Map 输出

至少输出：

~~~text
Application / Platform
        ↓
Vulkan Entry / Device
        ↓
Renderer / Frame Context
        ↓
RenderPass / Dynamic Rendering / RenderGraph
        ↓
Resource / Descriptor / Pipeline
        ↓
Command Recording
        ↓
Queue Submission / Synchronization
        ↓
Present
~~~

每个节点映射到项目文件 / 类 / 函数。某一层不存在时明确写“不存在 / 未抽象 / 未验证”，不要补造。

## 6. Change Impact Analysis

修改前按四级分类：

### Must Change

不改则目标无法达成，或违反兼容性 / 生命周期 / 同步要求。

### Should Change

不阻塞目标，但继续保留会形成明显技术债、重复路径或回归风险。

### Can Defer

当前目标不依赖，可以后置，并说明后置条件。

### Do Not Change

当前已有实现正确且无必要触碰，避免扩大回归面。

每项必须绑定：

- 文件 / 类 / 函数 [CODE]
- Vulkan 对象影响链
- 生命周期影响
- 同步影响
- Android 生命周期影响（如适用）
- 性能回归面

## 7. Implementation Handoff

输出给 coding agent 时使用：

### Goal
一句话说明目标。

### Current Evidence
列出关键 [CODE] 证据和当前架构。

### Target Design
描述目标架构，不重复通用 Vulkan 教程。

### Files To Modify
逐文件列出位置、计划修改、原因和依赖前置。

### Dependency Order
按真实依赖排序，禁止把有依赖的修改并行化。

### Implementation Steps
每一步明确 Vulkan 对象 / API / 状态变化。

### Risks
至少检查 API compatibility、descriptor / pipeline compatibility、resource lifetime、synchronization、frames-in-flight、swapchain-dependent resources、Android lifecycle、performance regression。

### Verification
复用 00_expert_entry/verification_gate.md G1-G6。

### Rollback
说明恢复旧路径的方法；架构迁移优先保留可切换边界直到验证完成。

### Definition of Done
必须是可验证条件，不使用“基本完成”“看起来正常”等表述。

## 8. 典型任务映射

### Vulkan 版本升级

先建立 apiVersion / features / extensions → submit model → rendering model → descriptor model → Android capability，再分为 Must Change / Should Change / Can Defer / Do Not Change。

不要把“升级 Vulkan 版本”自动等价为“必须迁移 Dynamic Rendering / Sync2”。

### Android rotation crash

把通用 Playbook 映射到：

~~~text
Surface callback
→ Native event
→ ANativeWindow owner
→ VkSurfaceKHR owner
→ Swapchain recreate
→ in-flight resource
~~~

### 新增 Compute Pass

必须优先复用项目现有 resource allocator、descriptor model、pipeline manager、command recording、submission / barrier system，禁止另起一套平行 Vulkan 管理路径。

## 9. 验收

- [ ] 所有关键架构结论有 [CODE] 或显式“未验证”状态。
- [ ] Architecture Map 能映射到源码。
- [ ] 修改项已分为 Must / Should / Can Defer / Do Not Change。
- [ ] 每个 Must Change 有对象链和依赖顺序。
- [ ] 实施计划可直接交给 coding agent。
- [ ] Verification Gate G1-G6 有对应验证入口。
- [ ] Android 项目覆盖 Surface / ANativeWindow / Swapchain 生命周期。
- [ ] 未为了“现代化”无条件引入 RenderGraph / Bindless / Async Compute / Dynamic Rendering。

## 10. 相关模块

- ../../00_expert_entry/progressive_retrieval.md
- ../../00_expert_entry/accuracy_check.md
- ../../02_core_mental_model/engine_architecture.md
- ../../02_core_mental_model/regression_reasoning.md
- ../../07_integration_pack/task_routing_rules.md
- ../../07_integration_pack/regression_checklist.md

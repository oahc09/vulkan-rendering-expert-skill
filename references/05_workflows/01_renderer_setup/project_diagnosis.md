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
- 已明确到单一函数、单一 VUID 的局部修复。

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

## 3. 前置检查

开始诊断前确认：

- [ ] 已能访问目标仓库实际源码，而不是只有目录截图或文件名列表。
- [ ] 已明确当前任务是诊断 / 升级 / 重构 / Debug / 性能中的哪一种。
- [ ] 已读取构建入口与平台分支，确认 Android / Desktop / 多平台边界。
- [ ] 已定位至少一个 Vulkan 初始化入口或调用点，避免根据命名猜架构。
- [ ] 若是修改类任务，已加载 `../../02_core_mental_model/regression_reasoning.md`。
- [ ] 若是架构类任务，已加载 `../../02_core_mental_model/engine_architecture.md`。

## 4. Vulkan 对象链路

按实际源码建立项目 Vulkan 主链，不存在或未验证的层必须显式标记：

~~~text
Application / Platform
→ VkInstance / VkPhysicalDevice / VkDevice
→ Queue Family / VkQueue
→ VkSurfaceKHR / VkSwapchainKHR
→ Frame Context / CommandPool / CommandBuffer
→ RenderPass / Dynamic Rendering / RenderGraph
→ Resource / Descriptor / Pipeline
→ Queue Submission / Synchronization
→ Present
~~~

Project Reconnaissance 至少定位：

1. Build / Platform：CMake / Gradle / GN / Bazel、NDK、Vulkan loader、第三方库版本。
2. Vulkan Entry：Instance、PhysicalDevice、Device、feature / extension negotiation。
3. Frame Loop：Acquire → wait/reset → record → submit → present。
4. Rendering Model：传统 RenderPass、Dynamic Rendering、RenderGraph 或混合路径。
5. Resource Model：Buffer / Image、allocator、deferred destruction、资源生命周期分组。
6. Descriptor / Binding Model：per-draw / per-material / per-frame、bindless / indexing、pool / cache。
7. Pipeline Model：PipelineLayout ownership、pipeline cache、dynamic state、rebuild trigger。
8. Synchronization / Submission：binary / timeline semaphore、fence、Submit / Submit2、barrier / Sync2、multi-queue。

每个关键节点映射到项目文件 / 类 / 函数。

## 5. 资源设计

本 Workflow 不默认新增资源，而是先识别项目现有资源模型：

| 资源类别 | 必查源码证据 | 影响面 |
|---|---|---|
| Persistent | 创建 / owner / 卸载路径 | 长生命周期、deferred destruction |
| Per-frame | FrameContext / frame index / fence | frames-in-flight 复用 |
| Transient | pass 创建 / last-use / alias | RenderGraph、显存峰值 |
| Swapchain-dependent | extent / recreate 注册 | resize / rotation |
| Streaming | upload / staging / retire | transfer 与可见性 |

如果目标改造需要新增资源，必须优先复用现有 allocator / owner / retire 机制；没有证据证明必要时，不另起平行资源系统。

## 6. Pipeline / Descriptor 设计

诊断项目时先确认：

- Shader set / binding 如何定义，是否有 reflection / schema。
- DescriptorSetLayout / PipelineLayout 的 owner 与 cache。
- Descriptor 是 per-frame、per-material、per-draw 还是 bindless。
- Pipeline 创建入口、缓存键、重建触发条件。
- RenderPass / Dynamic Rendering format compatibility 如何进入 pipeline key。

需要新增 pass / compute 时，优先复用当前 Descriptor / Pipeline 管理路径。若现有抽象本身是目标问题根因，才进入 Structural Fix。

## 7. 同步与 Layout 设计

建立真实 producer / consumer 图：

| Producer | Resource | 当前同步 / Layout | Consumer | 源码证据 |
|---|---|---|---|---|
| 实际写入点 | Buffer / Image | Barrier / Semaphore / Layout | 实际读取点 | [CODE] 文件 / 函数 |

必须确认：

- producer stage / access。
- consumer stage / access。
- image oldLayout / newLayout。
- 同 queue 还是跨 queue。
- frame-in-flight 资源何时可复用。
- swapchain acquire / present binary semaphore 边界。
- Android Surface 无效期间是否停止 acquire / present。

## 8. 实现步骤

### Step 1：Project Reconnaissance

按 §4 主链读取源码，建立 Architecture Map。

### Step 2：Evidence Map + Architecture Map

先输出关键 `[CODE]` Evidence Map，再输出与当前任务相关的 Architecture Map。即使主任务是版本升级、Debug 或性能分析，也不能跳过 Architecture Map；只允许缩小到相关主链，未知节点标记“未验证”。

关键判断统一记录：

| 结论 | 文件 / 类 / 函数 | 关键行为 | 证据等级 | 置信度 |
|---|---|---|---|---|
| 项目使用传统 RenderPass | Renderer.cpp::createPass | 调用 vkCreateRenderPass，pipeline creation 持有 renderPass handle | [CODE] | 高 |
| 同步使用 legacy submit | Queue.cpp::submit | 构造 VkSubmitInfo 并调用 vkQueueSubmit | [CODE] | 高 |

规则：

1. `[CODE]` 只证明当前项目如何实现，不能覆盖 `[SPEC]`。
2. 只有文件名 / 类名、没有读到实现时，标记“未验证”。
3. 项目代码与 `[SPEC]` 冲突时，报告项目实现风险。
4. 跨模块架构结论优先使用两条相互印证的源码证据。

### Step 3：Change Impact Analysis

所有修改项分为：

- **Must Change**：不改则目标无法达成，或违反兼容性 / 生命周期 / 同步要求。
- **Should Change**：不阻塞目标，但继续保留会形成明显技术债或回归风险。
- **Can Defer**：当前目标不依赖，可以后置，并给重新评估条件。
- **Do Not Change**：当前实现正确且不在影响链上，明确保持不动。

每项绑定文件 / 类 / 函数 `[CODE]`、Vulkan 对象影响链、生命周期、同步、Android 和性能回归面。

### Step 4：Implementation Handoff

输出给 coding agent：

- Goal
- Current Evidence
- Target Design
- Files To Modify
- Dependency Order
- Implementation Steps
- Risks
- Verification
- Rollback
- Definition of Done

有依赖的修改禁止并行化。

### Step 5：Verification Gate

按 `../../00_expert_entry/verification_gate.md` G1-G6 验证，不把 Validation clean 当成唯一完成条件。

## 9. Android 注意点

Android 项目额外沿真实代码追踪：

~~~text
Java/Kotlin Surface
→ JNI / Native event
→ ANativeWindow
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Render thread
~~~

必须检查：

- SurfaceView / NativeActivity / 其他 Surface 来源。
- ANativeWindow acquire / release ownership。
- pause / resume 与 Surface created / destroyed 的实际事件顺序。
- rotation / resize 后 swapchain-dependent resource 传播。
- extent=0 时的暂停 / 跳帧路径。
- render thread 在 Surface 无效期间是否停止 present。
- logcat / AGI / Validation 的对应证据。

## 10. 验证方式

- [ ] 所有关键项目事实均有 `[CODE]` 证据，或明确标记“未验证”。
- [ ] Architecture Map 每个已确认节点都映射到实际文件 / 类 / 函数。
- [ ] 修改项已分为 Must Change / Should Change / Can Defer / Do Not Change。
- [ ] 每个 Must Change 都有对象影响链和 Dependency Order。
- [ ] 实施计划能直接交给 coding agent，而不是通用 Vulkan 建议。
- [ ] Verification Gate G1-G6 均有已验证 / 未验证 / 不适用状态。
- [ ] Android 项目覆盖 Surface / ANativeWindow / Swapchain 生命周期。
- [ ] 未为了“现代化”无条件引入 RenderGraph / Bindless / Async Compute / Dynamic Rendering。

## 11. 常见失败模式

1. 只根据文件名 / 类名猜项目用了 RenderGraph、Bindless 或某种 queue model。
2. 把 Vulkan 版本升级自动等价为全量迁移 Dynamic Rendering / Synchronization2。
3. 新增 Compute Pass 时绕过项目现有 Resource / Descriptor / Pipeline / Command 系统，形成第二套平行架构。
4. 只列“需要修改的文件”，没有沿对象链继续推导下游兼容性。
5. 只给 Architecture Map，不给可实施的 Dependency Order / Rollback / DoD。
6. 用 `[CODE]` 替代 `[SPEC]` 判断 Vulkan 合法性。

## 12. 相关 API 卡片

按项目实际命中情况加载，常用入口：

- `../../03_api_manual/01_instance_device_queue/logical_device.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

## 13. 相关 Debug Playbook

根据问题定向加载：

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

## 14. 不确定时如何处理

信息不足时不要补造项目事实：

1. 先继续读取能消除分歧的源码调用点。
2. 只有源码和已有上下文都无法回答、且缺口会改变结论时，按 Progressive Retrieval R2 提 ≤3 个最小问题。
3. 未读取实现的判断标记“未验证”，不得标 `[CODE]`。
4. 若项目实现与 Vulkan Spec 冲突，明确区分“项目当前行为”和“规范要求”。
5. 两轮定向检索仍低置信时，把未验证项交给 Verification Gate，不伪装成确定结论。

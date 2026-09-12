# 引擎架构心智模型（Rendering Engine Architecture）

本文件建立图形引擎的子系统级心智模型（Part A）与架构决策框架（Part B）。它回答两个上层问题：一个 Vulkan 渲染引擎由哪些子系统构成、子系统级修改沿什么路径传播；面对架构选型时，如何用统一的六要素完成双向 Trade-off，并留下可重新评估的决策记录。[ENGINE]

---

## 0. 定位与边界

本文件不是图形引擎入门教程，不讲解"如何从零实现一个引擎"，也不复述任何 API 细节。它假定对象级知识（`vulkan_object_chain.md`）已经建立，在此之上回答子系统级的职责划分与架构决策问题。[ENGINE]

与既有文件的分工：

| 既有文件 | 它已覆盖 | 本文件的增量 |
|---|---|---|
| `vulkan_object_chain.md` | 对象级依赖链路 | 子系统级职责划分与跨子系统影响链（§1、§9） |
| `frame_lifecycle.md` | 单帧 CPU / GPU / Present 时序 | Frame Context 的资源结构（§3） |
| `resource_lifecycle.md` | 单个 Buffer / Image 生命周期 | 资源四类生命周期分组策略（§4、D6） |
| `render_graph_resource_lifetime.md` | Render Graph 内部机制（虚资源 / aliasing / barrier 推导） | Render Graph 的子系统职责与引入拐点（§5、D5） |
| `modern_patterns.md` | Bindless / Dynamic State 等模式机制 | 对应模式的架构选型判据（D2、D7） |
| `compute_graphics_relationship.md` | Compute ↔ Graphics 同步机制 | 任务归置判据（D3、D4） |
| `regression_reasoning.md` | 对象级修改传播规则 | 子系统级传播链（§9） |

[ENGINE]

---

## 1. 子系统总览

一个典型 Vulkan 渲染引擎可以划分为 7 个子系统。划分标准是"职责内聚 + 生命周期对齐"：同一子系统内的对象共享创建 / 销毁时机，跨子系统的修改路径必须显式声明。[ENGINE]

一帧内数据流经的子系统路径：[ENGINE]

```text
帧开始（等待本索引 fence）
→ Frame Context：取得 command buffer / UBO offset / per-frame set
→ Render Graph：setup（声明 pass 与资源读写）→ compile（分配与 barrier 计划）
→ Pipeline Manager：按 pass 需求解析 / 复用 / 创建 pipeline
→ Descriptor / Binding Model：为每个 pass 准备绑定（set 绑定或 bindless 索引）
→ Resource Manager：persistent 资源加载期已就绪；transient 由 RG 计划驱动创建
→ Queue / Submission Model：submit（timeline value）→ present
帧结束（GPU 完成后同索引 slot 可复用）
```

| 子系统 | 一句话定位 | 详见 |
|---|---|---|
| RHI / Device Abstraction | 设备与后端能力封装 | §2 |
| Frame Context | 每帧 CPU 侧资源与 GPU 进度对齐 | §3 |
| Resource Manager | 资源创建 / 复用 / 销毁与四类生命周期分组 | §4 |
| Render Graph | 帧级 pass 编排与 transient 资源计划 | §5 |
| Descriptor / Binding Model | shader 资源绑定抽象 | §6 |
| Pipeline Manager | pipeline 创建 / 缓存 / 预热 / 变体控制 | §7 |
| Queue / Submission Model | 多队列选择与提交时序 | §8 |

---

## 2. RHI / Device Abstraction

### 职责

一句话定位：封装设备创建、扩展与 feature 协商、内存类型查询，向上层提供与后端无关的能力面。它解决的问题：让渲染核心代码不直接依赖 backend 细节（Vulkan / D3D12 / Metal），并把"设备支持什么"收敛为单一协商点。[ENGINE]

### 拥有的 Vulkan 对象

```text
VkInstance
VkPhysicalDevice（枚举、评分、选择）
VkDevice
VkQueue 句柄获取（归属权在 §8 Queue Model）
VkDebugUtilsMessengerEXT（debug 构建）
VkPhysicalDeviceFeatures2 / Properties / MemoryTypes 查询缓存
VmaAllocator（若采用 VMA）
```
[SPEC]

### 职责边界

它不管：[ENGINE]

```text
- 渲染逻辑与 pass 编排（Render Graph 的职责）
- 任何 per-frame 资源（Frame Context 的职责）
- pipeline 状态与缓存、swapchain 生命周期（Pipeline Manager / surface 模块 + Swapchain-dependent 组）
```

### 生命周期

```text
创建：渲染器初始化时创建；feature 协商一次完成并缓存结果。
每帧：无逐帧动作（设备级对象不随帧变化）。
重建：进程级对象不重建；surface 事件只触发 swapchain 链（§9 链 1）。
销毁：必须在所有子系统资源销毁之后（VkDevice 销毁前其对象须已销毁）。[SPEC]
```

### 影响链

```text
feature / 扩展协商结果变化
→ Pipeline Manager（可用状态集、dynamic state 范围）
→ Descriptor Model（bindless / push descriptor 可用性）
→ Render Graph（dynamic rendering 还是 RenderPass 路径，见 D1）
→ Resource Manager（内存类型与 allocator 策略）
```
[ENGINE]

### 常见设计错误

1. RHI 接口把 `VkXXX` 句柄泄漏给上层，抽象在第一处跨后端需求时即失效。[ENGINE]
2. feature 检查散落在各子系统就地查询，没有收敛到 RHI 单一协商点，设备能力视图不一致。[ENGINE]
3. 把材质库、贴图池等全局资源挂到 RHI 单例上，RHI 退化为上帝对象。[ENGINE]

---

## 3. Frame Context

### 职责

一句话定位：封装"一帧 CPU 侧工作所需资源"的容器，按 frame-in-flight 索引对齐 GPU 完成进度。它解决的问题：多帧并行下 CPU 复用资源前必须确认 GPU 已完成——本子系统是 `../06_cases/07_engine_architecture/case_engine_architecture.md` 中 Per Frame Resource 案例 FrameContext Structural Fix 的抽象。时序基础见 `frame_lifecycle.md`。[ENGINE]

### 拥有的 Vulkan 对象

```text
按 frame-in-flight 索引成套持有：
  VkCommandBuffer（及其 VkCommandPool）
  VkFence（本索引 in-flight 完成信号）
  acquire / present VkSemaphore（或 timeline value 段）
  UBO ring buffer 的本索引 offset
  per-frame descriptor set（或 bindless 写入区）
```
[SPEC]

### 职责边界

它不管：[ENGINE]

```text
- 资源的创建与内容（Resource Manager 的职责；此处只声明"哪个 slot 拥有"）
- persistent 资源的跨帧持有（Resource Manager）
- pass 编排与帧内同步（Render Graph / 同步体系）
```

### 生命周期

```text
创建：与 frames-in-flight 数量一起创建（典型 2-3 套）。[ENGINE]
每帧：wait 本索引 fence → reset fence → reset/allocate cmd → 录制 → 提交。
重建：frames-in-flight 数量变化时必须成套扩展 / 收缩（regression_reasoning.md §2.4）。
销毁：等待全部 fence 后销毁；早于 GPU 完成销毁即 use-after-free。[SPEC]
```

### 影响链

```text
frames-in-flight 数量变化
→ Resource Manager（ring buffer 分段数、per-frame 资源份数）
→ Descriptor Model（per-frame set 数量）
→ Queue Model（timeline value 分配粒度）
```
[ENGINE]

### 常见设计错误

1. 混淆 swapchain image index 与 frame-in-flight index，等错 fence、复用错 slot。[ENGINE]
2. 单一全局 fence 服务所有帧，多帧并行退化成事实上的单缓冲。[ENGINE]
3. frames-in-flight 数量调整后 per-frame 资源没有成套扩展，直接串帧。[ENGINE]

---

## 4. Resource Manager

### 职责

一句话定位：资源的创建 / 复用 / 销毁，以及把所有资源划入四类生命周期分组（判据见 D6）。它解决的问题：不同生命周期的资源需要完全不同的管理策略，混在单一全局池里必然出现串帧 hazard 或显存峰值失控。[ENGINE]

四类生命周期分组：[ENGINE]

```text
Persistent           跨帧长期存在，随内容加载 / 卸载
                     （mesh / index buffer / 贴图 / 材质参数）
Per-frame            按 frame-in-flight 索引拥有，同索引复用前必须等 fence
                     （command buffer / UBO ring slice / per-frame set）
Transient            生命周期在单帧 first-use → last-use 区间，可参与 aliasing
                     （GBuffer / shadow map / 后处理中间 RT）
Swapchain-dependent 尺寸由 swapchain extent 直接或按比例派生，成组重建
                     （depth / MSAA resolve / offscreen RT / framebuffer）
```

### 拥有的 Vulkan 对象

```text
VkDeviceMemory / VmaAllocation（分配策略归属本子系统）
VkImage / VkBuffer 池（persistent 池 + per-frame ring + swapchain 组）
VkImageView 缓存（按 key 复用）
transient 资源的实际创建可委托 Render Graph 编译期完成（§5）
```
[SPEC]

### 职责边界

它不管：[ENGINE]

```text
- 帧内 barrier / layout（Render Graph 或手写同步的职责）
- per-frame slot 的对齐规则（Frame Context；此处只提供份数）
- present / acquire 时序（Queue Model）
```

### 生命周期

```text
Persistent：随内容加载 / 卸载（异步上传须与 Queue Model 协调）。
Per-frame：随 Frame Context 成套创建 / 销毁。
Transient：随 Render Graph 编译计划创建，last_use 后回收。
Swapchain-dependent：swapchain recreate 时整组重建（§9 链 1）。
```

### 影响链

```text
资源分组或尺寸策略变化
→ Render Graph（imported 资源的可用性与 extent）
→ Descriptor Model（view / descriptor 引用更新）
→ swapchain recreate 时沿链 1 传播
```
[ENGINE]

### 常见设计错误

1. per-frame 资源混入全局池复用，触发 SYNC-HAZARD-WRITE-AFTER-READ。[ENGINE]
2. swapchain recreate 只重建 framebuffer，不重建 depth / MSAA / offscreen 整组。[ENGINE]
3. 跨帧使用的资源标为 transient，被 alias 计划回收后悬空。[ENGINE]

---

## 5. Render Graph

本节只定义 Render Graph 作为子系统的职责边界与引入决策。虚资源、aliasing、barrier 推导等内部机制见 `render_graph_resource_lifetime.md`，此处不复述。

### 职责

一句话定位：帧级数据流编排器——用 pass DAG 声明"这一帧做什么"，由编译器决定资源计划与同步。它解决的问题：把 barrier / layout / transient 分配从每个 pass 的手写代码中抽走，让显存峰值与同步正确性可推导。[ENGINE]

### 拥有的 Vulkan 对象

```text
直接拥有：DAG / 虚资源描述（引擎侧结构，非 Vulkan 对象）
间接拥有（compile 期创建）：
  transient VkImage / VkBuffer（alias heap 内）
  VkImageView（按 key 缓存）
  VkRenderPass（传统路径下 compatible pass 合并的产物）
```
[SPEC][ENGINE]

### 职责边界

它不管：[ENGINE]

```text
- imported persistent 资源的生命周期（Resource Manager / 外部 owner 持有）
- 跨帧资源（必须 imported，机制见 render_graph_resource_lifetime.md §2）
- 提交时序与 queue 选择（只声明 cross-queue 边，执行归 Queue Model）
- pipeline 创建（只提出需求，见 Pipeline Manager）
```

### 生命周期

```text
创建：graph 系统随渲染器初始化；实例逐帧新建或 reset 复用。[ENGINE]
每帧：setup → compile → execute 三阶段（机制见 render_graph_resource_lifetime.md §1）。
重建：不随 swapchain 重建（extent 变化通过 imported 资源传播）。
销毁：transient 资源随 graph 销毁回收；view 缓存必须同步清理。
```

### 影响链

```text
pass 增删 / 读写声明变化
→ Resource Manager（transient 分配计划、alias 峰值）
→ Pipeline Manager（新 pass 的 pipeline 需求）
→ Descriptor Model（新资源的绑定）
→ 多 queue 时沿链 3 传播到 Queue Model
```
[ENGINE]

### 常见设计错误

1. demo 规模渲染器引入 RG：编译开销与学习成本大于收益（拐点判据见 D5）。[ENGINE]
2. imported persistent 资源被声明为 transient 参与 alias，破坏外部 owner。[ENGINE]
3. 视觉顺序约束（透明排序 / skybox 次序）只依赖 DAG 拓扑序，未加显式边。[ENGINE]

---

## 6. Descriptor / Binding Model

### 职责

一句话定位：决定"材质参数如何到达 shader"的绑定抽象。它解决的问题：把 shader 资源引用（set / binding 或 bindless 索引）与资源实例解耦，让绑定的更新频率与资源的生命周期分组对齐。[ENGINE]

### 拥有的 Vulkan 对象

```text
VkDescriptorPool（池策略：per-frame 划分 / 全局 / bindless 大数组）
VkDescriptorSetLayout（binding 结构）
VkDescriptorSet（实例）
VkPipelineLayout（与 Pipeline Manager 共享协议）
push constants（不占 descriptor 的小量高频数据）
```
[SPEC]

### 职责边界

它不管：[ENGINE]

```text
- pipeline 光栅化 / 着色状态（只负责 layout 兼容性协议）
- 资源内容与上传（Resource Manager）
- UPDATE_AFTER_BIND 之外的 GPU 读取时序（同步体系）
```

### 生命周期

```text
创建：layout 随 shader binding 设计创建；pool 随绑定策略创建。
每帧：per-frame set 的写入（或 bindless 页更新）。
重建：binding 结构变化 → layout → pipeline 全量重建（§9 链 2）。[SPEC]
销毁：pool 销毁前其 set 必须已全部释放。[SPEC]
```

### 影响链

```text
binding model 变化（传统 ↔ bindless）
→ Pipeline Manager（layout 兼容性破坏，全量 pipeline 重建）
→ Resource Manager（pool 策略、bindless heap 驻留）
→ 材质系统（参数编码方式）——详见 §9 链 2 与 D2
```
[ENGINE]

### 常见设计错误

1. 全局单 pool 不按 frame 划分，per-frame set 写入与 GPU 读取竞争。[ENGINE]
2. bindless 一刀切上线，没有低端设备的分档回退路径。[ENGINE][VENDOR]
3. layout 变化后只重编 shader 不重建 pipeline，违反 pipeline layout 兼容性。[SPEC]

---

## 7. Pipeline Manager

### 职责

一句话定位：pipeline 的创建、缓存、预热与变体控制。它解决的问题：pipeline 创建是最昂贵的运行时 Vulkan 操作之一，必须把"何时创建、创建多少变体、缓存如何命中"做成系统策略，而不是散落的就地调用。[ENGINE]

### 拥有的 Vulkan 对象

```text
VkPipeline（graphics / compute）
VkPipelineCache（分层：只读 base cache + 可写 user cache）
VkShaderModule（或以 SPIR-V 直接创建 pipeline）
VK_EXT_graphics_pipeline_library 拆分产物（若采用）
```
[SPEC]

### 职责边界

它不管：[ENGINE]

```text
- shader 资源绑定含义（Descriptor Model 的 layout 协议）
- render pass 兼容性声明（Render Graph / render target 模型提供）
- 录制期状态设置（dynamic state 的 vkCmdSetXxx 在录制侧）
```

### 生命周期

```text
创建：variant 首次需要时同步创建，或预热期异步创建（加载画面掩盖）。[ENGINE]
每帧：查缓存复用；命中失败时同步创建（帧尖刺来源）。
重建：layout / render pass 兼容性破坏时全量重建（§9 链 2 与链 4）。[SPEC]
销毁：cache 落盘前校验 app / driver / GPU 版本（案例见 §12 所列 case 文件）。
```

### 影响链

```text
pipeline 变体增长（状态维度 × 组合数）
→ RHI（预热线程 / 异步创建策略）
→ 帧尖刺（首次创建集中在进入新场景 / 新材质时）
→ D7 的选型压力（static 状态维度过多时评估 dynamic state）
```
[ENGINE]

### 常见设计错误

1. cache 无版本校验直接加载旧数据，驱动 / 应用更新后隐式失效（见 Pipeline Cache 案例）。[ENGINE]
2. 首帧同步创建全部 variant，进入战斗 / 关卡时集中卡顿。[ENGINE]
3. 状态全部静态化导致变体组合爆炸（选型判据见 D7）。[ENGINE]

---

## 8. Queue / Submission Model

### 职责

一句话定位：多 queue 的选择、提交时序与跨 queue 同步。它解决的问题：graphics / compute / transfer queue 的能力与负载差异，加上 frames-in-flight 并行，让"提交给谁、按什么顺序、等谁"成为必须显式建模的对象。[ENGINE]

### 拥有的 Vulkan 对象

```text
VkQueue（graphics / compute / transfer 句柄与 family 选择）
提交批次（VkSubmitInfo2 组织）
VkTimelineSemaphore（跨 queue / 跨帧进度追踪）
acquire / present semaphore（与 surface 模块的交界）
```
[SPEC]

### 职责边界

它不管：[ENGINE]

```text
- queue 内的 barrier / layout 同步（Render Graph 或手写 barrier）
- acquire / present 的 surface 生命周期（surface 模块）
- 资源内容与上传（transfer 策略与 Resource Manager 协同）
```

### 生命周期

```text
创建：启动期选择 queue family（能力 + 数量权衡）。
每帧：按依赖序提交各 queue 批次，signal / wait timeline value。
重建：family 选择通常不重建；async compute 开关变化时增删提交路径。
销毁：等待全部 in-flight 完成后销毁 semaphore。
```

### 影响链

```text
新增 async compute queue
→ Render Graph（cross-queue 边与 ownership transfer）
→ Frame Context（timeline 等待点增加）
→ Resource Manager（跨 queue 资源的 ownership 状态跟踪）——详见 §9 链 3 与 D4
```
[ENGINE]

### 常见设计错误

1. timeline value 复用或回退。[SPEC]
2. 把 async compute 当默认性能优化引入，忽视同步开销（判据见 D4）。[ENGINE]
3. 跨 queue 边只插 release barrier 不插 acquire barrier（或反之）。[SPEC]

---

## 9. 子系统间影响链

子系统级修改沿以下四条典型链传播。对象级传播规则见 `regression_reasoning.md`，本节是其子系统级上层。评估架构改动影响面时，先定位改动落在哪条链上，再沿链逐环核对。[ENGINE]

链 1 — swapchain extent 变化（resize / rotation / recreate）：[ENGINE]

```text
swapchain extent 变化
→ Resource Manager：Swapchain-dependent 组整组重建（depth / MSAA / offscreen / framebuffer）
→ Render Graph：imported 附件引用更新
→ Pipeline Manager：未用 dynamic viewport / scissor 的 pipeline 重建
→ Frame Context：viewport / scissor / renderingArea 更新
```

链 2 — binding model 变化（传统 ↔ bindless）：[ENGINE]

```text
binding model 变化
→ Descriptor Model：layout / pool 策略全量调整
→ Pipeline Manager：pipeline layout 兼容性破坏 → 全量 pipeline 重建
→ Resource Manager：descriptor pool 重建 + bindless heap 驻留策略
→ 材质系统：参数编码（binding 绑定 ↔ push 索引）
```

链 3 — 新增 async compute queue：[ENGINE]

```text
新增 async compute queue
→ Queue Model：提交批次与 timeline value 分配变化
→ Render Graph：cross-queue 边（ownership transfer barrier）
→ Frame Context：timeline 等待点增加
→ Resource Manager：跨 queue 资源 ownership 状态跟踪
```

链 4 — pipeline 变体增长：[ENGINE]

```text
pipeline 变体增长
→ Pipeline Manager：cache 策略与命中率恶化
→ RHI：预热 / 异步创建 / 加载画面策略
→ 帧尖刺：首次创建集中（新场景 / 新材质）
→ D7 选型压力：评估 dynamic state 收窄变体维度
```

---

## 10. 架构决策框架（Part B）

### 10.1 决策链与六要素

架构决策不是"选一个看起来更现代的方案"，而是走完以下决策链并留下记录：[ENGINE]

```text
需求 → 约束 → Candidate Architecture → Trade-off → Decision
     → Vulkan Mapping → Verification

需求 / 约束：目标平台、设备分布、性能预算、团队规模。
Candidate：至少两个候选（含"保持现状"）。
Trade-off：用六要素逐项对比（不默认任何一边）。
Decision：结论 + 为什么不选另一边。
Vulkan Mapping：决策落到哪些 Vulkan 对象 / 特性。
Verification：用什么工具与指标验证决策有效。
```

六要素定义：[ENGINE]

```text
适用条件      什么场景下该方案占优（含数量级）
不适用条件    什么场景下该方案失效或退化（含数量级 / 信号）
收益          可量化的改善方向
复杂度        实现成本 + 团队维护成本
性能风险      可能的退化点（含 Android / tile-based 评估）
重新评估条件  出现什么信号时应回到另一边（必须具体可判）
```

### 10.2 硬规则

1. 禁止默认推荐新技术方案（Bindless / RenderGraph / Async Compute / Mesh Shader 等）。每个 Decision 必须写明"为什么不选另一边"。[ENGINE]
2. 每组 trade-off 的"重新评估条件"必须具体可判（数量级 / 可观测信号），不得写"视情况而定"。[ENGINE]
3. Android / tile-based 影响必须在性能风险字段显式评估，不得省略。[ENGINE][ANDROID]
4. 复杂度字段必须计入团队维护成本，不只是实现工时。[ENGINE]

### 10.3 D1：RenderPass vs Dynamic Rendering

attachment 机制见 `render_target_model.md`；本节只做选型。

| 六要素 | A：传统 RenderPass（subpass） | B：Dynamic Rendering |
|---|---|---|
| 适用条件 | 需要 subpass 在 tile memory 内完成 GBuffer → 光照；tile-based 移动 GPU 占比高；需兼容 Vulkan 1.2 以下 | Vulkan 1.3+；pass 间无 subpass 依赖；附件组合逐帧动态变化 |
| 不适用条件 | 附件组合高度动态（VkRenderPass / VkFramebuffer 数量随组合爆炸，>100 组合即难管理） | 需要 on-tile 多 subpass 复用且设备低于 Vulkan 1.4（无 local read） |
| 收益 | tile-based GPU 上多 subpass 显著降低 bandwidth [VENDOR] | 消除 RenderPass / Framebuffer 预创建与缓存管理，与 RG 动态附件契合 |
| 复杂度 | subpass dependency 声明与兼容性管理；团队需理解 tile 模型 | 低；pass 间同步全部显式（通常交给 RG 推导） |
| 性能风险 | 桌面 IMR 上 subpass 收益趋零；兼容性误判引发 pipeline 重建 | tile-based GPU 上放弃 subpass → GBuffer 往返主存，bandwidth 上升，中低端 Android 机型需实测 frame time 差异 [ANDROID][VENDOR] |
| 重新评估条件 | 选 A 后：目标转为桌面为主且 RP / Framebuffer 对象数 >100、维护成本高 → 评估 B | 选 B 后：目标转向 tile-based 为主、引入 deferred on-tile 光照、profile 显示 bandwidth 受限 → 评估 subpass 或 Vulkan 1.4 local read [SPEC] |

Vulkan Mapping：A → `VkRenderPass` + `VkFramebuffer` + `VkSubpassDependency`；B → `vkCmdBeginRendering` + pipeline 创建时的 `VkPipelineRenderingCreateInfo`。[SPEC] Verification：RenderDoc / AGI 对比两条路径的 bandwidth 与 frame time；Validation 确认 subpass dependency 正确性。[TOOL]

### 10.4 D2：Traditional Descriptor vs Bindless

bindless 机制见 `modern_patterns.md` §2；本节只做迁移判据。

| 六要素 | A：传统 per-draw descriptor | B：Bindless |
|---|---|---|
| 适用条件 | 贴图规模 <100；设备分布含大量弱 descriptor indexing 机型；团队 1-3 人 | Vulkan 1.2+ 且设备 `shaderSampledImageArrayNonUniformIndexing` 覆盖率高；贴图 >100 且持续增长；GPU-driven 渲染 |
| 不适用条件 | descriptor update CPU 占比已 >15% 帧预算且贴图规模持续增长 | 低端移动设备占比高；团队无法承担 UPDATE_AFTER_BIND 同步纪律 |
| 收益 | 实现与调试直观，驱动行为可预期 | descriptor update 次数大幅下降；draw 间只 push 索引 |
| 复杂度 | 低起步；per-draw 更新代码随材质数线性增长 | descriptor heap 管理 + UPDATE_AFTER_BIND 同步 + shader 端 nonuniform 修饰；迁移触发 §9 链 2 全量重建 |
| 性能风险 | CPU 侧更新次数随 draw call 线性增长，移动端先触顶 | 低端移动设备上大 descriptor set 的内存占用与更新开销可能退化，需按设备分档回退 [ANDROID][VENDOR] |
| 重新评估条件 | 选 A 后：profile 显示 descriptor update 占比 >15% 且贴图 >100 → 启动迁移评估 | 选 B 后：低端机型 profile 显示退化且用户占比高 → 分档回退；UPDATE_AFTER_BIND hazard 频发 → 收窄 bindless 范围 |

Vulkan Mapping：A → `VkDescriptorPool` + per-draw `vkCmdBindDescriptorSets`；B → `VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT` / `UPDATE_AFTER_BIND_BIT` + push constant 传索引。[SPEC] Verification：CPU profile 对比 descriptor update 占比；设备分档实测 bindless 帧耗时。[TOOL]

### 10.5 D3：Graphics vs Compute（任务归置）

同步机制见 `compute_graphics_relationship.md`；本节只做归置判据。

| 六要素 | A：归置 graphics pipeline | B：归置 compute pipeline |
|---|---|---|
| 适用条件 | 需要 raster 固定功能（深度测试 / blend / 插值 / early-z 剔除） | 数据并行无 raster 需求；需要 workgroup shared memory；输出与图元无关（blur / 规约 / 粒子 / culling） |
| 不适用条件 | 输出尺寸与几何无关的纯像素并行（fragment 路径 wave 效率低）；需要 scatter 写 | 需要 blend / depth 语义的任务；一次性小任务（同步成本大于收益） |
| 收益 | 硬件 raster 单元承担裁剪与插值；early-z 免费剔除被遮挡片元 | workgroup 调度 + shared memory 复用片上数据；无 raster 固定开销 |
| 复杂度 | 低（默认路径） | 跨 pipeline 同步（barrier / layout 切换）显式化 |
| 性能风险 | 规约 / 卷积类任务塞进 fragment → 2x2 quad 利用率低、无法用 shared memory | dispatch 与 draw 的依赖交织造成 queue 内串行空泡 |
| 重新评估条件 | 选 A 后：fragment profile 显示 quad 利用率低、shared memory 可优化 → 迁 compute | 选 B 后：dispatch 后 graphics 长空泡 → 归置回 graphics 或评估 D4 |

Vulkan Mapping：A → `vkCmdDraw*` + graphics pipeline；B → `vkCmdDispatch` + compute pipeline（跨管线共享资源的 usage flag 必须覆盖双方）。[SPEC] Verification：AGI 对比两条路径的 GPU 时间与 wave 占用。[TOOL]

### 10.6 D4：Single Queue vs Async Compute

| 六要素 | A：单 queue 顺序提交 | B：async compute queue |
|---|---|---|
| 适用条件 | compute 工作占比小（<20% frame time）或与 graphics 强依赖交织；同步简单优先 | graphics 与 compute 时间互补（overlap 余量大）且负载隔离度高（少量 barrier 边）；桌面驱动多 queue 支持成熟 |
| 不适用条件 | 无失效场景，只有性能上限（串行叠加） | 同步开销大于 overlap 收益；移动端部分驱动多 queue 实现退化 [ANDROID][VENDOR] |
| 收益 | 时序可推理、无跨 queue 同步 | overlap 缩短 frame time（上限为串行路径中的 compute 段时长） |
| 复杂度 | 低 | ownership transfer + timeline value 管理 + RG cross-queue 边（§9 链 3） |
| 性能风险 | graphics 与 compute 串行叠加，frame time 上限固定 | semaphore 等待链变长；queue 间争抢共享执行单元（移动端常见）[VENDOR]；timeline 空泡 |
| 重新评估条件 | 选 A 后：AGI 显示 graphics 与 compute 互不重叠且合计 >30% frame time → 评估 B | 选 B 后：frame time 反升 / GPU timeline 出现同步空泡 → 回退单 queue（保留代码路径，先关开关） |

Vulkan Mapping：A → 单 `VkQueue` + queue 内 barrier；B → 独立 compute `VkQueue` + `VkTimelineSemaphore`（value 单调递增）。[SPEC] Verification：AGI GPU timeline 对比 overlap 面积与空泡；frame time 前后对比。[TOOL]

### 10.7 D5：Manual Resource Lifetime vs RenderGraph-managed

RG 内部机制见 `render_graph_resource_lifetime.md`；本节只做引入拐点判断。

| 六要素 | A：手动管理（手写 barrier + 显式创建 / 销毁） | B：RenderGraph 托管 |
|---|---|---|
| 适用条件 | pass <8；demo / 工具渲染器；团队 1-2 人 | pass ≥8 且持续增长；多平台目标（aliasing 降移动端显存峰值）；团队 ≥3 人需要统一资源声明协议 |
| 不适用条件 | pass 数增长使手写 barrier 接近 O(pass²)；resize 重建链频繁断裂 | demo / 工具渲染器（编译开销大于收益）；跨帧复杂依赖仍需外部 owner |
| 收益 | 无抽象层；调试直观；每个 barrier 可指认 | barrier / layout / aliasing 下沉到编译器；显存峰值可推导；pass 重排优化可行 |
| 复杂度 | 低起步，但正确性成本随 pass 数超线性增长 | graph 编译器实现或引入成本 + 调试间接层 + 团队学习曲线 |
| 性能风险 | 手写 barrier 倾向两端：过度同步（保守 mask）或遗漏（hazard） | setup / compile 的 CPU 开销进入帧预算；声明错误引入新 bug 类别（生命周期声明与实际使用不一致） |
| 重新评估条件 | 选 A 后：手写 barrier >50 处 / 新增 pass 平均改动 >3 个同步点 / transient 显存峰值接近设备 budget → 评估 B | 选 B 后：RG compile CPU 时间进入帧预算 top3 → 加编译缓存；声明类 bug 频发 → 收窄托管范围 |

Vulkan Mapping：A → 手写 `vkCmdPipelineBarrier2` + 显式创建 / 销毁；B → RG 编译期自动生成（机制见 `render_graph_resource_lifetime.md` §4-§6）。[SPEC][ENGINE] Verification：aliasing 前后显存峰值对比；Validation 同步检查零 hazard。[TOOL]

### 10.8 D6：Persistent / Per-frame / Transient / Swapchain-dependent 四类资源分类

先决定"是否采用四类分组"（vs 单一全局池）：[ENGINE]

| 六要素 | A：单一全局资源池 | B：四类生命周期分组 |
|---|---|---|
| 适用条件 | demo / 原型；资源总数 <20 且单 frame-in-flight | 任何多 frame-in-flight 渲染器；多分辨率 / 多平台目标 |
| 不适用条件 | frames-in-flight >1（串帧 hazard 必然出现） | 无整体失效场景，只有归类错误（代价见下表信号列） |
| 收益 | 实现最快 | 每类资源获得针对性策略：ring 复用 / alias / 成组重建 |
| 复杂度 | 低 | 注册与归类纪律；错分类需要静态检查兜底 |
| 性能风险 | per-frame 与 persistent 混用 → SYNC-HAZARD；显存峰值 = 全部资源之和 | 归类错误按类别付出不同代价；移动端 swapchain-dependent 与 transient 未拆分时显存峰值放大 [ANDROID] |
| 重新评估条件 | 首次出现 SYNC-HAZARD-WRITE-AFTER-READ 即应重新评估 | 错分类信号每迭代出现 >2 次 → 补静态检查 / 生命周期断言 |

归类判据表：[ENGINE]

| 类别 | 归类判据 | 典型资源 | 错分类信号 |
|---|---|---|---|
| Persistent | 生命周期跨帧、随内容加载 / 卸载、与 frame 索引无关 | mesh / 贴图 / 材质参数 | 显存峰值 = 全部资源之和（无 transient 复用） |
| Per-frame | 按 frame-in-flight 索引拥有；同索引复用前必须等 fence | command buffer / UBO ring slice / per-frame set | SYNC-HAZARD-WRITE-AFTER-READ / 串帧（§3） |
| Transient | 生命周期在单帧 first-use → last-use 区间内 | GBuffer / shadow map / 后处理中间 RT | 拖影 / 残留 / alias 后悬空（§5） |
| Swapchain-dependent | 尺寸由 swapchain extent 直接或按比例派生 | depth / MSAA resolve / offscreen / framebuffer | resize / rotation 后尺寸不一致、`VUID-vkCmdDraw-renderPass-02684` 类错误（§9 链 1） |

Vulkan Mapping：分组本身不引入新 Vulkan 对象，它决定既有对象的创建时机与销毁触发点（fence / graph last_use / swapchain recreate）。[ENGINE] Verification：debug 构建加生命周期断言（per-frame 写入必须在对应 fence 之后）；CI 覆盖 resize / rotation 场景。[TOOL]

### 10.9 D7：Static Pipeline State vs Dynamic State

dynamic state 机制见 `modern_patterns.md` §4；本节只做选型判据。

| 六要素 | A：状态烧进 pipeline（static） | B：Extended Dynamic State |
|---|---|---|
| 适用条件 | 状态组合少且稳定（变体 <100）；状态按材质而非按 draw 变化 | Vulkan 1.3+；viewport / scissor / blend constant 等按 draw 高频变化；变体维度多 |
| 不适用条件 | 状态维度乘积使变体 >500；viewport 随窗口 / 分辨率高频变化 | 需兼容不支持 extended dynamic state 的旧设备；状态实际稳定（per-draw 设置成为纯开销） |
| 收益 | 驱动可完全预优化；无 per-draw 状态设置开销 | 变体数坍缩（维度从乘积变加和）；pipeline 复用率上升 |
| 复杂度 | 变体管理与 cache 策略（§7 Pipeline Cache 案例） | 低（vkCmdSetXxx 直接调用）；但状态遗漏成为新 bug 类别 |
| 性能风险 | 变体爆炸 → 首次创建尖刺 + 显存占用 | 部分移动驱动对 dynamic state 有 per-draw 验证 / patch 开销，需实测 [ANDROID][VENDOR] |
| 重新评估条件 | 选 A 后：变体 >500 或创建尖刺频发 → 逐维度评估 B | 选 B 后：profile 显示 vkCmdSetXxx 开销可观（移动端）→ 高频稳定维度回静态 |

Vulkan Mapping：A → 状态写入 `VkGraphicsPipelineCreateInfo` 各状态结构；B → `vkCmdSetViewport` / `vkCmdSetScissor` / `vkCmdSetDepthBias` 等。[SPEC] Verification：变体数与 cache 命中率统计；per-draw 设置开销 profile。[TOOL]

---

## 11. Android / Mobile 架构边界

移动端不是桌面方案的缩水版，以下三个边界直接影响本文件的决策。[ANDROID]

### tile-based GPU 对 D1 / D6 的影响

- tile-based GPU（Mali / Adreno / PowerVR）以 tile memory 为中心，bandwidth 是第一性能约束。D1 的多 subpass 路径在 tile 内完成 GBuffer → 光照可避免往返主存，收益可能压倒 Dynamic Rendering 的简洁性——这是"不默认 Dynamic Rendering"硬规则的移动端依据。[ANDROID][VENDOR]
- D6 的四类分组在移动端更敏感：设备显存 budget 小，transient 未从 persistent 中拆分时显存峰值直接放大；aliasing 成为必要手段而非可选优化（机制与移动端注意见 `render_graph_resource_lifetime.md` 移动端小节）。[ANDROID]

### bandwidth 预算对 aliasing 策略的影响

- aliasing 决策必须以 bandwidth 实测为依据：aliasing 降低峰值显存（移动端关键收益），但可能破坏 tile memory 复用，两者方向在不同器件上可能相反。[VENDOR]
- 架构约束：aliasing 开关必须是运行时可切换的设备分档策略，而不是编译期常量。[ENGINE]

### Surface 生命周期对 Swapchain-dependent 资源组的影响

- Android 的 pause / resume / rotation / 分屏会销毁并重建 Surface，等价于触发 §9 链 1 的整组传播。Surface 状态机机制见 `android_surface_swapchain_lifecycle.md`；整组重建的故障形态与修复结构见 `../06_cases/07_engine_architecture/case_engine_architecture.md` 的 Swapchain Dependent Resource Group 案例，此处不复述。[ANDROID]
- 架构约束：Surface 无效期间渲染线程必须停止 present 并等待重建；Swapchain-dependent 组的重建入口必须唯一（单一事件入口传播到所有子系统，禁止局部处理）。[ANDROID][ENGINE]

---

## 12. 相关文件

- `vulkan_object_chain.md` — 对象级依赖链路，本文件子系统模型的对象基础。
- `frame_lifecycle.md` — 单帧 CPU / GPU / Present 时序，Frame Context（§3）的时序基础。
- `resource_lifecycle.md` — 单个 Buffer / Image 生命周期，四类分组（§4、D6）的底层。
- `render_graph_resource_lifetime.md` — Render Graph 内部机制；本文件 §5 与 D5 只做子系统职责与引入决策。
- `modern_patterns.md` — D2 / D7 的机制基础（bindless / dynamic state）；本文件只写选型判据。
- `compute_graphics_relationship.md` — Compute ↔ Graphics 同步机制；D3 只写归置判据。
- `render_target_model.md` — Render Target / attachment 模型；D1 的机制基础。
- `regression_reasoning.md` — 对象级修改传播规则；§9 是其子系统级上层。
- `android_surface_swapchain_lifecycle.md` — Surface / Swapchain 生命周期机制（§11 引用）。
- `../06_cases/07_engine_architecture/case_engine_architecture.md` — Frame Context、Pipeline Cache、Render Graph 生命周期、Swapchain-dependent 资源组四个架构案例。
- `../03_api_manual/08_synchronization/timeline_semaphore.md` — Queue Model（§8）的 timeline semaphore API 细节。
- `../03_api_manual/06_pipeline/pipeline_cache.md` — Pipeline Manager（§7）的 cache API。
- `../03_api_manual/02_surface_swapchain/swapchain_recreate.md` — 链 1 的 swapchain 重建 API。

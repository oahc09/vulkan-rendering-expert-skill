# TC9: 技能触发测试 — 提示词规格与验收标准

> **状态**: 待 Review
> **日期**: 2026-07-04
> **测试方法**: 通过子 Agent 实际调用 AI，验证 Vulkan 渲染专家技能被正确触发并产出符合规范的响应

---

## 1. 测试架构

### 1.1 执行流程

```
测试脚本 (Python)
  │
  ├── 1. 加载提示词文件 (tests/prompts/tc9_*.txt)
  ├── 2. 构造子 Agent 调用 (Agent tool, subagent_type="general-purpose")
  │      └── prompt = 加载技能上下文 + 用户提示词
  ├── 3. 发送请求, 等待 AI 响应
  ├── 4. 接收响应文本
  ├── 5. 执行自动化验收检查 (正则匹配 / 关键词检测 / 结构分析)
  └── 6. 输出 PASS / FAIL + 诊断信息
```

### 1.2 技能上下文注入方式

子 Agent 的 prompt 分为两部分：

**Part A — 技能上下文**（固定前缀）：

```
你是一名 Vulkan 渲染专家。请严格按照以下规则文件执行任务。

== role.md ==
{role.md 内容}

== hard_rules.md ==
{hard_rules.md 内容}

== task_classifier.md ==
{task_classifier.md 内容}

== response_formats.md ==
{response_formats.md 内容}

== accuracy_check.md ==
{accuracy_check.md 内容}

== debug_priority.md ==
{debug_priority.md 内容}

== performance_priority.md ==
{performance_priority.md 内容}
```

**Part B — 用户提示词**（每个测试用例不同）

### 1.3 验收检查类型

| 检查类型 | 说明 | 实现方式 |
|----------|------|----------|
| `FORMAT_CHECK` | 响应是否包含要求的章节标题 | 正则匹配 `##` 或数字编号标题 |
| `KEYWORD_CHECK` | 响应是否包含/不包含特定关键词 | 关键词集合交集/差集 |
| `ANTI_PATTERN` | 响应是否出现禁止的行为 | 负向断言 |
| `SOURCE_TAG` | 响应是否使用来源标签 | 正则 `\[([A-Z]+)\]` 提取后比对 |
| `STRUCTURE_CHECK` | 响应是否有结构化对象链路 | 检测 Vulkan 对象名 + API 调用 |
| `CLASSIFICATION` | AI 是否正确分类任务类型 | 检测分类关键词 |

---

## 2. 测试用例详细设计

### TC9.1 调试类触发 — 黑屏问题

**提示词文件**: `tests/prompts/tc9_01_black_screen.txt`

**提示词内容**:
```
我的 Vulkan 应用在 Android 设备上运行时出现黑屏。
设备是 Snapdragon 888，Vulkan 1.1。
渲染流程是：创建 Swapchain → 录制 Command Buffer → vkQueueSubmit → vkQueuePresentKHR。
没有 Validation Layer 报错，但屏幕全黑。
帮我排查。
```

**预期任务分类**: 调试问题（类型 4）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含调试类响应格式的章节 | 响应中包含以下至少 4 个关键词: "最可能原因"、"快速验证"、"检查点"、"修复方案"、"回归验证" |
| 2 | ANTI_PATTERN | 不直接猜 shader 问题 | 响应前 30% 文本中不出现 "shader" 作为首要排查方向；应先提及 acquire/submit/present 链路 |
| 3 | KEYWORD_CHECK | 提及渲染链路排查 | 响应中包含以下至少 3 个: "vkAcquireNextImageKHR"、"vkQueueSubmit"、"vkQueuePresentKHR"、"Command Buffer"、"Render loop" |
| 4 | KEYWORD_CHECK | 提及工具验证方式 | 响应中包含以下至少 1 个: "Validation Layer"、"RenderDoc"、"AGI" |
| 5 | KEYWORD_CHECK | 提及 Android Surface | 响应中包含 "Surface" 或 "ANativeWindow" |
| 6 | SOURCE_TAG | 包含来源标签 | 响应中包含至少 1 个 `[A-Z]` 格式的来源标签（如 `[SPEC]`、`[TOOL]`、`[ENGINE]`） |
| 7 | STRUCTURE_CHECK | 给出可执行的排查步骤 | 响应中包含编号列表（1. 2. 3. 或 - 步骤） |

**优先级**: P0

---

### TC9.2 性能类触发 — 移动端帧率低

**提示词文件**: `tests/prompts/tc9_02_mobile_perf.txt`

**提示词内容**:
```
我的 Vulkan 游戏在 Android 手机上帧率只有 25fps，目标是 60fps。
渲染管线包含：G-Buffer Pass（3 个 attachment）→ Lighting Pass（全屏）→ Bloom Pass（全屏）→ Tone Mapping Pass（全屏）。
设备是 Mali-G78，分辨率 2560x1440。
没有做 MSAA。怎么优化？
```

**预期任务分类**: 性能问题（类型 5）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含性能类响应格式的章节 | 响应中包含以下至少 4 个关键词: "瓶颈"、"CPU"、"GPU"、"Bandwidth"、"同步"、"优化优先级"、"验证" |
| 2 | ANTI_PATTERN | 不直接改 shader | 响应前 30% 文本中不出现 "修改 shader" 或 "优化 shader" 作为首要建议；应先判断瓶颈类型 |
| 3 | KEYWORD_CHECK | 进行瓶颈分类 | 响应中明确提到以下 4 个分类: "CPU bound"、"GPU"（或 "Fragment bound"）、"Bandwidth bound"、"Synchronization bound" |
| 4 | KEYWORD_CHECK | 提及移动端特有问题 | 响应中包含以下至少 2 个: "fullscreen pass"、"tile"、"overdraw"、"bandwidth"、"render target"、"attachment load/store" |
| 5 | KEYWORD_CHECK | 提及性能验证工具 | 响应中包含以下至少 1 个: "profiler"、"trace"、"counter"、"frame capture"、"AGI"、"RenderDoc" |
| 6 | SOURCE_TAG | 包含来源标签 | 响应中包含至少 1 个来源标签 |
| 7 | STRUCTURE_CHECK | 给出优化优先级排序 | 响应中包含编号或优先级排序（如 "优先"、"其次"、"1."、"2."） |

**优先级**: P0

---

### TC9.3 设计类触发 — 新建渲染链路

**提示词文件**: `tests/prompts/tc9_03_design_renderpass.txt`

**提示词内容**:
```
我需要在一个新的 Vulkan 引擎中实现一个基础的前向渲染管线。
要求：
- 支持 1 个 directional light
- 支持多个 point light（动态数量）
- 目标平台：桌面 + Android
请给我设计方案。
```

**预期任务分类**: 新建渲染链路（类型 1）/ 新增渲染效果（类型 2）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含设计类响应格式的章节 | 响应中包含以下至少 5 个关键词: "结论"、"推荐方案"、"对象链路"、"关键 API"、"同步"、"生命周期"、"Android"、"风险"、"验证" |
| 2 | STRUCTURE_CHECK | 给出完整 Vulkan 对象链路 | 响应中包含以下至少 5 个 Vulkan 对象: "Instance"、"PhysicalDevice"、"Device"、"Queue"、"Swapchain"、"Command Buffer"、"Pipeline"、"Descriptor"、"Render Pass"（或 "Dynamic Rendering"）、"Fence"、"Semaphore"、"Image"、"Buffer" |
| 3 | KEYWORD_CHECK | 提及 Descriptor 设计 | 响应中包含 "Descriptor" 且涉及 "set layout"、"pool" 或 "binding" |
| 4 | KEYWORD_CHECK | 提及同步设计 | 响应中包含 "Fence" 或 "Semaphore" 且涉及同步用途说明 |
| 5 | KEYWORD_CHECK | 提及 Android 注意点 | 响应中包含 "Android" 且有具体注意事项（非仅提及词） |
| 6 | ANTI_PATTERN | 不只给概念解释 | 响应中不只有概念描述，必须包含具体的 API 名称或对象创建流程 |
| 7 | KEYWORD_CHECK | 给出验证方式 | 响应中包含 "验证" 且有具体验证方法（如 Validation Layer、RenderDoc） |

**优先级**: P0

---

### TC9.4 代码类触发 — Descriptor 更新修改

**提示词文件**: `tests/prompts/tc9_04_code_descriptor.txt`

**提示词内容**:
```
我现在需要修改引擎代码，支持每帧动态更新 Uniform Buffer 中的 MVP 矩阵。
当前代码使用 vkAllocateDescriptorSets 每帧分配新的 Descriptor Set。
我想改成预分配 + vkUpdateDescriptorSets 方式。
帮我设计修改方案，包括需要改哪些文件、新增什么对象、初始化和每帧流程。
```

**预期任务分类**: 代码类问题 / API 使用问题（类型 3/6）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含代码类响应格式的章节 | 响应中包含以下至少 5 个关键词: "修改文件"、"新增"、"初始化"、"每帧"、"销毁"、"同步"、"验证" |
| 2 | STRUCTURE_CHECK | 给出 Vulkan 对象变更 | 响应中包含 "Descriptor" 且涉及 "pool"、"set layout"、"binding" 或 "VkDescriptorSet" |
| 3 | STRUCTURE_CHECK | 涉及 Buffer 更新机制 | 响应中包含 "Uniform Buffer" 或 "VkBuffer" 且涉及 "map"、"memcpy" 或 "update" |
| 4 | KEYWORD_CHECK | 提及生命周期管理 | 响应中包含 "销毁" 或 "释放" 且涉及 Vulkan 对象的清理顺序 |
| 5 | KEYWORD_CHECK | 提及同步关系 | 响应中包含 "Fence" 或 "Semaphore" 或 "barrier" 且说明与 UBO 更新的同步关系 |
| 6 | ANTI_PATTERN | 不只给伪代码 | 响应中必须包含具体的 Vulkan API 函数名（vk 开头），不能只有伪代码 |
| 7 | KEYWORD_CHECK | 给出验证步骤 | 响应中包含 "验证" 且有具体步骤（如 "检查 Validation Layer 输出"） |

**优先级**: P0

---

### TC9.5 API 解释类触发 — Pipeline Barrier

**提示词文件**: `tests/prompts/tc9_05_api_barrier.txt`

**提示词内容**:
```
解释一下 vkCmdPipelineBarrier 的作用和正确用法。
特别是 srcStageMask、dstStageMask、srcAccessMask、dstAccessMask 怎么设置。
我在做 image layout transition 时经常出错。
```

**预期任务分类**: API 解释类问题（类型 3）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含 API 解释类响应格式的章节 | 响应中包含以下至少 4 个关键词: "用途"、"链路"、"输入"、"输出"、"错误"、"关系"、"示例"、"验证" |
| 2 | STRUCTURE_CHECK | 解释 4 个 mask 参数 | 响应中明确解释以下 4 个参数: "srcStageMask"、"dstStageMask"、"srcAccessMask"、"dstAccessMask" |
| 3 | STRUCTURE_CHECK | 解释 image layout transition | 响应中包含 "VkImageMemoryBarrier" 且涉及 "oldLayout"、"newLayout" |
| 4 | KEYWORD_CHECK | 提及常见错误 | 响应中包含 "validation" 或 "VUID" 或具体的错误场景描述 |
| 5 | SOURCE_TAG | 包含来源标签 | 响应中包含 `[SPEC]` 或 `[REF]` 或 `[REGISTRY]`（因为这是 API 细节，应引用权威来源） |
| 6 | ANTI_PATTERN | 不编造不确定的 API 细节 | 如果 AI 对某些细节不确定，应建议 "回查 Vulkan Spec" 而非编造 |
| 7 | KEYWORD_CHECK | 给出验证方式 | 响应中包含 "Validation Layer" 作为验证工具 |

**优先级**: P1

---

### TC9.6 Android 生命周期触发 — Surface 销毁

**提示词文件**: `tests/prompts/tc9_06_android_surface.txt`

**提示词内容**:
```
我的 Android Vulkan 应用在用户切到后台再切回前台时崩溃。
日志显示：
- ANativeWindow 销毁后 vkQueuePresentKHR 返回 VK_ERROR_SURFACE_LOST_KHR
- 然后尝试 vkAcquireNextImageKHR 直接 crash
我该怎么处理这个生命周期？
```

**预期任务分类**: 调试问题（类型 4）/ API 使用问题（类型 3）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | KEYWORD_CHECK | 处理 Surface 生命周期 | 响应中包含 "Surface" 且涉及 "销毁"、"重建" 或 "recreate" |
| 2 | KEYWORD_CHECK | 处理 Swapchain 重建 | 响应中包含 "Swapchain" 且涉及 "vkCreateSwapchainKHR" 或 "recreate" |
| 3 | KEYWORD_CHECK | 提及 Android 生命周期事件 | 响应中包含以下至少 1 个: "onResume"、"onPause"、"onDestroy"、"ANativeWindow"、"Lifecycle" |
| 4 | STRUCTURE_CHECK | 给出完整的重建流程 | 响应中包含销毁旧对象 → 重建 Surface → 重建 Swapchain → 重建 Image/ImageView 的步骤序列 |
| 5 | ANTI_PATTERN | 不忽略同步 | 响应中提及在重建前等待 Fence 或确保 GPU 完成 |
| 6 | KEYWORD_CHECK | 提及错误处理 | 响应中包含 "VK_ERROR_SURFACE_LOST_KHR" 或 "VK_SUBOPTIMAL_KHR" 的处理方式 |
| 7 | SOURCE_TAG | 包含来源标签 | 响应中包含 `[ANDROID]` 或 `[SPEC]` |

**优先级**: P0

---

### TC9.7 硬规则违反检测 — 反模式诱导

**提示词文件**: `tests/prompts/tc9_07_antipattern.txt`

**提示词内容**:
```
我的 Vulkan 应用渲染太慢了，能不能用 OpenGL 来替代部分渲染？
另外给我讲讲什么是 Vulkan 的 Descriptor，概念解释一下就行。
```

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | ANTI_PATTERN | 拒绝用 OpenGL 替代 Vulkan | 响应中明确拒绝或不建议用 OpenGL 替代，坚持 Vulkan 方案 |
| 2 | ANTI_PATTERN | 不只给概念解释 | 对于 Descriptor 的解释，不仅限于概念，必须落到 Vulkan 对象、API、binding 关系 |
| 3 | KEYWORD_CHECK | 给出可执行方案 | 响应中包含具体的 Vulkan 优化方向或 API，而非纯概念 |
| 4 | STRUCTURE_CHECK | 如果涉及性能，先判断瓶颈 | 如果 AI 回应性能问题，应先分类 CPU/GPU/Bandwidth/Sync bound |

**优先级**: P1

---

### TC9.8 不确定性处理 — 模糊/罕见 API 问题

**提示词文件**: `tests/prompts/tc9_08_uncertain_api.txt`

**提示词内容**:
```
VkDeviceDeviceMemoryReportCreateInfoEXT 这个结构体在什么版本引入的？
它的 callback 机制和 VMA 的分配回调有什么区别？
我不确定这个扩展在 Android Adreno GPU 上的支持情况。
```

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | ANTI_PATTERN | 不编造不确定的 API 细节 | 如果 AI 不确定具体版本或支持情况，应明确表示不确定而非编造 |
| 2 | KEYWORD_CHECK | 建议回查官方文档 | 响应中包含 "Vulkan Spec"、"Vulkan Guide"、"Registry"、"Khronos" 或 "回查" 的建议 |
| 3 | KEYWORD_CHECK | 提及扩展查询方式 | 响应中包含 "vkEnumerateDeviceExtensionProperties" 或建议查询扩展可用性 |
| 4 | KEYWORD_CHECK | 提及厂商差异 | 响应中提及不同 GPU 厂商（如 Adreno、Mali）可能有不同支持情况 |
| 5 | SOURCE_TAG | 包含来源标签 | 如果给出具体信息，应标注来源（如 `[REGISTRY]`、`[SPEC]`） |

**优先级**: P1

---

### TC9.9 来源标签使用验证 — 综合问题

**提示词文件**: `tests/prompts/tc9_09_source_tags.txt`

**提示词内容**:
```
我在做 Vulkan 的 Image Layout Transition，从 VK_IMAGE_LAYOUT_UNDEFINED 转到 VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL。
这个 transition 的正确 barrier 参数是什么？
另外，移动端做 layout transition 有什么性能影响？
```

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | SOURCE_TAG | 包含权威来源标签 | 响应中包含 `[SPEC]` 或 `[REGISTRY]` 或 `[REF]`（因为涉及具体 API 参数） |
| 2 | SOURCE_TAG | 包含经验/工具标签 | 响应中包含 `[ENGINE]` 或 `[HEUR]` 或 `[TOOL]`（因为涉及性能经验） |
| 3 | SOURCE_TAG | 标签使用合理 | 权威标签用于 API 细节，经验标签用于性能建议（不混用） |
| 4 | STRUCTURE_CHECK | 给出具体 barrier 参数 | 响应中包含 "srcStageMask"、"dstStageMask"、"srcAccessMask"、"dstAccessMask" 的具体值 |
| 5 | KEYWORD_CHECK | 区分规范与经验 | 响应中能区分 "Spec 要求" 和 "工程经验" 的内容 |
| 6 | ANTI_PATTERN | 不把经验写成绝对结论 | 经验性建议有适用边界说明（如 "移动端" 或 "某些 GPU"） |

**优先级**: P1

---

### TC9.10 闪烁问题调试 — 同步排查

**提示词文件**: `tests/prompts/tc9_10_flicker_sync.txt`

**提示词内容**:
```
我的 Vulkan 应用画面闪烁，每隔几帧出现一次错误画面。
使用 2 frames-in-flight。
Fence 使用方式：vkResetFences → vkQueueSubmit → vkWaitForFences。
Uniform Buffer 每帧用 vkMapMemory + memcpy 更新。
帮我排查。
```

**预期任务分类**: 调试问题（类型 4）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含调试类响应格式 | 响应中包含以下至少 4 个: "最可能原因"、"快速验证"、"检查点"、"修复方案"、"回归验证" |
| 2 | KEYWORD_CHECK | 排查同步问题 | 响应中包含 "frames-in-flight" 且分析同步正确性 |
| 3 | KEYWORD_CHECK | 排查 Fence 使用 | 响应中分析 "vkResetFences" 和 "vkWaitForFences" 的顺序是否正确 |
| 4 | KEYWORD_CHECK | 排查 UBO 更新竞争 | 响应中分析 "vkMapMemory" + "memcpy" 是否存在 CPU/GPU 竞争（同一 buffer 被 CPU 写入时 GPU 仍在读取） |
| 5 | KEYWORD_CHECK | 提及工具验证 | 响应中包含 "RenderDoc" 或 "Validation Layer" 或 "AGI" |
| 6 | STRUCTURE_CHECK | 给出修复方案 | 响应中包含具体的修复步骤（如使用多 buffer ring buffer、延迟更新等） |
| 7 | SOURCE_TAG | 包含来源标签 | 响应中包含至少 1 个来源标签 |

**优先级**: P0

---

### TC9.11 架构类触发 — Render Graph 设计

**提示词文件**: `tests/prompts/tc9_11_architecture.txt`

**提示词内容**:
```
我在设计一个 Vulkan 渲染引擎的 Render Graph 系统。
需要支持：
- 动态 Pass 依赖关系
- 自动 Barrier 插入
- 资源别名（Resource Aliasing）
- 移动端兼容
请给我架构设计建议。
```

**预期任务分类**: 架构问题（类型 6）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | FORMAT_CHECK | 包含架构类响应格式 | 响应中包含以下至少 5 个: "架构结论"、"模块边界"、"数据流"、"对象归属"、"生命周期"、"同步策略"、"扩展性"、"风险"、"验证" |
| 2 | STRUCTURE_CHECK | 涉及 Vulkan 对象归属 | 响应中讨论 Resource/Aliasing 时涉及 "VkDeviceMemory"、"VkImage"、"VkBuffer" 的归属管理 |
| 3 | KEYWORD_CHECK | 提及同步策略 | 响应中包含 "Barrier" 且涉及自动插入策略 |
| 4 | KEYWORD_CHECK | 提及移动端兼容 | 响应中包含 "tile"、"bandwidth" 或 "移动端" 的具体兼容考虑 |
| 5 | ANTI_PATTERN | 抽象层不泄露 Vulkan 复杂度 | 响应中讨论抽象层设计时，考虑是否对使用者隐藏了 Vulkan 特定细节 |
| 6 | KEYWORD_CHECK | 给出验证任务 | 响应中包含 "验证" 且有具体的验证方式 |

**优先级**: P1

---

### TC9.12 非调试场景的 Validation Error 处理

**提示词文件**: `tests/prompts/tc9_12_validation_error.txt`

**提示词内容**:
```
我收到一个 Validation Layer 报错：
VUID-vkCmdBindDescriptorSets-pDescriptorSets-00358
这个是在绑定 Descriptor Set 时报的。
我用了 VkDescriptorSetLayoutBinding，binding 0 是 uniform buffer，binding 1 是 combined image sampler。
请帮我分析和修复。
```

**预期任务分类**: 调试问题 / API 使用问题（类型 3/4）

**验收标准**:

| # | 检查类型 | 检查内容 | 通过条件 |
|---|----------|----------|----------|
| 1 | KEYWORD_CHECK | 提取并分析 VUID | 响应中包含 "VUID" 或 "00358" 且分析其含义 |
| 2 | STRUCTURE_CHECK | 分析 Descriptor Set 绑定 | 响应中分析 "VkDescriptorSetLayoutBinding"、"binding" 与 "VkDescriptorSet" 的关系 |
| 3 | KEYWORD_CHECK | 定位创建点和使用点 | 响应中提及查找 Descriptor Set Layout 创建代码和 Bind 调用代码 |
| 4 | STRUCTURE_CHECK | 给出最小修复方案 | 响应中包含具体的修复建议（如检查 layout binding 数量、stage flags 等） |
| 5 | KEYWORD_CHECK | 给出验证方式 | 响应中提及用 Validation Layer 验证修复 |
| 6 | SOURCE_TAG | 包含来源标签 | 响应中包含 `[SPEC]` 或 `[REF]` 或 `[TOOL]` |

**优先级**: P1

---

## 3. 验收检查实现细节

### 3.1 自动化检查函数签名

```python
def check_format(response: str, required_keywords: list[str], min_count: int) -> tuple[bool, str]:
    """检查响应是否包含足够多的格式关键词"""
    found = [kw for kw in required_keywords if kw in response]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(required_keywords)}: {found}"
    return passed, detail

def check_anti_pattern(response: str, forbidden_patterns: list[str], window: float = 0.3) -> tuple[bool, str]:
    """检查响应前 window 比例的文本中是否出现禁止模式"""
    text = response[:int(len(response) * window)]
    violations = [p for p in forbidden_patterns if p.lower() in text.lower()]
    passed = len(violations) == 0
    detail = f"Violations in first {window*100}%: {violations}" if violations else "No violations"
    return passed, detail

def check_source_tags(response: str, required_tags: list[str] = None, min_count: int = 1) -> tuple[bool, str]:
    """检查响应中是否包含来源标签"""
    import re
    tags = re.findall(r'\[([A-Z]{2,})\]', response)
    if required_tags:
        found = [t for t in required_tags if f"[{t}]" in response]
        passed = len(found) >= min_count
        detail = f"Required: {required_tags}, Found: {found}"
    else:
        passed = len(tags) >= min_count
        detail = f"Found tags: {tags}"
    return passed, detail

def check_vulkan_objects(response: str, required_objects: list[str], min_count: int) -> tuple[bool, str]:
    """检查响应中是否包含足够的 Vulkan 对象引用"""
    found = [obj for obj in required_objects if obj.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(required_objects)}: {found}"
    return passed, detail

def check_keyword(response: str, keywords: list[str], min_count: int) -> tuple[bool, str]:
    """检查响应是否包含足够多的关键词"""
    found = [kw for kw in keywords if kw.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(keywords)}: {found}"
    return passed, detail
```

### 3.2 测试结果格式

```json
{
  "test_case": "TC9.1",
  "prompt_file": "tests/prompts/tc9_01_black_screen.txt",
  "task_type": "调试问题",
  "response_length": 3421,
  "checks": [
    {
      "id": 1,
      "type": "FORMAT_CHECK",
      "name": "调试类响应格式",
      "passed": true,
      "detail": "Found 5/6: ['最可能原因', '快速验证', '检查点', '修复方案', '回归验证']"
    },
    {
      "id": 2,
      "type": "ANTI_PATTERN",
      "name": "不直接猜shader",
      "passed": true,
      "detail": "No violations in first 30%"
    }
  ],
  "overall": "PASS",
  "failed_checks": []
}
```

---

## 4. 提示词文件清单

| 文件 | 测试用例 | 任务类型 | 优先级 |
|------|----------|----------|--------|
| `tc9_01_black_screen.txt` | TC9.1 黑屏调试 | 调试 | P0 |
| `tc9_02_mobile_perf.txt` | TC9.2 移动端性能 | 性能 | P0 |
| `tc9_03_design_renderpass.txt` | TC9.3 渲染管线设计 | 设计 | P0 |
| `tc9_04_code_descriptor.txt` | TC9.4 Descriptor 代码修改 | 代码 | P0 |
| `tc9_05_api_barrier.txt` | TC9.5 Pipeline Barrier API | API解释 | P1 |
| `tc9_06_android_surface.txt` | TC9.6 Android Surface 生命周期 | 调试/Android | P0 |
| `tc9_07_antipattern.txt` | TC9.7 反模式诱导 | 硬规则 | P1 |
| `tc9_08_uncertain_api.txt` | TC9.8 不确定 API 处理 | API解释 | P1 |
| `tc9_09_source_tags.txt` | TC9.9 来源标签验证 | 综合 | P1 |
| `tc9_10_flicker_sync.txt` | TC9.10 闪烁同步排查 | 调试 | P0 |
| `tc9_11_architecture.txt` | TC9.11 Render Graph 架构 | 架构 | P1 |
| `tc9_12_validation_error.txt` | TC9.12 Validation Error 处理 | 调试/API | P1 |

---

## 5. 子 Agent 调用规格

### 5.1 调用方式

使用 Agent tool 发起子 Agent 调用：

```
Agent(
  description="TC9.1 黑屏调试测试",
  subagent_type="general-purpose",
  prompt=<技能上下文 + 用户提示词>
)
```

### 5.2 技能上下文注入

从以下文件读取内容拼接到 prompt 前缀：

| 文件 | 用途 |
|------|------|
| `00_expert_entry/role.md` | 角色定义 |
| `00_expert_entry/hard_rules.md` | 硬规则 |
| `00_expert_entry/task_classifier.md` | 任务分类 |
| `00_expert_entry/response_formats.md` | 响应格式 |
| `00_expert_entry/accuracy_check.md` | 准确性要求 |
| `00_expert_entry/debug_priority.md` | 调试优先级 |
| `00_expert_entry/performance_priority.md` | 性能优先级 |

### 5.3 批量执行策略

- P0 用例（6 个）优先执行，每个用例独立 Agent 调用
- 单个 Agent 超时设为 120 秒
- 每个 Agent 调用之间无需等待（可并行）
- 如果某个用例 FAIL，记录失败详情，不阻塞其他用例
- 全部完成后汇总为 JSON 报告

### 5.4 结果汇总

```json
{
  "test_suite": "TC9_skill_trigger",
  "total": 12,
  "passed": 10,
  "failed": 2,
  "pass_rate": "83.3%",
  "results": [
    {"test_case": "TC9.1", "overall": "PASS", "checks_passed": 7, "checks_total": 7},
    {"test_case": "TC9.2", "overall": "FAIL", "checks_passed": 5, "checks_total": 7, "failed": ["检查#3", "检查#5"]},
    ...
  ]
}
```

---

## 6. 与其他测试类别的关系

| TC9 测试用例 | 关联的静态测试 | 验证的技能规则 |
|-------------|---------------|---------------|
| TC9.1 | TC5.2 (Playbook模板) | hard_rules #5, #7, #17; debug_priority 黑屏 |
| TC9.2 | TC5.3 (Workflow模板) | hard_rules #8; performance_priority |
| TC9.3 | TC5.1 (API卡片模板) | hard_rules #2, #3, #6, #11; role.md |
| TC9.4 | TC6.1 (Metadata) | hard_rules #2, #6, #11 |
| TC9.5 | TC4.1 (标签一致) | hard_rules #9; accuracy_check #1, #7 |
| TC9.6 | TC5.4 (Case模板) | hard_rules #4; debug_priority Crash |
| TC9.7 | — | hard_rules #1, #2, #11 |
| TC9.8 | — | hard_rules #9, #10; accuracy_check #4 |
| TC9.9 | TC4.3 (标签使用) | accuracy_check #1, #3, #5, #6 |
| TC9.10 | TC5.2 (Playbook模板) | hard_rules #5, #7; debug_priority 闪烁 |
| TC9.11 | TC5.3 (Workflow模板) | hard_rules #6, #11; task_classifier 架构 |
| TC9.12 | TC6.2 (Playbook引用) | hard_rules #9; debug_priority Validation Error |

---

## 7. 已知限制与注意事项

1. **AI 响应不确定性**: 同一提示词可能得到不同响应，验收标准应关注结构性要素而非具体措辞
2. **上下文长度**: 注入 7 个规则文件约 3000-4000 tokens，需确保不超出模型上下文窗口
3. **关键词匹配局限**: 正则/关键词匹配可能误判，建议对 FAIL 结果进行人工复核
4. **执行成本**: 12 个 Agent 调用消耗较多 token，建议先执行 P0 用例（6 个），通过后再执行 P1
5. **超时处理**: 如果 Agent 超时，标记为 SKIP 而非 FAIL，可重试
6. **并行执行**: 多个 Agent 调用可并行发起，但需注意 API 速率限制

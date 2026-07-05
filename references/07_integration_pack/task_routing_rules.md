# Task Routing Rules

## 1. 概念+链路类

用户问：Vulkan / Descriptor / Pipeline / Barrier / Swapchain 是什么？某个概念如何工作？

> 注意：概念解释仍需遵守 `00_expert_entry/hard_rules.md` 第 11 条——不能只输出概念解释，必须附带可执行的 Vulkan 对象链路、API 调用、资源变更和验证路径。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. 必要时引用 `03_api_manual`

不使用：

- `04_debug_playbooks`
- `05_workflows`
- `06_cases`

## 2. API 细节类

用户问：`vkCreateImage`、`VkDescriptorSetLayoutBinding`、`vkCmdPipelineBarrier2`、`VkSwapchainCreateInfoKHR` 等 API 或字段。

使用模块：

1. `00_expert_entry`
2. `01_source_map_and_api_manual_strategy`
3. `02_core_mental_model`
4. `03_api_manual`

## 3. 故障调试类

用户问：黑屏、Validation Error、Android 横竖屏 crash、compute 没输出、texture 黑、GPU hang、device lost。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `04_debug_playbooks`
4. 必要时引用 `03_api_manual`
5. 必要时引用 `06_cases`

## 4. 正向开发类

用户问：新增 fullscreen pass、compute pass、SurfaceView 接入、swapchain recreate、offscreen pass、后处理优化、OpenGL / Shadertoy 迁移。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows`
4. 必要时引用 `03_api_manual`
5. 必要时引用 `04_debug_playbooks`

## 5. 性能优化类

用户问：GPU frame time 高、fullscreen pass 很重、bandwidth 高、移动端发热、descriptor 更新开销高、barrier 是否过重。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows`
4. `04_debug_playbooks`
5. `06_cases`
6. 必要时引用 `03_api_manual`

## 6. 架构设计类

用户问：Render Graph、RHI 抽象、Resource Lifetime、Pipeline Cache、Frames-in-flight、Descriptor 管理策略。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows`（如涉及具体实现）
4. `06_cases`（如需要参考真实案例）
5. 必要时引用 `03_api_manual`

## 7. 经验案例类

用户问：有没有类似案例、为什么容易误判、真实工程怎么踩坑。

使用模块：

1. `00_expert_entry`
2. `06_cases`
3. 必要时引用 `04_debug_playbooks`
4. 必要时引用 `03_api_manual`

## 8. Android 专项类

用户问：SurfaceView 接 Vulkan、`ANativeWindow` 生命周期、pause/resume、rotation crash、Surface destroyed 后 present crash。

使用模块：

1. `00_expert_entry`
2. `02_core_mental_model`
3. `05_workflows/04_android_integration`
4. `04_debug_playbooks/05_android_specific`
5. `06_cases/04_swapchain_android`
6. 必要时引用 `03_api_manual/02_surface_swapchain` 与 `03_api_manual/08_synchronization` 相关卡片

## 9. 简短回答类

用户明确要求简短、只要重点、问题较小时使用。

处理规则：

1. 先判断主类型（参考本文件前述 8 类）。
2. 使用该主类型的输出结构，但每节压缩为 bullet 或一句话。
3. 必须保留：结论、关键链路、最高优先级检查项、最小验证方式。

使用模块：与判断出的主类型一致。

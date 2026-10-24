# Integration Test Plan

本文件是可随仓库检出复用的行为评估输入与判据，不是自动化测试执行记录。当前仓库未跟踪 pytest 测试套件；不能依据历史本地测试命令声称本次通过。评估时记录日期、所用模型 / 宿主、仓库提交及工作区差异、实际加载资料、回答、通过 / 失败 / 未运行和判定依据。知识库行为评估不等于真实 Vulkan 运行验证。

结构预检运行 `node scripts/check-skill.mjs`，按需加 `--max-files 200`；最新定向行为执行证据见 [behavior_evaluation.md](behavior_evaluation.md)。重新评估时只向答题上下文提供原始问题和技能入口，不加载本文件或历史答案；由评估方按本文件判据核对结果。

## 测试 1：黑屏调试

输入：

```text
Android Vulkan 工程运行后黑屏，没有 crash，怎么排查？
```

期望路由：

```text
根目录 SKILL.md
→ 02_core_mental_model/vulkan_object_chain.md
→ 04_debug_playbooks/01_visual_issues/black_screen.md
→ 03_api_manual/02_surface_swapchain/swapchain.md
→ 03_api_manual/03_command_buffer/command_buffer.md
→ 03_api_manual/06_pipeline/graphics_pipeline.md
→ 03_api_manual/05_descriptor/descriptor_set.md
→ 06_cases/01_black_screen/case_black_screen.md
```

合格输出必须覆盖：

- render loop
- acquire / submit / present
- clear color
- viewport / scissor
- pipeline / descriptor
- image layout
- Android Surface 生命周期
- Validation / RenderDoc / AGI 验证

## 测试 2：新增 fullscreen pass

输入：

```text
我要新增一个 fullscreen blur pass。
```

期望路由：

```text
根目录 SKILL.md
→ 02_core_mental_model/render_target_model.md
→ 05_workflows/02_render_pass_effects/add_fullscreen_pass.md
→ 03_api_manual/04_buffer_image_memory/image.md
→ 03_api_manual/05_descriptor/descriptor_set.md
→ 03_api_manual/06_pipeline/graphics_pipeline.md
→ 03_api_manual/08_synchronization/pipeline_barrier.md
→ 04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md
```

合格输出必须覆盖：

- input / output image
- image usage
- image view / sampler
- descriptor set
- fullscreen pipeline
- command buffer
- barrier / layout
- swapchain recreate
- RenderDoc / AGI 验证

## 测试 3：Android rotation crash

输入：

```text
Android 横竖屏切换后 Vulkan crash。
```

期望路由：

```text
根目录 SKILL.md
→ 02_core_mental_model/android_surface_swapchain_lifecycle.md
→ 04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md
→ 05_workflows/04_android_integration/handle_swapchain_recreate.md
→ 06_cases/04_swapchain_android/case_swapchain_android.md
```

合格输出必须覆盖：

- Surface / ANativeWindow
- out-of-date / suboptimal
- wait in-flight
- destroy old resources
- recreate swapchain
- recreate image views
- recreate depth / offscreen
- re-record command buffer
- update descriptor
- resume render loop

## 测试 4：Compute 输出给 Fragment

输入：

```text
Compute 写 storage image 后给 fragment shader 采样，结果是黑的。
```

期望路由：

```text
根目录 SKILL.md
→ 05_workflows/03_compute_workflows/compute_to_graphics_sync.md
→ 04_debug_playbooks/04_resource_sync/compute_no_output.md
→ 06_cases/03_sync_layout/case_sync_layout.md
→ 03_api_manual/08_synchronization/image_memory_barrier.md
```

合格输出必须覆盖：

- compute dispatch
- storage image usage
- descriptor bind point
- compute shader write
- image layout
- compute write → fragment read barrier
- descriptor imageLayout
- RenderDoc / AGI / sync validation

## 测试 5：性能优化

输入：

```text
Vulkan 后处理 pass 开启后 GPU 很高，怎么优化？
```

期望路由：

```text
根目录 SKILL.md
→ 05_workflows/07_optimization/optimize_fullscreen_pass.md
→ 04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md
→ 06_cases/06_performance/case_performance.md
```

合格输出必须覆盖：

- 先判断 CPU / GPU / bandwidth / sync
- fullscreen pass 数量
- render target 尺寸
- format
- sampling count
- load/store
- tile resolve
- AGI / RenderDoc 验证

## 测试 6：Descriptor 报错

输入：

```text
Validation 报 descriptor binding 不匹配，怎么定位？
```

期望路由：

```text
根目录 SKILL.md
→ 04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md
→ 03_api_manual/05_descriptor/descriptor_set_layout.md
→ 03_api_manual/05_descriptor/descriptor_set.md
→ 03_api_manual/06_pipeline/pipeline_layout.md
→ 06_cases/02_descriptor_pipeline/case_descriptor_pipeline.md
```

合格输出必须覆盖：

- shader set/binding
- descriptor set layout
- descriptor type
- stageFlags
- pipeline layout
- descriptor allocation
- descriptor update
- command buffer bind
- RenderDoc bound resources

## 测试 7：类似案例查询

输入：

```text
Compute 输出给 Fragment 采样黑屏，有没有类似案例？
```

期望路由：

```text
根目录 SKILL.md
→ 06_cases/03_sync_layout/case_sync_layout.md
→ 04_debug_playbooks/04_resource_sync/compute_no_output.md
→ 03_api_manual/08_synchronization/pipeline_barrier.md
```

合格输出必须覆盖：

- 相似案例
- 现象对比
- 初始误判
- 根因模式
- 修复方式
- 可复用经验

## 定向回归：版本、帧循环与证据边界

仅在对应规则变化时执行相关行，无需扩展为全平台测试矩阵。每行是一个输入场景，重点判断实际决策是否安全，不匹配固定措辞或标题。

| 输入 | 合格行为 | 不合格行为 |
|---|---|---|
| `设备 apiVersion 要和哪个 1.4 宏比较？scalarBlockLayout、sync2、timelineSemaphore 分别在哪个 feature struct 启用？` | 使用 VK_API_VERSION_1_4；scalarBlockLayout / timelineSemaphore 归 Vulkan12Features、sync2 归 Vulkan13Features；区分核心化、必须支持和启用 | 使用 VK_VERSION_1_4 作版本数值；将所有字段写进 Vulkan14Features；把 sync2 / timeline 的必须支持起点写为 1.4 |
| `帧开始 wait 后立刻 reset fence，acquire 返回 OUT_OF_DATE 就 return；SUBOPTIMAL 也 return，可以吗？` | 指出无 submit 的 unsignaled fence 会造成后续等待卡死；把 reset 移至实际 submit 前；区分 OUT_OF_DATE 与已取得 image 的 SUBOPTIMAL；submit 失败进入恢复 | 只增加 WaitIdle 或重建 semaphore，保留错误 fence 顺序；忽略 SUBOPTIMAL 的 image / 信号处理 |
| `2 个 frame slot、3 个 swapchain image，renderFinished 按 frame slot 分配；frame fence 结束后能复用或随旧 swapchain 释放吗？` | 分开 currentFrame 与 imageIndex；present wait semaphore 按 image 管理或提供等效完成证明；退役独立追踪，submit fence / WaitIdle 不单独证明 presentation 资源可释放 | 仅等待 submit fence 后复用 / 释放；只改数组长度不改索引；对 retired swapchain 再 acquire |
| `只解释 barrier2 的 srcStageMask；另给一个未运行的同步方案，能否宣布运行验证通过？` | 简单问答引用规范和边界，无需整张 G1-G6；方案可作静态判断并列执行计划，未运行项如实标注；实际修复声明仍检查所有适用关卡 | Validation clean 被表述为完整合法性证明；因为没有抓帧而拒绝解释 API；把文档 / 设计完成当作运行验证通过 |

需要验证实际 renderer 时，再按 `regression_checklist.md` 选择受影响项；本表没有执行记录就标为未运行，不能把定义了判据当作通过。

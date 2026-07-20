# Integration Test Plan

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

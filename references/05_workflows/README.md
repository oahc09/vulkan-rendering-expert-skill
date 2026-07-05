# 05_workflows：Vulkan 专家工作流模块

## 1. 模块定位

`05_workflows` 是 Vulkan Expert Skill 的专家工作流模块。

它面向**正向工程任务**，不以单个 API 为入口，也不以故障排查为入口。  
它解决的问题是：

> 面对一个真实 Vulkan 工程任务，高级 Vulkan 工程师应该如何从需求、对象链路、资源设计、同步设计、实现步骤到验证闭环完成交付。

---

## 2. 模块目标

本模块用于处理以下类型任务：

- 新建 Vulkan Renderer
- 建立 Vulkan frame loop
- 新增 fullscreen pass
- 新增 offscreen render pass
- 新增 postprocess pass
- 新增 compute pass
- 建立 compute → graphics 同步
- 接入 Android SurfaceView / ANativeWindow
- 处理 Android lifecycle / swapchain recreate
- 新增 texture / uniform / storage buffer / storage image
- 新增 graphics / compute pipeline
- 优化 fullscreen pass / bandwidth / descriptor / barrier
- 从 OpenGL / Shadertoy / GLSL 效果迁移到 Vulkan

---

## 3. 与其他模块关系

```text
00_expert_entry
定义专家行为、输出格式和硬约束。

01_source_map_and_api_manual_strategy
定义来源等级、可信来源、引用规则和更新策略。

02_core_mental_model
定义 Vulkan 对象链路、帧生命周期、资源生命周期和同步模型。

03_api_manual
定义 Vulkan API 专家卡片。

04_debug_playbooks
根据真实故障现象组织排查路径。

05_workflows
根据真实工程任务组织实现路径，并引用 02/03/04 模块内容。
```

---

## 4. 核心原则

1. 先明确任务目标，再进入 API 细节。
2. 先建立 Vulkan 对象链路，再设计代码结构。
3. 先设计资源生命周期，再创建资源。
4. 涉及资源跨 pass 使用时，必须设计 producer / consumer / barrier / layout。
5. 涉及 shader resource 时，必须设计 shader binding / descriptor layout / pipeline layout。
6. 涉及 Android 时，必须设计 Surface / ANativeWindow / pause / resume / rotation / swapchain recreate。
7. 每个 workflow 必须给出验证闭环：Validation Layer、RenderDoc / AGI、截图、frame time、多帧稳定性。
8. 不确定 API 细节时，不在 workflow 中编造，转向 `03_api_manual` 或官方文档回查。

---

## 5. 推荐目录结构

```text
05_workflows/
├── README.md
├── workflow_template.md
├── workflow_index.md
│
├── 01_renderer_setup/
│   ├── create_renderer_from_scratch.md
│   ├── setup_instance_device_queue.md
│   ├── setup_swapchain.md
│   ├── setup_frame_loop.md
│   └── setup_validation_debug.md
│
├── 02_render_pass_effects/
│   ├── add_fullscreen_pass.md
│   ├── add_texture_sampling_pass.md
│   ├── add_offscreen_render_pass.md
│   ├── add_postprocess_pass.md
│   ├── add_depth_pass.md
│   └── add_dynamic_rendering_pass.md
│
├── 03_compute_workflows/
│   ├── add_compute_pass.md
│   ├── compute_write_storage_image.md
│   ├── compute_write_storage_buffer.md
│   ├── compute_to_graphics_sync.md
│   └── compute_blur_pass.md
│
├── 04_android_integration/
│   ├── integrate_surfaceview_anativewindow.md
│   ├── handle_android_lifecycle.md
│   ├── handle_swapchain_recreate.md
│   ├── pause_resume_render_thread.md
│   └── android_validation_agi_workflow.md
│
├── 05_resource_management/
│   ├── add_texture_resource.md
│   ├── add_uniform_buffer.md
│   ├── add_storage_buffer.md
│   ├── add_offscreen_image.md
│   ├── manage_frame_resources.md
│   └── manage_resource_lifetime.md
│
├── 06_pipeline_descriptor/
│   ├── add_graphics_pipeline.md
│   ├── add_compute_pipeline.md
│   ├── add_descriptor_set.md
│   ├── add_pipeline_layout.md
│   └── shader_binding_workflow.md
│
├── 07_optimization/
│   ├── optimize_frame_time.md
│   ├── optimize_fullscreen_pass.md
│   ├── optimize_descriptor_updates.md
│   ├── optimize_barriers.md
│   ├── optimize_mobile_bandwidth.md
│   └── reduce_pipeline_creation_stutter.md
│
└── 08_migration/
    ├── port_opengl_to_vulkan.md
    ├── port_shadertoy_to_vulkan.md
    ├── port_glsl_effect_to_vulkan_android.md
    └── convert_single_pass_to_render_graph.md
```

---

## 6. P0 首批 Workflow

第一批建议优先完成：

```text
01_renderer_setup/create_renderer_from_scratch.md
01_renderer_setup/setup_frame_loop.md
02_render_pass_effects/add_fullscreen_pass.md
02_render_pass_effects/add_offscreen_render_pass.md
03_compute_workflows/add_compute_pass.md
03_compute_workflows/compute_to_graphics_sync.md
04_android_integration/integrate_surfaceview_anativewindow.md
04_android_integration/handle_swapchain_recreate.md
07_optimization/optimize_fullscreen_pass.md
```

这 9 个 workflow 覆盖 Vulkan 工程最常见的正向开发任务。

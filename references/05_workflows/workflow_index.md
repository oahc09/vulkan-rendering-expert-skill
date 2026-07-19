# Workflow Index

> 文件建议路径：`workflow_index.md`

---

## 1. Renderer Setup

| 任务 | Workflow |
|---|---|
| 从零创建 Vulkan Renderer | `01_renderer_setup/create_renderer_from_scratch.md` |
| 建立 instance / device / queue | `01_renderer_setup/setup_instance_device_queue.md` |
| 建立 frame loop | `01_renderer_setup/setup_frame_loop.md` |
| 建立 validation/debug | `01_renderer_setup/setup_validation_debug.md` |
| 建立 swapchain | `01_renderer_setup/setup_swapchain.md` |

---

## 2. Render Pass / Effect

| 任务 | Workflow |
|---|---|
| 新增 fullscreen pass | `02_render_pass_effects/add_fullscreen_pass.md` |
| 新增 offscreen render pass | `02_render_pass_effects/add_offscreen_render_pass.md` |
| 新增 depth pass | `02_render_pass_effects/add_depth_pass.md` |
| 新增 postprocess pass | `02_render_pass_effects/add_postprocess_pass.md` |
| 新增 texture sampling pass | `02_render_pass_effects/add_texture_sampling_pass.md` |
| 新增 dynamic rendering pass | `02_render_pass_effects/add_dynamic_rendering_pass.md` |

---

## 3. Compute

| 任务 | Workflow |
|---|---|
| 新增 compute pass | `03_compute_workflows/add_compute_pass.md` |
| Compute 写 storage image | `03_compute_workflows/compute_write_storage_image.md` |
| Compute 写 storage buffer | `03_compute_workflows/compute_write_storage_buffer.md` |
| Compute → Graphics 同步 | `03_compute_workflows/compute_to_graphics_sync.md` |
| Compute blur | `03_compute_workflows/compute_blur_pass.md` |

---

## 4. Android Integration

| 任务 | Workflow |
|---|---|
| 接入 SurfaceView / ANativeWindow | `04_android_integration/integrate_surfaceview_anativewindow.md` |
| 处理 Android 生命周期 | `04_android_integration/handle_android_lifecycle.md` |
| 处理 swapchain recreate | `04_android_integration/handle_swapchain_recreate.md` |
| 暂停/恢复 render thread | `04_android_integration/pause_resume_render_thread.md` |
| Android Validation / AGI 工作流 | `04_android_integration/android_validation_agi_workflow.md` |

---

## 5. Resource Management

| 任务 | Workflow |
|---|---|
| 新增 texture 资源 | `05_resource_management/add_texture_resource.md` |
| 新增 uniform buffer | `05_resource_management/add_uniform_buffer.md` |
| 新增 storage buffer | `05_resource_management/add_storage_buffer.md` |
| 新增 offscreen image | `05_resource_management/add_offscreen_image.md` |
| 管理 frame resources | `05_resource_management/manage_frame_resources.md` |
| 管理 resource lifetime | `05_resource_management/manage_resource_lifetime.md` |

---

## 6. Pipeline / Descriptor

| 任务 | Workflow |
|---|---|
| 新增 graphics pipeline | `06_pipeline_descriptor/add_graphics_pipeline.md` |
| 新增 compute pipeline | `06_pipeline_descriptor/add_compute_pipeline.md` |
| 新增 descriptor set | `06_pipeline_descriptor/add_descriptor_set.md` |
| 新增 pipeline layout | `06_pipeline_descriptor/add_pipeline_layout.md` |
| Shader binding 对齐 | `06_pipeline_descriptor/shader_binding_workflow.md` |

---

## 7. Optimization

| 任务 | Workflow |
|---|---|
| 优化 frame time | `07_optimization/optimize_frame_time.md` |
| 优化 fullscreen pass | `07_optimization/optimize_fullscreen_pass.md` |
| 优化 descriptor 更新 | `07_optimization/optimize_descriptor_updates.md` |
| 优化 barrier | `07_optimization/optimize_barriers.md` |
| 优化移动端 bandwidth | `07_optimization/optimize_mobile_bandwidth.md` |
| 减少 pipeline 创建卡顿 | `07_optimization/reduce_pipeline_creation_stutter.md` |

---

## 8. Migration

| 任务 | Workflow |
|---|---|
| 单 pass 迁移到 RenderGraph | `08_migration/convert_single_pass_to_render_graph.md` |
| OpenGL 迁移到 Vulkan | `08_migration/port_opengl_to_vulkan.md` |
| Shadertoy 迁移到 Vulkan | `08_migration/port_shadertoy_to_vulkan.md` |
| GLSL 效果迁移到 Android Vulkan | `08_migration/port_glsl_effect_to_vulkan_android.md` |

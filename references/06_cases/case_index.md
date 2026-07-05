# Case Index

> 文件建议路径：`case_index.md`

---

## 1. 黑屏类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `01_black_screen/case_black_screen_image_layout.md` | clear color 可见，但后处理 / 纹理采样黑 | black-screen, image-layout, sampled-image |
| `01_black_screen/case_black_screen_no_submit.md` | render loop 执行，但画面无变化 | black-screen, queue-submit, command-buffer |
| `01_black_screen/case_black_screen_wrong_viewport.md` | draw call 存在但无像素输出 | viewport, scissor, black-screen |
| `01_black_screen/case_black_screen_depth_cull.md` | mesh 存在但全部被 depth / MVP 裁掉 | depth, mvp, culling |

---

## 2. Descriptor / Pipeline 类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `02_descriptor_pipeline/case_descriptor_binding_mismatch.md` | Validation 报 binding / set 不匹配 | descriptor, binding, validation |
| `02_descriptor_pipeline/case_pipeline_layout_mismatch.md` | pipeline layout 与 descriptor set 不兼容 | pipeline-layout, descriptor |
| `02_descriptor_pipeline/case_descriptor_old_image_after_resize.md` | resize 后 descriptor 引用旧 image | resize, descriptor, old-image |
| `02_descriptor_pipeline/case_uniform_alignment_error.md` | uniform 参数异常或随机跳变 | uniform, alignment, dynamic-offset |

---

## 3. 同步 / Layout 类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `03_sync_layout/case_compute_to_fragment_missing_barrier.md` | compute 输出，fragment 采样黑 | compute, barrier, fragment |
| `03_sync_layout/case_transfer_to_shader_missing_transition.md` | 上传纹理后 shader 采样异常 | transfer, sampled-image, layout |
| `03_sync_layout/case_frame_resource_overwrite.md` | 多 frame-in-flight 闪烁 | frame-resource, fence, flickering |
| `03_sync_layout/case_command_buffer_reset_in_flight.md` | command buffer reset 后偶发 crash | command-buffer, in-flight |

---

## 4. Android / Swapchain 类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `04_swapchain_android/case_android_rotation_old_imageview.md` | 横竖屏切换后 crash / 黑屏 | android, rotation, swapchain |
| `04_swapchain_android/case_surface_destroy_present_crash.md` | Surface destroyed 后 native crash | surface, anativewindow, present |
| `04_swapchain_android/case_pause_resume_black_screen.md` | 切后台再回来黑屏 | pause, resume, android |
| `04_swapchain_android/case_extent_zero_swapchain_create.md` | extent 为 0 仍创建 swapchain | extent-zero, swapchain |

---

## 5. Compute 类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `05_compute/case_compute_dispatch_zero.md` | dispatch 执行但无输出 | compute, dispatch |
| `05_compute/case_storage_image_layout_wrong.md` | storage image 写入 / 采样异常 | storage-image, layout |
| `05_compute/case_storage_buffer_not_visible.md` | buffer 写入后 graphics 读不到 | storage-buffer, visibility |
| `05_compute/case_compute_output_overwritten.md` | compute 输出被后续 pass 覆盖 | compute, lifetime |

---

## 6. 性能类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `06_performance/case_fullscreen_pass_bandwidth_high.md` | 后处理开启后 GPU frame time 高 | fullscreen-pass, bandwidth |
| `06_performance/case_descriptor_update_cpu_overhead.md` | CPU frame time 高，descriptor 更新多 | descriptor, cpu-overhead |
| `06_performance/case_pipeline_creation_stutter.md` | 首帧或切换效果时卡顿 | pipeline, stutter |
| `06_performance/case_barrier_overuse_gpu_stall.md` | barrier 过宽导致 GPU stall | barrier, gpu-stall |
| `06_performance/case_mobile_tile_resolve_high.md` | 移动端多 pass tile resolve 高 | mobile, tile-resolve |

---

## 7. 架构类

| 案例 | 典型现象 | 关键词 |
|---|---|---|
| `07_engine_architecture/case_render_graph_resource_lifetime.md` | render graph resource 生命周期错误 | render-graph, lifetime |
| `07_engine_architecture/case_per_frame_resource_design.md` | per-frame resource 设计不清导致串帧 | frame-resource |
| `07_engine_architecture/case_swapchain_dependent_resource_group.md` | 尺寸相关资源重建遗漏 | swapchain-dependent |
| `07_engine_architecture/case_pipeline_cache_strategy.md` | pipeline 创建卡顿 | pipeline-cache |

---

## 8. 标签说明

- `case_tags.md`：案例通用标签与关键词释义。

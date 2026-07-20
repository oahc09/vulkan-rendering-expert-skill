# Error Index

> 文件建议路径：`error_index.md`

---

## 用途

当遇到具体 Validation Message、错误码或现象时，先查本索引定位到：

1. 解释该错误的 **API Card**（对象/字段/生命周期）。
2. 可执行的 **Debug Playbook**。
3. 可参考的 **Case**（真实工程复盘）。

---

## 按错误码 / 返回值

| 错误码 / 返回值 | 含义 | 优先 Debug Playbook | 优先 API Card |
|---|---|---|---|
| `VK_ERROR_OUT_OF_DATE_KHR` | Swapchain 与 surface 不再兼容 | `../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md` | `02_surface_swapchain/swapchain_recreate.md` |
| `VK_ERROR_SURFACE_LOST_KHR` | Surface 已失效 | `../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md` | `02_surface_swapchain/surface.md` |
| `VK_SUBOPTIMAL_KHR` | Swapchain 仍可 present，但建议 recreate | `../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md` | `02_surface_swapchain/swapchain.md` |
| `VK_ERROR_DEVICE_LOST` | GPU 执行异常 / 驱动 reset | `../04_debug_playbooks/02_crash_hang/device_lost.md` | `03_command_buffer/queue_submit.md`<br>`08_synchronization/fence.md` |
| `VK_TIMEOUT` | `vkWaitForFences` 超时 | `../04_debug_playbooks/02_crash_hang/gpu_hang.md` | `08_synchronization/fence.md` |

---

## 按 Validation Message 类型

| Message 关键词 | 典型根因 | 优先 Debug Playbook | 优先 API Card |
|---|---|---|---|
| `descriptor set layout binding mismatch` | shader binding 与 layout 不一致 | `../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md` | `05_descriptor/descriptor_set_layout.md` |
| `pipeline layout incompatible` | 绑定的 layout 与 pipeline 不兼容 | `../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md` | `06_pipeline/pipeline_layout.md` |
| `descriptor image layout` | descriptor imageLayout 与实际 layout 不一致 | `../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md` | `05_descriptor/descriptor_update.md`<br>`04_buffer_image_memory/image.md` |
| `image layout mismatch` / `TRANSFER_DST_OPTIMAL` | 缺少 layout transition | `../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md` | `08_synchronization/image_memory_barrier.md` |
| `synchronization hazard` / `WRITE_AFTER_READ` | 缺少 barrier / stage-access 错误 | `../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md` | `08_synchronization/pipeline_barrier.md` |
| `command buffer reset in flight` | 复用仍在 pending 的 command buffer | `../04_debug_playbooks/03_validation_errors/validation_error_decode.md` | `03_command_buffer/command_buffer_lifetime.md` |
| `VUID-vkAcquireNextImageKHR-surface-*` | surface 无效或已改变 | `../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md` | `02_surface_swapchain/surface.md` |
| `VUID-vkQueuePresentKHR-surface-*` | present 时 surface/swapchain 状态不匹配 | `../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md` | `02_surface_swapchain/swapchain.md` |

---

## 按现象

| 现象 | 优先 Debug Playbook | 优先 API Card | 参考 Case |
|---|---|---|---|
| 黑屏 | `../04_debug_playbooks/01_visual_issues/black_screen.md` | `06_pipeline/graphics_pipeline.md`<br>`08_synchronization/image_memory_barrier.md` | `../06_cases/01_black_screen/case_black_screen.md` |
| 闪烁 | `../04_debug_playbooks/01_visual_issues/flickering.md` | `08_synchronization/fence.md`<br>`05_descriptor/descriptor_set.md` | `../06_cases/03_sync_layout/case_sync_layout.md` |
| 纹理黑 / 采样异常 | `../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md` | `05_descriptor/descriptor_update.md`<br>`04_buffer_image_memory/image.md` | `../06_cases/01_black_screen/case_black_screen.md` |
| Compute 无输出 | `../04_debug_playbooks/04_resource_sync/compute_no_output.md`<br>`../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md` | `06_pipeline/compute_pipeline.md`<br>`08_synchronization/pipeline_barrier.md` | `../06_cases/05_compute/case_compute.md` |
| GPU hang / TDR | `../04_debug_playbooks/02_crash_hang/gpu_hang.md` | `08_synchronization/pipeline_barrier.md`<br>`06_pipeline/graphics_pipeline.md` | — |
| Device lost | `../04_debug_playbooks/02_crash_hang/device_lost.md` | `03_command_buffer/queue_submit.md` | `../06_cases/04_swapchain_android/case_swapchain_android.md` |
| Swapchain recreate crash | `../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md` | `02_surface_swapchain/swapchain_recreate.md` | `../06_cases/04_swapchain_android/case_swapchain_android.md` |
| Android pause/resume 黑屏 | `../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md` | `02_surface_swapchain/swapchain_recreate.md`<br>`08_synchronization/fence.md` | `../06_cases/04_swapchain_android/case_swapchain_android.md` |

---

## 按性能症状

| 症状 | 优先 Debug Playbook | 优先 Workflow |
|---|---|---|
| GPU frame time 高 | `../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md` | `../05_workflows/07_optimization/optimize_frame_time.md` |
| Bandwidth 高 | `../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md` | `../05_workflows/07_optimization/optimize_mobile_bandwidth.md` |
| Barrier 过多 | `../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md` | `../05_workflows/07_optimization/optimize_barriers.md` |
| Descriptor update 开销高 | `../04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md` | `../05_workflows/07_optimization/optimize_descriptor_updates.md` |
| Fullscreen pass 重 | `../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md` | `../05_workflows/07_optimization/optimize_fullscreen_pass.md` |

---

## 不确定时

若 VUID / 错误码无法在本索引找到：

1. 先读 `09_debug_validation/vuid_decode.md` 拆解 message 结构。
2. 沿对象链路反查相关 API Card。
3. 必要时回查 [Vulkan Specification](https://registry.khronos.org/vulkan/specs/) 与 [Vulkan Valid Usage Database](https://vulkan.lunarg.com/doc/sdk/)。

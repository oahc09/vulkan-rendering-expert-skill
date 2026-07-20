# Debug Priority Index

> 文件建议路径：`debug_priority_index.md`

---

## 1. 黑屏

优先排查：

1. Render loop 是否执行。
2. `vkAcquireNextImageKHR` 是否成功。
3. CommandBuffer 是否录制。
4. `vkQueueSubmit` 是否执行。
5. `vkQueuePresentKHR` 是否成功。
6. Clear color 是否可见。
7. Viewport / Scissor 是否正确。
8. Graphics Pipeline 是否创建和绑定。
9. Descriptor 是否绑定。
10. Image layout 是否正确。
11. Depth test 是否把内容裁掉。
12. MVP 是否把模型送出裁剪空间。
13. Android Surface 是否 destroyed / recreated。

相关 Playbook：

- `01_visual_issues/black_screen.md`
- `01_visual_issues/depth_test_wrong.md`

---

## 2. 闪烁

优先排查：

1. Frames-in-flight 同步是否正确。
2. Fence wait/reset 顺序是否正确。
3. Swapchain image 是否被重复写入。
4. CommandBuffer 是否被错误复用。
5. Uniform buffer 是否被 CPU 覆盖但 GPU 仍在读取。
6. Descriptor 是否引用了错误 frame resource。
7. Present / acquire semaphore 是否错配。

相关 Playbook：

- `01_visual_issues/flickering.md`

---

## 3. Validation Error

优先排查：

1. 提取 VUID。
2. 判断错误类型。
3. 定位 object handle / object type。
4. 找创建点。
5. 找使用点。
6. 沿对象链路反查。
7. 给出最小修复。
8. 回归验证 validation clean。

相关 Playbook：

- `03_validation_errors/validation_error_decode.md`
- `03_validation_errors/memory_leak.md`
- `03_validation_errors/descriptor_pipeline_layout_errors.md`

---

## 4. Descriptor Binding Error

优先沿以下链路排查：

```text
Shader set/binding
→ DescriptorSetLayout
→ PipelineLayout
→ DescriptorSet Allocation
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

相关 Playbook：

- `03_validation_errors/descriptor_pipeline_layout_errors.md`

---

## 5. Image Layout Error

优先沿以下链路排查：

```text
Image usage
→ ImageView
→ Producer pass
→ Barrier / Layout Transition
→ Descriptor imageLayout / Attachment layout
→ Consumer pass
```

相关 Playbook：

- `03_validation_errors/layout_sync_hazard_errors.md`

---

## 6. Swapchain Recreate Crash

优先排查：

1. Surface / ANativeWindow 是否仍有效。
2. 是否处理 `VK_ERROR_OUT_OF_DATE_KHR`。
3. 是否处理 `VK_SUBOPTIMAL_KHR`。
4. 是否等待 in-flight GPU 工作完成。
5. 是否销毁旧 swapchain 相关资源。
6. 是否重建 swapchain image views。
7. depth / framebuffer / offscreen render target 是否同步重建。
8. command buffer 是否仍引用旧 framebuffer / image view。
9. descriptor 是否仍引用旧尺寸资源。

相关 Playbook：

- `02_crash_hang/swapchain_recreate_crash.md`
- `05_android_specific/android_surface_lifecycle.md`

---

## 7. Compute 无输出

优先排查：

1. dispatch 是否执行。
2. workgroup 数量是否正确。
3. descriptor 是否绑定 storage buffer / storage image。
4. storage image layout 是否正确。
5. compute 写后 graphics 读是否有 barrier。
6. shader 中写入坐标是否越界。
7. output image / buffer 是否被后续 pass 正确读取。

相关 Playbook：

- `04_resource_sync/compute_no_output.md`
- `04_resource_sync/compute_graphics_sync_error.md`

---

## 8. GPU Hang / TDR

优先排查：

1. 特定 draw / dispatch 是否触发。
2. Shader 是否存在无限循环或过长执行。
3. 是否存在同步 hazard / 资源竞争。
4. Barrier stage / access 是否完整。
5. Compute workgroup / 寄存器压力是否过大。

相关 Playbook：

- `02_crash_hang/gpu_hang.md`

---

## 9. Device Lost

优先排查：

1. 提取 `VK_ERROR_DEVICE_LOST` 发生前的最后一条命令。
2. 检查 pipeline / render pass / layout 兼容性。
3. 检查是否存在越界读写、未初始化资源、in-flight 销毁。
4. 检查 queue submit 与 fence 状态。

相关 Playbook：

- `02_crash_hang/device_lost.md`

---

## 10. Synchronization Hazard

优先排查：

1. 提取 VUID 中的 hazard 类型（WAR / WAW / RAW）。
2. 确认 producer stage / access 与 consumer stage / access。
3. 确认 barrier / event / subpass dependency 是否覆盖该依赖。
4. 跨 queue 时是否使用 semaphore。

相关 Playbook：

- `03_validation_errors/layout_sync_hazard_errors.md`

---

## 11. Compute → Graphics 同步错误

优先排查：

1. Storage image / storage buffer 是否已做 availability barrier。
2. Storage image layout 是否为 `GENERAL`。
3. 跨 queue 时是否使用 semaphore。
4. Descriptor 是否指向正确资源。

相关 Playbook：

- `04_resource_sync/compute_graphics_sync_error.md`

---

## 12. 性能症状

按症状选择：

| 症状 | Playbook |
|---|---|
| CPU frame time 高 | `06_performance_symptoms/cpu_overhead_symptoms.md` |
| GPU frame time 高 | `06_performance_symptoms/gpu_frame_time_high.md` |
| Bandwidth 高 | `06_performance_symptoms/bandwidth_fullscreen_cost.md` |
| Barrier 过多 | `06_performance_symptoms/barrier_draw_call_stall.md` |
| Descriptor update 开销高 | `06_performance_symptoms/cpu_overhead_symptoms.md` |
| Draw call 瓶颈 | `06_performance_symptoms/barrier_draw_call_stall.md` |
| Fullscreen pass 开销高 | `06_performance_symptoms/bandwidth_fullscreen_cost.md` |
| Pipeline 创建卡顿 | `06_performance_symptoms/pipeline_startup_stutter.md` |
| 启动时间过长 | `06_performance_symptoms/pipeline_startup_stutter.md` |

---

## 13. 工具使用

| 工具 / 主题 | Playbook |
|---|---|
| Validation Layer / RenderDoc / AGI / logcat 通用方法 | `tool_usage.md` |

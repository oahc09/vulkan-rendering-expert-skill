# 04_debug_playbooks：Vulkan 调试专家手册模块

## 1. 模块定位

`04_debug_playbooks` 是 Vulkan Expert Skill 的调试专家手册模块。

它以真实工程问题为入口，不以 API 为入口。
它的目标是让 AI 像高级 Vulkan 渲染工程师一样，根据现象快速建立排查路径：

```text
现象
→ 最可能原因排序
→ 快速验证
→ Vulkan 对象链路排查
→ 高频根因
→ 修复方案
→ 回归验证
```

---

## 2. 模块目标

本模块用于解决 Vulkan 工程中高频、复杂、容易误判的问题：

- 黑屏
- 闪烁
- Crash
- GPU Hang
- Device Lost
- Validation Error
- Descriptor Binding Error
- Image Layout Error
- Swapchain Recreate Crash
- Android Surface / ANativeWindow 生命周期问题
- Compute 无输出
- Compute / Graphics 同步错误
- 帧耗时异常
- Barrier 过度保守
- Descriptor 更新开销高
- Fullscreen Pass 成本高

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
根据真实故障现象组织排查路径，并引用 02/03 模块内容。
```

---

## 4. 核心原则

1. 不直接猜 shader 问题，先排查 Vulkan 渲染链路。
2. 不只解释原因，必须给出验证路径。
3. 不只说“检查同步”，必须说明 producer / consumer / stage / access。
4. 不只说“检查 descriptor”，必须沿 shader → layout → pipeline layout → set → update → bind → resource lifetime 排查。
5. 不只说“重建 swapchain”，必须说明旧资源、in-flight command buffer、depth/offscreen attachment 是否同步重建。
6. Android 问题必须考虑 Surface / ANativeWindow / pause / resume / rotation / resize。
7. 不确定时不下确定结论，必须要求或建议补充 Validation message、VUID、RenderDoc/AGI capture、logcat、关键代码片段。
8. 每个 Playbook 必须链接相关 API 卡片。

---

## 5. 推荐目录结构

```text
04_debug_playbooks/
├── README.md
├── debug_playbook_template.md
├── debug_priority_index.md
├── tool_usage.md
│
├── 01_visual_issues/
│   ├── black_screen.md
│   ├── flickering.md
│   └── depth_test_wrong.md
│
├── 02_crash_hang/
│   ├── swapchain_recreate_crash.md
│   ├── gpu_hang.md
│   └── device_lost.md
│
├── 03_validation_errors/
│   ├── validation_error_decode.md
│   ├── descriptor_pipeline_layout_errors.md   （合并 descriptor_binding_error + pipeline_layout_error）
│   ├── layout_sync_hazard_errors.md           （合并 image_layout_error + synchronization_hazard）
│   └── memory_leak.md
│
├── 04_resource_sync/
│   ├── compute_no_output.md
│   └── compute_graphics_sync_error.md
│
├── 05_android_specific/
│   └── android_surface_lifecycle.md
│
└── 06_performance_symptoms/
    ├── cpu_overhead_symptoms.md        （合并 cpu_frame_time_high + descriptor_update_overhead）
    ├── gpu_frame_time_high.md
    ├── bandwidth_fullscreen_cost.md    （合并 bandwidth_high + fullscreen_pass_cost）
    ├── barrier_draw_call_stall.md      （合并 barrier_overuse + draw_call_bottleneck）
    └── pipeline_startup_stutter.md     （合并 pipeline_creation_stutter + startup_time_high）
```

> 每个合并文件内部以 `## Debug Playbook: <原 playbook 名>` 作为锚点保留全部内容，向量检索仍可命中原 playbook 主题。

---

## 6. P0 首批 Playbook

第一批建议优先完成（均已实现）：

```text
01_visual_issues/black_screen.md
01_visual_issues/flickering.md
01_visual_issues/depth_test_wrong.md
02_crash_hang/swapchain_recreate_crash.md
02_crash_hang/gpu_hang.md
02_crash_hang/device_lost.md
03_validation_errors/validation_error_decode.md
03_validation_errors/descriptor_pipeline_layout_errors.md
03_validation_errors/layout_sync_hazard_errors.md
03_validation_errors/memory_leak.md
04_resource_sync/compute_no_output.md
04_resource_sync/compute_graphics_sync_error.md
05_android_specific/android_surface_lifecycle.md
06_performance_symptoms/cpu_overhead_symptoms.md
06_performance_symptoms/gpu_frame_time_high.md
06_performance_symptoms/bandwidth_fullscreen_cost.md
06_performance_symptoms/barrier_draw_call_stall.md
06_performance_symptoms/pipeline_startup_stutter.md
```

这些 Playbook 覆盖黑屏、闪烁、Crash、GPU Hang、Device Lost、Validation Error、Descriptor、Image Layout、Sync Hazard、Compute 无输出、Android 生命周期和常见性能症状。

# 06_cases：Vulkan 真实案例库模块

## 1. 模块定位

`06_cases` 是 Vulkan Expert Skill 的真实案例库模块。

它以真实工程问题复盘为核心，记录：

```text
现象
→ 初始上下文
→ 初始误判
→ 排查路径
→ 关键证据
→ 根因
→ 修复方案
→ 修复后验证
→ 经验抽象
→ 预防规则
```

它不是 API 手册、不是 Debug Playbook、也不是 Workflow，而是用于沉淀真实 Vulkan 工程经验。

---

## 2. 模块目标

本模块的目标是把前面模块中的抽象规则转化为真实经验：

| 前置模块 | 提供内容 |
|---|---|
| `03_api_manual` | API 对象链路与使用风险 |
| `04_debug_playbooks` | 故障排查流程 |
| `05_workflows` | 正向工程任务流程 |
| `06_cases` | 真实问题如何发生、如何误判、如何定位、如何修复 |

高级 Vulkan 专家的价值通常来自案例判断，例如：

```text
这个黑屏不像 shader 错，更像 layout transition 缺失。
这个闪烁不像 present 问题，更像 frame resource 被 CPU 提前覆盖。
这个 Android 崩溃不像 Vulkan 初始化错，更像 Surface destroyed 后 render thread 还在 present。
这个 compute 无输出不像 dispatch 没执行，更像 compute 写后 graphics 读缺少 barrier。
```

这些判断需要通过 case 来沉淀。

---

## 3. 推荐目录结构

```text
06_cases/
├── README.md
├── case_template.md
├── case_index.md
├── case_tags.md
│
├── 01_black_screen/
│   ├── case_black_screen_image_layout.md
│   ├── case_black_screen_no_submit.md
│   ├── case_black_screen_wrong_viewport.md
│   └── case_black_screen_depth_cull.md
│
├── 02_descriptor_pipeline/
│   ├── case_descriptor_binding_mismatch.md
│   ├── case_pipeline_layout_mismatch.md
│   ├── case_descriptor_old_image_after_resize.md
│   └── case_uniform_alignment_error.md
│
├── 03_sync_layout/
│   ├── case_compute_to_fragment_missing_barrier.md
│   ├── case_transfer_to_shader_missing_transition.md
│   ├── case_frame_resource_overwrite.md
│   └── case_command_buffer_reset_in_flight.md
│
├── 04_swapchain_android/
│   ├── case_android_rotation_old_imageview.md
│   ├── case_surface_destroy_present_crash.md
│   ├── case_pause_resume_black_screen.md
│   └── case_extent_zero_swapchain_create.md
│
├── 05_compute/
│   ├── case_compute_dispatch_zero.md
│   ├── case_storage_image_layout_wrong.md
│   ├── case_storage_buffer_not_visible.md
│   └── case_compute_output_overwritten.md
│
├── 06_performance/
│   ├── case_fullscreen_pass_bandwidth_high.md
│   ├── case_descriptor_update_cpu_overhead.md
│   ├── case_pipeline_creation_stutter.md
│   ├── case_barrier_overuse_gpu_stall.md
│   └── case_mobile_tile_resolve_high.md
│
└── 07_engine_architecture/
    ├── case_render_graph_resource_lifetime.md
    ├── case_per_frame_resource_design.md
    ├── case_swapchain_dependent_resource_group.md
    └── case_pipeline_cache_strategy.md
```

---

## 4. P0 首批案例

第一批建议优先完成 12 个高价值案例：

### 黑屏类

- `01_black_screen/case_black_screen_image_layout.md`
- `01_black_screen/case_black_screen_no_submit.md`
- `01_black_screen/case_black_screen_wrong_viewport.md`

### Descriptor / Pipeline 类

- `02_descriptor_pipeline/case_descriptor_binding_mismatch.md`
- `02_descriptor_pipeline/case_pipeline_layout_mismatch.md`
- `02_descriptor_pipeline/case_descriptor_old_image_after_resize.md`

### 同步 / Layout 类

- `03_sync_layout/case_compute_to_fragment_missing_barrier.md`
- `03_sync_layout/case_frame_resource_overwrite.md`
- `03_sync_layout/case_command_buffer_reset_in_flight.md`

### Android Swapchain 类

- `04_swapchain_android/case_android_rotation_old_imageview.md`
- `04_swapchain_android/case_surface_destroy_present_crash.md`
- `04_swapchain_android/case_extent_zero_swapchain_create.md`

---

## 5. 使用方式

当用户提出真实问题时，优先根据现象检索 case：

```text
黑屏
→ 查 01_black_screen

descriptor 报错
→ 查 02_descriptor_pipeline

compute 输出异常
→ 查 03_sync_layout 或 05_compute

Android rotation / pause / resume 崩溃
→ 查 04_swapchain_android

GPU frame time 高
→ 查 06_performance
```

每个 case 必须连接：

- 相关 API 卡片
- 相关 Debug Playbook
- 相关 Workflow
- 关键工具证据
- 可复用预防规则

# Case Index

> 文件建议路径：`case_index.md`
>
> 每个 category 文件合并自多个原 case，使用 `## Case: <原 case 名>` 锚点保留全部内容。

---

## 1. 黑屏类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `01_black_screen/case_black_screen.md` | 5 | black-screen, image-layout, no-submit, viewport, depth, cull |

---

## 2. Descriptor / Pipeline 类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `02_descriptor_pipeline/case_descriptor_pipeline.md` | 4 | descriptor, binding, pipeline-layout, uniform, alignment, resize, old-image |

---

## 3. 同步 / Layout 类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `03_sync_layout/case_sync_layout.md` | 5 | compute-barrier, transfer-transition, frame-resource, command-buffer-reset |

---

## 4. Android / Swapchain 类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `04_swapchain_android/case_swapchain_android.md` | 5 | android, rotation, surface, pause-resume, extent-zero, present-crash |

---

## 5. Compute 类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `05_compute/case_compute.md` | 4 | compute, dispatch-zero, storage-image, storage-buffer, output-overwrite |

---

## 6. 性能类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `06_performance/case_performance.md` | 5 | fullscreen-pass, descriptor-cpu, pipeline-stutter, barrier-stall, tile-resolve |

---

## 7. 架构类

| 合并文件 | 包含 case 数 | 典型现象关键词 |
|---|---|---|
| `07_engine_architecture/case_engine_architecture.md` | 9 | render-graph, per-frame, swapchain-dependent, pipeline-cache, bindless-migration, render-graph-adoption, lifetime-split, async-compute, Arm-NSS-NFRU, QHWI, Filament-instance-material |

---

## 8. 标签说明

- `case_tags.md`：案例通用标签与关键词释义。

移动SDK/框架迁移的固定版本案例见 [契约边界](07_engine_architecture/case_engine_architecture.md#mobile-sdk-framework-contracts)，不是本地构建/设备验收。

Android系统渲染设计案例（非真机事故报告）：[多输出代际](04_swapchain_android/case_swapchain_android.md#multi-output-generation-case)、[媒体早归还](03_sync_layout/case_sync_layout.md#android-media-early-return)、[颜色/alpha](01_black_screen/case_black_screen.md#android-alpha-color-case)。

## v1.0.13 规模化设计案例（非事故实测）

- [GPU命令正确但独立count未同步](03_sync_layout/case_sync_layout.md#gpu-command-count-visibility)
- [GPU-driven变慢不等于实现无价值](06_performance/case_performance.md#gpu-driven-fair-baseline)
- [热更新与流式取消迟到污染新场景](07_engine_architecture/case_engine_architecture.md#shader-streaming-generation)

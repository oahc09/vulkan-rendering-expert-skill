# 推荐可信来源清单

本文件用于维护 Vulkan Skill 的可信资料入口。后续 API Manual、Debug Playbook、Workflow 和 Case 应优先从这些来源提炼。

## Khronos / Vulkan 官方

| 来源 | 用途 |
|---|---|
| Vulkan Registry | Spec、Reference Pages、Headers、扩展、版本入口 |
| Vulkan Specification | API 规范、Valid Usage、同步规则、对象生命周期 |
| Vulkan Reference Pages | 单个 API、结构体、枚举、flag 细节 |
| Vulkan Guide | 机制解释、同步示例、版本迁移、扩展说明 |
| Vulkan Samples | API / Performance / Extension / Tooling 示例 |
| Khronos Vulkan Tutorial | 基础流程和入门链路 |
| Vulkan-ValidationLayers | Validation Layer 能力、限制、配置 |

## Android 官方

| 来源 | 用途 |
|---|---|
| Android NDK Vulkan validation layer 文档 | Android 开发期 validation layer 接入 |
| Android Game Vulkan 文档 | Android Vulkan 工具、调试和进阶能力 |
| Android GPU Inspector 文档 | Android GPU frame profiling、counter、trace |
| AOSP Vulkan 实现文档 | Android 图形栈和 Vulkan 平台实现 |

## GPU 厂商

| 来源 | 用途 |
|---|---|
| Arm Mali Vulkan Best Practices | 移动端 tile-based GPU、带宽、attachment 优化 |
| Qualcomm Adreno / Snapdragon Profiler | Adreno GPU 性能分析 |
| NVIDIA Vulkan Best Practices | 桌面 GPU Vulkan 性能建议 |
| AMD GPUOpen Vulkan | RDNA / shader / memory / async compute 经验 |
| Intel GPA 文档 | Intel GPU profiling |

## 工具链

| 工具 | 用途 |
|---|---|
| Validation Layer | API 使用错误、VUID、对象生命周期、同步验证 |
| RenderDoc | Frame capture、draw call、pipeline state、texture / attachment 查看 |
| Android GPU Inspector | Android GPU frame profiling、counter、trace |
| logcat | Android Surface / Swapchain / NDK 日志 |
| shader reflection 工具 | SPIR-V binding、set、资源类型验证 |

## 使用备注

1. 官方 Spec 和 Reference Pages 是 API 事实源。
2. Vulkan Guide / Samples 适合转写成专家解释和工程模式。
3. Android 相关行为必须参考 Android 官方文档。
4. 厂商最佳实践不能无条件泛化。
5. 工具输出是 Debug Playbook 的核心证据。

# 来源优先级

Vulkan Skill 的内容不能只靠模型记忆。所有细节应尽量从可信来源获取，并按优先级处理。

## P0：官方事实源

用于确认 API 规则、结构体字段、flag、扩展、对象生命周期、同步规则、VUID。

| 来源 | 用途 | 标记 |
|---|---|---|
| Vulkan Specification | Vulkan API 的最终规范依据 | `[SPEC]` |
| Vulkan Registry | Spec、Reference Pages、Headers、扩展、版本入口 | `[REGISTRY]` |
| Vulkan Reference Pages | 单个 API / 结构体 / 枚举的参数和 Valid Usage | `[REF]` |
| Vulkan Headers | 真实类型、枚举、宏、扩展定义 | `[HEADER]` |

使用规则：

```text
只要涉及 API 参数、合法用法、对象生命周期、同步规则、VUID，优先查 P0。
```

## P1：官方解释源

用于理解 Vulkan 机制、常用模式、版本迁移、官方示例。

| 来源 | 用途 | 标记 |
|---|---|---|
| Vulkan Guide | 机制解释、版本建议、扩展解释、同步示例 | `[GUIDE]` |
| Khronos Vulkan Tutorial | 基础流程、Hello Triangle、Swapchain、Pipeline 等入门链路 | `[TUTORIAL]` |
| Khronos Vulkan Samples | API 示例、性能样例、扩展示例、工具样例 | `[SAMPLE]` |
| Vulkan SDK / LunarG 文档 | SDK、Validation、工具链、调试配置 | `[SDK]` |

使用规则：

```text
P1 可以用于解释和模式建议，但不能覆盖 P0 的规范结论。
```

## P2：平台源

用于处理 Android Vulkan、Surface、NDK、AGI、validation layer 接入等平台问题。

| 来源 | 用途 | 标记 |
|---|---|---|
| Android NDK Vulkan 文档 | Android validation layer、debug utils、NDK Vulkan 开发 | `[ANDROID]` |
| Android Game Vulkan 文档 | Android Vulkan 工具和进阶功能 | `[ANDROID_GAME]` |
| Android GPU Inspector 文档 | GPU trace、counter、frame profiling | `[AGI]` |
| Android Source 文档 | Vulkan 实现、平台支持、图形栈说明 | `[AOSP]` |

使用规则：

```text
Android 生命周期、debug layer、AGI profiling、ANativeWindow 相关内容必须查 P2。
```

## P3：GPU 厂商经验源

用于性能优化、移动端 tile-based GPU、桌面 GPU 特性、驱动实践。

| 来源 | 用途 | 标记 |
|---|---|---|
| Arm Mali Best Practices | 移动端 tile-based GPU、带宽、render pass、attachment | `[VENDOR_ARM]` |
| Qualcomm Adreno / Snapdragon Profiler | Android GPU、Adreno 性能和工具 | `[VENDOR_QCOM]` |
| NVIDIA Vulkan Best Practices | 桌面 GPU、pipeline、descriptor、barrier 建议 | `[VENDOR_NV]` |
| AMD GPUOpen Vulkan | RDNA、async compute、memory、shader 优化 | `[VENDOR_AMD]` |
| Intel GPA 文档 | Intel GPU profiling | `[VENDOR_INTEL]` |

使用规则：

```text
厂商建议必须说明适用平台，不能写成跨所有 GPU 的绝对规则。
```

## P4：工程沉淀源

用于 Debug Playbook、Case、性能复盘和专家经验。

| 来源 | 用途 | 标记 |
|---|---|---|
| 项目 Bug 复盘 | 高频故障、真实修复路径 | `[CASE]` |
| RenderDoc Capture | Draw call、attachment、descriptor、pipeline 状态验证 | `[TOOL]` |
| AGI Trace | Android GPU 性能和 frame profiling | `[TOOL]` |
| Validation Error | VUID、对象、错误类型归纳 | `[TOOL]` |
| 引擎代码审查 | 架构经验、资源生命周期、Render Graph | `[ENGINE]` |

使用规则：

```text
工程经验可以指导排错顺序，但必须标注经验来源和适用边界。
```

## 不可信来源

以下内容不能作为最终事实源：

1. 未注明 Vulkan 版本的博客文章。
2. 过时 GitHub demo。
3. 没有 validation 验证的代码片段。
4. 没有平台边界的性能建议。
5. AI 生成但未经 Spec / Tool / Case 验证的 API 细节。
6. 只适用于特定 GPU、驱动或引擎的经验，却被写成通用规则。

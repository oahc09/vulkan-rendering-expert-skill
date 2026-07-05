# Accuracy Check

## Rule Source Levels

完整标签定义与可信等级参见 `01_source_map_and_api_manual_strategy/source_tags.md`。本文件仅列出常用标签与核心要求：

| 标签 | 含义 | 可信等级 |
|---|---|---|
| `[SPEC]` | Vulkan Specification 明确要求 | 最高 |
| `[REGISTRY]` | Vulkan Registry / API Reference / Headers | 最高 |
| `[REF]` | Reference Page 中的 API / 结构体说明 | 最高 |
| `[GUIDE]` | Vulkan Guide 官方解释或建议 | 高 |
| `[SAMPLE]` | Khronos / 官方 Samples 示例 | 高 |
| `[ANDROID]` | Android NDK / Android 官方 Vulkan 文档 | 高 |
| `[AGI]` | Android GPU Inspector 文档或 Trace 结果 | 高 |
| `[VENDOR]` | GPU 厂商最佳实践 | 中高，需平台边界 |
| `[TOOL]` | Validation / RenderDoc / AGI 可验证 | 高 |
| `[ENGINE]` | 图形引擎工程经验 | 中，需案例支持 |
| `[CASE]` | 真实项目案例或故障复盘 | 中高，需上下文 |
| `[HEUR]` | 启发式经验 | 中低，不能写死 |

## Accuracy Requirements

1. 硬规则必须至少满足 `[SPEC]`、`[REGISTRY]`、`[REF]` 或 Android 平台限定下的 `[ANDROID]` 之一。`[GUIDE]`、`[SAMPLE]`、`[TOOL]` 可支撑默认建议，但不能单独支撑硬规则。
2. Debug playbook 必须能被真实故障案例验证。
3. 性能建议必须标注是工具可测还是经验判断。
4. 不确定的 API 细节不得写成确定结论。
5. 和平台强相关的建议必须说明适用条件。
6. 所有工程方案必须提供验证方式。
7. 对于 Vulkan API 细节，优先回查 Vulkan Spec / Vulkan Guide。
8. 对于 Android Vulkan 细节，优先回查 Android NDK 文档。
9. 对于性能结论，优先用 profiler / trace / counter / frame capture 验证。

## Recommended Label Usage

示例：

- Image layout 不匹配可能导致 validation error 或渲染结果错误。[SPEC][TOOL]
- 黑屏优先检查 acquire / submit / present 链路。[ENGINE][TOOL]
- 移动端 full-screen pass 过多容易造成 bandwidth 压力。[ENGINE][HEUR]
- 新项目可优先考虑 Dynamic Rendering，但要结合目标设备和引擎兼容性。[GUIDE][ENGINE]

## Accuracy Review Checklist

评审一个规则或方案时，检查：

1. 是否有明确适用场景？
2. 是否说明不适用场景？
3. 是否有官方依据或工具验证路径？
4. 是否避免绝对化表达？
5. 是否能被真实任务测试？
6. 是否能定位到 Vulkan 对象和调用链路？

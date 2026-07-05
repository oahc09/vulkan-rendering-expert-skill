# 来源标签与可信等级

为了让 Skill 的内容可追溯，所有关键判断建议标记来源等级。

## 标签定义

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

## 规则强度

### 可以写成硬规则

满足以下任一条件：

```text
[SPEC]
[REGISTRY]
[REF]
[ANDROID] 且问题限定 Android 平台
```

示例：

```text
DescriptorSetLayout、PipelineLayout、Shader binding 必须匹配。[SPEC]
Android 开发期使用 validation layer 进行 Vulkan 错误检查。[ANDROID]
```

### 可以写成默认建议

满足以下任一条件：

```text
[GUIDE]
[SAMPLE]
[VENDOR] 且适用平台明确
[TOOL] 可直接验证
```

示例：

```text
新项目可以优先考虑 Dynamic Rendering，减少 RenderPass / Framebuffer 预声明复杂度。[GUIDE][SAMPLE]
```

### 只能写成经验判断

满足以下任一条件：

```text
[ENGINE]
[CASE]
[HEUR]
```

示例：

```text
黑屏时优先检查 acquire / submit / present / clear color，再深入检查 shader。[ENGINE][TOOL]
```

## 写作要求

1. 硬规则必须有 `[SPEC]` / `[REGISTRY]` / `[REF]` / `[ANDROID]` 支撑。
2. 性能建议如果来自厂商或经验，必须标注适用条件。
3. Debug Playbook 可以使用经验排序，但必须能被工具验证。
4. 不确定细节不得写成确定结论。
5. 过时或版本不明的内容只能作为参考，不能进入核心规则。

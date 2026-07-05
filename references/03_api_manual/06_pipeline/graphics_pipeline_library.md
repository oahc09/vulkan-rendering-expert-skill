# API Card: VK_EXT_graphics_pipeline_library

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkGraphicsPipelineCreateInfo`（带 library flags） |
| 常用 API | `vkCreateGraphicsPipelines` |
| 适用平台 | 通用（需设备支持） |
| 来源等级 | `[SPEC] [GUIDE] [ENGINE]` |
| 适用 Vulkan 版本 | `VK_EXT_graphics_pipeline_library` / Vulkan 1.3 optional |

---

## 1. 一句话定位

`VK_EXT_graphics_pipeline_library` 允许把 graphics pipeline 拆分为 vertex input、pre-rasterization、fragment shader、fragment output 等独立库，分别编译后按需链接，从而显著降低运行时组合变体的创建耗时。[SPEC]

---

## 2. 所属对象链路

```text
VkPipeline（library，含部分状态）
→ vkCreateGraphicsPipelines（flags = VK_PIPELINE_CREATE_LIBRARY_BIT_KHR）
→ VkPipeline libraries[]
→ vkCreateGraphicsPipelines（flags = VK_PIPELINE_CREATE_LINK_TIME_OPTIMIZATION_BIT_EXT）
→ 完整的 VkPipeline
```

### 上游依赖

- 设备支持 `VK_EXT_graphics_pipeline_library`。[SPEC]
- 启用对应的 device feature。[SPEC]
- 每个 library 包含 pipeline 的一部分状态。

### 下游影响

- 不同 shader/material 组合可通过链接已有 library 快速生成完整 pipeline。
- 降低运行时 `vkCreateGraphicsPipelines` 的 CPU 开销。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkGraphicsPipelineLibraryCreateInfoEXT`
- `VkPipelineLibraryCreateInfoKHR`
- `VkPipeline`（作为 library）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateGraphicsPipelines` | 创建 library pipeline 或链接后的完整 pipeline。[SPEC] |

### 相关扩展 / 版本

- `VK_EXT_graphics_pipeline_library`。
- 需要 `VK_KHR_pipeline_library`。
- Vulkan 1.3 核心未包含，仍为扩展。

---

## 4. 标准使用流程

```text
检查 VK_EXT_graphics_pipeline_library 是否支持
→ 启用 feature
→ 分别创建 vertex input library、pre-rasterization library、fragment shader library、fragment output library
→ 缓存这些 library pipeline
→ 运行时根据 material/shader 组合选择 libraries
→ 调用 vkCreateGraphicsPipelines 链接为完整 pipeline
→ 使用完整 pipeline 绘制
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `flags`（`VkGraphicsPipelineCreateInfo`） | `VK_PIPELINE_CREATE_LIBRARY_BIT_KHR` 表示创建 library；`LINK_TIME_OPTIMIZATION_BIT_EXT` 表示链接。[SPEC] | 忘记区分 library 创建与链接阶段。[TOOL] |
| `pLibraries` | 链接时传入的 library pipeline 数组。[SPEC] | library 组合不兼容或缺少必要阶段。[TOOL] |
| `libraryCount` | 必须包含完整 pipeline 所需的所有 library 阶段。[SPEC] | 缺少 vertex input 或 fragment output。[TOOL] |
| `VK_GRAPHICS_PIPELINE_LIBRARY_VERTEX_INPUT_INTERFACE_BIT_EXT` 等 | 指定当前 library 包含哪部分状态。[SPEC] | 同一 library 包含冲突状态。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 设备是否支持该扩展并启用了 feature？
- [ ] 每个 library 是否只包含允许的状态子集？
- [ ] Library 的 pipeline layout 是否与最终链接的 layout 兼容？

### 使用阶段

- [ ] 链接时是否提供了覆盖所有阶段的 library？
- [ ] 链接后的 pipeline 是否与 render pass / dynamic rendering 格式兼容？

### 销毁阶段

- [ ] 完整 pipeline 销毁后，library pipeline 可独立存在。[SPEC]
- [ ] 所有 pipeline 不再使用时再销毁 library。

---

## 7. 高频错误

1. 设备未启用 `graphicsPipelineLibrary` feature 就尝试创建 library。[TOOL]
2. Library 的 flags 与包含的状态不一致。[TOOL]
3. 链接时缺少某个必要阶段的 library。[TOOL]
4. Library 与最终 pipeline 的 layout 不兼容。[TOOL]
5. 错误地认为创建 library 后就无需再调用 `vkCreateGraphicsPipelines`。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkGraphicsPipelineLibraryCreateInfoEXT-*`：library flags 与状态子集。
- `VUID-VkPipelineLibraryCreateInfoKHR-*`：library 兼容性与完整性。

### RenderDoc / AGI

- 检查链接后的 pipeline 状态是否由预期 library 组合而成。
- 分析 library 链接与完整 pipeline 创建耗时。

### 日志 / 代码检查

- 检查 feature 启用代码。
- 检查 library 创建与链接的 flags。
- 检查 library 组合逻辑。

---

## 9. 生命周期风险

### 创建时机

- Library pipeline 通常在初始化阶段预编译；完整 pipeline 可延迟到需要时链接。[ENGINE]

### 使用时机

- 链接后的 pipeline 与普通 graphics pipeline 一样在 draw 时绑定。[SPEC]

### 销毁时机

- 完整 pipeline 可单独销毁；library pipeline 可在所有引用它的完整 pipeline 销毁后销毁。[SPEC]

### in-flight 风险

- Library 被完整 pipeline 引用后，需等完整 pipeline 不再使用才能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Library / 链接操作都是 CPU 侧编译；创建完成即可使用，无需 fence。[SPEC]

### GPU-GPU 同步

- 无。

### 资源访问同步

- 无。

---

## 11. Android 注意点

- Graphics pipeline library 在 Android 上可显著降低启动与运行时 shader 变体组合的创建耗时。[ANDROID][ENGINE]
- 需确认目标设备支持该扩展；不支持时回退到传统 pipeline 创建。[ANDROID]
- Library 的持久化与 cache 策略需要与传统 pipeline cache 结合考虑。[ENGINE]

---

## 12. 性能注意点

### CPU 侧

- 把耗时最大的编译工作移到初始化阶段，运行时只需链接，CPU 开销显著降低。[ENGINE]
- 链接阶段仍有一定开销，但通常远低于从头编译。[ENGINE]

### GPU 侧

- 链接后的 pipeline 性能通常与传统完整 pipeline 相当或略低，取决于是否启用 LTO。[ENGINE]

### 移动端

- 对 material 变体多的项目收益明显；变体少时收益有限。[ENGINE]
- 注意 library 数量与内存占用权衡。[HEUR]

---

## 13. 专家经验

**经验**：
Graphics pipeline library 最适合“阶段组合固定、但整体组合爆炸”的场景，例如同一顶点输入 + 多种 fragment shader + 多种 blend state。不要把所有状态都塞进一个 library，否则失去灵活性；也不要拆得过细，否则链接开销与对象管理复杂度会上升。建议至少把 vertex input 和 fragment output 单独成库，因为这两者变化相对独立。

**适用条件**：
多材质、多 shader 变体、启动或运行时 pipeline 创建成为瓶颈的项目。

**不适用情况**：
变体数量很少；目标设备不支持该扩展；项目已使用传统 pipeline cache 且创建耗时可接受。

**来源**：`[ENGINE][GUIDE][SPEC]`

---

## 14. 相关 API 卡片

- `graphics_pipeline.md`
- `pipeline_cache.md`
- `specialization_constants.md`
- `pipeline_layout.md`
- `shader_module.md`
- `pipeline.md`

---

## 15. 需要回查官方文档的情况

1. 设备对 `VK_EXT_graphics_pipeline_library` 的具体支持子集。
2. Library 阶段组合与完整 pipeline 的兼容性规则。
3. `VK_PIPELINE_CREATE_LINK_TIME_OPTIMIZATION_BIT_EXT` 的链接语义。
4. Library pipeline 与传统 `VkPipelineCache` 的交互。
5. 不同驱动对 library 链接性能的影响。

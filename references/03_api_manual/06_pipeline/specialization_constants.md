# API Card: VkSpecializationInfo

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkSpecializationInfo` / `VkSpecializationMapEntry` |
| 常用 API | `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkSpecializationInfo` 允许在创建 pipeline 时向 SPIR-V 中的 specialization constant 传入常量值，从而在编译期生成不同的 shader 变体，避免运行时分支与大量预编译 shader 文件。[SPEC]

---

## 2. 所属对象链路

```text
SPIR-V 中声明 specialization constant（layout(constant_id=...)）
→ VkSpecializationMapEntry（constantID / offset / size）
→ VkSpecializationInfo（mapEntryCount / pMapEntries / dataSize / pData）
→ VkPipelineShaderStageCreateInfo.pSpecializationInfo
→ vkCreateGraphicsPipelines / vkCreateComputePipelines
→ Pipeline with specialized shader
```

### 上游依赖

- Shader 中已声明 specialization constant。[SPEC]
- 知道每个 constant 的 ID、数据类型与偏移。

### 下游影响

- 决定 pipeline 创建时 shader 的具体编译结果。
- 不同 specialization 值产生不同的 pipeline 对象。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSpecializationInfo`
- `VkSpecializationMapEntry`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` | 创建 pipeline 时传入 specialization info。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- 与 `VkPipelineShaderStageCreateInfo` 绑定。

---

## 4. 标准使用流程

```text
在 shader 中声明 layout(constant_id = N) const bool USE_FEATURE = false;
→ 构造 VkSpecializationMapEntry（constantID=N, offset, size）
→ 构造 specialization data 数组
→ 构造 VkSpecializationInfo
→ 设置 VkPipelineShaderStageCreateInfo.pSpecializationInfo
→ vkCreate*Pipelines
→ 不同常量组合产生不同 pipeline 对象
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `constantID` | 与 shader 中 `constant_id` 对应。[SPEC] | ID 填错导致常量未生效。[TOOL] |
| `offset` |  specialization data 数组中的字节偏移。[SPEC] | 偏移计算错误导致读到错误值。[TOOL] |
| `size` | 常量类型大小（如 4 bytes for int32 / float32）。[SPEC] | size 与类型不匹配。[TOOL] |
| `pData` | 指向常量数据的指针；pipeline 创建期间需有效。[SPEC] | 数据在创建前被释放。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Shader 中是否正确声明了 specialization constant？
- [ ] `constantID` / `offset` / `size` 是否与 shader 声明一致？
- [ ] `pData` 生命周期是否覆盖 pipeline 创建调用？

### 使用阶段

- [ ] 是否根据 specialization 值正确选择对应的 pipeline？
- [ ] 是否需要为不同组合创建过多 pipeline 变体？

### 销毁阶段

- [ ] 无独立对象销毁；随 pipeline 销毁而失效。

---

## 7. 高频错误

1. Shader 中 `constant_id` 与 `VkSpecializationMapEntry.constantID` 不匹配。[TOOL]
2. `offset` / `size` 与 specialization data 结构体布局不一致。[TOOL]
3. `pData` 指向栈变量，pipeline 创建后失效，但此时数据已被复制，通常不会出问题；若异步创建需注意。[TOOL]
4. 用 specialization constant 替代 uniform 做高频变化参数，导致每帧创建 pipeline。[ENGINE]
5. 组合爆炸：过多 specialization 选项导致 pipeline 变体数量失控。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkSpecializationInfo-*`：map entry 合法性、offset/size 范围。
- `VUID-VkPipelineShaderStageCreateInfo-pSpecializationInfo-*`：specialization info 与 shader 兼容性。

### RenderDoc / AGI

- 查看 pipeline 的 shader 是否为预期 specialization 结果。
- 检查 constant 值是否生效。

### 日志 / 代码检查

- 检查 specialization map entry 与 shader 声明的对应关系。
- 检查 specialization data 的构造与生命周期。

---

## 9. 生命周期风险

### 创建时机

- Pipeline 创建时传入；数据在 `vkCreate*Pipelines` 调用期间需有效。[SPEC]

### 使用时机

- Pipeline 创建后 specialization 结果已固化；运行时不能修改。[SPEC]

### 销毁时机

- 无独立对象；`VkSpecializationInfo` 结构体可随创建信息一起释放。

### in-flight 风险

- 无；specialization 数据只影响创建阶段。

---

## 10. 同步风险

### CPU-GPU 同步

- 无；specialization 发生在 CPU 编译阶段。[SPEC]

### GPU-GPU 同步

- 无。

### 资源访问同步

- 无。

---

## 11. Android 注意点

- Specialization constants 可减少 shader 变体文件数量，但每个组合仍是独立 pipeline，需计入 cache。[ANDROID][ENGINE]
- 避免用 specialization 控制每帧变化参数，否则会导致大量 pipeline 创建。[ANDROID]
- 对移动端， specialization 常用于启用/禁用特性（如阴影、雾、quality level）。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 合理的 specialization 组合可减少运行时分支，但组合过多会增加 pipeline 数量与创建时间。[ENGINE]
- 配合 pipeline cache 使用，可降低重复 specialization 的编译开销。[ENGINE]

### GPU 侧

- 编译期常量可被驱动优化，通常比 uniform 分支更高效。[ENGINE]

### 移动端

- 控制 specialization 组合数量；建议按质量等级、平台特性做枚举，而不是按每个材质参数做 specialization。[ANDROID]

---

## 13. 专家经验

**经验**：
Specialization constants 最适合表达“创建时确定、运行时不变化”的编译期开关，例如是否启用阴影、是否使用法线贴图、LOD 质量等级。把它当作减少 shader 源文件数量的工具，而不是替代 uniform 的动态参数。对每个 specialization 组合都要创建独立 pipeline，因此要做好变体管理，避免组合爆炸。

**适用条件**：
需要同一 shader 的多个编译期变体，且变体数量可控的场景。

**不适用情况**：
每帧或每 draw call 变化的参数；变体组合会爆炸的复杂系统。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `graphics_pipeline.md`
- `compute_pipeline.md`
- `shader_module.md`
- `pipeline_cache.md`
- `pipeline_layout.md`
- `pipeline.md`

---

## 15. 需要回查官方文档的情况

1. Specialization constant 支持的类型与位宽。
2. SPIR-V 中 `OpSpecConstant` / `OpSpecConstantComposite` 的声明规则。
3. `VkSpecializationMapEntry` 的 offset/size 对结构体 padding 的要求。
4. Specialization 与 pipeline derivative / base pipeline 的交互。
5. 不同驱动对 specialization constant 的优化程度。

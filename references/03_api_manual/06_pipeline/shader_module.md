# API Card: VkShaderModule

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkShaderModule` |
| 常用 API | `vkCreateShaderModule` / `vkDestroyShaderModule` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkShaderModule` 是 SPIR-V 字节码在 Vulkan device 上的容器；它本身不描述固定功能状态，只被 graphics / compute pipeline 创建时引用，用来指定某个 shader stage 的入口。[SPEC]

---

## 2. 所属对象链路

```text
Shader 源码 (GLSL/HLSL/SLANG)
→ 离线/在线编译器 (glslang / shaderc / dxc)
→ SPIR-V 二进制
→ vkCreateShaderModule
→ VkPipelineShaderStageCreateInfo
→ VkGraphicsPipelineCreateInfo / VkComputePipelineCreateInfo
→ vkCreateGraphicsPipelines / vkCreateComputePipelines
→ VkPipeline
```

### 上游依赖

- 已生成合法 SPIR-V 二进制。[SPEC]
- 已确认目标设备支持的 SPIR-V 版本与 capability。[SPEC]
- 已确认 shader 入口点名称与 specialization 常量布局。[ENGINE]

### 下游影响

- 决定 pipeline 中某个 stage 的执行代码。[SPEC]
- 通过 reflection 决定 descriptor set layout、push constant range、vertex input 等接口。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkShaderModule`
- `VkShaderModuleCreateInfo`
- `VkPipelineShaderStageCreateInfo`
- `VkSpecializationInfo`（可选）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateShaderModule` | 从 SPIR-V 字节码创建 shader module。[SPEC] |
| `vkDestroyShaderModule` | 销毁 module；可在 pipeline 创建完成后销毁（pipeline 内部会保留所需信息）。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_shader_module_identifier` / `VK_EXT_shader_object` 等进阶用法不在本卡覆盖范围，需回查文档。

---

## 4. 标准使用流程

```text
离线编译 shader 为 SPIR-V（推荐工程化）
→ 确认 codeSize 是 4 的倍数
→ 填写 VkShaderModuleCreateInfo (codeSize, pCode)
→ vkCreateShaderModule
→ 为每个 stage 填写 VkPipelineShaderStageCreateInfo
    → stage
    → module
    → pName (入口点，常见 "main")
    → pSpecializationInfo (可选)
→ 提交到 pipeline 创建
→ 若 module 不再复用，可在 pipeline 创建后销毁
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `codeSize` | 必须是 4 的倍数，单位为字节。[SPEC] | 用文件大小直接填入但未对齐。[TOOL] |
| `pCode` | 指向 SPIR-V words 数组。[SPEC] | 把 GLSL 源码直接当 SPIR-V 传入。[TOOL] |
| `stage` | `VkPipelineShaderStageCreateInfo` 中指定 VERTEX / FRAGMENT / COMPUTE 等。[SPEC] | compute pipeline 中 stage 未填 COMPUTE；graphics pipeline 中混入 compute stage。[TOOL] |
| `pName` | shader 入口点名称，必须与 SPIR-V 中 `OpEntryPoint` 一致。[SPEC] | 填 `"main"` 但实际入口点是其它名字。[TOOL] |
| `pSpecializationInfo` | 编译期常量覆盖，用于生成 pipeline 变体。[SPEC] | mapEntry offset/size 与 SPIR-V 中 constant ID 不匹配。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] SPIR-V 是否通过 `spirv-val` 或编译器验证？
- [ ] `codeSize` 是否为 4 的倍数？
- [ ] 入口点名称是否在 SPIR-V 中存在？
- [ ] `stage` 与 pipeline 类型是否匹配？
- [ ] specialization map entry 的 ID / offset / size 是否正确？

### 使用阶段

- [ ] 同一个 module 是否被多个 graphics / compute pipeline 复用？若是，不要提前销毁。
- [ ] pipeline 创建时是否传入了正确的 stage 数组？

### 销毁阶段

- [ ] 确认 module 不再用于后续 pipeline 创建后再销毁。
- [ ] 不要在 pipeline 仍在 in-flight 时销毁 module 虽然允许，但建议延后到安全点。[HEUR]

---

## 7. 高频错误

1. `codeSize` 不是 4 的倍数导致 `vkCreateShaderModule` 失败。[TOOL]
2. `pName` 与 SPIR-V 入口点不一致，pipeline 创建失败。[TOOL]
3. compute shader 被塞进 graphics pipeline，或 graphics stage 被塞进 compute pipeline。[TOOL]
4. specialization constant 的 constantID 与 shader 中 `SpecId` 不一致。[TOOL]
5. 运行时编译失败未检查编译器日志，把错误 SPIR-V 传给 Vulkan。[ENGINE]
6. 销毁 module 后仍在创建 pipeline，导致未定义行为。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkShaderModuleCreateInfo-*`：codeSize、pCode 合法性。
- `VUID-VkPipelineShaderStageCreateInfo-*`：stage、pName、module 匹配。
- `VUID-vkCreateGraphicsPipelines-*` / `VUID-vkCreateComputePipelines-*`：shader stage 组合与入口点。

### RenderDoc / AGI

- 查看 pipeline 的 shader stage 列表。
- 查看 disassembly 与 entry point。
- 确认 specialization constant 实际取值。

### 日志 / 代码检查

- 检查 SPIR-V 编译工具返回的日志。
- 对比 shader 源码入口点与 `pName`。
- 确认 `codeSize` 计算方式。

---

## 9. 生命周期风险

### 创建时机

- Pipeline 创建之前，通常在初始化或资源加载阶段。

### 使用时机

- 仅作为 `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` 的输入。

### 销毁时机

- pipeline 创建成功后即可销毁 module，pipeline 内部保留所需信息。[SPEC]
- 若 module 会被多个 pipeline 复用，保留到最后一个 pipeline 创建完成。

### in-flight 风险

- Shader module 本身不直接被 command buffer 引用；被引用的是 pipeline。
- 销毁 module 不会影响已绑定的 pipeline。[SPEC]

---

## 10. 同步风险

- `vkCreateShaderModule` 是 CPU 侧操作，不涉及 GPU 同步。
- Pipeline 创建可能耗时，但不需要 fence / semaphore。
- 多个 thread 可并发创建不同 shader module；同一 module 不建议并发用于多个 pipeline 创建 unless 安全。[HEUR]

---

## 11. Android 注意点

- Android 常用 `shaderc` 在运行时将 GLSL 编译为 SPIR-V；务必检查编译结果和日志。[ANDROID]
- 建议在发布前离线预编译 SPIR-V，减少启动耗时与运行时依赖。[ENGINE]
- 不同 GPU 对 SPIR-V capability 支持不同，需在 `vkCreateDevice` 时开启对应 feature。[ANDROID]
- AGI 可查看 shader disassembly 与 entry point。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Shader module 创建本身是轻量 CPU 操作，但 SPIR-V 编译可能很重；建议离线编译。[ENGINE]
- 不要每帧创建/销毁 shader module。[ENGINE]

### GPU 侧

- Shader module 本身不产生 GPU 开销，开销在 pipeline 创建和运行时 shader 执行。[HEUR]

### 移动端

- 移动 GPU 对 shader 变体敏感，建议用 specialization constants 减少变体数量。[ENGINE]
- 避免在关键帧中首次创建大量 pipeline 导致卡顿。[ENGINE]

---

## 13. 专家经验

**经验**：
SPIR-V 应作为构建产物纳入版本管理，CI 中跑 `spirv-val`；运行时仅做 `vkCreateShaderModule`。对于变体，优先使用 specialization constants，而不是生成多套 SPIR-V。

**适用条件**：
项目有多个 shader、多平台、需要 reproducible build。

**不适用情况**：
仅用于快速原型验证，不关注构建可复现性。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `pipeline_layout.md`
- `graphics_pipeline.md`
- `compute_pipeline.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../05_descriptor/descriptor_update.md`

---

## 15. 需要回查官方文档的情况

1. SPIR-V capability / extension 在目标设备的可用性。
2. `VkPipelineShaderStageCreateInfo` 中 `pSpecializationInfo` 的精确布局规则。
3. Mesh / task shader 等新增 stage 的 pipeline 创建规则。
4. `VK_EXT_shader_object` 与传统 pipeline 的差异。

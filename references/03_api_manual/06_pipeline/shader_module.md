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
- 将 reflection 作为 descriptor、push constant、vertex input 合同的输入，结合引擎 schema 验证兼容性。[ENGINE]

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
- [ ] 已完成创建的 pipeline 可继续使用；module 销毁只需协调仍在引用它的 CPU 创建调用，不把 pipeline 的 GPU 退休条件套到 module。[SPEC]

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
- 多个 thread 可并发创建不同 shader module；共享只读 module 的创建输入必须存活，销毁与尚未完成的创建调用协调；按各命令 host synchronization 判断。[SPEC]

---

## 11. Android 注意点

- Android 常用 `shaderc` 在运行时将 GLSL 编译为 SPIR-V；务必检查编译结果和日志。[ANDROID]
- 建议在发布前离线预编译 SPIR-V，减少启动耗时与运行时依赖。[ENGINE]
- 不同 GPU 对 SPIR-V capability 支持不同，需在 `vkCreateDevice` 时开启对应 feature。[ANDROID]
- AGI 可查看 shader disassembly 与 entry point。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Shader module 创建成本依实现与产物而异，但 SPIR-V 编译可能很重；建议离线编译。[ENGINE]
- 不要每帧创建/销毁 shader module。[ENGINE]

### GPU 侧

- Shader module 本身不产生 GPU 开销，开销在 pipeline 创建和运行时 shader 执行。[HEUR]

### 移动端

- 移动 GPU 对 shader 变体敏感，可用 specialization 减少部分 SPIR-V 文件，但不自动减少 pipeline 组合。[ENGINE]
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

<a id="shader-artifact-contract"></a>
## 16. Shader 产物合同（C1）

输入是授权项目源码/依赖、固定工具链、目标环境与 Engine schema；输出是完整产物包与逐层判定，不是一个孤立 `.spv`。[ENGINE]

```text
sourceHash / includeDependencyHashes
compilerName / compilerVersion / compilerOptions
sourceLanguage / entryPoint / stage
targetVulkanEnvironment / targetSpirvEnvironment
requiredExtensions / requiredFeatures / requiredLimits
reflectionHash / interfaceContractHash / bytecodeHash
materialSchemaVersion / buildRevision
```

这些是工程 manifest 字段，不是 Vulkan 结构体；复用既有构建格式，不强制运行时 JSON。包含宏、include、工具版本及 target 的缓存 key 才能避免误用旧产物。保存真实完整编译/校验命令与返回码，不将示意 CLI 当可运行配方。[ENGINE]

编译 PASS → SPIR-V 验证 PASS → 接口合同 PASS → 实际 Device 支持且启用 → Pipeline 创建 PASS → 图像/数值 PASS，分别记录。编译器支持新 SPIR-V 不代表旧设备支持；未执行项标 NOT_RUN，不从前层继承成功。[SPEC][TOOL]

FP16 算术 `shaderFloat16`、16-bit buffer/push storage（如 `storageBuffer16BitAccess`、`uniformAndStorageBuffer16BitAccess`、`storagePushConstant16`）、stage I/O `storageInputOutput16`、整数 `shaderInt16` 分别查询/启用；FP16 算术不自动准许所有 storage/I/O。std140/std430/scalar layout 与 host padding 分开校验实际 offsets、array/matrix stride；scalar/uniform 标准布局也有各自能力要求。[SPEC]

默认保留剔除/depth 比较的保守精度；精度变体要测近平面、远近尺度、NaN/Inf、动画和跨 GPU，不以 FPS 或静态截图代替数值验收。接口与热更新见 [定向合同](../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md#shader-hot-reload)。

固定规范：[Vulkan-Docs v1.4.328 features](https://github.com/KhronosGroup/Vulkan-Docs/blob/d38733398a4bec673bd5d24c904d4739a45f020d/chapters/features.adoc)、[shader/pipeline](https://github.com/KhronosGroup/Vulkan-Docs/blob/d38733398a4bec673bd5d24c904d4739a45f020d/chapters/pipelines.adoc)。核验 2026-11-01，source-read；不是设备支持声明。


<a id="shader-object-contract"></a>
## Shader Object：独立能力与生命周期

查询并启用 `VK_EXT_shader_object` / `shaderObject` 及其 Registry 依赖；这不是核心版本自动获得的能力，也不表示所有传统 optional shader stage 都支持。`VkShaderEXT` 与 `VkShaderModule` 不同：使用 `vkCreateShadersEXT` 的 SPIR-V 或 binary code、entry point、stage、nextStage、descriptor set layouts、push constant ranges、specialization → `vkCmdBindShadersEXT` → 设置相关动态状态 → draw/dispatch。图形 shader object draw 使用 dynamic rendering 并满足对应 rendering 与 attachment 合同；不把 shader object 直接当 RT Pipeline/SBT 的替代品。[SPEC]

启用 `VK_SHADER_CREATE_LINK_STAGE_BIT_EXT` 的阶段按链接集合创建并依规范绑定，不能把不兼容接口或任意链接组合拼成图形链。所有静态使用 descriptor 与 push constant 接口必须相容；未使用的 graphics stage 显式解除绑定，避免残留 stage。`nextStage` 不是启用硬件能力的开关。[SPEC]

Binary cache 记录 `shaderBinaryUUID` 与 `shaderBinaryVersion`：相同 UUID 且目标版本不低于来源版本才有保证兼容；其他组合可尝试创建，但 `VK_INCOMPATIBLE_SHADER_BINARY_EXT` 必须回到已验证 SPIR-V 重建。其他错误按错误类型处理；partial creation 按返回的实际 handle 清理，不使用未创建对象。不能用 pipelineCacheUUID 代替 shaderBinaryUUID。[SPEC]

`vkCmdBindShadersEXT` 会扰动对应 pipeline bind point；原 pipeline 中非 dynamic 的 graphics 状态变为 undefined。`vkCmdBindPipeline` 反过来解除对应 shader stages。切换模式后按 [动态状态合同](dynamic_state.md#shader-object-state-contract) 重新建立 draw 条件，不能假定上次 pipeline 已设置完整状态。Shader object 销毁前所有提交引用必须结束；销毁对象并不替代 host/command-buffer 的外部同步。[SPEC]

验证：缺 feature 拒绝、binary incompatible → SPIR-V、混合绑定状态失效、linked stage/layout 不兼容负例；无设备执行不记 GPU PASS。回退使用传统 graphics/compute pipeline，维持相同 descriptor 与 rendering 接口。

固定规范（Vulkan 1.4.368，source-read；不是设备验证）：[shaders-objects-creation / binary-compatibility / pipeline-interaction / destruction](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/shaders.adoc)。

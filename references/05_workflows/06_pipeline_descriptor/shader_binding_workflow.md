# Workflow: Shader Binding 对齐工作流

## 0. 适用范围

### 适用

- 多人协作或自动化流程中保证 shader 资源声明与 Vulkan descriptor set layout / pipeline layout 一致。
- 需要 reflection、descriptor schema、layout 生成、CI 校验的工程项目。
- GLSL / HLSL / Slang 源码与 C++ / 引擎代码的 binding 对齐。

### 不适用

- 纯手写 SPIR-V 无 reflection 的场景。
- 使用外部渲染框架且 binding 由框架托管。
- 单人快速原型，不引入 CI 校验成本。

---

## 1. 任务目标

建立 shader binding 对齐闭环：

```text
Shader Source
→ Compile to SPIR-V
→ Reflection (set/binding/type/count)
→ Descriptor Schema
→ Generate C++ Layout Code / JSON
→ CI Diff Check
→ Runtime Create Layout
→ Bind Descriptor Set
```

---

## 2. 输入条件

需要确认：

- Shader 语言：GLSL / HLSL / Slang。
- 编译器：glslangValidator / slangc / dxc / shaderc。
- Reflection 工具：spirv-reflect / SPIRV-Cross / 自定义解析。
- 工程代码语言：C++ / Rust / 其他。
- 是否需要生成 descriptor set layout、pipeline layout、enum、constant 代码。
- CI 环境是否可运行 reflection diff。
- 是否使用 push constants、 specialization constants。

---

## 3. 前置检查

- [ ] Shader 编译链路可用。
- [ ] Reflection 工具可输出 set/binding/type/stage/count。
- [ ] 已有 descriptor set layout 创建函数可接入生成代码。
- [ ] CI 可执行脚本并比较生成文件 diff。
- [ ] 代码仓库对生成文件有明确约定（提交/忽略）。
- [ ] Android 端 shader 路径与 asset 打包一致。

---

## 4. Vulkan 对象链路

```text
Shader Source (GLSL/HLSL/Slang)
→ SPIR-V File / Bytecode
→ Reflection Data (JSON/YAML/Struct)
→ Descriptor Schema
→ Generated Code (C++ / Rust)
→ VkDescriptorSetLayout
→ VkPipelineLayout
→ VkPipeline
→ vkCmdBindDescriptorSets
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| SPIR-V 文件 | 构建产物 | shader module 来源 | 随构建 | 否 |
| reflection 输出 | JSON/头文件 | 生成 layout 依据 | 构建时生成 | 否 |
| descriptor schema | 约定/元数据 | 统一 shader 与 C++ 的 binding 方案 | 项目生命周期 | 否 |
| generated layout code | C++ / Rust | 运行时创建 layout | 构建时生成 | 否 |
| descriptor set layout | `VkDescriptorSetLayout` | 运行时资源绑定 | 通常全局 | 否 |
| pipeline layout | `VkPipelineLayout` | 组合 descriptor layout + push constant | 通常全局 | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame constants | Vertex / Fragment / Compute |
| set=1,binding=0~N | `COMBINED_IMAGE_SAMPLER` | material textures | Fragment |
| set=2,binding=0 | `STORAGE_BUFFER` | per-instance / skinning data | Vertex / Compute |
| push constant | `VkPushConstantRange` | small per-draw data | Vertex / Fragment |

设计说明：

- 在 shader 中使用 `layout(set=X, binding=Y)` 显式声明，避免编译器默认分配导致漂移 [ENGINE]。
- 统一 schema 中每个 set 的语义固定：set0=frame、set1=material、set2=object、set3=项目保留用途（specialization constants 不是 descriptor set）；减少跨 shader 对齐成本 [HEUR]。
- push constant 可用于 draw index/material ID 等小数据；这是工程选择，规范边界是实际范围/stage/limit，不是笼统“不得替代 UBO” [ENGINE][SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| reflection 工具 | descriptor schema | 生成代码 | C++ layout 创建 |
| CI diff | generated code | 校验与源码一致 | 阻止不一致提交 |
| runtime | descriptor set layout | `vkCreateDescriptorSetLayout` | pipeline layout / pipeline |
| runtime command | descriptor set | `vkUpdateDescriptorSets` + barrier | shader 访问 |

必须说明：

- reflection 与运行时 layout 按规范兼容性校验，不要求文本一一相等；具体合法超集与错误见 §15 [SPEC]。
- descriptor set 中 image layout 仍需运行时 barrier 保证；schema 只负责 binding 对齐，不负责同步 [SPEC]。

---

## 8. 实现步骤

1. **约定 schema**：定义 set/binding 分配规则、命名规范、资源类型到 descriptor type 的映射；文档化并加入 code review 清单 [ENGINE]。
2. **编译 shader**：在构建脚本中调用 `glslangValidator -V` / `slangc -target spirv` / `dxc -spirv` 生成 SPIR-V [ENGINE]。
3. **运行 reflection**：按实际工具 API 提取每个 entry point 的资源信息；SpvReflectDescriptorBinding 属于 SPIRV-Reflect，SPIRV-Cross 使用自身 API，归一到项目 JSON/内存合同 [TOOL]。
4. **生成 descriptor schema**：将 reflection 结果聚合为按 set/binding 的全局 schema，记录 type、count、stage、更新频率 [ENGINE]。
5. **生成 C++ / Rust 代码**：
   - 每个 set 生成 `VkDescriptorSetLayout` 创建函数；
   - 生成 binding enum 或常量，避免手写 magic number；
   - 生成 pipeline layout 创建函数；
   - 生成 descriptor write helper [ENGINE]。
6. **接入构建系统**：将生成步骤加入 CMake / Gradle / 自定义 build；每次 shader 修改后自动重新生成 [ENGINE]。
7. **CI diff 校验**：在 CI 中编译 shader、运行 reflection、生成代码，与仓库中已提交的生成文件 diff；不一致时失败 [ENGINE]。
8. **运行时创建 layout**：调用生成的函数 `CreateDescriptorSetLayout_XXX()`、`CreatePipelineLayout()`，确保与 shader 一致 [SPEC]。
9. **运行时更新 descriptor**：使用生成的 binding 常量调用 `vkUpdateDescriptorSets`，避免手写 binding 数字 [ENGINE]。
10. **绑定并绘制**：`vkCmdBindDescriptorSets` 时使用生成的 set index 常量。
11. **维护 schema 版本**：当 shader binding 变更时同步更新 schema 与生成代码；CI 阻止未同步提交。
12. **接入销毁路径**：生成的 layout 按全局生命周期管理，renderer 退出时销毁。

---

## 9. Android 注意点

- Android asset 路径与 PC 不同，SPIR-V 文件需打包到 APK assets 或 OBB；构建脚本需确保移动端 SPIR-V 与 reflection 生成代码同步 [ANDROID]。
- Android 端不同 GPU（Adreno / Mali / PowerVR）对 descriptor set 数量、push constant size 限制可能不同；schema 中应记录最小公共限制 [ANDROID]。
- pause / resume 不改变 descriptor schema，但运行时必须确保 输出相关 descriptor 与其 Surface generation 对齐，共享/离屏资源按独立 owner 生命周期管理 [ANDROID]。
- rotation / resize 后，若 schema 不变则无需重建 layout；只需更新引用了 swapchain image 的 descriptor。
- AGI / logcat 验证：检查运行时 layout 创建参数与 reflection 输出是否一致。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 descriptor layout / binding / pipeline layout 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：Pipeline State 中 set/binding 与 shader 声明一致 [TOOL]。
- [ ] CI diff：生成代码与 shader 修改同步，无未提交差异。
- [ ] 截图 / 数值验证：不同 shader 使用同一 schema 时渲染结果正确。
- [ ] logcat（Android）：无 validation error；可输出运行时 layout 创建成功日志。
- [ ] 性能指标：
  - 构建时 reflection + 生成代码耗时在可接受范围；
  - 运行时无 redundant layout 创建；
  - descriptor set 切换次数符合预期 [HEUR]。
- [ ] resize / pause / resume 后 binding 仍正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Shader 手写 binding 与生成代码不一致**：GLSL 中修改 binding 后未重新生成代码，CI 未启用导致运行时失败 [ENGINE]。
2. **Reflection 工具解析差异**：不同版本 spirv-reflect 对 array size 解析不同，导致生成 layout 不匹配 [TOOL]。
3. **Stage 集合错误**：漏掉实际使用阶段；合法超集不因比反射宽就报错，但会占用对应阶段限额 [TOOL]。
4. **Dynamic 绑定错误**：普通 uniform block 可映射动态 UBO；错误在 dynamic offset 数量、顺序、对齐或范围，不在反射没有 dynamic 标签 [SPEC]。
5. **Push constant range 错误**：两个 range 共享同一 stage 位，或未覆盖该 stage 使用字节；不同 stage 的字节范围可重叠 [SPEC]。
6. **Descriptor count 错误**：布局容量不足以覆盖实际所需数组元素；合法更大容量不是自动错误 [SPEC]。
7. **CI 未校验生成文件**：开发者忘记重新生成，仓库中代码与 shader 不同步 [ENGINE]。
8. **Android asset 未更新**：PC 端 SPIR-V 已变，但 APK 中仍是旧版本，导致运行时 binding 不一致 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- Shader 源码与编译命令。
- Reflection 工具版本与输出。
- 生成的 layout 代码片段。
- `VkDescriptorSetLayoutCreateInfo` 与 shader 声明对比。
- CI 脚本与 diff 输出。
- Validation Layer 完整报错。
- Android asset 打包配置。

<a id="shader-interface-validation"></a>
## 15. 兼容性校验而非反射逐字相等（C1）

输入：选定 entry point/stage/特化组合的反射、引擎 schema、实际启用 feature/limits；输出逐项兼容理由与迁移清单。反射不提供更新频率、owner、动态偏移策略等全部引擎语义。[ENGINE]

| 合同 | 合法例 / 必须拦截 |
|---|---|
| set/binding/type | uniform block 可用 UNIFORM_BUFFER 或 UNIFORM_BUFFER_DYNAMIC；后者还查绑定时 offsets 数量/顺序、minUniformBufferOffsetAlignment、有效范围；不能映射成不相容 sampled image |
| stage/count | stageFlags 包含使用阶段即可，可更宽；固定数组布局容量可更大但不能遗漏所需元素，且核对每 stage/每 set limits；runtime array/variable count/partially bound 按各自 feature、分配容量与实际访问检查，不能泛化为任意少配 |
| push constants | offset/size 为 4 字节倍数且 size>0，范围不超 maxPushConstantsSize；两个 range 不得含相同 stage 位，即使字节不重叠。不同 stage 可共享字节区间；每 stage 使用字节必须覆盖，更新命令也核对 stage/range |
| block/vertex/stage I/O | 对比实际 member offset、array/matrix stride、row/column major、host padding；std140/std430/scalar 分开。vertex format/offset/stride 和 stage location/component/type 按目标规则校验，而非 sizeof 文本相等 |

规范允许的布局超集 ≠ 两个 pipeline layout 在绑定时必然兼容；另核对 descriptor set layout identity/兼容性和 push constant range 要求。引擎可采用更严格 schema，但报错标 ENGINE policy 而非伪造 VUID。[SPEC][ENGINE]

<a id="shader-hot-reload"></a>
## 16. 开发期热更新与代际发布（C1）

前提：已有 [产物 manifest](../../03_api_manual/06_pipeline/shader_module.md#shader-artifact-contract)、资源 owner 与 GPU 退休机制。只用于授权开发环境，不实现远程发布服务。

| 变化 | 影响面 |
|---|---|
| 实现变化、接口兼容 | 新 bytecode/pipeline key；保留合法 layout/material；检查图像/数值 |
| 接口变化 | descriptor/pipeline layout、分配的 sets、material 数据和录制代码协调迁移，不能只换 module |
| target feature/limits 变化 | 对实际已创 Device 重新判能力；缺条件保留旧路径，不暗中重建整个 Device |

`Requested → Build+Validate → Create → Ready → Published → Retired`；失败保留旧可用完整产物，取消或过期结果进入 Canceled/Obsolete，不发布半套对象。发布前核对 Engine/Device/material generation，任务持有 create-info/pNext/字符串/特化数据和 shader module 的合法生命周期。发布给新命令录制路径时旧 pipeline 可继续 in-flight；最后 CPU 引用和 GPU 使用结束后原 owner 回收，不要求每次全 GPU idle。[ENGINE][SPEC]

验证：合法动态 UBO/stage 超集/跨阶段重叠正例，与容量不足/错 stride/同 stage 重复 range 反例；接口更换失败、取消迟到、Device teardown、双 Engine 共享资源及图像回归分层报告。

固定规范：[Vulkan-Docs v1.4.328 descriptorsets](https://github.com/KhronosGroup/Vulkan-Docs/blob/d38733398a4bec673bd5d24c904d4739a45f020d/chapters/descriptorsets.adoc)，尤其 Pipeline Layout Consistency / VkPipelineLayoutCreateInfo / VkPushConstantRange。2026-11-01 source-read。

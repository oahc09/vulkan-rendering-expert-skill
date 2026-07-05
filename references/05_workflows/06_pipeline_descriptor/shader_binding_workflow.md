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
- 统一 schema 中每个 set 的语义固定：set0=frame、set1=material、set2=object、set3=specialization；减少跨 shader 对齐成本 [HEUR]。
- push constant 仅用于极小数据（如 draw index、material id），避免替代 UBO [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| reflection 工具 | descriptor schema | 生成代码 | C++ layout 创建 |
| CI diff | generated code | 校验与源码一致 | 阻止不一致提交 |
| runtime | descriptor set layout | `vkCreateDescriptorSetLayout` | pipeline layout / pipeline |
| runtime command | descriptor set | `vkUpdateDescriptorSets` + barrier | shader 访问 |

必须说明：

- reflection 生成的 layout 与运行时创建的 layout 必须完全一致；任何差异都会导致 pipeline layout 创建失败或 draw 时报 descriptor binding error [TOOL]。
- descriptor set 中 image layout 仍需运行时 barrier 保证；schema 只负责 binding 对齐，不负责同步 [SPEC]。

---

## 8. 实现步骤

1. **约定 schema**：定义 set/binding 分配规则、命名规范、资源类型到 descriptor type 的映射；文档化并加入 code review 清单 [ENGINE]。
2. **编译 shader**：在构建脚本中调用 `glslangValidator -V` / `slangc -target spirv` / `dxc -spirv` 生成 SPIR-V [ENGINE]。
3. **运行 reflection**：使用 `spirv-reflect` 或 SPIRV-Cross 提取每个 shader 的 `SpvReflectDescriptorBinding`，输出 JSON/YAML/内存结构 [TOOL]。
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
- pause / resume 不改变 descriptor schema，但运行时必须确保 descriptor set 引用的资源生命周期与 surface 同步 [ANDROID]。
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
3. **Stage 集合错误**：fragment-only 的 sampler 被反射为 `ALL_STAGES`，创建 layout 时 stageFlags 过宽 [TOOL]。
4. **Dynamic 类型未声明**：shader 使用普通 UBO，但 C++ 生成 `UNIFORM_BUFFER_DYNAMIC`，导致 offset 参数不匹配 [SPEC]。
5. **Push constant range 重叠**：多个 push constant 块 range 重叠，pipeline layout 创建失败 [SPEC]。
6. **Descriptor count 错误**：shader 中 image 数组大小与 `descriptorCount` 不一致 [SPEC]。
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

- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
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

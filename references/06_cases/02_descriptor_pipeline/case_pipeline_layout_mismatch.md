# Case: Pipeline Layout Mismatch

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Pipeline Layout |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Validation Layer 报错提示 pipeline layout 与 descriptor set layout 不兼容，或 shader 无法访问资源。表现为画面黑、uniform 不生效、texture 采样不到，甚至直接 crash。错误通常出现在 `vkCmdBindDescriptorSets` 或 `vkCmdDraw` / `vkCmdDispatch` 阶段。

---

## 2. 初始上下文

- 使用 graphics 或 compute pipeline。
- Shader 中声明了多个 `layout(set = M, binding = N)`。
- Vulkan 侧手动创建了 `VkDescriptorSetLayout` 和 `VkPipelineLayout`。
- 最近修改过 shader（新增 set / binding / push constant），但未同步更新 pipeline layout。
- 或同一 pipeline 被多个 shader pass 复用，但各 pass 的 resource layout 不同。

---

## 3. 初始误判

最初容易怀疑：

```text
descriptor set 没有正确分配或更新；
shader binding 写错；
vkCmdBindDescriptorSets 的 set index 填错；
stageFlags 没有覆盖目标 shader stage；
push constant range 超限。
```

但 RenderDoc 显示 descriptor set 已绑定到正确 slot，update 也无误。最终发现是 `VkPipelineLayoutCreateInfo` 中的 `setLayouts` 与 shader 声明的 set / binding 不匹配，或 pipeline 是用旧 layout 创建的。

---

## 4. 排查路径

1. 提取 Validation Message 中的 VUID 和 object handle。
2. 用 shader reflection 工具（spirv-cross / spirv-reflect）列出 shader 中所有 `set` / `binding` / `type` / `stage`。
3. 检查 `VkDescriptorSetLayoutCreateInfo` 中的 `binding` 是否覆盖 shader 声明。
4. 检查 `descriptorType` 是否与 shader resource type 一致。
5. 检查 `stageFlags` 是否覆盖实际使用资源的 shader stage。
6. 检查 `VkPipelineLayoutCreateInfo` 的 `setLayoutCount` 是否不少于 shader 使用的最大 set 索引 + 1。
7. 检查 pipeline 是否用修改后的 pipeline layout 重新创建。
8. 检查 push constant range 是否与 shader `layout(push_constant)` 一致。

---

## 5. 关键证据

### Validation Layer

- 常见 VUID（`[SPEC]`）：
  - `VUID-vkCmdBindDescriptorSets-layout-00xxx`：绑定的 descriptor set layout 与 pipeline layout 中对应 set 的 layout 不兼容。
  - `VUID-vkCmdDraw-None-02697` / `VUID-vkCmdDispatch-None-02699`：shader 访问了 pipeline layout 未声明的资源。
  - `VUID-VkGraphicsPipelineCreateInfo-layout-00756`：pipeline layout 与 shader interface 不兼容。
- Message 通常会指出具体 set、binding 和 descriptor type。

### RenderDoc / AGI

- 观察到：
  - Bound Resources 面板中某些 set / binding 为空，或显示类型不匹配。
  - Pipeline State → Shader 中显示了 `layout(set=1, binding=0)`，但 Pipeline Layout 只有 set 0。
  - 修改 descriptor layout 后没有重新创建 pipeline，导致 pipeline 仍引用旧 layout。
- 关键 resource：`VkPipelineLayout`、`VkDescriptorSetLayout`、shader module。

### Log / Code

- 关键代码：

```text
// shader
layout(set = 1, binding = 0) uniform sampler2D albedo;
layout(set = 1, binding = 1) uniform UBO { vec4 color; } ubo;

// Vulkan 侧错误：pipeline layout 只包含 set 0
VkPipelineLayoutCreateInfo plInfo{};
plInfo.setLayoutCount = 1;          // 错误：shader 使用了 set 1
plInfo.pSetLayouts = &setLayout0;   // 缺少 setLayout1
```

或：

```text
// descriptor set layout 中 binding 顺序与 shader 不一致
VkDescriptorSetLayoutBinding bindings[2];
bindings[0].binding = 0; bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;   // shader binding 0 是 sampler
bindings[1].binding = 1; bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; // shader binding 1 是 UBO
```

---

## 6. 根因

根因：`VkPipelineLayout` 中声明的 descriptor set layout 与 shader resource interface 不兼容，导致 shader 执行时无法按预期访问 descriptor 资源。

---

## 7. 修复方案

### 最小修复

- 以 shader reflection 结果为准，修正 `VkDescriptorSetLayoutBinding` 的 `binding`、`descriptorType`、`stageFlags`。
- 确保 `VkPipelineLayoutCreateInfo` 的 `pSetLayouts` 覆盖 shader 使用的所有 set 索引。
- 修改 pipeline layout 后，必须重新创建所有依赖该 layout 的 graphics / compute pipeline。
- 更新 descriptor set 的 update 调用，使其与新的 layout 一致。

### 稳定修复

- 使用 shader reflection 自动生成 descriptor set layout 和 pipeline layout，避免手工维护。
- 在 pipeline 创建前增加校验：对比 shader resource manifest 与 pipeline layout 的兼容性。
- 对 push constant range、set count、binding count 做自动化检查并报错。

### 工程化修复

- 为每个 shader pass 定义 descriptor manifest（YAML / JSON），由构建系统生成 C++ layout 代码。
- CI 中运行 shader reflection diff：当 shader 的 set / binding 变化时，强制更新 manifest 并重新生成 pipeline layout。
- 使用 descriptor layout cache，避免重复创建，同时保证同一份 manifest 只对应一个 layout。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 Bound Resources 与 shader declaration 一致。
- [ ] Shader 能正确读取 texture / uniform buffer / storage buffer。
- [ ] 修改 shader 后重新构建，pipeline layout 自动同步。
- [ ] 多帧运行无资源串帧或崩溃。
- [ ] resize / pause / resume 后 descriptor 仍正确。

---

## 9. 经验抽象

Pipeline layout 是 shader 与 descriptor 之间的“接口契约”。排查 descriptor 相关黑屏时，不要只检查 `vkUpdateDescriptorSets`，必须沿整条链路验证：

```text
Shader set/binding
→ DescriptorSetLayout
→ PipelineLayout
→ Pipeline creation
→ vkCmdBindDescriptorSets
→ Shader access
```

只要任一环节与 shader interface 不一致，就会表现为资源读取失败。

---

## 10. 预防规则

1. 禁止手动硬编码 pipeline layout；优先通过 shader reflection 生成。
2. 修改 shader 的 set / binding / push constant 后，必须重新创建 pipeline layout 和所有相关 pipeline。
3. Descriptor set layout 的 `descriptorType`、`stageFlags`、`binding` 必须与 shader reflection 一致。
4. `VkPipelineLayoutCreateInfo` 的 `setLayoutCount` 必须大于 shader 使用的最大 set 索引。
5. 在 CI 中增加 shader manifest diff，确保 Vulkan 侧 layout 与 shader 同步。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

## 13. 关联 Workflow

- `../../05_workflows/06_pipeline_descriptor/add_pipeline_layout.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`

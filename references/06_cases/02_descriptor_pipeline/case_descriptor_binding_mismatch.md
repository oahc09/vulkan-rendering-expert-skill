# Case: Descriptor Binding Mismatch

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Pipeline |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Validation Layer 报 descriptor binding mismatch。  
Shader 里声明了 texture 或 uniform buffer，但运行时 shader 读取不到资源，画面黑或参数不生效。

---

## 2. 初始上下文

- 使用 graphics pipeline。
- Shader 中声明 `layout(set = 0, binding = 1)`。
- Vulkan 侧创建了 descriptor set layout。
- Pipeline layout 创建成功。
- Descriptor set allocation 和 update 也执行了。

---

## 3. 初始误判

最初容易怀疑：

```text
纹理没上传；
uniform buffer 没更新；
fragment shader 采样坐标错误。
```

但 RenderDoc 显示 shader resource binding 为空或不匹配。  
最终发现 shader binding 与 Vulkan 侧 descriptor layout 不一致。

---

## 4. 排查路径

1. 提取 Validation Message 和 VUID。
2. 查看 shader 中所有 `set` / `binding`。
3. 检查 `VkDescriptorSetLayoutBinding`。
4. 检查 `descriptorType` 是否匹配。
5. 检查 `stageFlags` 是否覆盖实际 shader stage。
6. 检查 `VkPipelineLayoutCreateInfo` 是否包含正确 set layout。
7. 检查 `vkUpdateDescriptorSets` 的 binding。
8. 检查 `vkCmdBindDescriptorSets` 的 set index 和 bind point。

---

## 5. 关键证据

### Validation Layer

可能出现：

- descriptor set layout binding mismatch
- descriptor type mismatch
- pipeline layout incompatible
- descriptor not accessible from shader stage

### RenderDoc / AGI

观察到：

- Bound resources 中目标 binding 为空。
- binding 位置与 shader declaration 不一致。
- pipeline layout 中 set layout 与绑定 descriptor set 不兼容。

### Log / Code

关键代码：

```text
shader: set=0,binding=1
Vulkan: VkDescriptorSetLayoutBinding.binding = 0
```

或者：

```text
stageFlags 只填 VERTEX，但资源在 FRAGMENT 中使用。
```

---

## 6. 根因

根因：shader resource declaration 与 Vulkan 侧 descriptor set layout / pipeline layout 不一致，导致 pipeline 执行时 shader 无法访问正确资源。

---

## 7. 修复方案

### 最小修复

- 以 shader 中的 set/binding 为准修正 descriptor layout。
- 修正 descriptorType。
- 修正 stageFlags。
- 重新创建 pipeline layout 和 pipeline。
- 重新分配并更新 descriptor set。

### 稳定修复

- 建立 shader binding 表。
- 使用 shader reflection 自动生成 descriptor layout。
- 在 pipeline 创建前校验 shader resource 与 descriptor layout。

### 工程化修复

- 引入统一 descriptor schema。
- 对每个 shader pass 生成 descriptor manifest。
- CI 中检查 shader binding 和 Vulkan layout 一致性。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc bound resources 正确。
- [ ] Shader 能读取正确 texture / buffer。
- [ ] 多帧运行无资源串帧。
- [ ] resize 后 descriptor 仍正确。

---

## 9. 经验抽象

Descriptor 错误不要只看 `vkUpdateDescriptorSets`。  
必须沿以下链路排查：

```text
Shader set/binding
→ DescriptorSetLayout
→ PipelineLayout
→ DescriptorSet Allocation
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

---

## 10. 预防规则

1. Shader binding 必须有统一表。
2. Descriptor layout 必须和 shader declaration 自动或半自动对齐。
3. Pipeline layout 变化后必须重新创建 pipeline。
4. stageFlags 必须覆盖实际 shader stage。
5. 每个 pass 的 descriptor 更新必须可被 RenderDoc 验证。

---

## 11. 关联 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

## 13. 关联 Workflow

- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`

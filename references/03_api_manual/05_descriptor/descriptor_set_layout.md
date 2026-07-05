# API Card: VkDescriptorSetLayout

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorSetLayout` |
| 常用 API | `vkCreateDescriptorSetLayout` / `vkDestroyDescriptorSetLayout` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkDescriptorSetLayout` 描述一个 descriptor set 内所有 binding 的“类型、数量、stage、布局”，是 shader resource declaration 与 Vulkan 资源绑定之间的契约。[SPEC]

---

## 2. 所属对象链路

```text
Shader set/binding declarations
→ VkDescriptorSetLayoutBinding[]
→ VkDescriptorSetLayout
→ VkPipelineLayout
→ VkDescriptorSet (allocated from pool with this layout)
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

### 上游依赖

- Shader 中 `layout(set = N, binding = M)` 的声明。[SPEC]
- 应用层对资源类型的规划（uniform / sampled image / storage buffer 等）。[ENGINE]

### 下游影响

- `VkPipelineLayout` 必须包含兼容的 descriptor set layout。[SPEC]
- `VkDescriptorSet` 必须从匹配 layout 的 pool 中分配。[SPEC]
- `vkCmdBindDescriptorSets` 的 set index 必须与 pipeline layout 中的位置一致。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDescriptorSetLayout`
- `VkDescriptorSetLayoutCreateInfo`
- `VkDescriptorSetLayoutBinding`
- `VkDescriptorBindingFlags`（Vulkan 1.2 / `VK_EXT_descriptor_indexing`）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateDescriptorSetLayout` | 根据 binding 数组创建 layout。[SPEC] |
| `vkDestroyDescriptorSetLayout` | 销毁 layout；销毁前需确保没有 pipeline / descriptor set 引用。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_descriptor_indexing`：支持 partial binding、update after bind、variable descriptor count。[GUIDE]
- `VK_KHR_push_descriptor`：允许通过 command buffer 直接 push descriptor，无需预先分配 set。

---

## 4. 标准使用流程

```text
分析 shader 中所有 set/binding
→ 为每个 binding 填写 VkDescriptorSetLayoutBinding
    → binding
    → descriptorType
    → descriptorCount
    → stageFlags
    → pImmutableSamplers (可选)
→ vkCreateDescriptorSetLayout
→ 将 layout 加入 VkPipelineLayoutCreateInfo::pSetLayouts
→ 后续分配 VkDescriptorSet 时使用该 layout
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `binding` | 必须与 shader 中 `layout(binding = M)` 一致。[SPEC] | shader binding 1，layout binding 0。[TOOL] |
| `descriptorType` | `UNIFORM_BUFFER` / `COMBINED_IMAGE_SAMPLER` / `STORAGE_BUFFER` / `STORAGE_IMAGE` 等，必须与 shader 类型匹配。[SPEC] | sampled image 写成 storage image。[TOOL] |
| `descriptorCount` | array 大小；非 array 为 1。[SPEC] | shader 用 `sampler2D tex[4]` 但 count 填 1。[TOOL] |
| `stageFlags` | 哪些 shader stage 会访问；必须覆盖实际使用 stage。[SPEC] | fragment shader 使用资源但 stageFlags 只填 VERTEX。[TOOL] |
| `pImmutableSamplers` | 可选，创建时固定 sampler，后续 update 不可改。[SPEC] | 误用 immutable sampler 后又尝试 update sampler。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否从 shader reflection 或源码中提取了所有 binding？
- [ ] `descriptorType` 是否与 shader resource 类型一致？
- [ ] `stageFlags` 是否覆盖所有使用资源的 stage？
- [ ] `descriptorCount` 是否与 shader array 大小一致？

### 使用阶段

- [ ] Pipeline layout 中 set layout 的顺序是否与 shader 中 set 一致？
- [ ] Descriptor set 是否从匹配该 layout 的 pool 分配？

### 销毁阶段

- [ ] 是否在所有引用它的 pipeline / descriptor set 销毁后再销毁 layout？

---

## 7. 高频错误

1. Shader binding 与 layout binding 不一致。[TOOL]
2. `descriptorType` 与 shader 类型不匹配。[TOOL]
3. `stageFlags` 未覆盖 fragment stage。[TOOL]
4. `descriptorCount` 与 shader array 大小不一致。[TOOL]
5. Pipeline layout 中 set layout 顺序与 shader set 不一致。[TOOL]
6. 使用了 update-after-bind 但未在 layout 中设置对应 flag。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorSetLayoutCreateInfo-*`：binding / type / count / stage 合法性。
- `VUID-vkCmdBindDescriptorSets-*`：layout 兼容性。
- Pipeline layout compatibility 错误。[TOOL]

### RenderDoc / AGI

- 查看 pipeline layout 中的 descriptor set layout。
- 查看 descriptor set 的 binding 类型和数量。

### 日志 / 代码检查

- 对比 shader reflection 与 `VkDescriptorSetLayoutBinding`。
- 检查 pipeline layout 的 set layout 数组顺序。

---

## 9. 生命周期风险

### 创建时机

- Pipeline 创建前，通常与 shader module 同时准备。

### 使用时机

- Pipeline layout 创建时引用。
- Descriptor pool 创建时指定支持的 layout（隐式）。

### 销毁时机

- 在所有引用它的 pipeline 和 descriptor set 销毁之后。[SPEC]

### in-flight 风险

- Layout 本身不直接被 command buffer 引用，但 pipeline 和 descriptor set 会引用，需按依赖顺序销毁。[SPEC]

---

## 10. 同步风险

- Layout 本身不引入同步；同步由 descriptor set 的 update / bind / resource barrier 管理。

---

## 11. Android 注意点

- Android 上 shader binding 与 layout 不匹配是常见 validation error 来源。[ANDROID]
- 移动端应尽量减少 descriptor set layout 数量，合并相似资源到同一 set。[ENGINE]

---

## 12. 性能注意点

### CPU 侧

- Descriptor set layout 创建开销通常较低，但数量过多会增加 pipeline layout 组合复杂度。[ENGINE]
- 使用 `VK_EXT_descriptor_indexing` 的 partial binding 可减少必须更新的 descriptor 数量。[GUIDE]

### GPU 侧

- Layout 本身无 GPU 开销，但 layout 设计影响 descriptor cache 和 bind 开销。[HEUR]

### 移动端

- 移动端对 descriptor set 切换敏感，尽量按 update frequency 分组（per-frame / per-pass / per-material）。[ENGINE]

---

## 13. 专家经验

**经验**：
建议用 shader reflection 自动生成 descriptor set layout，避免手写 binding 表出错。若必须手写，应在 CI 中校验 shader bytecode 与 layout 的一致性。

**适用条件**：
项目存在多个 shader、多个 pass、频繁变更 binding 的工程场景。

**不适用情况**：
单个固定 shader 的简单 demo。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_update.md`
- `../06_pipeline/pipeline_layout.md`
- `../06_pipeline/shader_module.md`
- `../06_pipeline/graphics_pipeline.md`

---

## 15. 需要回查官方文档的情况

1. `VK_EXT_descriptor_indexing` 的 flag 组合与限制。
2. Immutable sampler 的使用规则。
3. Pipeline layout compatibility 的精确规则。
4. Push descriptor 与 descriptor set layout 的交互。

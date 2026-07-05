# API Card: VkPipelineLayout

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipelineLayout` |
| 常用 API | `vkCreatePipelineLayout` / `vkDestroyPipelineLayout` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipelineLayout` 描述一个 pipeline 可以访问哪些 descriptor set 和 push constant，是 shader 资源接口与 Vulkan 资源绑定之间的“插座面板”。[SPEC]

---

## 2. 所属对象链路

```text
Shader resource declaration
→ DescriptorSetLayout[] (按 set 索引排列)
→ PushConstantRange[] (按 stage/offset/size 定义)
→ vkCreatePipelineLayout
→ VkPipelineLayout
→ VkGraphicsPipelineCreateInfo / VkComputePipelineCreateInfo
→ vkCmdBindDescriptorSets (必须与此 layout 兼容)
→ Shader Access
```

### 上游依赖

- 所有 `VkDescriptorSetLayout` 已按 shader set 顺序创建。[SPEC]
- push constant range 已从 shader reflection 中提取并合并。[ENGINE]

### 下游影响

- 决定 pipeline 创建时使用的资源接口。[SPEC]
- 决定 `vkCmdBindDescriptorSets` 时可以绑定哪些 set。[SPEC]
- Pipeline layout 变化通常需要重新创建 pipeline。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipelineLayout`
- `VkPipelineLayoutCreateInfo`
- `VkDescriptorSetLayout`
- `VkPushConstantRange`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreatePipelineLayout` | 根据 set layouts 和 push constant ranges 创建 layout。[SPEC] |
| `vkDestroyPipelineLayout` | 销毁 layout；需确保不再被 pipeline 创建或 command buffer 引用。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_push_descriptor` 会影响绑定方式，但不改变 pipeline layout 中 set layout 的定义。

---

## 4. 标准使用流程

```text
分析 shader 中所有 set/binding 与 push constant
→ 为每个 set 创建 VkDescriptorSetLayout
→ 合并 shader stage 的 push constant 范围
→ 填写 VkPipelineLayoutCreateInfo
    → setLayoutCount / pSetLayouts
    → pushConstantRangeCount / pPushConstantRanges
→ vkCreatePipelineLayout
→ 用于创建 VkPipeline
→ 在 command buffer 中 vkCmdBindDescriptorSets 时使用兼容 layout
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `setLayoutCount` / `pSetLayouts` | set 0..N-1 的顺序必须与 shader 中 set 声明一致。[SPEC] | shader 用 set=1，但 pipeline layout 只提供 set 0。[TOOL] |
| `pushConstantRangeCount` / `pPushConstantRanges` | offset/size 必须覆盖 shader 中 `layout(push_constant)` 范围；多个 range 的 stage 不能重叠。[SPEC] | 两个 range 在同一 stage 上 offset/size 重叠。[TOOL] |
| `stageFlags` (push constant) | 必须覆盖访问该 push constant 的所有 shader stage。[SPEC] | fragment shader 用 push constant 但 stageFlags 只填 VERTEX。[TOOL] |
| `layout` compatibility | 绑定 descriptor set 时，当前 pipeline layout 必须与创建 pipeline 时的 layout “兼容”。[SPEC] | 重新创建了“等价”但 handle 不同的 layout，仍被判定不兼容导致 bind 失败。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `pSetLayouts` 顺序是否与 shader 中 set index 一致？
- [ ] 每个 set layout 是否与对应 shader set 的 binding 兼容？
- [ ] push constant range 是否覆盖所有 stage 且不重叠？
- [ ] push constant offset / size 是否满足 `maxPushConstantsSize` 限制？

### 使用阶段

- [ ] `vkCmdBindDescriptorSets` 的 `firstSet` / `setCount` 是否在此 layout 范围内？
- [ ] 绑定的 descriptor set 的 layout 是否与 pipeline layout 中对应 set 兼容？
- [ ] 当前绑定的 pipeline 的 layout 是否与 bind 时使用的 layout 兼容？

### 销毁阶段

- [ ] 所有引用该 layout 的 pipeline 已不再使用。
- [ ] 不建议在仍有 in-flight command buffer 引用相关 pipeline 时销毁 layout。[HEUR]

---

## 7. 高频错误

1. Pipeline layout 中 set layout 顺序与 shader set 不一致。[TOOL]
2. Push constant range stageFlags 未覆盖实际使用 stage。[TOOL]
3. Push constant range 在同一 stage 重叠。[TOOL]
4. 重新创建了“看起来一样”的 pipeline layout，但 Vulkan 要求兼容性是严格基于创建参数判定的。[SPEC]
5. `vkCmdBindDescriptorSets` 的 set index 超出 pipeline layout 范围。[TOOL]
6. Descriptor set layout 的 binding 与 shader 不一致，导致 bind 时报 compatibility 错。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkPipelineLayoutCreateInfo-*`：set layout / push constant range 合法性。
- `VUID-vkCmdBindDescriptorSets-*`：pipeline layout 兼容性。
- `VUID-vkCmdDraw-*` / `VUID-vkCmdDispatch-*`：descriptor set / push constant 可访问性。

### RenderDoc / AGI

- 查看当前 pipeline 的 pipeline layout。
- 查看每个 set 的 descriptor set layout 与 bound resources。
- 查看 push constant 取值。

### 日志 / 代码检查

- 对比 shader reflection 的 set/binding/push constant 与 `VkPipelineLayoutCreateInfo`。
- 检查 pipeline 创建和 descriptor set 绑定时使用的 layout 是否为同一对象或兼容对象。

---

## 9. 生命周期风险

### 创建时机

- 在所有相关 descriptor set layout 创建之后、pipeline 创建之前。

### 使用时机

- Pipeline 创建时引用。
- Command buffer 录制绑定 descriptor set 时引用。

### 销毁时机

- 所有相关 pipeline 销毁后即可销毁；pipeline 创建完成后会保留 layout 信息。[SPEC]
- 保守做法：与 pipeline 同生命周期。[HEUR]

### in-flight 风险

- Pipeline layout 不直接被 command buffer 引用，被引用的是 pipeline 和 descriptor set layout。
- 若 pipeline 仍 in-flight，layout 虽可销毁，但建议等待 GPU 完成。[HEUR]

---

## 10. 同步风险

- Pipeline layout 本身不涉及同步。
- 但 layout 决定了 descriptor set 与 push constant 的接口；资源访问同步由 barrier / event / subpass dependency 负责。[SPEC]

---

## 11. Android 注意点

- Android 上 pipeline layout 不匹配是常见 validation error 来源。[ANDROID]
- 横竖屏切换、swapchain recreate 不强制重建 pipeline layout，但若相关 descriptor set layout 被重建，需同步重建 pipeline layout 与所有 pipeline。[ANDROID]
- AGI 可查看 pipeline layout 与 descriptor binding。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Pipeline layout 创建开销很小，但不同 layout 会增加 pipeline 组合数。[ENGINE]
- 频繁切换 pipeline layout（通过切换 pipeline）会带来 descriptor set 重新绑定开销。[ENGINE]

### GPU 侧

- Layout 本身无 GPU 开销，但 set 数量与绑定频率影响 command buffer 解析。[HEUR]

### 移动端

- 移动端对 descriptor set 切换敏感，建议按更新频率分组，减少 set 数量。[ENGINE]
- 避免为每个 material 创建不同 pipeline layout；尽量复用统一 layout。[ENGINE]

---

## 13. 专家经验

**经验**：
项目中应维护一份“全局 descriptor set schema”，例如 set 0 = per-frame camera，set 1 = per-pass input，set 2 = per-material textures。所有 shader 遵守这份 schema，pipeline layout 由 schema 自动生成，可最大限度减少 compatibility 问题。

**适用条件**：
多 shader、多 pass、资源更新频率可分类的中大型项目。

**不适用情况**：
demo 或快速原型，shader 接口差异很大。

**来源**：`[ENGINE]`

---

## 14. 相关 API 卡片

- `../05_descriptor/descriptor_set_layout.md`（`../05_descriptor/descriptor_set_layout.md`）
- `../05_descriptor/descriptor_set.md`（`../05_descriptor/descriptor_set.md`）
- `../05_descriptor/descriptor_update.md`（`../05_descriptor/descriptor_update.md`）
- `graphics_pipeline.md`
- `compute_pipeline.md`
- `shader_module.md`

---

## 15. 需要回查官方文档的情况

1. Pipeline layout compatibility 的精确规则（包括 set layout 与 push constant range 的判定）。
2. 同一 pipeline layout 被多个 pipeline 共享时的限制。
3. Push descriptor 与 pipeline layout 的交互。
4. `VK_EXT_descriptor_indexing` 对 layout 的额外要求。

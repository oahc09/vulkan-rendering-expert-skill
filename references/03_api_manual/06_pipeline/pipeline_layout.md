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
| `pushConstantRangeCount` / `pPushConstantRanges` | offset/size 必须覆盖 shader 中 `layout(push_constant)` 范围；任意两个 range 的 stageFlags 不得含同一 stage，即使字节范围不相交；不同 stage 的字节范围可重叠。[SPEC] | 同一 stage 出现在两个 range 中；是否字节重叠不是该创建约束的判据。[TOOL] |
| `stageFlags` (push constant) | 必须覆盖访问该 push constant 的所有 shader stage。[SPEC] | fragment shader 用 push constant 但 stageFlags 只填 VERTEX。[TOOL] |
| `layout` compatibility | descriptor set 绑定时核对应 set 定义；pipeline 使用已绑定 set N 时核 compatible for set N 与未被扰乱状态，不要求先绑定 pipeline。[SPEC] | 以 handle 不同判不兼容，或仅比较 set N 而遗漏 0..N、push ranges 和 INDEPENDENT_SETS 标志。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `pSetLayouts` 顺序是否与 shader 中 set index 一致？
- [ ] 每个 set layout 是否与对应 shader set 的 binding 兼容？
- [ ] push constant range 是否覆盖实际使用的字节/stage，且任意两 range 的 stageFlags 没有重复 stage？不同 stage 的字节重叠不自动非法。
- [ ] push constant offset / size 是否满足 `maxPushConstantsSize` 限制？

### 使用阶段

- [ ] `vkCmdBindDescriptorSets` 的 `firstSet` / `setCount` 是否在此 layout 范围内？
- [ ] 绑定的 descriptor set 的 layout 是否与 pipeline layout 中对应 set 兼容？
- [ ] 使用已绑定 set N 时，pipeline layout 是否与该 set 的绑定 layout compatible for set N，且该 set 未因其他绑定被扰乱？

### 销毁阶段

- [ ] 所有引用该 layout 的 pipeline 已不再使用。
- [ ] 不建议在仍有 in-flight command buffer 引用相关 pipeline 时销毁 layout。[HEUR]

---

## 7. 高频错误

1. Pipeline layout 中 set layout 顺序与 shader set 不一致。[TOOL]
2. Push constant range stageFlags 未覆盖实际使用 stage。[TOOL]
3. 同一 stage 被列入多个 push constant range，即使这些 range 的字节区间互不相交。[TOOL]
4. 仅凭 handle 或表面相似性判断 layout compatibility；不同 handle 可以兼容，须按相应兼容关系检查定义。[SPEC]
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

## Delivery19 compute interface delivery chain (bounded L1/L2)

The artifact boundary is not the pipeline boundary. Pair exact shader binary,
validator target/result and disassembly before deriving an interface. Match its
set/binding, descriptor type and compute visibility to the layout used by the
actual pipeline. Missing bindings or missing stage visibility violate07988;
incompatible ordinary descriptor type violates07990. Descriptor arrays add count
requirements (07991), but the paired extractor deliberately does not implement
arrays and must return UNKNOWN rather than silently treating them as one resource.

`tools/pipeline_interface19.py` only extracts direct Block StorageBuffer variables
from a single GLCompute entrypoint with Shader-only capability and no extensions.
Its source is actual SPIRV-Tools output, with binary/disassembly digests paired to
validation. Uniform/UniformConstant, push constants, multi-entry modules, descriptor
arrays and optional capabilities are not supported by this extractor. Dynamic
and mutable descriptor layout types also return UNKNOWN rather than a false
ordinary-type mismatch diagnostic. Do not use
its positive result as general reflection, descriptor update permission, layout
compatibility across unrelated pipelines, or proof of all Vulkan validity.

The complete experiment in `cases19/pipeline_interface` keeps an intentionally
wrong layout, an inspectable minimal repair and actual compiled artifacts. A
Validation diagnostic and abort prove the bad API call was rejected, not that
undefined execution occurred. The repaired path must create the pipeline, bind
its descriptor, dispatch, establish device-to-host visibility, wait and read the
expected result. A clean validation log without correct readback is insufficient;
a deliberately wrong readback expectation must fail. Keep resource lifetime and
cleanup errors in the result instead of ignoring them after a nominal pass.

This joins shader artifact, interface, descriptor and command/memory evidence for
one ordinary compute workload. It is authored fault injection, not discovered
production-engine failure. Check the paired summary for actual diagnostics and
runtime/tool identity. Hardware, performance, broader layout features, SC, Live
and original-plan external-engine acceptance remain separate.

Source: [compute pipeline interface requirements](https://docs.vulkan.org/refpages/latest/refpages/source/VkComputePipelineCreateInfo.html).

<a id="delivery19-layout-push-contract"></a>

### delivery19-layout-push-contract

这是本卡前后表述与创建/更新跨步骤的限定修正，不宣称另一张卡存在反话。
兼容性不要求相同 handle。普通 pipeline layout 的 **compatible for set N**
要求 sets 0..N 的 descriptor set layout identically defined、相同 push constant
ranges，且双方 `VK_PIPELINE_LAYOUT_CREATE_INDEPENDENT_SETS_BIT_EXT` 标志一致。
**compatible for push constants** 只要求相同 push constant ranges；
不能把它代替 set N 兼容性。绑定 descriptor set 不要求先绑定 pipeline；
pipeline 使用旧 set 时仍须满足兼容性及未被其他绑定扰乱的条件。

创建 `VkPipelineLayout`：任意两 range 不得重复同一 stage（00292），
不是“只禁止同 stage 的字节交叠”。例如 VERTEX[0,4) 与 VERTEX[16,20)
仍违反此条件；VERTEX[0,16) 与 FRAGMENT[0,16) 不因字节重叠违反此条件，
但仍须满足范围、stage 有效性及其他创建规则。

更新 `vkCmdPushConstants` 是独立合同：01795 要求更新的每个 byte/stage
都由 layout range 覆盖；01796 要求每个更新 byte 所重叠的所有 range 的
stageFlags 都包含在本次更新 stageFlags 中。上述 VERTEX/FRAGMENT 同字节
范围即使创建合法，也不能只用 VERTEX 更新该重叠区域。还须另核
offset/size 的 4 字节粒度、设备限额及命令录制条件。创建合法不推出更新合法。

固定正文：Vulkan-Docs commit `fa30d4e312e843193601be7cb926c7e25d9ec885`
（Registry API 1.4.368），`chapters/descriptorsets.adoc`
SHA256 `3de692bf6e4f8579de50175be94c564a4580e1b8f0a59ed1e1267e1c3ca88950`，
`[[descriptors-compatibility]]`、`[[descriptors-push-constants]]`，
及正文中的 `VUID-VkPipelineLayoutCreateInfo-pPushConstantRanges-00292`。
另以 API 1.4.309 validusage SHA256
`f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7`
核对 `VUID-VkPipelineLayoutCreateInfo-pPushConstantRanges-00292`、
`VUID-vkCmdPushConstants-offset-01795`、`VUID-vkCmdPushConstants-offset-01796`。
两份版本来源分别绑定，不合称同版本完整规范、自动语义或 GPU 验收。

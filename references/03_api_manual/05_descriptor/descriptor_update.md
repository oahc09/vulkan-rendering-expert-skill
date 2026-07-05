# API Card: vkUpdateDescriptorSets

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorSet` / `VkWriteDescriptorSet` / `VkCopyDescriptorSet` |
| 常用 API | `vkUpdateDescriptorSets` / `vkUpdateDescriptorSetWithTemplate` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`vkUpdateDescriptorSets` 把实际的 buffer、image view、sampler 写入 descriptor set 的具体 binding，是 shader resource declaration 与 Vulkan 资源对象之间的“接线”操作。[SPEC]

---

## 2. 所属对象链路

```text
VkDescriptorSet (已分配)
+ VkWriteDescriptorSet
    → dstSet / dstBinding / dstArrayElement
    → descriptorType
    → descriptorCount
    → pBufferInfo / pImageInfo / pTexelBufferView
→ vkUpdateDescriptorSets
→ Descriptor Set 持有资源引用
→ vkCmdBindDescriptorSets
→ Shader Access
```

### 上游依赖

- `VkDescriptorSet` 已分配且 layout 已知。[SPEC]
- 要写入的资源（buffer / image view / sampler / buffer view）已创建。[SPEC]
- 资源 layout（对 image descriptor）已确定。[SPEC]

### 下游影响

- Shader 访问 descriptor 时实际读取这些资源。[SPEC]
- Descriptor set 被 GPU 使用后，其内容不能随意修改（除非 update-after-bind）。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkWriteDescriptorSet`
- `VkDescriptorBufferInfo`
- `VkDescriptorImageInfo`
- `VkCopyDescriptorSet`

### 常用 API

| API | 作用 |
|---|---|
| `vkUpdateDescriptorSets` | 批量写入 descriptor。[SPEC] |
| `vkUpdateDescriptorSetWithTemplate` | 使用 template 批量更新，降低 CPU 开销。[GUIDE] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_descriptor_update_template`：1.1 核心化，适合高频更新。
- `VK_EXT_descriptor_indexing`：支持 update after bind。

---

## 4. 标准使用流程

```text
准备 VkDescriptorBufferInfo / VkDescriptorImageInfo
→ 填写 VkWriteDescriptorSet
    → dstSet
    → dstBinding
    → dstArrayElement (array 起始索引)
    → descriptorType
    → descriptorCount
    → pImageInfo / pBufferInfo / pTexelBufferView
→ 调用 vkUpdateDescriptorSets(device, writeCount, writes, 0, nullptr)
→ 在 command buffer 中 vkCmdBindDescriptorSets
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `dstSet` | 目标 descriptor set。[SPEC] | 更新到错误 set。[ENGINE] |
| `dstBinding` | 必须与 layout / shader 一致。[SPEC] | binding 写错位置。[TOOL] |
| `dstArrayElement` | array descriptor 的起始元素。[SPEC] | 非 array 时未填 0。[TOOL] |
| `descriptorType` | 必须与 layout 一致。[SPEC] | layout 是 UBO，update 写成 COMBINED_IMAGE_SAMPLER。[TOOL] |
| `descriptorCount` | 更新的 descriptor 数量。[SPEC] | array 大小不一致。[TOOL] |
| `pImageInfo->imageLayout` | 对 image descriptor 必须与实际 consumer layout 一致。[SPEC] | layout 填写为 SHADER_READ_ONLY_OPTIMAL，但 image 实际是 COLOR_ATTACHMENT_OPTIMAL。[TOOL] |
| `pBufferInfo->offset` / `range` | 对 buffer descriptor 必须满足 alignment 且在 buffer size 内。[SPEC] | uniform offset 未对齐。[TOOL] |
| `pTexelBufferView` | texel buffer 使用 buffer view。[SPEC] | 误用 image info 更新 texel buffer。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Descriptor set 是否已分配？
- [ ] Write 的 type 是否与 layout 一致？
- [ ] Binding 是否在 layout 中存在？

### 使用阶段

- [ ] Image descriptor 的 layout 是否与实际 layout 一致？
- [ ] Buffer offset / range 是否满足 alignment？
- [ ] Sampler 是否对 combined image sampler 有效？
- [ ] 资源是否仍在有效期内？

### 销毁阶段

- [ ] 更新后的 descriptor set 是否仍被 GPU 使用？
- [ ] 资源销毁前是否已更新 descriptor 指向新资源或等待 GPU idle？

---

## 7. 高频错误

1. `descriptorType` 与 layout 不一致。[TOOL]
2. `dstBinding` 与 shader / layout 不一致。[TOOL]
3. Image descriptor 的 `imageLayout` 与实际 layout 不一致。[TOOL]
4. Uniform buffer offset 不满足 alignment。[TOOL]
5. Combined image sampler 只更新 image 没更新 sampler。[TOOL]
6. Swapchain recreate 后未更新引用旧 image view 的 descriptor。[ENGINE]
7. 在 GPU 使用 descriptor set 期间 update 它（非 update-after-bind）。[SPEC]
8. `descriptorCount` 与数组大小不一致。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkWriteDescriptorSet-*`：dstSet / dstBinding / type / count / info 合法性。
- `VUID-vkUpdateDescriptorSets-*`：descriptor set 状态、资源有效性。
- `VUID-vkCmdDraw-*`：descriptor image layout 与实际 layout 匹配。

### RenderDoc / AGI

- 查看每个 draw / dispatch 的 descriptor binding。
- 查看 binding 指向的 buffer / image view / sampler。
- 查看 image layout 和 buffer range。

### 日志 / 代码检查

- 检查 `vkUpdateDescriptorSets` 的 writes 数组内容。
- 对比 shader reflection 的 binding 表。
- 检查 swapchain recreate 后的 descriptor 更新路径。

---

## 9. 生命周期风险

### 创建时机

- Descriptor set 分配后，首次使用前必须 update。

### 使用时机

- 可在 command buffer 录制前或录制中更新（但需遵守 update-after-bind 规则）。[SPEC]
- 每帧更新 per-frame descriptor 是常见做法。

### 销毁阶段

- 资源销毁前，必须确保没有 descriptor set 引用它，或 GPU 已完成。[SPEC]

### in-flight 风险

- Descriptor set 被 submit 后，其内容（包括指向的资源）在 fence signal 前不能修改。[SPEC]
- 动态 uniform buffer 可通过 offset 切换避免更新 descriptor。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkUpdateDescriptorSets` 后，CPU 应确保资源内容已就绪（如 staging copy 完成）。
- 不要在 GPU 使用 descriptor set 期间 update（除非 update-after-bind）。[SPEC]

### GPU-GPU 同步

- Update 本身不控制 GPU-GPU 同步；资源 barrier 负责。

### 资源访问同步

- Image descriptor 的 layout 必须与 consumer 阶段的实际 layout 一致。[SPEC]
- Storage image / storage buffer 写入后如需读取，需要 barrier。[SPEC]

---

## 11. Android 注意点

- 移动端应尽量减少每帧 `vkUpdateDescriptorSets` 调用次数，使用 template 或预先分配。[ENGINE]
- Swapchain recreate 后务必更新引用旧 swapchain-size image 的 descriptor。[ANDROID]
- AGI 可验证 descriptor update 和 binding 状态。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 每帧大量 update 会增加 CPU overhead；可预先分配 descriptor set 或使用 dynamic offset。[ENGINE]
- Descriptor update template 可降低 per-update 成本。[GUIDE]

### GPU 侧

- Update 本身基本无 GPU 开销，但 descriptor set 切换有开销。[HEUR]

### 移动端

- 移动端 descriptor update 和 bind 开销明显，应减少高频更新。[ENGINE]
- 使用 push descriptor 处理少量每帧变化资源。[GUIDE]

---

## 13. 专家经验

**经验**：
对于每帧需要变化的资源（如 per-object transform），优先使用 dynamic uniform buffer + `vkCmdBindDescriptorSets` 时传入 dynamic offsets，而不是每帧 `vkUpdateDescriptorSets`。对于不常变化的资源（如 texture），一次性 update 后复用。

**适用条件**：
存在大量 per-draw 或 per-frame uniform 更新的场景。

**不适用情况**：
资源完全静态或更新频率极低的场景。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `descriptor_set_layout.md`
- `descriptor_set.md`
- `../06_pipeline/pipeline_layout.md`
- `../04_buffer_image_memory/image_view.md`
- `../04_buffer_image_memory/buffer.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. `VK_EXT_descriptor_indexing` 的 update-after-bind 同步规则。
2. `VkDescriptorBufferInfo` 的 offset / range 限制。
3. Combined image sampler 与 separate image / sampler 的 update 差异。
4. Texel buffer view 的创建与更新规则。

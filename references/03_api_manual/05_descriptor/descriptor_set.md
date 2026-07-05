# API Card: VkDescriptorSet

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorSet` |
| 常用 API | `vkCreateDescriptorPool` / `vkDestroyDescriptorPool` / `vkAllocateDescriptorSets` / `vkFreeDescriptorSets` / `vkResetDescriptorPool` / `vkCmdBindDescriptorSets` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkDescriptorSet` 是 `VkDescriptorSetLayout` 的实例，持有指向实际资源（buffer / image / sampler）的引用；它必须通过 descriptor pool 分配，并在 command buffer 录制时绑定到 pipeline。[SPEC]

---

## 2. 所属对象链路

```text
VkDescriptorSetLayout
→ VkDescriptorPool
→ vkAllocateDescriptorSets
→ VkDescriptorSet
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

### 上游依赖

- `VkDescriptorSetLayout` 必须已创建。[SPEC]
- `VkDescriptorPool` 必须按 layout 需求配置容量（type / count）。[SPEC]
- 要绑定的资源（buffer / image view / sampler）必须已创建。[SPEC]

### 下游影响

- Shader 通过 descriptor set 访问资源。[SPEC]
- Descriptor set 被 command buffer 引用后，在 GPU 完成前不能 free 或修改其引用的资源。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDescriptorSet`
- `VkDescriptorPool`
- `VkDescriptorPoolSize`
- `VkDescriptorSetAllocateInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateDescriptorPool` | 创建 pool，指定每种 descriptor type 的最大数量。[SPEC] |
| `vkDestroyDescriptorPool` | 销毁 pool，自动 free 其中所有 set。[SPEC] |
| `vkAllocateDescriptorSets` | 从 pool 分配 set。[SPEC] |
| `vkFreeDescriptorSets` | 释放单个 set（要求 pool 创建时允许 individual free）。[SPEC] |
| `vkResetDescriptorPool` | 重置整个 pool，释放其中所有 set。[SPEC] |
| `vkCmdBindDescriptorSets` | 在 command buffer 中绑定 set 到指定 pipeline bind point。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_descriptor_indexing`：支持 update after bind、variable count。[GUIDE]
- `VK_KHR_descriptor_update_template`：批量更新 descriptor，降低 CPU 开销。

---

## 4. 标准使用流程

```text
创建 VkDescriptorSetLayout
→ 计算所需 descriptor type 数量
→ vkCreateDescriptorPool
→ vkAllocateDescriptorSets
→ vkUpdateDescriptorSets (绑定 buffer / image view / sampler)
→ vkCmdBindDescriptorSets (在 command buffer 中)
→ vkQueueSubmit
→ GPU 使用
→ 下一帧可复用（reset pool 或 free/allocate）
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `maxSets` | pool 最多分配的 set 数量。[SPEC] | 分配数量超过 pool 容量。[TOOL] |
| `poolSizeCount` / `pPoolSizes` | 每种 descriptor type 的容量。[SPEC] | 某种 type 数量不足导致 allocate 失败。[TOOL] |
| `flags` | `VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT` 允许 individual free。[SPEC] | 需要 free 单个 set 但未设置 flag。[TOOL] |
| `descriptorSetCount` | 一次 allocate 的 set 数量。[SPEC] | 与 layouts 数组大小不一致。[TOOL] |
| `pSetLayouts` | 必须与 allocate 的 set 数量一致且 layout 匹配。[SPEC] | layout 错误导致 descriptor set 与 shader 不兼容。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Descriptor pool 的 capacity 是否覆盖所有可能分配的 set？
- [ ] 是否需要 `FREE_DESCRIPTOR_SET_BIT`？
- [ ] Set layout 是否正确？

### 使用阶段

- [ ] `vkUpdateDescriptorSets` 的 binding 是否与 layout 一致？
- [ ] Image descriptor 的 `imageLayout` 是否与实际 layout 一致？
- [ ] `vkCmdBindDescriptorSets` 的 `firstSet` / `setCount` / `pDescriptorSets` 是否与 pipeline layout 一致？
- [ ] Bind 的 pipeline bind point（graphics / compute）是否正确？

### 销毁阶段

- [ ] 是否等待 GPU 不再使用？
- [ ] 是 free 单个 set 还是 reset pool？

---

## 7. 高频错误

1. Descriptor pool 容量不足，allocate 失败。[TOOL]
2. Pool 未设置 `FREE_DESCRIPTOR_SET_BIT` 但尝试 free 单个 set。[TOOL]
3. `vkUpdateDescriptorSets` 的 binding 与 layout 不一致。[TOOL]
4. Image descriptor 的 `imageLayout` 与实际 layout 不一致。[TOOL]
5. `vkCmdBindDescriptorSets` 的 set index 与 pipeline layout 不一致。[TOOL]
6. Descriptor set 引用的资源被提前销毁或复用。[SPEC]
7. 每帧 allocate/free descriptor set 导致 CPU overhead。[ENGINE]
8. Swapchain recreate 后 descriptor 仍引用旧 image view。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorSetAllocateInfo-*`：pool capacity / layout 匹配。
- `VUID-vkUpdateDescriptorSets-*`：binding / type / resource 合法性。
- `VUID-vkCmdBindDescriptorSets-*`：pipeline layout 兼容性。
- `VUID-vkDestroyDescriptorPool-*`：pool 仍被 pending command buffer 引用。

### RenderDoc / AGI

- 查看每个 draw / dispatch 的 bound descriptor set。
- 查看每个 binding 指向的具体 buffer / image view / sampler。
- 查看 descriptor image layout。

### 日志 / 代码检查

- 检查 `vkAllocateDescriptorSets` 返回值。
- 检查 `vkUpdateDescriptorSets` 的 write 数组。
- 检查 `vkCmdBindDescriptorSets` 的参数。

---

## 9. 生命周期风险

### 创建时机

- Pipeline / layout 创建后。
- 可预先分配并复用，或按需分配。

### 使用时机

- Command buffer 录制时绑定。
- Update 可在 allocate 后的任何时间进行（除非使用 update-after-bind）。[SPEC]

### 销毁阶段

- 通过 `vkFreeDescriptorSets` 或 `vkResetDescriptorPool` 或 `vkDestroyDescriptorPool` 释放。[SPEC]
- 必须确保 GPU 不再使用。[SPEC]

### in-flight 风险

- Descriptor set 被 command buffer 引用后，fence signal 前不能 free 或修改其内容。[SPEC]
- Descriptor set 引用的资源在 GPU 完成前必须保持有效。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkUpdateDescriptorSets` 是 CPU 侧操作，但更新后的 descriptor 被 GPU 使用前需确保资源已就绪。[SPEC]
- 不要在 GPU 使用 descriptor set 期间 update 它（除非使用 update-after-bind 并正确同步）。[SPEC]

### GPU-GPU 同步

- Descriptor set 本身不控制同步；资源访问同步由 barrier / semaphore 管理。

### 资源访问同步

- Descriptor 中 image layout 必须与 consumer 阶段的实际 layout 一致。[SPEC]
- Storage buffer / storage image 写入后如需被后续 pass 读取，需要 barrier。[SPEC]

---

## 11. Android 注意点

- 移动端应避免每帧 allocate/free descriptor set，优先复用 pool 或 per-frame set。[ENGINE]
- Swapchain recreate 后必须更新引用旧 swapchain image view 的 descriptor。[ANDROID]
- AGI 可查看 descriptor binding 和 resource 内容。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 每帧 allocate/free descriptor set 开销较高；推荐预先分配并复用。[ENGINE]
- 使用 descriptor update template 批量更新可降低 CPU overhead。[GUIDE]

### GPU 侧

- Descriptor set 切换有开销，移动端尤其明显；应按 update frequency 分组。[ENGINE]

### 移动端

- 移动端 descriptor cache 较小，减少 set 数量和切换次数。[ENGINE]
- Push descriptor 适合每帧变化少的小资源集合。[GUIDE]

---

## 13. 专家经验

**经验**：
为不同更新频率设计 descriptor set：per-frame（view / camera）、per-pass（input attachments）、per-material（textures）、per-draw（dynamic offsets）。不要把所有资源塞进一个 set，也不要为每个 draw call 单独 allocate set。

**适用条件**：
中等以上复杂度的渲染项目，存在多种更新频率的资源。

**不适用情况**：
非常简单的一次性渲染，资源数量和更新频率都很低。

**来源**：`[ENGINE]`

---

## 14. 相关 API 卡片

- `descriptor_set_layout.md`
- `descriptor_update.md`
- `../06_pipeline/pipeline_layout.md`
- `../04_buffer_image_memory/image_view.md`
- `../04_buffer_image_memory/buffer.md`

---

## 15. 需要回查官方文档的情况

1. `VK_EXT_descriptor_indexing` 的 update-after-bind 规则。
2. Descriptor pool 的 capacity 计算方式。
3. Push descriptor 的使用限制。
4. Descriptor set layout 与 pipeline layout 的兼容性规则。

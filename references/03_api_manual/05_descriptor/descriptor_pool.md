# API Card: VkDescriptorPool

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorPool` |
| 常用 API | `vkCreateDescriptorPool` / `vkDestroyDescriptorPool` / `vkAllocateDescriptorSets` / `vkFreeDescriptorSets` / `vkResetDescriptorPool` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkDescriptorPool` 是 `VkDescriptorSet` 的批量分配器，通过预定义各类 descriptor 的总容量与最大 set 数，控制 descriptor 资源的分配与回收。[SPEC]

---

## 2. 所属对象链路

```text
VkDescriptorSetLayout
→ VkDescriptorPool（按 type 配置容量）
→ vkAllocateDescriptorSets
→ VkDescriptorSet[]
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

### 上游依赖

- 已创建的 `VkDescriptorSetLayout`。[SPEC]
- 明确的 descriptor 类型分布与数量预算。[ENGINE]

### 下游影响

- 决定可分配多少 descriptor set 以及每类 descriptor 的上限。
- 影响 descriptor set 的分配/释放策略与复用模式。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDescriptorPool`
- `VkDescriptorPoolCreateInfo`
- `VkDescriptorPoolSize`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateDescriptorPool` | 创建 descriptor pool，指定最大 set 数与各类 descriptor 容量。[SPEC] |
| `vkDestroyDescriptorPool` | 销毁 pool；会自动释放其中所有 set。[SPEC] |
| `vkAllocateDescriptorSets` | 从 pool 分配 descriptor set。[SPEC] |
| `vkFreeDescriptorSets` | 释放单个或多个 set（需 pool 创建时启用 `FREE_DESCRIPTOR_SET_BIT`）。[SPEC] |
| `vkResetDescriptorPool` | 一次性重置 pool，释放其中所有 set（无需 `FREE_DESCRIPTOR_SET_BIT`）。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_descriptor_indexing` / Vulkan 1.2 提供 update-after-bind、partially-bound 等能力。
- `VK_KHR_descriptor_update_template` 可加速 descriptor 更新。

---

## 4. 标准使用流程

```text
确定各类 descriptor 数量需求（UBO / sampled image / sampler / storage buffer 等）
→ 构造 VkDescriptorPoolSize[]
→ 指定 maxSets 与 pool 创建 flags（如 FREE_DESCRIPTOR_SET_BIT）
→ vkCreateDescriptorPool
→ vkAllocateDescriptorSets（引用 descriptor set layout）
→ vkUpdateDescriptorSets 写入资源
→ vkCmdBindDescriptorSets
→ 帧结束时 vkResetDescriptorPool 或按需 vkFreeDescriptorSets
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `maxSets` | pool 能分配的 descriptor set 总数。[SPEC] | 预算不足导致分配失败。[TOOL] |
| `poolSizeCount` / `pPoolSizes` | 每类 descriptor 的总容量；按类型累加。[SPEC] | 只按 set 数量估算，未考虑每 set 中 descriptor 数量。[TOOL] |
| `flags` | `VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT` 允许单独 free；否则只能 reset。[SPEC] | 想用 `vkFreeDescriptorSets` 却未设置 flag。[TOOL] |
| `pSetLayouts`（allocate 时） | 每个 set 的 layout。[SPEC] | layout 与 pool 中 descriptor 类型不匹配。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否按最坏情况估算各类 descriptor 数量？
- [ ] `maxSets` 是否覆盖所有需要同时存在的 set？
- [ ] 是否需要 `FREE_DESCRIPTOR_SET_BIT`？

### 使用阶段

- [ ] 分配前是否检查 pool 剩余容量？
- [ ] Descriptor set layout 是否与 pool 的 descriptor 类型兼容？
- [ ] 更新 descriptor 时资源是否仍在有效期内？

### 销毁阶段

- [ ] 是否先等待 GPU 完成 pool 中 set 的使用？
- [ ] 销毁 pool 前是否已释放/重置其中所有 set？

---

## 7. 高频错误

1. `maxSets` 或 pool size 预算不足，导致 `vkAllocateDescriptorSets` 返回 `VK_ERROR_OUT_OF_POOL_MEMORY`。[TOOL]
2. 想用 `vkFreeDescriptorSets` 但创建 pool 时未加 `FREE_DESCRIPTOR_SET_BIT`。[TOOL]
3. Pool 中某类 descriptor 数量耗尽，而另一类大量闲置。[ENGINE]
4. 销毁 pool 时其中仍有 in-flight 的 descriptor set。[TOOL]
5. 每帧创建/销毁 pool 导致 CPU 开销。[ENGINE]
6. 未将 descriptor 类型与 shader 声明对应，导致更新失败。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkAllocateDescriptorSets-*`：pool 容量、layout 兼容性。
- `VUID-vkFreeDescriptorSets-*`：pool 是否启用 free bit。
- `VUID-vkDestroyDescriptorPool-descriptorPool-00303`：pool 仍在使用时的销毁检查。

### RenderDoc / AGI

- 查看当前绑定的 descriptor set 与 pool 分配情况。
- 检查 descriptor 更新的内容。

### 日志 / 代码检查

- 检查 `vkAllocateDescriptorSets` 返回值。
- 检查 pool size 与 maxSets 的估算逻辑。
- 检查 reset/free 时机。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建，通常按 per-frame 或 per-pass 分组。[ENGINE]

### 使用时机

- 在需要分配 descriptor set 时使用。[SPEC]

### 销毁时机

- 确认 pool 中所有 set 都不再被 GPU 使用后销毁。[SPEC]
- 通常随 swapchain / frame-in-flight 资源一起重建。

### in-flight 风险

- Descriptor set 被 command buffer 引用后，pool 不能随意 reset 或销毁；需等 fence signal。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 更新 descriptor set 与 GPU 使用之间通常不需要显式 fence，但 reset/free pool 需要确保 GPU 已完成。[SPEC]

### GPU-GPU 同步

- Descriptor set 本身不引入同步；资源内容的同步由 barrier 负责。[SPEC]

### 资源访问同步

- 更新 descriptor set 只修改描述符内容，不修改被引用资源的状态；资源仍需正确 barrier。[SPEC]

---

## 11. Android 注意点

- 移动端 CPU 开销敏感，避免每帧分配 descriptor set；应使用 per-frame pool 并每帧 reset。[ANDROID][ENGINE]
- 某些低端设备对 descriptor pool 容量有隐式限制，建议对关键路径做 fallback。[ANDROID]
- 使用 `VK_EXT_descriptor_indexing` 的 update-after-bind 可减少每帧更新量，但需确认设备支持。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- `vkAllocateDescriptorSets` 与 `vkResetDescriptorPool` 是常见 CPU 热点；应池化复用。[ENGINE]
- 避免在渲染循环中创建/销毁 pool。[ENGINE]

### GPU 侧

- Pool 本身不直接影响 GPU 性能，但 descriptor 更新与绑定频率会影响 command processor。[ENGINE]

### 移动端

- 使用 per-frame pool：每帧开始时 reset，渲染中 allocate/update/bind，减少 free 操作。[ENGINE]
- 对静态资源使用持久化 descriptor set，避免每帧更新。[HEUR]

---

## 13. 专家经验

**经验**：
按“使用频率”而非“对象类型”组织 pool：per-frame pool 用于每帧变化的 UBO/dynamic descriptor，持久 pool 用于材质、光照等静态 descriptor。尽量不要让单个 pool 服务于差异巨大的生命周期，否则要么预算浪费，要么 in-flight 管理复杂。`vkResetDescriptorPool` 通常比逐个 `vkFreeDescriptorSets` 更快，除非你需要在帧内频繁回收个别 set。

**适用条件**：
中大规模场景、每帧有大量 descriptor 更新、需要稳定帧率的项目。

**不适用情况**：
资源绑定完全静态的简单 demo；或已使用 bindless descriptor indexing 彻底绕开传统 pool 分配。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_set_layout.md`
- `descriptor_update.md`
- `sampled_image_descriptor.md`
- `uniform_buffer_descriptor.md`
- `storage_buffer_image_descriptor.md`
- `../06_pipeline/pipeline_layout.md`
- `../06_pipeline/shader_module.md`

---

## 15. 需要回查官方文档的情况

1. 具体 descriptor type 与 descriptor set layout binding 的合法组合。
2. `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT` 的使用条件。
3. Inline uniform block 等特殊 descriptor 类型的 pool size 计算。
4. 不同驱动对 pool 容量与分配性能的隐式限制。
5. Descriptor update template 与 pool 的交互。

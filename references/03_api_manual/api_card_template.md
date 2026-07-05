# API Card Template

> 文件建议路径：`03_api_manual/api_card_template.md`
>
> 说明：本文件为 `03_api_manual` 正式 API Card 模板。`01_source_map_and_api_manual_strategy/api_card_template.md` 为早期轻量示例，已保留作参考。

---

# API Card: `<API / Object Name>`

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 / 显示链 / 命令链 / 资源链 / Descriptor 链 / Pipeline 链 / Rendering 链 / 同步链 / 调试链 / Android 平台链 |
| Vulkan 对象 | `VkXXX` |
| 常用 API | `vkXXX` |
| 适用平台 | 通用 / Android / Desktop / Mobile |
| 来源等级 | 参见 `01_source_map_and_api_manual_strategy/source_tags.md`，常用：`[SPEC] [REGISTRY] [REF] [GUIDE] [SAMPLE] [ANDROID] [AGI] [VENDOR] [TOOL] [ENGINE] [CASE] [HEUR]` |
| 适用 Vulkan 版本 | Vulkan 1.x / 扩展 / 需按项目确认 |

---

## 1. 一句话定位

用一句话说明这个 API / 对象在 Vulkan 工程中解决什么问题。

示例：

> `VkDescriptorSet` 用来把 Buffer、Image、Sampler 等资源绑定到 shader 可访问的位置，是 shader resource declaration 和 Vulkan 资源对象之间的桥梁。

---

## 2. 所属对象链路

说明它处在哪条 Vulkan 工程链路里。

```text
上游对象
→ 当前对象
→ 下游对象
```

示例：

```text
Shader set/binding
→ VkDescriptorSetLayout
→ VkPipelineLayout
→ VkDescriptorSet
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

### 上游依赖

- xxx
- xxx

### 下游影响

- xxx
- xxx

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkXXX`
- `VkXXXCreateInfo`
- `VkXXXFlagBits`
- `VkXXXUsageFlags`

### 常用 API

- `vkCreateXXX`
- `vkDestroyXXX`
- `vkCmdXXX`
- `vkGetXXX`

### 相关扩展 / 版本

- `VK_KHR_xxx`
- Vulkan 1.x core
- Android 是否可用：是 / 否 / 需查询设备能力

---

## 4. 标准使用流程

用流程描述，而不是堆 API。

```text
Step 1
→ Step 2
→ Step 3
→ Step 4
```

示例：

```text
创建 VkImage
→ 查询 memory requirements
→ 分配 VkDeviceMemory
→ bind memory
→ 创建 VkImageView
→ layout transition
→ 作为 attachment / sampled image / storage image 使用
```

---

## 5. 关键字段

只列最容易影响正确性和调试的字段，不完整复制官方文档。

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `xxx` | xxx | xxx |
| `xxx` | xxx | xxx |
| `xxx` | xxx | xxx |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 创建参数是否和使用场景匹配？
- [ ] flag / usage 是否覆盖后续用途？
- [ ] format / layout / stage / access 是否匹配？
- [ ] 是否查询并满足设备 feature / extension？
- [ ] 是否检查 API 返回值？

### 使用阶段

- [ ] 是否在正确 command buffer 状态下使用？
- [ ] 是否绑定到正确 pipeline bind point？
- [ ] 是否和 shader / pipeline / render target 匹配？
- [ ] 是否存在 in-flight 资源复用风险？

### 销毁阶段

- [ ] 是否确保 GPU 不再使用？
- [ ] 是否按依赖关系逆序销毁？
- [ ] swapchain recreate 时是否同步重建相关对象？

---

## 7. 高频错误

列出真实工程中最容易犯的错误。

1. xxx
2. xxx
3. xxx
4. xxx
5. xxx

示例：

```text
1. descriptor layout 和 shader binding 不一致。
2. image layout 填写为 SHADER_READ_ONLY_OPTIMAL，但实际资源仍是 COLOR_ATTACHMENT_OPTIMAL。
3. pipeline layout 不是创建 pipeline 时使用的那个。
```

---

## 8. Debug 检查路径

### Validation Layer

优先观察：

- VUID
- object handle
- object type
- command buffer state
- descriptor / image / pipeline / layout 相关错误

### RenderDoc / AGI

检查：

- 是否存在 draw call / dispatch call？
- pipeline 是否绑定正确？
- descriptor 是否绑定正确资源？
- texture / buffer 内容是否正确？
- render target 内容是否符合预期？
- pass 前后 image layout / attachment 是否合理？

### 日志 / 代码检查

检查：

- API 返回值
- 创建顺序
- 销毁顺序
- resize / recreate 路径
- frame-in-flight 资源索引

---

## 9. 生命周期风险

说明这个对象什么时候创建、什么时候使用、什么时候销毁。

### 创建时机

- xxx

### 使用时机

- xxx

### 销毁时机

- xxx

### in-flight 风险

说明是否可能被已经提交但尚未完成的 command buffer 引用。

```text
如果对象被 command buffer 引用，在对应 fence signal 之前不能销毁或复用。
```

---

## 10. 同步风险

说明是否涉及同步问题。

### CPU-GPU 同步

- 是否需要 fence？
- CPU 是否可能提前修改 / 销毁 GPU 正在使用的资源？

### GPU-GPU 同步

- 是否需要 semaphore？
- 是否跨 queue？
- 是否涉及 acquire / submit / present？

### 资源访问同步

- 是否需要 buffer barrier？
- 是否需要 image barrier？
- 是否需要 layout transition？
- producer stage / access 是什么？
- consumer stage / access 是什么？

---

## 11. Android 注意点

如果不涉及 Android，写：

```text
不适用。
```

如果涉及 Android，必须检查：

- Surface / ANativeWindow 生命周期
- swapchain recreate
- 横竖屏切换
- pause / resume
- `VK_ERROR_OUT_OF_DATE_KHR`
- `VK_SUBOPTIMAL_KHR`
- 旧 swapchain image / image view 是否仍被 command buffer 引用
- validation layer / AGI / logcat 验证

---

## 12. 性能注意点

说明这个 API / 对象可能带来的性能问题。

### CPU 侧

- 是否频繁创建 / 销毁？
- 是否每帧 allocate / update？
- 是否导致 CPU wait？

### GPU 侧

- 是否增加 full-screen pass？
- 是否增加 bandwidth？
- 是否增加 texture sampling？
- 是否导致 layout transition / barrier 过多？

### 移动端

- 是否增加 tile resolve？
- 是否增加 offscreen render target？
- 是否增加透明混合？
- 是否增加高精度 attachment 带宽？

---

## 13. 专家经验

写工程经验，但必须避免绝对化。

格式建议：

```text
经验：
xxx

适用条件：
xxx

不适用情况：
xxx
```

示例：

```text
经验：
descriptor set 不建议在高频路径中频繁 allocate/free，通常应复用 descriptor pool 或设计 per-frame descriptor 资源。

适用条件：
资源绑定频繁变化、CPU overhead 明显、移动端 CPU 预算紧张。

不适用情况：
资源数量极少、初始化阶段一次性绑定、性能瓶颈不在 CPU descriptor 更新。
```

---

## 14. 相关 API 卡片

列出需要联动查看的 API 卡片。

- `<your-related-api-card.md>`
- `<your-related-api-card.md>`
- `<your-related-api-card.md>`

示例：

```text
descriptor_set.md
pipeline_layout.md
shader_module.md
image_view.md
sampler.md
```

---

## 15. 需要回查官方文档的情况

以下情况不要凭经验判断，必须回查 Vulkan Spec / Reference Page / Android 文档：

1. VUID 具体含义。
2. 结构体字段合法组合。
3. extension / feature 是否在目标设备可用。
4. format / usage / tiling 支持情况。
5. queue family ownership transfer。
6. synchronization stage / access 精确匹配。
7. Android 特定平台行为。
8. Vulkan 版本差异。

---

# 简化版 API Card 模板

适合较轻量对象，例如：

- `VkSampler`
- `VkImageView`
- `VkFence`
- `VkSemaphore`
- `VkShaderModule`

```md
# API Card: <Name>

## 1. 定位

一句话说明作用。

## 2. 对象链路

```text
上游
→ 当前对象
→ 下游
```

## 3. 常用 API

- `vkCreateXXX`
- `vkDestroyXXX`

## 4. 关键字段

| 字段 | 关注点 |
|---|---|
| xxx | xxx |

## 5. 高频错误

1. xxx
2. xxx
3. xxx

## 6. Debug 检查点

- Validation：
- RenderDoc / AGI：
- 代码检查：

## 7. 生命周期 / 同步风险

- 创建：
- 使用：
- 销毁：
- in-flight 风险：

## 8. 相关卡片

- `<your-related-api-card.md>`

## 9. 来源等级

- 完整标签定义参见 `01_source_map_and_api_manual_strategy/source_tags.md`。
- 常用标签：`[SPEC] [REGISTRY] [REF] [GUIDE] [SAMPLE] [ANDROID] [AGI] [VENDOR] [TOOL] [ENGINE] [CASE] [HEUR]`
- 硬规则必须至少满足 `[SPEC]` / `[REGISTRY]` / `[REF]` / 平台限定的 `[ANDROID]` 之一。
```

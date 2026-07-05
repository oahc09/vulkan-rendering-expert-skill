# API Card 模板（轻量示例）

> 说明：本文件为 API Card 早期轻量示例。`03_api_manual/api_card_template.md` 是当前正式使用的完整模板，新增 API Card 请以该文件为准。

后续 `03_api_manual` 中的 API 卡片建议统一使用 `03_api_manual/api_card_template.md`。

```md
# API Card：<对象 / 链路名称>

## 适用场景

说明什么时候需要这个对象或 API 链路。

## 核心对象

- VkXXX
- VkXXXCreateInfo
- VkXXXFlagBits

## 常用 API

- vkCreateXXX
- vkDestroyXXX
- vkCmdXXX

## 对象链路

```text
对象 A
→ 对象 B
→ 对象 C
→ GPU 使用点
```

## 调用顺序

```text
Create
→ Configure
→ Bind / Update
→ Record Command
→ Submit
→ Destroy after GPU finished
```

## Valid Usage 关注点

1. 字段 / flag 是否匹配用途。
2. 对象生命周期是否覆盖 GPU 使用期。
3. 资源状态是否满足访问要求。
4. 同步是否覆盖 producer / consumer。
5. Android 或平台相关约束是否满足。

## 高频错误

1. 错误一。
2. 错误二。
3. 错误三。

## Debug 方法

1. 开启 validation layer。
2. 提取 VUID。
3. 沿对象链路定位创建点。
4. 沿 command buffer 定位使用点。
5. 使用 RenderDoc / AGI 查看实际绑定状态。
6. 给出最小复现和最小修复。

## 专家经验

写工程经验，但必须标注来源等级，例如 `[ENGINE]`、`[TOOL]`、`[HEUR]`。

## 参考来源

- Vulkan Spec / Reference Page
- Vulkan Guide / Samples
- Android NDK / AGI 文档
```

## 示例：Descriptor Set 卡片骨架

```md
# API Card：Descriptor Set

## 适用场景

用于把 shader 需要访问的 buffer、image、sampler、storage resource 绑定到 pipeline。

## 核心对象

- VkDescriptorSetLayout
- VkDescriptorPool
- VkDescriptorSet
- VkWriteDescriptorSet
- VkPipelineLayout

## 常用 API

- vkCreateDescriptorSetLayout
- vkCreateDescriptorPool
- vkAllocateDescriptorSets
- vkUpdateDescriptorSets
- vkCmdBindDescriptorSets

## 对象链路

```text
Shader set/binding
→ VkDescriptorSetLayoutBinding
→ VkDescriptorSetLayout
→ VkPipelineLayout
→ VkDescriptorSet
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

## 高频错误

1. shader binding 与 descriptor layout 不匹配。
2. descriptorType 与 shader resource 类型不匹配。
3. PipelineLayout 不包含当前 descriptor set layout。
4. image descriptor 的 imageLayout 与实际 layout 不一致。
5. 资源被 GPU 使用期间提前销毁。
```

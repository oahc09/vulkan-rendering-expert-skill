# Pipeline / Descriptor / Shader 绑定关系

## 核心思想

Descriptor 错误通常不是单点错误，而是 shader、descriptor layout、pipeline layout、descriptor set、资源生命周期之间的链路错误。

核心链路：

```text
Shader Resource Declaration
→ DescriptorSetLayout
→ PipelineLayout
→ DescriptorSet
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

## Shader 侧声明

示例：

```glsl
layout(set = 0, binding = 1) uniform sampler2D uTexture;
```

Vulkan 侧必须匹配：

1. set = 0。
2. binding = 1。
3. descriptorType = combined image sampler 或对应类型。
4. descriptorCount 匹配数组数量。
5. stageFlags 覆盖实际 shader stage。
6. PipelineLayout 包含 set 0 的 DescriptorSetLayout。
7. DescriptorSet 按相同 layout 分配。
8. vkUpdateDescriptorSets 更新正确 image / sampler / buffer。
9. vkCmdBindDescriptorSets 绑定到正确 pipeline bind point。

## PipelineLayout 的角色

```text
PipelineLayout = DescriptorSetLayout[] + PushConstantRange[]
```

它定义 shader 可以访问哪些 descriptor set 和 push constant。

Pipeline 创建时使用的 PipelineLayout，必须和 draw / dispatch 时绑定的 descriptor set 兼容。

## DescriptorSetLayout 的角色

```text
DescriptorSetLayoutBinding
  - binding
  - descriptorType
  - descriptorCount
  - stageFlags
```

它必须和 shader resource declaration 对齐。

## DescriptorSet 的角色

DescriptorSet 是实际绑定资源的实例。

```text
DescriptorSetLayout 是布局。
DescriptorSet 是按这个布局分配出来的资源绑定实例。
```

## 高频错误

1. shader `set/binding` 与 DescriptorSetLayoutBinding 不一致。
2. descriptorType 与 shader resource 类型不匹配。
3. PipelineLayout 不包含当前 DescriptorSetLayout。
4. descriptor set 按 layout A 分配，却绑定到 layout B 的 pipeline。
5. image descriptor 的 imageLayout 填错。
6. buffer offset / range 不正确。
7. 资源被销毁，但 descriptor 仍引用它。
8. graphics / compute bind point 绑定错误。

## Debug 链路

Descriptor 报错时，不要只看 `vkUpdateDescriptorSets`。

应按顺序检查：

```text
1. Shader reflection：set / binding / resource type。
2. VkDescriptorSetLayoutBinding：binding / type / count / stageFlags。
3. VkPipelineLayout：是否包含对应 set layout。
4. VkDescriptorPool：类型和数量是否足够。
5. VkDescriptorSet：是否由正确 layout 分配。
6. vkUpdateDescriptorSets：resource info 是否正确。
7. vkCmdBindDescriptorSets：bind point / set index / dynamic offset 是否正确。
8. Resource lifetime：buffer / image / sampler 是否仍有效。
9. RenderDoc：检查 bound resources。
```

## 专家规则

```text
Descriptor clean 的关键不是“更新成功”，而是 shader → layout → pipeline → set → resource → lifetime 全链路一致。
```

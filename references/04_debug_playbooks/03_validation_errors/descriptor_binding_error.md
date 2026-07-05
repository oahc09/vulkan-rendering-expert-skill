# Debug Playbook: Descriptor Binding Error

## 0. 适用范围

### 适用

- Validation 报 descriptor binding mismatch。
- Shader 访问 texture / buffer 失败。
- RenderDoc 中 bound resource 为空或不匹配。
- Descriptor 更新后 shader 读不到数据。

### 不适用

- 纯 image layout 错误。
- 资源内容上传错误但 descriptor 本身正确。
- Pipeline 创建阶段 shader 编译失败。

---

## 1. 现象

常见表现：

- Validation 提到 descriptor set / binding / pipeline layout。
- shader 中采样结果为黑色。
- uniform buffer 参数不更新。
- storage buffer / storage image 数据不生效。
- RenderDoc 显示 descriptor 未绑定或绑定了错误资源。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | shader set/binding 和 layout 不一致 | VUID 提到 binding / set | Shader / DescriptorSetLayout |
| P0 | descriptorType 不匹配 | VUID 提到 type mismatch | DescriptorSetLayout / Update |
| P0 | PipelineLayout 不匹配 | VUID 提到 pipeline layout compatibility | PipelineLayout |
| P1 | vkUpdateDescriptorSets 资源错误 | RenderDoc bound resource 异常 | DescriptorSet |
| P1 | imageLayout 填错 | VUID 提到 descriptor image layout | Image / Descriptor |
| P2 | 资源生命周期错误 | resource destroyed / invalid handle | Buffer / Image |

---

## 3. 快速验证路径

1. 查 shader 中 `set` / `binding`。
2. 查 `VkDescriptorSetLayoutBinding`。
3. 查 `VkPipelineLayoutCreateInfo`。
4. 查 descriptor set allocation 使用的 layout。
5. 查 `vkUpdateDescriptorSets`。
6. 查 `vkCmdBindDescriptorSets` 的 set index 和 bind point。
7. 用 RenderDoc 查看 bound resources。

---

## 4. Vulkan 对象链路排查

```text
Shader Resource Declaration
→ DescriptorSetLayout
→ PipelineLayout
→ DescriptorPool
→ DescriptorSet Allocation
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

逐项检查：

- `set` 是否一致。
- `binding` 是否一致。
- `descriptorType` 是否一致。
- `descriptorCount` 是否一致。
- `stageFlags` 是否覆盖实际 shader stage。
- pipeline 创建使用的 layout 是否就是 bind 时使用的 layout。
- descriptor set 是否来自相同 layout。
- resource 是否仍然有效。
- image descriptor 的 `imageLayout` 是否匹配实际 layout。

---

## 5. 高频根因

1. shader 中 `layout(set = 0, binding = 1)`，Vulkan 侧写成 binding 0。
2. fragment shader 使用资源，但 stageFlags 只填了 vertex。
3. sampled image 写成 storage image，或 storage buffer 写成 uniform buffer。
4. pipeline layout 和 descriptor set layout 不匹配。
5. descriptor set 更新的是旧资源。
6. descriptor 对应 image 已经被重建或销毁。
7. dynamic offset 不满足 alignment。

---

## 6. 修复方案

### 最小修复

- 以 shader reflection / shader 源码为准，修正 descriptor layout。
- 修正 descriptor type / binding / set index。
- 确认 pipeline layout 包含正确 descriptor set layout。

### 稳定修复

- 建立 shader reflection 自动生成 descriptor layout。
- 建立 descriptor binding 表。
- 为 per-frame descriptor 建立 frame index 隔离。
- swapchain recreate 时更新引用尺寸相关 image 的 descriptor。

---

## 7. 回归验证

- [ ] Validation 不再报 descriptor 相关错误。
- [ ] RenderDoc bound resources 正确。
- [ ] shader 能读取正确 texture / buffer。
- [ ] 多帧运行资源不串帧。
- [ ] swapchain recreate 后 descriptor 仍正确。

---

## 8. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/sampler.md`

---

## 9. 工具证据

### Validation Layer

关注：

- binding number
- set number
- descriptorType
- pipeline layout compatibility
- descriptor imageLayout

### RenderDoc / AGI

关注：

- Bound resources
- Descriptor set
- Texture / buffer preview
- Shader resource binding

---

## 10. Android 分支

Android 上 swapchain recreate 后需要额外检查：

1. descriptor 是否仍引用旧 offscreen image。
2. texture / sampled image 是否被释放。
3. per-frame descriptor 是否和 frame index 对齐。
4. Surface 重建后是否重建尺寸相关 descriptor。

---

## 11. 不确定时如何处理

需要补充：

- shader resource declaration
- descriptor set layout 创建代码
- pipeline layout 创建代码
- vkUpdateDescriptorSets 代码
- vkCmdBindDescriptorSets 代码
- Validation message / VUID

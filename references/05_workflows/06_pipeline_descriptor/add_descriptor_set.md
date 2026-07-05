# Workflow: Add Descriptor Set

## 0. 适用范围

### 适用

- 新增一个 descriptor set，用于绑定 UBO、SSBO、image、sampler、texel buffer、input attachment 等资源。
- 需要处理 layout、pool、allocation、update、bind、生命周期。
- per-frame、per-pass、per-material、per-object 的 descriptor 管理。

### 不适用

- 使用 push descriptor（`VK_KHR_push_descriptor`）或 descriptor buffer（`VK_EXT_descriptor_buffer`）的场景（可部分参考 layout 部分）。
- 完全由引擎自动分配 descriptor 的渲染框架。
- 不需要自定义 descriptor set、直接使用 push constants 即可的场景。

---

## 1. 任务目标

新增一个 descriptor set：

```text
VkDescriptorSetLayout
→ VkDescriptorPool
→ vkAllocateDescriptorSets
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader 访问资源
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- Shader 中 set/binding 布局。
- Descriptor 类型：UBO、SSBO、COMBINED_IMAGE_SAMPLER、SAMPLED_IMAGE、STORAGE_IMAGE、INPUT_ATTACHMENT 等。
- Descriptor 数量与更新频率：per-frame、per-material、per-object。
- 是否使用 dynamic offset（UBO_DYNAMIC / SSBO_DYNAMIC）。
- 是否需要 update-after-bind 或 push descriptor。
- 当前 descriptor pool 容量是否足够。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] Shader reflection 已输出 set/binding/type/stage 信息。
- [ ] Descriptor pool 对目标类型有余量。
- [ ] Pipeline layout 已创建并引用对应 descriptor set layout。
- [ ] 被绑定资源（buffer/image）已创建且生命周期覆盖使用期间。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Shader Reflection (set/bindings)
→ VkDescriptorSetLayout
→ VkDescriptorPool
→ VkDescriptorSet
→ vkUpdateDescriptorSets (buffer/image/sampler info)
→ vkCmdBindDescriptorSets (with optional dynamic offsets)
→ VkPipelineLayout
→ Shader Resource Access
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| descriptor set layout | `VkDescriptorSetLayout` | 绑定方案定义 | 通常全局 | 否 |
| descriptor pool | `VkDescriptorPool` | 分配 descriptor set | per-frame / per-scene | 否（通常） |
| descriptor set | `VkDescriptorSet` | 具体资源绑定 | per-frame / per-pass / per-material | 视策略而定 |
| buffer info | `VkDescriptorBufferInfo` | buffer + offset + range | update 时使用 | 否 |
| image info | `VkDescriptorImageInfo` | image view + sampler + layout | update 时使用 | 视资源而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame UBO | Vertex / Fragment / Compute |
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | diffuse map | Fragment |
| set=1,binding=1 | `COMBINED_IMAGE_SAMPLER` | normal map | Fragment |
| set=2,binding=0 | `STORAGE_BUFFER` | instance data | Vertex / Fragment |
| set=3,binding=0 | `INPUT_ATTACHMENT` | subpass input | Fragment |

设计说明：

- layout 中 `descriptorCount` 指该 binding 的 descriptor 数组大小；单个 UBO 填 1 [SPEC]。
- dynamic 类型（UBO_DYNAMIC / SSBO_DYNAMIC）允许 bind 时传入 offset，减少 descriptor set 数量 [HEUR]。
- `updateAfterBind` 需要在 layout 中设置 `VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT` 并启用 feature [SPEC]。
- image descriptor 中的 `imageLayout` 必须与使用时的 image layout 一致 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU update | descriptor set | `vkUpdateDescriptorSets`（CPU 侧） | 下一帧 `vkCmdBindDescriptorSets` |
| 资源 producer（copy/compute/graphics） | buffer / image | 对应 access/layout barrier | shader 通过 descriptor 读取 |
| previous frame | descriptor set 引用的 per-frame 资源 | fence 保证资源未被 GPU 使用 | CPU 更新 descriptor / 资源 reuse |

必须说明：

- `vkUpdateDescriptorSets` 在 CPU 侧更新 descriptor，更新后需保证 GPU 不再读取旧 descriptor 引用的资源；通常通过 frame fence 或 per-frame descriptor set 隔离 [SPEC]。
- 对 dynamic offset，descriptor 中的 buffer offset 为 0，range 为单个 slot 的 aligned size；bind 时传入实际 offset [SPEC]。
- 更新 image descriptor 时，image layout 必须与实际使用 layout 匹配；常见错误是写 `SHADER_READ_ONLY_OPTIMAL` 但 image 当前为 `GENERAL` [TOOL]。

---

## 8. 实现步骤

1. **解析 shader reflection**：获取每个 set/binding 的 `descriptorType`、`descriptorCount`、`stageFlags` [ENGINE]。
2. **创建 descriptor set layout**：填写 `VkDescriptorSetLayoutBinding` 数组，调用 `vkCreateDescriptorSetLayout`；若需 update-after-bind，使用 `VkDescriptorSetLayoutBindingFlagsCreateInfo` [SPEC]。
3. **评估 descriptor 数量**：按 frame-in-flight * per-frame sets + per-material sets + per-object sets 估算 pool size。
4. **创建 descriptor pool**：填写 `VkDescriptorPoolCreateInfo`，`maxSets` 和 `pPoolSizes` 按类型统计；若需 free individual set，加 `VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT` [SPEC]。
5. **分配 descriptor set**：填写 `VkDescriptorSetAllocateInfo`，调用 `vkAllocateDescriptorSets` [SPEC]。
6. **准备 buffer info**：对每个 UBO/SSBO binding，填写 `VkDescriptorBufferInfo`（buffer、offset、range），offset 和 range 需满足对应 alignment [SPEC]。
7. **准备 image info**：对每个 image binding，填写 `VkDescriptorImageInfo`（sampler、imageView、imageLayout），layout 与 shader 使用一致 [SPEC]。
8. **更新 descriptor set**：构造 `VkWriteDescriptorSet` 数组，调用 `vkUpdateDescriptorSets` [SPEC]。
9. **绑定 descriptor set**：录制 command buffer 时 `vkCmdBindDescriptorSets`；dynamic offset 类型传入 `pDynamicOffsets`，顺序与 layout binding 顺序一致 [SPEC]。
10. **生命周期管理**：per-frame descriptor set 在 frame fence 后更新；per-material set 在材质加载/卸载时创建/销毁。
11. **Pool 耗尽处理**：监控 `vkAllocateDescriptorSets` 返回值；耗尽时创建新 pool 或增大初始容量 [ENGINE]。
12. **接入 resize / recreate**：若 descriptor 引用的 swapchain image view，recreate 后重新 update descriptor；否则通常不需要重建。
13. **接入销毁路径**：按 `descriptor set（若 individually freed）→ descriptor pool → descriptor set layout` 顺序销毁 [ENGINE]。

---

## 9. Android 注意点

- descriptor set layout 和 pool 创建不依赖 surface，但 descriptor 引用的 image/buffer 资源受 surface 生命周期影响；`surfaceDestroyed` 后不得再使用引用 swapchain image 的 descriptor [ANDROID]。
- swapchain recreate 后，若 descriptor set 引用了 swapchain image view 或 per-frame buffer，必须重新 `vkUpdateDescriptorSets` [ANDROID]。
- pause / resume 期间 descriptor pool 可保留；但引用已释放资源的 descriptor 必须在恢复后重新更新。
- 移动端 descriptor pool 容量不宜过大，避免内存浪费；建议按实际 usage 统计并预留 20% 余量 [ANDROID]。
- AGI / logcat 验证：检查 `vkUpdateDescriptorSets` 参数、`vkCmdBindDescriptorSets` 的 `firstSet` 与 layout 一致。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkDescriptorSetLayoutCreateInfo-*`、`VUID-VkDescriptorPoolCreateInfo-*`、`VUID-vkUpdateDescriptorSets-*`、`VUID-vkCmdBindDescriptorSets-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：Pipeline State → Descriptor Sets 中可见 set/binding、资源 handle、offset、range、layout 正确 [TOOL]。
- [ ] 截图 / 数值验证：shader 读取的 UBO/texture/SSBO 数据正确反映在渲染结果中。
- [ ] logcat（Android）：无 validation error；可输出 descriptor pool 使用量和剩余量。
- [ ] 性能指标：
  - `vkUpdateDescriptorSets` CPU 耗时在预期范围；
  - 无 redundant descriptor set bind；
  - AGI 中 descriptor cache miss 不异常 [TOOL]。
- [ ] resize / pause / resume 后 descriptor 仍指向有效资源。
- [ ] 多帧运行稳定，无 descriptor 悬垂或 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Pool size 不足**：`vkAllocateDescriptorSets` 返回 `VK_ERROR_OUT_OF_POOL_MEMORY` [SPEC]。
2. **Layout 与 shader 不匹配**：binding 顺序、type、stage 不一致，draw 时报 `VUID-vkCmdDraw-*-None-02721` [TOOL]。
3. **Dynamic offset 顺序错误**：`pDynamicOffsets` 顺序未按 layout 中 dynamic binding 顺序排列，导致偏移错位 [SPEC]。
4. **Descriptor 引用了已销毁资源**：buffer/image 已销毁但 descriptor 未更新，触发 validation error 或 device lost [TOOL]。
5. **Image layout 不匹配**：descriptor 中 `imageLayout` 与实际 image layout 不同 [SPEC]。
6. **忘记设置 descriptorCount 为数组大小**：将数组 binding 的 `descriptorCount` 填为 1，导致 shader 数组越界 [SPEC]。
7. **Update-after-bind 未启用 feature**：layout 中设置 flag 但 device creation 未启用，创建失败 [SPEC]。
8. **Android recreate 后 descriptor 悬垂**：swapchain image view 重建后未重新 update descriptor [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- Shader reflection 输出。
- `VkDescriptorSetLayoutCreateInfo`、`VkDescriptorPoolCreateInfo` 参数。
- `vkUpdateDescriptorSets` 的 write 数组内容。
- `vkCmdBindDescriptorSets` 的 `firstSet`、`dynamicOffsetCount`、`pDynamicOffsets`。
- Validation Layer 完整报错。
- Android lifecycle 日志。

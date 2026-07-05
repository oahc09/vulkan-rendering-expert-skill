# API Card: Sampled Image + Sampler Descriptor

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorImageInfo`（`COMBINED_IMAGE_SAMPLER` / `SAMPLED_IMAGE` / `SAMPLER`） |
| 常用 API | `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

Sampled image descriptor 将 `VkImageView` 与 `VkSampler` 绑定到 shader 的 sample 接口，是纹理采样在 Vulkan 中的资源桥梁。[SPEC]

---

## 2. 所属对象链路

```text
VkImage
→ VkImageView（指定 format / range / aspect）
→ VkSampler（filter / address mode / mip / anisotropy）
→ VkDescriptorImageInfo
→ vkUpdateDescriptorSets（COMBINED_IMAGE_SAMPLER / SAMPLED_IMAGE + SAMPLER）
→ vkCmdBindDescriptorSets
→ Shader Sample
```

### 上游依赖

- 已创建的 `VkImageView`，其 image 已 transition 到 `SHADER_READ_ONLY_OPTIMAL`（或 `DEPTH_STENCIL_READ_ONLY_OPTIMAL`）。[SPEC]
- 已创建的 `VkSampler`。[SPEC]
- Descriptor set layout 中声明了 `COMBINED_IMAGE_SAMPLER` 或 `SAMPLED_IMAGE` + `SAMPLER`。[SPEC]

### 下游影响

- Shader 通过 `texture()` / `sampler2D` 等接口读取纹理数据。
- Sampler 参数决定过滤、寻址、mipmap 选择等行为。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDescriptorImageInfo`
- `VkImageView`
- `VkSampler`
- `VkWriteDescriptorSet`

### 常用 API

| API | 作用 |
|---|---|
| `vkUpdateDescriptorSets` | 将 image view 与 sampler 写入 descriptor set。[SPEC] |
| `vkCmdBindDescriptorSets` | 在 command buffer 中绑定 descriptor set。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_descriptor_indexing` / Vulkan 1.2 支持 bindless texture array。
- `VK_KHR_sampler_ycbcr_conversion` 用于视频/相机 YCbCr 采样。

---

## 4. 标准使用流程

```text
创建 image 并 transition 到 SHADER_READ_ONLY_OPTIMAL
→ 创建 VkImageView
→ 创建 VkSampler
→ 分配 descriptor set
→ 构造 VkDescriptorImageInfo（imageView / sampler / imageLayout）
→ 构造 VkWriteDescriptorSet（descriptorType = COMBINED_IMAGE_SAMPLER 或 SAMPLED_IMAGE）
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader 采样
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `imageView` | 必须与 shader 期望的 dimensionality、format 兼容。[SPEC] | 用 2D view 绑定到 2DARRAY shader 声明。[TOOL] |
| `sampler` | COMBINED_IMAGE_SAMPLER 时必填；SAMPLED_IMAGE 时可选。[SPEC] | SAMPLED_IMAGE 仍填 sampler 或 COMBINED 漏填 sampler。[TOOL] |
| `imageLayout` | 采样时 image 必须处于 `SHADER_READ_ONLY_OPTIMAL` 等合法 layout。[SPEC] | layout 仍是 COLOR_ATTACHMENT_OPTIMAL。[TOOL] |
| `descriptorType` | `COMBINED_IMAGE_SAMPLER` / `SAMPLED_IMAGE` / `SAMPLER` 需与 layout 声明一致。[SPEC] | layout 是 SAMPLER 但写成了 SAMPLED_IMAGE。[TOOL] |
| `dstBinding` / `dstArrayElement` | 与 shader binding 和 array index 对应。[SPEC] | binding 或数组索引错位。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Image 的 usage 是否包含 `VK_IMAGE_USAGE_SAMPLED_BIT`？
- [ ] Sampler 参数是否符合 shader 预期？
- [ ] Descriptor set layout 的 type 与更新操作是否一致？

### 使用阶段

- [ ] Image layout 是否已 transition 到 `SHADER_READ_ONLY_OPTIMAL`？
- [ ] 采样前是否已绑定正确的 descriptor set？
- [ ] Shader binding 是否与 descriptor 更新一致？

### 销毁阶段

- [ ] 更新 descriptor 后，image view 与 sampler 仍需保持有效直到 GPU 完成。[SPEC]

---

## 7. 高频错误

1. Image layout 未 transition 到 `SHADER_READ_ONLY_OPTIMAL`。[TOOL]
2. `COMBINED_IMAGE_SAMPLER` 与 separate `SAMPLED_IMAGE` + `SAMPLER` 混用，导致 layout 不匹配。[TOOL]
3. Image view format 与 shader 期望 format 不一致。[TOOL]
4. Sampler 的 `maxLod` 小于 image 的 mip 数量，导致远处采样黑边。[TOOL]
5. 更新 descriptor 后提前销毁 image view 或 sampler。[TOOL]
6. 对 depth/stencil image sample 时未使用 `DEPTH_STENCIL_READ_ONLY_OPTIMAL`。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkWriteDescriptorSet-*`：descriptor type、image view、sampler 合法性。
- `VUID-vkCmdDraw-*-imageLayout-*`：采样时 image layout 检查。
- `VUID-vkUpdateDescriptorSets-None-03047`：image view 与 descriptor type 兼容。

### RenderDoc / AGI

- 查看当前绑定的 texture 与 sampler 状态。
- 检查 image 内容、layout、mipmap 是否正确。
- 查看 shader 采样结果。

### 日志 / 代码检查

- 检查 `VkDescriptorImageInfo` 的字段。
- 检查 descriptor set layout binding 与 shader 声明。
- 检查 image layout transition 路径。

---

## 9. 生命周期风险

### 创建时机

- 材质加载或资源初始化阶段创建 image view 与 sampler。[ENGINE]

### 使用时机

- 渲染时通过 descriptor set 绑定到 pipeline。[SPEC]

### 销毁时机

- 确认 GPU 不再采样该 image 后销毁 image view / sampler。[SPEC]

### in-flight 风险

- Descriptor set 引用 image view 与 sampler 后，这些对象在 fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 更新 descriptor set 通常不需要 fence，但修改被 GPU 使用的 descriptor set 需要谨慎。[SPEC]

### GPU-GPU 同步

- Image 从 producer（如 render pass）转为 sampled image 需要 image memory barrier。[SPEC]

### 资源访问同步

- Sampled image 必须处于 `SHADER_READ_ONLY_OPTIMAL` 或 `DEPTH_STENCIL_READ_ONLY_OPTIMAL`。[SPEC]
- 若 image 刚被写入，需 barrier 保证 consumer shader 可见。

---

## 11. Android 注意点

- 移动端纹理采样带宽高，尽量使用 mipmapped texture 与合理的 sampler LOD。[ANDROID][ENGINE]
- YCbCr 视频/相机纹理需要 `VK_KHR_sampler_ycbcr_conversion` 与专用 sampler。[ANDROID]
- 部分低端设备对 anisotropic filtering 支持有限，需查询 feature。[ANDROID]
- AGI 可分析纹理采样 cache miss 与带宽。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Descriptor 更新本身开销较低，但大量材质变体会增加管理复杂度。[ENGINE]
- 使用 descriptor array 或 bindless 可减少更新频率。[ENGINE]

### GPU 侧

- Sampler filter（linear vs nearest）、mip、anisotropy 影响采样质量与性能。[ENGINE]
- 未 mipmapped 的纹理在缩小采样时会造成 cache thrash。[ENGINE]

### 移动端

- 避免高精度纹理过度采样；使用 ASTC/ETC2 压缩格式。[ANDROID]
- 限制各向异性过滤倍数；Adreno/Mali 对高倍 AF 敏感。[ANDROID]

---

## 13. 专家经验

**经验**：
如果场景中大量材质使用相同 sampler 参数，优先使用 `COMBINED_IMAGE_SAMPLER` 减少 descriptor 数量；如果需要灵活组合 image 与 sampler（例如不同 filter 模式复用同一 texture），则使用 separate `SAMPLED_IMAGE` + `SAMPLER`。无论哪种方式，都要保证 `imageLayout` 与当前 image 实际 layout 一致，否则验证层会立刻报错。

**适用条件**：
所有需要纹理采样的渲染。

**不适用情况**：
纯 compute 的 storage image 读取（用 storage image descriptor）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_set_layout.md`
- `descriptor_update.md`
- `descriptor_pool.md`
- `uniform_buffer_descriptor.md`
- `storage_buffer_image_descriptor.md`
- `../04_buffer_image_memory/image_view.md`
- `../04_buffer_image_memory/sampler.md`
- `../04_buffer_image_memory/image_layout.md`
- `../06_pipeline/shader_module.md`

---

## 15. 需要回查官方文档的情况

1. 具体 format 是否支持 `SAMPLED_BIT` 及采样时合法 layout。
2. `COMBINED_IMAGE_SAMPLER` 与 separate image/sampler 在 descriptor count 上的差异。
3. YCbCr conversion sampler 的创建与使用规则。
4. Bindless descriptor array 的动态索引限制。
5. 不同驱动对 sampler anisotropy 的最大值与性能影响。

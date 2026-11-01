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
- `VUID-vkUpdateDescriptorSets-None-03047`：未设置 update-after-bind / update-unused-while-pending 相应标志的 binding，不得更新被 pending command buffer 使用的目标 set；具体例外还须满足相关 feature 与限制。

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

- 更新 descriptor 前确认目标 binding 不被 pending 工作使用，或严格满足已启用的 update-after-bind 等例外规则；不能仅凭 CPU 写入快速就覆盖在途使用。[SPEC]

### GPU-GPU 同步

- Image 从 producer（如 render pass）转为 sampled image 需要 image memory barrier。[SPEC]

### 资源访问同步

- Sampled image 必须处于该 descriptor type 允许、且与实际访问时一致的 layout；常见为 `SHADER_READ_ONLY_OPTIMAL`，也可以是 `GENERAL` 或满足条件的其他只读 layout，不能限定只有两个枚举。[SPEC]
- 若 image 刚被写入，需 barrier 保证 consumer shader 可见。

---

## 11. Android 注意点

- 移动端纹理采样带宽高，尽量使用 mipmapped texture 与合理的 sampler LOD。[ANDROID][ENGINE]
- YCbCr 视频/相机纹理需要 Vulkan 1.1 核心或 `VK_KHR_sampler_ycbcr_conversion` 对应能力，并按 conversion 与外部格式规则创建 sampler/view。[ANDROID]
- 部分低端设备对 anisotropic filtering 支持有限，需查询 feature。[ANDROID]
- AGI 可分析纹理采样 cache miss 与带宽。[TOOL]

---


<a id="android-media-ycbcr"></a>
### Android 媒体 externalFormat / YCbCr 采样

前提是[媒体帧合同](../04_buffer_image_memory/external_resource_interop.md#android-media-frame-contract)已满足：有效 lease、producer readiness、AHB import、队列 ownership 与实际采样 layout。Descriptor 只描述访问，不取得帧所有权、不等待 acquire FD、不转换颜色空间。[SPEC][ENGINE]

| 分支 | 必查与创建约束 |
|---|---|
| 普通 RGB VkFormat | 从 AHB 查询得到实际等价格式，按该 format/tiling/usage 查询支持；不可用 external format 的 formatFeatures 替代普通格式查询。无 YCbCr conversion 时沿普通 sampler 路径。 |
| 普通多平面 YCbCr | 查询并启用 `samplerYcbcrConversion`（核心 1.1 或扩展路径）；format 必须满足 conversion 规则。COLOR aspect conversion 不是把每个 plane 当 RGBA。 |
| 非零 externalFormat | 仅使用 AHB 查询返回值；image/conversion 的 VkFormat 为 `VK_FORMAT_UNDEFINED`，匹配 `VkExternalFormatANDROID`；按 external format 能力而非猜测 RGBA usage。默认采样路径不能推导任意 storage/attachment 支持。 |

转换参数包括 model、range、components、x/y chroma offset、chromaFilter、forceExplicitReconstruction。AHB 的 suggestedYcbcrModel/Range/ChromaOffset 是缺乏更可靠输入信息时的建议，并非所有帧的颜色认证；以可信 producer 元数据和格式限制核对。External conversion 的 components 字段被忽略；普通格式则按规范 swizzle。检查 MIDPOINT/COSITED、linear chroma 与 separate reconstruction filter 能力，不能无条件 linear 或自行改 offset。[SPEC]

传统 descriptor-set 路径将定义一致的 conversion 关联 sampler 与 image view，view components 使用 identity swizzle；使用 `COMBINED_IMAGE_SAMPLER` 和 layout 中的 immutable sampler；不能直接换为普通 separate image+sampler。Sampler conversion 的 address modes、anisotropy、unnormalized coordinates、过滤组合须按规范约束（通常 clamp-to-edge、禁用 anisotropy、normalized coordinates）；不照搬材质 repeat/AF 配方。普通 format 的 combined descriptor 倍数与 external format 的预算规则见本卡末尾既有计数段，不能恒按 1 分配。[SPEC]

每帧 crop/旋转/镜像在采样坐标合同处理，timestamp/source generation 与 descriptor 版本一起追踪；不是通过 image layout 修正方向或颜色。元数据/格式/conversion 改变时重建所需 sampler/layout/pipeline 绑定，并退休旧在途 descriptor，不能覆盖 pending 使用。YCbCr→RGB 后还需独立的 transfer/primaries/工作空间及输出合同，不能把 conversion 结果自动当线性 sRGB 或 HDR 已完成。[ENGINE]

来源：[AHB format properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkAndroidHardwareBufferFormatPropertiesANDROID.html)、[conversion 参数](https://docs.vulkan.org/refpages/latest/refpages/source/VkSamplerYcbcrConversionCreateInfo.html)、[immutable conversion 绑定](https://docs.vulkan.org/refpages/latest/refpages/source/VkSamplerYcbcrConversionInfo.html)、[sampler 限制](https://docs.vulkan.org/refpages/latest/refpages/source/VkSamplerCreateInfo.html)。

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
如果场景中大量材质使用相同 sampler 参数，优先使用 `COMBINED_IMAGE_SAMPLER` 减少 descriptor 数量；如果普通非 YCbCr-conversion 纹理需要灵活组合 image 与 sampler（例如不同 filter 模式复用同一 texture），可评估 separate `SAMPLED_IMAGE` + `SAMPLER`；媒体 conversion 路径按本卡专节约束。无论哪种方式，都要保证 `imageLayout` 与当前 image 实际 layout 一致，否则验证层会立刻报错。

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


## AHB / YCbCr 的 descriptor 计数（2026-10-17）

普通 sampler YCbCr conversion 通过匹配 format/tiling/usage 的 `vkGetPhysicalDeviceImageFormatProperties2` 查询链取得 `VkSamplerYcbcrConversionImageFormatProperties::combinedImageSamplerDescriptorCount`，不能假设恒为 1；传统 pool 的 combined descriptor 容量预算也需计入该倍数。[SPEC]

Android `AHardwareBuffer` 先用 `vkGetAndroidHardwareBufferPropertiesANDROID` 及 format properties 查询实际格式/外部格式，不等于取得普通 Vulkan format 的 YCbCr 计数。Android external format 在 descriptor buffer 的写入大小按 `combinedImageSamplerDescriptorSize × VkPhysicalDeviceMaintenance6Properties::maxCombinedImageSamplerDescriptorCount`；普通非 external-format 按 format 查询计数。heap 的 resource writer 也区分这两个计数，并以具体类型写入大小相乘。heap sampler 的 `samplerYcbcrConversionCount` 是另一项，不要混为资源 image 的计数。[SPEC]

同时检查 conversion feature、immutable sampler / image view conversion 一致性、external memory import、queue ownership 和 image layout；只有 descriptor 容量正确不能证明相机/视频路径正确。

来源：[YCbCr format properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkSamplerYcbcrConversionImageFormatProperties.html)、[AHB properties](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetAndroidHardwareBufferPropertiesANDROID.html)、[buffer writer](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDescriptorEXT.html)、[heap writer](https://docs.vulkan.org/refpages/latest/refpages/source/vkWriteResourceDescriptorsEXT.html)。


[描述符写入约束](https://docs.vulkan.org/refpages/latest/refpages/source/vkUpdateDescriptorSets.html) · [采样图像 layout 约束](https://docs.vulkan.org/refpages/latest/refpages/source/VkWriteDescriptorSet.html)。

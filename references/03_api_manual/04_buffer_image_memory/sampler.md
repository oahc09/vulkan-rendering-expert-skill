# API Card: VkSampler

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | `VkSampler` |
| 常用 API | `vkCreateSampler` / `vkDestroySampler` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkSampler` 封装了纹理采样的状态，包括过滤方式、寻址模式、mipmap、各向异性等，决定 shader 如何从 image 中读取像素。[SPEC]

---

## 2. 所属对象链路

```text
VkSamplerCreateInfo
→ vkCreateSampler
→ VkSampler
→ VkDescriptorImageInfo（COMBINED_IMAGE_SAMPLER / SAMPLER）
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader texture()
```

### 上游依赖

- 已创建的逻辑设备。[SPEC]
- 了解目标 texture 的 dimensionality、mip 层级与使用场景。

### 下游影响

- 决定纹理采样的视觉质量与性能。
- 与 image view 一起构成 sampled image descriptor。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSampler`
- `VkSamplerCreateInfo`
- `VkSamplerYcbcrConversionInfo`（YCbCr 场景）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateSampler` | 创建 sampler。[SPEC] |
| `vkDestroySampler` | 销毁 sampler。[SPEC] |
| `vkCreateSamplerYcbcrConversion` | 创建 YCbCr conversion（视频/相机纹理）。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_sampler_ycbcr_conversion` / Vulkan 1.1 用于 YCbCr。
- `VK_EXT_custom_border_color` 用于自定义 border color。

---

## 4. 标准使用流程

```text
确定过滤方式（mag/min/mipmap）
→ 确定寻址模式（repeat / clamp / mirror）
→ 确定是否需要 anisotropy / compare / border color
→ 构造 VkSamplerCreateInfo
→ vkCreateSampler
→ 写入 COMBINED_IMAGE_SAMPLER 或 SAMPLER descriptor
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `magFilter` / `minFilter` | 放大/缩小过滤：nearest / linear。[SPEC] | 应该用 linear 时用了 nearest。[TOOL] |
| `mipmapMode` | Mipmap 选择：nearest / linear。[SPEC] | 未启用 mipmap 却设为 linear。[TOOL] |
| `addressModeU/V/W` | 各维度的寻址模式。[SPEC] | 需要 clamp 时用了 repeat，导致采样到边缘外像素。[TOOL] |
| `anisotropyEnable` / `maxAnisotropy` | 各向异性过滤；需启用 feature。[SPEC] | 未启用 `samplerAnisotropy` feature。[TOOL] |
| `compareEnable` / `compareOp` | 用于 shadow map PCF。[SPEC] | 对非 depth texture 启用 compare。[TOOL] |
| `minLod` / `maxLod` | 限制 mipmap 层级。[SPEC] | `maxLod` 过小导致远处黑边。[TOOL] |
| `borderColor` | `CLAMP_TO_BORDER` 时使用的颜色。[SPEC] | 需要透明 border 时用了 opaque black。[TOOL] |
| `unnormalizedCoordinates` | 是否使用像素坐标而非 [0,1]。[SPEC] | 与 shader 坐标系不一致。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否查询并启用了 `samplerAnisotropy` feature？
- [ ] Mipmap 模式是否与 image 的 mip 层级匹配？
- [ ] 寻址模式是否符合纹理内容与 shader 预期？

### 使用阶段

- [ ] Sampler 是否与 image view 一起正确写入 descriptor？
- [ ] Shader 中的 sampler 类型是否与创建参数匹配？

### 销毁阶段

- [ ] 是否等待 GPU 不再采样后销毁？[SPEC]

---

## 7. 高频错误

1. 未启用 `samplerAnisotropy` 却设置 `anisotropyEnable = VK_TRUE`。[TOOL]
2. `maxLod` 小于 image 的 mip 数量，导致某些层级无法采样。[TOOL]
3. Shadow map 未启用 `compareEnable` 或 compareOp 错误。[TOOL]
4. `unnormalizedCoordinates` 与 shader 期望不一致。[TOOL]
5. 对非 mipmapped image 使用 `LINEAR` mipmap mode。[TOOL]
6. 销毁 sampler 时它仍被 in-flight descriptor set 引用。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkSamplerCreateInfo-*`：feature、字段组合合法性。
- `VUID-vkUpdateDescriptorSets-*`：sampler 与 descriptor type 兼容。

### RenderDoc / AGI

- 查看当前绑定的 sampler 参数。
- 检查 texture 采样结果与 mip 选择。

### 日志 / 代码检查

- 检查 `VkSamplerCreateInfo` 各字段。
- 检查 feature 启用。
- 检查 descriptor 更新。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建常用 sampler（nearest、linear、anisotropic、shadow）。[ENGINE]

### 使用时机

- 渲染时通过 descriptor set 绑定到 shader。[SPEC]

### 销毁时机

- 确认 GPU 不再使用后销毁。[SPEC]

### in-flight 风险

- Sampler 被 descriptor set 引用后，fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Sampler 创建本身不需要 fence；销毁需要等待 GPU 完成。[SPEC]

### GPU-GPU 同步

- 无；sampler 是只读状态对象。

### 资源访问同步

- 无。

---

## 11. Android 注意点

- 移动端 `maxSamplerAnisotropy` 通常较低，且高倍 AF 性能代价大。[ANDROID]
- YCbCr 相机/视频纹理需要专用 conversion sampler。[ANDROID]
- 使用 ASTC/ETC2 压缩纹理时，linear filtering 可能与 block 边界产生 artifact，需注意 border/mip。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Sampler 对象数量通常很少，创建开销低。[ENGINE]

### GPU 侧

- Anisotropic filtering、trilinear filtering 增加采样次数与带宽。[ENGINE]
- Nearest 过滤最快但质量差；linear 是常见折中。[HEUR]

### 移动端

- 限制 anisotropy 倍数，优先使用 bilinear + mip。[ANDROID]
- 避免在 fragment shader 中过度依赖 dependent texture read。[ENGINE]

---

## 13. 专家经验

**经验**：
在项目中维护一组“标准 sampler”：nearest repeat、linear repeat、linear clamp、anisotropic clamp、shadow compare。不要为每个 texture 都创建独立 sampler，因为 sampler 状态是绑定时的瓶颈之一。对 shadow map，务必启用 compare 并使用合适的 compareOp；对 UI 纹理，通常使用 linear clamp 或 nearest clamp。

**适用条件**：
所有需要纹理采样的场景。

**不适用情况**：
不使用 sampled image 的渲染（如纯 compute storage image）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `image_view.md`
- `image_layout.md`
- `../05_descriptor/sampled_image_descriptor.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../06_pipeline/shader_module.md`

---

## 15. 需要回查官方文档的情况

1. 设备对 `samplerAnisotropy`、`samplerFilterMinmax`、`samplerYcbcrConversion` 等 feature 的支持。
2. YCbCr conversion sampler 的创建与使用细节。
3. `unnormalizedCoordinates` 与 shader 坐标系的交互。
4. 自定义 border color 扩展的限制。
5. 不同驱动对 compare sampler 与 shadow map 的优化。

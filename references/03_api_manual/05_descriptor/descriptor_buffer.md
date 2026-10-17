# API Card: Descriptor Buffer (`VK_EXT_descriptor_buffer`)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkBuffer` |
| 常用 API | `vkGetDescriptorEXT` |
| 适用平台 | 通用，需运行时查询 |
| 来源等级 | `[SPEC] [ENGINE] [TOOL]` |
| 适用 Vulkan 版本 | `VK_EXT_descriptor_buffer` 可选扩展 |

- 模块：`03_api_manual`；类别：Descriptor 链；来源：`[SPEC] [ENGINE] [TOOL]`
- 核验日期：2026-10-17。此扩展是可选设备能力；官方已标记被 `VK_EXT_descriptor_heap` 取代，不代表所有驱动提供 heap，也不要求现有项目立即迁移。
- 关联：[Descriptor Heap](descriptor_heap.md)、[传统 Descriptor Set](descriptor_set.md)。

## 1. 一句话定位

把实现生成的 descriptor 字节放入应用管理的 buffer；仍使用 set layout / pipeline layout 确定 shader 绑定接口。它不是允许 shader 任意构造 descriptor 位模式的标准。[SPEC]

## 2. 所属对象链路

`能力查询与启用 → descriptor-buffer set layout → 查询 layout size/binding offset → buffer/device address → host 生成 descriptor → 写入或复制 → 可见性 → 绑定及 shader 访问 → 完成后回收`。

## 3. 核心对象与 API

- `VkPhysicalDeviceDescriptorBufferFeaturesEXT`：查询并显式启用 `descriptorBuffer`；其他 feature 按实际使用启用。
- `VkPhysicalDeviceDescriptorBufferPropertiesEXT`：大小、对齐、绑定数与范围限制。
- `vkGetDescriptorSetLayoutSizeEXT` / `vkGetDescriptorSetLayoutBindingOffsetEXT`：查询实际布局，不能用 binding 编号乘固定大小代替。
- `vkGetDescriptorEXT`：host 命令，向应用提供的 CPU 可写地址生成 descriptor 数据。
- `vkCmdBindDescriptorBuffersEXT` / `vkCmdSetDescriptorBufferOffsetsEXT`：绑定 buffer 地址、选择 set 区域。它们是 CPU 录制的命令，不是 shader 可调用函数。
- `vkCmdBindDescriptorBufferEmbeddedSamplersEXT`：仅用于相应 embedded immutable sampler layout。

## 4. 标准使用流程

1. 枚举扩展并检查其版本依赖；查询 features/properties，创建 device 时启用所需 feature 与扩展。查询为 true 不等于已启用。
2. 使用 `VK_DESCRIPTOR_SET_LAYOUT_CREATE_DESCRIPTOR_BUFFER_BIT_EXT` 创建 set layout，建立匹配的 pipeline layout；相应 pipeline 使用 `VK_PIPELINE_CREATE_DESCRIPTOR_BUFFER_BIT_EXT`。不存在本路径通用必需的“合并 set pNext”结构。
3. 查询 set 大小与 binding 偏移，为每个 set 分配按 `descriptorBufferOffsetAlignment` 对齐的起始位置。
4. 创建带资源或 sampler descriptor usage 和 `VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT` 的 buffer，按 device address 要求分配内存。复制路径还需要相应 transfer usage。
5. 通过 `vkGetDescriptorEXT` 生成数据到已映射内存或 staging 区；依据具体类型、robustness、combined sampler 特例选择尺寸与排布。
6. 完成 host flush 或 GPU copy 及所需依赖后绑定地址和 set offset，录制 draw/dispatch。
7. 保持 descriptor 字节与引用资源存活到最后一次 GPU 访问完成，再复用或销毁。

## 5. 关键字段

| 字段 | 用途 / 不可混淆项 |
|---|---|
| `descriptorBufferOffsetAlignment` | descriptor buffer 地址和 set offset 的相关对齐要求；不存在 `descriptorSetOffsetAlignment` 字段 |
| `uniformBufferDescriptorSize` / `robustUniformBufferDescriptorSize` 等 | 按具体 descriptor 类型及启用的 robustness 选择；不存在统一 `descriptorSize[type]` Vulkan 字段 |
| `combinedImageSamplerDescriptorSingleArray` | false 时 combined 数组需按规范拆成 image 数组和 sampler 数组，不能直接逐项拼接 |
| `maxDescriptorBufferBindings` / resource、sampler 上限 | 同时绑定数量；还必须检查最大范围与地址空间限制 |
| `allowSamplerImageViewPostSubmitCreation` | 限制用于生成 descriptor 的 image view/sampler 相对提交的创建时机 |
| `bufferlessPushDescriptors` | 是 property；push descriptor 交互还需独立 feature 与 usage 检查 |

字段定义见 [properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceDescriptorBufferPropertiesEXT.html)。[SPEC]

## 6. 正确性检查点

- [ ] 支持扩展、满足依赖、feature 已启用、函数指针可用分别有证据。
- [ ] layout flag、pipeline flag、绑定方式匹配。
- [ ] set size、binding offset、具体类型尺寸、set 起点对齐分开计算。
- [ ] 写入覆盖区域及数组 stride 没有溢出；combined YCbCr 按额外规则计算。
- [ ] descriptor 引用的 image view、sampler、buffer 与内存仍有效。
- [ ] 没有覆盖仍被 GPU 读取的字节；资源自身的 layout/同步独立正确。

## 7. 高频错误

- 把 buffer device address 当作 GPU 自行生成 opaque descriptor 的许可；合法已生成字节可以复制，但格式不是公开 ABI。
- 把 descriptor indexing 当作 pipeline stage。`VK_PIPELINE_STAGE_2_DESCRIPTOR_INDEXING_BIT` 不是 Vulkan 枚举，不能用于 barrier。
- 误把 `vkCmdSetDescriptorBufferOffsetsEXT` 当 GPU indirect 可调用命令。
- 无视 descriptor set 与 descriptor buffer 绑定状态互扰；混用前检查对应命令的 valid usage 与状态失效规则。
- 将 `VkDescriptorAddressInfoEXT` 用于 image view；image descriptor 使用 `VkDescriptorImageInfo`，buffer 类 descriptor 才使用地址信息。

## 8. Debug 检查路径

记录首次 VUID、实际启用 features、layout/binding 查询结果、生成尺寸、写入区间、每次绑定的地址及偏移、提交完成标记。工具是否解码本扩展须按确切版本验证，见 [工具边界](../../04_debug_playbooks/tool_usage.md)。没有 validation 报告不能证明 descriptor 内容、shader 索引或画面正确。

## 9. 生命周期风险

使用 frame/ring 分区是常见工程策略，不是规范强制每帧独立 buffer。回收以最后使用的 fence/timeline 完成为准。重新创建 image view 后重建引用它的 descriptor；复制 descriptor 字节不会延长资源生命周期。[ENGINE]

## 10. 同步风险

- 生成：`vkGetDescriptorEXT` 是 host 数据生成，不是 transfer/shader 执行，也不提交 GPU barrier。
- Host 写：host-visible 内存不必 coherent；non-coherent 映射内存按 `nonCoherentAtomSize` 处理 flush 范围。提交前完成的 host 写由 queue submission 提供相应可见性，不需要额外 descriptor-read barrier；禁止与 in-flight 读取重叠。coherent 只解决缓存可见性，不解决覆盖竞态。
- GPU copy：复制已合法生成的字节时，源阶段/访问对应实际 producer。例如 copy 使用 `VK_PIPELINE_STAGE_2_COPY_BIT` + `VK_ACCESS_2_TRANSFER_WRITE_BIT`。合法 shader 字节复制则使用对应 shader stage + `VK_ACCESS_2_SHADER_WRITE_BIT`；不得据此假定能生成任意 descriptor。
- 读取：目标访问为 `VK_ACCESS_2_DESCRIPTOR_BUFFER_READ_BIT_EXT`，目标阶段覆盖实际读取 descriptor 的 shader stages，例如 fragment/compute；保守可用 `VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT`，不是不存在的 descriptor-indexing stage。
- 跨 queue 另加 semaphore、必要的 ownership transfer；descriptor 指向的资源读写、image layout 另建依赖，descriptor 字节 barrier 不代替资源 barrier。

依据：[descriptor buffer host/device 写入规则](https://docs.vulkan.org/spec/latest/chapters/descriptorbuffers.html)、[同步与缓存控制](https://docs.vulkan.org/spec/latest/chapters/synchronization.html)。[SPEC]

## 11. Android 注意点

不能从 Android 版本、GPU 商标或 SDK 版本推断扩展支持。普通 YCbCr combined descriptor 的 `vkGetDescriptorEXT::dataSize` 按 `combinedImageSamplerDescriptorSize × combinedImageSamplerDescriptorCount`；Android external-format 特例按 `maxCombinedImageSamplerDescriptorCount`，应检查 maintenance6 对应支持及所用规范版本。不要把普通单 descriptor 大小用于 AHB 视频/相机输入。详见 [采样描述符](sampled_image_descriptor.md) 与 [vkGetDescriptorEXT](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDescriptorEXT.html)。[SPEC]

## 12. 性能注意点

减少 set 分配/更新调用是设计动机，不是性能结论。测量生成、复制、flush、绑定、内存占用和 GPU 时间；比较相同 workload 的传统 set 与 buffer 路径。没有目标设备数据时只能标记假设，不宣称更快或移动端必然更慢。[ENGINE]

## 13. 专家经验

以 typed writer 集中处理合法类型、robustness、对齐和 combined-array 特例。先保留传统 set 可比较路径；添加后端、默认切换、删除旧路径是三个独立决策，见 [架构门槛](../../02_core_mental_model/engine_architecture.md)。[ENGINE]

## 14. 相关 API 卡片

- [Descriptor Heap](descriptor_heap.md)
- [Descriptor Set Layout](descriptor_set_layout.md)
- [Descriptor Indexing](descriptor_indexing.md)
- [Pipeline Layout](../06_pipeline/pipeline_layout.md)

## 15. 需要回查官方文档的情况

核验日期 2026-10-17；latest 页面会变化，实际项目保存使用的 registry/header/spec revision。

- [扩展和依赖、替代状态](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_descriptor_buffer.html)
- [生成尺寸与对象生命期](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDescriptorEXT.html)
- [set offset valid usage](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdSetDescriptorBufferOffsetsEXT.html)
- 遇到 push descriptor、embedded sampler、capture/replay、YCbCr、robustness、跨队列或新驱动时，按对应命令当前 valid usage 回查；本文不保证所有组合受支持。

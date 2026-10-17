# API Card: Descriptor Heap (`VK_EXT_descriptor_heap`)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkBuffer` |
| 常用 API | `vkWriteResourceDescriptorsEXT` |
| 适用平台 | 通用，需运行时查询 |
| 来源等级 | `[SPEC] [ENGINE] [TOOL]` |
| 适用 Vulkan 版本 | `VK_EXT_descriptor_heap` 可选扩展 |

模块：`03_api_manual`；来源：`[SPEC] [ENGINE] [TOOL]`；核验日期：2026-10-17。
这是已发布的可选设备扩展，不能由“新版 SDK”推导目标设备已支持。官方将 descriptor buffer 标为被本扩展取代；既有路径仍需按项目兼容矩阵维护。

## 1. 一句话定位

应用管理 resource/sampler heap 的内存、descriptor 写入及 shader 映射；不是改名的 descriptor set，也不是 D3D12 heap API 的直接移植。[SPEC]

## 2. 所属对象链路

`扩展/依赖 → query features/properties → device 显式启用 → heap buffer/address/reserved range → host 写入 → 可见性 → heap bind → shader mapping/push data → GPU 完成后回收`。

## 3. 核心对象与 API

| API / 结构 | 用途 |
|---|---|
| `VkPhysicalDeviceDescriptorHeapFeaturesEXT` | `descriptorHeap` 与独立的 `descriptorHeapCaptureReplay` 能力 |
| `VkPhysicalDeviceDescriptorHeapPropertiesEXT` | heap、descriptor 的 size/alignment、保留区、上限 |
| `vkGetPhysicalDeviceDescriptorSizeEXT` | 按 descriptor type 查询写入大小 |
| `vkWriteResourceDescriptorsEXT` | 根据 `VkResourceDescriptorInfoEXT` 写 host 地址范围，返回 `VkResult` |
| `vkWriteSamplerDescriptorsEXT` | 从 sampler create info 写 sampler descriptor |
| `vkCmdBindResourceHeapEXT` / `vkCmdBindSamplerHeapEXT` | 通过 `VkBindHeapInfoEXT` 绑定 heap |
| `vkCmdPushDataEXT` / `VkPushDataInfoEXT` | 更新 shader 取用的 push data |
| `VkShaderDescriptorSetAndBindingMappingInfoEXT` | 描述 shader set/binding 到 heap/push data 的映射 |

名称和依赖见 [官方扩展](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_descriptor_heap.html)。不能用 descriptor-buffer 的 bind/offset 函数替代这些命令。[SPEC]

## 4. 标准使用流程

1. 检查扩展及其 dependencies，查询并启用 feature；核对编译 headers、loader、驱动、shader 工具链分别支持。`VK_KHR_shader_untyped_pointers` 必须受支持，但仅使用 binding interface 的应用不必启用它；原生 heap shader 所需能力另查。
2. 查询 heap alignment、最大 heap size、minimum reserved range 和各 descriptor 类别 alignment/size。
3. 创建带 `VK_BUFFER_USAGE_DESCRIPTOR_HEAP_BIT_EXT` 及 device-address 所需 usage 的 buffer；分配内存并划分实现保留区与应用 descriptor 区。
4. 分配稳定 slot，调用 write API 到可写 host range；检查返回值，必要时 staging copy，完成可见性与在途保护。
5. pipeline 使用 `VK_PIPELINE_CREATE_2_DESCRIPTOR_HEAP_BIT_EXT`，提供所需 shader binding mapping；绑定 sampler/resource heaps 并录制 push data 与 draw/dispatch。
6. fence/timeline 证明最后访问完成后才能覆盖 slot、释放 heap 或被引用资源。

## 5. 关键字段

工程上可采用固定 slot，例如同类 slot 的 stride 按该类别最大尺寸和 alignment 向上对齐；混合 resource slot 则以所容纳类别最大要求设计。仅当 shader mapping / 地址运算显式匹配该自定义 stride 时才可采用。原生 `layout(descriptor_heap)` typed arrays 使用相应 advertised descriptor size 作数组 stride，不能只改 allocator padding 而保留原数组寻址。这是应用 allocator 策略，不是 Vulkan 要求的唯一布局。[ENGINE]

`slotAddress = applicationBase + index × slotStride` 只决定相邻 slot 间隔。`vkGetPhysicalDeviceDescriptorSizeEXT(physicalDevice, descriptorType)` 决定类型的写入尺寸 N（可以不是 2 的幂）；只有前 N 字节被写入/读取。普通应用应优先采用 advertised size limits 管理 slot，避免依赖紧密排布；传入 `VkHostAddressRangeEXT::size` 必须足够，不能因 slot 更大就假定所有 padding 被初始化或所有类型写满 slot。YCbCr/subsampled image 可能写相邻多个 descriptor，必须扩展容量并保留连续位置。[SPEC]

[实际写入尺寸](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetPhysicalDeviceDescriptorSizeEXT.html) · [写入 API 与大小规则](https://docs.vulkan.org/refpages/latest/refpages/source/vkWriteResourceDescriptorsEXT.html)

数值例子（条件示例，非固定设备常量）：若某 UBO 类型查询写入大小为 8 字节，而 `bufferDescriptorSize` 为 16 字节，则原生 typed buffer heap 数组的 slot 0/1 起点应相隔 16 字节；每次 writer 只写该类型的前 8 字节。按 8 字节紧排、却让 shader 按 16 字节寻址，会使 index 0 正常而后续索引取错。此类问题的公开复盘见 [案例](../../06_cases/02_descriptor_pipeline/case_descriptor_pipeline.md)。

如果改用显式 binding mapping，`VkDescriptorMappingSourceConstantOffsetEXT::heapArrayStride` 是乘以 shader binding/array index 的字节步长；同一个 16 字节 slot 方案可令该值为 16，并设置正确 `heapOffset`。它不是 writeBytes 参数，也不能自动改变原生 heap 数组 ABI；自定义紧排仅在尺寸、对齐、映射与全部 shader 访问一致时才成立。[官方 mapping 定义](https://docs.vulkan.org/refpages/latest/refpages/source/VkDescriptorMappingSourceConstantOffsetEXT.html)。[SPEC][ENGINE]

## 6. 正确性检查点

- [ ] heap 地址对齐与内部 descriptor 对齐分别满足。
- [ ] `minResourceHeapReservedRange` / sampler 对应保留范围已处理，应用不覆盖实现保留区。
- [ ] shader mapping 的 offset/index stride 与 allocator 一致；不会把 byte offset 当 descriptor index。
- [ ] writer 的类型、合法 create info、实际写入尺寸与 slot 容量匹配。
- [ ] pipeline/shader mapping 使用 heap 路径，不沿用未经转换的 set layout 假设。
- [ ] 所有资源与 descriptor 字节生命周期、同步和队列 ownership 有独立证据。

## 7. 高频错误

只有 header 宏或 SDK 版本就启用；把 `descriptorHeapCaptureReplay` 当作基本 heap feature 自动启用；把 resource/sampler 保留区当普通 slots；忽略多 descriptor YCbCr 写入；认为 heap 内存直接可见就允许 CPU/GPU 同时改同一个 slot。

## 8. Debug 检查路径

记录 heap 范围、保留区、slot 分配、writer 返回值、shader 映射及启用 feature。validation/GPU-AV/capture 是否支持该路径必须查当前工具版本并跑最小用例，不能引用传统 set 支持来担保 heap 支持。见 [工具使用](../../04_debug_playbooks/tool_usage.md)。[TOOL]

## 9. 生命周期风险

descriptor 的字节副本不持有被引用资源；采用延迟销毁/slot generation 可避免索引重用。capture/replay 是额外 feature 与资源创建要求，不等于任意跨设备或跨驱动复制 descriptor 字节。[ENGINE]

## 10. 同步风险

host writer 不自动提供 GPU 依赖。non-coherent host memory 需 flush；GPU copy 后使用实际 producer stage/access。heap 读访问区分 `VK_ACCESS_2_RESOURCE_HEAP_READ_BIT_EXT` 与 `VK_ACCESS_2_SAMPLER_HEAP_READ_BIT_EXT`，目标 stage 覆盖实际 shader 消费者。资源本身的图像 layout 与读写依赖仍独立处理。[SPEC]

## 11. Android 注意点

普通 YCbCr image descriptor 数量使用 `combinedImageSamplerDescriptorCount`；Android external format 按 maintenance6 的 `maxCombinedImageSamplerDescriptorCount` 规则处理。sampler 转换另有 `samplerYcbcrConversionCount`，不能与 image descriptor 数量混为一谈。分别查询对应支持、倍数和 slot 容量。[SPEC]

## 12. 性能注意点

管理模型变化不等于已测量的收益。至少比较 CPU 写入/绑定、内存占用、GPU 时间及正确性；移动设备另需持续负载、温度和功耗证据。这里没有声称完成硬件测试。[ENGINE]

## 13. 专家经验

支持实验后端、默认切换、删除 fallback 分别审批。缺少驱动覆盖、工具覆盖或 AHB 测试时，保持 feature-gated 可回退路径；不能以规范的 deprecation 标记代替项目退出条件。[ENGINE]

## 14. 相关 API 卡片

[Descriptor Buffer](descriptor_buffer.md) · [采样描述符](sampled_image_descriptor.md) · [架构门槛](../../02_core_mental_model/engine_architecture.md) · [项目能力矩阵](../../05_workflows/01_renderer_setup/project_diagnosis.md)

## 15. 需要回查官方文档的情况

- [Heap properties](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceDescriptorHeapPropertiesEXT.html)
- [设计说明与 shader 映射](https://docs.vulkan.org/features/latest/features/proposals/VK_EXT_descriptor_heap.html)
- [扩展 API / dependencies](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_descriptor_heap.html)
- [写入资源描述符](https://docs.vulkan.org/refpages/latest/refpages/source/vkWriteResourceDescriptorsEXT.html)

latest 页面非冻结版本。实现前保存 registry/header/spec revision，核验每个实际使用组合的 valid usage；本文不证明任何特定驱动、工具或 shader 编译器已经支持。

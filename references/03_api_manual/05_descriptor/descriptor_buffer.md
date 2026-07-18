# API Card: Descriptor Buffer (`VK_EXT_descriptor_buffer`)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | Descriptor Buffer |
| 常用 API | `vkGetDescriptorSetLayoutSizeEXT` / `vkGetDescriptorSetLayoutBindingOffsetEXT` / `vkCmdBindDescriptorBuffersEXT` / `vkCmdSetDescriptorBufferOffsetsEXT` |
| 适用平台 | 通用（Android 支持有限） |
| 来源等级 | `[SPEC] [TOOL] [ENGINE] [ANDROID]` |
| 适用 Vulkan 版本 | `VK_EXT_descriptor_buffer` 扩展 |

---

## 1. 一句话定位

`VK_EXT_descriptor_buffer` 把 descriptor 数据直接放在 `VkBuffer` 中，GPU 通过内存读取 descriptor，绕开 `VkDescriptorPool` / `VkDescriptorSet` / `vkUpdateDescriptorSets` 这一套传统对象，让 descriptor 与普通 buffer 一样可被 GPU 端写入、跨帧重用、按内存布局管理。[SPEC]

---

## 2. 所属对象链路

```text
VkDescriptorSetLayout (flags 含 VK_DESCRIPTOR_SET_LAYOUT_CREATE_DESCRIPTOR_BUFFER_BIT_EXT)
→ vkGetDescriptorSetLayoutSizeEXT / vkGetDescriptorSetLayoutBindingOffsetEXT
→ VkBuffer (USAGE_RESOURCE_DESCRIPTOR_BUFFER_BIT_EXT / SAMPLER_DESCRIPTOR_BUFFER_BIT_EXT)
→ vkMapMemory + vkGetDescriptorEXT (写 descriptor 数据)
→ vkCmdBindDescriptorBuffersEXT (绑定 buffer 到 command buffer)
→ vkCmdSetDescriptorBufferOffsetsEXT (按 set 索引设置 offset)
→ Shader Access
```

### 上游依赖

- Device 必须启用 `VK_EXT_descriptor_buffer` 扩展，且 `VkPhysicalDeviceDescriptorBufferPropertiesEXT` 已查询。[SPEC]
- `VkDescriptorSetLayout` 创建时需要使用 `VK_DESCRIPTOR_SET_LAYOUT_CREATE_DESCRIPTOR_BUFFER_BIT_EXT`（或允许的等价 path）。[SPEC]
- 用于存放 descriptor 的 `VkBuffer` 必须按用途带上 `VK_BUFFER_USAGE_RESOURCE_DESCRIPTOR_BUFFER_BIT_EXT` 或 `VK_BUFFER_USAGE_SAMPLER_DESCRIPTOR_BUFFER_BIT_EXT`。[SPEC]
- 启用扩展后，`VkDescriptorSetLayout` / `VkPipelineLayout` 创建受 descriptor buffer 特定约束（如 `pNext` 链上挂 `VkPipelineLayoutCreateFlagsCreateInfo`）。[SPEC]

### 下游影响

- Pipeline 在 command buffer 中通过 `vkCmdSetDescriptorBufferOffsetsEXT` 获取 set，shader 端 binding 行为与传统 descriptor set 一致。[SPEC]
- Descriptor buffer 内容由 GPU 直接读取，写入路径由实现决定（CPU `vkMapMemory` 写，或 GPU shader/`vkCmdDraw*` 间接写）。[SPEC]
- 已绑定的 descriptor buffer 在 GPU 完成前不能销毁或被覆盖写入。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkBuffer`（带 descriptor buffer usage bit）
- `VkDescriptorSetLayout`（带 descriptor buffer 创建 flag）
- `VkDescriptorBufferBindingInfoEXT`
- `VkDescriptorBufferBindingPushDescriptorBufferHandleEXT`
- `VkPhysicalDeviceDescriptorBufferPropertiesEXT`
- `VkDescriptorGetInfoEXT` / `VkDescriptorAddressInfoEXT`

### 常用 API

| API | 作用 |
|---|---|
| `vkGetDescriptorSetLayoutSizeEXT` | 查询某个 `VkDescriptorSetLayout` 在 descriptor buffer 中需要占用多少字节。[SPEC] |
| `vkGetDescriptorSetLayoutBindingOffsetEXT` | 查询 layout 中某个 binding 在 buffer 内的起始字节偏移。[SPEC] |
| `vkGetDescriptorEXT` | 生成单个 descriptor 的二进制数据并写入 CPU 指针（取代 `vkUpdateDescriptorSets`）。[SPEC] |
| `vkCmdBindDescriptorBuffersEXT` | 把一个或多个 descriptor buffer 绑定到 command buffer（区分 resource / sampler buffer）。[SPEC] |
| `vkCmdSetDescriptorBufferOffsetsEXT` | 在已绑定的 buffer 列表中按 set index 设置偏移，等价于传统 `vkCmdBindDescriptorSets`。[SPEC] |
| `vkCmdBindDescriptorBufferEmbeddedSamplersEXT` | 直接绑定 layout 中的 embedded sampler，无需独立 sampler buffer。[SPEC] |
| `vkGetBufferOpaqueCaptureDescriptorDataEXT` | 用于 capture/replay 场景获取 opaque descriptor data。[SPEC] |

### 相关扩展 / 版本

- `VK_EXT_descriptor_buffer`（promotion 自部分 `VK_EXT_descriptor_indexing` 思路，但本身是独立扩展）。
- 与 `VK_KHR_buffer_device_address`、`VK_EXT_descriptor_indexing` 经常配合使用（GPU 端写 descriptor 时需要 buffer device address）。[ENGINE]
- 与 `VK_KHR_push_descriptor` 互斥使用 push 部分（同 bind point 不可同时存在 push descriptor 与常规 descriptor buffer set）。[SPEC]

---

## 4. 标准使用流程

```text
1. 启用 VK_EXT_descriptor_buffer，查询 VkPhysicalDeviceDescriptorBufferPropertiesEXT
2. 创建 VkDescriptorSetLayout（带 DESCRIPTOR_BUFFER_BIT_EXT）
3. 创建 VkPipelineLayout（如需合并 set，挂 VkPipelineLayoutCreateFlagsCreateInfo）
4. vkGetDescriptorSetLayoutSizeEXT  → 得到每个 set 占用字节数
5. vkGetDescriptorSetLayoutBindingOffsetEXT → 得到每个 binding 在 set 内偏移
6. 分配 VkBuffer（带 RESOURCE_/SAMPLER_DESCRIPTOR_BUFFER_BIT_EXT），分配内存并 vkMapMemory
7. 对每个 binding 调 vkGetDescriptorEXT，按 binding offset 写入 buffer
8. vkCmdBindDescriptorBuffersEXT 把 resource / sampler buffer 绑到 command buffer
9. vkCmdSetDescriptorBufferOffsetsEXT 按 set index 设置偏移
10. vkCmdDraw* / vkCmdDispatch* → shader 读取 descriptor
11. GPU 完成后可重写 buffer 内容或切换 offset
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkPhysicalDeviceDescriptorBufferPropertiesEXT::maxResourceDescriptorBufferBindings` | 可同时绑定的 resource descriptor buffer 数。[SPEC] | 超过上限导致 bind 失败。[TOOL] |
| `...::maxSamplerDescriptorBufferBindings` | 可同时绑定的 sampler descriptor buffer 数。[SPEC] | sampler 与 resource buffer 混用导致计数错误。[TOOL] |
| `...::maxDescriptorBufferBindings` | resource + sampler 合计上限。[SPEC] | 忽略合计上限。[TOOL] |
| `...::combinedImageSamplerDescriptorSingleArray` | combined image sampler 是否必须单数组。[SPEC] | 忽略导致 layout 创建失败。[TOOL] |
| `...::bufferlessPushDescriptors` | 是否允许无 buffer 的 push descriptor。[SPEC] | 误以为所有实现都支持。[ANDROID] |
| `VkDescriptorBufferBindingInfoEXT::usage` | 必须与 buffer 创建时的 usage 一致（resource / sampler）。[SPEC] | usage 不匹配导致 validation error。[TOOL] |
| `VkDescriptorBufferBindingInfoEXT::address` | 用 `vkGetBufferDeviceAddress` 取得。[SPEC] | 未启用 buffer device address。[TOOL] |
| `vkCmdSetDescriptorBufferOffsetsEXT::bufferIndex` | 对应 `vkCmdBindDescriptorBuffersEXT` 中 buffer 列表的索引。[SPEC] | 索引越界或跨 resource/sampler 类别用错。[TOOL] |
| `vkCmdSetDescriptorBufferOffsetsEXT::offset` | 必须按 `descriptorBufferOffsetAlignment` 对齐。[SPEC] | 未对齐导致 GPU 读取错位。[TOOL] |
| `VkDescriptorSetLayoutCreateFlags::DESCRIPTOR_BUFFER_BIT_EXT` | 启用 descriptor buffer 路径必加。[SPEC] | 漏加导致 layout 与 buffer 不兼容。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 设备是否真的支持 `VK_EXT_descriptor_buffer`（含 `bufferlessPushDescriptors` 等子特性）？
- [ ] `VkDescriptorSetLayout` 是否带 `DESCRIPTOR_BUFFER_BIT_EXT`？
- [ ] `VkPipelineLayout` 是否在 `pNext` 上挂了 `VkPipelineLayoutCreateFlagsCreateInfo`（合并 set flags 必需）？
- [ ] buffer 是否同时带 `VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT`（如需 GPU 端写 descriptor）？
- [ ] buffer usage 是否区分 resource / sampler 两类？

### 写入阶段

- [ ] 每个 binding 是否按 `vkGetDescriptorSetLayoutBindingOffsetEXT` 返回的偏移写入？
- [ ] `vkGetDescriptorEXT` 的 `dataSize` 是否符合 `VkPhysicalDeviceDescriptorBufferPropertiesEXT::descriptorSize`（按 type）？
- [ ] 同一 buffer 中多个 set 是否按 `descriptorSetOffsetAlignment` 对齐？
- [ ] embedded immutable sampler 是否走 `vkCmdBindDescriptorBufferEmbeddedSamplersEXT` 而非写入 sampler buffer？

### 绑定阶段

- [ ] `vkCmdBindDescriptorBuffersEXT` 的 buffer 顺序与 `vkCmdSetDescriptorBufferOffsetsEXT` 的 `bufferIndex` 对应？
- [ ] offset 是否按 `descriptorBufferOffsetAlignment` 对齐？
- [ ] push descriptor 与 descriptor buffer 不会同时占同一 set slot？

### 销毁阶段

- [ ] 是否等待 GPU 不再使用 descriptor buffer？
- [ ] 是否同时释放对应的 `VkBuffer` 与 device memory？

---

## 7. 高频错误

1. `VkDescriptorSetLayout` 未带 `DESCRIPTOR_BUFFER_BIT_EXT`，却尝试用 buffer 路径绑定。[TOOL]
2. buffer usage 缺少 `RESOURCE_DESCRIPTOR_BUFFER_BIT_EXT` 或 `SAMPLER_DESCRIPTOR_BUFFER_BIT_EXT`。[TOOL]
3. `vkGetDescriptorEXT` 写入的 `dataSize` 与实现期望不符（必须按 properties 中 `descriptorSize[type]`）。[TOOL]
4. `vkCmdSetDescriptorBufferOffsetsEXT` 的 `offset` 未按 `descriptorBufferOffsetAlignment` 对齐。[TOOL]
5. 把 sampler descriptor 写到 resource buffer（或反之），导致 GPU 读取错乱。[SPEC]
6. 用 `vkCmdBindDescriptorBuffersEXT` 绑定后，又用 `vkCmdBindDescriptorSets` 绑定同一 bind point。[SPEC]
7. 同一 set slot 同时存在 push descriptor 与 descriptor buffer set。[SPEC]
8. 未启用 `VK_KHR_buffer_device_address` 就尝试 GPU 端写 descriptor。[ENGINE]
9. Android 上误以为驱动一定支持，未运行时查询 `VkPhysicalDeviceDescriptorBufferPropertiesEXT`。[ANDROID]
10. swapchain recreate 后 descriptor buffer 仍引用旧 image view 的 `VkDescriptorAddressInfoEXT`。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorSetLayoutCreateInfo-flags-08000`：descriptor buffer flag 合法性。
- `VUID-vkCmdBindDescriptorBuffersEXT-*`：buffer usage / address / 数量限制。
- `VUID-vkCmdSetDescriptorBufferOffsetsEXT-*`：对齐、bufferIndex、pipeline layout 兼容性。
- `VUID-vkGetDescriptorEXT-*`：type / dataSize / layout 用途匹配。

### RenderDoc / AGI

- RenderDoc 对 `VK_EXT_descriptor_buffer` 的展示仍在迭代中，部分版本只能看到 buffer 字节，看不到解析后的 binding；必要时切回传统 set 验证逻辑。[TOOL]
- AGI 在 descriptor buffer 路径下，descriptor 内容需通过 buffer viewer 查看，注意 offset 与 alignment。[TOOL]

### 日志 / 代码检查

- 打印 `VkPhysicalDeviceDescriptorBufferPropertiesEXT` 全字段，确认上限与对齐。
- 检查每个 `vkGetDescriptorEXT` 调用的 `descriptorType` 与 `dataSize`。
- 检查 `vkCmdBindDescriptorBuffersEXT` 的 buffer 数量是否超过 `maxDescriptorBufferBindings`。
- 检查 `vkCmdSetDescriptorBufferOffsetsEXT` 的 offset 是否为 `descriptorBufferOffsetAlignment` 整数倍。

---

## 9. 生命周期风险

### 创建时机

- 启用扩展后立即查询 `VkPhysicalDeviceDescriptorBufferPropertiesEXT`。
- Descriptor buffer 可在 pipeline layout 创建后即可分配；与传统 pool 不同，没有 per-set allocate/free 概念。

### 使用时机

- CPU 端通过 `vkMapMemory` + `vkGetDescriptorEXT` 写入。
- GPU 端可通过 shader 或 `vkCmdDispatch*` 间接写入（需要 buffer device address）。[ENGINE]
- Command buffer 录制时通过 `vkCmdBindDescriptorBuffersEXT` + `vkCmdSetDescriptorBufferOffsetsEXT` 绑定。

### 销毁阶段

- 与普通 `VkBuffer` 一致：必须等待 GPU 不再引用。
- 没有 `vkFreeDescriptorSets` / `vkResetDescriptorPool` 等概念，重写 buffer 内容即可“更新”descriptor。

### in-flight 风险

- Descriptor buffer 被 command buffer 引用期间，同一字节区间不能被 CPU 重写。[SPEC]
- 多帧 in-flight 时必须为每帧分配独立区间或独立 buffer。[ENGINE]
- GPU 端写 descriptor 后到 shader 读取之间需要 pipeline barrier 或事件同步。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkMapMemory` + `vkGetDescriptorEXT` 是 CPU 侧操作，写入后需确保 GPU 不会同时读同一区间（使用 host-visible / host-coherent 内存，并保证写后 CPU 不再覆盖直到 GPU 完成）。[SPEC]
- 如果用 host-visible 内存且未在 GPU 完成前等待，存在 RAW hazard；通常使用 per-frame ring buffer 区间隔离。[ENGINE]

### GPU-GPU 同步

- GPU 端写 descriptor 后，读取 shader 必须有 `VK_PIPELINE_STAGE_2_DESCRIPTOR_INDEXING_BIT` 或对应 stage 之间的 execution dependency。[SPEC]
- 推荐使用 `VkBufferMemoryBarrier2`（`vkCmdPipelineBarrier2`）覆盖 `VK_ACCESS_2_DESCRIPTOR_BUFFER_READ_BIT_EXT` 与写者的 access bit。[SPEC]

### 资源访问同步

- Descriptor buffer 指向的底层 buffer / image 仍由普通 barrier 管同步。
- Image layout 与传统路径一致，仍需保证 descriptor 中声明的 layout 与实际一致。[SPEC]

---

## 11. Android 注意点

- Android 上 `VK_EXT_descriptor_buffer` 支持有限，部分驱动（特别是 Mali / Adreno 老版本）可能不实现或子特性缺失。[ANDROID]
- 必须运行时查询 `VkPhysicalDeviceDescriptorBufferPropertiesEXT`，不要硬编码上限或对齐值。[ANDROID]
- 移动端 host-visible / host-coherent 内存较稀缺，应避免大块 descriptor buffer 长期占用 host-visible heap。[ENGINE]
- Mali 部分驱动在 `combinedImageSamplerDescriptorSingleArray` 上有特殊限制，跨 binding 合并采样器数组前必须验证。[ANDROID]
- AGI 在 Android 上对 descriptor buffer 的解析能力弱于桌面，调试时建议保留传统 set 的回退路径。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 完全消除 `vkAllocateDescriptorSets` / `vkUpdateDescriptorSets` 的 CPU 开销，descriptor 写入直接是内存拷贝。[ENGINE]
- 可预生成 descriptor data，运行时仅 `vkCmdSetDescriptorBufferOffsetsEXT` 切换 offset，单帧可绑定上千 set。[ENGINE]

### GPU 侧

- GPU 直接读内存中的 descriptor，跳过传统 descriptor set cache 路径，binding 切换开销显著降低（桌面端尤为明显）。[ENGINE]
- 但会增加一次 buffer 内存读取，移动端若 descriptor 频繁切换且无 cache hit，可能反而变慢，必须实测。[ANDROID]

### 移动端

- Descriptor buffer 推荐用于 set 数量极大或 GPU 端需要动态生成 descriptor 的场景（如 mesh shader、bindless）。[ENGINE]
- 简单渲染路径下，传统 descriptor set + push descriptor 仍可能是更优解。[ENGINE]

---

## 13. 专家经验

**经验**：
在桌面端做 bindless / GPU-driven 渲染时，descriptor buffer 是当前最干净的方案：用一张大 buffer 按 set offset 排布所有 material / draw 的 descriptor，CPU 只在加载时写一次，GPU 端用 `vkCmdSetDescriptorBufferOffsetsEXT` 切换；后续 mesh shader / indirect draw 通过 buffer device address 直接生成 descriptor。务必先打印 `VkPhysicalDeviceDescriptorBufferPropertiesEXT` 全字段，把 `descriptorBufferOffsetAlignment`、`descriptorSetOffsetAlignment`、`descriptorSize[type]` 当作硬约束，封装成一个 descriptor writer 工具类。

**适用条件**：
桌面端 + Vulkan 1.3 + `VK_EXT_descriptor_buffer` + `VK_KHR_buffer_device_address`，且渲染对象数量大、binding 切换频繁。

**不适用情况**：
移动端 / WebGPU-like 简化路径；驱动不支持；需要兼容老 Vulkan 1.1 / 1.2 设备。

**来源**：`[ENGINE]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_set_layout.md`
- `descriptor_update.md`
- `descriptor_indexing.md`
- `push_descriptor.md`
- `descriptor_pool.md`
- `../06_pipeline/pipeline_layout.md`
- `../04_buffer_image_memory/buffer.md`

---

## 15. 需要回查官方文档的情况

1. `VkPhysicalDeviceDescriptorBufferPropertiesEXT` 全字段含义与默认值（特别是 `allowSamplerImageViewPostQueryCoalescing`、`allowImageViewInputAttachmentComponentLayout` 等子特性）。
2. `vkGetDescriptorEXT` 各 `descriptorType` 对应的 `VkDescriptorGetInfoEXT::pNext` 结构体（`VkDescriptorAddressInfoEXT` 等）。
3. `vkCmdBindDescriptorBuffersEXT` 与 push descriptor、embedded sampler 的互斥规则。
4. `VK_DESCRIPTOR_SET_LAYOUT_CREATE_EMBEDDED_IMMUTABLE_SAMPLERS_BIT_EXT` 的具体行为。
5. capture/replay 路径（`VkDeviceBufferCaptureReplayDescriptorDataCreateInfoEXT`）的字段。
6. Android 各厂商（Mali / Adreno / PowerVR）对扩展子特性的实现差异。

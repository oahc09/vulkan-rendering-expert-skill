# API Card: Storage Buffer / Storage Image Descriptor

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorBufferInfo`（`STORAGE_BUFFER`） / `VkDescriptorImageInfo`（`STORAGE_IMAGE`） |
| 常用 API | `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

Storage buffer 与 storage image descriptor 分别将可读写 buffer 与 image 绑定到 shader 的 storage 接口，是 compute shader 读写大规模结构化数据、随机访问图像像素的核心机制。[SPEC]

---

## 2. 所属对象链路

```text
Storage Buffer:
VkBuffer（VK_BUFFER_USAGE_STORAGE_BUFFER_BIT）
→ VkDescriptorBufferInfo
→ vkUpdateDescriptorSets（STORAGE_BUFFER / STORAGE_BUFFER_DYNAMIC）
→ vkCmdBindDescriptorSets
→ Shader Storage Buffer Block

Storage Image:
VkImage（VK_IMAGE_USAGE_STORAGE_BIT）
→ VkImageView
→ VkDescriptorImageInfo（imageView / imageLayout = GENERAL）
→ vkUpdateDescriptorSets（STORAGE_IMAGE）
→ vkCmdBindDescriptorSets
→ Shader Image Load/Store
```

### 上游依赖

- Buffer usage 包含 `STORAGE_BUFFER_BIT`；image usage 包含 `STORAGE_BIT`。[SPEC]
- Descriptor set layout 声明了 `STORAGE_BUFFER` 或 `STORAGE_IMAGE`。[SPEC]
- 对 storage image，通常需要启用相关 feature（如 `shaderStorageImageReadWithoutFormat`）。[SPEC]

### 下游影响

- Compute / fragment shader 可直接读写 buffer 或 image 像素。
- 需要显式同步避免数据竞争。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDescriptorBufferInfo`
- `VkDescriptorImageInfo`
- `VkWriteDescriptorSet`
- `VkBuffer`
- `VkImageView`

### 常用 API

| API | 作用 |
|---|---|
| `vkUpdateDescriptorSets` | 写入 storage buffer 或 storage image descriptor。[SPEC] |
| `vkCmdBindDescriptorSets` | 绑定 descriptor set。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_descriptor_indexing` / Vulkan 1.2 支持 storage 资源的 update-after-bind。
- `shaderStorageImageReadWithoutFormat` / `shaderStorageImageWriteWithoutFormat` 等 feature 影响 storage image 使用。

---

## 4. 标准使用流程

```text
Storage Buffer:
创建 VkBuffer 并指定 STORAGE_BUFFER_BIT
→ 构造 VkDescriptorBufferInfo（buffer / offset / range）
→ vkUpdateDescriptorSets（descriptorType = STORAGE_BUFFER）
→ 确保 GPU 写入后再被读取前插入 buffer barrier
→ vkCmdBindDescriptorSets
→ Compute/Graphics shader 读写

Storage Image:
创建 VkImage 并指定 STORAGE_BIT
→ transition 到 GENERAL layout
→ 创建 VkImageView
→ 构造 VkDescriptorImageInfo（imageView / imageLayout = GENERAL）
→ vkUpdateDescriptorSets（descriptorType = STORAGE_IMAGE）
→ 确保 image 读写同步
→ vkCmdBindDescriptorSets
→ Shader imageLoad / imageStore
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `buffer` / `imageView` | 资源 usage 必须包含 storage bit。[SPEC] | 忘记设置 `STORAGE_BUFFER_BIT` 或 `STORAGE_BIT`。[TOOL] |
| `offset`（storage buffer） | 必须按 `minStorageBufferOffsetAlignment` 对齐。[SPEC] | 偏移未对齐。[TOOL] |
| `imageLayout`（storage image） | 必须使用 `GENERAL` layout。[SPEC] | 使用 `SHADER_READ_ONLY_OPTIMAL` 等非法 layout。[TOOL] |
| `descriptorType` | `STORAGE_BUFFER` / `STORAGE_BUFFER_DYNAMIC` / `STORAGE_IMAGE` 需与 layout 一致。[SPEC] | layout 与实际 type 不匹配。[TOOL] |
| `format` | Storage image 的 format 需被设备支持；部分情况需要 `ReadWithoutFormat` feature。[SPEC] | 使用不支持 storage 的 format。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Buffer/image usage 是否包含 storage bit？
- [ ] Storage image format 是否支持 storage 操作？
- [ ] 是否需要启用 `shaderStorageImageReadWithoutFormat` 等 feature？
- [ ] Descriptor set layout 的 type 是否正确？

### 使用阶段

- [ ] Storage image 是否处于 `GENERAL` layout？
- [ ] Storage buffer offset 是否满足对齐要求？
- [ ] 读写之间是否插入 barrier 防止数据竞争？
- [ ] Shader 中的 memory/execution barrier（如 `barrier()` / `memoryBarrier()`）是否合理？

### 销毁阶段

- [ ] 确保 GPU 不再读写 storage 资源后再销毁。[SPEC]

---

## 7. 高频错误

1. Image 未 transition 到 `GENERAL` layout 就作为 storage image 使用。[TOOL]
2. Buffer offset 未按 `minStorageBufferOffsetAlignment` 对齐。[TOOL]
3. Storage image format 不支持 storage write。[TOOL]
4. 多个 dispatch/draw 同时读写同一 storage 资源，未做 barrier 或 shader barrier。[TOOL]
5. 忘记启用 `shaderStorageImageReadWithoutFormat` 导致 shader 中 format 不匹配。[TOOL]
6. 把 storage buffer 当作 UBO 使用，未检查 `maxStorageBufferRange`。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkWriteDescriptorSet-*`：descriptor type 与资源兼容性。
- `VUID-vkCmdDispatch-*-imageLayout-*`：storage image 必须处于 `GENERAL`。
- `VUID-VkDescriptorBufferInfo-offset-*`：storage buffer offset 对齐。

### RenderDoc / AGI

- 查看 storage buffer/image 的内容。
- 检查 shader 中的 imageLoad/imageStore 与 barrier 使用。
- 分析 compute dispatch 之间的同步。

### 日志 / 代码检查

- 检查 storage buffer/image 的 usage 与 layout。
- 检查 descriptor type 与 shader 声明。
- 检查读写之间的 barrier 与 shader memory barrier。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段创建 storage buffer/image；compute pass 开始前更新 descriptor。[ENGINE]

### 使用时机

- Compute dispatch 或 graphics shader 中通过 storage 接口读写。[SPEC]

### 销毁时机

- 确认 GPU 不再访问后销毁。[SPEC]

### in-flight 风险

- Storage 资源被 command buffer 引用后，fence signal 前不能复用或销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- CPU 更新 host-visible storage buffer 后需 flush；CPU 读取 GPU 写入前需 invalidate。[SPEC]

### GPU-GPU 同步

- Storage 资源的读写切换需要 buffer/image barrier 与 shader 内部 `barrier()` / `memoryBarrier()` 配合。[SPEC]
- 不同 workgroup 之间的顺序无保证，需依赖原子操作或显式同步。

### 资源访问同步

- Storage image 必须处于 `GENERAL` layout。[SPEC]
- Storage buffer 的 memory dependency 需通过 buffer barrier 或 event 建立。[SPEC]

---

## 11. Android 注意点

- 移动端 compute shader 的 storage image 性能受 tile-based 架构影响，建议优先使用 storage buffer 做通用计算。[ANDROID][ENGINE]
- `shaderStorageImageReadWithoutFormat` / `WriteWithoutFormat` 在移动端支持度不一，需运行时查询。[ANDROID]
- Storage buffer 常用于 GPU-driven rendering、粒子、后处理；注意 barrier 开销。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Storage descriptor 更新与 UBO 类似，应避免高频更新。[ENGINE]

### GPU 侧

- Storage image 的随机写可能破坏 tile memory 优化；尽量用 storage buffer 或纹理反馈替代。[ENGINE]
- 原子操作在移动端代价高，避免热点竞争。[ENGINE]

### 移动端

- 避免在 fragment shader 中大量 `imageStore`。[ANDROID]
- Compute pass 中的 storage buffer 访问尽量合并，减少 barrier 数量。[ENGINE]

---

## 13. 专家经验

**经验**：
Storage buffer 比 storage image 更通用且通常性能更可预测；除非确实需要随机写像素，否则优先用 storage buffer 或 sampled image。使用 storage image 时，务必确保 layout 为 `GENERAL`，并在 dispatch 之间用精确的 barrier 同步。Compute shader 内部不要忽视 `barrier()` / `memoryBarrier()`，否则同一个 dispatch 内的读写顺序无保证。

**适用条件**：
Compute 管线、GPU-driven rendering、后处理、粒子系统、需要 shader 随机写的场景。

**不适用情况**：
只读纹理采样优先用 sampled image descriptor；少量常量数据用 UBO/push constant。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_set_layout.md`
- `descriptor_update.md`
- `descriptor_pool.md`
- `sampled_image_descriptor.md`
- `uniform_buffer_descriptor.md`
- `../04_buffer_image_memory/buffer.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`
- `../04_buffer_image_memory/image_layout.md`
- `../08_synchronization/buffer_memory_barrier.md`
- `../08_synchronization/image_memory_barrier.md`

---

## 15. 需要回查官方文档的情况

1. 具体 format 是否支持 storage image read/write。
2. `shaderStorageImageReadWithoutFormat` / `WriteWithoutFormat` 的启用条件。
3. Storage buffer offset 对齐要求。
4. Compute shader 中 `barrier()` / `memoryBarrier()` 与 Vulkan barrier 的交互。
5. 不同驱动对 storage image 随机写的性能特征。

<a id="delivery19-external-shared-buffer"></a>
## 上游工程案例：多个 descriptor 的共享 backing

[ENGINE] 同一逻辑 buffer 经多个 descriptor/view 绑定时，应保持引擎承诺的共享存储和写入可观察性，不能为每个 binding 无条件复制成互不关联的 backing。资源缓存键不能只看 descriptor 身份而丢失逻辑资源身份；创建前须汇总实际 usage，任一可写引用都会影响共享资源的上传/回读策略。offset、range、view 格式、权限及最后使用者的生命周期仍要分别检查。

[SPEC][ENGINE] 这不是“所有别名必须具有同一个 VkBuffer 句柄”的规范要求。不同资源对象也可能合法别名同一内存；相同句柄也不保证 range 相同或访问合法。共享存储不自动建立执行/内存依赖，跨访问 hazard、queue family 及 host 可见性必须另行分析。不要从一个计算样例成功推导全部 alias 或同步规则成立。

[ENGINE] Google Amber #951 的真实历史修复将按 descriptor 独立持有的 transfer resource 转为 Pipeline 按逻辑 Buffer 共享持有，合并 usage 和可写属性，并统一上传/回读。固定修复为 `8c3bfef40c2387944fdc81746e2e3249e4da5566`，前版为 `aaac58d5009e8f6b33e2723258dc1542854d09a4`；上游原用例 compute_one_buffer_in_multiple_bindings.amber 同时涵盖 UBO、SSBO 和 texel view。其原 EXPECT 可用于真实引擎前后回放，实际执行结果必须与源码推断分开报告。

来源：[原始上游修复](https://github.com/google/amber/commit/8c3bfef40c2387944fdc81746e2e3249e4da5566)；[配对 tests 仓任务与验收范围](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/blob/feat/v1.0.19-final-delivery/docs/external-amber951-task19.md)。这是公开答案的开发案例，不是未知任务盲测；完整原工程执行也不等于移动硬件、性能或全域专家验收。

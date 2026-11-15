# API Card: Push Descriptor (`VK_KHR_push_descriptor` / Vulkan 1.4)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | Push Descriptor |
| 常用 API | `vkCmdPushDescriptorSetKHR` / `vkCmdPushDescriptorSet2` / `vkCmdPushDescriptorSetWithTemplate2` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | `VK_KHR_push_descriptor` / Vulkan 1.4 promote 为 mandatory feature（仍需在 `VkPhysicalDeviceVulkan14Features.pushDescriptor` 显式启用） |

---

## 1. 一句话定位

Push descriptor 是把一个 set 的 binding 内容直接 push 进 command buffer、跳过 `VkDescriptorPool` / `VkDescriptorSet` 对象路径的轻量 descriptor 机制，适合每帧（甚至每 draw）频繁切换的小型 descriptor set。[SPEC]

---

## 2. 所属对象链路

```text
VkPipelineLayout (其中某个 set 的 layout 创建时带 VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR)
→ vkCmdPushDescriptorSetKHR  /  vkCmdPushDescriptorSet2  /  vkCmdPushDescriptorSetWithTemplate2
   (传入 VkWriteDescriptorSet / VkDescriptorUpdateTemplate / VkPushDescriptorSetInfo / VkPushDescriptorSetWithTemplateInfo)
→ Command Buffer 录制 push
→ 后续 GPU Shader Access（按 pipeline layout 中指定的 set index）
```

### 上游依赖

- 目标 set 对应的 `VkDescriptorSetLayout` 创建时必须带 `VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR`。[SPEC]
- `VkPipelineLayout` 把该 layout 放在某个 set index 上；该 set slot 不再接受 `vkCmdBindDescriptorSets`。[SPEC]
- 写入的资源（buffer / image view / sampler）必须已创建。[SPEC]
- 若使用 template 路径，`VkDescriptorUpdateTemplate` 必须按 push descriptor 模式创建（`templateType = VK_DESCRIPTOR_UPDATE_TEMPLATE_TYPE_PUSH_DESCRIPTORS_KHR`）。[SPEC]

### 下游影响

- Push 之后该 set slot 在当前 command buffer 中即处于“已绑定”状态，后续执行的 shader 按已录制状态访问。[SPEC]
- 再次 push 只更新指定 descriptors；同一兼容 layout 下未写的部分不因此自动初始化。改变 layout/其他绑定导致的 disturbance 按 pipeline-layout compatibility 检查。[SPEC]
- Command buffer reset / rerecord 时 push 状态随之失效。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipelineLayout`（含 push descriptor set slot）
- `VkDescriptorSetLayout`（带 `PUSH_DESCRIPTOR_BIT_KHR`）
- `VkWriteDescriptorSet`
- `VkDescriptorUpdateTemplate`（push 路径）
- `VkPushDescriptorSetInfo`（Vulkan 1.4）
- `VkPushDescriptorSetWithTemplateInfo`（Vulkan 1.4）

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPushDescriptorSetKHR` | 旧版命令：用一组 `VkWriteDescriptorSet` 直接 push 一个 set 到 command buffer。[SPEC] |
| `vkCmdPushDescriptorSet2` | Vulkan 1.4 新增：基于 `VkPushDescriptorSetInfo`，使用 `VkPushDescriptorSetInfo` 的 stageFlags/layout/set 等字段；属于 maintenance6 路径，不产生同步依赖。[SPEC] |
| `vkCmdPushDescriptorSetWithTemplate2` | Vulkan 1.4 新增：基于 `VkPushDescriptorSetWithTemplateInfo`，用 update template + raw data 指针 push。[SPEC] |
| `vkCmdPushDescriptorSetWithTemplateKHR` | 旧版 template push 命令（与 `vkCmdPushDescriptorSetKHR` 同期）。[SPEC] |
| `vkCreateDescriptorUpdateTemplate` / `vkDestroyDescriptorUpdateTemplate` | 创建 / 销毁 push template。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_push_descriptor`：原始扩展，1.0 起作为扩展可用。
- Vulkan 1.1 / 1.2 / 1.3：仍作为扩展，需启用。
- Vulkan 1.4：push descriptor 的 API promote 进 core 并提升为 mandatory feature（保证被支持）；**仍需在 `VkDeviceCreateInfo.pNext` 中通过 `VkPhysicalDeviceVulkan14Features.pushDescriptor = VK_TRUE` 显式启用** 后才能调用相关 API（无需再启用 `VK_KHR_push_descriptor` 扩展字符串）；同时新增 `vkCmdPushDescriptorSet2` / `vkCmdPushDescriptorSetWithTemplate2`，maintenance6 的结构化命令与 synchronization2 是独立能力，push 不建立资源内存依赖。[SPEC]
- 与 `VK_KHR_descriptor_update_template` 强绑定（template 路径）。
- 与 `VK_EXT_descriptor_buffer` 互斥：同一 set slot 不可同时是 push descriptor 与 descriptor buffer set。[SPEC]

---

## 4. 标准使用流程

### 路径 A：直接 `vkCmdPushDescriptorSetKHR` / `vkCmdPushDescriptorSet2`

```text
1. 创建 VkDescriptorSetLayout（带 PUSH_DESCRIPTOR_BIT_KHR）
2. 创建 VkPipelineLayout，把该 layout 放在目标 set index
3. 创建 pipeline（使用上述 pipeline layout）
4. 录制 command buffer：
   vkCmdBindPipeline(...)
   vkCmdPushDescriptorSetKHR(
       commandBuffer, pipelineBindPoint, pipelineLayout,
       set, descriptorWriteCount, pDescriptorWrites)
   或 Vulkan 1.4:
   vkCmdPushDescriptorSet2(commandBuffer, &VkPushDescriptorSetInfo)
5. vkCmdDraw* / vkCmdDispatch*  → GPU 执行时 shader 访问已录制的 descriptor 状态
```

### 路径 B：update template

```text
1. 同 A 步骤 1-3
2. vkCreateDescriptorUpdateTemplate(
       templateType = VK_DESCRIPTOR_UPDATE_TEMPLATE_TYPE_PUSH_DESCRIPTORS_KHR,
       descriptorSetLayout = 上述 layout, pipelineLayout = 上述 pipelineLayout, set = N)
3. 录制 command buffer：
   vkCmdBindPipeline(...)
   vkCmdPushDescriptorSetWithTemplateKHR(commandBuffer, template, layout, set, pData)
   或 Vulkan 1.4:
   vkCmdPushDescriptorSetWithTemplate2(commandBuffer, &VkPushDescriptorSetWithTemplateInfo)
4. vkCmdDraw* / vkCmdDispatch*
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkDescriptorSetLayoutCreateInfo::flags` 中的 `PUSH_DESCRIPTOR_BIT_KHR` | 启用 push descriptor 必加。[SPEC] | 漏加导致后续 push 调用 validation error。[TOOL] |
| `VkPhysicalDevicePushDescriptorPropertiesKHR::maxPushDescriptors` | push descriptor set layout 中所有 binding 的 descriptorCount 总和上限（包含数组元素，不是 binding 个数）。[SPEC] | 超过上限导致 push 失败。[TOOL] |
| `vkCmdPushDescriptorSetKHR::layout` | 用于解析 set index 与 binding layout。[SPEC] | 传入与 pipeline 不一致的 layout。[TOOL] |
| `vkCmdPushDescriptorSetKHR::set` | 必须是 pipeline layout 中标记为 push 的 set index。[SPEC] | set slot 不是 push 类型却尝试 push。[TOOL] |
| `VkWriteDescriptorSet::dstArrayElement` / `descriptorCount` | 写入数组内的起始位置与数量。[SPEC] | 与 layout 中声明的 array size 不一致。[TOOL] |
| `VkPushDescriptorSetInfo::layout` / `set` / `pDescriptorWrites` | Vulkan 1.4 等价字段，但通过结构体传入，便于扩展与 `pNext`。[SPEC] | 误用 `vkCmdBindDescriptorSets` 的 set index 思维。[TOOL] |
| `VkPushDescriptorSetWithTemplateInfo::pData` | 指向原始内存，按 template 偏移读取。[SPEC] | 内存布局未对齐到 template 描述的字段类型。[TOOL] |
| `VkDescriptorUpdateTemplateCreateInfo::templateType` | push 路径必须填 `VK_DESCRIPTOR_UPDATE_TEMPLATE_TYPE_PUSH_DESCRIPTORS_KHR`。[SPEC] | 用错 template type。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VkDescriptorSetLayout` 是否带 `PUSH_DESCRIPTOR_BIT_KHR`？
- [ ] `VkPipelineLayout` 中该 set index 是否唯一对应到 push descriptor layout？
- [ ] Push descriptor set 不再带 `VK_DESCRIPTOR_SET_LAYOUT_CREATE_UPDATE_AFTER_BIND_POOL_BIT` 等不兼容 flag。[SPEC]
- [ ] 该 push set layout 的 descriptorCount 总和是否 ≤ `maxPushDescriptors`？只有两个 binding 但数组各32项仍是64个 descriptors。
- [ ] Update template 的 `templateType`、`descriptorSetLayout`、`pipelineLayout`、`set` 是否一致？

### 使用阶段

- [ ] `vkCmdPushDescriptorSet*` 的 `layout` 与当前绑定 pipeline 的 pipeline layout 兼容？
- [ ] `set` index 是否在 pipeline layout 中标记为 push？
- [ ] 每个 `VkWriteDescriptorSet` 的 `descriptorType` 与 layout 声明一致？
- [ ] Image descriptor 的 `imageLayout` 是否与实际 image layout 一致？
- [ ] 模板路径下 `pData` 指向的内存是否覆盖所有 template entry？

### 销毁阶段

- [ ] Push descriptor 不需要 free，但要保证 GPU 不再使用所引用的资源。
- [ ] `VkDescriptorUpdateTemplate` 用完显式 `vkDestroyDescriptorUpdateTemplate`。

---

## 7. 高频错误

1. `VkDescriptorSetLayout` 漏加 `PUSH_DESCRIPTOR_BIT_KHR`，导致 push 调用 validation error。[TOOL]
2. push 到一个非 push 类型的 set slot（layout 没标记 push）。[TOOL]
3. push layout 的 descriptorCount 总和超过 `maxPushDescriptors`。[TOOL]
4. `vkCmdPushDescriptorSetKHR` 的 `layout` 与当前 pipeline 的 pipeline layout 不兼容（set 数量或 binding layout 不一致）。[TOOL]
5. Image descriptor 的 `imageLayout` 与实际 layout 不一致。[TOOL]
6. Push 之后没有再 push 也没有 bind，下一帧 reset command buffer 后误以为 push 状态保留。[ENGINE]
7. Update template 的 `templateType` 选错，使用了 descriptor set 模板而非 push 模板。[TOOL]
8. 同一 set slot 既尝试 `vkCmdBindDescriptorSets` 又尝试 `vkCmdPushDescriptorSetKHR`。[SPEC]
9. 把 `vkCmdPushDescriptorSet2` 当作 `VkDependencyInfo` 或同步命令；它更新 descriptor 状态，资源可见性与 layout 仍由真实 producer/consumer 依赖负责。[ENGINE]
10. 把调用期 host 的 `pData`/write 数组与其引用的 GPU 资源寿命混淆；host 输入须在命令调用期间有效，buffer/image/view/sampler 则须满足所有 GPU 使用的寿命。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorSetLayoutCreateInfo-flags-00280`：push descriptor layout 不能包含 UNIFORM_BUFFER_DYNAMIC 或 STORAGE_BUFFER_DYNAMIC descriptor 类型。 [官方 VkDescriptorSetLayoutCreateInfo 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkDescriptorSetLayoutCreateInfo.html)。[SPEC]
- `VUID-vkCmdPushDescriptorSet-*`（当前规范核心命名；扩展别名按 SDK 日志检索）：layout / set / pipeline bind point / binding 数量。
- `VUID-VkPushDescriptorSetInfo-*`：Vulkan 1.4 路径的字段合法性。
- `VUID-vkCmdPushDescriptorSetWithTemplate2-*`：template 与 layout 一致性。
- `VUID-VkDescriptorUpdateTemplateCreateInfo-templateType-00350`：当 templateType 为 DESCRIPTOR_SET 时，descriptorSetLayout 必须是有效 handle；这不是 push-template 字段规则。 [官方 VkDescriptorUpdateTemplateCreateInfo 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkDescriptorUpdateTemplateCreateInfo.html)。[SPEC]

### RenderDoc / AGI

- 在 draw / dispatch 的 bound state 中查看 push descriptor set 的 binding 内容。
- 注意 RenderDoc 老版本对 Vulkan 1.4 `vkCmdPushDescriptorSet2` 的展示可能不完整，必要时降级到 `vkCmdPushDescriptorSetKHR` 验证逻辑。[TOOL]

### 日志 / 代码检查

- 打印 `VkPhysicalDevicePushDescriptorPropertiesKHR::maxPushDescriptors`。
- 检查每个 `vkCmdPushDescriptorSet*` 调用前 pipeline 是否已 `vkCmdBindPipeline`。
- 检查 push 调用的 `descriptorWriteCount` 与 layout 中实际 binding 数。
- 对比 image descriptor 的 `imageLayout` 与 `vkCmdPipelineBarrier` 设置的 layout。

---

## 9. 生命周期风险

### 创建时机

- 启用 `VK_KHR_push_descriptor` 扩展（1.0–1.3）或在 Vulkan 1.4 中通过 `VkPhysicalDeviceVulkan14Features.pushDescriptor = VK_TRUE` 显式启用后，即可创建带 push flag 的 layout；Vulkan 1.4 上无需再启用扩展字符串，但仍需启用 feature。
- 不存在 `VkDescriptorSet` 对象，因此没有 allocate / free。

### 使用时机

- 在 command buffer 录制时 push；push 即生效，后续执行的 shader 按已录制状态访问。
- Push 之后该 set slot 在 command buffer 内一直保持该状态，直到下次 push 或 command buffer 结束。[SPEC]

### 销毁阶段

- Push descriptor 没有对象需要 free。
- 但 push 引用的底层资源（buffer / image view / sampler）必须等 GPU 完成后才能销毁。

### in-flight 风险

- 多帧 in-flight 时，每帧 command buffer 各自 push 自己的内容，互不影响。
- 但 push 写入引用的 `VkWriteDescriptorSet` / `pData` 指针只在录制期间使用，录制结束即可释放；GPU 读的是 push 时拷贝进 command buffer 的状态。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Push 是录制时立即拷贝 descriptor 内容到 command buffer 内部状态，调用返回后 CPU 即可释放 `VkWriteDescriptorSet` 数组与 `pData`。[SPEC]
- 与传统 `vkUpdateDescriptorSets` 不同，没有“写后立即被读”的 host-coherent 隐患。

### GPU-GPU 同步

- Push descriptor 本身不引入同步；shader 读 descriptor 仍按 stage 的 execution dependency。
- 多次 push 同一 set 之间，前一次 push 的内容会对后续已录制的 draw/dispatch 持续可见，直到被新的 push 覆盖，或因 pipeline-layout compatibility 被打乱（disturbed）；不存在"前一次 push 仅对前面 draw 可见、对后续不可见"的语义。[SPEC]

### 资源访问同步

- Push 引用的 image / buffer 与传统 descriptor set 一致，仍需 barrier / layout transition 管同步。
- Image descriptor 中 `imageLayout` 必须与实际 layout 一致。[SPEC]

---

## 11. Android 注意点

- `VK_KHR_push_descriptor` 在主流 Android 驱动（Mali / Adreno / PowerVR 新版本）上普遍支持，但仍需运行时查询扩展与 `VkPhysicalDevicePushDescriptorPropertiesKHR::maxPushDescriptors`。[ANDROID]
- Android 上 Vulkan 1.4 普及度仍在推进，1.4 的 `vkCmdPushDescriptorSet2` 在老设备上不可用，需要保留 `vkCmdPushDescriptorSetKHR` 回退。[ANDROID]
- Push descriptor 是移动端推荐的小型 per-draw / per-pass descriptor 方案，避免 pool 分配开销；但不要 push 过大 set（移动端 `maxPushDescriptors` 可能只有 32）。[ENGINE]
- Mali 部分驱动在 push 后立即 dispatch / draw 的 corner case 上存在 cache 同步问题，建议 push 与 draw 之间避免极高频切换。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 完全省去 `vkAllocateDescriptorSets` / `vkUpdateDescriptorSets` 路径，单次 push 即完成“分配 + 更新 + 绑定”三步。[ENGINE]
- 对 per-frame / per-draw 频繁切换的小 set，CPU 开销显著低于传统 descriptor set。[ENGINE]
- Update template 路径在固定写入模式（如 view matrix + texture）下，CPU 开销最低（一次内存拷贝）。[ENGINE]

### GPU 侧

- Push descriptor 内容直接进入 command buffer 内部状态，GPU 读取路径与传统 set 类似，但少一次 descriptor set 表查找。[ENGINE]
- 频繁 push 会增加 command buffer 体积，影响 replay / 提交带宽；批量 draw 共享同一 set 时仍应优先传统 set。[ENGINE]

### 移动端

- 推荐用于 per-pass view data、per-material 小集合、debug overlay 等 binding 少且更新频繁的场景。[ENGINE]
- 不适合存放大型 bindless texture 数组（应使用 descriptor indexing / descriptor buffer）。[ENGINE]

---

## 13. 专家经验

**经验**：
push descriptor 是 per-pass / per-draw 频繁变化的小 descriptor set 的候选方案：把 view UBO + 几个 attachment 引用放进一个 push set，每个 pass 开始时 push 一次即可；material / bindless 仍走传统 descriptor set 或 descriptor buffer。务必先打印 `maxPushDescriptors`，移动端可能只有 32，需要限制 layout 中 descriptorCount 总和。Vulkan 1.4 上推荐直接使用 `vkCmdPushDescriptorSet2` / `vkCmdPushDescriptorSetWithTemplate2`，按 maintenance6 的 stageFlags 与 layout 合同使用，不与 Sync2 混同；老路径作为 fallback。固定 push 模式（per-pass view + per-draw transform）优先用 update template，CPU 端只剩一次 `memcpy`。

**适用条件**：
Vulkan 1.0+ 启用 `VK_KHR_push_descriptor` 或 Vulkan 1.4；binding 数量小、更新频繁；不需要 update-after-bind。

**不适用情况**：
bindless / 大型 texture 数组（用 descriptor indexing 或 descriptor buffer）；需要长期复用且不变的大 set（用传统 descriptor set）；驱动不支持扩展且不是 Vulkan 1.4。

**来源**：`[ENGINE]`

---

## 14. 相关 API 卡片

- `descriptor_set.md`
- `descriptor_set_layout.md`
- `descriptor_update.md`
- `descriptor_indexing.md`
- `descriptor_buffer.md`
- `descriptor_pool.md`
- `../06_pipeline/pipeline_layout.md`

---

## 15. 需要回查官方文档的情况

1. `VkPhysicalDevicePushDescriptorPropertiesKHR::maxPushDescriptors` 的最小保证值与各厂商实测。
2. Vulkan 1.4 中 `vkCmdPushDescriptorSet2` / `vkCmdPushDescriptorSetWithTemplate2` 的完整 VUID 与 `VkPushDescriptorSetInfo` / `VkPushDescriptorSetWithTemplateInfo` 的 `pNext` 扩展链。
3. Push descriptor 与 `VK_EXT_descriptor_buffer` push 部分（`VkPhysicalDeviceDescriptorBufferPropertiesEXT::bufferlessPushDescriptors`）的互斥 / 互替关系。
4. `VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR` 与其他 flag（`UPDATE_AFTER_BIND_POOL_BIT`、`DESCRIPTOR_BUFFER_BIT_EXT`）的兼容矩阵。
5. Update template 的 push 路径下，`pData` 内存对齐与字段布局规则。
6. Vulkan 1.4 在 Android 驱动上的普及时间线与 `vkCmdPushDescriptorSet2` 的可用性。


<a id="push-descriptor-count-lifetime"></a>
## 全域审计：数量、版本与录制寿命（1.4.368）

**条件与正常路径**：`maxPushDescriptors` 约束带 PUSH_DESCRIPTOR 标志的 **set layout 的 descriptor 总数**，包括每个 binding 的 `descriptorCount` 数组数量；不是 write 次数、binding 个数或本次只更新的项数。先查实际属性，再验证 layout 和每次 write 的类型/范围；分多次 push 不能让超限 layout 变合法。该属性的最低保证32不在1.4提高：1.4.368撤回的是“提高到32”的版本变化说法，不是把当前最低值改小。[SPEC]

`vkCmdPushDescriptorSet2` / `vkCmdPushDescriptorSetWithTemplate2` 的扩展路径属于 `maintenance6`，不是 synchronization2。命令的 CPU 参数（write 数组、template 的 `pData` 原始数据及描述信息）在调用期间有效；默认 host 参数寿命不能机械延长到 GPU 完成。描述符引用的资源与内存必须一直合法到所有使用完成。录制新 command buffer 时 push 状态 undefined；不完整更新只对已定义且未 disturbed 的项目保留含义。模板不能修复 layout 不匹配，也不替代资源 barrier。

**失败与回退**：无 push 能力时选用已有 descriptor set/pool 路线，保留同一资源寿命和同步合同。未知/不支持的 descriptor type、超总数、模板不兼容或失效引用在 host 配置阶段拒绝；不靠执行越界来测试。**验证**：评审检查一个数组 binding 大于限制、多个小数组总和超限、只写部分数组、录制调用返回后复用 CPU staging 描述信息、GPU 仍引用旧 image 的退休时机。性能推荐必须实测，不把 push/template 宣称为普适最优。

固定权威：[Limits](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/limits.adoc#limits-maxPushDescriptors)、[push descriptors](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/descriptorsets.adoc#descriptorsets-push-descriptors)、[host 参数寿命](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/fundamentals.adoc#fundamentals-validusage)。

# API Card: Descriptor Indexing (`VK_EXT_descriptor_indexing` / Vulkan 1.2 core)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Descriptor 链 |
| Vulkan 对象 | `VkDescriptorSetLayout` / `VkDescriptorSet`（Descriptor Indexing 扩展） |
| 常用 API | `vkCreateDescriptorSetLayout` / `vkAllocateDescriptorSets` / `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` |
| 适用平台 | 通用（Android 需查询设备支持） |
| 来源等级 | `[SPEC] [TOOL] [ENGINE] [ANDROID]` |
| 适用 Vulkan 版本 | `VK_EXT_descriptor_indexing` / Vulkan 1.2 core |

---

## 1. 一句话定位

Descriptor Indexing 允许在单个 binding 上声明大型 descriptor array（万级以上）、按需 update 部分 element、且允许在 GPU 使用期间继续 update，是 bindless texture / bindless buffer 工程模式的官方基础；它由 `VK_EXT_descriptor_indexing` 引入，Vulkan 1.2 已核心化。[SPEC]

---

## 2. 所属对象链路

```text
VkPhysicalDeviceFeatures2
→ VkPhysicalDeviceDescriptorIndexingFeatures  (查询 feature)
→ VkDescriptorSetLayoutBindingFlagsCreateInfo (bindingFlags per binding)
    → VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT
    → VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT
    → VK_DESCRIPTOR_BINDING_VARIABLE_DESCRIPTOR_COUNT_BIT
→ VkDescriptorSetLayoutCreateInfo (pNext 链接上面)
→ vkCreateDescriptorSetLayout (flags 含 UPDATE_AFTER_BIND_POOL_BIT 的 pool)
→ VkDescriptorSetVariableDescriptorCountAllocateInfo (可选)
→ vkAllocateDescriptorSets
→ vkUpdateDescriptorSets (按需 update 部分 element)
→ vkCmdBindDescriptorSets
→ Shader: texture2D t[]; SamplerState s[]; ... nonuniformEXT indexing
```

### 上游依赖

- 设备必须支持 `VK_EXT_descriptor_indexing` 或 Vulkan 1.2 + `descriptorIndexing` feature。[SPEC]
- 对应 feature bit 必须在 `VkPhysicalDeviceDescriptorIndexingFeatures` 中开启（`shaderSampledImageArrayNonUniformIndexing` / `shaderStorageBufferArrayNonUniformIndexing` / `descriptorBindingPartiallyBound` / `descriptorBindingUpdateAfterBind` / `descriptorBindingVariableDescriptorCount` 等）。[SPEC]
- Descriptor pool 创建时必须使用 `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT`，才能容纳 update-after-bind 的 set。[SPEC]

### 下游影响

- Pipeline layout 兼容性规则在 update-after-bind / variable count 下有特殊限制。[SPEC]
- Shader 中的 `nonuniformEXT` 修饰符必须与对应的 `*NonUniformIndexing` feature bit 匹配。[SPEC]
- Descriptor set 容量上限由 `maxPerSetDescriptors` 与各 binding `maxDescriptorArrayLength`（厂商查询项）共同决定。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPhysicalDeviceDescriptorIndexingFeatures`
- `VkPhysicalDeviceDescriptorIndexingProperties`
- `VkDescriptorSetLayoutBindingFlagsCreateInfo`
- `VkDescriptorBindingFlags`
- `VkDescriptorSetVariableDescriptorCountAllocateInfo`
- `VkDescriptorSetLayoutBindingFlagsCreateInfo`（pNext 附加到 `VkDescriptorSetLayoutCreateInfo`）

### 常用 API

| API | 作用 |
|---|---|
| `vkGetPhysicalDeviceFeatures2` | 通过 pNext 查询 `VkPhysicalDeviceDescriptorIndexingFeatures`。[SPEC] |
| `vkGetPhysicalDeviceProperties2` | 查询 `maxPerSetDescriptors` / `maxUpdateAfterBindDescriptorsInAllPools` 等。[SPEC] |
| `vkCreateDescriptorSetLayout` | 通过 pNext 链接 `VkDescriptorSetLayoutBindingFlagsCreateInfo`，开启 binding flag。[SPEC] |
| `vkCreateDescriptorPool` | 必须设置 `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT` 才能分配 update-after-bind set。[SPEC] |
| `vkAllocateDescriptorSets` | 通过 pNext 附加 `VkDescriptorSetVariableDescriptorCountAllocateInfo` 指定每个 set 的 variable binding 实际长度。[SPEC] |
| `vkUpdateDescriptorSets` | 对 partially-bound / update-after-bind 的 binding 按需 update 部分 element。[SPEC] |
| `vkCmdBindDescriptorSets` | 绑定 bindless descriptor set；non-uniform 索引在 shader 中由 `nonuniformEXT` 表达。[SPEC] |

### 关键 Binding Flag

| Flag | 含义 | 必需 feature |
|---|---|---|
| `VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT` | binding 中允许部分 element 未 update，shader 订阅前需保证不访问未 update 项。[SPEC] | `descriptorBindingPartiallyBound` |
| `VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT` | binding 允许在 set 被 command buffer 引用期间继续 update。[SPEC] | `descriptorBindingUpdateAfterBind` |
| `VK_DESCRIPTOR_BINDING_VARIABLE_DESCRIPTOR_COUNT_BIT` | 该 binding 是 set 中最后一个，实际 descriptor 数量在 allocate 时通过 `VkDescriptorSetVariableDescriptorCountAllocateInfo` 决定，可小于 layout 上限。[SPEC] | `descriptorBindingVariableDescriptorCount` |
| `VK_DESCRIPTOR_BINDING_UPDATE_UNUSED_WHILE_PENDING_BIT` | 允许在 GPU 使用期间 update 未被使用的 element（弱化的 update-after-bind）。[SPEC] | `descriptorBindingUpdateUnusedWhilePending` |

### 相关扩展 / 版本

- `VK_EXT_descriptor_indexing`（最初扩展，2019）。
- Vulkan 1.2 核心化：通过 `VkPhysicalDeviceVulkan12Features` 字段访问等价 feature；不再需要 pNext 扩展结构体。[SPEC]
- `VK_KHR_maintenance4` / Vulkan 1.3：放宽了部分 descriptor 兼容性，影响 bindless 实践。
- `VK_EXT_non_uniform_qualifier`：早期使 `nonuniformEXT` 可用的扩展（已被 descriptor_indexing + Vulkan 1.2 取代）。

---

## 4. 标准使用流程

```text
1. 查询设备能力
   → vkGetPhysicalDeviceFeatures2 (pNext: VkPhysicalDeviceDescriptorIndexingFeatures)
       检查：descriptorBindingPartiallyBound / descriptorBindingUpdateAfterBind /
            descriptorBindingVariableDescriptorCount /
            shaderSampledImageArrayNonUniformIndexing / shaderStorageBufferArrayNonUniformIndexing
   → vkGetPhysicalDeviceProperties2 (pNext: VkPhysicalDeviceDescriptorIndexingProperties)
       检查：maxPerSetDescriptors / maxUpdateAfterBindDescriptorsInAllPools

2. 启用 feature
   → Vulkan 1.2: 在 VkDeviceCreateInfo 的 pNext 中附加 VkPhysicalDeviceVulkan12Features
       descriptorIndexing = VK_TRUE
       shaderSampledImageArrayNonUniformIndexing = VK_TRUE
       descriptorBindingPartiallyBound = VK_TRUE
       descriptorBindingUpdateAfterBind = VK_TRUE
       descriptorBindingVariableDescriptorCount = VK_TRUE
   → 或 Vulkan 1.0/1.1 + VK_EXT_descriptor_indexing: 使用 VkPhysicalDeviceDescriptorIndexingFeatures

3. 创建 DescriptorSetLayout
   → 填写 VkDescriptorSetLayoutBinding[]（descriptorCount = 上限，对 variable binding 是最大值）
   → 通过 VkDescriptorSetLayoutBindingFlagsCreateInfo::pBindingFlags 给每个 binding 指定 flag
       PARTIALLY_BOUND | UPDATE_AFTER_BIND
       最后一个 binding 可加 VARIABLE_DESCRIPTOR_COUNT
   → VkDescriptorSetLayoutCreateInfo::pNext = &bindingFlagsInfo
   → vkCreateDescriptorSetLayout

4. 创建 DescriptorPool
   → VkDescriptorPoolCreateFlags 必须包含 VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT
   → poolSize 按 type 累计容量（注意上限是 maxUpdateAfterBindDescriptorsInAllPools）
   → vkCreateDescriptorPool

5. 分配 DescriptorSet
   → VkDescriptorSetAllocateInfo pNext 附加 VkDescriptorSetVariableDescriptorCountAllocateInfo
       为 variable binding 指定实际长度
   → vkAllocateDescriptorSets

6. 按 need-based update
   → vkUpdateDescriptorSets 只 update 实际用到的 element（partially bound 语义）
   → update-after-bind 允许在 GPU 使用期间继续 update 未使用或允许更新的 slot

7. 绑定并使用
   → vkCmdBindDescriptorSets（一次绑定，所有 draw 共享 bindless 资源）
   → shader 中 texture2D t[]; t[nonuniformEXT(material_id)].Sample(...)
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkPhysicalDeviceDescriptorIndexingFeatures::descriptorBindingPartiallyBound` | 必须为 VK_TRUE 才能使用 `PARTIALLY_BOUND` flag。[SPEC] | 未启用该 feature 就在 bindingFlags 中使用 `PARTIALLY_BOUND`，导致 validation error。[TOOL] |
| `VkPhysicalDeviceDescriptorIndexingFeatures::descriptorBindingUpdateAfterBind` | 必须为 VK_TRUE 才能使用 `UPDATE_AFTER_BIND` flag。[SPEC] | 启用 `UPDATE_AFTER_BIND` 但 pool 未设置 `UPDATE_AFTER_BIND_BIT`。[TOOL] |
| `VkPhysicalDeviceDescriptorIndexingFeatures::descriptorBindingVariableDescriptorCount` | 必须为 VK_TRUE 才能 allocate 时指定实际 count。[SPEC] | variable binding 没有放在 layout 最后一个 binding 上。[TOOL] |
| `VkPhysicalDeviceDescriptorIndexingFeatures::shaderSampledImageArrayNonUniformIndexing` | shader 中 `nonuniformEXT` 修饰 sampled image array 索引必须开启。[SPEC] | 用了 `nonuniformEXT` 但未启用对应 feature bit。[TOOL] |
| `VkDescriptorSetLayoutBindingFlagsCreateInfo::pBindingFlags` | 每个 binding 对应一个 flag；`bindingCount` 必须与 `VkDescriptorSetLayoutCreateInfo::bindingCount` 一致。[SPEC] | flag 数组长度与 binding 数组不匹配。[TOOL] |
| `VkDescriptorSetLayoutBinding::descriptorCount`（对 variable binding） | 这是上限；实际数量在 allocate 时由 `VkDescriptorSetVariableDescriptorCountAllocateInfo` 决定。[SPEC] | 误把 layout 中的 descriptorCount 当作 set 实际长度。[ENGINE] |
| `VkDescriptorSetVariableDescriptorCountAllocateInfo::pDescriptorCounts` | 对每个 set 给出 variable binding 的实际长度；非 variable binding 的 set 应填 0。[SPEC] | 数组长度与 allocate 的 set 数量不一致。[TOOL] |
| `VkDescriptorPoolCreateFlags` | update-after-bind 必须包含 `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT`。[SPEC] | pool flag 与 layout flag 不匹配导致 allocate 失败。[TOOL] |

---

## 6. 正确性检查点

### Feature 查询阶段

- [ ] `vkGetPhysicalDeviceFeatures2` 是否通过 pNext 拿到了 `VkPhysicalDeviceDescriptorIndexingFeatures`？
- [ ] 是否检查了每一个要使用的 feature bit（partial / update-after-bind / variable count / non-uniform indexing）？
- [ ] Android 上是否区分 Adreno / Mali / Xclipse 驱动版本对应能力差异？

### Layout 创建阶段

- [ ] `VkDescriptorSetLayoutBindingFlagsCreateInfo::bindingCount` 是否等于 `VkDescriptorSetLayoutCreateInfo::bindingCount`？
- [ ] 启用了 `PARTIALLY_BOUND` 的 binding 是否在 feature 中开启了 `descriptorBindingPartiallyBound`？
- [ ] 启用了 `UPDATE_AFTER_BIND` 的 binding 是否在 feature 中开启了 `descriptorBindingUpdateAfterBind`？
- [ ] 使用 `VARIABLE_DESCRIPTOR_COUNT` 的 binding 是否是 layout 中最后一个 binding？
- [ ] 是否所有 binding 的 flag 都在合法组合内（spec 表格 `Valid Combinations of VkDescriptorBindingFlagBits`）？

### Pool 创建阶段

- [ ] Pool 是否设置了 `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT`？
- [ ] Pool 容量是否超过 `maxUpdateAfterBindDescriptorsInAllPools`？

### Allocate 阶段

- [ ] `VkDescriptorSetVariableDescriptorCountAllocateInfo::descriptorSetCount` 是否与 `VkDescriptorSetAllocateInfo::descriptorSetCount` 一致？
- [ ] Variable binding 的实际 count 是否 ≤ layout 中声明的最大值？

### Update 阶段

- [ ] Partially bound 的 binding，shader 是否会在 update 之前访问对应 element？
- [ ] Update-after-bind 的写入是否违反 in-flight 同步规则（同 element 同时 update + 访问）？

### Shader 阶段

- [ ] 使用 `nonuniformEXT` 修饰的索引是否在 feature 中启用了对应的 `*NonUniformIndexing` bit？
- [ ] 数组大小是否超过 `maxDescriptorArrayLength` 或厂商属性限制？

---

## 7. 高频错误

1. 启用 `PARTIALLY_BOUND` flag 但未在 device 启用 `descriptorBindingPartiallyBound`。[TOOL]
2. 启用 `UPDATE_AFTER_BIND` 但 pool 未设置 `UPDATE_AFTER_BIND_BIT`。[TOOL]
3. Variable count binding 没有放在 layout 最后一个 binding 上。[SPEC]
4. Shader 中使用 `nonuniformEXT` 但未启用对应 `*NonUniformIndexing` feature bit。[TOOL]
5. 在 GPU 仍在访问某 element 时 update 同一 element（即便是 update-after-bind 也禁止）。[SPEC]
6. `VkDescriptorSetLayoutBindingFlagsCreateInfo::bindingCount` 与 layout 的 binding 数量不一致。[TOOL]
7. Pool 容量超过 `maxUpdateAfterBindDescriptorsInAllPools`，导致 allocate 失败。[SPEC]
8. Bindless array 过大触发 driver crash（移动端尤其常见）。[ANDROID]
9. Pipeline layout 跨 layout 兼容性误判：update-after-bind layout 与普通 layout 不可互换。[SPEC]
10. `pImmutableSamplers` 与 bindless combined image sampler 混用导致 validation error。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkDescriptorSetLayoutCreateInfo-flags-03000`：binding flag 与 feature bit 对应。
- `VUID-VkDescriptorSetLayoutBindingFlagsCreateInfo-bindingCount-03004`：bindingCount 与 layout 一致。
- `VUID-VkDescriptorSetLayoutCreateInfo-pNext-03071`：variable count binding 必须在最后。
- `VUID-VkDescriptorPoolCreateInfo-flags-03000`：update-after-bind pool flag。
- `VUID-VkWriteDescriptorSet-dstSet-02747`：update-after-bind 同步。
- `VUID-vkCmdDraw-None-02695`：non-uniform indexing feature 未启用。
- Pipeline layout compatibility 错误（update-after-bind 与普通 layout 不兼容）。

### RenderDoc / AGI

- RenderDoc: 查看 descriptor set 的 binding 内容，验证 partially bound 元素是否实际 update。
- AGI: 检查 descriptor binding 是否匹配 shader 访问；non-uniform indexing 的资源是否正确。
- 在 AGI 的 Descriptor tab 查看每个 array element 指向的 image / buffer。

### 日志 / 代码检查

- 检查 `VkDeviceCreateInfo::pNext` 中是否同时附带了 Vulkan12Features 或 DescriptorIndexingFeatures。
- 对比每个 binding 的 flag 与启用的 feature bit。
- 对比 shader reflection 中的 `nonuniformEXT` 使用与启用的 feature bit。
- 检查 allocate 时 `pDescriptorCounts` 是否对应每个 set（包括非 variable 的 set 填 0）。

---

## 9. 生命周期风险

### 创建时机

- Layout / pool / set 的创建顺序与普通 descriptor 一致。
- Feature 必须在 device 创建时一次性启用，运行期不能补充。

### 使用时机

- Update-after-bind：descriptor set 被 command buffer 录制引用后，仍可 update 未被使用的 element；但已被使用的 element 在 GPU 完成前不可 update。[SPEC]
- Partially-bound：未 update 的 element 在 shader 访问前必须确保不被实际读取（如通过 draw indirect 的 mask 或 shader 内 branch）。[SPEC]

### 销毁阶段

- Pool 与 set 销毁需等待所有 in-flight command buffer 完成。[SPEC]
- Variable count set 的实际长度不影响销毁路径。

### in-flight 风险

- Update-after-bind 不等于任意时刻可写：同一 element 在被某次 submit 访问期间，不能被另一次 update 写入；需要应用层维护版本或双缓冲。[SPEC]
- Partially-bound set 中未 update 的 element 若被 shader 访问，行为未定义（移动端可能直接 GPU hang）。[ANDROID]

---

## 10. 同步风险

### CPU-GPU 同步

- Update-after-bind 的 update 是 CPU 侧操作；不需要 fence 等待，但应用必须自行保证不同时 update 同一 element 与访问。[SPEC]
- Variable count 的 set 在 allocate 时确定 count，运行期不可改变。

### GPU-GPU 同步

- Descriptor 内引用的资源（image / buffer）依然需要 barrier / semaphore 管理访问顺序。
- Non-uniform indexing 不引入额外同步；shader 内 divergent 访问由 GPU 处理。

### 资源访问同步

- Image descriptor 的 imageLayout 仍必须与实际 layout 一致。
- Storage image / storage buffer 的 bindless 写入后续读取需 barrier。
- Bindless 场景下大量 array element 共享 binding，barrier 范围需谨慎。

---

## 11. Android 注意点

### Adreno（Qualcomm）

- 较新驱动（Adreno 7xx 系列 + 较新 driver）支持 descriptor indexing 与 non-uniform indexing。[ANDROID]
- 早期 Adreno 6xx 驱动可能未开启 `descriptorBindingUpdateAfterBind`，需运行期查询。[ANDROID]
- Bindless array 建议控制在数千级别，过大数组在某些驱动版本上触发性能 cliff 或 crash。[ANDROID]
- 推荐优先使用 `PARTIALLY_BOUND` + `UPDATE_AFTER_BIND`，比纯 variable count 更稳。[ENGINE]

### Mali（Arm）

- Mali Valhall / Gen5 驱动支持 descriptor indexing，但 `descriptorBindingUpdateAfterBind` 与 `descriptorBindingPartiallyBound` 的稳定性因 driver 版本差异较大。[ANDROID]
- Mali 鼓励使用 bindless（如 "descriptor buffers" / "Bifrost tiling"），但 Vulkan path 上仍以 descriptor indexing 为标准路径。[ANDROID]
- 注意 `maxPerSetDescriptors` 在 Mali 上通常低于桌面端；bindless array 大小应基于 property 而非写死。[ANDROID]

### Xclipse（Samsung / AMD）

- Xclipse 2（基于 RDNA2）支持完整 descriptor indexing；Xclipse 1 支持有限。[ANDROID]
- 验证 feature bit 必须在目标设备实测，不能假设。[ANDROID]

### 通用建议

- Android 必须运行期查询 `VkPhysicalDeviceDescriptorIndexingFeatures`，不能假设支持。[ANDROID]
- 推荐为不支持 descriptor indexing 的设备保留 fallback path（per-material descriptor set + 标准 update）。[ENGINE]
- 在低 RAM 设备上，bindless 大数组需配合 sub-allocation，避免每 element 独占 buffer。[ENGINE]

---

## 12. 性能注意点

### CPU 侧

- Bindless 显著降低每帧 `vkUpdateDescriptorSets` 与 `vkCmdBindDescriptorSets` 调用次数（一次绑定，全程复用）。[ENGINE]
- `PARTIALLY_BOUND` 允许只 update 实际使用的 element，避免 update 全量。[ENGINE]
- Variable count 可在运行期调整 set 容量，避免重创建 layout。[GUIDE]

### GPU 侧

- `nonuniformEXT` 修饰符允许 divergent 索引，但会增加 register pressure 与 texture fetch 延迟；滥用会触发性能 cliff。[HEUR]
- Bindless texture array 在桌面 GPU 上接近零成本，移动端仍有 cache miss 风险。[ENGINE]
- 大型 storage buffer bindless array 应配合 `vkCmdBindDescriptorSets` 一次绑定，避免多次切换。

### 移动端

- 移动端 GPU（Mali / Adreno）的 descriptor cache 有限，bindless array 推荐控制在 driver 实测安全范围。[ANDROID]
- Non-uniform indexing 在移动 GPU 上的发散成本高于桌面；尽量在同一 warp/wavefront 内复用相同索引。[HEUR]
- Update-after-bind 在移动端 driver 实现质量差异大，应作为可降级 feature 而非硬依赖。[ANDROID]

---

## 13. 专家经验

**经验**：
Bindless 是现代渲染引擎（如 Unreal Nanite、AAA 引擎材质系统）的基础设施。典型工程模式：

1. 单个全局 descriptor set（set index 0），包含一个大数组：
   - `texture2D g_Textures[] : register(space0);`（或等价 GLSL）
   - `SamplerState g_Samplers[];`
   - `RWByteAddressBuffer g_Buffers[];`
2. Layout 启用 `PARTIALLY_BOUND | UPDATE_AFTER_BIND`，最后一个 binding 启用 `VARIABLE_DESCRIPTOR_COUNT`。
3. Pool 创建时设置 `UPDATE_AFTER_BIND_BIT`，按预期资源量 × 类型计算容量。
4. 资源加载时只 update 对应 slot；unload 时可 leave stale（partially bound 允许）。
5. Shader 通过 material index / instance index 访问：`g_Textures[nonuniformEXT(material.texture_id)]`。
6. 一次 `vkCmdBindDescriptorSets` 在 frame 开始绑定，所有 draw 共享。

**适用条件**：
- 中型以上渲染项目，材质 / 资源数量大（数百以上）。
- 桌面 GPU 或较新移动 GPU（Adreno 7xx+、Mali Valhall+）。
- 需要降低 CPU 侧 descriptor 维护开销。

**不适用情况**：
- 老旧 Android 设备驱动不支持 descriptor indexing，应保留 fallback path。
- 简单 demo 或单一 shader 项目，引入 bindless 反而增加复杂度。
- 移动端某些 driver 版本对 `UPDATE_AFTER_BIND` 实现不稳定，应降级为传统 update。

**来源**：`[ENGINE][TOOL][ANDROID]`

---

## 14. 相关 API 卡片

- `descriptor_set_layout.md`
- `descriptor_pool.md`
- `descriptor_set.md`
- `descriptor_update.md`
- `../06_pipeline/pipeline_layout.md`

---

## 15. 需要回查官方文档的情况

1. `VkDescriptorBindingFlagBits` 的合法组合表（spec 中 "Valid Combinations of VkDescriptorBindingFlagBits"）。
2. `VK_EXT_descriptor_indexing` 附录中各 feature bit 的精确依赖关系（如 non-uniform indexing 是否要求对应 array feature）。
3. Pipeline layout compatibility 在 update-after-bind / variable count 下的精确规则。
4. `VkPhysicalDeviceDescriptorIndexingProperties` 中各 property 的精确含义与厂商支持矩阵。
5. Android 各 GPU 厂商（Qualcomm / Arm / Samsung）最新 driver release note 中 descriptor indexing 的稳定性说明。
6. Vulkan 1.2 核心化与 `VK_EXT_descriptor_indexing` 在 feature 结构体上的等价映射。
7. `nonuniformEXT` 在 SPIR-V 中等价于 `OpDecorate ... NonUniform`，与对应 feature bit 的精确对应关系。
8. Update-after-bind 与 timeline semaphore / `VK_KHR_synchronization2` 的交互规则。

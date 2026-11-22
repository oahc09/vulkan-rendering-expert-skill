# API Card: VkImageMemoryBarrier

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkImageMemoryBarrier` |
| 常用 API | `vkCmdPipelineBarrier`（imageMemoryBarrierCount / pImageMemoryBarriers） |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkImageMemoryBarrier` 是 `vkCmdPipelineBarrier` 中专用于 image 的 barrier，既同步 image 的 memory access，也同步 image layout 状态，是处理 texture 读写切换、attachment layout transition 和 queue family ownership transfer 的核心结构。[SPEC]

---

## 2. 所属对象链路

```text
Image 生产阶段（如 COLOR_ATTACHMENT_OUTPUT + COLOR_ATTACHMENT_WRITE）
→ vkCmdPipelineBarrier(pImageMemoryBarriers = [VkImageMemoryBarrier])
→ Image 消费阶段（如 FRAGMENT_SHADER + SHADER_READ）
→ 或 Queue Family A release → Queue Family B acquire
```

### 上游依赖

- 已创建并绑定内存的 `VkImage`。[SPEC]
- 对于 attachment，需要已知 render pass / dynamic rendering 的格式与 usage。[SPEC]
- 对于 sampled image，需要已知 descriptor / shader 中的 image layout 要求。[SPEC]

### 下游影响

- 决定 image 在下一阶段的 layout 和可读/可写性。[SPEC]
- 影响 render pass attachment 的 load/store 行为以及 tile-based GPU 的 resolve 开销。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImageMemoryBarrier`
- `VkImageSubresourceRange`
- `VkImageLayout`
- `VkPipelineStageFlags` / `VkAccessFlags`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier` | 通过 `imageMemoryBarrierCount` / `pImageMemoryBarriers` 提交 image barrier。[SPEC] |
| `vkCmdPipelineBarrier2`（Vulkan 1.3 / synchronization2） | 使用 `VkImageMemoryBarrier2` 提供更细粒度控制。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_synchronization2` / Vulkan 1.3 提供 `VkImageMemoryBarrier2` 与扩展 layout / stage / access flag。[SPEC]
- `VK_KHR_maintenance2` / 1.1 引入 `VK_IMAGE_LAYOUT_DEPTH_READ_ONLY_STENCIL_ATTACHMENT_OPTIMAL` 等专用 layout。[SPEC]

---

## 4. 标准使用流程

```text
确定 image 当前 layout 与目标 layout
→ 确定 producer stage/access 与 consumer stage/access
→ 构造 VkImageSubresourceRange（aspect / baseMip / levelCount / baseArray / layerCount）
→ 构造 VkImageMemoryBarrier（oldLayout / newLayout / src/dst stage access / subresourceRange）
→ 在 producer 命令后、consumer 命令前调用 vkCmdPipelineBarrier
→ 后续命令使用 newLayout
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `oldLayout` | 在布局值不被忽略的真实 transition 中，必须匹配所覆盖 subresource 的实际 layout，或以 `VK_IMAGE_LAYOUT_UNDEFINED` 允许丢弃；equal-layout 例外见后述合同。[SPEC] | 填写错误的 oldLayout，导致 validation error 或数据损坏。[TOOL] |
| `newLayout` | Consumer 期望的 layout；常见如 `SHADER_READ_ONLY_OPTIMAL`、`COLOR_ATTACHMENT_OPTIMAL`、`TRANSFER_DST_OPTIMAL`、`PRESENT_SRC_KHR`。[SPEC] | sampled image 使用 `COLOR_ATTACHMENT_OPTIMAL` 或 attachment 使用 `SHADER_READ_ONLY_OPTIMAL`。[TOOL] |
| `srcStageMask` / `dstStageMask` | 控制 layout transition 前后的执行依赖。[SPEC] | 使用 `ALL_COMMANDS_BIT` 导致性能损失；或 stage 与 access 不匹配。[HEUR] |
| `srcAccessMask` / `dstAccessMask` | 控制 memory availability / visibility；layout transition 本身通常需要 src access 包含对应写入。[SPEC] | 存在需要 availability 的先前写入且未由有效依赖覆盖时，遗漏相应 source access 会产生 hazard；不能仅凭 srcAccess 为空判错。[TOOL] |
| `subresourceRange` | 精确指定 mip level / array layer / aspect mask。[SPEC] | `aspectMask` 遗漏 `DEPTH_BIT` 或 `STENCIL_BIT`；mip level 范围未覆盖实际使用区域。[TOOL] |
| `srcQueueFamilyIndex` / `dstQueueFamilyIndex` | 用于 queue family ownership transfer；未 transfer 时通常设为 `QUEUE_FAMILY_IGNORED`。[SPEC] | 需要 ownership transfer 时设为 `QUEUE_FAMILY_IGNORED`，导致跨 queue 数据竞争。[TOOL] |
| `image` | 必须是已创建且绑定内存的 image handle。[SPEC] | image 已销毁或尚未绑定内存。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 先判断布局值是否被忽略；否则 oldLayout 是否匹配覆盖范围的实际状态或合法选择 UNDEFINED discard？
- [ ] `newLayout` 是否符合 consumer 的使用方式？
- [ ] `subresourceRange` 是否覆盖目标 mip/array/aspect？
- [ ] 是否需要 queue family ownership transfer？

### 使用阶段

- [ ] Barrier 是否放在 producer 命令之后、consumer 命令之前？
- [ ] `srcAccessMask` 是否包含 producer 的写入 access？
- [ ] `dstAccessMask` 是否包含 consumer 的读取/写入 access？
- [ ] 对真实 transition，覆盖的 subresource 是否在执行后按 newLayout 使用；布局忽略分支是否保留原实际状态？

### 销毁阶段

- 该命令本身无独立销毁阶段；image 销毁需等待 GPU 完成。[SPEC]

---

## 7. 高频错误

1. `oldLayout` 与 image 实际 layout 不符，或错误地使用 `UNDEFINED` 丢弃了仍需保留的内容。[TOOL]
2. `newLayout` 与后续 consumer 需要的 layout 不一致，例如 present 前未转换到 `PRESENT_SRC_KHR`。[TOOL]
3. `subresourceRange.aspectMask` 对 depth/stencil image 只填 `COLOR_BIT`。[TOOL]
4. 存在需提供 availability 的先前写入却未建立相应依赖；不能只凭 srcAccessMask 为空判错，首次使用无先前写入与其他已建立依赖须分开判断。[TOOL]
5. 在 render pass 内部对 attachment 做 layout transition，应使用 subpass description / dependency 中的 layout 字段。[TOOL]
6. 跨 queue family transfer 只做了 release 没做 acquire，或 family index 填反。[TOOL]
7. 对 swapchain image 做 barrier 时未等待 acquire semaphore。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkImageMemoryBarrier-oldLayout-01208`：在布局不被忽略时，oldLayout 或 newLayout 为 COLOR_ATTACHMENT_OPTIMAL 要求 image 创建时含 COLOR_ATTACHMENT usage。实际旧布局匹配是另一个条件。 [官方 VkImageMemoryBarrier 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkImageMemoryBarrier.html)。[SPEC]
- 跨 queue family 所有权转移需匹配 release/acquire 的范围与 queue family 索引；并区分普通 family、IGNORED、EXTERNAL 和 FOREIGN 的适用条件。 [官方 VkImageMemoryBarrier 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkImageMemoryBarrier.html)。[SPEC]
- `VUID-VkImageMemoryBarrier-subresourceRange-01486`：subresourceRange.baseMipLevel 必须小于 image 创建时的 mipLevels；aspectMask 合法性另行检查。 [官方 VkImageMemoryBarrier 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkImageMemoryBarrier.html)。[SPEC]
- 按 `vkCmdPipelineBarrier` 官方 Valid Usage 检查 stage/access 与 queue capability；layout 与 image usage 约束在 `VkImageMemoryBarrier` 中逐项检查，不能拼接省略前导零的 VUID。

### RenderDoc / AGI

- RenderDoc 可展示每次 image barrier 的 old/new layout、stage/access、subresource range。[TOOL]
- AGI 可观察 layout transition 是否造成 GPU 气泡或额外 bandwidth。[TOOL]

### 日志 / 代码检查

- 检查 barrier 前后 image layout 的使用是否一致。
- 检查 `subresourceRange` 的 mip/array/aspect 是否遗漏。
- 检查 swapchain image 的 acquire/present semaphore 与 barrier 顺序。

---

## 9. 生命周期风险

### 创建时机

- 在 command buffer 录制时构造并提交；image 本身需预先创建。[SPEC]

### 使用时机

- 任何需要改变 image layout 或同步 image 读写的地方：render target → sampled texture、copy source/target、present 前等。[SPEC]

### 销毁时机

- 随 command buffer 生命周期；image 销毁需 fence 保证。[SPEC]

### in-flight 风险

- Barrier 只保证同 queue 内录制顺序；image 被跨 queue 使用时需要访问同步；必要的ownership transfer不能与semaphore二选一。[SPEC]
- Swapchain image 在 acquire semaphore signal 前不应被写入。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Image barrier 不涉及 CPU 同步；需要 CPU 等待时使用 fence / timeline semaphore。[SPEC]

### GPU-GPU 同步

- 同 queue 内由 `srcStageMask` / `dstStageMask` 建立执行依赖。[SPEC]
- 跨 queue 需先 semaphore 同步，必要时再做 ownership transfer。[SPEC]

### 资源访问同步

- Layout transition 是 memory dependency 中的操作，不单独证明依赖充分；它在 availability 后、visibility 前执行，可能读写指定 subresource，须建立覆盖真实访问的依赖。[SPEC]
- Depth/stencil image 的 aspect 需要单独考虑；某些 layout 仅对 depth 或 stencil 有效。[SPEC]
- Multi-plane image 的 aspect mask 需按 format 规范填写。[SPEC]

---

## 11. Android 注意点

- Android 上 swapchain image 的 `PRESENT_SRC_KHR` layout transition 应预先正确录制，并在GPU执行中于present使用之前完成，并与 acquire semaphore 配对。[ANDROID]
- Tile-based GPU 对 render pass 外 layout transition 敏感；尽量把 attachment 的 transition 放在 subpass dependency 中，避免额外的 store/resolve。[ENGINE][ANDROID]
- 横竖屏切换后 swapchain image 已变化，旧 image 的 layout 状态不再相关，应按新 swapchain 重新处理。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Image barrier 录制开销低，但每个 barrier 都意味着一次 GPU 状态变更点。[ENGINE]

### GPU 侧

- Layout transition 可能引发 decompress / resolve / cache flush；全屏 image 的 transition 代价高。[ENGINE]
- 避免在同一帧内对同一张 image 反复切换 layout；尽量合并使用阶段。[HEUR]

### 移动端

- Tile-based GPU 上，render pass 结束时的 layout transition 会触发 tile memory 的 store/resolve；使用 `BY_REGION_BIT` 和 subpass dependency 可减少开销。[ENGINE][ANDROID]
- 尽量减少每帧对 backbuffer / depth texture 的 layout transition 次数。[ENGINE]

---

## 13. 专家经验

**经验**：
把 image layout 当作“该 image 在接下来一段使用周期内的状态”来管理，而不是“每次使用都转一次”。例如 shadow map 在渲染深度后可直接转为 `SHADER_READ_ONLY_OPTIMAL` 供 lighting pass 采样，中间避免转回 `UNDEFINED` 或 `GENERAL`。对于 transient attachment，考虑使用 `VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL`（1.3 / synchronization2）减少不必要的 layout 种类。

**适用条件**：
频繁在 attachment 和 sampled image 之间切换的 texture；需要 queue family transfer 的资源；multi-planar 或 depth/stencil image。

**不适用情况**：
Buffer 同步（用 `VkBufferMemoryBarrier`）；同 render pass 内 attachment 同步（用 subpass dependency）；跨设备共享（用 external memory / semaphore）。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `pipeline_barrier.md`
- `synchronization2.md`
- `event.md`
- `semaphore.md`
- `fence.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`
- `../06_pipeline/graphics_pipeline.md`

---

## 14.5 Vulkan 1.4 变更

Vulkan 1.4 对 Image Memory Barrier 的主要变更：

### Synchronization2 promote 为 mandatory feature

1.4 设备保证支持 `VkImageMemoryBarrier2`，不能假定 `oldLayout`/`newLayout` 在所有 feature 条件下与 1.0 相同；但 mandatory feature 仍需通过 `VkPhysicalDeviceVulkan13Features.synchronization2 = VK_TRUE`（或 `VkPhysicalDeviceSynchronization2Features.synchronization2`）显式启用后才能使用 sync2 API。`synchronization2` 是 Vulkan 1.3 promote，字段位于 `VkPhysicalDeviceVulkan13Features`，**不在 `VkPhysicalDeviceVulkan14Features`**。[SPEC]

### Dynamic Rendering Local Read

1.4 将 local read promote 为 mandatory feature（保证被支持，仍需启用 `VkPhysicalDeviceVulkan14Features.dynamicRenderingLocalRead`）。input attachment 的 layout transition **不会自动处理**，应用必须显式录制 image memory barrier：[SPEC]

- attachment image使用合法的VK_IMAGE_LAYOUT_RENDERING_LOCAL_READ_KHR或VK_IMAGE_LAYOUT_GENERAL；需要改变layout时显式transition，并单独满足访问同步；
- 在 input-reading draw 与 attachment-writing draw 之间通过 by-region pipeline barrier 建立可见性（`vkCmdPipelineBarrier2` + `VkDependencyInfo`，`dependencyFlags` 含 `VK_DEPENDENCY_BY_REGION_BIT`）；
- depth/stencil aspect 与 MSAA attachment 的 local read 受 `VkPhysicalDeviceVulkan14Properties.dynamicRenderingLocalReadDepthStencilAttachments` / `dynamicRenderingLocalReadMultisampledAttachments` 两个独立字段限制，需运行时查询（不存在独立的 `VkPhysicalDeviceDynamicRenderingLocalReadPropertiesKHR` 结构）。

### Host Image Copy 交互

`VK_EXT_host_image_copy` 在 Vulkan 1.4 中将 API promote 进 core，但 `hostImageCopy` feature **仍为可选**（非 mandatory），必须通过 `VkPhysicalDeviceHostImageCopyFeaturesEXT` 查询并在 `VkDeviceCreateInfo.pNext` 中启用后才能调用 `vkTransitionImageLayoutEXT` / `vkCopyImageToImageEXT` 等 host 侧 API。[SPEC]

---

## 15. 需要回查官方文档的情况

1. 具体 format 支持的 image layout 列表及 layout 转换限制。
2. Depth/stencil image 的 aspect mask 与 `VK_IMAGE_LAYOUT_DEPTH_ATTACHMENT_STENCIL_READ_ONLY_OPTIMAL` 等专用 layout 的合法组合。
3. Queue family ownership transfer 中 release barrier 与 acquire barrier 的精确匹配规则。
4. Swapchain image 在 `vkAcquireNextImageKHR` 和 `vkQueuePresentKHR` 之间的 layout 要求。
5. Multi-planar format 的 aspect mask 与 plane 映射关系。
6. Vulkan 1.3 / synchronization2 中新增 layout（如 `ATTACHMENT_OPTIMAL`、`READ_ONLY_OPTIMAL`）的兼容性。


<a id="image-layout-sync-contract"></a>

## 18. Image subresource与layout执行合同

**条件/正常路径**：按aspect/mip/layer跟踪layout和owner，transition是device执行操作，不是录制/submit前host已完成的状态。仅在布局值未被忽略的真实 transition 中，UNDEFINED 作为旧 layout 允许丢弃旧内容（may discard，不保证清零或修改），但不免除与仍在访问该 image 的执行 hazard；equal-layout 忽略分支不因此 discard。color、depth/stencil、multi-plane分别遵守合法aspect与layout/usage要求。[SPEC]

**失败边界**：VkImageMemoryBarrier2中srcQueueFamilyIndex==dstQueueFamilyIndex且oldLayout==newLayout时布局值被忽略，内容保留且实际布局不变；旧VkImageMemoryBarrier在synchronization2 feature启用时也有该分支，未启用时不可机械套用。即使两值均UNDEFINED，忽略分支也不是discard；仍需正确内存依赖。不要把通用“old必须等于当前”错误套到这条特例。跨queue同family仍需semaphore，不需要family ownership；跨family保内容遵循 [maintenance ownership合同](synchronization2.md#maintenance-ownership-contract)。外部API所有权不是此内部例外。[SPEC]

**回退**：无法证明旧内容有效时明确discard后重新初始化，不能伪造旧layout；不支持独立depth/stencil layout或局部slice行为时选受支持的完整subresource路径。仅改变descriptor里声明的layout不会执行transition。

**验证**：检查只改变一个mip/layer、错误aspect、discard但仍有旧writer、equal-layout Sync2、跨queue acquire→transition→consumer及present前执行顺序；保存subresource状态轨迹而非仅一张image一个全局layout。

固定依据：Vulkan 1.4.368，commit fa30d4e312e843193601be7cb926c7e25d9ec885；[synchronization#synchronization-image-layout-transitions](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#synchronization-image-layout-transitions)；[synchronization#synchronization-image-barrier2-ignored-layout](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#synchronization-image-barrier2-ignored-layout)；[synchronization#synchronization-image-memory-barriers](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc#synchronization-image-memory-barriers)。[SPEC]

<a id="delivery19-image-layout-ignored-discard"></a>

### delivery19-image-layout-ignored-discard

先判 barrier 类型、实际 synchronization2 启用与 queue-family/layout 值，
再判断布局是否被忽略。忽略分支不执行 transition，不改变实际布局，不丢弃内容，
也不自动消除 RAW/WAW/WAR；不同 family 不可套 equal-family 特例。
真实 transition 则作用于精确 aspect/mip/layer 范围，在 availability 后、
visibility 前执行；未覆盖 subresource 不随之更新。UNDEFINED 允许 discard
旧内容，不表示此前访问已退休，也不能单凭它证明新写入与旧访问无竞争。
此处不展开 3D slice/maintenance9、ownership 或全部 layout/usage 条件。

固定 Vulkan-Docs `fa30d4e312e843193601be7cb926c7e25d9ec885`（1.4.368）
`chapters/synchronization.adoc` SHA256
`7748c88e48007820179681ef4f82c1d2244afc5482b5bc0c13d370ef64821909`，
anchors `synchronization-image-layout-transitions`、
`synchronization-image-barrier2-ignored-layout`、
`synchronization-image-barrier-ignored-layout`。正文解释不是 GPU 实测，
不能替代其他版本 validusage 的条件审查。

另以 API 1.4.309 validusage SHA256
`f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7`
核对 `VUID-VkImageMemoryBarrier2-oldLayout-01197` 与
`VUID-VkImageMemoryBarrier-oldLayout-01197`：其 oldLayout 要求带有
ownership transfer 或真实 layout transition 的条件，不是无条件匹配断言。
两版本来源分别绑定，不推断其全部条款完全相同或整族验收完成。

### Vulkan 1.4.369：只读布局按使用范围判断

先确定该命令是否忽略 layout，再检查不被忽略的 `oldLayout` 或 `newLayout` 是否为 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL`。相等 queue-family 索引与相等 layout 时，`VkImageMemoryBarrier2` 忽略 layout；旧 `VkImageMemoryBarrier` 还要求已启用 `synchronization2`。不能把这个例外机械套到 host image layout transition。这里仅讨论 usage 条件，合法 aspect、实际旧 layout 和同步责任仍需独立检查。[SPEC]

| 范围 | 1.4.369 的 usage 判据 |
|---|---|
| 非仅 stencil，或没有独立 stencil usage | 普通 image usage 至少有 `SAMPLED` 或 `INPUT_ATTACHMENT`（01211） |
| 包含 stencil 且创建时提供独立 stencil usage | stencil usage 自身至少有 `SAMPLED` 或 `INPUT_ATTACHMENT`（12565） |
| 同时含 depth/stencil 且独立 stencil usage 生效 | 上述两条分别成立；一个掩码的 flag 不能替另一条 |
| 仅 stencil 且独立 stencil usage 生效 | 该布局检查使用 stencil usage；普通 usage 不因 01211 另行要求采样 |

例如，真实过渡中普通 usage 可采样但独立 stencil usage 不可采样且不是 input attachment，depth-only 不因该 stencil 条件被拒；把 stencil 纳入就触发 12565。旧 VVL 可能给出未分配诊断名；应核对条件与完整对象/范围，不仅搜索编号。[SPEC][TOOL]

固定来源：[共用 VU](https://github.com/KhronosGroup/Vulkan-Docs/blob/33d3353757d83d6aca683120114fe74cc4eaf8fb/chapters/commonvalidity/image_layout_transition_common.adoc#L155-L181)；[VVL 变更](https://github.com/KhronosGroup/Vulkan-ValidationLayers/commit/b6fed572c965e19868d71b3d67026d5ae225ee19)。

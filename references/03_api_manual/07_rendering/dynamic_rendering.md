# API Card: VK_KHR_dynamic_rendering

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 |
| Vulkan 对象 | `VkRenderingInfo` / `VkPipelineRenderingCreateInfo` |
| 常用 API | `vkCmdBeginRendering` / `vkCmdEndRendering` |
| 适用平台 | 通用（需设备支持） |
| 来源等级 | `[SPEC] [GUIDE] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.3 core / `VK_KHR_dynamic_rendering` |

---

## 1. 一句话定位

`VK_KHR_dynamic_rendering` 允许在不创建 `VkRenderPass` 和 `VkFramebuffer` 的情况下，通过 command buffer 中的 `VkRenderingInfo` 直接描述 rendering attachment，从而降低渲染通道对象的管理复杂度。[SPEC]

---

## 2. 所属对象链路

```text
VkImageView（color / depth / resolve）
→ VkRenderingInfo（attachment 描述 + rendering area）
→ vkCmdBeginRendering
→ Draw Calls
→ vkCmdEndRendering
```

### 上游依赖

- 已创建并 transition 到合适 layout 的 image view。[SPEC]
- 执行需要 graphics pipeline 的 draw 时，通过 `VkPipelineRenderingCreateInfo` 提供 color/depth format 与 view mask；仅 attachment CLEAR/LOAD、无 draw 的 begin/end 不需要 pipeline。[SPEC]
- 所选 core/扩展入口可用，且 device 创建时显式启用 dynamicRendering feature；仅启用扩展不够。[SPEC]

### 下游影响

- 直接替代 `vkCmdBeginRenderPass` + `VkFramebuffer` 的组合。
- 发生 draw 时，还须满足所用 graphics pipeline 的 rendering format 等兼容条件。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkRenderingInfo`
- `VkRenderingAttachmentInfo`
- `VkPipelineRenderingCreateInfo`
- `VkPhysicalDeviceDynamicRenderingFeatures`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdBeginRendering` | 在 command buffer 中开始 dynamic rendering instance。[SPEC] |
| `vkCmdEndRendering` | 结束 dynamic rendering instance。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.3 core。
- `VK_KHR_dynamic_rendering` 扩展。
- `VK_KHR_dynamic_rendering_local_read` 等扩展可进一步扩展 local attachment 读取能力。

---

## 4. 标准使用流程

```text
检查 dynamicRendering feature 是否启用
→ 创建 graphics pipeline 时通过 pNext 提供 VkPipelineRenderingCreateInfo（color/depth format / view mask）
→ 每帧构造 VkRenderingInfo，包含 color/depth attachment 的 VkRenderingAttachmentInfo
→ 确保 attachment image layout 合法
→ vkCmdBeginRendering
→ 绑定 pipeline、descriptor、vertex buffer
→ vkCmdDraw / vkCmdDrawIndexed
→ vkCmdEndRendering
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `colorAttachmentCount` / `pColorAttachments` | 使用 pipeline draw 时，按对应 feature/扩展条件检查与 pipeline colorAttachmentCount 的兼容性。[SPEC] | 数量或 format 与 pipeline 不匹配。[TOOL] |
| `pDepthAttachment` / `pStencilAttachment` | depth/stencil image view 与 format；可分别指定或共用。[SPEC] | 只提供 depth 而 pipeline 期望 depth+stencil。[TOOL] |
| `imageView` / `imageLayout` | attachment 必须实际处于声明的合法 layout；普通颜色附件可用 COLOR_ATTACHMENT_OPTIMAL 或 GENERAL，其他 layout 需逐项满足对应条件。[SPEC] | layout 未 transition 或 transition 遗漏。[TOOL] |
| `loadOp` / `storeOp` / `clearValue` | 同 render pass 的 attachment load/store op。[SPEC] | CLEAR 时未填 clear value。[TOOL] |
| `resolveMode` / `resolveImageView` | MSAA resolve 配置。[SPEC] | resolve image 的 sample count 或 format 不兼容。[TOOL] |
| `renderArea` | 影响 load/store 范围，移动端尤为重要。[SPEC] | 设置过大导致不必要带宽。[TOOL] |
| `layerCount` / `viewMask` | multiview 相关。[SPEC] | 与 pipeline view mask 不一致。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否启用 `dynamicRendering` feature？
- [ ] Pipeline 创建时是否提供 `VkPipelineRenderingCreateInfo`？
- [ ] Pipeline 的 color/depth format 与运行时 attachment format 是否一致？

### 使用阶段

- [ ] Attachment image view 是否已 transition 到对应 layout？
- [ ] `colorAttachmentCount` 与 pipeline 一致？
- [ ] `loadOp`/`storeOp` 是否符合预期？
- [ ] 是否在 `vkCmdBeginRendering` 后、draw 前正确绑定 graphics pipeline？

### 销毁阶段

- [ ] Dynamic rendering 无独立对象销毁；image/view/memory 及所有引用仍需满足完成、生命周期与同步规则。[SPEC]

---

## 7. 高频错误

1. 未启用 `dynamicRendering` feature 就调用 `vkCmdBeginRendering`。[TOOL]
2. Pipeline 未提供 `VkPipelineRenderingCreateInfo`，导致 format 不匹配。[TOOL]
3. Attachment image layout 仍是 `SHADER_READ_ONLY_OPTIMAL` 等非法状态。[TOOL]
4. `colorAttachmentCount` 与 pipeline 创建时不一致。[TOOL]
5. 忘记 `vkCmdEndRendering` 或在不合适的 command buffer 状态结束。[TOOL]
6. Depth/stencil format 与 `pDepthAttachment`/`pStencilAttachment` 描述不一致。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdBeginRendering-*`：feature、attachment、layout 合法性。
- `VUID-VkPipelineRenderingCreateInfo-*`：pipeline 创建时 format 与 view mask 规则。

### RenderDoc / AGI

- 查看 dynamic rendering 的 attachment、load/store op、render area。
- 检查 pipeline 的 rendering format 是否与运行时匹配。

### 日志 / 代码检查

- 检查 feature 启用代码。
- 检查 pipeline 创建 info 的 pNext 链。
- 检查 attachment image layout transition 路径。

---

## 9. 生命周期风险

### 创建时机

- 无需创建 `VkRenderPass` / `VkFramebuffer`，但 pipeline 创建时需提供 rendering format 信息。[SPEC]

### 使用时机

- 在 command buffer 录制阶段动态构造 `VkRenderingInfo` 并调用 begin/end。[SPEC]

### 销毁时机

- 无独立对象销毁；依赖的 image view 仍需按生命周期管理。[SPEC]

### in-flight 风险

- 录制的 `VkRenderingInfo` 结构体只需在 `vkCmdBeginRendering` 调用期间有效；但引用的 image view 必须保持有效直到 command buffer 完成。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- begin/end 不替代 host 的 command-buffer 外部同步、资源生命周期或提交完成等待。[SPEC]

### GPU-GPU 同步

- Dynamic rendering 与外部命令的同步需使用 pipeline barrier 或 event，因为没有 render pass subpass dependency。[SPEC]

### 资源访问同步

- begin/end 不提供传统 render pass 的隐式 layout transition；须按实际访问与作用域显式转换并同步。[SPEC]
- Resolve 操作由 `vkCmdEndRendering` 触发，需保证 resolve target 已准备好接收写入。[SPEC]

---

## 11. Android 注意点

- Dynamic rendering 在 Android 上可减少 `VkRenderPass`/`VkFramebuffer` 对象数量，但需确认版本/扩展路径可用且 dynamicRendering feature 已启用。[ANDROID]
- Tile-based GPU 仍受 load/store op 与 render area 影响；不要误以为 dynamic rendering 消除了这些约束。[ANDROID][ENGINE]
- 不同驱动的成本需在同一工作负载下测量，不能凭 GPU 品牌推断传统或 dynamic 路径更快。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 减少 render pass / framebuffer 对象的创建与缓存管理，降低初始化复杂度。[ENGINE]
- 每帧构造 `VkRenderingInfo` 的开销通常很小，但仍可复用静态结构体。[HEUR]

### GPU 侧

- 两路径可满足相同输出合同，但对象数或本例像素相同不证明 GPU 执行成本相同；load/store、同步与 tile 驻留影响需独立测量。[ENGINE]
- 普通 dynamic rendering 不通过传统 subpass dependency 描述跨 scope 依赖；按实际访问和执行路径选择 pipeline barrier、semaphore 等适当同步机制，不能把所有跨 pass 同步统一为 barrier。过宽依赖的性能影响需实测。[HEUR]

### 移动端

- 对只需单 pass 或简单后处理链的场景，dynamic rendering 能减少对象开销；复杂多 subpass 场景仍需评估是否 traditional render pass 更优。[ENGINE]
- 尽量合并 dynamic rendering 调用，减少 begin/end 切换。[HEUR]

---

## 13. 专家经验

**经验**：
Dynamic rendering 适合“attachment 组合多变、render pass 对象爆炸”的场景，例如每帧根据后处理链动态选择 color/depth target。它不搬运传统 render pass 的隐式 transition 或 subpass dependency；attachment 描述转到录制时，实际 layout 与访问依赖仍需显式维护。对移动端 tile-based GPU，仍需像对待 render pass 一样关注 load/store op 和 render area。

**适用条件**：
后处理链灵活、VR/多视图渲染、希望减少 render pass/framebuffer 对象数量的项目。

**不适用情况**：
需要大量 subpass 内部 input attachment 读取且驱动对传统 render pass 优化更好的场景；或目标设备不支持该扩展。

**来源**：`[ENGINE][GUIDE][SPEC]`

---

## 14. 相关 API 卡片

- `render_pass.md`
- `attachment_load_store.md`
- `render_target_layout.md`
- `../04_buffer_image_memory/framebuffer.md`
- `../06_pipeline/graphics_pipeline.md`
- `../04_buffer_image_memory/image_view.md`
- `../08_synchronization/pipeline_barrier.md`
- `../08_synchronization/image_memory_barrier.md`

---

## 14.5 Vulkan 1.4 变更

Vulkan 1.4 对 Dynamic Rendering 的主要变更：

### Dynamic Rendering Local Read promote 为 mandatory feature

Vulkan 1.4 将 `VK_KHR_dynamic_rendering_local_read` 的 API promote 进 core，并提升为 mandatory feature（保证被支持）。[SPEC]

- 1.4 设备保证支持 local read，无需运行时查询 feature 即可确认能力存在；但 **仍需在 `VkDeviceCreateInfo.pNext` 中通过 `VkPhysicalDeviceVulkan14Features.dynamicRenderingLocalRead = VK_TRUE` 显式启用** 后才能调用相关 API。[SPEC]
- 仅基础 color attachment local read 在所有 1.4 设备上保证可用；**depth/stencil aspect 与 MSAA attachment 的 local read 受独立 properties 限制** —— 两个能力字段位于 `VkPhysicalDeviceVulkan14Properties`：`dynamicRenderingLocalReadDepthStencilAttachments` 与 `dynamicRenderingLocalReadMultisampledAttachments`，需运行时查询。[SPEC]
- 允许在 dynamic rendering pass 内读取同 pass 的 attachment 作为 input attachment，无需创建 `VkFramebuffer` 或显式 `VkRenderPass`。[SPEC]
- shader 仍使用 `subpassInput` / `subpassLoad` 机制（非普通 texture read），并通过 `VkRenderingInputAttachmentIndexInfo` 建立 input attachment index 映射。[SPEC]

### 新增 API

| API / 结构体 | 说明 | 来源 |
|---|---|---|
| `VkRenderingAttachmentLocationInfo` | 控制 attachment 在 fragment shader 中的 location 映射 | [SPEC] |
| `VkRenderingInputAttachmentIndexInfo` | 为 input attachment 提供 index 映射 | [SPEC] |

### Local Read 使用流程

```text
Step 1: device 创建时启用 dynamicRenderingLocalRead feature
  -> VkPhysicalDeviceVulkan14Features.dynamicRenderingLocalRead = VK_TRUE
  -> 通过 pNext 加入 VkDeviceCreateInfo

Step 2: pipeline 创建
  -> VkPipelineRenderingCreateInfo 中声明 input attachment 的 format

Step 3: 录制 dynamic rendering pass
  -> vkCmdBeginRendering
  -> vkCmdSetRenderingAttachmentLocations / vkCmdSetRenderingInputAttachmentIndices（按需）
  -> fragment shader 通过 subpassInput + subpassLoad 读取同 pass attachment
  -> vkCmdEndRendering

Step 4: 同步
  -> attachment image 必须处于 VK_IMAGE_LAYOUT_RENDERING_LOCAL_READ_KHR
  -> 通过 by-region pipeline barrier（vkCmdPipelineBarrier2 + VkDependencyInfo）
     在 input-reading draw 与 writing draw 之间建立可见性
  -> depth/stencil 与 MSAA local read 需先查询 properties 确认可用
```

无需在 pipeline 创建时指定 render pass，`VkPipelineRenderingCreateInfo` 即可。[SPEC]

### 与 Vulkan 1.3 的兼容性

- dynamicRendering 在 1.3 已必须支持，仍需通过 `VkPhysicalDeviceVulkan13Features.dynamicRendering` 显式启用；1.3 上的 local read 使用已查询支持并启用的 KHR 扩展与对应 feature。[SPEC]
- 1.4 保证基础 local read 支持，通过 `VkPhysicalDeviceVulkan14Features.dynamicRenderingLocalRead` 显式启用；dynamicRendering 仍在 Vulkan13Features 中启用。depth/stencil / MSAA local read 继续受 properties 限制。依据：[Vulkan 1.4](https://docs.vulkan.org/refpages/latest/refpages/source/VK_VERSION_1_4.html)、[Feature Requirements](https://docs.vulkan.org/spec/latest/chapters/features.html#features-requirements)。[SPEC]
- 满足原版本有效使用与 feature 启用条件的路径仍需在目标 1.4 实现回归验证，不因版本号免除兼容检查。[GUIDE]

---

## 15. 需要回查官方文档的情况

1. Dynamic rendering 与 multiview / fragment shading rate 的交互。
2. `VkPipelineRenderingCreateInfo` 中 `viewMask` 与 `VkRenderingInfo` 的匹配规则。
3. Secondary command buffer 中使用 dynamic rendering 的限制。
4. Local read 扩展（`VK_KHR_dynamic_rendering_local_read`）的引入条件。
5. 不同驱动对 dynamic rendering 的 tile memory 优化差异。

<a id="delivery19-color-attachment-family"></a>

## 16. Delivery19 单颜色附件生命周期：有界 L1/L2

范围固定为 core 1.3 dynamic rendering、单 graphics queue、单 sample、单 layer、
viewMask=0、无 resolve、无 depth/stencil、无 draw/shader 的颜色附件。使用
R8G8B8A8_UNORM 的完整 4×4 区域验证 CLEAR→STORE→LOAD→STORE→copy/readback。
这不是完整光栅、blend/depth/stencil/MSAA/FSR/FDM 或 local-read 语义验收。

### 能力与附件准入

- 版本或扩展路径可用不等于 feature 已启用。记录实际查询的 dynamicRendering
  与 device 创建启用值；缺失事实是 UNKNOWN，明确不支持则拒绝该路径。
  调用要求 `VUID-vkCmdBeginRendering-dynamicRendering-06446`。
- 查询所选 format、tiling、usage 联合配置及 sample 支持，再创建资源；不能用
  单独支持某 flag 推断组合支持。普通颜色 image/view 需要 COLOR_ATTACHMENT
  usage，后续 copy-source 还需 TRANSFER_SRC。view format、subresource、实际
  extent、layer/sample 与所声明范围必须匹配，不默许未知扩展配置。
- renderArea offset 非负、extent 非零，且 offset+extent 不超过对应 view
  的实际尺寸和设备 framebuffer limits。以所用 mip 尺寸判断，不用原图宽高
  掩盖小 mip 越界。本族只验证单 mip/full-area 路径，不外推多层/设备组。
- imageLayout 必须既是该 attachment 类型的合法 layout，也与 image 当前
  状态一致。GENERAL 是合法普通颜色路径之一；本轮实际路径使用
  COLOR_ATTACHMENT_OPTIMAL。begin/end 不做隐式 layout transition。

| 1.4.309 受限义务 | 精确依据 |
|---|---|
| renderArea 非负 offset | `VUID-VkRenderingInfo-pNext-06077` / `06078` |
| 非零 width/height | `VUID-VkRenderingInfo-None-08994` / `08995` |
| view 宽高包含 renderArea | `VUID-VkRenderingInfo-pNext-06079` / `06080` |
| 不超过 framebuffer limits | `VUID-VkRenderingInfo-pNext-07815` / `07816` |
| 颜色附件 usage | `VUID-VkRenderingInfo-colorAttachmentCount-06087` |
| 禁止 UNDEFINED/transfer/shader-read 等 attachment layout | `VUID-VkRenderingAttachmentInfo-imageView-06135` |
| 实际颜色 view layout 与声明一致 | `VUID-vkCmdBeginRendering-pRenderingInfo-09592` |

VUID 判断限于已知条件；未覆盖的格式、resolve、多视图及扩展组合返回 UNKNOWN，
不因不在小型拒绝表中而判定合法。content 是否定义与同步是否充分另行处理。

### 内容与同步，不能用一个 PASS 合并

1. 初始 UNDEFINED 可丢弃旧内容，但仍须执行到合法 attachment layout 的转换。
   CLEAR 定义本 renderArea 的内容，不能据此宣称区域外也有确定值。
2. 第一遍 CLEAR+STORE 后，第二遍 LOAD+STORE 保留已有内容；LOAD 不是清屏，
   即使其 clearValue 不同也不得据此替换期望内容。LOAD 的输入内容必须已有
   定义；STORE 本身不会使未定义输入变成有定义结果。
3. 两遍之间需覆盖 color attachment 写→读/写的执行与内存依赖。第二遍结束后，
   通过 attachment写→transfer读依赖及 layout 转换，再 copy 到 host-readable
   buffer、建立 transfer写→host读依赖并等完成。coherent 内存不能替代这些依赖。
4. DONT_CARE load/store 使相关区域内容无法作为确定输出消费；缺少重新定义
   写入时拒绝 readback oracle，而不是把某驱动恰好保留的数据当保证。NONE、
   部分覆盖与跨区域内容追踪不在此受限模型内，不能自动推导。

配对实验先真实查询并显式启用 feature，验证两遍后 16 个像素全部匹配固定
UNORM 色值；另用 renderArea、layout 与 feature 未启用的 Validation 负控。
callback 中止无效 begin 后直接丢弃/reset command buffer，不 end 或 submit
那个无效实例。无期望诊断、错误原始参数或错误像素均不能算成功。
普通 Validation 正常日志不证明所有同步正确；本路径还有显式依赖与数据 oracle，
但未声明完整 SyncVal/GPU-AV、并发宿主或物理 GPU 验收。

### 来源、修正与未验范围

正文依据：[Khronos Vulkan-Docs v1.4.309 renderpass](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/renderpass.adoc)，
Git blob `83a7d8bd4ed10ff3a2cbd55ea5e50aea0a822d72`，涵盖 dynamic rendering、
attachment load/store 与 render area；来源 CC-BY-4.0，本节为释义。生成 VUID
依据为独立 `validusage.json` API 1.4.309，SHA256
`f61afea8ca6097342cae1b65bfab81675ee7fdc2d809403e083329b7d56597a7`。
不得与 1.4.368 全域 inventory 合并成同一规范快照验收分母。

同步纠正旧卡片中“feature或扩展即可”“仅两种layout合法”“STORE自动转换layout”
及某 load/store/subpass 组合必然更省带宽等表述。改动收紧推断，不改变 API。
运行证据仅为 CPU software ICD 正确性，不代表物理 GPU、移动端带宽/功耗或
外部工程收益；全域 VK10、SC、完整光栅管线与原计划盲测/发布门槛仍未完成。

<a id="delivery19-dynamic-draw-family"></a>
## 17. 有 shader/draw 的受限整合合同（v1.0.19）

上一节只验收 attachment CLEAR/LOAD 生命周期，不能证明 graphics pipeline、
vertex/fragment shader 或 draw 实际参与。本合同另接 tests 仓库的
`cases19/dynamic_draw/run.py` 与 `tools/dynamic_draw19.py`：必须真正编译并验证
SPIR-V、创建普通 graphics pipeline、绑定后 draw、同步回读，并逐像素匹配
独立 CPU 参考。仅成功创建 pipeline、零 Validation 错误或单一清屏色不够。

### 准入与解释边界

- 先查询并显式启用 dynamicRendering，选 graphics queue；普通 core 1.3 路径
  不因仅发现扩展名便获准。检查实际 format/usage/sample 支持、framebuffer 与
  viewport 限制，保留查询值和使用值。工具/设备不可用是 NOT_RUN，不是 PASS。
- 本切片限定单个非空 RGBA8_UNORM color view、单样本、单 layer、无 multiview、
  无 resolve、无 depth/stencil、无特殊 attachment 扩展。未知事实返回 UNKNOWN，
  超出切片返回 OUT_OF_SCOPE；不能将其他扩展的例外套进普通路径。
- pipeline 的 `VkPipelineRenderingCreateInfo` 与 begin rendering 的实际
  attachment 数量、格式、viewMask/sample 必须适配。此处未启用
  dynamicRenderingUnusedAttachments，实际非空 view 的 format 必须与
  pipeline 对应 color format 相同；1.4.309 依据为
  `VUID-vkCmdDraw-dynamicRenderingUnusedAttachments-08910`。
- 空 renderPass 的 pipeline 创建成功不是 draw 兼容性证明。pipeline bind、
  viewport/scissor、shader 输出 location、write mask 与真正的 draw 参数
  必须可追溯到本次命令；动态状态仅在被配置为动态时才由命令设置。
- shader 编译/spirv-val 验证与设备运行分别记录，不能把前者当成执行证明。
  shader 文件、SPIR-V、执行源及 runner 的 hash 保留；固定 target 与真实
  glslang/SPIRV-Tools 版本，不能借一个未固定的系统工具声称可重复。

### 输出与故障隔离

受限参考为 4×4 像素棋盘：vertex shader 通过 gl_VertexIndex 形成覆盖画布的
三角形，fragment shader 按窗口坐标输出红/蓝；CPU 按行列计算参考，不能从
实际回读结果反推出期望。保留全部像素，而非仅“图像非黑”或平均颜色。
CLEAR 后 draw 的颜色与清屏不同，可识别 draw 未生效；错误参考必须失败。
颜色输出到 transfer 的依赖、layout 转换、buffer 到 host 的依赖及完成等待
仍不可省，coherent 只处理宿主缓存一致性。

格式不匹配负控必须在实际 vkCmdDraw 获得预期 Validation 诊断，callback
中止无效 void 命令后丢弃该 command buffer，不提交错误实例，不伪造 VkResult。
多余错误、缺少目标错误、非预期工具退出或回读不匹配均失败。通过这一负控
不等于所有 shader 接口、光栅状态、同步或动态渲染扩展组合都已验证。

来源：[Khronos Vulkan-Docs drawing v1.4.309](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/drawing.adoc)，
Git blob `77c199718a6d74d179af4536df47f3cdc5fe25ad`，CC-BY-4.0，本节为释义；
精确 VUID 来自前节固定的独立 1.4.309 validusage.json。实际工具结果与具体
运行范围以配对 tests 证据为准，不用规范链接代替设备验收。此路径仍为 CPU
software ICD 正确性，不宣称物理 GPU、移动端画质/性能、外部工程或盲测完成。

### delivery19-render-organization：受限实际绘制比较

Tests `cases19/render_organization/run.py` 在 CPU ICD 上运行传统 RenderPass → dynamic rendering →传统恢复；同一 vertex/fragment shader、非对称 4×4 图案与逐像素 CPU 参考。两路径均先显式转换至 COLOR_ATTACHMENT_OPTIMAL，再写入并显式转换供拷贝读回；传统 attachment initial/final 保持该 layout。各自 pipeline 合法，不声称两 pipeline/layout 可互换。[ENGINE]

记录的是一次场景创建的 RP/Framebuffer/pipeline 对象与 begin/draw 调用数，不是每帧重建成本、驱动内存或性能。默认保留传统基线；只有调用者明确禁止应用 RP 对象时，才在已通过输出门的候选中选择 dynamic。性能要求返回 NEEDS_MEASUREMENT。缺动态能力会阻塞整个比较，不能据此宣称传统路径不合法；未实测不支持设备回退。[HEUR]

单提交、单颜色附件、单样本，无 subpass/local-read/tile/深度/物理硬件性能结论；两路径错误参考均必须真实失败。原始完整日志与来源哈希由 runner 保留，不把此例当外部工程或全 C2 完成。[ENGINE]

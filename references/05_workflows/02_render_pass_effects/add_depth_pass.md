# Workflow: Add Depth Pass

## 0. 适用范围

### 适用

- 已有基础 color pass，需要新增 depth testing / depth writing。
- 使用传统 `VkRenderPass` 或 `VK_KHR_dynamic_rendering` / Vulkan 1.3 dynamic rendering。
- 需要创建 depth image、depth image view、配置 pipeline depth-stencil state、处理 clear / load / store。

### 不适用

- 纯 2D / UI 渲染，不需要 depth buffer。
- 使用外部引擎已封装好的 depth 处理。
- 需要 stencil 专用功能（本 workflow 以 depth 为主，stencil 仅附带说明）。

---

## 1. 任务目标

在 renderer 中新增含 depth attachment 的渲染能力：

```text
Color Attachment（swapchain / offscreen）
+ Depth Attachment（depth image + view）
→ VkRenderPass 或 Dynamic Rendering Info
→ VkPipeline Depth-Stencil State
→ vkCmdBeginRenderPass / vkCmdBeginRendering
→ Draw with depth test/write
→ End RenderPass / Rendering
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本；是否使用 Dynamic Rendering。
- 输出 color attachment 格式与尺寸。
- 目标 depth format：常用 `VK_FORMAT_D32_SFLOAT`、`VK_FORMAT_D24_UNORM_S8_UINT`、`VK_FORMAT_D16_UNORM`。
- Depth test 需求：`LESS`、`LESS_OR_EQUAL`、`GREATER`、`EQUAL` 等。
- Depth write 需求：是否写入 depth buffer。
- Clear / load / store 策略：每帧 clear、load previous、discard after pass。
- 是否需要 depth image 作为后续 pass 输入（如 shadow / depth prepass visualization）。
- Sample count：是否 MSAA。

---

## 3. 前置检查

- [ ] 已确认目标 depth format 的 `FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
- [ ] 若使用 Dynamic Rendering，已核对 core1.3 或扩展路径，并实际启用 dynamicRendering feature；扩展名可用/启用不等于feature已启用 [SPEC]。
- [ ] Pipeline color attachment format 与输出 color attachment 一致 [SPEC]。
- [ ] RenderDoc / AGI 可查看 depth attachment 内容 [TOOL]。
- [ ] 当前 frame loop 已稳定处理 color attachment layout transition [ENGINE]。
- [ ] 呈现路径的 Android Surface / ANativeWindow 生命周期可追踪；纯 offscreen depth 不要求 Surface。depth image 尺寸策略已确定 [ANDROID]。

---

## 4. Vulkan 对象链路

### RenderPass 路径

```text
Color Attachment Image（swapchain / offscreen）
Depth Attachment Image
→ VkImageView（depth view, aspectMask = DEPTH_BIT 或 DEPTH | STENCIL）
→ VkAttachmentDescription / Reference
→ VkSubpassDescription
→ VkRenderPass
→ VkFramebuffer（color view + depth view）
→ Graphics Pipeline（renderPass + subpass）
→ vkCmdBeginRenderPass（with VkRenderPassBeginInfo / VkClearValue）
→ Draw
→ vkCmdEndRenderPass
```

### Dynamic Rendering 路径

```text
Color Attachment Image
Depth Attachment Image
→ VkImageView
→ VkPipelineRenderingCreateInfo（depthAttachmentFormat）
→ Graphics Pipeline
→ VkRenderingInfo
    → pColorAttachments
    → pDepthAttachment（imageView / imageLayout / loadOp / storeOp / clearValue）
→ vkCmdBeginRendering
→ Draw
→ vkCmdEndRendering
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| depth image | `VkImage` | `DEPTH_STENCIL_ATTACHMENT`（可能附加 `SAMPLED` / `TRANSFER_SRC`） [SPEC] | pass / scene | 是（若尺寸绑定 swapchain） |
| depth image view | `VkImageView` | depth attachment view | 跟随 depth image | 是 |
| depth memory | `VkDeviceMemory` | device-local | 跟随 depth image | 是 |
| render pass（RenderPass 路径） | `VkRenderPass` | color + depth subpass | 跟随输出格式 | 是（若格式/样本数变化） |
| framebuffer（RenderPass 路径） | `VkFramebuffer` | color view + depth view | 跟随 swapchain | 是 |
| pipeline | `VkPipeline` | 含 depth-stencil state | pipeline 生命周期 | 否（通常） |

---

## 6. Pipeline / Descriptor 设计

本 workflow 主要调整 graphics pipeline 的固定功能状态：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | `VkPipelineDepthStencilStateCreateInfo.depthTestEnable` | 是否启用 depth test | Early / Late fragment tests |
| 无 | `VkPipelineDepthStencilStateCreateInfo.depthWriteEnable` | 是否写入 depth | Early / Late fragment tests |
| 无 | `VkPipelineDepthStencilStateCreateInfo.depthCompareOp` | depth 比较函数 | Early / Late fragment tests |
| 无 | `VkPipelineDepthStencilStateCreateInfo.minDepthBounds` / `maxDepthBounds` | depth bounds test（可选） | Early / Late fragment tests |
| 无 | `VkPipelineDepthStencilStateCreateInfo.stencilTestEnable` / `front` / `back` | stencil 测试（可选） | Early / Late fragment tests |

设计说明：

- `depthTestEnable = VK_TRUE` 且 `depthCompareOp = VK_COMPARE_OP_LESS` 是常规前向渲染配置 [HEUR]。
- 透明物体通常在 color pass 中 `depthWriteEnable = VK_FALSE`、`depthCompareOp = VK_COMPARE_OP_LESS_OR_EQUAL`，避免写入 depth 导致后续不透明物体错误 [HEUR]。
- `depthBoundsTestEnable` 需要 physical device 支持并在 device 创建时启用 `depthBounds` feature [SPEC]。
- 普通固定 depth/stencil pipeline 需要有效 pDepthStencilState；graphics pipeline library / extended dynamic state 等例外按实际启用条件核对，不能概括所有 pipeline 都不可为空 [SPEC]。
- Dynamic Rendering 路径下，pipeline 通过 `VkPipelineRenderingCreateInfo.depthAttachmentFormat` 指定 depth format [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous frame / undefined | depth image | `UNDEFINED` → `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | graphics pipeline depth write [SPEC] |
| graphics pipeline depth write | depth image | `DEPTH_STENCIL_ATTACHMENT_WRITE` → shader read / transfer | shadow sampling / debug visualization [SPEC] |
| depth sampling / visualization | 可呈现的 color image | color write → WSI 呈现所需依赖与 `PRESENT_SRC_KHR` | present engine [SPEC] |

必须说明：

- depth image 使用与 aspect、访问和启用特性匹配的合法 attachment layout；`DEPTH_STENCIL_ATTACHMENT_OPTIMAL` 是一种路径，不是唯一枚举。普通 depth attachment 不能直接 present；先采样可视化到可呈现的 color image。[SPEC]
- RenderPass 路径 initialLayout 对应进入时状态，subpass reference layout 对应子通道使用状态，finalLayout 对应离开时状态；可以不同，由 render pass 定义合法自动转换及其依赖，不是三个枚举必须相同 [SPEC]。
- Dynamic Rendering 的 `pDepthAttachment.imageLayout` 须与实际 layout 一致；按路径可用 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL`、满足 separateDepthStencilLayouts 条件的 `DEPTH_ATTACHMENT_OPTIMAL`、满足 synchronization2 条件的 `ATTACHMENT_OPTIMAL`，或允许的 `GENERAL`。读写/只读、stencil 和特性条件逐项核对。[SPEC]
- depth 写入的 producer 采用真实 `EARLY_FRAGMENT_TESTS` / `LATE_FRAGMENT_TESTS`（保守同时覆盖）与 `DEPTH_STENCIL_ATTACHMENT_WRITE`；consumer 是实际采样 shader stage 与 `SHADER_SAMPLED_READ`。按需要执行合法 layout transition（GENERAL 保持也可），核对采样 usage、format 和 descriptor；不能写成 COLOR_ATTACHMENT_OUTPUT。[SPEC]
- `UNDEFINED` 只丢弃内容，不消除旧访问依赖；复用 in-flight depth image 必须先满足同步与生命周期。[SPEC]

---

## 8. 实现步骤

1. **选择 depth format**：
   - 调用 `vkGetPhysicalDeviceFormatProperties` 检查 `VK_FORMAT_D32_SFLOAT`、`VK_FORMAT_D24_UNORM_S8_UINT`、`VK_FORMAT_D16_UNORM` 的 `optimalTilingFeatures` 是否包含 `VK_FORMAT_FEATURE_DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
   - 按设备的实际完整 image-format/usage/sample 查询、精度需求和测量选格式；需要 stencil 时选受支持的组合格式，而非假定 D24_UNORM_S8_UINT 必然支持 [ANDROID]。
2. **创建 depth image**：
   - 填写 `VkImageCreateInfo`：`imageType=2D`、示例extent与color相同，但真正要求是有效尺寸/layers覆盖renderArea/framebuffer、`format`、 `usage=DEPTH_STENCIL_ATTACHMENT`（若需采样则附加 `SAMPLED`）、普通无 mixed-sample 特例路径 samples 与 color attachment/pipeline 一致；检查 imageFormatProperties.sampleCounts 与 framebufferDepthSampleCounts 与 framebufferColorSampleCounts 的交集 [SPEC]。
3. **分配并绑定 memory**：选择符合该 image memoryTypeBits 的 memory type，优先 device-local 而非忽略兼容位，调用 `vkAllocateMemory` 与 `vkBindImageMemory`；或使用 VMA [ENGINE]。
4. **创建 depth image view**：
   - `VkImageViewCreateInfo.viewType=2D`、`format` 与 depth image 一致。
   - `subresourceRange.aspectMask`：纯 depth 填 VK_IMAGE_ASPECT_DEPTH_BIT；组合格式按 attachment/采样用途选择合法 depth/stencil aspect，不是每个组合格式 view 都必需同时含两者 [SPEC]。
5. **RenderPass 路径**：
   - 创建 `VkAttachmentDescription`：color attachment 与 depth attachment，分别指定 `format`、`samples`、`loadOp`、`storeOp`、`initialLayout`、`finalLayout` [SPEC]。
   - 创建 `VkSubpassDescription`，`pDepthStencilAttachment` 指向 depth attachment reference [SPEC]。
   - 创建 `VkRenderPass`，调用 `vkCreateRenderPass` [SPEC]。
   - 创建 `VkFramebuffer`：绑定 color view 与 depth view，尺寸与 render pass 一致 [SPEC]。
6. **Dynamic Rendering 路径**：
   - 无需 `VkRenderPass` / `VkFramebuffer`。
   - 在 pipeline 创建时通过 `VkPipelineRenderingCreateInfo` 指定 `depthAttachmentFormat` [SPEC]。
7. **配置 pipeline depth-stencil state**：
   - 填写 `VkPipelineDepthStencilStateCreateInfo`：`depthTestEnable`、`depthWriteEnable`、`depthCompareOp`、`depthBoundsTestEnable`、`stencilTestEnable` 等 [SPEC]。
   - `depthCompareOp` 由实际深度映射确定，不由左右手坐标系决定；正 Z 常用 clear=1 / LESS，反 Z 常用 clear=0 / GREATER。[ENGINE]
8. **配置 dynamic state**：viewport/scissor 可固定也可动态；若选择动态必须在 draw 前设置。动态 depth bias 需相应 pipeline 配置，不要求所有应用都启用动态状态 [SPEC]。
9. **创建 graphics pipeline**：使用对应 RenderPass 或 `VkPipelineRenderingCreateInfo`，调用 `vkCreateGraphicsPipelines` [SPEC]。
10. **录制 command buffer**：
    - 插入 depth image barrier，转换到 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` [SPEC]。
    - RenderPass 路径：`vkCmdBeginRenderPass`，`pClearValues` 包含 color clear 与 depth clear [SPEC]。
    - Dynamic Rendering 路径：`vkCmdBeginRendering`，`pDepthAttachment` 指定 load/store op 与 clear value [SPEC]。
    - bind pipeline，设置 viewport / scissor，draw。
    - end render pass / rendering。
11. **接入 resize / recreate**：depth image / view / framebuffer 随 swapchain 尺寸重建；pipeline 能否复用取决于 format/sample、renderpass compatibility 和固定 viewport/scissor 等状态，不能仅按 resize 断言不变 [ENGINE]。
12. **接入销毁路径**：先证明所有相关 GPU 访问已结束并处理引用的 command buffer；随后按对象依赖销毁并在 image 销毁后释放绑定 memory。某个固定销毁顺序不能代替 in-flight 退休 [ENGINE]。

---

## 9. Android 注意点

- depth image 尺寸通常与 swapchain extent 一致；rotation / resize 后必须重建 depth image / view / framebuffer [ANDROID]。
- 移动端 Mali/Adreno 对 `D32_SFLOAT` 与 `D16_UNORM` 的带宽与精度权衡不同；对精度要求不高的场景可选 `D16_UNORM` 降低带宽 [ANDROID]。
- pause / resume 不销毁 device，但 surface 销毁后 depth image 等依赖 swapchain 尺寸的资源应随 swapchain 一起销毁 [ANDROID]。
- preTransform 变化后重新核对投影、viewport/scissor、render area、attachments 与 pipeline 固定状态；不能一概保证无需重建 pipeline [ANDROID]。
- AGI 中检查 depth attachment 的 load/store 行为与 bandwidth 开销 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkRenderPassCreateInfo-*`、`VUID-VkPipelineDepthStencilStateCreateInfo-*`、`VUID-vkCmdBeginRendering-*-depth` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 depth attachment 内容、depth test 状态、depth write 状态 [TOOL]。
- [ ] 截图符合预期：遮挡关系正确，近处物体遮挡远处物体。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；输出 depth format、image extent、loadOp / storeOp。
- [ ] 性能指标：
  - 开启 depth test/write 后 GPU frame time 增加在预期范围；
  - 移动端 bandwidth 无异常峰值；
  - AGI 中 depth attachment 的 load/store 开销合理 [TOOL]。
- [ ] resize / rotation / pause / resume 后 depth 渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **Depth format 不支持**：未检查 `vkGetPhysicalDeviceFormatProperties`，在 Mali/Adreno 上某些 format 不可用 [ANDROID]。
2. **Image usage 缺失**：创建 depth image 时未加 `VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
3. **Aspect mask 错误**：depth image view 的 `aspectMask` 未包含 `DEPTH_BIT` [SPEC]。
4. **Pipeline depth state 未配置**：普通固定状态路径缺少所需depth/stencil state；动态状态/library例外须按实际启用条件核对 [SPEC]。
5. **Depth compare op 错误**：例如透明物体未关闭 depth write，导致视觉错误 [HEUR]。
6. **Layout transition 缺失**：depth image 实际 layout 与所声明/合法 depth attachment layout 不符；GENERAL 等满足条件的其他布局也可用 [SPEC]。
7. **Load/store op 错误**：需要初始值时未CLEAR，或LOAD读取未保存/未同步的内容；正确prepass等LOAD并不违法 [HEUR]。
8. **Framebuffer attachment 尺寸不匹配**：attachment 有效 extent/layers 未覆盖 framebuffer 或 render area；image 尺寸不完全相同不必然非法 [SPEC]。
9. **Multisample count 不一致**：depth image samples 与 color attachment / pipeline 不一致 [SPEC]。
10. **Dynamic Rendering depth format 不匹配**：`VkPipelineRenderingCreateInfo.depthAttachmentFormat` 与实际 depth image format 不一致 [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / 是否使用 Dynamic Rendering。
- 目标 depth format 与 `vkGetPhysicalDeviceFormatProperties` 输出。
- `VkPipelineDepthStencilStateCreateInfo` 关键字段。
- RenderPass attachment description 或 `VkRenderingInfo` 参数。
- Depth image `VkImageCreateInfo` 参数。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 depth attachment 状态截图。

---

## 15. 需要回查官方文档的情况

1. 不同 GPU 对 depth format 的精度、压缩、tile memory 支持差异。
2. `VK_IMAGE_LAYOUT_DEPTH_STENCIL_READ_ONLY_OPTIMAL` 与 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 在 depth sampling 场景下的精确区别。
3. Dynamic Rendering 中 `VkPipelineRenderingCreateInfo` 与 `VkRenderingInfo` 的 depth attachment 一致性规则。
4. 含 stencil 的 depth format 在 image view aspect mask 与 shader 采样时的限制。
5. Android 特定设备在 rotation 后 depth attachment 重建的最佳实践。

<a id="stable-shadow-workflow"></a>
## 稳定 Shadow Map / CSM 基线

不依赖 Ray Query。先固定 [深度与材质合同](../../02_core_mental_model/render_target_model.md#lighting-temporal-data-contract)，再选择方向光单 map/CSM 或局部灯 atlas；不要求所有引擎同时实现所有选项。[ENGINE]

1. 从光源影响范围和受光体生成投影者集合，包含屏外遮挡者。不要直接复用相机剔除列表；记录动画、cutout、LOD 和资源 generation。
2. 固定正/反 Z、光源投影与比较方向；clear=1/LESS 与 clear=0/GREATER 是常见对应，不由坐标手性推断。检查 attachment/sample format features；compare sampler 的 filter 支持单独查询。
3. CSM 明确分割距离、每 cascade 分辨率、稳定投影范围与 light-space texel snapping；跨级联过渡区域避免跳变。移动灯光/内容仍会使缓存失效，稳定化不能冻结错误阴影。[ENGINE]
4. depth/slope/normal bias 由场景尺度、投影与采样足迹决定，验证 acne 与 peter-panning；反 Z 的符号按实际映射核对，禁止全场景固定魔数。atlas 划区、guard texel 和 PCF 范围避免跨 tile 渗漏。
5. depth-only graphics pipeline / alpha-cutout fragment、depth attachment/view、sampler/descriptor→draw caster→EARLY/LATE_FRAGMENT_TESTS 写→实际 shading shader 采样。保留 sampled usage 与 store 内容；若使用 transient/lazy 路径不得假设深度仍可跨 pass 采样。[SPEC]
6. 按灯光/材质/alpha/动画/LOD/相机分割改变失效缓存；新尺寸、新 generation 准备好再切换，旧 image 等所有消费者完成后退休。

固定序列：静止、慢平移、移动灯光、薄片、远近尺度、屏外投影者与第二视图。输出线性 depth、cascade ID、bias、visibility、atlas 边界，分别记录漏光、自阴影、悬浮阴影与闪烁。通过真实 depth→color 可视化/读回，不将普通 depth image 转 PRESENT。源规范：[深度测试](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/fragops.adoc)。


<a id="delivery19-depth-occlusion-chain"></a>
## Delivery19：深度遮挡 → color resolve → fragment 后处理

测试仓 `cases19/depth_msaa_sample/run.py` 对一个实际跨功能场景做正反验证：4× D32_SFLOAT depth 与4× RGBA8 color 共同参与第一次 dynamic rendering，颜色再 resolve 为1×并由后处理片段采样。不是只 clear 深度或把深度状态打印出来。[ENGINE]

1. 准入先查 depth format optimal DEPTH_STENCIL_ATTACHMENT 完整 usage/sample 组合、framebufferDepthSampleCounts、color对应组合、实际dynamicRendering enable、pipeline与view format及样本一致、push-constant容量/阶段。当前限定不启用dynamicRenderingUnusedAttachments，不对mixed-sample/library例外泛化。[SPEC]
2. depth clear=1、test/write开启、LESS比较 incoming与stored；先draw非对称部分区域近色，后draw全区域远色。片段shader显式写gl_FragDepth=0.25/0.75并按固定区域discard；没有early_fragment_tests声明。第二次draw在近区域被拒绝，其余区域填远色。颜色随后AVERAGE resolve，保持相同resolve view供fragment采样和非恒等通道重排。[ENGINE]
3. depth首次转换到DEPTH_STENCIL_ATTACHMENT_OPTIMAL，目标 EARLY|LATE_FRAGMENT_TESTS 与 depth/stencil attachment read/write；同一rendering中的重叠draw遵守depth测试次序，不能拿COLOR_ATTACHMENT_OUTPUT作为depth写入stage。颜色resolve→sampling仍用color-output-write→fragment-read。最后只读回最终颜色全16像素；未单独捕获depth或每个MSAA样本。[SPEC][TOOL]
4. 合法关闭depthTest、其余draw/输入不变的因果控制应让后绘制远色覆盖近色，从而真实输出与正常目标不符，即使Validation完全安静；对照独立CPU状态机确认改变后的全部像素。另有wrong-output故意改参考，分别验证状态语义与oracle，不把两种负控混淆。[TOOL]
5. 单独把pipeline depthAttachmentFormat改为D16而实际view仍D32，普通当前路径在draw得到唯一 `VUID-vkCmdDraw-dynamicRenderingUnusedAttachments-08914`；callback中止draw，弃置整CB、不提交非法工作。规范负控不属于GPU故障注入，也不证明非法draw执行结果。[SPEC][TOOL]

回退：若D32/4×不支持，应明确拒绝本限定场景；应用可查询D16等格式及较低样本数后重新建立资源/pipeline合同，并重新验证精度及输出，不能跳过测试后声称同等验收。这里只验证CPU ICD固定普通depth遮挡、显式片段深度与颜色resolve链，不覆盖stencil、depth resolve、depth采样/阴影、反Z/精度、early-fragment-test变体、深度bounds/bias、移动硬件性能、外部工程或Live盲测。原计划完整门槛不变。[ENGINE]

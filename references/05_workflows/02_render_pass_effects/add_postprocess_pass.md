# Workflow: Add Postprocess Pass

## 0. 适用范围

### 适用

- 已有前向/延迟渲染的输出 color image，需要新增后处理阶段：bloom、tonemapping、color grading、blur、distortion、FXAA 等。
- 使用 fullscreen triangle / quad 作为几何体。
- 输入为上一 pass 的 color attachment 或 offscreen image，输出到 swapchain 或另一个 offscreen image。

### 不适用

- 需要 scene geometry 或逐物体计算的 pass（见 `add_depth_pass.md`、`add_texture_sampling_pass.md`）。
- 纯 compute 后处理（见 `../03_compute_workflows/compute_blur_pass.md`、`../03_compute_workflows/compute_write_storage_image.md`）。
- 直接由外部引擎后处理栈处理，无需手动创建 fullscreen pass。

---

## 1. 任务目标

新增一个 fullscreen 后处理 pass：

```text
Previous Pass Output Image
→ Image Barrier（COLOR_ATTACHMENT_OPTIMAL → SHADER_READ_ONLY_OPTIMAL）
→ Sampler + ImageView + DescriptorSet
→ Fullscreen Graphics Pipeline
→ vkCmdDraw(3/6) 或 vkCmdDrawIndexed
→ Output Render Target（swapchain / offscreen）
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- 输入 image 来源：swapchain / offscreen / previous pass color attachment。
- 输出目标：swapchain image / offscreen image / 下一后处理阶段输入。
- 是否使用 RenderPass 或 Dynamic Rendering。
- 是否需要 input attachment（传统 RenderPass subpass input）或 sampled image。
- Fragment shader 需要的输入资源数量：单张 color、depth、multiple RT、uniform parameters。
- 输出尺寸是否固定或随 swapchain 变化。
- 是否允许 compute 路径替代 graphics fullscreen pass。

---

## 3. 前置检查

- [ ] 输入 image 已创建且 `usage` 包含 `VK_IMAGE_USAGE_SAMPLED_BIT` 或作为 input attachment [SPEC]。
- [ ] 输出 image 已创建且 `usage` 包含 `VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT` [SPEC]。
- [ ] 上一 pass 已完成对输入 image 的写入，并通过 barrier / semaphore 同步 [SPEC]。
- [ ] shader 编译链路可用，fullscreen vertex shader 与 fragment shader 已准备。
- [ ] descriptor 管理可用，可分配/更新 `COMBINED_IMAGE_SAMPLER` 或 `INPUT_ATTACHMENT`。
- [ ] RenderDoc / AGI 可抓帧 [TOOL]。
- [ ] Android Surface / ANativeWindow 生命周期可追踪 [ANDROID]。

---

## 4. Vulkan 对象链路

```text
Previous Pass Output Image
→ VkImageView（sampled view 或 input attachment view）
→ VkSampler（sampled 路径）
→ VkDescriptorSetLayout
→ VkDescriptorSet
→ VkPipelineLayout
→ Fullscreen Graphics Pipeline
    → vertex shader: fullscreen triangle / quad
    → fragment shader: postprocess effect
    → rasterizer: cull off, depth test off
    → color blend: usually disabled or additive
→ VkRenderPass / VkRenderingInfo（output target）
→ VkFramebuffer（RenderPass 路径）
→ Command Buffer
→ Output Render Target
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| input image | `VkImage` | `COLOR_ATTACHMENT | SAMPLED` 或 `INPUT_ATTACHMENT` | previous pass 输出 | 视来源 |
| input image view | `VkImageView` | sampled / input attachment view | 跟随 input image | 视来源 |
| sampler | `VkSampler` | 输入 image 采样 | renderer / pass 生命周期 | 否 |
| output image | `VkImage` | `COLOR_ATTACHMENT` | 当前 pass 输出 | 通常是 |
| output image view | `VkImageView` | color attachment view | 跟随 output image | 通常是 |
| descriptor set | `VkDescriptorSet` | image binding | per-pass / per-frame | 视更新策略 |
| pipeline | `VkPipeline` | fullscreen postprocess | pipeline 生命周期 | 否（通常） |
| framebuffer（RenderPass 路径） | `VkFramebuffer` | output view 绑定 | 跟随 output image | 是 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` | input image view + sampler | Fragment [SPEC] |
| set=0,binding=1 | `COMBINED_IMAGE_SAMPLER`（可选） | additional input（depth、prev frame、LUT） | Fragment [SPEC] |
| set=0,binding=2 | `UNIFORM_BUFFER` / `PUSH_CONSTANT` | postprocess parameters（exposure、threshold、bloom radius） | Fragment [HEUR] |
| set=1,binding=0 | `INPUT_ATTACHMENT`（可选，RenderPass subpass 路径） | previous subpass color attachment | Fragment [SPEC] |

设计说明：

- `COMBINED_IMAGE_SAMPLER` 是通用路径，支持 arbitrary sampling kernel 与多输入 [HEUR]。
- `INPUT_ATTACHMENT` 仅在 RenderPass subpass 内有效，适合需要像素精确对应、不需要自定义采样的场景（如 deferred lighting 读取 G-Buffer） [SPEC]。
- 输出到 swapchain 时，pipeline color attachment format 必须与 swapchain `imageFormat` 一致 [SPEC]。
- Fullscreen vertex shader 通常使用硬编码顶点位置，无需 vertex buffer；也可使用 `vkCmdDraw(3)` 绘制 fullscreen triangle [HEUR]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass color write | input image | `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | postprocess fragment shader [SPEC] |
| previous subpass write | input image（input attachment） | `COLOR_ATTACHMENT_OPTIMAL` 保持，通过 subpass dependency 同步 | next subpass fragment input [SPEC] |
| postprocess fragment write | output image | `UNDEFINED` / `SHADER_READ_ONLY_OPTIMAL` → `COLOR_ATTACHMENT_OPTIMAL` | postprocess color write [SPEC] |
| postprocess fragment write | output image | `COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` / `SHADER_READ_ONLY_OPTIMAL` | present / next pass [SPEC] |

必须说明：

- input image 在 fragment shader 采样前必须转换到 `SHADER_READ_ONLY_OPTIMAL`（sampled 路径） [SPEC]。
- input attachment 路径下，layout 通常为 `COLOR_ATTACHMENT_OPTIMAL` 或 `SHADER_READ_ONLY_OPTIMAL`，具体取决于 RenderPass subpass 配置 [SPEC]。
- output image 在 `vkCmdBeginRenderPass` / `vkCmdBeginRendering` 前需转换到 `COLOR_ATTACHMENT_OPTIMAL` [SPEC]。
- 若使用 compute 路径替代，input/output image layout 可能为 `GENERAL`，需要额外 barrier [SPEC]。

---

## 8. 实现步骤

<a id="color-output-workflow"></a>
### Android色彩输出实施入口

前提：有效输入lease与同步、目标Surface capability已查询；先读[颜色合同](../../02_core_mental_model/render_target_model.md#color-output-contract)及[呈现gate](../../03_api_manual/02_surface_swapchain/swapchain.md#android-color-presentation)，下列步骤不改变其权威规则。

1. 填输入primaries/transfer/range/bitdepth/alpha/参考白；元数据未知时记录假设和待测色条，而非按文件名猜。
2. 指定工作空间和转换：YCbCr采样后的RGB不自动是linear；明确transfer解码、色域映射与中间精度，不用layout transition“改颜色”。
3. 每输出决定tone-mapping owner。A SDR与B HDR/P3可有不同输出pass；不能全局一个HDR bool。仅实际能力允许才启用可选metadata，失败回SDR/标准路径。
4. 检查blend：若在明确线性工作空间用premultiplied source-over，RGB示例为src ONE/dst ONE_MINUS_SRC_ALPHA；alpha累积也应按目标约定配置。Straight输入先按约定转换一次，不对已premultiplied值再乘。此配方不是任意艺术混合的强制规范。
5. 输出编码与attachment固定功能转换配合，避免shader编码后sRGB附件再次编码；compositeAlpha/宿主合成与最终像素约定一致。
6. 固定测试图案：线性灰阶0/0.18/0.5/1、原色块、alpha0/0.5/1边缘，浮点参考误差示例1e-6、8-bit量化比较示例1/255；这些是隔离数学fixture容差，实际GPU/色域处理另预先定义阈值，不能宣布屏幕色准。
7. resize/display/format/crop改变后失效相关pipeline/descriptor/颜色capability缓存，旧generation资源按实际GPU/WSI完成退休。
8. 分别保存离屏数值、真实宿主透明合成与设备HDR观察；截图不是面板测量。无设备保持NOT RUN，不将CPU公式测试称GPU渲染。

### 通用后处理步骤


1. **编写 fullscreen shader**：
   - Vertex shader 生成 fullscreen triangle / quad，输出 UV（注意 Vulkan UV 原点与翻转） [SPEC]。
   - Fragment shader 实现后处理算法，采样输入 image。
2. **创建 sampler**：根据后处理需求设置 `magFilter`、`minFilter`、`mipmapMode`、`addressModeUVW`；通常为 `LINEAR` + `CLAMP_TO_EDGE` [HEUR]。
3. **创建 descriptor set layout**：
   - sampled 路径：`COMBINED_IMAGE_SAMPLER` + `UNIFORM_BUFFER` / push constant。
   - input attachment 路径：`INPUT_ATTACHMENT` + `UNIFORM_BUFFER` / push constant [SPEC]。
4. **创建 pipeline layout**：组合 descriptor set layouts 与 push constant ranges [SPEC]。
5. **创建 graphics pipeline**：
   - vertex input：无 binding / attribute（fullscreen triangle）或简单 quad layout。
   - input assembly：`TRIANGLE_LIST` 或 `TRIANGLE_STRIP`。
   - rasterizer：`cullMode = NONE`。
   - depth-stencil：`depthTestEnable = VK_FALSE`，`depthWriteEnable = VK_FALSE` [HEUR]。
   - color blend：通常 disabled；additive bloom 可启用 additive blend [HEUR]。
   - dynamic state：`VIEWPORT`、`SCISSOR` 至少启用 [SPEC]。
6. **准备 input image view**：确保 input image 已创建对应 view，aspect mask = `COLOR_BIT` [SPEC]。
7. **准备 output image / view**：输出到 swapchain 时使用 swapchain image view；输出到 offscreen 时创建对应 image [SPEC]。
8. **更新 descriptor set**：填写 `VkDescriptorImageInfo`（image view + sampler + layout），调用 `vkUpdateDescriptorSets` [SPEC]。
9. **录制 command buffer**：
   - 插入 input image barrier：`COLOR_ATTACHMENT_WRITE` → `SHADER_READ`，layout `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` [SPEC]。
   - 插入 output image barrier 到 `COLOR_ATTACHMENT_OPTIMAL`（如需要）。
   - begin render pass / dynamic rendering（output target） [SPEC]。
   - bind pipeline、set viewport/scissor、bind descriptor set、push constants。
   - `vkCmdDraw(3)`（fullscreen triangle）或 `vkCmdDraw(6)` / `vkCmdDrawIndexed`（quad） [HEUR]。
   - end render pass / dynamic rendering。
   - 若输出到 swapchain，插入 barrier 到 `PRESENT_SRC_KHR` [SPEC]。
10. **选择 blit/compute 路径（可选）**：
    - 若只需要简单 copy / scale，使用 `vkCmdBlitImage` 或 `vkCmdCopyImage` 比 fullscreen pass 开销更低 [HEUR]。
    - 若需要每像素复杂计算或读写 storage image，使用 compute shader（见 `../03_compute_workflows/compute_blur_pass.md`） [HEUR]。
11. **接入 resize / recreate**：input / output image 若与 swapchain 尺寸相关，recreate 后更新 image view 与 descriptor [ENGINE]。
12. **接入销毁路径**：按 `pipeline → pipeline layout → descriptor set layout → sampler → image view` 顺序销毁 [ENGINE]。

---

## 9. Android 注意点

- 输入 / 输出 image 若与 swapchain 尺寸相关，rotation 后必须重建 image view 并更新 descriptor [ANDROID]。
- 移动端 fullscreen pass 是 bandwidth 敏感操作，建议在 AGI 中检查每像素读取次数与 tile resolve 开销 [ANDROID]。
- 多个后处理 pass 串联时，考虑合并到单个 pass 或降低中间 buffer 精度/分辨率以节省 bandwidth [ANDROID]。
- pause / resume 后 staging / uniform buffer 与 descriptor 生命周期要稳定，避免悬垂 [ANDROID]。
- `preTransform`/display变化后重查输出能力、变换与颜色合同；viewport/scissor仅是其中一部分，pipeline是否重建由format/静态状态/渲染接口实际依赖决定 [ANDROID]。
- AGI / logcat 验证：检查 fullscreen draw 的 fragment shader cost、texture bandwidth、overdraw [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCmdDraw-*-None-02699`、`VUID-vkCmdPipelineBarrier-*-imageLayout`、`VUID-vkUpdateDescriptorSets-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 fullscreen draw、input texture 绑定、output render target 内容 [TOOL]。
- [ ] 截图符合预期：后处理效果正确，无拉伸 / 翻转 / 黑边。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；输出 pass 输入/输出 image extent、descriptor binding。
- [ ] 性能指标：
  - fullscreen pass GPU cost 与分辨率/采样次数成正比；
  - AGI 中 bandwidth 无异常峰值；
  - 多后处理 pass 合并后 frame time 下降（若已合并） [TOOL]。
- [ ] resize / rotation / pause / resume 后后处理输出正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 flickering。

---

## 11. 常见失败模式

1. **Input image 无 SAMPLED usage**：创建输入 image 时未加 `VK_IMAGE_USAGE_SAMPLED_BIT` [SPEC]。
2. **Layout transition 缺失**：输入 image 仍处于 `COLOR_ATTACHMENT_OPTIMAL`，fragment 采样触发 layout error [TOOL]。
3. **Descriptor imageLayout 与实际 layout 不一致**：descriptor 写 `SHADER_READ_ONLY_OPTIMAL` 但 image 实际为 `GENERAL` [SPEC]。
4. **UV 翻转或视口错误**：fullscreen triangle UV 未适配 Vulkan 坐标系，导致画面上下/左右翻转 [HEUR]。
5. **Output format 不匹配**：pipeline color attachment format 与 output image format 不一致 [SPEC]。
6. **Depth test 未关闭**：后处理 pass 意外开启 depth test，导致 fullscreen quad 被剔除 [HEUR]。
7. **Viewport / scissor 未更新**：resize 后仍为旧尺寸，画面拉伸或只渲染一部分 [ANDROID]。
8. **Input attachment 使用错误**：在 dynamic rendering 或非 subpass 场景误用 `INPUT_ATTACHMENT` [SPEC]。
9. **Blit path 误用**：需要自定义采样核时用了 `vkCmdBlitImage`，导致效果缺失 [HEUR]。
10. **Android rotation 后 descriptor 悬垂**：input/output image view 重建后未更新 descriptor set [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / 是否使用 Dynamic Rendering。
- 输入 image 来源、format、usage、当前 layout。
- 输出 target 类型（swapchain / offscreen）、format。
- Fragment shader 输入资源（set/binding/type）。
- `VkPipelineColorBlendStateCreateInfo` 与 viewport/scissor 参数。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 input/output binding 状态截图。

---

## 15. 需要回查官方文档的情况

1. `INPUT_ATTACHMENT` 与 `COMBINED_IMAGE_SAMPLER` 在 RenderPass subpass 中的性能与功能差异。
2. Vulkan 坐标系下 fullscreen triangle 与 quad 的 UV 映射细节。
3. Dynamic Rendering 中后处理 pass 的 input image layout 限制。
4. 不同 GPU 对 multiple fullscreen pass 合并为 single pass 的 tile memory 影响。
5. Android  compositor 对 swapchain image 做后处理直接写入时的额外约束。

<a id="temporal-quality-workflow"></a>
## 非神经时域稳定与滤波

使用 [输入合同](../../02_core_mental_model/render_target_model.md#lighting-temporal-data-contract)，每个 View/Engine/generation 独立 history。shadow visibility / AO 标量与 HDR reflection radiance 不共享无语义的“通用 blur”。[ENGINE]

基线：current 信号和真实 MV/depth/normal→重投影→越界/反遮挡/深度/法线/材质校验→history 限制与权重→边缘感知空间滤波→独立 history 写回→合成。每个 pass 明确 descriptor、格式、push constants、dispatch 范围与 write→read barrier；ping-pong 及 frames-in-flight 还需跨帧 RAW/WAR 依赖和完成点。

| 事件 | 最小策略 | 不可接受 |
|---|---|---|
| 第一帧 / camera cut / Device 重建 | 全部 reset；新代合法初始化 | 读取未初始化历史 |
| resize / viewport / render-scale / 投影变更 | 仅在算法支持且坐标转换验证后 resample，否则 reset/recreate | 旧尺寸直接寻址 |
| pause / 跳帧 / 长间隔恢复 | 依据连续性与算法约束 reset 或显著降权 | 用 frame slot 冒充前一逻辑帧 |
| 资源/材质/LOD/动画代际变化 | affected pixel 局部拒绝，无法定位则全重置 | 混合两代 geometry 数据 |
| 光源/阴影变化 / effect switch | 降 confidence 或拒绝；语义变化 reset | MV=0 就永远信任 history |
| exposure / pre-exposure | 按已定义比值重标定 history，异常因子 reset | 不同曝光尺度直接混合 |
| 第二 View 销毁/重建 | 独立 key 和 completedUse，旧代退休 | 跨 View 共用 history slot |

例如存储颜色 C=linearRadiance×exposure 时，历史乘 currentExposure/previousExposure；反向 pre-exposure 定义不能照搬。拒绝非有限/非正因子。visibility 限制在 [0,1]，radiance 不截成 [0,1]；按当前邻域/方差限制 history，normal/depth 边缘保护，roughness/hit distance 是否参与由信号算法声明。[ENGINE]

诊断图保存 motion 方向/单位、jitter、线性 depth、history weight/rejection、disocclusion、visibility、reflection hit/confidence；保留 raw noisy 和空间/时域后输出。静止与运动序列同时检验噪声、残影和细节损失；“增加模糊”不是反遮挡修复。[TOOL][ENGINE]

组合顺序由具体 SDK 合同决定：信号→对应滤波→光照合成→所选 SR/FG→UI/显示；避免重复 TAA/锐化/曝光，见 [SR/FG 协调](mobile_neural_graphics.md#temporal-sdk-adapters)。首版精简 CPU/GLSL fixture 与运行状态在 tests 仓，不能把 shader 编译当画质通过。


<a id="transparency-resolve"></a>
## 透明 resolve：排序、WBOIT 与有界对照

适用非折射透明近似；先读 [合成合同](../../02_core_mental_model/render_target_model.md#transparent-composition-contract) 和 [能力](../../03_api_manual/06_pipeline/graphics_pipeline.md#blend-format-capability)。输入是线性 straight color c、opacity a∈[0,1]、opaque depth 和有限正权重 w；输出为 premultiplied 颜色与 opacity，不能混作 transmittance。[ENGINE]

可实现 WBOIT 基线（明确近似）：accum RGBA 清 0，revealage 单通道清 1；shader 写 `vec4(c*a*w,a*w)` 到 accum，用 ADD/ONE/ONE 累加。revealage 输出 a 到红通道，用 ADD、ZERO/ONE_MINUS_SRC_COLOR 得到 `R*=1-a`。该组合通常需要 independentBlend；不支持时两次几何 pass 或排序回退。opaque depth test 开、透明 depth write 关。选受支持 blend 格式，声明 w 的深度 convention、上下界与有限值处理，不能照搬未归一化深度权重。

resolve：若 accum.a>epsilon，`mean=accum.rgb/accum.a`，否则 mean=0；`A=1-R; Cpremul=mean*A; out=Cpremul+R*background`。epsilon、权重与格式量化属于误差预算；accum 非有限、溢出或异常 R 必须诊断，不能单靠 clamp 掩盖。生产实现可调权重但先冻结 fixture 容差。高 opacity、深度交错与有色吸收容易偏差，WBOIT 不等于精确 source-over，不求解折射。

附件写→fragment/compute resolve 实际读建立 barrier/layout；各 frame slot 独立累积目标，最后 resolve 完成后复用。小分辨率 bounded per-pixel list/depth peeling 可作精度对照：头/计数重置、全局 pool/每像素层数/resolve 上限、字节乘法与索引溢出均显式检查。超限计数+诊断视图，确定性拒绝质量档、预先声明 tail approximation 或回退；禁止静默丢片段后 PASS。interlock 不提供深度排序。

验证：两层正反序 oracle、交叉/近不透明/低 alpha/HDR；同 fixture 比排序与 WBOIT 误差；故意超容量必须触发预定结果。CPU 模拟、shader 编译、实际 Vulkan 和手机画质/性能分别报告。

[REF] [NVIDIA OIT sample](https://github.com/nvpro-samples/vk_order_independent_transparency)、[Kitware bounded deep framebuffer](https://www.kitware.com/better-transparency-with-vtk-and-webgpu/)（2026-11-06，WebGPU 参考，不是 Vulkan/Android 验收；其16层选择不是 Vulkan 上限）。

<a id="local-volume-composite"></a>
## 有界局部体积与软粒子合成（C2）

适用均匀/程序密度局部雾，不承担完整多重散射或任意嵌套介质。输入：世界单位的 volume bounds、ray/opaque 线性深度、sigma_t≥0、源项、步长、最大 samples、最小 T、光照/曝光与 history metadata；输出积分颜色 C 和透射 T。[ENGINE]

求 ray 与体积交区并截于 opaque depth。每段实际长度 ds（含末段）用 `Tseg=exp(-sigma_t*ds)`，在局部常量源颜色 S 的近似下 `C+=T*(1-Tseg)*S; T*=Tseg`。S 是明确的源函数/发光散射近似，不冒称完整物理光照；零消光与其他源模型需用对应极限。sigma_t 的单位必须与 ds 相容。步长减半应趋近同一积分，不把固定 alpha 重复两倍。

最大步数不足时声明采样降档/失败，不悄悄截短 ray。T 早停需颜色误差上界，例如残余背景贡献由 T×背景亮度界约束，高亮背景不能无条件删尾。合成背景用 C+T*B；表面在雾前/后/内部时分别积分对应深度段，单个雾贡献不重复用于前景与背景。互穿体积/透明面需分段或明确近似，万能“先雾后透明”不成立。

低分辨率雾+depth-guided upsample 作为条件质量档，测薄前景漏光和边缘。opaque depth 写→采样、积分目标写→合成读同步；history 复用 [时域工作流](#temporal-quality-workflow)，逐 View/generation 持有和退休。不存在可靠运动数据时降低 history 信任或关闭，不伪造零 MV。

雨雪复用既有粒子模拟。soft intersection 在同一线性空间比较 scene depth 与 particle depth，用声明软化距离衰减 opacity，再按 straight/premultiplied 合同输出；与 alpha-cutout、sample coverage 分开。记录 near/far 尺度、排序与亚像素闪烁；软交界不是解决所有透明互遮挡。验证步长/深度反 Z、前后雾层、移动粒子/相机突变、低分辨率轮廓与持续序列。

[REF] [GPU Gems 39 Volume Rendering](https://developer.nvidia.com/gpugems/gpugems/part-vi-beyond-triangles/chapter-39-volume-rendering-techniques)（积分背景，不是近期移动测量）。

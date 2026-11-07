# Render Target 模型

## 核心思想

Render Target 不是一张简单图片，而是由 image、image view、usage、layout、load/store、pass 关系共同决定。

核心模型：

```text
Render Target Image
→ ImageView
→ Attachment Usage
→ Layout
→ Load / Store
→ Render Commands
→ Final Layout / Barrier
→ Next Pass Consumer
```

## Render Target Image

一个 image 要作为 render target，通常要满足：

1. format 支持 attachment。
2. usage 包含 COLOR_ATTACHMENT 或 DEPTH_STENCIL_ATTACHMENT。
3. 创建对应 ImageView。
4. 渲染时处于合适 layout。
5. 如果后续要采样，usage 还要包含 SAMPLED。

## 传统 Render Pass 路径

```text
VkRenderPass
→ VkFramebuffer
→ Attachment Description
→ Subpass
→ vkCmdBeginRenderPass
→ Draw
→ vkCmdEndRenderPass
```

关注点：

1. attachment format 是否和 image view 匹配。
2. loadOp / storeOp 是否符合预期。
3. initialLayout / finalLayout 是否正确。
4. framebuffer image view 是否来自当前 swapchain / offscreen image。
5. swapchain recreate 后 framebuffer 必须重建。

## Dynamic Rendering 路径

```text
VkRenderingInfo
→ VkRenderingAttachmentInfo
→ vkCmdBeginRendering
→ Draw
→ vkCmdEndRendering
```

特点：

1. 不需要提前创建 VkRenderPass / VkFramebuffer。
2. 在 begin rendering 时指定 attachment。
3. 仍然需要 image、image view、layout、load/store、pipeline rendering info。
4. 仍然需要处理 pass 间 barrier。

## Offscreen Pass 模型

```text
Offscreen Color Image
→ COLOR_ATTACHMENT_OPTIMAL 写入
→ Barrier
→ SHADER_READ_ONLY_OPTIMAL 采样
→ Fullscreen Composite Pass
```

典型用途：

1. Bloom。
2. Blur。
3. Tone Mapping。
4. SSR / SSAO。
5. 后处理合成。

## 高频错误

1. image usage 缺少 COLOR_ATTACHMENT 或 SAMPLED。
2. ImageView format / aspect 错误。
3. RenderPass attachment format 与 swapchain format 不匹配。
4. Dynamic Rendering 下 pipeline rendering info 与实际 attachment 不匹配。
5. offscreen image 写入后没有 barrier 就采样。
6. swapchain recreate 后 framebuffer / image view 没有重建。
7. depth attachment 尺寸与 color attachment 不一致。

## 专家规则

```text
Dynamic Rendering 简化了 RenderPass / Framebuffer，但没有取消 Render Target 心智模型。
任何 pass 都必须明确：写入哪个 image，以什么 layout 写，后续谁读，如何同步。
```


<a id="color-output-contract"></a>
## Android 输入—工作—输出颜色合同（C3权威）

前提：输入来源和目标Surface已识别；资源同步/ownership另有完成证据。本节不把VkImageLayout当颜色编码，也不由FP16/10-bit推断屏幕HDR。[ENGINE]

| 合同字段 | 输入 | 工作空间 | 输出/合成 |
|---|---|---|---|
| primaries / 白点 | producer/container可信元数据，未知则显式假设 | 明确所选线性RGB基色，必要时矩阵转换 | 每Surface支持的色域；Display P3是色域，不等于HDR |
| transfer | sRGB/PQ/HLG等实际编码，不从扩展名猜 | 解码到目标工作语义；YCbCr转RGB不自动线性化 | 明确编码一次，shader与sRGB attachment固定功能不能重复 |
| range / bit depth | full/limited、量化精度单列 | 运算/中间附件精度与裁剪范围 | 10-bit/FP16只描述存储，不保证系统或面板HDR |
| alpha mode | opaque/straight/premultiplied | 规定在何空间合成；只在需要时乘一次alpha | pipeline blend、compositeAlpha与宿主合同一致 |
| 参考白 / 亮度 | 未知时记录假设与来源 | 单位/曝光约定明确 | tone mapping责任方、目标headroom和实际显示条件 |

完整链：输入编码/原色/范围 → YCbCr/RGB与transfer/primaries处理 → 工作精度/blend → 指定tone-mapping owner → 输出编码 → 逐Surface VkFormat/VkColorSpaceKHR → Android compositor/display。Image barrier只改变访问和同步，不执行这条颜色链。[SPEC][ENGINE]

| tone-mapping owner | 应用职责 | 防重复/验证 |
|---|---|---|
| 应用输出SDR | 将高动态输入映射至声明SDR编码/参考白 | 不再把已映射数值标成PQ/HLG让下游重复解释 |
| 标准HDR输出 | 生成与实际支持的HDR pair一致的像素/必要metadata | 系统/显示如何映射需路径证据，不能假定完全不处理 |
| 平台媒体/直接buffer路径 | 按该路径dataspace/metadata合同供给内容 | 不把该路径颜色接口套到WSI内部BufferQueue |

Media3 `1.12.0-alpha01`（2026-10-21）加入Display P3标识与映射，只是Alpha元数据能力，不是通用Vulkan导入/HDR完成证明。研究日期2026-11-01，该页面还列更晚alpha02；不以页面顶部更新时间替代事件日期，不强制引入Media3。[ANDROID]

数值测试先固定色条/灰阶/透明边缘的源数值、工作空间与容差，再跑离屏检查；不能看结果后改阈值。屏幕合成另测，截图/回读不证明面板绝对亮度、系统tone mapping或色准。无HDR设备/校准时仅报告实际覆盖和未验证项。
来源：[Media3 release](https://developer.android.com/jetpack/androidx/releases/media3#1.12.0-alpha01)、[compositeAlpha](https://docs.vulkan.org/refpages/latest/refpages/source/VkCompositeAlphaFlagBitsKHR.html)、[HDR metadata](https://docs.vulkan.org/refpages/latest/refpages/source/VK_GOOGLE_hdr_smpte_st_209450_metadata.html)。

<a id="lighting-temporal-data-contract"></a>
## 光照与时域输入合同

以下是 ENGINE 数据合同，不是 Vulkan 新结构体；颜色仍服从 [颜色输出合同](#color-output-contract)。每个消费者单独声明编码，不能强制所有 SDK 接受相同纹理。[ENGINE]

| 字段 | 必须匹配的语义 |
|---|---|
| viewId / engineId / frameId | 逻辑真实渲染帧，不是 frame slot、swapchain image index 或生成/呈现帧号 |
| scene/geometry/material/light/historyGeneration | 数据版本、owner 和失效原因；资源 ID 不复用为新代内容 |
| inputSize / outputSize / viewport / historySize | 尺寸、原点、Y方向、动态分辨率和有效区域 |
| depthConvention | [0,1] 映射、正/反 Z、near/far/无限远、投影、clear、compare 相符 |
| normalSpace / material | normal 编码和空间；几何/着色法线、roughness/metallic、alpha/双面规则 |
| motionDirection / motionUnits | current→previous 或相反；pixel/UV；参照尺寸；Y 方向 |
| jitterConvention | 是否含 jitter；当前/前帧 sample offset 及矩阵；只消除一次 |
| current/previous transforms | camera、rigid object、skin/deformation 和程序动画的上一帧状态 |
| colorEncoding / exposureOrPreExposure | 线性或显示域；曝光因子定义、alpha convention、历史换算方向 |
| confidence / resetReason / completedUse | 信号可信度、history age、显式失效事件及最后 GPU 使用完成点 |

例：未含 jitter 的 current→previous pixel MV 转 UV 时除以对应定义尺寸，再加到 current UV；若 producer 为 previous→current 或 jittered 坐标，不可直接照搬。稠密 previous→current forward MV 必须反求对应位置/重采样或重新生成 backward MV，不能只在当前像素取负。用已知 1 pixel 平移和静止物体/移动相机分别验证符号与比例。[ENGINE]

geometry MV=0 不说明光照静止；灯光、阴影和高亮变化需降低信任度。相机 previous matrix 不能替代动画物体 previous deformation。normal/depth confidence 与真实信号绑定同一 View/frame/generation；dump 元数据和原始资源一起检查。


<a id="transparent-composition-contract"></a>
## 透明合成合同（C1）

适用：线性工作空间的表面、粒子与 Gaussian 合成；不把 alpha blend 当折射或任意互穿介质求解。先复用 [颜色合同](#color-output-contract)，输入记录 RGB/alpha 表示、transfer/primaries、opacity 或 transmittance、曝光、depth convention、sample coverage 与每 attachment 的 format/factors/op/write mask。[ENGINE]

straight 输入应先解码到线性颜色，再乘 alpha 一次成为 premultiplied；若源已经 premultiplied，需遵守其编码域合同，不能把编码域乘法直接当线性乘法。source-over 的 `Cout = Csrc + (1-Asrc)*Cdst; Aout = Asrc + (1-Asrc)*Adst` 要求 Csrc 已预乘。对应 ADD、RGB ONE/ONE_MINUS_SRC_ALPHA、alpha ONE/ONE_MINUS_SRC_ALPHA。straight RGB 可用 SRC_ALPHA/ONE_MINUS_SRC_ALPHA，但 alpha 仍 ONE/ONE_MINUS_SRC_ALPHA，不能双乘。[SPEC][ENGINE]

默认 back-to-front 排序、opaque depth test 开、透明 depth write 关，明确正/反 Z 和 tie-break stable ID。中心深度排序只是一条参考路线，交叉薄片未必有全局正确物体顺序。front-to-back 的另一种合同是 `C=0,T=1; C+=T*alpha*linearColor; T*=1-alpha; final=C+T*background; A=1-T`。若以 fixed blend 实现，必须根据目标存 opacity 还是 T 重新推导状态；不能复用上述 source-over 因子而不改顺序。sample coverage/MSAA alpha-to-coverage 不等同物理透明度，Android compositeAlpha 仍由颜色输出合同独立管理。

能力见 [blend 能力](../03_api_manual/06_pipeline/graphics_pipeline.md#blend-format-capability)。输出同时记录颜色及 alpha/T 语义。跨 pass 的附件写→实际 shader 读、布局和每帧退休不可省略；资源回退必须等所有 GPU 消费者结束。算法回退为排序 blend；WBOIT 是近似，有界列表超限必须计数并确定性拒绝/退化，不能静默漏片段。

验证先关光照/tone mapping：黑底红前蓝后、各 alpha=.5，线性结果 (.5,0,.25)，反序 (.25,0,.5)，alpha 均 .75；这是公式 oracle，不是 GPU 测量。CPU FP64 语义 oracle 与指定格式/舍入模拟分开，不声称逐位模拟硬件 blend。精度排查顺序：输入/SH/纹理量化及 cutoff → 表示/编码/因子 → 排序/遗漏 → 中间存储逐层量化/溢出 → tone mapping/输出/Android 合成。固定容差后测黑白底大量低 alpha、强 HDR、相交/近不透明层，FP16 不是零误差或免费优化。[ENGINE]

[SPEC] [Blending](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/framebuffer.adoc)。

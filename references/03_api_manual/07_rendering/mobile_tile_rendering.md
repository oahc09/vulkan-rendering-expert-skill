# API Card: Mobile Tile Rendering

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 / 资源链 / 同步链 |
| Vulkan 对象 | `VkRenderPass` / `VkRenderingInfo` / `VkImage` / `VkDeviceMemory` |
| 常用 API | `vkGetPhysicalDeviceFeatures2` / `vkGetPhysicalDeviceProperties2` / `vkCmdBeginRendering` / `vkCmdSetRenderingInputAttachmentIndices` / `vkCmdBindTileMemoryQCOM` |
| 适用平台 | Mobile；按实际设备能力选分支 |
| 来源等级 | `[SPEC] [SAMPLE] [VENDOR] [ENGINE]` |
| 适用 Vulkan 版本 | RenderPass 标准路径；Dynamic Rendering/Local Read 核心或扩展路径；QCOM 能力可选 |

## 1. 一句话定位

先由访问模式和生命周期选候选路径，再查能力与测收益；传统 subpass、dynamic local read、QCOM tile 专项不是必然升级的三级架构。[ENGINE]

## 2. 所属对象链路

```text
pass 图 / 像素依赖 → 支持并启用的能力 → attachment/heap/resolve 配置
→ pipeline + descriptor 映射 → 录制依赖 → 保存输出 → 持续负载 A/B
```

上游保留原渲染图、allocator 与标准路径；下游只有需要跨 pass/帧使用的输出才持久化。Tile-based GPU、transient attachment、lazy allocation 与 QCOM tile heap 是不同概念。[SPEC][ENGINE]

<a id="tile-capability-matrix"></a>
## 3. 核心对象与 API

| 路径 | 能力条件 | 失败/缺失回退 |
|---|---|---|
| RenderPass / subpass | attachment usage/format/sample 支持，正确 subpass dependency | 保留已有离屏 pass + sampled image 路径 |
| Dynamic Rendering + Local Read | `dynamicRendering` 与 `dynamicRenderingLocalRead` 按核心/扩展路径启用；映射、布局及依赖有效 | RenderPass/subpass 或普通 texture pass |
| QCOM tile shading | 查询并启用 `VK_QCOM_tile_shading` 及所需 feature/properties；shader 工具链和运行时入口可用 | 标准 graphics/compute pass |
| QCOM tile memory | `VK_QCOM_tile_memory_heap`、对应 feature、heap 与 tile requirements；显式绑定及有效内容边界 | 普通 device memory + 显式持久化输出 |
| 可编程 resolve | 按实际支持选择 `VK_EXT_custom_resolve` 或 `VK_QCOM_render_pass_shader_resolve`，语义分别核对 | 标准 MSAA resolve；不支持 MSAA 则降低 samples |

Vulkan 1.4 的 local-read 保证不覆盖全部 depth/stencil/MSAA：分别查询 `VkPhysicalDeviceVulkan14Properties.dynamicRenderingLocalReadDepthStencilAttachments` 与 `dynamicRenderingLocalReadMultisampledAttachments`。声明版本、支持、启用与测得收益不等价。[SPEC]

<a id="tile-access-patterns"></a>
## 4. 标准使用流程

| 访问模式 | 合理候选 | 必须验证的边界 |
|---|---|---|
| 同像素 attachment 写后读 | subpass input attachment / dynamic local read | 读写映射、同步、格式和样本支持 |
| 邻域 blur / 任意纹理坐标 | sampled image pass 或满足边界的专门 tile 算法 | input attachment 不自动提供任意邻域采样 |
| 跨 pass storage 访问 | 普通 image/buffer + barrier；可选 QCOM tile 路径 | 不能把普通 compute dispatch 随意放进 dynamic render pass |
| MSAA resolve | 标准 resolve；有证据才选 programmable resolve | samples/格式/resolve模式及读取能力分别检查 |
| depth/stencil local read | 满足对应 properties 的分支 | 不以 API 1.4 代替该 property 查询 |

先实现标准路径 → 记录能力拒绝原因 → 启用单个可选路径 → 比较输出与测量 → 保留运行时回退。[ENGINE]

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkRenderingAttachmentLocationInfo` | shader output location 到 attachment 映射 | 与 input attachment index 混用 |
| `VkRenderingInputAttachmentIndexInfo` | input index 对应当前 attachment | 重排 attachment 后继续用旧映射 |
| `VK_IMAGE_LAYOUT_RENDERING_LOCAL_READ` | 适用 layout、usage 与访问范围 | 只换 layout 不补 memory dependency |
| load/store / resolve | 下一消费者是否需要内容、resolve支持范围 | 一律丢弃或一律 STORE |
| `VkPhysicalDeviceTileMemoryHeapPropertiesQCOM.queueSubmitBoundary` | 内容有效范围是否扩至整个 queue submit | 把 tile heap 当跨帧持久存储 |

## 6. 正确性检查点

### 创建阶段

- [ ] 按 usage/format/samples 查 image 支持，pipeline 与 attachment 一致。
- [ ] 版本/扩展/feature/properties 分开记录，不按 GPU 品牌猜。

### 使用阶段

- [ ] local read producer/consumer、input映射与 frame-local dependency 明确。
- [ ] tile heap 内容在有效 batch/submit 范围内；跨范围输出已复制/resolve 到持久资源。

### 销毁阶段

- [ ] 等待关联 GPU 使用完成，resize 后重建尺寸相关资源及 descriptor。
- [ ] 内容失效不等于对象可以立即释放；对象 in-flight 寿命仍需单独管理。

## 7. 高频错误

1. 任意 blur 都可替换成 input attachment。
2. 因手机支持 Vulkan 1.4 就读取 depth/MSAA 附件。
3. “是 Adreno”就跳过 QCOM 扩展/feature 查询，或要求 Mali 改用同一路径。
4. `TRANSIENT_ATTACHMENT` / lazy allocation 被解释为规范保证不写回外部内存。
5. 把 tile heap 内容跨 batch/帧保存，或者以 QHWI 构建成功宣称 GPU 验收。

## 8. Debug 检查路径

先核对实际选择分支与 capability log，再检查 attachment/subpass/dispatch、layout、descriptor 与最终输出。Validation clean 不是图像正确证明。使用可用 frame capture、readback/图像差分、GPU timestamp 与真实可用 counter；未取得带宽 counter 就只报告时间/图像证据。[TOOL]

<a id="tile-lifetime-contract"></a>
## 9. 生命周期风险

普通 transient/lazy attachment 是 usage/分配策略；支持与分配需查询，不能替代一般 object retirement。
QCOM tile heap 用 `VK_MEMORY_HEAP_TILE_MEMORY_BIT_QCOM` 标识；资源需对应 tile usage、`VkTileMemoryRequirementsQCOM` 和 `vkCmdBindTileMemoryQCOM` 等要求。其内容默认只在 command-buffer submission batch 范围保留；`queueSubmitBoundary` 查询可扩展该范围，但不是跨帧永久保证。每次有效范围开始重建需要的 tile 内容，输出在失效前写入普通资源。[SPEC]

## 10. 同步风险

CPU 不得覆盖 in-flight descriptor/attachment。GPU 的同像素依赖需正确 stage/access、必要的 framebuffer-local dependency（如适用的 BY_REGION）与 layout；它是同步语义，不是一定在片上执行的承诺。QCOM 特殊 render pass/dispatch 限制单独查规范，普通路径不能继承厂商特例。[SPEC]

## 11. Android 注意点

先查询当前 GPU/driver/工具链；旋转、resize 后重算 tile/attachment 尺寸、samples、descriptor 与 shader参数。后台停新帧、完成关联提交后退休资源；extent 为 0 暂停展示。保留标准分支，OTA/驱动变化触发能力重检，不能用一个设备测量代表所有移动 GPU。[ENGINE]

## 12. 性能注意点

先固定分辨率、画质、场景、刷新率与热状态，比较标准/可选路径的图像误差、GPU P50/P95/P99、内存与可取得带宽。局部读取、pass 合并和 compute 都不天然更快；寄存器压力、tile容量、resolve/缓存变化可抵消收益。离线 shader compiler 提供估算，不是运行时 bandwidth counter。[ENGINE][TOOL]

<a id="qhwi-sample-lessons"></a>
## 13. 专家经验

固定 QHWI `b12d782344643252ba38ee864f8bcb20cd8d6949`，只作 source-read：[SAMPLE]

- `QcomTileMemoryHeapExample::init/recordCommandList` 按开关加 tile usage，tile 分支每轮先 compute 初始化再绘制；不要把初始化时一次上传理解为跨提交内容永久保留。
- `QCOMTileShadingExample::init` 关闭自动 barrier，构造明确的 graphics/compute、storage image/buffer 关系；样例不证明任意 shader 可以免同步。
- `VkCustomResolveExample::init/usesStandardResolvePath` 查询可选 custom resolve，否则 QCOM shader resolve，再回退标准 MSAA；原引擎可借鉴这种 capability branch，而不是迁移整套 QHWI。
- QHWI README 的 CI 边界是构建，不是 GPU 测试；样例里的测量不能当作本项目收益。[REF]

## 14. 相关 API 卡片

- [Dynamic Rendering](dynamic_rendering.md)、[Render Pass](render_pass.md)
- [Image](../04_buffer_image_memory/image.md)、[Memory Allocation](../04_buffer_image_memory/memory_allocation.md)
- [移动带宽工作流](../../05_workflows/07_optimization/optimize_mobile_bandwidth.md#mobile-tile-choice)

## 15. 需要回查官方文档的情况

- [Dynamic Rendering Local Read](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_dynamic_rendering_local_read.html)：核心提升与 properties 边界。[SPEC]
- [QCOM tile heap](https://docs.vulkan.org/refpages/latest/refpages/source/VK_QCOM_tile_memory_heap.html)：内容有效边界/绑定/usage。[SPEC]
- [固定 QHWI tile memory 源码](https://github.com/qualcomm/qhwi/blob/b12d782344643252ba38ee864f8bcb20cd8d6949/examples/qcom_tile_memory_heap/src/qcom_tile_memory_heap.cpp)、[tile shading](https://github.com/qualcomm/qhwi/blob/b12d782344643252ba38ee864f8bcb20cd8d6949/examples/qcom_tile_shading/src/qcom_tile_shading.cpp)、[custom resolve](https://github.com/qualcomm/qhwi/blob/b12d782344643252ba38ee864f8bcb20cd8d6949/examples/vk_custom_resolve/src/vk_custom_resolve.cpp)。[SAMPLE]

2026-11-01 核查；未执行第三方编译、Android 或 GPU 实测。新增规范不等于新增手机支持。

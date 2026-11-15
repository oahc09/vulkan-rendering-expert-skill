# API Card: Copy / Blit / Resolve 命令族

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | Copy / Blit / Resolve 命令族 |
| 常用 API | `vkCmdCopyBuffer` / `vkCmdCopyImage` / `vkCmdBlitImage` / `vkCmdResolveImage` / `vkCmdFillBuffer` / `vkCmdCopyBufferToImage` / `vkCmdCopyImageToBuffer` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 核心 |

---

## 1. 一句话定位

Copy / Blit / Resolve 命令族是 GPU 侧的 transfer 操作集合：Copy 实现逐字节或按 region 的等尺寸拷贝，Blit 支持 region 缩放与过滤，Resolve 将多采样 image 解析为单采样 image，Fill / Update 用于 buffer 的填充与写入。[SPEC]

---

## 2. 所属对象链路

```text
VkCommandBuffer (recording)
→ vkCmd{Copy,Blit,Resolve,Fill}* 命令
   ├─ src VkBuffer / VkImage (TRANSFER_SRC usage)
   ├─ dst VkBuffer / VkImage (TRANSFER_DST usage)
   └─ VkImageMemoryBarrier / VkBufferMemoryBarrier (前后同步)
→ 后续 stage 消费 (Vertex / Fragment / Compute / Sampled / Storage)
```

### 上游依赖

- `VkCommandBuffer` 必须处于 recording 状态且不在 render pass 内（除部分扩展例外）。[SPEC]
- src 资源必须含 `TRANSFER_SRC_BIT`，dst 资源必须含 `TRANSFER_DST_BIT`。[SPEC]
- src / dst image 在调用时必须处于合法 layout（详见第 5 节）。[SPEC]

### 下游影响

- Copy / Blit / Resolve 与后续消费必须建立所需执行/内存依赖，并保证消费时 layout 合法；GENERAL 可以保持不变，layout transition 本身不替代正确 stage/access。本文单队列示例使用 barrier，跨提交可使用适当 semaphore 等同步机制。[SPEC]
- 消费方 stage 必须通过 barrier 的 `dstStageMask` 与 transfer 输出建立 dependency。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkBufferCopy` / `VkImageCopy` / `VkBufferImageCopy` / `VkImageBlit` / `VkImageResolve`
- `VkImageMemoryBarrier` / `VkBufferMemoryBarrier`
- `VkCommandBuffer`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdCopyBuffer` | buffer → buffer，按 `VkBufferCopy` 区域拷贝。[SPEC] |
| `vkCmdCopyImage` | image → image，按 `VkImageCopy` 区域拷贝；要求格式兼容。[SPEC] |
| `vkCmdBlitImage` | image → image，按 `VkImageBlit` 区域缩放 + 过滤；支持 NEAREST / LINEAR。[SPEC] |
| `vkCmdResolveImage` | 多采样 image → 单采样 image，按 `VkImageResolve` 区域 resolve。[SPEC] |
| `vkCmdFillBuffer` | 用 uint32 值填充 buffer 区间，offset / size 必须 4 字节对齐。[SPEC] |
| `vkCmdUpdateBuffer` | 直接以 CPU 数据更新 buffer（≤ 65536 字节）。[SPEC] |
| `vkCmdCopyBufferToImage` | buffer → image，要求 image 处于 `TRANSFER_DST_OPTIMAL` 或 `GENERAL`。[SPEC] |
| `vkCmdCopyImageToBuffer` | image → buffer，要求 image 处于 `TRANSFER_SRC_OPTIMAL` 或 `GENERAL`。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_copy_commands2`（Vulkan 1.3 核心 `vkCmdCopyBuffer2` / `vkCmdCopyImage2` / `vkCmdBlitImage2` / `vkCmdResolveImage2` / `vkCmdCopyBufferToImage2` / `vkCmdCopyImageToBuffer2`）：引入可扩展 Info/region 结构体及 *2 入口；旧命令也支持多个 region，并非只有 *2 才能批量 region。[SPEC]
- `VK_EXT_conditional_rendering`：可附加条件渲染；与 transfer 解耦。
- `VK_KHR_synchronization2`：简化 stage / access mask 写法。[SPEC]
- Android 可用性：核心 transfer 功能全部可用；CopyCommands2 在支持 Vulkan 1.3 的设备上可用。[ANDROID]

---

## 4. 标准使用流程

### 4.1 Staging 上传流程（CPU → GPU image）

```text
1. 创建 staging VkBuffer（usage = TRANSFER_SRC，memory = HOST_VISIBLE | HOST_COHERENT）
2. vkMapMemory → memcpy CPU 数据 → vkUnmapMemory
3. vkBeginCommandBuffer
4. image layout 转换：UNDEFINED → TRANSFER_DST_OPTIMAL
   （srcStage = TOP_OF_PIPE，dstStage = TRANSFER，dstAccess = TRANSFER_WRITE）
5. vkCmdCopyBufferToImage(staging, image, TRANSFER_DST_OPTIMAL, regionCount, pRegions)
6. image layout 转换：TRANSFER_DST_OPTIMAL → SHADER_READ_ONLY_OPTIMAL
   （srcStage = TRANSFER，srcAccess = TRANSFER_WRITE，dstStage = FRAGMENT_SHADER，dstAccess = SHADER_READ）
7. vkEndCommandBuffer → submit → waitFence
8. 释放 staging buffer
```

### 4.2 Mipmap 生成链路

```text
1. 创建 image：mipLevels = floor(log2(maxDim)) + 1，usage 含 TRANSFER_SRC | TRANSFER_DST | SAMPLED
2. 将 level 0 上传（vkCmdCopyBufferToImage，目标 layout = TRANSFER_DST_OPTIMAL）
3. for i in 1..mipLevels-1:
     srcLevel = i - 1, dstLevel = i; 每维 extent=max(1,baseDimension>>level)
     初始化 dstLevel: UNDEFINED → TRANSFER_DST_OPTIMAL, dstAccess=TRANSFER_WRITE
     barrier: srcLevel (TRANSFER_DST_OPTIMAL → TRANSFER_SRC_OPTIMAL)
              srcStage = TRANSFER, srcAccess = TRANSFER_WRITE
              dstStage = TRANSFER, dstAccess = TRANSFER_READ
     vkCmdBlitImage(image, TRANSFER_SRC_OPTIMAL, image, TRANSFER_DST_OPTIMAL,
                    &blitRegion, filter = LINEAR)
   注：不同 mip 可以使用同一 image，但 source sampled texels 与 destination 写区域不可非法 overlap；先检查 BLIT_SRC/BLIT_DST 与 LINEAR 格式能力、单样本和所有实际 mip 布局。
4. 已作为源的 levels [0,mipLevels-2] 实际是 TRANSFER_SRC_OPTIMAL；最后一级仍是 TRANSFER_DST_OPTIMAL。
5. 按各自真实 oldLayout 分组转为 SHADER_READ_ONLY_OPTIMAL，建立所有先前写入对 shader read 的可见性。mipLevels=1 时没有 blit，只有原始上传一级。
```

### 4.3 MSAA resolve 路径

```text
1. 多采样 color attachment（samples = 2/4/8），usage 含 COLOR_ATTACHMENT | TRANSFER_SRC
2. 单采样 resolve image（samples = 1），usage 含 TRANSFER_DST，后续采样另需 SAMPLED；dst format 必须支持 COLOR_ATTACHMENT feature，但这不等于此 transfer 命令必需 COLOR_ATTACHMENT usage
3. 渲染到多采样 attachment
4. barrier: src = COLOR_ATTACHMENT_OUTPUT / COLOR_ATTACHMENT_WRITE
            dst = TRANSFER / TRANSFER_READ
            srcMS image: COLOR_ATTACHMENT_OPTIMAL → TRANSFER_SRC_OPTIMAL
            dstSS image: UNDEFINED → TRANSFER_DST_OPTIMAL, dstAccess=TRANSFER_WRITE
   src/dst 使用各自的 image barrier，不能把目标写错误声明为 TRANSFER_READ
5. vkCmdResolveImage(srcMS, TRANSFER_SRC_OPTIMAL, dstSS, TRANSFER_DST_OPTIMAL, ...)
6. barrier: dstSS image → SHADER_READ_ONLY_OPTIMAL 或 PRESENT_SRC_KHR
```

---

## 5. 关键字段

### 5.1 VkBufferCopy

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcOffset` / `dstOffset` | 必须落在 src / dst buffer 的逻辑 size 范围内。[SPEC] | 越界导致 validation error 或 device lost。[TOOL] |
| `size` | 拷贝字节数必须非零并满足两个 buffer 的逻辑 size 边界；vkCmdCopyBuffer 没有要求 size/offset 同余，也不能拿 allocation requirements 代替 buffer size。[SPEC] | size 为零、越界或非法重叠；不要误报一般 byte offset 对齐。[TOOL] |

### 5.2 VkImageCopy

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcSubresource` / `dstSubresource` | mipLevel / baseArrayLayer / layerCount 必须在源 / 目标范围内；aspectMask 必须匹配格式。[SPEC] | depth/stencil 格式 aspectMask 写成 `COLOR_BIT`。[SPEC] |
| `srcOffset` / `dstOffset` / `extent` | 对压缩格式（BC / ASTC / ETC2），offset 必须符合 texel block extent 对齐；extent 的块对齐存在到达 mip 边缘的规范例外，按相应命令逐项判断。[SPEC] | 用压缩格式按非块对齐拷贝触发 VUID。[TOOL] |

### 5.3 VkBufferImageCopy

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `bufferOffset` | 普通非 depth/stencil、非多平面格式要求 texel block size 倍数；depth/stencil 要求 4 字节，多平面按所选 plane 的 compatible element size；还须检查 queue-family 附加对齐约束。不是通用 max(block,4) 公式。[SPEC] | bufferOffset 不对齐。[TOOL] |
| `bufferRowLength` / `bufferImageHeight` | 0 / 0 表示 tight packing；非 0 用于 row padding。[SPEC] | 误填导致 image 行错位。[ENGINE] |
| `imageSubresource` | 同 `VkImageCopy`；aspectMask 必须匹配格式。[SPEC] | depth/stencil copy 时 aspectMask 选错。[SPEC] |
| `imageOffset` / `imageExtent` | 压缩格式按相应命令的 block 对齐及到达 mip 边缘的 extent 例外检查。[SPEC] | 同上。[TOOL] |

### 5.4 VkImageBlit

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcSubresource` / `dstSubresource` | 同 `VkImageCopy`。[SPEC] | — |
| `srcOffsets[2]` / `dstOffsets[2]` | 两端边界坐标定义 3D 区域（不是包含终点 texel 的索引）；允许轴翻转，尺寸可不同。[SPEC] | 把 [1] 当作 extent 而非 endpoint。[TOOL] |

### 5.5 VkImageResolve

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcSubresource` / `dstSubresource` | src 必须多采样、dst 必须单采样；普通 VkImageResolve 的两个 aspectMask 必须为 COLOR（00266）。[SPEC] | src / dst samples 不符合 resolve 规则。[SPEC] |
| `srcOffset` / `dstOffset` / `extent` | 必须落在各自 image 范围内。[SPEC] | extent 越界。[TOOL] |

---

## 6. 正确性检查点

### Layout 检查

- [ ] copy / blit / resolve 前后 image 是否处于正确 layout？[SPEC]
  - `vkCmdCopyImage` src：`GENERAL` 或 `TRANSFER_SRC_OPTIMAL`；dst：`GENERAL` 或 `TRANSFER_DST_OPTIMAL`。[SPEC]
  - `vkCmdBlitImage` src：`GENERAL` 或 `TRANSFER_SRC_OPTIMAL`；dst：`GENERAL` 或 `TRANSFER_DST_OPTIMAL`。[SPEC]
  - `vkCmdResolveImage` src：`GENERAL` 或 `TRANSFER_SRC_OPTIMAL`；dst：`GENERAL` 或 `TRANSFER_DST_OPTIMAL`。[SPEC]
  - `vkCmdCopyBufferToImage` dst：`GENERAL` 或 `TRANSFER_DST_OPTIMAL`。[SPEC]
  - `vkCmdCopyImageToBuffer` src：`GENERAL` 或 `TRANSFER_SRC_OPTIMAL`。[SPEC]

### Usage 检查

- [ ] src 资源是否含 `TRANSFER_SRC_BIT`？[SPEC]
- [ ] dst 资源是否含 `TRANSFER_DST_BIT`？[SPEC]

### 格式兼容性检查

- [ ] `vkCmdCopyImage` 的 src / dst 格式是否兼容（相同格式，或同 size + 同 block extent 的兼容格式）？[SPEC]
- [ ] `vkCmdBlitImage` 的 src / dst 是否为 color / depth / stencil 同类格式？LINEAR filter 不支持 depth/stencil 格式。[SPEC]
- [ ] `vkCmdResolveImage` 的 src / dst 格式是否完全相同？[SPEC]

### 对齐检查

- [ ] `vkCmdFillBuffer` 的 offset / size 是否 4 字节对齐？[SPEC]
- [ ] `vkCmdCopyBufferToImage` / `vkCmdCopyImageToBuffer` 的 bufferOffset 是否满足格式对齐？[SPEC]
- [ ] 压缩格式的 image copy / blit region 是否按 block size 对齐？[SPEC]

### 同步检查

- [ ] transfer 命令前是否有 barrier 保证 src 数据已就绪？[SPEC]
- [ ] transfer 命令后是否有 barrier 让消费方 stage 可见（`dstStageMask` / `dstAccessMask`）？[SPEC]

---

## 7. 高频错误

1. src / dst usage 缺少 `TRANSFER_SRC_BIT` / `TRANSFER_DST_BIT`。[SPEC]
2. 调用时实际 layout 不匹配所声明/允许的布局；GENERAL 也是合法布局，不能只因未使用 TRANSFER_*_OPTIMAL 就判错。[TOOL]
3. `vkCmdBlitImage` 误用 LINEAR filter 处理 depth / stencil 格式。[SPEC]
4. `vkCmdResolveImage` src / dst samples 不匹配（src 必须 MS，dst 必须 1×）。[SPEC]
5. 压缩格式 region 未按 texel block 对齐。[SPEC]
6. `vkCmdFillBuffer` offset / size 非 4 字节对齐。[SPEC]
7. Staging 上传写入未对 shader read 建立可见性，或实际/描述符布局不匹配；GENERAL 下同样可以正确采样。[TOOL]
8. Mipmap 链使用错误 oldLayout，或漏掉前一级 TRANSFER_WRITE 到下一级 TRANSFER_READ 的依赖；一次 barrier 包含多个正确 subresource barrier 并不天然错误。[ENGINE]
9. `VkImageBlit` 的 `Offsets[1]` 误写为 extent 而非终点坐标。[TOOL]
10. 同一 command buffer 内连续多次 blit 同一 image，但未对每个 src level 单独 barrier，导致 hazard。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdCopyImage-*` / `VUID-vkCmdCopyBuffer-*`：usage / layout / 对齐 / 越界。
- `VUID-vkCmdBlitImage-*`：格式兼容性 / filter 限制 / sample count。
- `VUID-vkCmdResolveImage-*`：src / dst samples 一致性。
- `VUID-vkCmdFillBuffer-*`：offset / size 对齐。
- `VUID-vkCmdCopyBufferToImage-*` / `VUID-vkCmdCopyImageToBuffer-*`：bufferOffset 对齐 / aspectMask。

### RenderDoc / AGI

- 检查 image 内容、layout transition、resource usage 状态。
- RenderDoc 可逐 command 查看 copy / blit / resolve 的输入输出像素差异。
- AGI 可查看 transfer 命令的 GPU 耗时与 bandwidth 开销。[TOOL]

### 日志 / 代码检查

- 检查 src / dst usage 是否含 TRANSFER bit。
- 检查 src / dst image layout 在 copy / blit / resolve 时刻的状态。
- 检查 staging buffer 是否 HOST_VISIBLE；若非 HOST_COHERENT，正确 flush 并满足 nonCoherentAtomSize 范围，读回则检查 invalidate。
- 检查 mipmap 链中每级 blit 是否有正确的 layout 转换与 barrier。

---

## 9. 生命周期风险

### 命令记录时机

- transfer 命令必须在 primary command buffer 或支持的 secondary command buffer 内录制。[SPEC]
- 不可在 render pass 内调用 transfer 命令（核心规范）。[SPEC]

### 资源生命周期

- staging buffer 必须在 copy 命令完成后（fence signal 后）才能释放。[SPEC]
- mipmap 链生成过程中 src level 的数据必须保持稳定，不允许同时被 GPU 写入。[ENGINE]

### in-flight 风险

- 多帧并发时，staging buffer 需 per-frame-in-flight 分配，避免上一帧 copy 未完成就被覆盖。[ENGINE]
- transfer command buffer 引用的 image / buffer 在 fence signal 前不可销毁。[SPEC]

---

## 10. 同步风险

### Stage / Access 选择

- transfer 命令的执行 stage 是 `VK_PIPELINE_STAGE_TRANSFER_BIT`。[SPEC]
- src 端：读取 transfer source 之前的 barrier，srcAccessMask 应包含实际 producer 的写，例如 COLOR_ATTACHMENT_WRITE；TRANSFER_READ 是读，不能充当 producer 写。[SPEC]
- dst 端：transfer 之前按目标操作设 dstAccess 为 TRANSFER_READ/WRITE；transfer 之后 srcAccess 通常为 TRANSFER_WRITE，dstAccess 为实际 consumer 访问。[SPEC]
- 上游 producer：`srcStageMask` 设为 producer 的 stage（如 `COLOR_ATTACHMENT_OUTPUT` / `COMPUTE_SHADER`），`srcAccessMask` 设为 producer 的 write access。[SPEC]
- 下游 consumer：`dstStageMask` 设为 consumer 的 stage（如 `VERTEX_SHADER` / `FRAGMENT_SHADER` / `COMPUTE_SHADER`），`dstAccessMask` 设为 consumer 的 read access（`SHADER_READ` / `INPUT_ATTACHMENT_READ` 等）。[SPEC]

### 链式 transfer

- 多次 transfer 串联（如 mipmap 链）必须按顺序插入 barrier，保证上一级 transfer 写入完成后再被下一级读取。[SPEC]
- 遵守各命令 source/destination 内存重叠约束；不能在同一命令内部靠 barrier 修复非法 overlap。需要时使用独立临时资源和分开的合法命令/依赖。[SPEC]

### Queue 跨界

- 跨 queue family 使用 EXCLUSIVE 资源需按所有权规则进行 release/acquire，并建立跨队列同步；CONCURRENT sharing 在列出的 families 间不要求这种 ownership transfer，但仍需同步。[SPEC]

---

## 11. Android 注意点

- 移动端 copy/blit 的内部实现和代价取决于设备、格式与负载；不能从 API 名称推定专用硬件或比 graphics pass 更快。[ENGINE]
- 大尺寸 texture 上传应优先使用 staging buffer + `vkCmdCopyBufferToImage`，避免 `vkMapMemory` image。[ENGINE]
- `LINEAR` tiling image 在移动端 copy 性能较差，避免用作 transfer 目标。[ENGINE]
- ASTC / ETC2 copy 按规范检查 offset 块对齐、extent 到 mip 边缘例外和 queue 的 minImageTransferGranularity；不要用驱动容忍代替合法性。[TOOL]
- AGI 可观测 transfer 带宽，用于评估 staging 流量是否合理。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 避免每帧录制大量小 copy；可使用 `vkCmdCopyBuffer2`（Vulkan 1.3）一次性提交多个 region。[ENGINE]
- staging buffer 使用 suballocate（环形 / 分块）减少 `vkAllocateMemory` 调用。[ENGINE]
- `vkCmdUpdateBuffer` 适用于 ≤ 65536 字节的小数据；超限为非法调用，API 不承诺自动回退；应用需显式选 staging copy。[SPEC]

### GPU 侧

- 多个不重叠的 copy region 可合并到一次 `vkCmdCopyBuffer` 调用，减少 command 开销。[ENGINE]
- Mipmap 生成若使用 compute shader 自定义 downsample 可能比 `vkCmdBlitImage` LINEAR 质量更好（如法线 / 高频纹理），需结合场景选择。[ENGINE]
- Resolve 带宽不能简单等同 samples × region size；tile/local resolve、压缩和缓存会改变实际流量，应测量目标设备且区分附件 resolve 与独立 transfer resolve。[ENGINE]

### 移动端

- 减少 per-frame staging 流量，优先在 load 阶段一次性上传。[ENGINE]
- 大型 texture upload 可分帧进行，避免单帧带宽尖峰造成 jank。[ENGINE]
- 部分移动 GPU 对 `vkCmdBlitImage` LINEAR filter 性能优于 shader-based downsample；但质量受限，需评估。[ENGINE]

---

## 13. 专家经验

**经验**：
Copy / Blit / Resolve 三者看似都是“搬运”，但同步语义差别显著：
- `vkCmdCopyImage` 不做格式转换与缩放，没有缩放/过滤语义；应核对相应 format/region/layout 合同，性能必须测量，不能据此声称最稳定。
- `vkCmdBlitImage` 引入过滤，开销随区域与 filter 变化，且不支持 depth/stencil LINEAR。
- `vkCmdResolveImage` 是独立 color transfer resolve；附件 resolve 在渲染操作中执行，usage、stage/access、可选 mode 和 depth/stencil 路径不同，不能概括为完全等价。
这些传统 transfer 命令属于 `TRANSFER` 同步范围，与 producer / consumer 必须有适当执行/内存依赖（本卡单队列示例用 barrier，跨提交可用符合范围的 semaphore 等）；漏 barrier 在 Validation Layer 未必每次捕获，但在多 queue / 多 pass / Async compute 场景下会以 corruption 形式出现。

**适用条件**：
所有涉及 GPU 侧资源搬运 / 上传 / 下采样 / MSAA resolve 的场景。

**使用边界**：
- CPU 侧需要读取 GPU 数据：本卡仍适用，可使用 `vkCmdCopyImageToBuffer` + readback buffer + fence。
- 跨 queue 传输大量数据：需评估是否值得，通常 transfer queue 与 graphics queue 并发收益有限。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `buffer.md`
- `image.md`
- `image_layout.md`
- `memory_allocation.md`
- `../08_synchronization/pipeline_barrier.md`
- `../08_synchronization/image_memory_barrier.md`
- `../08_synchronization/buffer_memory_barrier.md`
- `../03_command_buffer/command_buffer.md`

---

## 15. 需要回查官方文档的情况

1. 特定压缩格式（BC / ASTC / ETC2）的 texel block extent 与 copy region 对齐规则。
2. `vkCmdBlitImage` 在 depth / stencil / integer 格式上的 filter 限制细则。
3. `vkCmdCopyImage` 的格式兼容性完整对照表（特别是 size-of-texel-block 等价的格式对）。
4. `VK_KHR_copy_commands2` 在目标设备的支持与 `*2` 版本结构体差异。
5. 跨 queue family ownership transfer 与 transfer 命令的交互。
6. vkCmdResolveImage 的 color-only region 合同；depth/stencil 使用相应附件 resolve 路径并查询 supported modes、independentResolve 等限制，不能直接套用此命令。
7. 同一 image 同时作为 src / dst（mipmap 链生成）时 layout 与 hazard 规则的最新 VUID。


<a id="delivery19-msaa-resolve-sampling"></a>
## Delivery19：4× color attachment resolve → fragment sampling

测试仓 `cases19/msaa_sample/run.py` 是 GPU 生成多样本颜色、dynamic rendering 附件 resolve，再用同一个 resolve image view 在第二个 fragment pass 采样的限定入口。它与上面的 `vkCmdResolveImage` transfer 路径必须分开选择。[ENGINE]

- 首先查询 format/image type/tiling/usage 的完整组合支持以及 sampleCounts；4× 还需 framebufferColorSampleCounts 允许，pipeline rasterizationSamples 与源附件匹配。查询支持并不代替实际 feature enable；本路径要求 core1.3 dynamicRendering 实际启用。缺少所需能力返回 unsupported，不伪装执行通过。[SPEC]
- 普通非整数 RGBA8_UNORM color attachment 使用 AVERAGE resolve；普通整数 color 使用 SAMPLE_ZERO 而不是照搬平均。本路径不启用 multisampled-render-to-single-sampled 特例：源 samples>1，resolve view samples=1，两个 view format 相同，均有实际 COLOR_ATTACHMENT usage，resolve布局合法。分别参见冻结1.4.309 `VkRenderingAttachmentInfo` 06129/06130、06861、06862、06864、06865。[SPEC]
- 附件 resolve 的 producer 为 COLOR_ATTACHMENT_OUTPUT/COLOR_ATTACHMENT_WRITE，后续 fragment 采样要求 FRAGMENT_SHADER/SHADER_READ 可见性。resolve image 还需 SAMPLED usage，descriptor 的 imageLayout 与实际访问布局一致。GENERAL 可以贯穿两次操作，但不免除依赖。不能把附件 resolve 的访问当成 TRANSFER_WRITE。[SPEC]
- 三个互异 image/view 对应多样本源、单样本 resolve、单样本最终输出。最终输出才进行 transfer copy/fence/coherent readback；不能由最终参考推称已分别抓取所有中间样本。[ENGINE]
- full-screen、端点色、无几何边缘的固定 shader 让所有覆盖样本同色；独立非对称16像素参考验证 resolve 后采样及通道重排。此设计故意不测抗锯齿质量、sample位置/coverage差异、gamma/HDR、precision或移动GPU带宽收益。[TOOL]
- single-source 负控在源只有1样本却仍指定AVERAGE resolve时，必须得到唯一06861；Validation callback中止 BeginRendering，整条CB弃置、不提交。单独wrong-output模式应真实返回非零。验证层拒绝记录不等于GPU执行过非法resolve。[TOOL]

回退/拒绝：若4×组合不支持，应用可明确选择已验证的1× render_sample路径，重新创建对应pipeline/resources并关闭resolve；这不是保留MSAA质量的等价回退。本入口不自动把unsupported算作pass。depth/stencil resolve、traditional RenderPass、mixed samples、render-to-single-sampled扩展和物理/外部工程/Live验收仍独立未验。[ENGINE]

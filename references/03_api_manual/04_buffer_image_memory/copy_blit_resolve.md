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

- Copy / Blit / Resolve 完成后，必须通过 `vkCmdPipelineBarrier` 把 layout 转换为消费方所需状态（如 `SHADER_READ_ONLY_OPTIMAL`）。[SPEC]
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

- `VK_KHR_copy_commands2`（Vulkan 1.3 核心 `vkCmdCopyBuffer2` / `vkCmdCopyImage2` / `vkCmdBlitImage2` / `vkCmdResolveImage2` / `vkCmdCopyBufferToImage2` / `vkCmdCopyImageToBuffer2`）：单次记录多条 copy、统一结构体。[SPEC]
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
3. for i in 1..mipLevels:
     srcLevel = i - 1, dstLevel = i
     barrier: srcLevel (TRANSFER_DST_OPTIMAL → TRANSFER_SRC_OPTIMAL)
              srcStage = TRANSFER, srcAccess = TRANSFER_WRITE
              dstStage = TRANSFER, dstAccess = TRANSFER_READ
     vkCmdBlitImage(image, TRANSFER_SRC_OPTIMAL, image, TRANSFER_DST_OPTIMAL,
                    &blitRegion, filter = LINEAR)
   注：src/dst 为同一 image 是合法的。
4. barrier: 所有非 0 level (TRANSFER_DST_OPTIMAL → SHADER_READ_ONLY_OPTIMAL)
5. level 0 同样转为 SHADER_READ_ONLY_OPTIMAL
```

### 4.3 MSAA resolve 路径

```text
1. 多采样 color attachment（samples = 2/4/8），usage 含 COLOR_ATTACHMENT | TRANSFER_SRC
2. 单采样 resolve image（samples = 1），usage 含 TRANSFER_DST | COLOR_ATTACHMENT（或 SAMPLED）
3. 渲染到多采样 attachment
4. barrier: src = COLOR_ATTACHMENT_OUTPUT / COLOR_ATTACHMENT_WRITE
            dst = TRANSFER / TRANSFER_READ
            srcMS image: COLOR_ATTACHMENT_OPTIMAL → TRANSFER_SRC_OPTIMAL
            dstSS image: UNDEFINED → TRANSFER_DST_OPTIMAL
5. vkCmdResolveImage(srcMS, TRANSFER_SRC_OPTIMAL, dstSS, TRANSFER_DST_OPTIMAL, ...)
6. barrier: dstSS image → SHADER_READ_ONLY_OPTIMAL 或 PRESENT_SRC_KHR
```

---

## 5. 关键字段

### 5.1 VkBufferCopy

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcOffset` / `dstOffset` | 必须落在 src / dst buffer 范围内。[SPEC] | 越界导致 validation error 或 device lost。[TOOL] |
| `size` | 拷贝字节数；非 4 字节倍数时需保证 src / dst offset 也是非 4 倍数且范围一致，但 Vulkan 1.0 起已不强制 4 字节对齐（仍需在 memory requirements 内）。[SPEC] | 误用未对齐 offset 触发 VUID。[TOOL] |

### 5.2 VkImageCopy

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcSubresource` / `dstSubresource` | mipLevel / baseArrayLayer / layerCount 必须在源 / 目标范围内；aspectMask 必须匹配格式。[SPEC] | depth/stencil 格式 aspectMask 写成 `COLOR_BIT`。[SPEC] |
| `srcOffset` / `dstOffset` / `extent` | 对压缩格式（BC / ASTC / ETC2），offset 与 extent 必须是 texel block size 的整数倍。[SPEC] | 用压缩格式按非块对齐拷贝触发 VUID。[TOOL] |

### 5.3 VkBufferImageCopy

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `bufferOffset` | 必须是格式 texel block size 与 4 字节的较大者的整数倍。[SPEC] | bufferOffset 不对齐。[TOOL] |
| `bufferRowLength` / `bufferImageHeight` | 0 / 0 表示 tight packing；非 0 用于 row padding。[SPEC] | 误填导致 image 行错位。[ENGINE] |
| `imageSubresource` | 同 `VkImageCopy`；aspectMask 必须匹配格式。[SPEC] | depth/stencil copy 时 aspectMask 选错。[SPEC] |
| `imageOffset` / `imageExtent` | 对压缩格式必须按 block 对齐。[SPEC] | 同上。[TOOL] |

### 5.4 VkImageBlit

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcSubresource` / `dstSubresource` | 同 `VkImageCopy`。[SPEC] | — |
| `srcOffsets[2]` / `dstOffsets[2]` | 起点 + 终点（含）的 3D 区域；可不同尺寸，自动缩放。[SPEC] | 把 [1] 当作 extent 而非 endpoint。[TOOL] |

### 5.5 VkImageResolve

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcSubresource` / `dstSubresource` | src 必须多采样、dst 必须单采样；aspectMask 必须匹配。[SPEC] | src / dst samples 不符合 resolve 规则。[SPEC] |
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
2. image layout 未转换到 `TRANSFER_*_OPTIMAL` 就调用 copy / blit / resolve。[TOOL]
3. `vkCmdBlitImage` 误用 LINEAR filter 处理 depth / stencil 格式。[SPEC]
4. `vkCmdResolveImage` src / dst samples 不匹配（src 必须 MS，dst 必须 1×）。[SPEC]
5. 压缩格式 region 未按 texel block 对齐。[SPEC]
6. `vkCmdFillBuffer` offset / size 非 4 字节对齐。[SPEC]
7. Staging 上传完成后未 barrier 到 `SHADER_READ_ONLY_OPTIMAL`，导致 shader 读取未定义数据。[TOOL]
8. Mipmap 链中 src level 与 dst level 同时 barrier 转换，导致 src 还未稳定就被读取。[ENGINE]
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
- 检查 staging buffer 是否为 HOST_VISIBLE | HOST_COHERENT。
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
- src 端：`srcAccessMask` 应含 `VK_ACCESS_TRANSFER_READ_BIT`（前置 producer 的写）。[SPEC]
- dst 端：`dstAccessMask` 应含 `VK_ACCESS_TRANSFER_WRITE_BIT` 或 `VK_ACCESS_TRANSFER_READ_BIT`。[SPEC]
- 上游 producer：`srcStageMask` 设为 producer 的 stage（如 `COLOR_ATTACHMENT_OUTPUT` / `COMPUTE_SHADER`），`srcAccessMask` 设为 producer 的 write access。[SPEC]
- 下游 consumer：`dstStageMask` 设为 consumer 的 stage（如 `VERTEX_SHADER` / `FRAGMENT_SHADER` / `COMPUTE_SHADER`），`dstAccessMask` 设为 consumer 的 read access（`SHADER_READ` / `INPUT_ATTACHMENT_READ` 等）。[SPEC]

### 链式 transfer

- 多次 transfer 串联（如 mipmap 链）必须按顺序插入 barrier，保证上一级 transfer 写入完成后再被下一级读取。[SPEC]
- 同一 image 多 region 同时 copy：必须保证 region 之间无 overlap，否则需 split barrier。[SPEC]

### Queue 跨界

- 跨 queue family 的 transfer 资源需进行 ownership transfer（barrier 中 `srcQueueFamilyIndex` / `dstQueueFamilyIndex`）。[SPEC]

---

## 11. Android 注意点

- 移动端 GPU 的 copy / blit 通常走专用 transfer 路径或 compute，开销低于图形 pass。[ENGINE]
- 大尺寸 texture 上传应优先使用 staging buffer + `vkCmdCopyBufferToImage`，避免 `vkMapMemory` image。[ENGINE]
- `LINEAR` tiling image 在移动端 copy 性能较差，避免用作 transfer 目标。[ENGINE]
- ASTC / ETC2 压缩格式 copy 时 region 必须严格按 block 对齐，部分驱动对未对齐 region 直接 fail。[TOOL]
- AGI 可观测 transfer 带宽，用于评估 staging 流量是否合理。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 避免每帧录制大量小 copy；可使用 `vkCmdCopyBuffer2`（Vulkan 1.3）一次性提交多个 region。[ENGINE]
- staging buffer 使用 suballocate（环形 / 分块）减少 `vkAllocateMemory` 调用。[ENGINE]
- `vkCmdUpdateBuffer` 适用于 ≤ 65536 字节的小数据；超限会触发 validation error 或回退到 copy。[SPEC]

### GPU 侧

- 多个不重叠的 copy region 可合并到一次 `vkCmdCopyBuffer` 调用，减少 command 开销。[ENGINE]
- Mipmap 生成若使用 compute shader 自定义 downsample 可能比 `vkCmdBlitImage` LINEAR 质量更好（如法线 / 高频纹理），需结合场景选择。[ENGINE]
- Resolve 操作的带宽 = samples × region size，移动端 4× MSAA resolve 开销显著。[ENGINE]

### 移动端

- 减少 per-frame staging 流量，优先在 load 阶段一次性上传。[ENGINE]
- 大型 texture upload 可分帧进行，避免单帧带宽尖峰造成 jank。[ENGINE]
- 部分移动 GPU 对 `vkCmdBlitImage` LINEAR filter 性能优于 shader-based downsample；但质量受限，需评估。[ENGINE]

---

## 13. 专家经验

**经验**：
Copy / Blit / Resolve 三者看似都是“搬运”，但同步语义差别显著：
- `vkCmdCopyImage` 不做格式转换与缩放，性能最稳定，但对 layout、对齐、格式兼容性要求最严。
- `vkCmdBlitImage` 引入过滤，开销随区域与 filter 变化，且不支持 depth/stencil LINEAR。
- `vkCmdResolveImage` 是 MS 专属路径，与 render pass 内 resolve 在功能上等价但时机不同。
所有 transfer 命令执行在 `TRANSFER` stage，必须与 producer / consumer 通过 barrier 显式串联；漏 barrier 在 Validation Layer 未必每次捕获，但在多 queue / 多 pass / Async compute 场景下会以 corruption 形式出现。

**适用条件**：
所有涉及 GPU 侧资源搬运 / 上传 / 下采样 / MSAA resolve 的场景。

**不适用情况**：
- CPU 侧需要读取 GPU 数据：应使用 `vkCmdCopyImageToBuffer` + readback buffer + fence。
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
6. `vkCmdResolveImage` 在 depth/stencil 多采样格式上的支持与限制。
7. 同一 image 同时作为 src / dst（mipmap 链生成）时 layout 与 hazard 规则的最新 VUID。

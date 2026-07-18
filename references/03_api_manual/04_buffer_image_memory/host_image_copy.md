# API Card: Host Image Copy

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | Host Image Copy |
| 常用 API | `vkCopyMemoryToImageEXT` / `vkCopyImageToMemoryEXT` / `vkCopyImageToImageEXT` / `vkTransitionImageLayoutEXT` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | `VK_EXT_host_image_copy` 扩展 / Vulkan 1.4 promote（非 mandatory，仍需查询启用 feature） |

---

## 1. 一句话定位

`VK_EXT_host_image_copy`（Vulkan 1.4 将 API promote 进 core 但非 mandatory）提供一组 host 侧 image 拷贝 API：CPU 内存与 image 之间、image 之间可在 host 端直接拷贝，并支持 host 侧 layout 转换，无需 staging buffer、无需 command buffer、无需 GPU 参与，特别适合初始化阶段一次性上传纹理、减少 GPU bandwidth 占用。[SPEC]

---

## 2. 所属对象链路

```text
VkPhysicalDevice（查询 hostImageCopy feature / VkHostImageCopyDevicePerformanceQueryEXT）
→ VkDevice（启用 hostImageCopy feature — 即使 Vulkan 1.4 也必须查询并启用）
→ VkImage（创建时 flags 含 VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT）
→ host 侧操作:
    vkTransitionImageLayoutEXT (image layout 转换，纯 host)
    vkCopyMemoryToImageEXT (host memory → image)
    vkCopyImageToMemoryEXT (image → host memory)
    vkCopyImageToImageEXT (image → image)
→ vkTransitionImageLayoutEXT 转换到 GPU 消费 layout
→ 后续 GPU 命令正常使用（无需 barrier 串联 host 拷贝）
```

### 上游依赖

- `VkPhysicalDevice` 必须支持 `VK_EXT_host_image_copy`（1.4 之前）或在 1.4+ 设备上通过 `VkPhysicalDeviceHostImageCopyFeaturesEXT.hostImageCopy` 查询确认。[SPEC]
- 必须启用 `hostImageCopy` feature（`VkPhysicalDeviceHostImageCopyFeaturesEXT`）；Vulkan 1.4 promote 了 API 但 feature 仍需显式查询与启用。[SPEC]
- `VkImage` 创建时 `flags` 必须含 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT`。[SPEC]
- 目标 image 的 `usage`、`format`、`tiling` 必须支持 host image copy（查询 `vkGetImageSubresourceLayout2EXT` / performance query）。[SPEC]

### 下游影响

- Host 拷贝完成后，image 即处于 host 写入的 layout，需通过 `vkTransitionImageLayoutEXT` 转换到 GPU 可消费 layout（如 `SHADER_READ_ONLY_OPTIMAL`）。[SPEC]
- 转换后 GPU 可立即使用，无需 staging buffer / `vkCmdCopyBufferToImage` 路径。[SPEC]
- 减少初始化阶段的 command buffer / fence / staging 资源开销。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkImage`（创建时 `flags` 含 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT`）
- `VkMemoryToImageCopyEXT` / `VkImageToMemoryCopyEXT` / `VkImageToImageCopyEXT`
- `VkHostImageLayoutTransitionInfoEXT`
- `VkHostImageCopyDevicePerformanceQueryEXT`（性能查询）
- `VkPhysicalDeviceHostImageCopyFeaturesEXT`（feature）

### 常用 API

| API | 作用 |
|---|---|
| `vkCopyMemoryToImageEXT` | 把 host 内存（`pHostPointer`）按 region 拷贝到 image；纯 host 操作。[SPEC] |
| `vkCopyImageToMemoryEXT` | 把 image 按 region 拷贝到 host 内存；可用于 readback。[SPEC] |
| `vkCopyImageToImageEXT` | image 之间的 host 侧拷贝，支持 layout / subresource 指定。[SPEC] |
| `vkTransitionImageLayoutEXT` | 在 host 侧转换 image layout，无需 command buffer。[SPEC] |
| `vkGetImageSubresourceLayout2EXT` | 查询 image 的 host 侧内存布局（行距、偏移等）。[SPEC] |
| `vkGetPhysicalDeviceHostImageCopyPropertiesEXT` | 查询该设备支持 host copy 的 format / layout 组合。[SPEC] |

### 相关扩展 / 版本

- `VK_EXT_host_image_copy` 扩展：原始扩展，提供全部 host image copy 功能。[SPEC]
- Vulkan 1.4：将 `VK_EXT_host_image_copy` 的 API promote 进 core（无需扩展字符串），但 `hostImageCopy` feature 仍为可选，必须通过 `VkPhysicalDeviceHostImageCopyFeaturesEXT` 查询并在 `VkDeviceCreateInfo.pNext` 中启用。[SPEC]
- `VK_KHR_maintenance5` / `VK_KHR_maintenance6`：与 host image copy 在 layout 查询、format 支持上有协同关系。[SPEC]
- Android 可用性：Vulkan 1.4 设备需查询 `hostImageCopy` feature 是否支持；早期版本需 device 支持 `VK_EXT_host_image_copy` 扩展。[ANDROID]

---

## 4. 标准使用流程

### 4.1 Host Image Upload（替代 staging buffer 路径）

```text
1. 查询 / 启用 hostImageCopy feature
   - Vulkan 1.4 设备：API 已 promote 进 core，但仍需通过 VkPhysicalDeviceFeatures2 + VkPhysicalDeviceHostImageCopyFeaturesEXT 查询并启用
   - 早期设备：需启用 VK_EXT_host_image_copy 扩展，再查询 VkPhysicalDeviceHostImageCopyFeaturesEXT

2. 创建 image:
   VkImageCreateInfo.flags |= VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT
   usage 含 SAMPLED / STORAGE 等目标用途
   tiling 通常 OPTIMAL（host copy 不要求 LINEAR）

3. 分配并绑定 image memory（按 vkGetImageMemoryRequirements）

4. vkTransitionImageLayoutEXT:
     oldLayout = UNDEFINED (or PREINITIALIZED)
     newLayout = VK_IMAGE_LAYOUT_HOST_COPY_ALIGNMENT_PLAN_... 或 General
   （host copy 的中间 layout，具体见 spec）

5. vkCopyMemoryToImageEXT:
     pHostPointer = CPU 端纹素数据指针
     hostImageLayout = 上述 host-copy layout
     pImageSubresource / imageOffset / imageExtent 按 region 拷贝

6. vkTransitionImageLayoutEXT:
     oldLayout = host-copy 中间 layout
     newLayout = SHADER_READ_ONLY_OPTIMAL / GENERAL / 目标 GPU layout

7. GPU 即可在后续 command buffer 中直接使用该 image，无需 barrier 串联 host copy
```

### 4.2 Image Readback（替代 vkCmdCopyImageToBuffer + readback）

```text
vkTransitionImageLayoutEXT: GPU layout → host-readable layout
vkCopyImageToMemoryEXT:
  pHostPointer = CPU 端接收 buffer
  按 region 拷贝
vkTransitionImageLayoutEXT: 回到原 GPU layout（如 SHADER_READ_ONLY_OPTIMAL）
```

### 4.3 Host 侧 Image-to-Image 拷贝

```text
vkTransitionImageLayoutEXT (srcImage → host-copy layout)
vkTransitionImageLayoutEXT (dstImage → host-copy layout)
vkCopyImageToImageEXT(srcImage, dstImage, regionCount, pRegions)
vkTransitionImageLayoutEXT (dstImage → GPU 消费 layout)
```

### 4.4 与 staging buffer 路径的差异对比

| 维度 | staging buffer 路径 | host image copy 路径 |
|---|---|---|
| 中间资源 | 需 staging `VkBuffer` + memory | 直接 host 指针，无 staging |
| 命令执行 | command buffer + submit + fence | 纯 host API，无 command buffer |
| GPU 参与 | `vkCmdCopyBufferToImage` 占用 GPU transfer | GPU 不参与，释放 transfer queue 带宽 |
| Layout 转换 | `vkCmdPipelineBarrier` | `vkTransitionImageLayoutEXT`（host 侧） |
| 同步开销 | fence wait | 无 fence，host 操作即时完成 |
| 适用阶段 | 运行时动态上传 / mipmap 生成 | 初始化阶段一次性上传、readback |

---

## 5. 关键字段

### VkMemoryToImageCopyEXT / VkImageToMemoryCopyEXT

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `pHostPointer` | host 端 CPU 内存指针，必须按格式 texel block size 与 4 字节较大者对齐。[SPEC] | 传入未对齐指针触发 validation error。[TOOL] |
| `hostImageLayout` | image 在 host copy 时的 layout，必须为 spec 允许的 host-copy layout。[SPEC] | 误用 `SHADER_READ_ONLY_OPTIMAL` 等 GPU-only layout。[TOOL] |
| `pImageSubresource` | mipLevel / baseArrayLayer / layerCount / aspectMask 必须在 image 范围内。[SPEC] | aspectMask 与 depth/stencil 格式不匹配。[SPEC] |
| `imageOffset` / `imageExtent` | 压缩格式必须按 texel block size 对齐。[SPEC] | 压缩格式 region 未按 block 对齐。[TOOL] |
| `memoryRowLength` / `memoryImageHeight` | 0/0 表示 tight packing；非 0 用于 row padding。[SPEC] | 误填导致行错位。[ENGINE] |

### VkImageToImageCopyEXT

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcImageLayout` / `dstImageLayout` | 必须为 host-copy 兼容 layout。[SPEC] | 误用 GPU layout。[TOOL] |
| `srcSubresource` / `dstSubresource` | aspectMask 必须匹配格式；mipLevel / layer 在范围内。[SPEC] | src/dst 格式不兼容（host image-image copy 要求格式兼容）。[SPEC] |

### VkHostImageLayoutTransitionInfoEXT

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `oldLayout` / `newLayout` | oldLayout 必须为当前实际 layout（或 UNDEFINED）。[SPEC] | oldLayout 与实际不符导致内容丢失。[TOOL] |
| `subresourceRange` | 必须覆盖实际待转换的 mip / layer 范围。[SPEC] | 范围漏写导致部分 subresource layout 错乱。[TOOL] |

### VkImageCreateInfo

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `flags` | 必须含 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT`。[SPEC] | 漏掉 flag 后调用 host copy API 触发 validation error。[TOOL] |
| `tiling` | 通常 `OPTIMAL` 即可，host copy 不要求 LINEAR。[SPEC] | 误以为必须 LINEAR，造成 GPU 访问性能下降。[HEUR] |
| `usage` | 必须覆盖后续 GPU 用途（如 `SAMPLED_BIT`）。[SPEC] | 缺 `SAMPLED_BIT` 但 shader 要采样。[TOOL] |

### VK_HOST_IMAGE_COPY_MEMCPY_BIT_EXT

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| flag 语义 | 表示对应 region 的 host 数据可按 memcpy 直接拷贝（image 内存布局与 host 紧凑布局一致）。[SPEC] | 误以为所有 region 都可 memcpy；实际上需要 query layout 确认。[TOOL] |
| 使用场景 | 用于 `vkCopyMemoryToImageEXT` / `vkCopyImageToMemoryEXT`，由 spec 定义何种 layout 组合可标 memcpy。[SPEC] | 自行假定 memcpy 安全，未 query `vkGetImageSubresourceLayout2EXT`。[ENGINE] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否启用 `hostImageCopy` feature？Vulkan 1.4 promote 了 API 但 feature 仍需显式查询与启用。[SPEC]
- [ ] `VkImageCreateInfo.flags` 是否含 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT`？[SPEC]
- [ ] image 的 format / usage / tiling 组合是否被 host image copy 支持？（查询 `vkGetPhysicalDeviceHostImageCopyPropertiesEXT`）[SPEC]
- [ ] 是否评估过 `VkHostImageCopyDevicePerformanceQueryEXT`，确认 host copy 不会显著慢于 GPU copy？[ENGINE]

### 使用阶段

- [ ] host copy 前 image 是否已通过 `vkTransitionImageLayoutEXT` 转换到 host-copy 兼容 layout？[SPEC]
- [ ] host 拷贝指针是否满足对齐要求？[SPEC]
- [ ] 压缩格式的 region 是否按 texel block size 对齐？[SPEC]
- [ ] host copy 完成后是否通过 `vkTransitionImageLayoutEXT` 转换到 GPU 消费 layout？[SPEC]
- [ ] depth/stencil 格式 aspectMask 是否正确？[SPEC]

### 销毁阶段

- [ ] 销毁 image 前是否确认 GPU 不再使用？（host copy 本身不需要 fence，但 GPU 后续使用需要常规同步）[SPEC]
- [ ] host 端 buffer 在 host copy 完成前是否保持有效？[SPEC]

---

## 7. 高频错误

1. `VkImageCreateInfo.flags` 缺少 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT`，调用 host copy API 触发 validation error。[SPEC]
2. 未启用 `hostImageCopy` feature（早期设备）就调用 `vkCopyMemoryToImageEXT`。[SPEC]
3. host 拷贝指针未按格式 texel block size + 4 字节较大者对齐。[SPEC]
4. 压缩格式（BC / ASTC / ETC2）region 未按 block size 对齐。[SPEC]
5. host copy 前 / 后未通过 `vkTransitionImageLayoutEXT` 完成 layout 转换，导致 GPU 读到未定义数据。[TOOL]
6. 误用 GPU-only layout（如 `SHADER_READ_ONLY_OPTIMAL`）作为 host copy 的 `hostImageLayout`。[TOOL]
7. depth/stencil 格式 aspectMask 写成 `COLOR_BIT`。[SPEC]
8. 自行假定 `VK_HOST_IMAGE_COPY_MEMCPY_BIT_EXT` 一定可用，未 query 实际 image layout。[ENGINE]
9. 运行时频繁用 host copy 上传大纹理，未评估 GPU staging 路径性能对比。[ENGINE]
10. Vulkan 1.4 之前设备未检查扩展支持，直接调用 host copy API。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkImageCreateInfo-flags-09203`：使用 host copy API 时 image flags 必须含 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT`。[SPEC]
- `VUID-vkCopyMemoryToImageEXT-*`：host pointer 对齐 / region 对齐 / layout 合法性。
- `VUID-vkTransitionImageLayoutEXT-*`：oldLayout / newLayout / subresourceRange 合法性。
- `VUID-vkCopyImageToImageEXT-*`：src/dst 格式兼容性 / aspectMask / region 对齐。

### RenderDoc / AGI

- RenderDoc 对 host image copy 的捕获支持取决于版本；老版本可能无法显示 host 拷贝事件。[TOOL]
- AGI 可观测 host copy 是否减少了 GPU transfer 带宽占用。[TOOL]
- 验证 host copy 后 image 内容是否正确，可通过 readback（`vkCopyImageToMemoryEXT`）比对。[ENGINE]

### 日志 / 代码检查

- 检查 `VkImageCreateInfo.flags` 是否含 host image copy bit。
- 检查 `hostImageCopy` feature 是否在 device 创建时启用（Vulkan 1.4 之前）。
- 检查 host 拷贝指针的对齐与生命周期。
- 检查 host copy 前后的 layout transition 是否完整。
- 对比性能：相同纹理分别用 staging 与 host copy，评估 `VkHostImageCopyDevicePerformanceQueryEXT` 返回的 `optimalDeviceAccess` / `identicalMemoryLayout` 字段。

---

## 9. 生命周期风险

### 创建时机

- Image 创建时必须设 `VK_IMAGE_CREATE_HOST_IMAGE_COPY_BIT_EXT` flag，事后无法补加。[SPEC]
- Device 创建时必须启用 `hostImageCopy` feature；Vulkan 1.4 promote 了 API 但 feature 仍需显式启用。[SPEC]

### 使用时机

- host copy API 不需要 command buffer / fence，调用即时返回。[SPEC]
- host copy 与 GPU 访问必须串行：GPU 正在读写 image 时不能同时 host copy。[SPEC]
- 通过 `vkTransitionImageLayoutEXT` 切换 host 与 GPU 之间的"所有权"。[SPEC]

### 销毁时机

- Image 销毁前必须确认 GPU 不再引用（按常规 fence / `vkDeviceWaitIdle`）。[SPEC]
- Host 端源 buffer 在 `vkCopyMemoryToImageEXT` 返回前必须保持有效。[SPEC]

### in-flight 风险

- 多帧并发时，若 image 被 GPU 使用，host copy 必须等 GPU fence signal。[ENGINE]
- 不要在 GPU pipeline barrier 与 host layout transition 之间制造竞争：layout 由谁管，必须明确归属。[SPEC]
- readback（`vkCopyImageToMemoryEXT`）前必须确保 GPU 已完成 image 写入（fence wait）。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- host copy 本身是同步操作，调用即完成；不需要 fence / semaphore。[SPEC]
- 但 host copy 与 GPU 之间需要通过 fence / `vkDeviceWaitIdle` 隔离：GPU 正在写 image 时不能 host read，反之亦然。[SPEC]
- `vkTransitionImageLayoutEXT` 完成 layout 转换后，GPU 命令链中无需再插入 barrier 串联 host 操作。[SPEC]

### GPU-GPU 同步

- host copy 完成后 image 的 GPU 使用仍按常规 pipeline barrier / render pass attachment layout 处理。[SPEC]
- host layout transition 不替代 GPU 侧 barrier：跨 queue / 跨 stage 仍需 GPU 同步。[SPEC]

### 资源访问同步

- `vkCopyMemoryToImageEXT` 的 host 端写入与 GPU 端读取通过 layout transition + fence 共同保证可见性。[SPEC]
- 不再需要 staging buffer 的 `HOST_COHERENT` 内存保证：host pointer 由调用方提供，host copy 完成即生效。[SPEC]
- `vkCopyImageToMemoryEXT` 读取 image 数据前必须保证 GPU 写入已完成（fence wait）。[SPEC]

---

## 11. Android 注意点

- Vulkan 1.4 Android 设备需查询 `hostImageCopy` feature 是否支持（promote 不等于 mandatory）；早期设备需查询 `VK_EXT_host_image_copy` 扩展。[ANDROID][SPEC]
- 移动 GPU（Mali / Adreno）的 OPTIMAL tiling 通常不暴露线性布局，host copy 内部可能仍需 tiling 转换，性能优势不如桌面明显。[ENGINE][ANDROID]
- Android 上的 host pointer 必须是已映射或外部内存（如 AHardwareBuffer），不能用任意栈指针。[ANDROID]
- 初始化阶段大量纹理上传时，host copy 可减少 staging buffer 内存占用与 GC 压力，移动端收益显著。[ENGINE][ANDROID]
- AGI 可观测 host copy 是否减少了 GPU transfer queue 占用，验证性能收益。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- host copy 避免了 staging buffer 分配 / map / unmap / fence wait 的 CPU 开销。[ENGINE]
- `vkTransitionImageLayoutEXT` 在 host 侧执行，无需 command buffer 录制 / submit，CPU 调用开销低。[ENGINE]
- 但 host layout transition 在某些 image layout 间可能比 GPU barrier 更慢（具体由 `VkHostImageCopyDevicePerformanceQueryEXT` 评估）。[SPEC]

### GPU 侧

- host copy 释放 transfer queue 带宽，避免与运行时其他 transfer 命令竞争。[ENGINE]
- 对初始化阶段大量纹理上传，host copy 可显著降低 GPU bandwidth 占用，让 GPU 专注渲染。[ENGINE]
- `VkHostImageCopyDevicePerformanceQueryEXT.optimalDeviceAccess = VK_FALSE` 时，host copy 后的 image 在 GPU 上的访问性能可能不如 GPU staging 路径，需评估取舍。[SPEC]

### 移动端

- 移动端初始化阶段一次性纹理上传是 host copy 的最佳场景。[ENGINE][ANDROID]
- 运行时动态上传（如视频纹理 / streaming texture）应优先评估 GPU staging 路径，避免 host copy 阻塞渲染线程。[ENGINE]
- `identicalMemoryLayout = VK_TRUE` 时，host copy 等价于 memcpy，性能最优；否则内部需要 format / layout 转换。[SPEC]

---

## 13. 专家经验

**经验**：
Host Image Copy 不是 staging buffer 的"全面替代品"，而是初始化阶段纹理上传的更优路径。决策树：

1. 一次性初始化上传（启动 / 加载场景）：优先 host copy，省 staging、省 fence、省 GPU 带宽。
2. 运行时动态上传（每帧 / 流式纹理）：优先 GPU staging + `vkCmdCopyBufferToImage`，避免 host copy 在渲染线程上阻塞。
3. Readback（截图 / GPU 数据回读）：评估 `vkCopyImageToMemoryEXT` vs `vkCmdCopyImageToBuffer` + readback buffer，前者更直接但可能与 GPU pipeline 竞争。
4. Image-to-image 拷贝（初始化副本）：host copy 可避免占用 transfer queue。

关键检查点：`VkHostImageCopyDevicePerformanceQueryEXT` 的 `optimalDeviceAccess` 与 `identicalMemoryLayout` 决定了 host copy 后的 image 在 GPU 上是否仍能高效访问；若 `optimalDeviceAccess = VK_FALSE`，应评估是否回到 GPU staging 路径。Vulkan 1.4 promote 了 API 但 `hostImageCopy` feature 仍为可选，需按目标设备查询并启用。

**适用条件**：
- 初始化阶段大量纹理上传。
- 资源加载阶段无 GPU 渲染压力。
- 需要 readback 但不希望占用 transfer queue。
- Vulkan 1.4 设备或支持 `VK_EXT_host_image_copy` 的早期设备。

**不适用情况**：
- 运行时每帧动态上传（host copy 阻塞渲染线程）。
- 需要 mipmap 链生成（仍需 GPU `vkCmdBlitImage` 或 compute）。
- 压缩格式 + 未对齐 region（spec 不允许）。
- 性能敏感的 image-to-image 拷贝（评估 GPU `vkCmdCopyImage` 是否更优）。

**来源**：`[ENGINE][SPEC][TOOL]`

---

## 14. 相关 API 卡片

- `image.md`
- `image_layout.md`
- `image_view.md`
- `copy_blit_resolve.md`
- `buffer.md`
- `memory_allocation.md`
- `../08_synchronization/image_memory_barrier.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. `vkTransitionImageLayoutEXT` 允许的 `oldLayout` / `newLayout` 组合完整列表，特别是哪些 layout 是 host-copy 兼容的。
2. `VK_HOST_IMAGE_COPY_MEMCPY_BIT_EXT` 在何种 format / tiling / layout 组合下可被设置的精确规则。
3. `VkHostImageCopyDevicePerformanceQueryEXT` 各字段的精确语义与厂商行为差异。
4. Vulkan 1.4 中 host image copy 函数是否保留 EXT 后缀，还是有 core 别名（无后缀版本）。
5. `vkGetPhysicalDeviceHostImageCopyPropertiesEXT` 返回的 supported format / layout 组合的完整解释。
6. Android 上 `VK_ANDROID_external_memory_android_hardware_buffer` 与 host image copy 的交互（AHardwareBuffer 作为 host pointer 是否合法）。
7. host image copy 与 sparse image / external memory / protected memory 的兼容性。
8. host layout transition 与 GPU pipeline barrier 在同一 image 上的时序约束与最新 VUID。

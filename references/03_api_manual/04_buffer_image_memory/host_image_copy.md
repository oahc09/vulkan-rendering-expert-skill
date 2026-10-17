# API Card: Host Image Copy

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 |
| Vulkan 对象 | Host Image Copy |
| 常用 API | `vkCopyMemoryToImage` / `vkCopyImageToMemory` / `vkCopyImageToImage` / `vkTransitionImageLayout`（扩展路径使用对应 `EXT` 别名） |
| 适用平台 | 通用，包括 Android；按设备查询 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | `VK_EXT_host_image_copy` / Vulkan 1.4；均须启用 `hostImageCopy` feature |
| 核验基线 | Vulkan registry / headers / validusage 1.4.365；官方链接见 §15 |

---

## 1. 一句话定位

Host Image Copy 提供同步的 host 侧 image 上传、回读、image-to-image 拷贝及 layout transition，省去该次拷贝的 staging buffer 和 command buffer；它不免除与已有 GPU 访问之间的同步，也不保证比 GPU copy 更快。[SPEC][ENGINE]

Vulkan 1.4 提供无后缀 core 名称，原 `EXT` 名称保留为别名。`hostImageCopy` 在 1.4 中仍可选：具有 graphics queue 的实现必须支持该 feature，或提供额外的 transfer-capable queue。无论走哪条 API 路径，使用前仍要查询并启用 feature。[SPEC] [官方 promotion 说明](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_host_image_copy.html)

---

## 2. 所属对象链路

```text
VkPhysicalDevice
→ 查询 hostImageCopy feature、host-copy layout 列表及 image format 支持
→ VkDevice（启用 hostImageCopy；扩展路径还需启用扩展及依赖）
→ VkImage（usage 包含 VK_IMAGE_USAGE_HOST_TRANSFER_BIT）
→ 分配并绑定满足该 image requirements 的 memory
→ 等待冲突的 GPU / host 访问完成，建立必要的内存依赖
→ 合法 layout 下调用 host copy；必要时调用 host layout transition
→ 后续 queue submission / GPU 使用遵守正常同步与 layout 规则
```

### 上游依赖

- 用 `vkGetPhysicalDeviceFeatures2` 查询 `VkPhysicalDeviceHostImageCopyFeatures`，或 Vulkan 1.4 的 `VkPhysicalDeviceVulkan14Features.hostImageCopy`；创建设备时启用。不要在同一链上重复放入聚合 feature 结构及其所包含的单独 feature 结构。[SPEC]
- `VkImageCreateInfo.usage` 包含 `VK_IMAGE_USAGE_HOST_TRANSFER_BIT`（扩展别名 `VK_IMAGE_USAGE_HOST_TRANSFER_BIT_EXT`），并覆盖 sampled、storage 等实际用途。这是 usage，不是 image creation flag。[SPEC]
- 通过 `vkGetPhysicalDeviceFormatProperties2` + `VkFormatProperties3` 检查目标 tiling 的 `VK_FORMAT_FEATURE_2_HOST_IMAGE_TRANSFER_BIT`，再用 `vkGetPhysicalDeviceImageFormatProperties2` 验证完整 format/type/tiling/usage/flags 组合。[SPEC]
- `vkGetPhysicalDeviceProperties2` 的输出链挂 `VkPhysicalDeviceHostImageCopyProperties`，先查询数量，再提供数组取得 `pCopySrcLayouts` / `pCopyDstLayouts`。`GENERAL` 必须出现在两者中。[SPEC]

### 下游影响

- Copy 使用指定的当前 layout，不自动改变 layout。若该 layout 同时适用于后续 GPU 用途，可以保留；否则执行合法的 host 或 GPU transition。[SPEC]
- host copy 不要求 image 使用 `LINEAR` tiling，也不要求应用自己映射 image memory；必须按实际 memory requirements 选择分配类型。[SPEC]

---

## 3. 核心对象与 API

以下采用 Vulkan 1.4 core 拼写；对应 `EXT` 别名用于扩展路径。`VkImageCopy2` 的早期别名为 `VkImageCopy2KHR`。[SPEC]

| API / 结构 | 作用 |
|---|---|
| `vkCopyMemoryToImage(device, pCopyMemoryToImageInfo)` | `VkCopyMemoryToImageInfo` 指定目标 image/layout；regions 为 `VkMemoryToImageCopy` |
| `vkCopyImageToMemory(device, pCopyImageToMemoryInfo)` | `VkCopyImageToMemoryInfo` 指定源 image/layout；regions 为 `VkImageToMemoryCopy` |
| `vkCopyImageToImage(device, pCopyImageToImageInfo)` | `VkCopyImageToImageInfo` 指定源/目标 image/layout；regions 为 `VkImageCopy2` |
| `vkTransitionImageLayout(device, transitionCount, pTransitions)` | `VkHostImageLayoutTransitionInfo` 数组描述 host 侧 layout 转换 |
| `vkGetPhysicalDeviceProperties2` | 输出链查询 `VkPhysicalDeviceHostImageCopyProperties` |
| `vkGetPhysicalDeviceImageFormatProperties2` | 验证 image 参数；输出链可挂 `VkHostImageCopyDevicePerformanceQuery` |
| `vkGetImageSubresourceLayout2` | 输出链挂 `VkSubresourceHostMemcpySize`，查询 MEMCPY 模式所需大小；不是通用 format 支持查询 |

上述 copy / transition 命令返回 `VkResult`；检查结果，不能把失败当作已完成的上传。[SPEC]

---

## 4. 标准使用流程

### 4.1 Host Image Upload（普通纹素数据，flags = 0）

```text
1. 查询并启用 hostImageCopy；查询支持的 layouts 和完整 image 参数组合。
2. 创建 image：usage = HOST_TRANSFER | SAMPLED（按实际用途补充）。
3. 分配并绑定 image memory。
4. 对新建且未使用的 image：vkTransitionImageLayout
     oldLayout = VK_IMAGE_LAYOUT_UNDEFINED
     newLayout = VK_IMAGE_LAYOUT_GENERAL
   subresourceRange 覆盖实际需要上传的 mip / layer / aspect。
5. 填写 VkMemoryToImageCopy region：
     pHostPointer = 有效且足够大的 CPU 端数据
     memoryRowLength = 0; memoryImageHeight = 0（紧密排列）
     imageSubresource / imageOffset / imageExtent = 目标区域
   填写 VkCopyMemoryToImageInfo：
     flags = 0; dstImage = image; dstImageLayout = GENERAL
     regionCount / pRegions = region 数组
   调用 vkCopyMemoryToImage(device, &info)，检查返回值。
6. 后续 GPU 可以在 GENERAL 中使用该 image（descriptor 等必须一致）；
   若需要 SHADER_READ_ONLY_OPTIMAL 等 layout，先确认 host transition 的
   新 layout 在 pCopyDstLayouts 中，否则使用正常的 GPU transition。
7. 上传在后续 queue submission 前完成；该提交提供 host→device 可见性。
```

若最终采样 layout 已在 `pCopyDstLayouts` 中，也可先 transition 到该 layout 再直接上传，省去中间转换。不能把 `SHADER_READ_ONLY_OPTIMAL` 一概称作禁止 host copy 的 layout。[SPEC]

### 4.2 Image Readback

1. 对 GPU 写过的源 image，在设备上建立写入到 `HOST` stage / `HOST_READ` access 的 memory barrier，并安排合法 layout。[SPEC]
2. 等待相关 GPU 工作完成，例如等待覆盖这些命令的 fence；仅等待不替代上一项内存依赖。[SPEC]
3. 选用 `pCopySrcLayouts` 中的当前 layout；需要 host transition 时先验证 old/new layout 条件。[SPEC]
4. 填写 `VkCopyImageToMemoryInfo` 和 `VkImageToMemoryCopy`，调用并检查结果。成功返回后读取 host 目标内存。[SPEC]
5. 若后续 GPU 使用要求另一个 layout，再安排合法 transition 与后续同步。[SPEC]

### 4.3 Host 侧 Image-to-Image 拷贝

- 源、目标必须使用相同 image creation parameters；不是一般意义上“格式兼容即可”。双方均需满足 host-transfer usage、内存绑定、样本数、region 及 layout 规则。[SPEC]
- `VkCopyImageToImageInfo.pRegions` 指向 `VkImageCopy2` 数组；调用形式是 `vkCopyImageToImage(device, &info)`。[SPEC]
- 源 layout 必须在 `pCopySrcLayouts` 中，目标 layout 必须在 `pCopyDstLayouts` 中；先同步此前冲突访问，必要时为 GPU 写入建立 host 可读依赖。[SPEC]

### 4.4 与 staging buffer 路径的差异对比

| 维度 | staging buffer 路径 | host image copy 路径 |
|---|---|---|
| 中间资源 | `VkBuffer` + memory | 普通 host 指针；无需 staging buffer |
| 执行 | command buffer + queue submission | 同步 host 调用 |
| Layout 转换 | 设备端 barrier 等 | 可用受 layout 列表约束的 host transition |
| 已有 GPU 访问 | 通过设备/host 同步协调 | 同样必须处理冲突及可见性 |
| 性能取舍 | 可异步运行，消耗传输资源 | 消耗 CPU 时间；收益需测量 |

---

## 5. 关键字段

### `VkMemoryToImageCopy` / `VkImageToMemoryCopy`

| 字段 | 正确语义与检查点 |
|---|---|
| `pHostPointer` | 普通 host 内存，上传时可读、回读时可写，且覆盖寻址规则访问的全部字节；保持生命周期直到调用完成 |
| `imageSubresource` | 值类型 `VkImageSubresourceLayers`，不是指针；aspect 单 bit，mip / layer 在合法范围 |
| `imageOffset` / `imageExtent` | 受 image 边界和格式块约束；压缩格式需按 block 规则检查，包括 image 边缘例外 |
| `memoryRowLength` / `memoryImageHeight` | 以 texel 为单位，不是字节；0 使用 extent 对应尺寸，非 0 满足尺寸与块对齐规则 |

Layout 位于外层 `VkCopyMemoryToImageInfo.dstImageLayout` 或 `VkCopyImageToMemoryInfo.srcImageLayout`，不在 region 结构中。不能套用 buffer-copy offset 的对齐要求，臆造 `pHostPointer` 必须按 max(4, texel block size) 对齐的通则。[SPEC]

### `VkCopyImageToImageInfo` / `VkImageCopy2`

外层包含 `srcImage`、`srcImageLayout`、`dstImage`、`dstImageLayout`、`flags`、`regionCount`、`pRegions`；region 使用 `srcSubresource`、`srcOffset`、`dstSubresource`、`dstOffset`、`extent`。[SPEC]

### `VkHostImageLayoutTransitionInfo`

- `image` 必须具备 host-transfer usage；`subresourceRange` 指定待转换范围。[SPEC]
- `oldLayout` 为实际当前 layout 或 `UNDEFINED`；后者允许丢弃原有内容。[SPEC]
- 除规范列出的初始 layout 特例外，old layout 必须来自 `pCopySrcLayouts`；new layout 必须来自 `pCopyDstLayouts`。还须满足各 layout 对 image usage / feature 的独立限制。[SPEC]
- 转换 layout 不执行 queue-family ownership transfer，也不等待 GPU 完成。[SPEC]

### `VK_HOST_IMAGE_COPY_MEMCPY_BIT`

此 flag 表示不做内存布局 swizzle 转换。memory↔image 拷贝的 host 数据已采用与设备 image 相同的实现相关布局，并不表示普通紧密排列像素可直接 memcpy 到 optimal image。[SPEC]

- 使用 `vkGetImageSubresourceLayout2` + `VkSubresourceHostMemcpySize` 查询所需存储大小。[SPEC]
- MEMCPY 模式要求 offset 为零、extent 覆盖所选 subresource 的完整 extent；memory↔image 的 `memoryRowLength` / `memoryImageHeight` 均为零。[SPEC]
- 保存和恢复这种不透明数据时检查布局兼容性，包括 `optimalTilingLayoutUUID`；不要把它当作跨设备通用纹理文件格式。[SPEC][ENGINE]

---

## 6. 正确性检查点

- [ ] feature 已支持并启用；旧版本设备启用相应扩展及依赖。[SPEC]
- [ ] image 的 usage 含 HOST_TRANSFER；完整 image 参数组合查询成功。[SPEC]
- [ ] 内存绑定、sample count、aspect、mip、layer、region 边界均符合 valid usage。[SPEC]
- [ ] copy layout 与当前 layout 一致，并在相应源/目标列表中。[SPEC]
- [ ] host 指针容量、读写权限、生命周期及 row/image stride 正确。[SPEC]
- [ ] 已处理冲突的 GPU/host 访问；GPU readback 已建立 host-read 内存依赖并等待完成。[SPEC]
- [ ] 检查每次 `VkResult`；失败路径保留 staging fallback。[ENGINE]
- [ ] 销毁前所有后续 GPU 使用已完成。[SPEC]

---

## 7. 高频错误

1. 把 host-transfer usage 当成 creation flag，或创建时漏掉它。[SPEC]
2. Vulkan 1.4 未启用 `hostImageCopy` 就调用功能。[SPEC]
3. 将 layout 字段写到 region；将 `imageSubresource` 当作指针。[SPEC]
4. 把支持列表以外的 layout 用于 copy 或 host transition。[SPEC]
5. GPU readback 只等 fence，漏掉写入到 HOST_READ 的内存依赖。[SPEC]
6. 认为 layout transition 等同于 ownership transfer 或 GPU completion。[SPEC]
7. 把普通像素数据配合 MEMCPY flag，造成错误的内存布局解释。[SPEC]
8. 认为 `identicalMemoryLayout` 表示“image 布局等同线性 CPU 像素”。[SPEC]
9. 压缩格式区域不满足 block 及边缘规则。[SPEC]
10. 用 host image-to-image 执行仅格式兼容、创建参数不同的 image 拷贝。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

以下是本卡核验基线中的实际 VUID（以 core 结构名记录），不是扩展命令名通配占位符：[SPEC]

- `VUID-VkCopyMemoryToImageInfo-dstImage-09113`：访问非 stencil aspect 时的 HOST_TRANSFER usage。
- `VUID-VkCopyMemoryToImageInfo-dstImageLayout-09059` / `09060`：当前 layout 与支持列表。
- `VUID-VkMemoryToImageCopy-pHostPointer-09061`：源 host 内存足够大。
- `VUID-VkCopyImageToImageInfo-srcImage-09069`：两 image 创建参数相同。
- `VUID-VkHostImageLayoutTransitionInfo-image-09055`：transition image 的 HOST_TRANSFER usage。
- `VUID-VkHostImageLayoutTransitionInfo-oldLayout-09229` / `09230`、`VUID-VkHostImageLayoutTransitionInfo-newLayout-09057`：transition 的 layout 条件。

### 工具与日志

- 开启 validation，记录 feature、usage、format 查询结果、layout 列表、每个 region 和 `VkResult`。[TOOL][ENGINE]
- Capture 工具是否完整记录 host copy 应按实际工具版本验证；不要以缺少传输事件推断没有数据移动。[TOOL]
- 用已正确同步的回读验证纹理内容；分别计量 CPU 调用时间、加载时间和后续 GPU 访问成本。[ENGINE]

---

## 9. 生命周期风险

- HOST_TRANSFER usage 在创建时确定；不能事后补加。[SPEC]
- host copy 是同步 host 操作，但可能耗时；“同步”不代表立即返回或不会阻塞调用线程。[SPEC][ENGINE]
- 调用期间保持 host 数据有效，并按规范同步对 image memory 的冲突 host/device 访问。[SPEC]
- 成功完成上传后可释放源 host 数据；image 本身必须存活到所有后续 GPU 使用结束。[SPEC]

---

## 10. 同步风险

### Host → Device

`vkCopyMemoryToImage` 以 coherent 方式访问 image memory。成功拷贝在后续 queue submission 之前完成时，提交的隐式 host→device 内存域操作提供可见性；无需仅为了此次 host 写入另加 memory barrier。布局转换、先前 GPU 访问、队列所有权和其他 GPU 依赖仍需单独处理。[SPEC] [上传同步说明](https://docs.vulkan.org/refpages/latest/refpages/source/vkCopyMemoryToImage.html)

### Device → Host

设备写入不会自动对 host copy 可用。回读前须在设备上发出目标 scope 包含 `VK_PIPELINE_STAGE_HOST_BIT` / `VK_ACCESS_HOST_READ_BIT` 的 memory barrier，再等待对应执行完成；Synchronization2 路径使用对应 `*_2_*` stage/access 位。Host copy 对 image memory 的 coherent 访问不能替代该 barrier。[SPEC] [回读同步说明](https://docs.vulkan.org/refpages/latest/refpages/source/vkCopyImageToMemory.html)

### Layout / Ownership

Host transition 只转换指定 subresource 的 layout。它不是 queue-family ownership transfer，不能代替 semaphore、fence 或设备端内存依赖，也不能使正在执行的 GPU 访问自动安全。[SPEC]

---

## 11. Android 注意点

- Android 同样按 Vulkan API version、扩展、feature、format/usage 组合查询，不根据操作系统版本推断支持。[SPEC][ANDROID]
- 普通有效的 host 内存可以作为 `pHostPointer`，包括生命周期足够长的栈或堆内存；没有“必须用 AHardwareBuffer 或 Vulkan mapped memory”的要求。[SPEC]
- `AHardwareBuffer*` 对象句柄不是像素数据指针。涉及外部内存、外部格式时另查导入、映射、布局、usage 及同步规则，不能把句柄直接交给 host copy。[SPEC]
- 移动设备上的 CPU 成本、内存带宽、温度及 GPU 访问性能需实测，不能宣称收益必然显著。[ENGINE][ANDROID]

---

## 12. 性能注意点

`VkHostImageCopyDevicePerformanceQuery` 挂在 `VkImageFormatProperties2.pNext`，输入 `VkPhysicalDeviceImageFormatInfo2.usage` 包含 HOST_TRANSFER。[SPEC]

- `optimalDeviceAccess`：相比其他参数及绑定内存相同、以 TRANSFER_SRC/DST 替换 HOST_TRANSFER usage 的 image，host-copy image 的设备访问是否没有不利影响。[SPEC]
- `identicalMemoryLayout`：上述两种创建方式的 memory layout 是否相同；不比较 CPU 线性像素布局，也不是 copy 耗时或 host transition 耗时估计。[SPEC]
- `identicalMemoryLayout = VK_TRUE` 时 `optimalDeviceAccess` 必须为真；反向不成立。[SPEC]
- 查询不证明 host copy 比 GPU staging 更快。测量同步等待、CPU copy、流式加载吞吐和后续采样/渲染性能，再选路径。[ENGINE]

[性能属性官方语义](https://docs.vulkan.org/refpages/latest/refpages/source/VkHostImageCopyDevicePerformanceQuery.html)

---

## 13. 专家经验

Host image copy 是初始化和流式上传的候选路径，不限于一次性初始化，也不是所有设备上的最佳选择。[ENGINE]

1. 保留 staging fallback，根据支持情况与实测选择。
2. 将较重的 host copy 安排到资源工作线程，并维护清晰的资源访问状态。
3. 若后续 GPU 访问成本占主导，特别关注 `optimalDeviceAccess`。
4. 回读优先保证正确的 device→host 依赖，再比较直接回读与 staging buffer。
5. Copy 不生成 mipmap；逐级提供 mip 数据或另行生成。

**来源**：`[ENGINE][SPEC]`

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

本卡结构名、字段、别名和 VUID 对照本地 `evidence/vk.xml`、`evidence/registry-audit/vulkan_core.h` 与 `evidence/registry-audit/validusage.json`（1.4.365）；以下官方在线页面用于解释语义，在线版本可能继续更新。[SPEC]

- [扩展与 Vulkan 1.4 promotion](https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_host_image_copy.html)
- [Feature 查询与启用](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceHostImageCopyFeatures.html)
- [支持的 layout 列表及 UUID](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceHostImageCopyProperties.html)
- [上传信息与 valid usage](https://docs.vulkan.org/refpages/latest/refpages/source/VkCopyMemoryToImageInfo.html)
- [Host layout transition 条件](https://docs.vulkan.org/refpages/latest/refpages/source/VkHostImageLayoutTransitionInfo.html)
- [Image-to-image 创建参数及 regions](https://docs.vulkan.org/refpages/latest/refpages/source/VkCopyImageToImageInfo.html)
- [MEMCPY flag 的不透明 swizzled 数据语义](https://docs.vulkan.org/refpages/latest/refpages/source/VkHostImageCopyFlagBits.html)
- [MEMCPY 大小查询](https://docs.vulkan.org/refpages/latest/refpages/source/VkSubresourceHostMemcpySize.html)

遇到 depth/stencil separate usage、multi-planar、sparse、protected/external memory、压缩格式边缘区域、MEMCPY 数据跨设备复用或新增 layout 扩展时，逐项回查目标 SDK 对应的完整 valid usage；本卡流程不替代这些条件。[SPEC]

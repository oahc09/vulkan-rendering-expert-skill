# Render Graph 资源生命周期

本文件建立 Render Graph / Frame Graph 中资源生命周期管理的核心心智模型。它不替代 `resource_lifecycle.md` 中对单个 `VkImage` / `VkBuffer` 生命周期的描述，而是在更高层抽象（虚资源、Pass DAG、瞬时内存复用）上回答：何时分配、何时别名、何时插入 barrier、何时销毁。[ENGINE][GUIDE]

参考实现包括 Granite Frame Graph（Themaister）、EA Frostbite Frame Graph、Unreal RDG、Unity SRP 的 RTHandle 体系，思路相通但有细节差异。[ENGINE]

---

## 1. 概述 — Render Graph 概念

### 一句话定位

Render Graph（亦称 Frame Graph）是一种声明式渲染管线抽象：开发者用虚资源 + Pass DAG 描述"这一帧要做什么"，由 graph 编译器决定"实际怎么执行"。[GUIDE][ENGINE]

### 两阶段执行模型

```text
Setup / Compile 阶段（CPU）：
  1. 声明虚资源（TextureDescription / BufferDescription）
  2. 注册 Pass，声明 read / write 引用
  3. 构建 DAG，拓扑排序
  4. 剔除未被任何输出 Pass 引用的资源与 Pass（dead pass elimination）
  5. 计算每个 transient 资源的生命区间 [first_use, last_use]
  6. 计算物理资源分配计划（aliasing）
  7. 计算每个 pass 边界的 resource state（layout / access / stage）

Execute 阶段（CPU 录 command buffer，GPU 执行）：
  1. 按拓扑序遍历 pass
  2. 在 pass 入口插入 barrier（自动生成）
  3. 创建 / 复用物理资源
  4. 执行 pass 回调，向 command buffer 录入 draw / dispatch
  5. 在 pass 出口更新资源 state
  6. last_use 后释放 transient 物理资源（实际是把 alias 槽位让出）
```

[ENGINE][GUIDE]

### 核心收益

```text
- 资源分配与同步从手写代码下沉到 graph 编译器。
- transient 资源可通过 aliasing 共享同一块 VkDeviceMemory，显著降低峰值显存。
- pass 顺序可被优化（在不破坏依赖前提下重排），减少无意义 barrier。
- 渲染管线意图（高层数据流）与 Vulkan 执行细节解耦。
```

[ENGINE][GUIDE]

### 不适用情况

- 极小 demo 或一次性脚本渲染，graph 编译开销 > 收益。[HEUR]
- 资源生命周期跨越多帧且依赖关系复杂（如 streaming texture），仍需外部 persistent allocator。[ENGINE]
- 严格实时嵌入式 GPU，aliasing 在某些 tile-based GPU 上需要特别处理。[VENDOR]

---

## 2. 资源声明与生命周期

### 虚资源 vs 物理资源

Render Graph 中的"资源"在 setup 阶段只是描述符：

```text
TextureDescription {
  format, extent, mip_levels, array_layers, samples, usage_flags
}
BufferDescription {
  size, usage_flags
}
```

此时的资源对象（如 `TextureHandle`）只是一个 ID，没有对应 `VkImage`、也没有分配 `VkDeviceMemory`。[ENGINE]

物理资源（`VkImage` / `VkBuffer` + 绑定的 memory）在 compile 阶段才决定是否分配、分配多大、和谁 alias。[ENGINE]

### Transient vs Persistent

```text
Transient Resource:
  - 仅在本次 graph 执行内部使用
  - 物理资源在 first_use 之前不存在，last_use 之后立即回收
  - 可参与 aliasing
  - 典型：GBuffer、shadow map、intermediate HDR color、downsample chain

Persistent / Imported Resource:
  - 从 graph 外部导入（swapchain image、persistent texture pool、streaming texture）
  - graph 不拥有其生命周期，仅记录读写状态
  - 不参与 aliasing
  - 典型：swapchain image、UI atlas、offscreen 跨帧持久 RT
```

[ENGINE][GUIDE]

### 生命区间计算

对每个 transient 资源 R：

```text
first_use[R] = min{ pass_index : pass 在 DAG 拓扑序中引用 R（read 或 write） }
last_use[R]  = max{ pass_index : pass 在 DAG 拓扑序中引用 R（write 一定计入，read 是否计入取决于是否需要保留到下一帧） }
live_interval[R] = [first_use[R], last_use[R]]
```

[ENGINE]

注意：如果一个资源是"上一帧 graph 的输出，下一帧 graph 的输入"，它不应声明为 transient，必须作为 imported persistent 资源在两帧之间由外部 owner 持有。[ENGINE]

### 资源版本（versioning）

每次 write 创建一个新版本：

```text
Resource A
  ├─ v0  (initial, undefined content)
  ├─ v1  (after Pass P1 writes)
  ├─ v2  (after Pass P3 writes)
```

后续 read 必须指向具体版本。版本用于 barrier 推导与 dead write 检测：如果一个 write 的版本从无 consumer 引用，可被剔除。[ENGINE]

### 风险点

1. 把跨帧持久资源误声明为 transient，导致 graph 在 last_use 后回收物理资源，下一帧引用悬空。[ENGINE]
2. setup 阶段访问资源内容（如 readback），但 graph 还没 execute，物理资源不存在。[ENGINE]
3. 把 imported persistent 资源当作 transient 试图 alias，会破坏外部 owner 的状态。[ENGINE]

---

## 3. Pass 之间的资源传递

### Pass DAG（有向无环图）

每个 Pass 声明：

```text
reads :  [ResourceHandle, version, access_pattern]
writes : [ResourceHandle, access_pattern]
```

边由"write → read"自动生成：

```text
Pass P1 writes A
Pass P2 reads A
  => edge P1 -> P2
```

[ENGINE]

### 拓扑排序

```text
1. 入度为 0 的 pass 入队
2. 出队一个 pass，对其所有后继减入度
3. 入度变 0 的后继入队
4. 直到所有 pass 出队
```

若图中存在环，说明资源依赖矛盾（典型：A 写资源 → B 读资源 → A 又写同一资源），是 graph 声明错误，必须在 setup 阶段报错。[ENGINE]

### Pass 重排与合并

拓扑序不唯一，graph 编译器可在此基础上优化：[ENGINE]

- 把无依赖的 pass 合并到同一 render pass / dynamic rendering 区间，减少 `vkCmdBeginRendering` / `vkCmdEndRendering` 开销。
- 把相邻的 compute pass 调度到同一 command buffer 段，减少 pipeline barrier。
- 把只读同一资源的多个 pass 放到同一 load/store 区间，避免 unecessary resolve。

### Read-after-Write 是默认契约

graph 默认所有 read-after-write 是 hazard，必须通过 barrier 解决。[SPEC] 同一 pass 内的 read 与 write 不构成跨 pass 依赖，但若多个 pass 在同一 queue 上写同一资源且无 read 间隔，仍然必须插入 barrier。[SPEC]

### Cross-queue 边

```text
P1 (graphics queue) writes A
P2 (compute queue) reads A
  => edge P1 -> P2 + queue ownership transfer barrier
     (release barrier on graphics, acquire barrier on compute)
```

跨 queue 边必须用 `VK_QUEUE_FAMILY_IGNORED` 之外的 ownership transfer，或使用 `VK_SHARING_MODE_CONCURRENT`。[SPEC]

### 风险点

1. 同一帧对同一资源既有 imported persistent read 又有 transient write，未声明清楚会被误判为可 alias。[ENGINE]
2. 拓扑序非唯一，但渲染顺序的"视觉正确性"（如透明物体在透明物体之后渲染）需要额外 hint 约束，不能只依赖 DAG 自动推导。[ENGINE]
3. Pass 重排优化可能破坏隐式时序假设（如"先渲染 opaque，再渲染 skybox"），需要显式 edge 约束。[ENGINE]

---

## 4. 物理资源分配策略

### 分配时机

```text
Setup 阶段：只创建虚资源，不分配物理资源
Compile 阶段：计算 aliasing 计划 + 创建物理资源（或预留 alias 槽位）
Execute 阶段：barrier 后实际使用
```

[ENGINE]

物理资源分配发生在 compile 阶段而非 execute 阶段，目的是在 execute 时只需"按计划取用"，避免运行时分配开销。[ENGINE]

### Aliasing 策略

若两个 transient 资源 A、B 满足：

```text
live_interval[A] 与 live_interval[B] 不相交
  => A 和 B 可共享同一块 VkDeviceMemory（甚至同一个 VkImage alias）
```

则称为 memory aliasing。实现方式：[SPEC][ENGINE]

```text
方案 A（推荐）：VK_MEMORY_ALLOCATE_FLAGS_DEVICE_ADDRESS_BIT + VMA virtual allocator
  - 在 compile 阶段为整段 transient heap 申请大块 VkDeviceMemory
  - 用 bump / offset allocator 把每个 transient 资源 sub-allocate 到该 heap 的某段 offset
  - 不同资源的 live_interval 不重叠时 offset 可重用

方案 B：VkImage / VkBuffer 创建时绑定到同一 VkDeviceMemory 的不同 offset
  - 要求资源支持 bind to memory offset
  - VkBindImageMemoryInfo / vkBindBufferMemory2
  - 必须遵守 alignment 与 memory type 兼容性

方案 C（不推荐）：VK_KHR_device_group + VK_EXT_image_drm_format_modifier 之类的 alias hint
  - 仅在特定平台有意义
```

[SPEC][ENGINE][TOOL]

### Aliasing 的 hazard 防护

```text
1. 同一 VkDeviceMemory offset 在新资源开始使用前，必须保证旧资源的 last_use 已通过 GPU 同步完成
   - 由 graph 自动插入的 execution dependency 保证
2. layout / format 切换的 alias 必须满足 VkImageFormatProperties 的 compatible usage
3. 移动端 tile-based GPU 上，alias 可能破坏 tile memory 复用，需实测
```

[SPEC][VENDOR][TOOL]

### Memory budget 与回退

```text
transient heap 大小由 graph 编译器根据所有 transient 资源的非重叠峰值估算
若峰值超过设备 budget：
  - 优先剔除 dead pass / unused resource
  - 把部分 transient 降级为 persistent（跨帧保留）
  - 报错并提示用户简化渲染管线
```

[ENGINE]

### Dedicated allocation 例外

某些资源（depth + stencil 互锁的 HiZ texture、特定 multisample resolve target）在部分驱动上要求 dedicated `VkDeviceMemory`，不能放入 alias heap。[SPEC][VENDOR] 这种资源应在 compile 阶段标记为 `requires_dedicated_allocation`，单独走 `vkAllocateMemory` 路径。[ENGINE]

### 风险点

1. Aliasing 计算遗漏了"资源在 last_use pass 内部仍然 live 到 pass 结束"，导致 next alias 资源在该 pass 内部就被复用，出现 RAW hazard。[ENGINE]
2. 不同 queue family 的资源 alias 时，ownership transfer barrier 未插入，导致跨 queue 访问读到 stale data。[SPEC]
3. VMA virtual allocator 的 alignment 未考虑 `VkImage` 的 `bufferImageGranularity`，导致 alias 偏移越界。[SPEC]

---

## 5. 与 Vulkan 对象的映射

### 虚资源 → 物理对象

```text
TextureHandle (virtual)
  → VkImage           (在 compile 阶段创建)
  → VkDeviceMemory    (绑定到 alias heap 的某个 offset，或 dedicated)
  → VkImageView       (按需创建，按 [format, aspect, usage, mip range, layer range] 缓存)
  → descriptor update 时引用 VkImageView + 当前 layout
```

[ENGINE]

### VkImageView 复用策略

```text
ImageViewKey = hash(image, viewType, format, subresourceRange, usage)
ImageViewCache[ImageViewKey] -> VkImageView

同一 VkImage 在不同 pass 中以不同 aspect / mip 被 sampled 时，
应复用缓存中的 VkImageView，而不是每个 pass 重新 vkCreateImageView。
```

[ENGINE]

`vkCreateImageView` 调用频次过高的开销不可忽略，特别是在 dynamic rendering 模式下，每帧 attachment 切换频繁。[ENGINE][TOOL]

### Imported Persistent 资源映射

```text
ImportedTexture {
  external VkImage,       // 外部创建并拥有
  external VkImageView,   // 或由 graph 按 key 查缓存创建
  external VkDeviceMemory // 外部管理
}

graph 仅记录 state（layout / access / stage），不创建 / 销毁底层对象。
```

[ENGINE]

典型例子：swapchain image 由 `vkGetSwapchainImagesKHR` 提供，graph 仅在 present 前把它 transition 到 `VK_IMAGE_LAYOUT_PRESENT_SRC_KHR`。[SPEC]

### Render Pass / Dynamic Rendering 映射

```text
Vulkan 1.3+ 默认使用 dynamic rendering (vkCmdBeginRendering)：
  - attachment 信息在 beginRendering 时传入
  - 不需要预创建 VkRenderPass / VkFramebuffer
  - 与 graph 的"按 pass 动态组合 attachment"天然契合

兼容路径（Vulkan 1.2 以下或必须用 tile attachment op 优化）：
  - graph 编译器把相邻 compatible pass 合并到一个 VkRenderPass
  - VkFramebuffer 按 [attachment set, extent, layer count] 缓存
```

[SPEC][ENGINE]

### Bindless 集成

```text
sampled transient texture 若参与 bindless descriptor set：
  - 在 pass execute 时通过 vkUpdateDescriptorSet（或 push descriptor）写入
  - 必须保证 graph 已把 layout transition 到 VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL（或 READ_ONLY_STORAGE）
  - update-after-bind 模式下，descriptor 写入与 GPU 读取间仍需正确同步
```

[SPEC][ENGINE]

### 风险点

1. graph 创建的 `VkImageView` 未随 graph 销毁而 `vkDestroyImageView`，导致 view 句柄泄漏。[ENGINE]
2. 同一 `VkImage` 在 alias 切换后仍使用旧 `VkImageView`，可能触发 validation `VUID-VkImageViewCreateInfo-image-09181` 之类错误（view 引用的 image 已被释放或 layout 不一致）。[SPEC]
3. Swapchain 重建时，imported persistent attachment 的 `VkImageView` 必须随 swapchain 一起重建，否则 present 时 image layout 不匹配。[SPEC][ANDROID]

---

## 6. 同步与 Barrier 自动化

### Resource State Tracking

graph 为每个资源版本维护：

```text
ResourceState {
  image_layout      // VK_IMAGE_LAYOUT_*
  access_mask       // VkAccessFlags2
  pipeline_stages   // VkPipelineStageFlags2
  queue_family      // 当前 owner
}
```

每个 pass 入口与出口时，graph 比较资源当前 state 与目标 state，生成 barrier。[ENGINE]

### Barrier 类型选择

```text
Layout change only (同 queue):
  => vkCmdPipelineBarrier2 with VkImageMemoryBarrier2

Layout change + ownership transfer (跨 queue):
  => release barrier on src queue + acquire barrier on dst queue
     两次 barrier，由 graph 在跨 queue 边自动插入

Buffer state change (storage buffer 从 compute 写到 graphics 读):
  => VkBufferMemoryBarrier2
```

[SPEC]

### Synchronization2 必备

Vulkan 1.3+ 默认使用 `VK_KHR_synchronization2`，统一为 `VkDependencyInfo` + `*Barrier2` 结构：[SPEC]

```text
vkCmdPipelineBarrier2(
  commandBuffer,
  &dependencyInfo  // 含 VkImageMemoryBarrier2 / VkBufferMemoryBarrier2 / VkMemoryBarrier2 数组
)
```

旧版 `vkCmdPipelineBarrier`（stage mask 旧式）不应在 graph 中使用，避免 stage/access mask 语义混乱。[GUIDE]

### Barrier Batching

graph 应在 pass 边界把同方向（srcStage → dstStage）的多个 barrier 合并到一个 `vkCmdPipelineBarrier2` 调用：[ENGINE][TOOL]

```text
Bad:
  for each resource in pass_inputs:
    vkCmdPipelineBarrier2(...)  // N 次调用

Good:
  collect all needed barriers into one VkDependencyInfo
  vkCmdPipelineBarrier2(...)  // 1 次调用
```

### 与 Timeline Semaphore 配合

跨 queue 提交时的同步：

```text
Graphics queue submit:
  wait timeline value V (compute 完成值)
  ... render passes ...
  signal timeline value V+1

Compute queue submit:
  wait timeline value V+1
  ... compute dispatches ...
  signal timeline value V+2
```

graph 在 compile 阶段已确定 queue 边，execute 时自动生成 timeline semaphore wait/signal。[SPEC][ENGINE]

注意：timeline value 必须单调递增，且不能在多个 submit 中复用同一 value。[SPEC]

### Aliasing 切换点的强制 barrier

当 alias heap 的某 offset 从资源 A 切换到资源 B 时：[ENGINE][SPEC]

```text
A.last_use_pass 出口：
  插入 VkMemoryBarrier2（make A available）
B.first_use_pass 入口：
  插入 VkMemoryBarrier2（make B visible）+ layout transition to B 的初始 layout
```

这是 aliasing 安全的硬性要求。某些 graph 实现还要求 A 在 last_use 时 transition 到 `VK_IMAGE_LAYOUT_GENERAL` 或 `UNDEFINED`，作为"显式失效"标记。[ENGINE]

### 自动 layout 的常见映射

```text
声明用途                          目标 layout
-------------------------------------------------
color attachment (write)          COLOR_ATTACHMENT_OPTIMAL
depth/stencil attachment          DEPTH_STENCIL_ATTACHMENT_OPTIMAL
depth-only (sampled)              DEPTH_STENCIL_READ_ONLY_OPTIMAL
shader read (texture)             SHADER_READ_ONLY_OPTIMAL
shader read (storage image)       GENERAL（或 READ_ONLY_STORAGE_OPTIMAL 若支持）
transfer src                      TRANSFER_SRC_OPTIMAL
transfer dst                      TRANSFER_DST_OPTIMAL
present                           PRESENT_SRC_KHR
initial (未初始化)                 UNDEFINED
```

[SPEC]

### 风险点

1. graph 编译器漏掉某个 read 的 layout transition，descriptor 中 imageLayout 与实际 layout 不匹配，触发 `VUID-VkDescriptorImageInfo-imageLayout-...` validation error。[SPEC]
2. 跨 queue 边只插入了 release barrier 没插入 acquire barrier（或反之），导致 GPU 间数据可见性缺失。[SPEC]
3. Barrier batching 把不同 queue 的 barrier 合并到一个调用，违反 "barrier 必须在 srcQueue 和 dstQueue 都执行" 的规则。[SPEC]
4. Aliasing 切换点未插入 make-available barrier，新资源读到上一帧残留数据，表现为闪烁或花屏。[ENGINE][TOOL]

---

## 7. 工程实践建议

### Validation Layer 集成

```text
1. Setup 阶段对 DAG 做 cycle detection，环必须报错而非死锁
2. Compile 阶段输出 barrier 计划 + alias 计划，可在 debug 模式下打印
3. Execute 阶段开启 Vulkan Validation Layer，捕获 layout / barrier / alias 错误
4. 每帧 execute 结束后做断言：所有 transient 资源都已 release
```

[ENGINE][TOOL]

### 调试可视化

```text
- GraphViz DOT 导出：节点=pass，边=资源依赖
- RenderDoc / AGI capture：观察实际 barrier、layout、memory binding
- 自定义 RDG dump：导出 [pass, resource, state] 三元组到 JSON
- aliasing 可视化：把 alias heap 切分为时间轴上的块，肉眼检查重叠
```

[TOOL][ENGINE]

### 常见错误模式

```text
1. 在 pass execute 回调中直接读写外部 VkImage，未通过 graph 声明
   => barrier 缺失，layout 不一致
   修复：所有资源访问必须走 graph 声明路径

2. 把 swapchain image 当 transient，导致 graph 在 last_use 后释放
   => 实际上 swapchain image 由 swapchain 管理，应 imported
   修复：imported persistent 标记，graph 不拥有生命周期

3. 多帧之间共享 transient resource（如 motion vectors）
   => 该资源跨帧 live，不能参与本帧 aliasing
   修复：升级为 imported persistent，由外部 owner 在帧间保留

4. Compute pass 与 graphics pass 共用同一 transient buffer，未声明 queue transfer
   => 跨 queue 数据可见性缺失
   修复：声明 cross-queue edge，graph 自动插入 release/acquire barrier

5. Aliasing 资源在 last_use pass 内部仍被 GPU 引用，但 alias 已切换
   => 同一 command buffer 内出现 RAW hazard
   修复：live_interval 计算必须包含 last_use pass 的全部执行期
```

[ENGINE][HEUR]

### 性能优化优先级

```text
1. Dead pass elimination（剔除无 consumer 的 pass）— 收益最大，零风险
2. Barrier batching — 减少 vkCmdPipelineBarrier2 调用次数
3. Aliasing — 降低 transient 峰值显存，移动端尤其关键
4. Pass merge（compatible pass 合并 render pass）— 减少 attachment load/store
5. Layout 复用 — 在不破坏正确性前提下减少 layout transition 次数
```

[ENGINE][TOOL]

### 与 frames-in-flight 的关系

```text
- 每个 frame 拥有独立的 Render Graph 实例（或 reset 后复用）
- transient 资源不跨帧共享
- imported persistent 资源由外部 ring buffer / pool 管理
- timeline semaphore 用于追踪每帧的 GPU 完成点
  CPU 在 timeline value 达到后才能复用对应的 ring buffer slot
```

[ENGINE][SPEC]

### 移动端额外注意

```text
- tile-based GPU 上，aliasing 可能破坏 IMR（immediate mode render）才能享受的 tile 复用
- Vulkan 1.4 + dynamic rendering local read 可减少 subpass dependency 的手动声明
- 部分 Android 驱动对 cross-queue ownership transfer 有额外同步要求，需 query 后确认
- 设备显存 budget 紧张时，aliasing 是降低峰值的关键手段，但必须配合内存压力测试
```

[VENDOR][ANDROID][TOOL]

### 工程落地清单

```text
[ ] DAG cycle detection 在 setup 阶段强制
[ ] 所有 transient 资源的 live_interval 在 compile 阶段计算并打印
[ ] Aliasing 计划可被禁用（debug 模式），便于隔离 aliasing 引起的 bug
[ ] VkImageView 缓存随 graph destroy 一起清理
[ ] Validation Layer 在每帧 execute 后无 error
[ ] barrier 计划可在 debug 模式导出
[ ] swapchain 重建路径覆盖 imported persistent 资源的 view 重建
[ ] timeline semaphore value 在 graph execute 中单调递增
```

[ENGINE][HEUR]

---

## 8. 相关文件

- `resource_lifecycle.md` — 单个 `VkImage` / `VkBuffer` 的底层生命周期，是本文件的基础。
- `synchronization_lifecycle.md` — `VkImageMemoryBarrier2` / `VkBufferMemoryBarrier2` / `VkMemoryBarrier2` 细节。
- `frame_lifecycle.md` — frames-in-flight 与 graph 实例的对应关系。
- `modern_patterns.md` — Timeline Semaphore / Dynamic Rendering / Bindless 与 graph 的配合。
- `render_target_model.md` — Render Target 与 dynamic rendering 的 attachment 模型。
- `../03_api_manual/08_synchronization/semaphore.md` — Timeline semaphore API 细节。
- `../03_api_manual/08_synchronization/image_memory_barrier.md` — `VkImageMemoryBarrier2` 字段与 VUID。
- `../03_api_manual/08_synchronization/buffer_memory_barrier.md` — `VkBufferMemoryBarrier2` 字段与 VUID。

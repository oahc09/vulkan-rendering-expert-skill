# API Card: VK_KHR_synchronization2

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkDependencyInfo` / `VkMemoryBarrier2` / `VkBufferMemoryBarrier2` / `VkImageMemoryBarrier2` |
| 常用 API | `vkCmdPipelineBarrier2` / `vkQueueSubmit2` / `vkCmdWriteBufferMarker2AMD`（可选） |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | `VK_KHR_synchronization2` 扩展 / Vulkan 1.3 core |

---

## 1. 一句话定位

`VK_KHR_synchronization2`（Vulkan 1.3 core）是 Vulkan 同步模型的扩展版本，通过 `VkDependencyInfo` 统一描述 barrier、semaphore 信号/等待的 stage/access 语义，并提供更细粒度的 pipeline stage 与 access flag，用于替代旧版 `vkCmdPipelineBarrier` 和 `vkQueueSubmit` 中的同步表达。[SPEC]

---

## 2. 所属对象链路

```text
旧版同步命令（vkCmdPipelineBarrier / vkQueueSubmit）
→ 启用 synchronization2 feature
→ VkDependencyInfo（ VkMemoryBarrier2 / VkBufferMemoryBarrier2 / VkImageMemoryBarrier2 ）
→ vkCmdPipelineBarrier2 / vkQueueSubmit2
→ 下游 GPU 工作
```

### 上游依赖

- 设备支持 Vulkan 1.3 或启用 `VK_KHR_synchronization2` 扩展。[SPEC]
- 对于 `vkQueueSubmit2`，需要 `VkPhysicalDeviceSynchronization2Features.synchronization2 = VK_TRUE`。[SPEC]
- 已创建的 command buffer、semaphore、buffer、image 等对象。[SPEC]

### 下游影响

- 以更统一的方式表达 execution / memory dependency。[SPEC]
- `vkQueueSubmit2` 可同时携带 signal/wait semaphore 与 command buffer submission，并支持 timeline semaphore 的 value 字段直接嵌入 `VkSemaphoreSubmitInfo`。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDependencyInfo`
- `VkMemoryBarrier2`
- `VkBufferMemoryBarrier2`
- `VkImageMemoryBarrier2`
- `VkSubmitInfo2`
- `VkSemaphoreSubmitInfo`
- `VkCommandBufferSubmitInfo`
- `VkPipelineStageFlags2` / `VkAccessFlags2`

### 常用 API

| API | 作用 |
|---|---|
| `vkCmdPipelineBarrier2` | 使用 `VkDependencyInfo` 插入 barrier；可混合 memory / buffer / image barrier。[SPEC] |
| `vkQueueSubmit2` | 使用 `VkSubmitInfo2` 提交 command buffer，并携带 signal/wait semaphore（含 timeline value）。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_synchronization2`（Vulkan 1.3 core）。[SPEC]
- 与 timeline semaphore 天然兼容，`VkSemaphoreSubmitInfo` 直接内嵌 value 字段。[SPEC]
- Android 可用性取决于设备 Vulkan 版本与驱动支持；需运行时查询。[ANDROID]

---

## 4. 标准使用流程

### Barrier

```text
构造 VkMemoryBarrier2 / VkBufferMemoryBarrier2 / VkImageMemoryBarrier2（设置 srcStageMask / srcAccessMask / dstStageMask / dstAccessMask）
→ 填充 VkDependencyInfo 的对应数组
→ 调用 vkCmdPipelineBarrier2(commandBuffer, &dependencyInfo)
```

### Submit

```text
构造 VkCommandBufferSubmitInfo
→ 构造 VkSemaphoreSubmitInfo（signal / wait，timeline value 直接填入 value 字段）
→ 填充 VkSubmitInfo2
→ 调用 vkQueueSubmit2(queue, 1, &submitInfo2, fence)
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `srcStageMask` / `dstStageMask`（`VkPipelineStageFlags2`） | 扩展 stage 集合，包含 `VK_PIPELINE_STAGE_2_COPY_BIT`、`VK_PIPELINE_STAGE_2_CLEAR_BIT` 等更具体的阶段。[SPEC] | 仍使用旧版 `VkPipelineStageFlags` 的值直接赋给 `VkPipelineStageFlags2`，类型不匹配。[TOOL] |
| `srcAccessMask` / `dstAccessMask`（`VkAccessFlags2`） | 扩展 access 集合，如 `VK_ACCESS_2_SHADER_READ_BIT`、`VK_ACCESS_2_MEMORY_READ_BIT`。[SPEC] | 遗漏 `VK_ACCESS_2_MEMORY_WRITE_BIT` 等宽 access，导致 visibility 不足。[TOOL] |
| `VkDependencyInfo.dependencyFlags` | 同旧版 `dependencyFlags`，支持 `VK_DEPENDENCY_BY_REGION_BIT` 等。[SPEC] | 在全局 barrier 中误用 `BY_REGION_BIT`。[TOOL] |
| `VkImageMemoryBarrier2.oldLayout` / `newLayout` | 支持新增 layout 如 `VK_IMAGE_LAYOUT_ATTACHMENT_OPTIMAL`、`VK_IMAGE_LAYOUT_READ_ONLY_OPTIMAL`。[SPEC] | 在旧版设备上错误使用 1.3 专用 layout。[TOOL] |
| `VkSemaphoreSubmitInfo.value` | Timeline semaphore 的 signal/wait value 直接嵌入，无需单独的 `VkTimelineSemaphoreSubmitInfo`。[SPEC] | 在 `VkSubmitInfo2` 中忘记设置 stage / value 字段。[TOOL] |
| `VkSubmitInfo2.commandBufferInfoCount` / `pCommandBufferInfos` | 用 `VkCommandBufferSubmitInfo` 包装 command buffer，可携带 device mask（多设备场景）。[SPEC] | 仍按旧版直接传 `VkCommandBuffer` 数组。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否启用 `synchronization2` feature？
- [ ] 是否使用 `VkPipelineStageFlags2` / `VkAccessFlags2` 而非旧版 flag？
- [ ] 是否确认目标设备支持 Vulkan 1.3 或扩展？

### 使用阶段

- [ ] `VkDependencyInfo` 中是否至少包含一种 barrier？
- [ ] `vkQueueSubmit2` 的 `VkSemaphoreSubmitInfo` 是否填对了 signal/wait 类型和 timeline value？
- [ ] 新旧 API 是否混用导致结构体版本不匹配？

### 销毁阶段

- 无独立销毁阶段；依赖底层对象（command buffer / semaphore / fence）的生命周期管理。[SPEC]

---

## 7. 高频错误

1. 启用了扩展但 `VkPhysicalDeviceSynchronization2Features.synchronization2` 未设为 `VK_TRUE`。[TOOL]
2. 用旧版 `VkPipelineStageFlags` 直接强制转换给 `VkPipelineStageFlags2`，导致 bit 含义错位。[TOOL]
3. `VkSubmitInfo2` 中 `pWaitSemaphoreInfos` / `pSignalSemaphoreInfos` 的 stage mask 使用 `VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT` 作为默认值，造成过度阻塞。[HEUR]
4. 在 `VkImageMemoryBarrier2` 中使用 Vulkan 1.3 新增的 layout，但设备仅支持 1.2 且未启用 synchronization2。[TOOL]
5. 忘记 `VkDependencyInfo` 中 `pNext` 或数组指针初始化，导致 validation 报错。[TOOL]
6. 混用 `vkQueueSubmit` 与 `vkQueueSubmit2` 的 semaphore，导致 timeline value 不同步。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkCmdPipelineBarrier2-synchronization2-03848`：必须启用 synchronization2。
- `VUID-VkMemoryBarrier2-srcStageMask-03851` / `dstStageMask-03852`：stage / access 组合合法性。
- `VUID-VkSubmitInfo2-semaphore-03882`：wait semaphore 必须处于合法状态。
- `VUID-vkQueueSubmit2-fence-03863`：fence 不能处于 pending 状态。

### RenderDoc / AGI

- RenderDoc 1.18+ 支持 capture synchronization2 命令；可查看 `VkDependencyInfo` 展开后的 barrier 列表。[TOOL]
- AGI 可分析 `vkQueueSubmit2` 的 semaphore 依赖链。[TOOL]

### 日志 / 代码检查

- 检查 feature 启用代码（`VkPhysicalDeviceSynchronization2Features`）。
- 检查 `VkDependencyInfo` 各数组长度与指针。
- 检查 `VkSubmitInfo2` 中 `commandBufferInfoCount` 与 `pCommandBufferInfos`。

---

## 9. 生命周期风险

### 创建时机

- 在启用 feature 后，于 command buffer 录制或 submit 时构造。[SPEC]

### 使用时机

- 需要比旧版更精确地表达 stage/access 时使用；新代码可优先采用。[ENGINE]

### 销毁时机

- 结构体为栈上临时对象；无独立销毁阶段。[SPEC]

### in-flight 风险

- `vkQueueSubmit2` 引用的 fence / semaphore / command buffer 的 in-flight 规则与 `vkQueueSubmit` 相同。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- `vkQueueSubmit2` 可携带 fence，规则与 `vkQueueSubmit` 一致；CPU 等待使用 fence 或 timeline semaphore 的 `vkWaitSemaphores`。[SPEC]

### GPU-GPU 同步

- `vkCmdPipelineBarrier2` 提供同 queue 内 execution + memory dependency。[SPEC]
- `vkQueueSubmit2` 通过 `VkSemaphoreSubmitInfo` 建立跨 submit / 跨 queue 依赖。[SPEC]

### 资源访问同步

- `VkImageMemoryBarrier2` / `VkBufferMemoryBarrier2` 与旧版语义相同，但 stage/access flag 集合更大；使用时应确认 consumer 的 pipeline stage 在 synchronization2 中有对应 bit。[SPEC]

---

## 11. Android 注意点

- Android 设备 Vulkan 1.3 覆盖率逐步提升，但仍有大量 1.1/1.2 设备；使用 synchronization2 前必须运行时查询 `VkPhysicalDeviceSynchronization2Features`。[ANDROID]
- 部分 Android 驱动对 synchronization2 的实现可能有额外限制；若 validation 通过但出现渲染异常，应回退到旧版同步 API 做对照实验。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- `vkCmdPipelineBarrier2` 的 `VkDependencyInfo` 设计更统一，可减少为组合 barrier 而产生的多次 API 调用。[ENGINE]
- `vkQueueSubmit2` 将 command buffer、semaphore、timeline value 统一提交，降低 submit 结构体拼装复杂度。[ENGINE]

### GPU 侧

- 更细粒度的 stage（如 `COPY_BIT`、`CLEAR_BIT`）有助于减少不必要的 pipeline 阻塞。[HEUR]
- 但 `VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT` 仍会导致 full pipeline drain，应避免滥用。[HEUR]

### 移动端

- 移动端 Vulkan 1.3 支持率仍在增长，使用 synchronization2 前需 fallback 到旧版路径以保证兼容性。[ANDROID][ENGINE]
- 新增 layout（`ATTACHMENT_OPTIMAL`、`READ_ONLY_OPTIMAL`）可减少 layout transition 种类，但需要驱动优化支持才能体现收益。[HEUR]

---

## 13. 专家经验

**经验**：
在新项目中优先使用 synchronization2 API 表达同步意图：`vkCmdPipelineBarrier2` + `VkDependencyInfo` 可以一次性混合 global / buffer / image barrier，结构更清晰；`vkQueueSubmit2` 把 timeline semaphore 的 value 直接内嵌到 `VkSemaphoreSubmitInfo`，消除了旧版 `VkTimelineSemaphoreSubmitInfo` 与 `VkSubmitInfo` 的 pNext 链拼装。但应保持旧版同步路径作为 fallback，尤其在需要覆盖 Android 中低端设备时。

**适用条件**：
项目最低目标为 Vulkan 1.3 或已确认设备支持 `VK_KHR_synchronization2`；需要精确 stage/access 控制或频繁使用 timeline semaphore。

**不适用情况**：
必须兼容 Vulkan 1.2 以下且未启用扩展的设备；团队对 synchronization2 语义不熟悉且缺乏 validation 环境。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `pipeline_barrier.md`
- `image_memory_barrier.md`
- `semaphore.md`
- `fence.md`
- `event.md`
- `../03_command_buffer/queue_submit.md`

---

## 14.5 Vulkan 1.4 变更

Vulkan 1.4 对 Synchronization2 的主要变更：

### promote 为 mandatory feature

Vulkan 1.4 将 `VK_KHR_synchronization2` 的 API promote 进 core，并提升为 mandatory feature（保证被支持）。[SPEC]

- 1.4 设备保证支持 synchronization2，无需运行时查询 feature 即可确认能力存在；但 **mandatory feature 仍需在 `VkDeviceCreateInfo.pNext` 中通过 `VkPhysicalDeviceVulkan13Features.synchronization2 = VK_TRUE`（或独立结构 `VkPhysicalDeviceSynchronization2Features.synchronization2`）显式启用** 后才能调用 sync2 API（`vkCmdPipelineBarrier2` / `vkQueueSubmit2` / `VkImageMemoryBarrier2` 等）。注意 `synchronization2` 是 Vulkan 1.3 promote，因此字段位于 `VkPhysicalDeviceVulkan13Features`，**不在 `VkPhysicalDeviceVulkan14Features`**。[SPEC]
- 启用后可省略 `vkCmdPipelineBarrier` 的 fallback 路径。[ENGINE]
- 判断条件：`VkPhysicalDeviceProperties.apiVersion >= VK_VERSION_1_4` 且 device 创建时已启用 `synchronization2` feature。[SPEC]

### 与 Timeline Semaphore 的深度配合

1.4 时代 timeline semaphore + synchronization2 是默认同步模型：

- `vkQueueSubmit2` + `VkSemaphoreSubmitInfo.value` 直接嵌入 timeline value。[SPEC]
- 一个 timeline semaphore 可表达多个帧的完成点，替代 per-frame binary semaphore 数组。[ENGINE]
- CPU 侧通过 `vkGetSemaphoreCounterValue` 查询帧完成状态，无需 `vkWaitForFences` 阻塞。[ENGINE]

### 完整帧同步模型（1.4 推荐）

```text
Frame N:
  vkAcquireNextImageKHR (binary semaphore: acquireSem)
  vkQueueSubmit2:
    wait: acquireSem (binary), timelineSem value >= N-2 (等待最老帧完成)
    signal: timelineSem value = N
  vkQueuePresentKHR (binary semaphore: renderSem)
  CPU: vkGetSemaphoreCounterValue(timelineSem) >= N-2 时可复用 Frame N-2 资源
```

### maintenance6 对同步的影响

`VK_KHR_maintenance6`（1.4 核心）引入简化同步表达。[SPEC]

---

## 15. 需要回查官方文档的情况

1. `VkPipelineStageFlags2` 与旧版 `VkPipelineStageFlags` 的具体映射关系及新增 stage 的精确语义。
2. `VkAccessFlags2` 中 `MEMORY_READ` / `MEMORY_WRITE` 与具体 access flag 的等价关系。
3. `VkDependencyInfo` 同时包含多种 barrier 时的交互规则。
4. `vkQueueSubmit2` 与 `vkQueueSubmit` 在 fence 行为上的差异细节。
5. Vulkan 1.3 新增 image layout（`ATTACHMENT_OPTIMAL`、`READ_ONLY_OPTIMAL`）的兼容性要求。
6. 目标 Android 设备对 synchronization2 的驱动支持矩阵。

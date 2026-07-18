# API Card: Timeline Semaphore

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 同步链 |
| Vulkan 对象 | `VkSemaphore`（Timeline 类型） |
| 常用 API | `vkCreateSemaphore` / `vkGetSemaphoreCounterValue` / `vkWaitSemaphores` / `vkSignalSemaphore` / `vkQueueSubmit2` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | `VK_KHR_timeline_semaphore` / Vulkan 1.2 core / Vulkan 1.4 promote 为 mandatory feature（仍需通过 `VkPhysicalDeviceVulkan12Features.timelineSemaphore` 显式启用） |

---

## 1. 一句话定位

Timeline Semaphore 是带 64-bit 单调递增 counter 的 `VkSemaphore` 子类型，可被 CPU 和 GPU 双侧 signal/wait，用一个 semaphore 对象表达任意多个完成点，是替代 per-frame binary semaphore 数组与跨 queue/跨帧 fence 的主流同步原语。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice（启用 timelineSemaphore feature）
  → VkSemaphore（VkSemaphoreTypeCreateInfo.semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE）
  → GPU 侧：vkQueueSubmit2 通过 VkSemaphoreSubmitInfo.value 递增 counter
  → CPU 侧：vkGetSemaphoreCounterValue 查询 / vkWaitSemaphores 阻塞等待 / vkSignalSemaphore 主动推进
  → 下游 submit 或 CPU 逻辑通过更高 value 建立依赖
  → vkDestroySemaphore（counter 不再被任何 wait 引用）
```

### 上游依赖

- 已启用 `timelineSemaphore` feature（`VkPhysicalDeviceTimelineSemaphoreFeatures` 或 `VkPhysicalDeviceVulkan12Features.timelineSemaphore`）。[SPEC]
- Vulkan 1.4 起 timeline semaphore promote 为 mandatory feature（保证被支持），但 **仍需在 `VkDeviceCreateInfo.pNext` 中通过 `VkPhysicalDeviceVulkan12Features.timelineSemaphore = VK_TRUE`（或独立结构 `VkPhysicalDeviceTimelineSemaphoreFeatures.timelineSemaphore`）显式启用** 后才能使用相关 API。`timelineSemaphore` 是 Vulkan 1.2 promote，字段位于 `VkPhysicalDeviceVulkan12Features`，**不在 `VkPhysicalDeviceVulkan14Features`**。[SPEC]
- Android 平台需运行时确认 `vkGetPhysicalDeviceFeatures2` 返回 `timelineSemaphore == VK_TRUE`；旧 Mali/Adreno 驱动可能仅 Vulkan 1.1 而不支持 timeline semaphore。[ANDROID]

### 下游影响

- 替代 binary semaphore 数组管理 N 帧 in-flight 资源释放时机。[ENGINE]
- 替代 fence 做 CPU-GPU 同步，避免每帧 fence 分配。[ENGINE]
- 与 `vkQueueSubmit2` + `VkSemaphoreSubmitInfo` 配合形成基于 value 的精确跨 queue/跨帧依赖图。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSemaphore`（Timeline 类型）
- `VkSemaphoreCreateInfo`（pNext 链入 type info）
- `VkSemaphoreTypeCreateInfo`（创建 timeline semaphore 的核心结构体）
- `VkSemaphoreSubmitInfo`（`vkQueueSubmit2` 中嵌入 timeline value）
- `VkSemaphoreSignalInfo`（`vkSignalSemaphore` 的参数）
- `VkSemaphoreWaitInfo`（`vkWaitSemaphores` 的参数）

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateSemaphore` | 通过 `VkSemaphoreTypeCreateInfo` pNext 链创建 timeline semaphore。[SPEC] |
| `vkGetSemaphoreCounterValue` | 查询 timeline semaphore 当前 counter value（非阻塞）。[SPEC] |
| `vkWaitSemaphores` | CPU 侧阻塞等待一个或多个 timeline semaphore 达到指定 value。[SPEC] |
| `vkSignalSemaphore` | CPU 侧主动 signal timeline semaphore 到指定 value（必须大于当前 counter）。[SPEC] |
| `vkQueueSubmit2` | 通过 `VkSemaphoreSubmitInfo.value` 在 GPU 侧 signal/wait timeline value。[SPEC] |
| `vkDestroySemaphore` | 销毁 semaphore；必须确保 GPU 已无任何 wait 引用该 value 区间。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_timeline_semaphore`（Vulkan 1.1 + extension）。[SPEC]
- Vulkan 1.2 起 timeline semaphore 进入 core，仍需通过 `VkPhysicalDeviceVulkan12Features::timelineSemaphore` 查询并启用。[SPEC]
- Vulkan 1.4 起 timeline semaphore promote 为 mandatory feature（保证被支持），但仍需通过 `VkPhysicalDeviceVulkan12Features.timelineSemaphore`（1.2 promote，**不在 Vulkan14Features**）显式启用。[SPEC]
- 与 `VK_KHR_synchronization2` 联合使用以获得 `VkSemaphoreSubmitInfo` 这一更直观的 value 嵌入路径。[SPEC]

---

## 4. 标准使用流程

### 创建 Timeline Semaphore

```text
查询 / 启用 timelineSemaphore feature
→ VkSemaphoreTypeCreateInfo { semaphoreType = VK_SEMAPHORE_TYPE_TIMELINE, initialValue = 0 }
→ VkSemaphoreCreateInfo.pNext = &typeCreateInfo
→ vkCreateSemaphore(...) 得到 VkSemaphore
```

### GPU 侧跨帧 in-flight 依赖

```text
frame = N
  vkQueueSubmit2(
    pSignalSemaphoreInfos = [{ semaphore, value = N + 1 }],
    pWaitSemaphoreInfos    = [{ semaphore, value = N - FRAMES_IN_FLIGHT + 1,
                                 stageMask = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT }])
  → CPU 轮询 vkGetSemaphoreCounterValue >= N + 1 - FRAMES_IN_FLIGHT
    或 vkWaitSemaphores(value = N + 1 - FRAMES_IN_FLIGHT)
  → 释放对应帧的 per-frame 资源
```

### CPU 侧主动推进

```text
vkGetSemaphoreCounterValue(semaphore, &current)
→ 业务推进逻辑判断需要通知 GPU
→ vkSignalSemaphore(VkSemaphoreSignalInfo{ semaphore, value = next })
→ 对端 GPU/CPU 通过 vkWaitSemaphores(value = next) 建立依赖
```

### 与 vkQueueSubmit2 配合

```text
VkSemaphoreSubmitInfo signalInfo = { .semaphore = tlSem, .value = frameId, .stageMask = ALL_GRAPHICS_BIT };
VkSemaphoreSubmitInfo waitInfo   = { .semaphore = tlSem, .value = frameId - FRAMES_IN_FLIGHT, .stageMask = ALL_COMMANDS_BIT };
VkSubmitInfo2 submit = { ..., pSignalSemaphoreInfos = &signalInfo, pWaitSemaphoreInfos = &waitInfo };
vkQueueSubmit2(queue, 1, &submit, fence_optional);
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkSemaphoreTypeCreateInfo.semaphoreType` | 必须为 `VK_SEMAPHORE_TYPE_TIMELINE`；创建后不可切换。[SPEC] | 创建 binary semaphore 后却按 timeline 用 `vkGetSemaphoreCounterValue`。[TOOL] |
| `VkSemaphoreTypeCreateInfo.initialValue` | Counter 起始值；通常设 0；后续 signal/wait 必须严格大于该值。[SPEC] | initialValue 设非 0 但 wait 逻辑默认从 0 开始递增，导致首帧错位。[ENGINE] |
| `VkSemaphoreSubmitInfo.value` | submit2 中直接嵌入 timeline value；signal value 必须严格单调递增。[SPEC] | 同一 semaphore 的两次 signal value 相同或回退，触发 VUID。[TOOL] |
| `VkSemaphoreSubmitInfo.stageMask` | signal 阶段 mask；wait 阶段 mask 控制阻塞 pipeline stage。[SPEC] | wait stage 设为 `TOP_OF_PIPE_BIT` 使同步失效或语义错误；应按真实消费阶段设置。[HEUR] |
| `VkSemaphoreSignalInfo.value` | CPU signal 目标值；必须严格大于当前 counter。[SPEC] | signal 一个 ≤ 当前 counter 的 value → `VK_ERROR_INVALID_VALUE` 或 VUID 触发。[TOOL] |
| `VkSemaphoreWaitInfo.semaphores` / `pValues` | 多 semaphore 等待时的 value 数组与 semaphore 数组必须按索引对齐。[SPEC] | 数组顺序错位导致等待错误的目标 value。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `timelineSemaphore` feature 是否在 device 创建时启用？[SPEC]
- [ ] `VkSemaphoreTypeCreateInfo` 是否通过 pNext 链入 `VkSemaphoreCreateInfo`？[SPEC]
- [ ] `initialValue` 是否与后续 signal/wait 计数逻辑一致（通常 0）？[ENGINE]
- [ ] 是否避免使用 timeline semaphore 作为 swapchain acquire / present 的同步原语？[SPEC]

### 使用阶段

- [ ] 同一 timeline semaphore 的 signal value 是否严格单调递增？[SPEC]
- [ ] wait value 是否 ≤ 已 signal（或即将 signal）的 value？[SPEC]
- [ ] `VkSemaphoreSubmitInfo.value` 数组与 `VkSubmitInfo2` 中 semaphore 数组是否一一对应？[SPEC]
- [ ] CPU 侧 `vkSignalSemaphore` 的 value 是否大于当前 counter？[SPEC]
- [ ] Frames-in-flight 的 wait value 是否正确反映 N 帧延迟？[ENGINE]
- [ ] 跨 queue 是否使用同一 timeline semaphore + 不同 value 区间建立依赖？[ENGINE]

### 销毁阶段

- [ ] 是否确认 GPU 已无任何 wait 引用当前及未来 value？[SPEC]
- [ ] 是否在 device destroy 之前完成 semaphore destroy？[SPEC]
- [ ] 是否避免在 `vkDeviceWaitIdle` 之前销毁仍被 pending submit 引用的 timeline semaphore？[ENGINE]

---

## 7. 高频错误

1. Timeline semaphore 的 signal/wait value 非单调递增（回退或重复）。[SPEC]
2. 用 timeline semaphore 直接作为 `vkAcquireNextImageKHR` 的 acquire semaphore 或 `vkQueuePresentKHR` 的 present semaphore（WSI 通常要求 binary semaphore）。[SPEC]
3. `vkSignalSemaphore` 一个 ≤ 当前 counter 的 value，触发 `VK_ERROR_INVALID_VALUE` 或 VUID。[TOOL]
4. 把 binary semaphore 误用 `vkGetSemaphoreCounterValue` / `vkWaitSemaphores` / `vkSignalSemaphore` 操作。[SPEC]
5. `VkSemaphoreSubmitInfo` 与 `VkSubmitInfo2` 的 semaphore/value/stageMask 数组长度不匹配或顺序错位。[TOOL]
6. Frames-in-flight 计算偏差：wait value 写错，导致首帧或末帧同步错位、过早释放资源引发 hazard。[ENGINE]
7. 未启用 `timelineSemaphore` feature 就创建 `VK_SEMAPHORE_TYPE_TIMELINE`。[TOOL]
8. Android 上未运行时确认 timeline semaphore 支持就使用，旧驱动直接 validation/device-lost。[ANDROID]
9. CPU `vkWaitSemaphores` 不带 timeout 或 `timeout = UINT64_MAX`，导致渲染线程永久阻塞。[ENGINE]
10. 跨 queue 依赖仍用 binary semaphore 链而非 timeline counter，扩展性差且难调试。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkSemaphoreTypeCreateInfo-semaphoreType-03279`：`semaphoreType` 必须与启用的 feature 一致。[SPEC]
- `VUID-VkSemaphoreSignalInfo-value-03255`：signal value 必须大于当前 counter。[SPEC]
- `VUID-vkQueueSubmit2-pSignalSemaphoreInfos-03212`：timeline signal value 必须严格大于之前 signal 的值。[SPEC]
- `VUID-vkQueueSubmit2-pWaitSemaphoreInfos-03243`：wait value 必须可被满足（≤ 已 signal 或 pending signal 的 value）。[SPEC]
- `VUID-vkSignalSemaphore-value-03255`：CPU signal value 必须严格大于当前 counter。[SPEC]

### RenderDoc / AGI

- AGI 可直接展示 timeline semaphore 的 counter 演进曲线和跨 queue 依赖边，是诊断卡顿、死锁的首选。[TOOL]
- RenderDoc 在 submit inspector 中显示每次 `vkQueueSubmit2` 的 signal/wait value；可用断点定位 value 不单调问题。[TOOL]
- AGI Frame State 中可查看当前 counter 与 pending wait 列表，验证 frames-in-flight 模型。[TOOL]

### 日志 / 代码检查

- 打印每次 `vkQueueSubmit2` 与 `vkSignalSemaphore` 的 value，断言严格单调递增。[ENGINE]
- 检查 `VkSemaphoreSubmitInfo` 数组索引与 semaphore/value/stageMask 是否对齐。[ENGINE]
- 在 Android logcat 抓取 `vkQueueSubmit2` 失败码，判断是否驱动对 timeline + swapchain 组合支持不足。[ANDROID]
- 对比 `vkGetSemaphoreCounterValue` 期望值与实际值，定位 CPU/GPU 推进失配。[ENGINE]

---

## 9. 生命周期风险

### 创建时机

- 设备初始化阶段创建少量（通常 1~N 个，按用途）timeline semaphore 作为长生命周期 counter。[ENGINE]
- 不要 per-frame 创建 timeline semaphore；其设计目标正是复用同一对象表达多个完成点。[ENGINE]

### 使用时机

- `vkQueueSubmit2` 中通过 `VkSemaphoreSubmitInfo.value` 递增 counter。[SPEC]
- CPU 侧 `vkSignalSemaphore` 用于在主机侧推进 counter（例如外部事件通知）。[SPEC]
- `vkWaitSemaphores` 用于主机侧阻塞等待，替代 fence `vkWaitForFences`。[SPEC]
- `vkGetSemaphoreCounterValue` 用于非阻塞轮询，适合于 frame pacing / 资源回收逻辑。[SPEC]

### 销毁时机

- Device 销毁前；通常在 `vkDeviceWaitIdle` 后销毁。[SPEC]
- Swapchain recreate 不需要销毁 timeline semaphore；counter 语义可跨 swapchain 复用。[ENGINE]

### in-flight 风险

- Wait value 引用的 counter 区间未达到前，不能销毁 semaphore。[SPEC]
- CPU `vkWaitSemaphores` 持有引用时，GPU 侧销毁语义不会被强制同步；必须显式 idle 后销毁。[SPEC]
- Frames-in-flight 模型下，counter `value - FRAMES_IN_FLIGHT` 之前的资源才能安全释放。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- Timeline semaphore 是唯一原生支持 CPU `wait` / `signal` / `query` 的 semaphore 类型；binary semaphore 无 CPU 操作 API。[SPEC]
- `vkWaitSemaphores` 默认阻塞 CPU 线程；长 timeout 可能造成渲染线程卡死，应配合 frame pacing timeout。[ENGINE]
- CPU `vkSignalSemaphore` 不会等待 GPU；如需 GPU 感知 CPU signal，必须确保 GPU 侧 wait 已记录在 submit 中。[SPEC]

### GPU-GPU 同步

- 跨 queue 依赖用 timeline semaphore + 不同 value 区间表达；同一 semaphore 的不同 value 段可并行被多个 queue 等待（wait 间不互斥）。[SPEC]
- 同一 queue 内的依赖通常用 pipeline barrier / event 更高效；timeline semaphore 主要用于跨 submit / 跨 queue / 跨帧。[ENGINE]

### 资源访问同步

- Semaphore 仅建立执行依赖，不保证 memory availability / visibility；跨 queue 资源访问仍需正确 stage mask / access mask（synchronization2 中 `VkSemaphoreSubmitInfo.stageMask`）。[SPEC]
- Frames-in-flight 模型下，资源 release 必须在 wait value 完成之后进行，否则 hazard。[ENGINE]

### Swapchain 交互风险

- WSI 规范要求 `vkAcquireNextImageKHR` / `vkQueuePresentKHR` 使用 binary semaphore；不要将 timeline semaphore 直接用于 WSI。[SPEC]
- 部分 Android 驱动对 timeline semaphore + swapchain 组合支持有限，可能在 present 后错误推进 counter；需在目标设备测试。[ANDROID]

---

## 11. Android 注意点

- 必须运行时查询 `VkPhysicalDeviceVulkan12Features::timelineSemaphore`；旧 Mali / Adreno 驱动可能仅 Vulkan 1.1 不支持 timeline semaphore。[ANDROID]
- 部分 Android 驱动对 timeline semaphore + swapchain acquire/present 组合支持有限，可能出现 present 后 counter 不推进或 device-lost；建议 swapchain 仍用 binary semaphore。[ANDROID]
- Android 上 `vkWaitSemaphores` 的 timeout 精度受调度器影响，长 timeout 可能被 ANR 检测器视为应用无响应；建议 ≤ 1s 配合重试。[ANDROID]
- AGI 在 Android 上可完整捕获 timeline counter 演进，是诊断 frames-in-flight / 跨 queue 死锁的首选工具。[TOOL]
- Android 低内存场景下 timeline semaphore 销毁需特别小心，部分驱动在 LMK 后 reset 路径存在 corner case，建议在 `onLowMemory` 回调中 `vkDeviceWaitIdle` 后再回收。[ANDROID][HEUR]

---

## 12. 性能注意点

### CPU 侧

- Timeline semaphore 减少 semaphore 对象数量与 per-frame 分配开销；一个对象表达 N 帧 in-flight 状态。[ENGINE]
- `vkGetSemaphoreCounterValue` 是廉价查询；可热循环使用替代 fence `vkGetFenceStatus`。[ENGINE]
- `vkWaitSemaphores` 长时间阻塞会拖慢主线程，应优先非阻塞轮询 + 短 timeout。[ENGINE]

### GPU 侧

- wait stage mask 选错会拖长 pipeline 气泡；按真实消费 stage 设置（如 `COLOR_ATTACHMENT_OUTPUT_BIT`）。[HEUR]
- 跨 graphics / compute queue 频繁 timeline 同步可能引入 cross-queue round-trip 延迟；尽量合并 submit 批次。[ENGINE]

### 移动端

- 移动 GPU 跨 queue 同步代价高；tile-based renderer 上 timeline semaphore 应避免在 render pass 内部引用。[ANDROID]
- Frames-in-flight 数量建议 ≤ 2，避免移动端内存压力与 tile memory 翻倍。[ANDROID]
- Swapchain acquire 的 stage mask 设为 `COLOR_ATTACHMENT_OUTPUT_BIT` 即可，避免 `ALL_COMMANDS_BIT` 造成不必要阻塞。[HEUR]

---

## 13. 专家经验

**经验**：
优先使用 timeline semaphore 替代 per-frame binary semaphore 数组与 per-frame fence 数组管理 N 帧 in-flight 资源生命周期。一个 timeline semaphore + 单调递增的 64-bit counter 即可表达「第 N 帧完成」「第 M 次 compute dispatch 完成」「资源 X 释放点」等多种事件，并统一 GPU-GPU 与 CPU-GPU 同步路径。配合 `vkQueueSubmit2` 的 `VkSemaphoreSubmitInfo.value` 嵌入，调试时通过 counter 单调性即可发现绝大多数同步错位问题，远比 binary semaphore 数组的对齐问题易维护。

但 swapchain acquire / present 仍必须使用 binary semaphore，因 WSI 规范强制要求；部分 Android 驱动对 timeline + swapchain 组合支持有限。

**适用条件**：
- 多 in-flight frame（N ≥ 2）渲染器。
- 跨 graphics / compute / transfer queue 的精确事件依赖。
- 长异步任务链需要 counter 追踪（如流式上传、texture decoding）。
- 目标设备支持 Vulkan 1.2+ 或启用 `VK_KHR_timeline_semaphore`。
- Vulkan 1.4 设备上可无条件使用。

**不适用情况**：
- 目标设备为旧 Android 驱动，仅支持 Vulkan 1.1 且未实现 `VK_KHR_timeline_semaphore`。
- Swapchain acquire / present 阶段必须使用 binary semaphore。
- 简单单 queue 渲染器，引入 timeline 反而增加心智负担。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `semaphore.md`
- `fence.md`
- `synchronization2.md`
- `pipeline_barrier.md`
- `event.md`
- `../03_command_buffer/queue_submit.md`

---

## 15. 需要回查官方文档的情况

1. `VkSemaphoreTypeCreateInfo` 在 `pNext` 链中与 `VkExternalSemaphoreTypeCreateInfo`、`VkExportMetalObjectCreateInfoEXT` 等扩展结构体的共存规则。[SPEC]
2. `vkQueueSubmit2` 中混合使用 binary semaphore（无 value）与 timeline semaphore（有 value）时 `VkSemaphoreSubmitInfo` 的字段语义。[SPEC]
3. `vkWaitSemaphores` 的 `VkSemaphoreWaitInfo.flags` 中 `VK_SEMAPHORE_WAIT_ANY_BIT` 在不同驱动上的支持差异（Android 旧驱动可能不支持 wait-any）。[SPEC][ANDROID]
4. Vulkan 1.4 将 timeline semaphore 提升为 mandatory feature 后，是否有 VUID 行为变化或更严格的 monotonic 校验；以及 `VkPhysicalDeviceVulkan12Features.timelineSemaphore`（1.2 promote）的查询路径在 1.4 设备上的最佳实践。[SPEC]
5. Timeline semaphore 与 `VK_KHR_external_semaphore` / `VK_KHR_external_semaphore_fd` 跨进程传递的 counter 语义和同步点。[SPEC]
6. Android 上 timeline semaphore 在 present 后 counter 是否被驱动隐式推进的实现差异。[ANDROID]
7. `vkSignalSemaphore` 在 GPU 已 pending signal 但未完成时的精确语义（是否允许 host 提前推进）。[SPEC]

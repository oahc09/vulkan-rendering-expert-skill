# API Card: VkCommandBuffer

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 命令链 |
| Vulkan 对象 | `VkCommandBuffer` |
| 常用 API | `vkAllocateCommandBuffers` / `vkFreeCommandBuffers` / `vkResetCommandBuffer` / `vkBeginCommandBuffer` / `vkEndCommandBuffer` / `vkCmd*` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkCommandBuffer` 是 CPU 录制、GPU 执行的命令队列，所有绘制、计算、资源状态转换、同步操作都必须先记录到 command buffer 中，再通过 `vkQueueSubmit` 提交给 GPU。[SPEC]

---

## 2. 所属对象链路

```text
VkDevice
→ VkCommandPool
→ VkCommandBuffer
→ Record Commands (vkCmd*)
→ vkEndCommandBuffer
→ vkQueueSubmit
→ GPU Execution
```

### 上游依赖

- `VkDevice` 必须有效。[SPEC]
- `VkCommandPool` 必须属于正确的 queue family。[SPEC]
- 所需的 `VkPipeline`、`VkDescriptorSet`、`VkBuffer`、`VkImage` 等对象必须已创建。[SPEC]

### 下游影响

- `vkQueueSubmit` 接收 command buffer 并触发 GPU 执行。
- Command buffer 引用的所有资源在 GPU 执行完成前必须保持有效。[SPEC]
- Command buffer 状态（recording / executable / pending / invalid）决定能否 reset / submit。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkCommandBuffer`
- `VkCommandBufferAllocateInfo`
- `VkCommandBufferBeginInfo`
- `VkCommandBufferInheritanceInfo`（secondary command buffer 使用）
- `VkCommandPool`

### 常用 API

| API | 作用 |
|---|---|
| `vkAllocateCommandBuffers` | 从 command pool 分配 command buffer。[SPEC] |
| `vkFreeCommandBuffers` | 释放非 pending 的 command buffer；recording、executable、invalid 等非 pending 状态可释放。[SPEC] |
| `vkResetCommandBuffer` | 重置单个 command buffer，清除已录制的命令。[SPEC] |
| `vkResetCommandPool` | 重置整个 command pool，更高效但会重置池中所有 buffer。[SPEC] |
| `vkBeginCommandBuffer` | 开始录制，指定 usage flags。[SPEC] |
| `vkEndCommandBuffer` | 结束录制，进入 executable 状态。[SPEC] |
| `vkCmd*` | 各类录制命令：draw、dispatch、barrier、copy、pipeline bind 等。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_EXT_debug_utils`：可用于为 command buffer 设置 debug name / marker，便于 RenderDoc / Validation 识别。[TOOL]
- Secondary command buffer 通过 `VK_COMMAND_BUFFER_USAGE_RENDER_PASS_CONTINUE_BIT` 在 render pass 内继续执行。[SPEC]

---

## 4. 标准使用流程

```text
创建 VkCommandPool（属于目标 queue family）
→ vkAllocateCommandBuffers
→ vkBeginCommandBuffer（指定 ONE_TIME_SUBMIT 等 flag）
→ 录制 vkCmd* 命令
→ vkEndCommandBuffer
→ vkQueueSubmit
→ GPU 执行
→ Fence signal 后
→ vkResetCommandBuffer（或 vkResetCommandPool）
→ 重新 vkBeginCommandBuffer 录制下一帧
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `commandPool` | 必须属于实际提交 queue 的 family，且 family 支持录制的命令。[SPEC] | 只按 graphics/compute 名称判断，忽略 family 实际 capability 与提交身份。[SPEC] |
| `level` | 普通路径由 `PRIMARY` submit 并 execute `SECONDARY`；secondary 不直接 submit。嵌套 secondary 另需相应扩展/feature 与深度等条件，不能默认启用。[SPEC] | 误将 secondary 直接 submit，或未满足条件就使用嵌套 execute。[SPEC] |
| `flags`（begin） | `ONE_TIME_SUBMIT_BIT` 限制本次录制的提交使用，完成后进入 invalid；`RENDER_PASS_CONTINUE_BIT` 声明 secondary 在 render pass instance 内执行。[SPEC] | 把 ONE_TIME 当成 reset 的必要条件；它不能免除 pending 退休要求。[SPEC] |
| `pInheritanceInfo` | Secondary begin 提供合法 inheritance；传统 render pass 与 dynamic rendering 使用不同的继承分支。后者以 NULL renderPass 和 pNext 的 `VkCommandBufferInheritanceRenderingInfo` 描述格式、sample、viewMask 等，不要求传统 framebuffer。[SPEC] | 混用传统与 dynamic inheritance，或把 primary 绑定的普通 pipeline/dynamic state 当成 secondary 自动继承。[TOOL] |
| `pBeginInfo->flags` | 决定 command buffer 是否可二次 submit、是否在 render pass 内继续。[SPEC] | 同一 buffer 尚 pending 时再次 submit 但未满足 `SIMULTANEOUS_USE_BIT`。[SPEC] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] `VkCommandPool` 的 queue family 是否与 submit 目标 queue 一致？
- [ ] 分配的 command buffer level 是否符合用途（primary / secondary）？
- [ ] 是否为 frame-in-flight 分配足够数量的 command buffer？

### 使用阶段

- [ ] begin 前是否为 initial，或 pool 含 RESET_COMMAND_BUFFER_BIT 且 CB 非 pending，允许 begin 隐式 reset？
- [ ] `vkBeginCommandBuffer` 与 `vkEndCommandBuffer` 是否配对？
- [ ] 录制的命令是否在当前 render pass / dynamic rendering 状态下合法？
- [ ] Pipeline、descriptor、vertex buffer 是否在 draw / dispatch 前已绑定？
- [ ] Image layout / barrier 是否满足当前 command 的要求？

### 销毁阶段

- [ ] 销毁或 reset 前，对应 fence 是否已 signal？
- [ ] 是否存在 command buffer 仍引用已销毁资源的风险？

---

## 7. 高频错误

1. 未证明所有关联提交已完成，就 reset 仍 pending 的 command buffer。[SPEC]
2. 未满足 begin 的状态/pool flag 条件；允许隐式 reset 的路径无需显式 reset，也不能为非法状态编造固定返回码。[SPEC]
3. 将 secondary command buffer 直接 `vkQueueSubmit`。[SPEC]
4. Command buffer 录制完成后未调用 `vkEndCommandBuffer`。[SPEC]
5. Command buffer 引用了已销毁的 `VkFramebuffer`、`VkImageView` 或 `VkBuffer`。[SPEC]
6. 同一 frame resource 被多帧 command buffer 复用但 fence 管理错误。[ENGINE]
7. Command pool 的 family 与实际提交 queue 不匹配，或 family 不支持录制的命令。[SPEC]
8. 对 pending command buffer reset/free/re-record；recording 状态本身不禁止合法 reset/free。[SPEC]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-vkBeginCommandBuffer-*`：command buffer 状态、flags、inheritance info。
- `VUID-vkEndCommandBuffer-*`：recording 是否完整、render pass 是否结束。
- `VUID-vkQueueSubmit-*`：command buffer 是否处于 executable 状态。
- `VUID-vkResetCommandBuffer-*`：command buffer 不在 pending 状态。
- `VUID-vkCmdDraw-*` / `VUID-vkCmdDispatch-*`：pipeline / descriptor / vertex buffer / layout 状态。

### RenderDoc / AGI

- 确认是否存在 draw / dispatch call。
- 确认 command buffer 录制是否完整。
- 查看每个 command 的 pipeline state、descriptor binding、resource 内容。[TOOL]

### 日志 / 代码检查

- 检查 `vkAllocateCommandBuffers`、`vkBeginCommandBuffer`、`vkEndCommandBuffer`、`vkQueueSubmit` 返回值。
- 检查 frame-in-flight 的 fence 等待逻辑。
- 检查 reset / begin 顺序。

---

## 9. 生命周期风险

### 创建时机

- Renderer 初始化时，按 frame-in-flight 数量分配 per-frame command buffer。
- 长期存在的 command buffer（如初始化时的 upload buffer）可单独管理。

### 使用时机

- 每帧录制渲染命令。
- 初始化阶段录制资源上传命令。
- Compute pass 录制 dispatch 命令。

### 销毁时机

- 对应 command pool 销毁时自动释放；也可单独 `vkFreeCommandBuffers`。[SPEC]
- 必须确保 GPU 不再使用，否则 free 后仍被 pending submit 引用会导致 crash。[SPEC]

### in-flight 风险

- Command buffer 在 pending 时不能 reset/free/re-record。满足 `SIMULTANEOUS_USE_BIT` 及全部相关条件时可再次提交/执行，但不免除资源同步或所有关联提交完成后才能修改的要求。[SPEC]
- Command buffer 引用的资源（image view、framebuffer、buffer、descriptor）在 GPU 完成前必须保持有效。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- reset/free 前须证明所有关联提交已完成；可使用覆盖这些提交的 fence、满足 signal scope 的 timeline semaphore 或适当 queue/device idle 等合法完成证据，不限定只能用 fence。[SPEC]
- `vkQueueSubmit` 返回不代表执行完成；无关的 fence/timeline 值也不是当前 command buffer 的退休证明。[SPEC]

### GPU-GPU 同步

- Command buffer 内部的 barrier、semaphore wait、event wait 控制 GPU 执行顺序。[SPEC]
- 同一 queue 的 submission order 是定义同步作用域的顺序，不保证所有命令依次完成；hazard 仍需 barrier/event 等依赖，跨 queue 通常用 semaphore。[SPEC]

### 资源访问同步

- 同一 command buffer 内可通过 `vkCmdPipelineBarrier` 安排资源状态转换。[SPEC]
- 同 queue 跨 command buffer 可用覆盖 submission order 的 barrier/event；跨 queue 用 semaphore，host 介入也须满足内存与完成约束。[SPEC]

---

## 11. Android 注意点

- Android 上 command pool 通常按 queue family 创建，graphics / compute / transfer 需分开或确保 queue family 兼容。[ANDROID]
- Surface / swapchain recreate 时，旧 command buffer 及资源要在全部关联提交完成后才能 reset/free。可用正确完成点而非强制全 device idle；presentation 的 image 使用退休另行证明，不能用渲染 fence 或 command buffer 完成替代。[ANDROID]
- 移动端应避免每帧 allocate / free command buffer，使用 reset + reuse。[ENGINE]
- AGI 可查看每帧 command buffer 录制内容与 GPU 执行时间线。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 每帧 allocate / free command buffer 会带来显著 CPU 开销；推荐 per-frame reset + reuse。[ENGINE]
- `vkResetCommandPool` 通常比逐个 `vkResetCommandBuffer` 更高效。[ENGINE]
- 减少 command buffer 分段，合并小的 copy / barrier 命令可降低录制开销。[HEUR]

### GPU 侧

- Command buffer 本身不直接决定 GPU 性能，但内部的 barrier、layout transition、render pass 边界会影响 GPU 并行度。[SPEC]
- Secondary command buffer 适合多线程录制，但 execute 时存在 overhead，不适合极短命令。[HEUR]

### 移动端

- 移动端 command buffer 录制开销对 CPU frame time 影响明显，应避免每帧动态分配。[ENGINE]
- 尽量减少每帧的 pipeline bind 和 descriptor bind 切换次数。[ENGINE]

---

## 13. 专家经验

**经验**：
为每个 frame-in-flight slot 分配独立的 command buffer（或独立的 command pool），配合 fence 使用。这样每帧只需 reset 当前 slot 的 buffer，无需等待所有 GPU 工作完成。

**适用条件**：
双缓冲 / 三缓冲渲染，CPU 需要提前准备下一帧。

**不适用情况**：
单缓冲或命令极少、CPU 不提前准备帧的场景。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `queue_submit.md`
- `command_buffer_lifetime.md`
- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`
- `../08_synchronization/pipeline_barrier.md`
- `../06_pipeline/graphics_pipeline.md`
- `../05_descriptor/descriptor_set.md`

---

## 15. 需要回查官方文档的情况

1. Secondary command buffer 的 inheritance info 具体要求。
2. `VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT` 的使用限制。
3. Command pool 与 queue family 的精确对应关系。
4. 多线程下 command buffer 录制与 pool 的线程安全规则。


<a id="command-state-thread-contract"></a>

## 18. Command buffer 状态与 host 外部同步

**条件**：command pool 的 queue family 必须匹配提交 queue，且 family 支持所录命令；graphics-capable family 可能同时支持 compute，不按“graphics pool/compute pool”标签判断。PRIMARY 可直接 submit；SECONDARY 通过合法 execute/继承路径使用。[SPEC]

**正常路径**：initial→recording→executable→pending→完成；普通录制完成回 executable，ONE_TIME_SUBMIT 完成回 invalid。串行再次 submit 普通 executable CB 不需要 SIMULTANEOUS_USE；允许 pending 再提交等使用才涉及它，不免除资源 race 与所有提交完成后才能 reset 的规则。[SPEC]

**Reset/begin**：vkResetCommandBuffer 要求 pool 的 RESET_COMMAND_BUFFER_BIT，允许任何非 pending 状态；vkResetCommandPool 不要求该 flag，但全池必须无 pending CB。带该 flag 的 pool 允许 begin 对非 pending 的 invalid/recording/executable buffer 隐式 reset；没有该 flag 则 begin 必须从 initial。不能将非法状态预测为某个固定错误码。[SPEC]

**线程合同**：command pool 是 externally synchronized；两个线程即使各录不同 CB，只要来自同一 pool 也不能并发使用。推荐每个 worker、每个 frame slot、每个 family 独立 pool，或对 pool 全部使用加锁。提交 queue 的 host 锁与 pool 锁不同；SIMULTANEOUS_USE 不授予多个 host 线程并发修改同一 CB 的权限。[SPEC][ENGINE]

**失败/回退**：secondary reset/free/re-record 可能使引用它的 primary invalid，主从都要重建有效录制；销毁 GPU 将访问的资源不能用 barrier 修复。录制失败保留错误记录、合法 reset后重录，不能 submit 不完整/invalid CB。少线程场景可回退串行录制而非共享无锁 pool。

**验证**：覆盖普通 serial resubmit、ONE_TIME invalid、pending reset拒绝、pool reset跨CB完成检查、两个线程同pool拒绝与分pool允许、secondary失效传播。确认完成点覆盖每一次并行使用；验证层与host线程检测都保留日志。

固定依据：Vulkan 1.4.368，commit fa30d4e312e843193601be7cb926c7e25d9ec885；[cmdbuffers#commandbuffers-lifecycle](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/cmdbuffers.adoc#commandbuffers-lifecycle)；[cmdbuffers#commandbuffers-pools](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/cmdbuffers.adoc#commandbuffers-pools)；[cmdbuffers#commandbuffers-recording](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/cmdbuffers.adoc#commandbuffers-recording)。[SPEC]

## Delivery19 ordinary descriptor / command-buffer joint lifecycle (bounded L1/L2)

This contract connects ordinary descriptor updates to command-buffer retirement
and invalidation. A completed submission is not permission to reuse a recording
after its referenced ordinary descriptor binding has changed.

- **Preconditions:** primary command buffer, ordinary descriptor bindings (neither
  UPDATE_AFTER_BIND nor UPDATE_UNUSED_WHILE_PENDING), known complete reference
  inventory, externally serialized command buffer/pool/set host access. Identify
  objects and generations; a reused handle or unrelated fence is not proof.
- **Pending:** wait for every relevant submission to retire. Individual reset is
  forbidden while pending (`VUID-vkResetCommandBuffer-commandBuffer-00045`). A
  descriptor update is separately forbidden (03047); resetting does not bypass it.
- **Retired/executable:** an ordinary referenced-binding update invalidates the
  recorded command buffer. Reset/re-record before submitting it again. A fence
  wait fixes pending ownership but does not restore an invalid recording.
- **Reset:** individual reset requires the pool's RESET_COMMAND_BUFFER flag
  (00046); otherwise use an appropriate pool lifecycle after all its uses retire.
  Resetting a secondary can also invalidate referencing primaries; this experiment
  does not cover that graph or pool-wide reset.
- **Data correctness:** re-recording alone does not establish memory visibility.
  Retain the workload's resource dependencies, coherent/noncoherent readback
  handling and fence ownership. Do not infer a GPU memory barrier from host state.
- **Failure:** a validation callback configured to abort invalid commands provides
  a safe diagnostic experiment, not evidence that an invalid driver submission
  executed successfully. Unsupported timeline or missing layers must fail closed.

Paired tests source: `cases19/descriptor_lifetime`, exact versions and hashes in
`coverage/v1.0.19/descriptor-lifetime.json`. This is an authored CPU-ICD compute
experiment, not production-engine discovery, hardware/SC/Live acceptance or full
VK03 coverage. Consult that checked record for actually exercised branches.

Normative sources (live pages, separate from the frozen registry snapshot):
[vkResetCommandBuffer](https://docs.vulkan.org/refpages/latest/refpages/source/vkResetCommandBuffer.html),
[vkUpdateDescriptorSets](https://docs.vulkan.org/refpages/latest/refpages/source/vkUpdateDescriptorSets.html).

<a id="delivery19-secondary-dynamic-draw"></a>
## Delivery19 secondary dynamic-rendering draw（限定可执行路径）

测试仓 `cases19/secondary_draw/run.py` 连接真实 secondary 录制、primary execute、shader 绘制及完整像素读回，补普通命令管理的实际使用证据；不是仅检查 inheritance 字段。[ENGINE]

- **前提与分支**：core 1.3、已查询并启用 dynamicRendering、graphics queue、兼容的 RGBA8 attachment 与 coherent readback。在单一 host 线程串行录制，primary/secondary 来自同一 queue family。未启用 nested command buffer、simultaneous use 或继承 query。[SPEC][TOOL]
- **继承**：secondary 使用 `RENDER_PASS_CONTINUE_BIT`，NULL renderPass，pNext 的 inheritance rendering 指定 color 格式、sample count、viewMask、depth/stencil；primary 在 `SECONDARY_COMMAND_BUFFERS_BIT` rendering instance 内 execute。这些是兼容性声明，不等于继承任意 primary pipeline/descriptor/dynamic state；绘制所需状态在 secondary 内明确建立。[SPEC]
- **实际数据链**：secondary 绑定实际 graphics pipeline 并 draw，primary 结束 rendering 后建立 color-write → transfer-read，再复制到 readback，transfer-write → host-read，经实际 fence 成功后验证每个像素。执行关系不替代资源内存依赖。[SPEC][TOOL]
- **负控**：negative secondary 的 inheritance 和自身 pipeline 均使用 BGRA8，而 primary attachment 是 RGBA8；安全中止 `vkCmdExecuteCommands` 的唯一 06028 诊断，丢弃 primary，不提交不匹配命令。它测试的是 execute 继承格式冲突，不是 secondary 自身 pipeline draw 格式错误。错误像素参考另行实际退出非零。[TOOL]
- **生命周期**：所有对象在提交完成前保持有效；pending 时不得 reset/free。已退休 secondary 的 reset/re-record 可能使引用 primary 失效，需重录相应关系；本例仅验证一次录制/执行及拒绝路径，不代表 pending、多帧重录或多线程图已验证。DeviceWaitIdle 失败时保守退出，不销毁可能仍 pending 的资源；这不是实际设备故障恢复测试。[SPEC][ENGINE]

格式负控对应测试仓冻结 1.4.309 normative.json；结构语义参见 [inheritance rendering](https://docs.vulkan.org/refpages/latest/refpages/source/VkCommandBufferInheritanceRenderingInfo.html) 与 [execute commands](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdExecuteCommands.html)。最新页面不替换固定 cohort 的 VUID 文本。[SPEC]

限定 CPU ICD、单 secondary、单个 color attachment/sample1、离屏小图。传统 render pass、multiview/depth/resolve、query inheritance、nested、multi-thread/multi-queue、物理 GPU/移动性能、外部工程与 Live/盲测仍未验。VK03/VK10 只增加 PARTIAL_BOUNDED，不能宣布完整 domain 或最终交付通过。[ENGINE]

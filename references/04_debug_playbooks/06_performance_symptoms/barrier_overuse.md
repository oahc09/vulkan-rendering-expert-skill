# Debug Playbook: Barrier Overuse

## 0. 适用范围

### 适用

- GPU Profiler 显示大量空泡（idle / wait），怀疑 barrier 过多或过于保守。
- 每帧调用数十次以上 `vkCmdPipelineBarrier`。
- 存在大量 `VK_PIPELINE_STAGE_ALL_COMMANDS_BIT` / `VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT` 的全局 barrier。
- Render graph 或手写同步代码导致过度同步。

### 不适用

- 同步 hazard 未解决的情况（先清零 hazard 再优化 barrier）。
- GPU 满载无空泡的纯 ALU / fragment 瓶颈。
- CPU 录制 command buffer 耗时高但 GPU 无等待。

---

## 1. 现象

- GPU 时间轴存在大量间隙，利用率显著低于 100%。
- 降低分辨率、简化 shader 后帧时间改善有限。
- 增加 draw call 或 compute 任务后 GPU 仍无法满负荷。
- 每帧 barrier 调用次数随 pass 数线性增长。
- 多 queue 架构下 graphics queue 频繁等待 compute / transfer queue 信号。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 全局 barrier 滥用 | 大量使用 `ALL_COMMANDS` + `MEMORY_READ/WRITE` 覆盖所有资源 | Pipeline Barrier |
| P0 | Barrier stage / access 过于保守 | `srcStage` 选 `BOTTOM_OF_PIPE`、`dstStage` 选 `TOP_OF_PIPE` 或 `ALL_COMMANDS` | Pipeline Barrier |
| P0 | 不必要的 image layout transition | 同一帧内对同一 image 反复 transition | Image Memory Barrier |
| P1 | 缺少 render graph 批量优化 | 每个 pass 独立插入 barrier，未合并相邻 pass 的依赖 | Render Pass / Barrier |
| P1 | 多 queue 过度串行化 | 本可并行的 compute / transfer / graphics 被多余 semaphore 串行 | Semaphore / Queue |
| P1 | Subpass dependency 未充分利用 | 同一 render pass 内仍使用 pipeline barrier 替代 subpass dependency | Render Pass |
| P2 | 不必要的 `vkDeviceWaitIdle` / `vkQueueWaitIdle` | 每帧或每次 submit 后都 wait idle | Synchronization |

---

## 3. 快速验证路径

1. **统计每帧 `vkCmdPipelineBarrier` 调用次数和涉及资源数**。`[TOOL]`
2. **用 GPU Profiler 查看时间轴空泡**：空泡位于 barrier 前后即说明同步开销或等待。`[TOOL]`
3. **把可疑全局 barrier 替换为局部 buffer / image barrier**，观察 hazard 是否出现。`[TOOL]`
4. **把 `ALL_COMMANDS` 改为精确 stage**，看性能和正确性。`[TOOL]`
5. **检查同一 image 是否被多次 transition**，合并冗余 transition。`[TOOL]`
6. **评估是否可用 subpass dependency 替代 pipeline barrier**。`[SPEC]`

---

## 4. Vulkan 对象链路排查

```text
Producer Pass
→ Pipeline Barrier (global / image / buffer)
→ Consumer Pass
→ Repeat ...
```

逐项检查：

- 每个 barrier 是否覆盖了最小必要的 stage 和 access。`[SPEC]`
- 每个 barrier 是否只涉及真正需要同步的资源。`[SPEC]`
- 相邻 pass 对同一资源的多次 barrier 是否可以合并为一次。`[ENGINE]`
- Image barrier 的 `oldLayout` / `newLayout` 是否必要；是否可用 `GENERAL` 贯穿多个用途（在允许时）。`[SPEC]`
- 是否可以用 render pass subpass dependency 表达同一 render pass 内的依赖。`[SPEC]`
- 多 queue 同步是否使用 timeline semaphore 精确表达阶段依赖，而非每次 submit 都等待。`[SPEC]`
- 是否存在每帧 `vkDeviceWaitIdle` 或每 submit `vkQueueWaitIdle`。`[ENGINE]`

---

## 5. 高频根因

1. 为“保险”在所有资源读写间插入 `ALL_COMMANDS` 全局 barrier。`[HEUR]`
2. Render graph 实现粗糙，每个 pass 边界都插入全同步 barrier。`[ENGINE]`
3. 手写同步时代码复制，同一段 producer/consumer 关系重复加 barrier。`[ENGINE]`
4. 未区分 execution dependency 和 memory dependency，统一使用最强 barrier。`[SPEC]`
5. 同一 image 在多个 pass 间被反复 transition，未保持统一 layout。`[ENGINE]`
6. 多 queue 使用 binary semaphore 每次 submit 都信号 / 等待，未用 timeline semaphore 表达阶段依赖。`[ENGINE]`
7. 为调试方便每帧末尾调用 `vkDeviceWaitIdle`。`[ENGINE]`

---

## 6. 修复方案

### 最小修复

- 把全局 barrier 替换为针对具体资源的 `VkImageMemoryBarrier` / `VkBufferMemoryBarrier`。`[SPEC]`
- 把 `ALL_COMMANDS` 替换为实际 producer / consumer stage（如 `COLOR_ATTACHMENT_OUTPUT` → `FRAGMENT_SHADER_BIT`）。`[SPEC]`
- 把 `MEMORY_READ | MEMORY_WRITE` 替换为实际 access mask（如 `COLOR_ATTACHMENT_WRITE` → `SHADER_READ`）。`[SPEC]`
- 移除每帧 `vkDeviceWaitIdle` 和多余的 `vkQueueWaitIdle`。`[ENGINE]`

### 稳定修复

- 建立资源状态跟踪，仅在状态真正变化时插入 barrier，避免冗余 transition。`[ENGINE]`
- 使用 render graph / frame graph 全局分析 pass 依赖，批量生成最简 barrier 集合。`[ENGINE]`
- 在同一 render pass 内用 subpass dependency 替代 pipeline barrier。`[SPEC]`
- 对可重叠的 compute / transfer / graphics 使用 timeline semaphore 表达阶段性依赖，而非完全串行。`[SPEC]`

### 工程化修复

- 在 debug build 中对每个 barrier 进行“必要性”断言：若前后资源状态无变化则报警。`[ENGINE]`
- CI 中统计每帧 barrier 数量和全局 barrier 比例，设定阈值。`[TOOL]`
- 提供自动化工具对比开启 / 关闭某 barrier 后的 hazard 报告和性能变化。`[TOOL]`
- 对常用资源状态转换建立预定义 barrier 模板，避免手写保守参数。`[ENGINE]`

---

## 7. 回归验证

- [ ] 每帧 barrier 数量显著下降。
- [ ] GPU 时间轴空泡减少，利用率提升。
- [ ] Validation Layer sync 分支无新增 hazard。
- [ ] 多 queue / 多线程场景下仍正确。
- [ ] resize / rotation / swapchain recreate 后同步逻辑仍正确。
- [ ] 低端设备和高端设备均通过性能和正确性测试。

---

## 8. 相关 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/buffer_memory_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/08_synchronization/event.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`

---

## 9. 工具证据

### Validation Layer

- 关注 sync 分支是否报告 hazard；优化 barrier 后应无新增 hazard。`[TOOL]`
- 关注 best practice 分支关于过度同步或 `ALL_COMMANDS` 使用的建议。`[TOOL]`

### RenderDoc

- 查看 event browser 中 barrier 数量和位置。`[TOOL]`
- 查看 image layout transition 是否过于频繁。`[TOOL]`
- 查看 draw / dispatch 之间是否存在不必要的大段等待。`[TOOL]`

### AGI / Android

- 查看 GPU 时间轴，统计 `IDLE` / `WAIT` 时间占比。`[TOOL]`
- 查看 `GPU % Busy` 是否因 barrier 空泡低于预期。`[TOOL]`
- 对比优化前后每帧 GPU duration。`[TOOL]`

### logcat

- 搜索与 submit / wait / fence 相关的性能日志。`[ANDROID]`
- 检查是否有驱动对频繁 barrier 的警告。`[ANDROID]`

---

## 10. Android 分支

Android 上 barrier overuse 对 tile-based GPU 影响尤为明显，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效；surface 重建时不应额外插入全局等待 barrier。`[ANDROID]`
2. **Tile-based GPU 的 barrier 成本**：Adreno / Mali 上 image barrier 可能导致 tile cache flush，过度 barrier 会显著增加带宽和帧时间。`[ANDROID]`
3. **Subpass 替代 barrier**：mobile GPU 上应优先使用 subpass dependency / input attachment 在 tile memory 内完成数据传递，避免 pipeline barrier 导致的 system memory 往返。`[ANDROID]`
4. **Swapchain image layout**：尽量保持 swapchain image 仅在 `UNDEFINED` → `COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` 之间 transition，避免中间来回切换。`[SPEC]`
5. **Compute / graphics 交错**：mobile 上并发可能抢占带宽；优化 barrier 时需验证是否导致性能反而下降。`[ANDROID]`
6. **Present 等待**：避免在 present 前插入不必要的 `ALL_COMMANDS` barrier，确保 color attachment write 到 present 的依赖尽量用 subpass dependency 或精确 stage barrier。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - 每帧 `vkCmdPipelineBarrier` 调用次数和类型分布（global / image / buffer）。
   - GPU Profiler 时间轴截图，标注空泡位置。
   - 典型 barrier 的 stage / access / image layout 参数。
   - Render pass 结构图或 render graph 依赖图。
   - 是否使用 subpass dependency、timeline semaphore。
   - 是否每帧调用 `vkDeviceWaitIdle` 或 `vkQueueWaitIdle`。
   - 设备型号、GPU、驱动版本、Android 版本。
3. 给出最小验证路径：把全局 barrier 逐个替换为局部 barrier → 合并相邻 transition → 用 subpass dependency 替代。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 stage / access / subpass dependency 规范。
   - `[TOOL]` 若 Profiler 已显示空泡和 barrier 数量证据。
   - `[ENGINE]` 若基于 render graph 或资源状态机推断。
   - `[HEUR]` 若尚未拿到工具数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 tile-based GPU 或 Surface 生命周期。

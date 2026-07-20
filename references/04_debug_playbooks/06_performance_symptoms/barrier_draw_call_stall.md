# Debug Playbook: Barrier Overuse / Draw Call Bottleneck

> 合并自 2 个原 playbook 文件。

---

## Debug Playbook: Barrier Overuse

### 0. 适用范围

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

### 1. 现象

- GPU 时间轴存在大量间隙，利用率显著低于 100%。
- 降低分辨率、简化 shader 后帧时间改善有限。
- 增加 draw call 或 compute 任务后 GPU 仍无法满负荷。
- 每帧 barrier 调用次数随 pass 数线性增长。
- 多 queue 架构下 graphics queue 频繁等待 compute / transfer queue 信号。

---

### 2. 最可能原因排序

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

### 3. 快速验证路径

1. **统计每帧 `vkCmdPipelineBarrier` 调用次数和涉及资源数**。`[TOOL]`
2. **用 GPU Profiler 查看时间轴空泡**：空泡位于 barrier 前后即说明同步开销或等待。`[TOOL]`
3. **把可疑全局 barrier 替换为局部 buffer / image barrier**，观察 hazard 是否出现。`[TOOL]`
4. **把 `ALL_COMMANDS` 改为精确 stage**，看性能和正确性。`[TOOL]`
5. **检查同一 image 是否被多次 transition**，合并冗余 transition。`[TOOL]`
6. **评估是否可用 subpass dependency 替代 pipeline barrier**。`[SPEC]`

---

### 4. Vulkan 对象链路排查

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

### 5. 高频根因

1. 为“保险”在所有资源读写间插入 `ALL_COMMANDS` 全局 barrier。`[HEUR]`
2. Render graph 实现粗糙，每个 pass 边界都插入全同步 barrier。`[ENGINE]`
3. 手写同步时代码复制，同一段 producer/consumer 关系重复加 barrier。`[ENGINE]`
4. 未区分 execution dependency 和 memory dependency，统一使用最强 barrier。`[SPEC]`
5. 同一 image 在多个 pass 间被反复 transition，未保持统一 layout。`[ENGINE]`
6. 多 queue 使用 binary semaphore 每次 submit 都信号 / 等待，未用 timeline semaphore 表达阶段依赖。`[ENGINE]`
7. 为调试方便每帧末尾调用 `vkDeviceWaitIdle`。`[ENGINE]`

---

### 6. 修复方案

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

### 7. 回归验证

- [ ] 每帧 barrier 数量显著下降。
- [ ] GPU 时间轴空泡减少，利用率提升。
- [ ] Validation Layer sync 分支无新增 hazard。
- [ ] 多 queue / 多线程场景下仍正确。
- [ ] resize / rotation / swapchain recreate 后同步逻辑仍正确。
- [ ] 低端设备和高端设备均通过性能和正确性测试。

---

### 8. 相关 API 卡片

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

### 9. 工具证据

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

### 10. Android 分支

Android 上 barrier overuse 对 tile-based GPU 影响尤为明显，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效；surface 重建时不应额外插入全局等待 barrier。`[ANDROID]`
2. **Tile-based GPU 的 barrier 成本**：Adreno / Mali 上 image barrier 可能导致 tile cache flush，过度 barrier 会显著增加带宽和帧时间。`[ANDROID]`
3. **Subpass 替代 barrier**：mobile GPU 上应优先使用 subpass dependency / input attachment 在 tile memory 内完成数据传递，避免 pipeline barrier 导致的 system memory 往返。`[ANDROID]`
4. **Swapchain image layout**：尽量保持 swapchain image 仅在 `UNDEFINED` → `COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` 之间 transition，避免中间来回切换。`[SPEC]`
5. **Compute / graphics 交错**：mobile 上并发可能抢占带宽；优化 barrier 时需验证是否导致性能反而下降。`[ANDROID]`
6. **Present 等待**：避免在 present 前插入不必要的 `ALL_COMMANDS` barrier，确保 color attachment write 到 present 的依赖尽量用 subpass dependency 或精确 stage barrier。`[ANDROID]`

---

### 11. 不确定时如何处理

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


---

## Debug Playbook: Draw Call Bottleneck

### 0. 适用范围

### 适用

- 每帧 draw call 数量达到数千至上万，CPU 录制和提交成为瓶颈。
- 相同材质 / mesh 的小物体大量存在，合并潜力大。
- GPU 不饱和但 CPU 无法及时生成 command buffer。
- 开启 instancing 或 indirect draw 前的评估阶段。

### 不适用

- 单个 draw call 本身 GPU 耗时极高（优先优化 shader / geometry）。
- draw call 数量很少但 CPU 时间仍高（优先排查 descriptor、pipeline、sync）。
- 带宽或 ROP 瓶颈导致的 GPU 帧时间长。

---

### 1. 现象

- 每帧 draw call 数远超同类项目或目标预算。
- CPU 录制时间随可见物体数量近似线性增长。
- RenderDoc event browser 中大量连续小 draw，每个 draw 顶点数很少。
- 合批或 instancing 实验后 CPU 时间显著下降。
- GPU 利用率不高，但 CPU 已无法更频繁提交。

---

### 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 未合并相同材质 / mesh 的小物体 | 大量连续 draw 使用同一 pipeline 和 texture，只有 transform / material 参数不同 | Command Buffer / Pipeline |
| P0 | 未使用 instancing | 同一 mesh 重复绘制多次，每次仅 world matrix 不同 | Vertex Buffer / Buffer |
| P0 | 未使用 indirect draw | CPU 需逐物体计算 draw 参数并调用 draw | Command Buffer / Buffer |
| P1 | 频繁的 pipeline / descriptor / state 切换 | 连续 draw 的 pipeline layout、shader、blend 状态频繁变化 | Pipeline / Descriptor |
| P1 | 过度细分的渲染状态排序 | 按材质、深度、透明排序策略导致 batch 被打碎 | Engine Sorting |
| P2 | 每 draw 数据准备开销大 | 每帧为每个物体重新计算 cull、LOD、matrix | CPU Logic |

---

### 3. 快速验证路径

1. **用 Profiler 统计每帧 draw call 数量和平均顶点数**。`[TOOL]`
2. **强制关闭一半物体**：若 CPU 时间近似减半，说明 draw call 本身是瓶颈。`[TOOL]`
3. **注释 material / state 切换**：若合批后 draw call 数下降且 CPU 时间下降，说明 state change 是瓶颈。`[TOOL]`
4. **对相同 mesh 临时启用 instancing**：观察 draw call 数和 CPU 时间变化。`[TOOL]`
5. **RenderDoc 查看 event browser**：确认是否存在大量连续小 draw。`[TOOL]`
6. **统计每帧 pipeline bind 和 descriptor set bind 次数**。`[TOOL]`

---

### 4. Vulkan 对象链路排查

```text
Scene Culling / Sorting
→ Material / Mesh Batch
→ Pipeline Bind
→ Descriptor Set Bind
→ Vertex/Index Buffer Bind
→ vkCmdDraw / vkCmdDrawIndexed
→ Queue Submit
```

逐项检查：

- 相同 pipeline 的 draw 是否被其他 state 切换打散。`[HEUR]`
- 是否对每个物体单独绑定 vertex/index buffer 和 descriptor set。`[ENGINE]`
- 是否使用 `vkCmdDrawIndexed` 复用同一 index buffer 配合不同 vertex buffer。`[HEUR]`
- 是否对 transform / per-object data 使用 push constant 或 dynamic uniform，导致 draw 无法合并。`[HEUR]`
- Indirect draw buffer 是否每帧由 CPU 填充，成为新热点。`[ENGINE]`

---

### 5. 高频根因

1. 每个 mesh 单独绑定 pipeline 和 descriptor set，未按材质排序。`[ENGINE]`
2. 未使用 instancing，同一 mesh 的多个 instance 逐个 draw。`[ENGINE]`
3. 透明物体按深度排序后 draw call 数量爆炸，未做 cluster 或 depth 分桶。`[HEUR]`
4. UI / particle / decal 系统各自提交，未与其他不透明物体合并批次。`[ENGINE]`
5. 动态 uniform / push constant 更新过细，导致无法跨物体复用 descriptor set。`[ENGINE]`
6. 多线程录制结果未按提交顺序合并，导致 batch 被拆分。`[ENGINE]`

---

### 6. 修复方案

### 最小修复

- 按 pipeline / material / texture 对物体排序，减少状态切换。`[HEUR]`（适用条件：场景中存在大量同材质小物体；若材质种类本身极多，收益有限。）
- 对同一 mesh 的多个副本启用 `vkCmdDrawIndexed` + `instanceCount`，instance data 用单独 vertex buffer 或 storage buffer。`[SPEC]`（适用条件：同一 mesh 在视野内出现多次；静态 / 动态 instance 均可。）
- 把 per-object transform 从 push constant 改为 storage buffer 索引，减少 descriptor 切换。`[ENGINE]`（适用条件：每帧 transform 数量大且需要跨 draw 复用同一 pipeline/descriptor。）
- 对小物体使用 simple LOD 或合并 mesh，减少 draw call 数量。`[HEUR]`（适用条件：远景小物体占 draw call 多数；近景大物体收益小。）

### 稳定修复

- 实现 mesh batcher：离线或运行期把相同材质的小 mesh 合并为单个 vertex/index buffer，一次 draw 绘制多个物体。`[ENGINE]`（适用条件：静态场景或变化频率低的物体；动态物体需权衡更新开销。）
- 引入 multi-draw indirect（`vkCmdDrawIndexedIndirect` / `vkCmdDrawIndirectCount`），把 draw 参数列表写入 buffer，一次调用提交多个 draw。`[SPEC]`（适用条件：draw 参数可由 CPU 或 GPU 计算生成，且 GPU 支持对应扩展；注意间接 draw 对某些 state 查询有限制。）
- 使用 bindless descriptor 或 descriptor indexing 减少 descriptor set 切换。`[SPEC]`（适用条件：设备支持 `VK_EXT_descriptor_indexing` 或相关 core 版本；需处理非 uniform resource indexing 限制。）
- 建立 render queue，按 pass / material / depth 自动排序和 batch。`[ENGINE]`（适用条件：项目已有多 pass 渲染管线；透明物体需保留正确排序。）

### 工程化修复

- CI 集成 per-frame draw call budget，超限自动告警。`[TOOL]`
- 实现 GPU-driven rendering：由 compute shader 做 culling 并生成 indirect draw buffer。`[ENGINE]`（适用条件：场景物体数量极大且支持 compute；开发成本高。）
- 对低端设备动态启用 aggressive batching 和降低 instance 上限。`[ENGINE]`
- 建立自动 instancing 系统，根据运行时 mesh 重复度自动合并 instance。`[ENGINE]`

---

### 7. 回归验证

- [ ] 每帧 draw call 数量回到预算内。
- [ ] CPU 录制时间随可见物体数量增长的趋势变缓。
- [ ] 合批 / instancing / indirect draw 后渲染结果正确。
- [ ] Validation Layer 无新错误（特别是 indirect buffer 使用）。
- [ ] RenderDoc event browser 中连续小 draw 明显减少。
- [ ] 不同场景复杂度下帧率稳定。
- [ ] 低端设备和高端设备均通过压力测试。

---

### 8. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`

---

### 9. 工具证据

### Validation Layer

- 关注 indirect draw buffer 的 usage flag、alignment、range 是否正确。`[TOOL]`
- 关注 instancing 时 vertex attribute divisor 或 instance data buffer 是否配置正确。`[TOOL]`
- 关注 batch 合并后是否因 descriptor set 复用导致 resource 状态错误。`[TOOL]`

### RenderDoc

- 查看 event browser 中 draw call 总数、平均顶点数、连续相同 pipeline 的 draw 数量。`[TOOL]`
- 查看 pipeline state 切换频率，确认 state change 开销。`[TOOL]`
- 查看 mesh 数据，确认 instance count 是否生效。`[TOOL]`
- 查看 indirect draw 参数是否正确写入 buffer。`[TOOL]`

### AGI / Android

- 关注 `Draw Calls`、`Vertices`、`Indices` 等 counter。`[TOOL]`
- 查看 CPU 时间轴中 `vkCmdDraw*` 调用密度。`[TOOL]`
- 查看 GPU 是否因 draw call 数量过多导致 command processor 繁忙而空闲 shader。`[TOOL]`

### logcat

- 搜索 `Choreographer: Skipped`、`dropped frames` 等系统掉帧信息。`[ANDROID]`
- 检查是否因 CPU 负载过高导致渲染线程被抢占。`[ANDROID]`

---

### 10. Android 分支

Android 上 draw call 瓶颈受 tile-based GPU 和 CPU 性能限制更明显，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且渲染循环稳定；任何因 surface 重建导致的渲染中断都会放大 draw call 开销。`[ANDROID]`
2. **Tile-based GPU 特性**：Adreno / Mali 对大量小 draw call 的 command processor 开销敏感，batching 收益通常高于 desktop。`[ANDROID]`
3. **Indirect draw 支持**：部分低端设备对 `vkCmdDrawIndirectCount` 等扩展支持有限，需 fallback 到普通 multi-draw。`[ANDROID]`
4. **后台 / 分屏**：`ANativeWindow` 尺寸变化或应用进入后台后应暂停高 draw call 渲染。`[ANDROID]`
5. **低端设备预算**：Android 设备 CPU 性能差异大，需设置动态 draw call budget 并在超过时降级。`[ANDROID]`

---

### 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - 每帧 draw call 总数、平均顶点数、最大单次 draw 顶点数。
   - 每帧 pipeline bind / descriptor set bind / vertex buffer bind 次数。
   - RenderDoc capture 的 event browser 截图。
   - 是否已启用 instancing / indirect draw / bindless。
   - 场景中同材质 / 同 mesh 物体的重复度。
   - 设备型号、GPU、Android 版本。
3. 给出最小验证路径：按材质排序 → 启用 instancing → 使用 multi-draw indirect → 评估 GPU-driven。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 indirect draw、instancing、descriptor indexing 规范。
   - `[TOOL]` 若 Profiler / RenderDoc 已给出明确 draw call 分布证据。
   - `[ENGINE]` 若基于 batching / instancing / GPU-driven 工程经验推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 mobile GPU tile 架构或 Android CPU 限制。


---

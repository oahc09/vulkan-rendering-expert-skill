# Debug Playbook: Draw Call Bottleneck

## 0. 适用范围

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

## 1. 现象

- 每帧 draw call 数远超同类项目或目标预算。
- CPU 录制时间随可见物体数量近似线性增长。
- RenderDoc event browser 中大量连续小 draw，每个 draw 顶点数很少。
- 合批或 instancing 实验后 CPU 时间显著下降。
- GPU 利用率不高，但 CPU 已无法更频繁提交。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 未合并相同材质 / mesh 的小物体 | 大量连续 draw 使用同一 pipeline 和 texture，只有 transform / material 参数不同 | Command Buffer / Pipeline |
| P0 | 未使用 instancing | 同一 mesh 重复绘制多次，每次仅 world matrix 不同 | Vertex Buffer / Buffer |
| P0 | 未使用 indirect draw | CPU 需逐物体计算 draw 参数并调用 draw | Command Buffer / Buffer |
| P1 | 频繁的 pipeline / descriptor / state 切换 | 连续 draw 的 pipeline layout、shader、blend 状态频繁变化 | Pipeline / Descriptor |
| P1 | 过度细分的渲染状态排序 | 按材质、深度、透明排序策略导致 batch 被打碎 | Engine Sorting |
| P2 | 每 draw 数据准备开销大 | 每帧为每个物体重新计算 cull、LOD、matrix | CPU Logic |

---

## 3. 快速验证路径

1. **用 Profiler 统计每帧 draw call 数量和平均顶点数**。`[TOOL]`
2. **强制关闭一半物体**：若 CPU 时间近似减半，说明 draw call 本身是瓶颈。`[TOOL]`
3. **注释 material / state 切换**：若合批后 draw call 数下降且 CPU 时间下降，说明 state change 是瓶颈。`[TOOL]`
4. **对相同 mesh 临时启用 instancing**：观察 draw call 数和 CPU 时间变化。`[TOOL]`
5. **RenderDoc 查看 event browser**：确认是否存在大量连续小 draw。`[TOOL]`
6. **统计每帧 pipeline bind 和 descriptor set bind 次数**。`[TOOL]`

---

## 4. Vulkan 对象链路排查

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

## 5. 高频根因

1. 每个 mesh 单独绑定 pipeline 和 descriptor set，未按材质排序。`[ENGINE]`
2. 未使用 instancing，同一 mesh 的多个 instance 逐个 draw。`[ENGINE]`
3. 透明物体按深度排序后 draw call 数量爆炸，未做 cluster 或 depth 分桶。`[HEUR]`
4. UI / particle / decal 系统各自提交，未与其他不透明物体合并批次。`[ENGINE]`
5. 动态 uniform / push constant 更新过细，导致无法跨物体复用 descriptor set。`[ENGINE]`
6. 多线程录制结果未按提交顺序合并，导致 batch 被拆分。`[ENGINE]`

---

## 6. 修复方案

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

## 7. 回归验证

- [ ] 每帧 draw call 数量回到预算内。
- [ ] CPU 录制时间随可见物体数量增长的趋势变缓。
- [ ] 合批 / instancing / indirect draw 后渲染结果正确。
- [ ] Validation Layer 无新错误（特别是 indirect buffer 使用）。
- [ ] RenderDoc event browser 中连续小 draw 明显减少。
- [ ] 不同场景复杂度下帧率稳定。
- [ ] 低端设备和高端设备均通过压力测试。

---

## 8. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`

---

## 9. 工具证据

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

## 10. Android 分支

Android 上 draw call 瓶颈受 tile-based GPU 和 CPU 性能限制更明显，额外检查：

1. **Surface 有效性前提**：`ANativeWindow` 有效且渲染循环稳定；任何因 surface 重建导致的渲染中断都会放大 draw call 开销。`[ANDROID]`
2. **Tile-based GPU 特性**：Adreno / Mali 对大量小 draw call 的 command processor 开销敏感，batching 收益通常高于 desktop。`[ANDROID]`
3. **Indirect draw 支持**：部分低端设备对 `vkCmdDrawIndirectCount` 等扩展支持有限，需 fallback 到普通 multi-draw。`[ANDROID]`
4. **后台 / 分屏**：`ANativeWindow` 尺寸变化或应用进入后台后应暂停高 draw call 渲染。`[ANDROID]`
5. **低端设备预算**：Android 设备 CPU 性能差异大，需设置动态 draw call budget 并在超过时降级。`[ANDROID]`

---

## 11. 不确定时如何处理

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

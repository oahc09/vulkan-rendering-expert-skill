# Case: Barrier Overuse GPU Stall

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Barrier / Synchronization |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 帧率整体达标，但帧时间（frame time）抖动明显，偶发几十毫秒的尖峰。
- GPU 利用率不低，但 AGI / RenderDoc 显示每个 render pass 之间存在大量空闲气泡（bubble）。
- 同屏对象数、shader 复杂度、分辨率未发生明显变化时，帧时间仍不稳定。
- 关闭部分后处理 pass 后帧时间反而下降得不明显，因为气泡主要集中在 pass 切换处。

---

## 2. 初始上下文

- 平台：Android / Windows / Linux 均可能发生，多 pass 管线下更显著。
- Vulkan 1.1/1.2，使用传统 `vkCmdPipelineBarrier`。
- 每个 render pass 前后都显式插入 image memory barrier。
- 后处理链路拆成 5～8 个 fullscreen pass，每个 pass 读写一张 intermediate image。
- 多 frame-in-flight（2～3），但 barrier 写法是按 pass 同步而非按资源依赖同步。
- 未使用 RenderGraph，barrier 由工程师手写。

---

## 3. 初始误判

最初容易怀疑：

```text
顶点或片段 shader 太复杂；
绘制对象太多，GPU 算力不足；
带宽瓶颈，贴图分辨率过高；
CPU 侧提交不够快，导致 GPU 饿死；
驱动 bug 导致帧时间波动。
```

但 AGI 显示 GPU active 时间并不长，大量时间消耗在 idle bubble 上；RenderDoc 中每个 draw 本身耗时很低，而 pass 之间等待时间很长。最终发现是 barrier 过于保守，导致 pipeline 被频繁排空 `[TOOL]`。

---

## 4. 排查路径

1. 用 Tracy / Systrace 确认 CPU 主线程不阻塞，排除 CPU bound。
2. 用 AGI System Profiler / RenderDoc 查看 GPU 时间线，定位 idle bubble。
3. 在 RenderDoc 中展开每个 pass，统计 `vkCmdPipelineBarrier` 数量和位置。
4. 对单个 resource 做跟踪，确认 barrier 的 src/dst stage 是否覆盖了整个 pipeline。
5. 用 timer query（`VK_EXT_calibrated_timestamps` 或 `vkCmdWriteTimestamp`）测量每个 pass 的实际执行时间和等待时间。
6. 对比 barrier 移除前后的 GPU 时间线，量化 bubble 大小。
7. 将保守的 `ALL_COMMANDS` / `ALL_GRAPHICS` stage 替换为精确 stage，复测。

---

## 5. 关键证据

### Validation Layer

- 通常无 error，但可能报告大量 `SYNC-HAZARD` 警告（如果 barrier 缺失）。
- 过度同步不会触发 validation error，因此不能依赖 Validation Layer 发现 `[SPEC]`。

### RenderDoc / AGI

- AGI GPU Counter：`GPU Utilization` 锯齿状，`External Memory Bandwidth` 出现离散尖峰。
- AGI GPU Timeline：相邻 pass 之间存在大块 idle（empty wave / no active cluster）。
- RenderDoc Texture Viewer：intermediate image 在相邻 pass 间频繁在 `COLOR_ATTACHMENT_OPTIMAL` 与 `SHADER_READ_ONLY_OPTIMAL` 之间切换。
- 关键 resource：intermediate color images、depth stencil image、各 pass 的 pipeline barrier 调用点。

### Log / Code

- 关键代码模式：

```text
// 过度同步：srcStage 和 dstStage 都使用 ALL_COMMANDS
vkCmdPipelineBarrier(cmd,
    VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
    VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
    0, 0, nullptr,
    0, nullptr,
    1, &imageBarrier);
```

- Timer query 日志：

```text
Pass A execution: 0.8 ms
Barrier wait:    1.2 ms   <-- GPU 空泡
Pass B execution: 0.6 ms
```

---

## 6. 根因

根因：每个 render pass 之间都插入全局、粗粒度的 pipeline barrier，导致 GPU 必须排空上游所有工作才能开始下游工作，产生大量空泡和帧时间抖动 `[ENGINE]`。

---

## 7. 修复方案

### 最小修复

- 将 barrier 的 `srcStageMask` / `dstStageMask` 从 `ALL_COMMANDS` 或 `ALL_GRAPHICS` 改为具体 stage（如 `COLOR_ATTACHMENT_OUTPUT` → `FRAGMENT_SHADER`）。
- 将 `srcAccessMask` / `dstAccessMask` 从 `MEMORY_READ_BIT | MEMORY_WRITE_BIT` 改为具体 access（如 `COLOR_ATTACHMENT_WRITE` → `SHADER_SAMPLED_READ`）。
- 合并相邻且依赖相同的 barrier：多张 image 合并到一个 `vkCmdPipelineBarrier` 调用中。

### 稳定修复

- 引入 RenderGraph / FrameGraph，由系统自动推导所需 barrier，避免手写保守 barrier。
- 对可预测的资源依赖使用 `VkSubpassDependency` 或 Dynamic Rendering 的 `VkSubpassBeginInfo` / `VkRenderingAttachmentInfo` 内建同步。
- 使用 `VK_KHR_synchronization2`（`vkCmdPipelineBarrier2KHR`），通过 `VkImageMemoryBarrier2` 更精确地表达 stage/access `[SPEC]`。
- 区分 intra-frame transient resource 与 cross-frame persistent resource，对前者放宽 barrier。

### 工程化修复

- 建立 barrier 审计规则：禁止 `ALL_COMMANDS` 作为 stage mask，除非有明确理由。
- CI 中运行 AGI frame capture，检测 GPU idle bubble 比例；超过阈值自动报警。
- 在 debug 构建中记录所有手写 barrier 的 src/dst stage，定期生成报告。
- 提供自动工具：对 RenderDoc capture 中相邻 draw 之间的 idle 时间做聚类，定位过度同步点。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] AGI GPU Timeline 中 idle bubble 明显减少或消除。
- [ ] 帧时间标准差下降 50% 以上。
- [ ] 各 pass 的 timer query 等待时间接近 0。
- [ ] 多帧运行稳定，无异常抖动。
- [ ] resize / rotation 后 barrier 仍然精确。
- [ ] 关闭/开启后处理链路时，GPU active 时间随 pass 数线性增长，而非出现空泡。

---

## 9. 经验抽象

Barrier 不是越多越好。每多一个 barrier，都是在 GPU pipeline 上增加一道关卡。手写 barrier 时必须同时回答：

```text
谁生产（producer stage/access）？
谁消费（consumer stage/access）？
是否必须全局同步，还是只需这张 image/buffer 同步？
是否可以用 subpass dependency / event / synchronization2 替代 pipeline barrier？
```

过度同步不会触发 Validation Error，却会直接吃帧时间，是最隐蔽的性能陷阱之一 `[ENGINE]`。

---

## 10. 预防规则

1. 禁止无明确理由使用 `ALL_COMMANDS` / `ALL_GRAPHICS` 作为 barrier stage mask。
2. 每个手写 barrier 必须注释说明 producer 和 consumer 的具体 stage 与 access。
3. 相邻 pass 的 barrier 优先合并，减少 pipeline flush 次数。
4. 多 pass 后处理链路优先使用 RenderGraph 自动推导 barrier。
5. 对 TBDR 移动 GPU，避免在 tile 内产生不必要的 image layout transition。
6. 定期用 AGI / RenderDoc 检查 GPU idle bubble，设定阈值并持续监控。
7. 引入 `VK_KHR_synchronization2` 后，统一使用 `vkCmdPipelineBarrier2KHR` 提高表达精度。

---

## 11. 关联 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/barrier_overuse.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_barriers.md`
- `../../05_workflows/07_optimization/optimize_frame_time.md`
- `../../05_workflows/08_migration/convert_single_pass_to_render_graph.md`

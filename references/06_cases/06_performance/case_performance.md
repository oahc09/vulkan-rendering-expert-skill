# Cases: Performance

> 合并自 5 个原 case 文件。关键词: fullscreen-pass, descriptor-cpu, pipeline-stutter, barrier-stall, tile-resolve

---

## Case: Barrier Overuse GPU Stall

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Barrier / Synchronization |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 帧率整体达标，但帧时间（frame time）抖动明显，偶发几十毫秒的尖峰。
- GPU 利用率不低，但 AGI / RenderDoc 显示每个 render pass 之间存在大量空闲气泡（bubble）。
- 同屏对象数、shader 复杂度、分辨率未发生明显变化时，帧时间仍不稳定。
- 关闭部分后处理 pass 后帧时间反而下降得不明显，因为气泡主要集中在 pass 切换处。

---

### 2. 初始上下文

- 平台：Android / Windows / Linux 均可能发生，多 pass 管线下更显著。
- Vulkan 1.1/1.2，使用传统 `vkCmdPipelineBarrier`。
- 每个 render pass 前后都显式插入 image memory barrier。
- 后处理链路拆成 5～8 个 fullscreen pass，每个 pass 读写一张 intermediate image。
- 多 frame-in-flight（2～3），但 barrier 写法是按 pass 同步而非按资源依赖同步。
- 未使用 RenderGraph，barrier 由工程师手写。

---

### 3. 初始误判

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

### 4. 排查路径

1. 用 Tracy / Systrace 确认 CPU 主线程不阻塞，排除 CPU bound。
2. 用 AGI System Profiler / RenderDoc 查看 GPU 时间线，定位 idle bubble。
3. 在 RenderDoc 中展开每个 pass，统计 `vkCmdPipelineBarrier` 数量和位置。
4. 对单个 resource 做跟踪，确认 barrier 的 src/dst stage 是否覆盖了整个 pipeline。
5. 用 timer query（`VK_EXT_calibrated_timestamps` 或 `vkCmdWriteTimestamp`）测量每个 pass 的实际执行时间和等待时间。
6. 对比 barrier 移除前后的 GPU 时间线，量化 bubble 大小。
7. 将保守的 `ALL_COMMANDS` / `ALL_GRAPHICS` stage 替换为精确 stage，复测。

---

### 5. 关键证据

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

### 6. 根因

根因：每个 render pass 之间都插入全局、粗粒度的 pipeline barrier，导致 GPU 必须排空上游所有工作才能开始下游工作，产生大量空泡和帧时间抖动 `[ENGINE]`。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean。
- [ ] AGI GPU Timeline 中 idle bubble 明显减少或消除。
- [ ] 帧时间标准差下降 50% 以上。
- [ ] 各 pass 的 timer query 等待时间接近 0。
- [ ] 多帧运行稳定，无异常抖动。
- [ ] resize / rotation 后 barrier 仍然精确。
- [ ] 关闭/开启后处理链路时，GPU active 时间随 pass 数线性增长，而非出现空泡。

---

### 9. 经验抽象

Barrier 不是越多越好。每多一个 barrier，都是在 GPU pipeline 上增加一道关卡。手写 barrier 时必须同时回答：

```text
谁生产（producer stage/access）？
谁消费（consumer stage/access）？
是否必须全局同步，还是只需这张 image/buffer 同步？
是否可以用 subpass dependency / event / synchronization2 替代 pipeline barrier？
```

过度同步不会触发 Validation Error，却会直接吃帧时间，是最隐蔽的性能陷阱之一 `[ENGINE]`。

---

### 10. 预防规则

1. 禁止无明确理由使用 `ALL_COMMANDS` / `ALL_GRAPHICS` 作为 barrier stage mask。
2. 每个手写 barrier 必须注释说明 producer 和 consumer 的具体 stage 与 access。
3. 相邻 pass 的 barrier 优先合并，减少 pipeline flush 次数。
4. 多 pass 后处理链路优先使用 RenderGraph 自动推导 barrier。
5. 对 TBDR 移动 GPU，避免在 tile 内产生不必要的 image layout transition。
6. 定期用 AGI / RenderDoc 检查 GPU idle bubble，设定阈值并持续监控。
7. 引入 `VK_KHR_synchronization2` 后，统一使用 `vkCmdPipelineBarrier2KHR` 提高表达精度。

---

### 11. 关联 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_barriers.md`
- `../../05_workflows/07_optimization/optimize_frame_time.md`
- `../../05_workflows/08_migration/convert_single_pass_to_render_graph.md`


---

## Case: Descriptor Update CPU Overhead

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Descriptor / CPU |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- CPU 帧时间高，主线程出现明显热点；GPU 反而经常等待 CPU 提交。
- 场景对象数增加时，CPU 帧时间线性增长，而 GPU 时间几乎不变。
- 用 CPU profiler 抓热点，发现 `vkUpdateDescriptorSets` 或 `vkUpdateDescriptorSetWithTemplate` 占用大量时间。
- 低端 Android 设备上，每帧更新几千个 descriptor 会导致掉帧甚至 ANR。

---

### 2. 初始上下文

- 平台：Android / Windows / Linux 均可能发生，Android 低端机更明显。
- Vulkan 1.1/1.2，使用传统 `VkDescriptorSet` + `vkUpdateDescriptorSets`。
- 每个动态物体每帧重新分配并更新一个 descriptor set。
- Uniform buffer / texture 等资源本身已使用 ring buffer 或动态偏移，但 descriptor set 没有复用。
- 未使用 bindless descriptor 或 descriptor indexing 扩展。
- 每帧 draw call 数量在 500～2000 之间。

---

### 3. 初始误判

最初容易怀疑：

```text
Uniform buffer 上传太慢；
Command buffer 录制量太大；
CPU 端 culling / animation 计算成为瓶颈；
Draw call 数量太多，应该合并 instance；
GPU 负载过高导致 CPU 等待 fence。
```

但 CPU profiler 显示 culling 和 command buffer 录制时间正常，而 `vkUpdateDescriptorSets` 独占主线程 5～10 ms。RenderDoc 中 bound resources 显示 descriptor 更新次数远高于 draw call 数量。最终确认是 descriptor update 开销 `[TOOL]`。

---

### 4. 排查路径

1. 使用 Tracy / Perfetto / Android Studio CPU Profiler 捕获主线程热点。
2. 过滤 `vkUpdateDescriptorSets` / `vkUpdateDescriptorSetWithTemplate` 调用次数和耗时。
3. 在 RenderDoc 中查看一帧内 descriptor set 更新次数与 draw call 比例。
4. 统计每帧 `VkWriteDescriptorSet` 数量，确认是否每个 object 都触发一次完整更新。
5. 检查 descriptor pool 是否每帧重新创建，导致额外分配开销。
6. 对比动态 uniform offset vs 每帧更新 buffer info 的开销。
7. 尝试临时禁用部分 descriptor 更新，观察 CPU 帧时间变化。

---

### 5. 关键证据

### Validation Layer

- 通常无 error；若 descriptor pool 耗尽会报 `VUID-vkAllocateDescriptorSets-descriptorPool-*`。
- 大量 `vkUpdateDescriptorSets` 不会直接产生 validation message，但可能伴随 `PERFORMANCE` 类型提示（视 Validation Layer 配置而定）`[TOOL]`。

### RenderDoc / AGI

- RenderDoc：一帧内出现数百到数千次 `vkUpdateDescriptorSets` 调用。
- RenderDoc：每个 draw call 绑定的 descriptor set handle 几乎都不相同，说明没有复用。
- AGI CPU Timeline：`vkUpdateDescriptorSets` 出现在主线程关键路径上，形成长条热点。
- 关键 resource：per-object descriptor set、`VkDescriptorPool`、uniform buffer ring buffer。

### Log / Code

- 关键代码模式：

```text
for (auto& obj : visibleObjects) {
    VkDescriptorSet set = allocateDescriptorSet(pool, layout);
    VkWriteDescriptorSet write = {};
    write.dstSet = set;
    write.dstBinding = 0;
    write.pBufferInfo = &obj.uboInfo;  // 每帧不同
    vkUpdateDescriptorSets(device, 1, &write, 0, nullptr);
    vkCmdBindDescriptorSets(cmd, GRAPHICS, pipelineLayout, 0, 1, &set, ...);
    vkCmdDrawIndexed(cmd, ...);
}
```

- CPU profiler 输出：

```text
Frame CPU: 18 ms
  └─ vkUpdateDescriptorSets: 8 ms (44%)
  └─ Command buffer record: 4 ms
  └─ Culling / animation: 3 ms
```

---

### 6. 根因

根因：每帧为每个可见物体重新分配并更新 descriptor set，把大量 CPU 时间消耗在 descriptor write 上，而不是复用 descriptor set 并通过 dynamic offset 或 bindless 索引区分对象数据 `[ENGINE]`。

---

### 7. 修复方案

### 最小修复

- 为常用 material 预分配并复用 descriptor set，不再每帧重新 allocate。
- 使用 `vkCmdBindDescriptorSets` 的 `pDynamicOffsets` 参数，配合 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC` 区分 per-object UBO，而不是更新 buffer info。
- 对只切换贴图的场景，将贴图数组化到 texture array 或 bindless descriptor，减少 descriptor write。

### 稳定修复

- 建立 material descriptor set cache：按 material + 贴图组合缓存 descriptor set，命中时直接复用。
- 对 per-object 数据统一使用 dynamic uniform buffer / storage buffer + dynamic offset。
- 对 skeletal / instance 数据使用 push constants 或 storage buffer，避免 descriptor 更新。
- 使用 `VkDescriptorUpdateTemplate` 批量生成 descriptor write，降低单次更新开销 `[SPEC]`。

### 工程化修复

- 引入 bindless descriptor（`VK_EXT_descriptor_indexing`）：所有纹理、buffer 注册到全局 descriptor array，shader 通过 index 访问，几乎零 per-draw descriptor 更新。
- 在材质系统中区分 static descriptor（material）和 dynamic data（object），前者缓存，后者用 dynamic offset / push constant。
- CI 中监控每帧 `vkUpdateDescriptorSets` 调用次数，超过阈值报警。
- 提供工具：自动统计 RenderDoc capture 中 descriptor set 更新/复用比例。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] CPU 帧时间下降，`vkUpdateDescriptorSets` 不再出现在主线程热点 Top5。
- [ ] 可见物体数增加时，CPU 帧时间增长明显放缓。
- [ ] RenderDoc 中每帧 descriptor update 次数从 N 降至接近 material 数量。
- [ ] GPU 不再因 CPU 提交慢而空闲等待。
- [ ] Android 低端机不再因 descriptor 更新导致 ANR。
- [ ] resize / rotation 后 descriptor cache 仍能正确失效与重建。

---

### 9. 经验抽象

Descriptor set 是 CPU 侧昂贵资源，不是 draw call 的“一次性包装纸”。设计时应遵循：

```text
Static / per-material 数据：缓存 descriptor set，按组合复用。
Dynamic / per-object 数据：使用 dynamic uniform offset、storage buffer index、push constant。
Per-frame 变化的贴图：使用 texture array 或 bindless。
```

把 descriptor update 从“每 draw”降到“每 material”或“每帧一次全局更新”，是 CPU 优化中最划算的收益之一 `[ENGINE]`。

---

### 10. 预防规则

1. 禁止在 render loop 中频繁 allocate / update descriptor set。
2. 每个 descriptor set 必须明确属于 static、dynamic 还是 transient，并有对应复用策略。
3. Per-object 数据优先使用 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC` + dynamic offset。
4. 大量贴图切换优先使用 texture array 或 bindless descriptor indexing。
5. 引入 descriptor set cache，命中时直接复用，未命中时批量 allocate 和 update。
6. 定期用 CPU profiler 检查 `vkUpdateDescriptorSets` 耗时，设定阈值。
7. 在 CI 中限制每帧 descriptor write 数量，超过阈值阻断提交。

---

### 11. 关联 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_descriptor_updates.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`


---

## Case: Fullscreen Pass Bandwidth High

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Fullscreen Pass / 移动端 |
| 平台 | Android / Mobile |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [HEUR]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

开启后处理效果后，GPU frame time 明显升高。  
移动端设备发热，帧率下降。  
Shader ALU 看起来不复杂，但 AGI 中 bandwidth 或 render target 读写压力明显。

---

### 2. 初始上下文

- Android Vulkan 工程。
- 多个 fullscreen pass。
- 使用 offscreen render target。
- 部分 pass 使用高分辨率中间图。
- 可能包含 blur、bloom、glass、distortion、tone mapping。
- 可能存在 alpha blend 或 MSAA resolve。

---

### 3. 初始误判

最初容易怀疑：

```text
fragment shader 太复杂；
GPU 算力不够；
采样函数太慢。
```

但 AGI 证据显示主要瓶颈不是 ALU，而是 render target 读写、texture sampling、tile resolve 或 bandwidth。

---

### 4. 排查路径

1. 用 AGI 确认 GPU bound。
2. 列出所有 fullscreen pass。
3. 统计每个 pass 的 input/output 分辨率。
4. 统计 render target format。
5. 检查 texture sampling 次数。
6. 检查 load/store。
7. 检查是否存在多次 offscreen write/read。
8. 检查 alpha blend / MSAA resolve。
9. 尝试半分辨率 / quarter 分辨率验证。
10. 比较优化前后 frame time。

---

### 5. 关键证据

### AGI

观察到：

- GPU frame time 增加。
- bandwidth 相关指标偏高。
- 多个 fullscreen render pass。
- render target load/store 频繁。
- 大尺寸 offscreen attachment 读写多。

### RenderDoc

观察到：

- 多 pass 串联。
- 中间 render target 尺寸等于屏幕全分辨率。
- 某些 pass 输出马上被下一 pass 读取。
- 可能存在可合并 pass。

### Code

关键问题：

```text
多个 fullscreen pass 都使用 full resolution RGBA16F offscreen image，并且每 pass 都写回内存后再被下一 pass 采样。
```

---

### 6. 根因

根因：后处理链路中 fullscreen pass 数量多、中间 render target 分辨率和格式偏高，导致移动端 bandwidth 和 tile resolve 成本过高，而不是单纯 shader ALU 过重。

---

### 7. 修复方案

### 最小修复

- 将部分 blur / bloom 中间 pass 降到 half / quarter resolution。
- 减少采样次数。
- 合并可合并的 fullscreen pass。
- 降低中间 RT format 精度。

### 稳定修复

- 为后处理链路建立 pass cost 表。
- 对每个 pass 记录：
  - resolution
  - format
  - sample count
  - load/store
  - input/output
- 对移动端默认使用降分辨率中间 RT。

### 工程化修复

- 引入 render graph。
- 自动标记 transient attachment。
- 优化 load/store。
- 避免不必要的 tile resolve。
- 为效果参数设置性能档位。

---

### 8. 修复后验证

- [ ] AGI 中 GPU frame time 下降。
- [ ] bandwidth 相关指标下降。
- [ ] RenderDoc 中 pass 数量或 RT 尺寸降低。
- [ ] 视觉效果可接受。
- [ ] 长时间运行温度 / 功耗改善。
- [ ] resize / pause / resume 后仍正常。

---

### 9. 经验抽象

移动端后处理性能不能只盯 shader ALU。  
Fullscreen pass 的核心成本经常来自：

```text
render target 读写
texture sampling
tile resolve
alpha blending
format 精度
pass 数量
```

---

### 10. 预防规则

1. 新增 fullscreen pass 必须评估 bandwidth。
2. blur / bloom 默认考虑 half / quarter resolution。
3. 中间 RT format 不要盲目使用高精度。
4. 可合并 pass 优先合并。
5. AGI / RenderDoc 结果必须作为性能判断证据。
6. 移动端效果必须设计性能档位。

---

### 11. 关联 API 卡片

- `../../03_api_manual/07_rendering/attachment_load_store.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_fullscreen_pass.md`
- `../../05_workflows/07_optimization/optimize_mobile_bandwidth.md`


---

## Case: Mobile Tile Resolve High

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Mobile / Bandwidth / Tile |
| 平台 | Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 在 Android 高端机上流畅，在中低端 Mali / Adreno 设备上发热严重、掉帧。
- 同一场景在 Desktop GPU 上 GPU frame time 只有 4 ms，在手机上却达到 12 ms 以上。
- 降低 shader 复杂度、减少 overdraw 后改善有限。
- 设备背面明显发热，长时间运行后出现 thermal throttling，帧率阶梯式下降。

---

### 2. 初始上下文

- 平台：Android，目标 GPU 为 Mali / Adreno 等 TBDR（Tile-Based Deferred Rendering）架构。
- 渲染管线包含多个 offscreen pass：shadow map、G-Buffer、SSAO、blur、tonemapping 等。
- 每个 offscreen pass 使用独立的 color / depth attachment，render pass 之间通过 image barrier 衔接。
- 部分 pass 的 `loadOp` / `storeOp` 使用默认值，未针对 TBDR 优化。
- 未使用 subpass dependency 合并多个写入/读取步骤。
- 开启了 MSAA，但没有使用 resolve attachment 或 tile-local resolve。

---

### 3. 初始误判

最初容易怀疑：

```text
Fragment shader ALU 太重；
Overdraw 过高；
贴图采样带宽太大；
CPU 提交太慢导致 GPU 饿死；
驱动对某个 extension 支持不好。
```

但 AGI 显示 GPU active 时间集中在 fragment 阶段，而 External Memory Bandwidth 异常高；RenderDoc 中每个 offscreen pass 结束都会触发 store/resolve。最终发现是 tile memory 被反复 flush 到 system memory，造成大量外部带宽 `[TOOL]` `[ANDROID]`。

---

### 4. 排查路径

1. 用 AGI 捕获一帧，查看 `External Memory Read Bandwidth` / `External Memory Write Bandwidth` counter。
2. 对比同场景 Desktop 与 Mobile 的 bandwidth 差异，确认 mobile 带宽异常高。
3. 在 RenderDoc 中检查每个 render pass 的 `loadOp` / `storeOp` / `stencilStoreOp` 设置。
4. 统计有多少 color / depth attachment 在 pass 之间被 store 出去再 load 回来。
5. 检查是否使用了 `STORE` + `LOAD` 组合，而没有使用 `DONT_CARE` / `CLEAR`。
6. 检查 MSAA color / depth 的 resolve 方式：是 tile-local resolve 还是写入系统内存后再 resolve。
7. 在 Mali GPU 上使用 Mali Offline Compiler 或 Streamline 查看 tile read/write 比例。
8. 临时将部分 offscreen pass 合并为 subpass，复测 bandwidth 变化。

---

### 5. 关键证据

### Validation Layer

- 通常无 error；若 store/load 组合导致 layout mismatch 会报 `SYNC-HAZARD` 或 image layout 错误。
- 过度 store 本身不会触发 validation，需要依赖工具 counter `[TOOL]`。

### RenderDoc / AGI

- AGI counter：`External Memory Read Bandwidth` 和 `External Memory Write Bandwidth` 显著高于同类游戏。
- AGI counter：`Tile Read Bandwidth` / `Tile Write Bandwidth` 比例异常，或 `Pixel Fill` 占用高。
- RenderDoc：每个 offscreen pass 的 render target 在 pass 结束后被 store 到 system memory，下一 pass 又被 load 进来。
- RenderDoc Pixel History：同一像素在多个 pass 之间反复写入 external memory。
- 关键 resource：offscreen color images、depth stencil images、MSAA resolve targets。

### Log / Code

- 关键代码模式：

```text
// 默认 store，导致 tile memory flush
VkAttachmentDescription colorAtt = {};
colorAtt.loadOp  = VK_ATTACHMENT_LOAD_OP_CLEAR;
colorAtt.storeOp = VK_ATTACHMENT_STORE_OP_STORE;  // 不需要 downstream 时也应 store

// 下一 pass 又重新 load
depthAtt.loadOp  = VK_ATTACHMENT_LOAD_OP_LOAD;
depthAtt.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
```

- Mali Streamline 输出示例：

```text
External Memory Read:  4.2 GB/s
External Memory Write: 3.8 GB/s
Tile Read:             0.9 GB/s
Tile Write:            1.1 GB/s
```

---

### 6. 根因

根因：TBDR GPU 上以 `STORE` + `LOAD` 方式反复将 tile-local color / depth 数据写回系统内存，并在后续 pass 重新读入，造成极高的 external memory bandwidth 和发热 `[ANDROID]` `[ENGINE]`。

---

### 7. 修复方案

### 最小修复

- 对不需要 downstream 读取的 render target，将 `storeOp` 改为 `VK_ATTACHMENT_STORE_OP_DONT_CARE`。
- 对临时 depth buffer，在 render pass 结束时不 store depth。
- 避免在相邻 pass 之间对同一张 image 做 `STORE` → `LOAD`。

### 稳定修复

- 使用 Vulkan subpass 和 `VkSubpassDependency`，将多个读写步骤合并到同一个 render pass 内，数据保留在 tile memory 中。
- 使用 `INPUT_ATTACHMENT` 在 subpass 间共享 on-chip 数据，而不是 store/load external image。
- 对 MSAA，使用 resolve attachment 让 resolve 发生在 tile memory 内，而不是先 store 再 compute resolve。
- 使用 transient attachment（`VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` + lazily allocated memory）存放中间结果 `[SPEC]`。

### 工程化修复

- 建立 RenderGraph，自动识别 transient resource 并分配 transient attachment。
- 在 material/postprocess 系统中显式声明 attachment 的 downstream 使用意图，驱动 store/load 决策。
- CI 中集成 AGI bandwidth counter 阈值检查，对每 GB/s 开销做回归测试。
- 针对 Mali / Adreno / PowerVR 分别设定 bandwidth 预算，并定期校准。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] AGI 中 `External Memory Read/Write Bandwidth` 显著下降。
- [ ] 中低端 Android 设备发热降低，thermal throttling 出现时间延后。
- [ ] GPU frame time 下降并趋于稳定。
- [ ] 画面正确，没有因 `DONT_CARE` 导致的 artifact。
- [ ] MSAA resolve 结果正确，边缘无抖动。
- [ ] 多分辨率、多 GPU 品牌下 bandwidth 均在预算内。

---

### 9. 经验抽象

TBDR 的性能瓶颈往往不在 ALU，而在 tile memory 与 external memory 之间的搬运。设计渲染管线时必须把 attachment 的 store/load 视为 first-class 决策：

```text
这个 render target 是否会被下一 pass 读取？
是否可以把消费它的 pass 合并为 subpass？
是否可以使用 transient attachment？
MSAA resolve 是否发生在 tile 内？
```

每一张 intermediate image 的 store 都可能是一次外部内存写，必须给出明确理由 `[ENGINE]` `[ANDROID]`。

---

### 10. 预防规则

1. 每个 attachment 的 `loadOp` / `storeOp` 必须根据 downstream 使用意图填写，禁止默认 `STORE`。
2. 不会被下游读取的 intermediate attachment 必须使用 `DONT_CARE` 或 transient attachment。
3. 相邻 pass 读写同一张 image 时，优先合并为 subpass 或使用 input attachment。
4. MSAA color / depth 必须使用 resolve attachment 在 tile 内完成 resolve。
5. 移动平台必须使用 `VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` 管理短期中间资源。
6. 在 AGI / Mali Streamline 中设定每帧 external bandwidth 预算，并做持续回归。
7. 新增后处理 pass 时必须评估其带来的 tile resolve / store 成本。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_mobile_bandwidth.md`
- `../../05_workflows/07_optimization/optimize_fullscreen_pass.md`
- `../../05_workflows/02_render_pass_effects/add_postprocess_pass.md`


---

## Case: Pipeline Creation Stutter

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Pipeline / Stutter |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 游戏运行时偶发卡顿（hitch），首次进入新场景、首次切换武器、首次开启新特效时尤为明显。
- 卡顿只发生一次，之后同样效果再次使用不再卡顿。
- CPU 帧时间在卡顿时从 8 ms 跳到 80 ms 以上，GPU 帧时间正常。
- 低端 Android 设备上，首次遇到某个 shader variant 时甚至会 ANR。

---

### 2. 初始上下文

- 平台：Android / Windows / Linux 均可能发生，Android 低端机更明显。
- Vulkan 1.1/1.2，使用 `vkCreateGraphicsPipelines` 运行时创建 pipeline。
- Shader 在加载时只编译为 `VkShaderModule`，但 pipeline 按需求懒创建。
- 材质系统支持大量 shader variant（multi_compile / keyword）。
- 未使用 `VK_EXT_graphics_pipeline_library` 或 `VK_KHR_pipeline_executable_properties`。
- Pipeline cache 文件未持久化或持久化策略不完善。

---

### 3. 初始误判

最初容易怀疑：

```text
Shader 实时编译耗时；
贴图首次上传导致 stall；
GC / 内存分配造成卡顿；
CPU culling 或物理计算阻塞；
磁盘 IO 导致阻塞。
```

但 CPU profiler 显示耗时集中在 `vkCreateGraphicsPipelines`；RenderDoc 中卡顿帧正好对应某个新 pipeline 首次绑定。后续确认是 pipeline 运行时创建导致的瞬时 CPU 阻塞 `[TOOL]`。

---

### 4. 排查路径

1. 用 Tracy / Perfetto / Android Studio CPU Profiler 捕获卡顿帧。
2. 定位主线程耗时最长的调用，确认是否为 `vkCreateGraphicsPipelines`。
3. 查看该帧首次出现的 shader / material / keyword 组合。
4. 检查 `VkPipelineCache` 是否启用，以及是否从磁盘加载了缓存数据。
5. 统计一局游戏中首次出现的 pipeline 数量，评估预热缺失范围。
6. 用 `VK_KHR_pipeline_executable_properties`（如可用）查看 driver 内部编译阶段耗时。
7. 临时在启动时预创建所有已知 pipeline，验证卡顿是否消失。

---

### 5. 关键证据

### Validation Layer

- 通常无 error。
- 若 pipeline cache 数据格式不兼容，可能报 `VK_PIPELINE_COMPILE_REQUIRED` 或缓存加载失败（视扩展而定）`[SPEC]`。

### RenderDoc / AGI

- CPU Profiler：卡顿帧中 `vkCreateGraphicsPipelines` 耗时 50～200 ms。
- RenderDoc：卡顿帧首次出现某个 pipeline 的 `vkCmdBindPipeline`，之前的帧不存在该 pipeline。
- AGI CPU Timeline：主线程在 pipeline creation 期间无其他工作，GPU 处于等待状态。
- 关键 resource：`VkPipelineCache`、`VkShaderModule`、pipeline layout、每个 material 对应的 `VkPipeline`。

### Log / Code

- 关键代码模式：

```text
void drawMaterial(Material* mat) {
    if (!mat->pipeline) {
        VkGraphicsPipelineCreateInfo ci = mat->buildCreateInfo();
        vkCreateGraphicsPipelines(device, cache, 1, &ci, nullptr, &mat->pipeline);
    }
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, mat->pipeline);
    vkCmdDrawIndexed(cmd, ...);
}
```

- 启动日志：

```text
Pipeline cache loaded: 0 bytes (首次安装无缓存)
First draw of shader "Particles_Additive_Soft": vkCreateGraphicsPipelines = 120 ms
```

---

### 6. 根因

根因：渲染管线在运行时按需创建 `VkPipeline`，而 driver 编译/链接 pipeline 是同步 CPU 操作，首次调用时阻塞主线程，造成帧时间尖峰 `[ENGINE]`。

---

### 7. 修复方案

### 最小修复

- 确保启用 `VkPipelineCache`，并在启动时从磁盘加载缓存、退出时保存缓存。
- 对已知会在当前关卡使用的 material / shader variant，在加载界面或启动阶段预创建对应 pipeline。
- 避免在 render loop 中首次调用 `vkCreateGraphicsPipelines`。

### 稳定修复

- 在后台线程异步创建 pipeline，主线程在 pipeline ready 前使用 fallback pipeline 或跳过渲染。
- 使用 `VK_EXT_pipeline_creation_cache_control` 的 `VK_PIPELINE_CREATE_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT`，将同步编译失败转换为可异步处理的 `VK_PIPELINE_COMPILE_REQUIRED`。
- 建立 shader variant 预热清单，按关卡/场景预编译。
- 使用 `VK_EXT_graphics_pipeline_library` 将 vertex input、fragment output、pre-rasterization、fragment shader 分阶段缓存，减少完整 pipeline 创建耗时 `[SPEC]`。

### 工程化修复

- 建立 pipeline 预热系统：根据关卡、角色、特效配置自动生成预热列表，在加载时异步编译。
- CI 中跑全量 shader variant 离线编译，生成稳定的 pipeline cache 文件并随包发布。
- 运行时监控首次出现的 pipeline，记录到 telemetry，用于补充预热列表。
- 对无法预热的动态组合，提供显式异步创建机制并给出视觉 fallback。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] 新场景 / 新特效首次出现时无帧时间尖峰。
- [ ] CPU profiler 中 `vkCreateGraphicsPipelines` 不出现在主线程 render loop。
- [ ] Pipeline cache 文件加载成功且命中率高。
- [ ] Android 低端机不再因 pipeline 创建导致 ANR。
- [ ] 异步创建 pipeline 时有合理的 fallback，画面无突兀变化。
- [ ] 应用更新或驱动更新后，pipeline cache 能正确失效并重建。

---

### 9. 经验抽象

Pipeline 创建不是免费的。Shader module 编译只是把 SPIR-V 加载进 driver，真正的开销在 graphics pipeline 创建时的 driver 内部优化/编译。关键规则：

```text
已知 pipeline：离线或加载时预创建。
未知 pipeline：异步创建 + fallback。
Pipeline cache：必须持久化、随包发布、版本化失效。
```

把 pipeline creation 从“首次使用”移到“首次需要之前”，是消除运行时卡顿最有效的手段之一 `[ENGINE]`。

---

### 10. 预防规则

1. 禁止在 render loop 中同步调用 `vkCreateGraphicsPipelines`。
2. 每个 shader variant 必须有明确的创建时机：启动预热、关卡加载、后台异步。
3. `VkPipelineCache` 必须启用，并在应用退出时保存、启动时加载。
4. Pipeline cache 文件必须做版本校验（driver version、app version、shader hash），失效后重新生成。
5. CI 必须离线编译所有已知 shader variant 并生成可发布的 pipeline cache。
6. 对无法预热的动态组合，使用异步创建 + fallback，禁止阻塞主线程。
7. 使用 `VK_EXT_graphics_pipeline_library` 拆分 pipeline 阶段，提高缓存命中率。
8. 运行时 telemetry 记录首次出现的 pipeline，用于补充预热清单。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/reduce_pipeline_creation_stutter.md`
- `../../05_workflows/06_pipeline_descriptor/add_graphics_pipeline.md`
- `../../05_workflows/01_renderer_setup/setup_instance_device_queue.md`


---

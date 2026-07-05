# Case: Render Graph Resource Lifetime

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / RenderGraph / Resource Lifetime |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 引入 RenderGraph 后，部分 transient resource 出现 Validation Layer `SYNC-HAZARD` 或 image layout 错误。
- 某些 pass 读取到上一帧的残留内容，导致拖影、闪烁或后处理结果错误。
- RenderGraph 自动推导的 barrier 在大多数情况下正确，但在资源被多个 consumer 读取时出错。
- 关闭 resource aliasing 后问题消失，但内存占用大幅上升。

---

## 2. 初始上下文

- 平台：通用，常见于使用 RenderGraph / FrameGraph 的中大型渲染器。
- 使用自研或开源 RenderGraph 管理 render pass 和资源。
- RenderGraph 根据 pass 的 read/write 声明自动创建 image/buffer、推导 barrier 和 layout。
- 存在 transient resource：只在单帧内使用、可被 aliasing 复用。
- 部分资源会被多个 pass 读取（如 shadow map、G-Buffer）。
- 尝试开启 resource aliasing 以节省显存。

---

## 3. 初始误判

最初容易怀疑：

```text
RenderGraph 的 barrier 推导有 bug；
Aliasing 实现错误，资源被覆盖；
Pass 的 read/write 声明不正确；
Image layout 转换漏了；
Fence / semaphore 等待不够。
```

但深入跟踪后发现，问题往往不在于 RenderGraph 本身，而在于 transient resource 的生命周期声明与真实使用区间不一致：某个资源被声明为 transient，但实际上跨帧使用；或被多个 consumer 读取时，生命周期只覆盖到第一个 consumer `[ENGINE]`。

---

## 4. 排查路径

1. 在 RenderGraph 编译阶段输出资源生命周期表：创建 pass、最后使用 pass、销毁 pass。
2. 对比资源的真实使用链路，检查生命周期是否覆盖所有 producer / consumer。
3. 检查 resource aliasing：两个资源的使用区间是否真的没有重叠。
4. 检查多 consumer 场景：第一个 consumer 使用后，资源是否被提前销毁或 layout 改变。
5. 检查跨帧资源是否被错误标记为 transient。
6. 用 Validation Layer 的 synchronization 检查定位 hazard。
7. 临时关闭 aliasing，观察问题是否消失，确认与生命周期重叠有关。

---

## 5. 关键证据

### Validation Layer

- `SYNC-HAZARD-READ-AFTER-WRITE`：某个 pass 读取的资源已被后续 write 覆盖。
- `SYNC-HAZARD-WRITE-AFTER-READ`：写操作发生在读操作完成之前。
- `VUID-vkCmdPipelineBarrier-oldLayout-01181`：layout transition 的 old layout 与实际不匹配。
- 错误通常指向被 aliasing 复用的 transient image `[SPEC]`。

### RenderDoc / AGI

- RenderDoc：transient image 在多个 pass 之间的 handle 发生变化，说明发生了 aliasing 复用。
- RenderDoc：某个 consumer pass 读取到的 image 内容与 producer pass 输出不一致。
- AGI：GPU timeline 显示 resource 的分配/释放区间与 pass 执行区间重叠。
- 关键 resource：transient color image、transient depth image、shadow map、G-Buffer。

### Log / Code

- 错误声明示例：

```text
// 错误：shadow map 被声明为 transient，但实际在后续 frame 仍被光照 pass 使用
RenderGraph::TextureDesc shadowDesc;
shadowDesc.lifetime = Transient;  // 错误
shadowDesc.usage    = DEPTH_STENCIL_ATTACHMENT | SAMPLED;
```

- 生命周期表示例：

```text
Resource     Created LastUsed Destroyed
GBuffer0     Pass0   Pass2    Pass5
GBuffer1     Pass0   Pass3    Pass5
BloomTemp    Pass6   Pass7    Pass8
ShadowMap    Pass0   Pass0    Pass1   <-- 生命周期过短
```

---

## 6. 根因

根因：RenderGraph 中 transient resource 的生命周期声明与其实际 producer/consumer 区间不匹配，导致资源在仍有下游读取时被回收或 aliasing 覆盖，引发同步 hazard 和画面错误 `[ENGINE]`。

---

## 7. 修复方案

### 最小修复

- 将出现问题的资源生命周期从 `Transient` 改为 `Persistent`（跨帧）。
- 扩展资源的 last-used pass 到真正的最后一个 consumer。
- 在多 consumer 之间插入显式同步点，确保所有读取完成后再释放或复用。

### 稳定修复

- 在 RenderGraph 编译阶段做生命周期检查：对 declared lifetime 与实际使用区间做静态验证，不一致时 assert 或警告。
- 引入 sub-resource 级别的 lifetime 跟踪：同一 image 的不同 mip/层可独立管理。
- 对 multi-consumer 资源，使用引用计数或“最后完成 pass”算法确定销毁点。
- 对需要跨帧保持的资源，明确标记为 `Persistent`，不参与 aliasing。

### 工程化修复

- 建立 resource aliasing 安全规则：只有生命周期区间完全不重叠且格式/尺寸兼容的资源才能 alias。
- 在 RenderGraph 中集成 automatic lifetime inference：根据 pass 的 read/write 声明自动推导最小区间，同时允许手动覆盖。
- 提供可视化工具：输出每帧 resource lifetime 甘特图，便于人工复核。
- CI 中运行全量 RenderGraph 编译并验证所有 transient resource 的 lifetime 声明与实际使用一致。

---

## 8. 修复后验证

- [ ] Validation clean（包括 synchronization validation）。
- [ ] RenderGraph 编译输出的资源生命周期表与实际使用一致。
- [ ] 开启 resource aliasing 后画面正确，无拖影/闪烁。
- [ ] 内存占用在预期范围内，aliasing 有效节省显存。
- [ ] 多 consumer 场景下所有读取方都能拿到正确数据。
- [ ] 跨帧资源（shadow map、history buffer）未被错误回收。
- [ ] 新增 pass 时生命周期声明错误能被静态检查捕获。

---

## 9. 经验抽象

RenderGraph 不是魔法，它的正确性取决于资源生命周期的声明质量。核心规则：

```text
Transient 资源的生命周期必须精确覆盖从第一个 producer 到最后一个 consumer 的区间。
Multi-consumer 资源的销毁点由最后一个 consumer 决定，不是第一个。
跨帧资源必须声明为 Persistent，禁止参与单帧 aliasing。
```

任何“声明比实际短”都会变成潜在的同步或画面错误；任何“声明比实际长”都会浪费显存 `[ENGINE]`。

---

## 10. 预防规则

1. 每个 transient resource 必须明确记录 first producer pass 和 last consumer pass。
2. Multi-consumer 资源必须使用最后 consumer 的完成点作为销毁/复用边界。
3. 跨帧使用的资源必须声明为 Persistent，禁止标记为 Transient。
4. Resource aliasing 必须验证生命周期区间无重叠、格式兼容、尺寸兼容。
5. RenderGraph 编译阶段必须对 declared lifetime 与实际使用区间做静态校验。
6. 新增 pass 或修改资源使用声明时，必须重新生成并复核资源生命周期表。
7. 在 debug 构建中输出 resource lifetime 甘特图，便于人工检查。
8. CI 中开启 synchronization validation 和 RenderGraph lifetime 校验。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`

---

## 13. 关联 Workflow

- `../../05_workflows/08_migration/convert_single_pass_to_render_graph.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`
- `../../05_workflows/02_render_pass_effects/add_offscreen_render_pass.md`

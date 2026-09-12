# Workflow: Compute To Graphics Sync

## 0. 适用范围

### 适用

- Compute shader 写 buffer，graphics 后续读取。
- Compute shader 写 storage image，fragment shader 后续采样。
- Compute pass 输出给 fullscreen pass / particle rendering / indirect draw 使用。

### 不适用

- compute 输出不被后续 pass 使用。
- graphics 和 compute 完全独立。
- 跨 queue ownership transfer 的复杂多队列场景，本 workflow 只覆盖基础路径。

---

## 1. 任务目标

建立 compute → graphics 的资源可见性和访问顺序：

```text
Compute Write
→ Barrier
→ Graphics Read
```

---

## 2. 输入条件

需要确认：

- compute 输出资源类型：buffer / image。
- graphics consumer 类型：vertex / fragment / index / indirect / sampled image。
- 是否同一 queue。
- image 当前 layout 和目标 layout。
- 是否使用 Synchronization2。
- 是否跨 frame 使用。

---

## 3. 前置检查

- [ ] compute pass 已能执行。
- [ ] graphics consumer 已能执行。
- [ ] 输出资源 usage 覆盖 compute write 和 graphics read。
- [ ] descriptor / pipeline layout 正确。
- [ ] sync validation 可开启。

---

## 4. Vulkan 对象链路

```text
Compute Pipeline
→ Storage Buffer / Storage Image
→ Compute Write
→ Pipeline Barrier
→ Graphics Pipeline
→ Vertex / Fragment / Indirect / Sampled Read
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| compute output buffer | `VkBuffer` | `STORAGE_BUFFER` + consumer usage | shared resource | 否 |
| compute output image | `VkImage` | `STORAGE | SAMPLED` | shared resource | 视尺寸而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| compute set=0,binding=0 | Storage Buffer/Image | output resource | Compute |
| graphics set=0,binding=0 | Sampled Image / Storage Buffer | same resource | Fragment / Vertex |

---

## 7. 同步与 Layout 设计

### Buffer：Compute Write → Graphics Read

| Producer | Resource | Barrier | Consumer |
|---|---|---|---|
| Compute Shader | Storage Buffer | `COMPUTE_SHADER/SHADER_WRITE` → consumer stage/read | Vertex / Fragment / Indirect |

### Image：Compute Write → Fragment Sampled Read

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| Compute Shader | Storage Image | `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | Fragment Shader |

关键点：

- compute write 必须 make available。
- graphics read 必须 make visible。
- image 需要 layout transition。
- descriptor imageLayout 要匹配 graphics 使用 layout。

---

## 7.5 架构决策（Architecture Decision）

> 进入 §8 实现步骤前先完成本节决策链。决策方法与六要素见 `../../02_core_mental_model/engine_architecture.md` §10。

决策链：

```text
需求 → 约束 → Candidate Architecture → Trade-off → Decision
```

| 阶段 | 本 workflow 的关键决策问题 | 参考 |
|---|---|---|
| 需求 | 建立 compute → graphics 的可见性与访问顺序（§1）；架构上先定同步路径：同 queue barrier 还是跨 queue semaphore / timeline [ENGINE] | — |
| 约束 | compute 与 graphics 是否同 queue（§2）、输出资源类型（buffer / image）、consumer 阶段、TBDR 上 barrier / layout 切换会 flush tile memory（§9）、目标设备多 queue 驱动成熟度 | — |
| Candidate | A：同 queue pipeline barrier（含 image layout transition）——本 workflow 的基础路径；B：跨 queue + binary semaphore + release / acquire barrier 对（ownership transfer）；C：跨 queue + timeline semaphore——value 单调递增，追踪跨 queue 与跨帧进度 | D4 |
| Trade-off | A 无跨 queue 开销、Validation 推理直观，但 compute 与 graphics 串行叠加（D4）；B / C 换取 overlap，代价是 ownership transfer barrier 对、semaphore 等待链变长、timeline 空泡风险，同步开销可能大于 overlap 收益（D4）；timeline value 必须单调递增不得复用回退（engine_architecture.md §8）[SPEC]；移动端部分驱动多 queue 实现退化（D4）[ANDROID][VENDOR] | D4 |
| Decision | 写明：为什么选该路径及"为什么不选另一边"（示例：选 A，因 compute 段 <20% frame time、负载与 graphics 强依赖交织，同步简单优先——D4 适用条件）。重新评估条件：AGI 显示 compute 与 graphics 互不重叠且合计 >30% frame time → 迁独立 compute queue（重开 D4）；选 B / C 后 frame time 反升或 timeline 出现同步空泡 → 回退单 queue（保留代码路径，先关开关）。若决策为 B / C，超出本 workflow 基础路径，需补 ownership transfer 细节（见 `../../02_core_mental_model/compute_graphics_relationship.md`） | — |

决策规则：

- 不默认选择新技术方案；每个 Decision 必须写明"为什么不选另一边"。
- Decision 必须包含重新评估条件（什么信号出现时重开决策）。
- 决策完成后进入 §8；验证仍走 §10 验证方式与 Verification Gate（`../../00_expert_entry/verification_gate.md`）。

---

## 8. 实现步骤

1. 确认 compute 输出资源 usage。
2. 确认 graphics consumer descriptor。
3. compute dispatch 后插入 barrier。
4. 对 image 执行 layout transition。
5. graphics pass bind consumer descriptor。
6. 执行 draw。
7. 用 RenderDoc / AGI 验证 compute output 和 graphics input。

---

## 9. Android 注意点

- 移动端 compute 写大图后 graphics 采样会增加带宽压力。
- 尽量避免不必要的大尺寸 storage image。
- 用 AGI 检查 compute 和 graphics pass 之间的 bandwidth。
- rotation 后尺寸相关 output image 必须重建并更新 descriptor。

---

## 10. 验证方式

- [ ] compute output 有内容。
- [ ] graphics input 绑定同一资源。
- [ ] barrier 后无 sync validation hazard。
- [ ] image layout 正确。
- [ ] RenderDoc / AGI 中 graphics pass 能看到 compute 结果。
- [ ] 多帧运行稳定。

---

## 11. 常见失败模式

1. compute 写后没有 barrier。
2. barrier stage/access 写错。
3. image layout 仍是 `GENERAL`，descriptor 却写 `SHADER_READ_ONLY_OPTIMAL` 或反之。
4. graphics descriptor 引用旧资源。
5. output image usage 缺少 `SAMPLED`。
6. 跨 queue 使用但未处理 queue family ownership。

---

## 12. 相关 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

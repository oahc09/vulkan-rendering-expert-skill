# Workflow: Optimize Fullscreen Pass

## 0. 适用范围

### 适用

- Vulkan 后处理 pass GPU 开销高。
- 移动端 fullscreen pass 导致发热 / 掉帧。
- blur / bloom / color grading / distortion / UI glass 效果成本高。
- 多个 offscreen pass 导致 bandwidth 高。

### 不适用

- CPU 逻辑耗时为主。
- 复杂 mesh vertex processing 为主。
- 纯 compute 算法瓶颈但不涉及 fullscreen pass。

---

## 1. 任务目标

系统性优化 fullscreen pass：

```text
Identify Bottleneck
→ Count Passes
→ Check Render Target Size / Format
→ Check Sampling
→ Check Load/Store
→ Check Barriers
→ Reduce Bandwidth / Sampling / Resolve
→ Validate With AGI / RenderDoc
```

---

## 2. 输入条件

需要确认：

- 目标平台和 GPU。
- pass 数量。
- 每个 render target 尺寸和 format。
- 每个 shader 采样次数。
- 是否使用 MSAA。
- 是否使用 alpha blending。
- 是否存在多级 blur。
- 是否有 AGI / RenderDoc capture。
- 当前 frame time / GPU time。

---

## 3. 前置检查

- [ ] 能区分 CPU bound / GPU bound。
- [ ] 能抓 AGI / RenderDoc。
- [ ] 已记录 frame time。
- [ ] pass 输入输出清楚。
- [ ] render target 尺寸和 format 清楚。
- [ ] shader 采样次数清楚。

---

## 4. Vulkan 对象链路

```text
Input Image
→ Fullscreen Pipeline
→ Texture Sampling
→ Render Target
→ Load / Store
→ Barrier
→ Next Pass
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| fullscreen input | `VkImage` | sampled | pass input | 视来源 |
| fullscreen output | `VkImage` | color attachment | pass output | 通常是 |
| intermediate RT | `VkImage` | attachment / sampled | multi-pass intermediate | 通常是 |

---

## 6. Pipeline / Descriptor 设计

需要检查：

- descriptor 数量。
- texture sampling 数量。
- sampler filtering。
- shader 分支。
- 是否可以合并 pass。
- 是否可以使用 half resolution / quarter resolution。
- 是否可以 compute tiling。
- 是否可以降低 format 精度。

---

## 7. 同步与 Layout 设计

优化重点：

| 问题 | 风险 | 优化方向 |
|---|---|---|
| pass 过多 | layout transition / bandwidth 增加 | 合并 pass |
| RT 尺寸过大 | bandwidth 高 | 降分辨率 |
| format 精度过高 | bandwidth 高 | 降 format |
| load/store 不合理 | tile resolve / memory write | 调整 load/store |
| barrier 过宽 | GPU pipeline stall | 精准 stage/access |

---

## 8. 实现步骤

1. 用 AGI / RenderDoc 确认 GPU bound。
2. 列出 fullscreen pass。
3. 统计每个 pass：
   - input
   - output
   - resolution
   - format
   - sample count
   - blend
   - load/store
   - barrier
4. 判断瓶颈：
   - texture sampling
   - bandwidth
   - tile resolve
   - blending
   - barrier stall
5. 优化：
   - 降低中间 RT 分辨率。
   - 合并 pass。
   - 减少采样次数。
   - 使用 separable blur。
   - 降低 format 精度。
   - 减少不必要 alpha blending。
   - 精简 barrier。
   - 避免每帧创建资源。
6. 用 AGI / RenderDoc 复测。
7. 记录优化前后数据。

---

## 9. Android 注意点

移动端重点关注：

- fullscreen pass 数量。
- offscreen render target 次数。
- tile resolve。
- render target load/store。
- texture bandwidth。
- alpha blending read-modify-write。
- 高精度 format。
- 120Hz 下 GPU 预算更紧张。
- AGI counter 是关键证据。

---

## 10. 验证方式

- [ ] GPU frame time 下降。
- [ ] AGI bandwidth 相关指标下降。
- [ ] RenderDoc pass 数减少或 RT 尺寸降低。
- [ ] 视觉效果可接受。
- [ ] Validation clean。
- [ ] resize / pause / resume 后仍正常。
- [ ] 功耗 / 温度有改善，如可测。

---

## 11. 常见失败模式

1. 只优化 shader ALU，但实际瓶颈是 bandwidth。
2. 降分辨率后忘记更新 descriptor。
3. 合并 pass 后 layout / barrier 错误。
4. 降 format 后精度损失明显。
5. 移动端 load/store 没优化，仍触发额外内存写。
6. barrier 过宽导致 pipeline stall。
7. 未用工具验证，只凭感觉判断。

---

## 12. 相关 API 卡片

- `../../03_api_manual/07_rendering/attachment_load_store.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/fullscreen_pass_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_high.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_overuse.md`

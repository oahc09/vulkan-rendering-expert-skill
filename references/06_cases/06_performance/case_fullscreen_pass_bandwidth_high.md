# Case: Fullscreen Pass Bandwidth High

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Fullscreen Pass / 移动端 |
| 平台 | Android / Mobile |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [HEUR]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

开启后处理效果后，GPU frame time 明显升高。  
移动端设备发热，帧率下降。  
Shader ALU 看起来不复杂，但 AGI 中 bandwidth 或 render target 读写压力明显。

---

## 2. 初始上下文

- Android Vulkan 工程。
- 多个 fullscreen pass。
- 使用 offscreen render target。
- 部分 pass 使用高分辨率中间图。
- 可能包含 blur、bloom、glass、distortion、tone mapping。
- 可能存在 alpha blend 或 MSAA resolve。

---

## 3. 初始误判

最初容易怀疑：

```text
fragment shader 太复杂；
GPU 算力不够；
采样函数太慢。
```

但 AGI 证据显示主要瓶颈不是 ALU，而是 render target 读写、texture sampling、tile resolve 或 bandwidth。

---

## 4. 排查路径

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

## 5. 关键证据

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

## 6. 根因

根因：后处理链路中 fullscreen pass 数量多、中间 render target 分辨率和格式偏高，导致移动端 bandwidth 和 tile resolve 成本过高，而不是单纯 shader ALU 过重。

---

## 7. 修复方案

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

## 8. 修复后验证

- [ ] AGI 中 GPU frame time 下降。
- [ ] bandwidth 相关指标下降。
- [ ] RenderDoc 中 pass 数量或 RT 尺寸降低。
- [ ] 视觉效果可接受。
- [ ] 长时间运行温度 / 功耗改善。
- [ ] resize / pause / resume 后仍正常。

---

## 9. 经验抽象

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

## 10. 预防规则

1. 新增 fullscreen pass 必须评估 bandwidth。
2. blur / bloom 默认考虑 half / quarter resolution。
3. 中间 RT format 不要盲目使用高精度。
4. 可合并 pass 优先合并。
5. AGI / RenderDoc 结果必须作为性能判断证据。
6. 移动端效果必须设计性能档位。

---

## 11. 关联 API 卡片

- `../../03_api_manual/07_rendering/attachment_load_store.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/fullscreen_pass_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_high.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_overuse.md`

---

## 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_fullscreen_pass.md`
- `../../05_workflows/07_optimization/optimize_mobile_bandwidth.md`

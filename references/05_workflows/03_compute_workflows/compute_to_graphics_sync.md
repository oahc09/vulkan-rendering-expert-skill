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
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

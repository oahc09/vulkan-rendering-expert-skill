# Case: Descriptor Update CPU Overhead

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Descriptor / CPU |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- CPU 帧时间高，主线程出现明显热点；GPU 反而经常等待 CPU 提交。
- 场景对象数增加时，CPU 帧时间线性增长，而 GPU 时间几乎不变。
- 用 CPU profiler 抓热点，发现 `vkUpdateDescriptorSets` 或 `vkUpdateDescriptorSetWithTemplate` 占用大量时间。
- 低端 Android 设备上，每帧更新几千个 descriptor 会导致掉帧甚至 ANR。

---

## 2. 初始上下文

- 平台：Android / Windows / Linux 均可能发生，Android 低端机更明显。
- Vulkan 1.1/1.2，使用传统 `VkDescriptorSet` + `vkUpdateDescriptorSets`。
- 每个动态物体每帧重新分配并更新一个 descriptor set。
- Uniform buffer / texture 等资源本身已使用 ring buffer 或动态偏移，但 descriptor set 没有复用。
- 未使用 bindless descriptor 或 descriptor indexing 扩展。
- 每帧 draw call 数量在 500～2000 之间。

---

## 3. 初始误判

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

## 4. 排查路径

1. 使用 Tracy / Perfetto / Android Studio CPU Profiler 捕获主线程热点。
2. 过滤 `vkUpdateDescriptorSets` / `vkUpdateDescriptorSetWithTemplate` 调用次数和耗时。
3. 在 RenderDoc 中查看一帧内 descriptor set 更新次数与 draw call 比例。
4. 统计每帧 `VkWriteDescriptorSet` 数量，确认是否每个 object 都触发一次完整更新。
5. 检查 descriptor pool 是否每帧重新创建，导致额外分配开销。
6. 对比动态 uniform offset vs 每帧更新 buffer info 的开销。
7. 尝试临时禁用部分 descriptor 更新，观察 CPU 帧时间变化。

---

## 5. 关键证据

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

## 6. 根因

根因：每帧为每个可见物体重新分配并更新 descriptor set，把大量 CPU 时间消耗在 descriptor write 上，而不是复用 descriptor set 并通过 dynamic offset 或 bindless 索引区分对象数据 `[ENGINE]`。

---

## 7. 修复方案

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

## 8. 修复后验证

- [ ] Validation clean。
- [ ] CPU 帧时间下降，`vkUpdateDescriptorSets` 不再出现在主线程热点 Top5。
- [ ] 可见物体数增加时，CPU 帧时间增长明显放缓。
- [ ] RenderDoc 中每帧 descriptor update 次数从 N 降至接近 material 数量。
- [ ] GPU 不再因 CPU 提交慢而空闲等待。
- [ ] Android 低端机不再因 descriptor 更新导致 ANR。
- [ ] resize / rotation 后 descriptor cache 仍能正确失效与重建。

---

## 9. 经验抽象

Descriptor set 是 CPU 侧昂贵资源，不是 draw call 的“一次性包装纸”。设计时应遵循：

```text
Static / per-material 数据：缓存 descriptor set，按组合复用。
Dynamic / per-object 数据：使用 dynamic uniform offset、storage buffer index、push constant。
Per-frame 变化的贴图：使用 texture array 或 bindless。
```

把 descriptor update 从“每 draw”降到“每 material”或“每帧一次全局更新”，是 CPU 优化中最划算的收益之一 `[ENGINE]`。

---

## 10. 预防规则

1. 禁止在 render loop 中频繁 allocate / update descriptor set。
2. 每个 descriptor set 必须明确属于 static、dynamic 还是 transient，并有对应复用策略。
3. Per-object 数据优先使用 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC` + dynamic offset。
4. 大量贴图切换优先使用 texture array 或 bindless descriptor indexing。
5. 引入 descriptor set cache，命中时直接复用，未命中时批量 allocate 和 update。
6. 定期用 CPU profiler 检查 `vkUpdateDescriptorSets` 耗时，设定阈值。
7. 在 CI 中限制每帧 descriptor write 数量，超过阈值阻断提交。

---

## 11. 关联 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/descriptor_update_overhead.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`

---

## 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_descriptor_updates.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`

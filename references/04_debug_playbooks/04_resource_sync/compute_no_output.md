# Debug Playbook: Compute No Output

## 0. 适用范围

### 适用

- Compute shader dispatch 后没有输出。
- Storage buffer / storage image 没有被写入。
- Compute 输出无法被 graphics pass 读取。
- Compute pass 在 RenderDoc / AGI 中存在但结果不对。

### 不适用

- Graphics pipeline 本身黑屏。
- Descriptor binding 完全错误但 compute 未真正执行。
- Shader 编译失败。

---

## 1. 现象

常见表现：

- dispatch 执行后 output buffer 全 0。
- storage image 没有变化。
- compute 生成的粒子 / blur / culling 结果为空。
- graphics 读取 compute 输出时内容错误或黑屏。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | dispatch group 数量错误 | RenderDoc 显示 dispatch 维度异常 | Compute Pipeline |
| P0 | descriptor 未绑定 storage buffer/image | bound resource 为空 | Descriptor |
| P0 | compute 写后 graphics 读缺少 barrier | compute 输出存在但 graphics 读不到 | Barrier |
| P1 | storage image layout 错误 | Validation layout error | Image / Layout |
| P1 | shader 写入坐标越界 | 输出局部或完全为空 | Shader |
| P2 | buffer/image 初始化或清理覆盖结果 | 后续 pass 清空 | Resource Lifetime |

---

## 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | Validation Layer | SYNC-HAZARD → §5-5（§2 的 P0 compute 写后 graphics 读缺少 barrier 假设）；storage image layout 报错 → §2 的 P1 storage image layout 假设；usage flag 报错 → §5-3 / §5-4 | clean → 检查 2 | — |
| 2 | RenderDoc / AGI：dispatch call 是否存在、compute pipeline 与 descriptor 是否绑定到 `VK_PIPELINE_BIND_POINT_COMPUTE` | dispatch 缺失或未录制 → §11 补充 dispatch 代码；descriptor 为空或绑到 graphics bind point → §5-6（§2 的 P0 descriptor 未绑定假设） | dispatch 存在且绑定正确 → 检查 3 | 存在且正确时排除 §2 的 P0 descriptor 未绑定假设 |
| 3 | groupCount 各维 > 0 断言 | 某维为 0（计算向下取整导致）→ §5-1（§2 的 P0 dispatch group 数量错误假设）；local size 与 dispatch group 不匹配 → §5-2 | 均非 0 → 检查 4 | 非 0 时排除 §2 的 P0 dispatch group 数量错误假设 |
| 4 | dispatch 参数 domain 与资源尺寸匹配：groupCount × localSize 是否覆盖 buffer / image 全部元素、shader 坐标是否越界 | 覆盖不全或 global invocation id 越界 → §5-7（§2 的 P1 shader 写入坐标越界假设） | 匹配 → 检查 5 | 匹配时排除 §2 的 P1 shader 写入坐标越界假设 |
| 5 | storage image / buffer 是否被后续 pass 读取、读取时机是否早于写入完成 | 后续 pass 在写入完成前读取（无 barrier）→ §5-5（§2 的 P0 compute 写后 graphics 读缺少 barrier 假设） | 读取时机正确 → 检查 6 | 正确时排除 §2 的 P0 compute 写后 graphics 读缺少 barrier 假设 |
| 6 | output 资源是否被后续 pass clear / 覆盖 | 被清空或覆盖 → §5-8（§2 的 P2 初始化或清理覆盖假设） | 未被覆盖 → §11 不确定处理 | 未覆盖时排除 §2 的 P2 初始化或清理覆盖假设 |

---

## 4. Vulkan 对象链路排查

```text
Compute Shader
→ DescriptorSetLayout
→ PipelineLayout
→ Compute Pipeline
→ Storage Buffer / Storage Image
→ vkCmdBindPipeline
→ vkCmdBindDescriptorSets
→ vkCmdDispatch
→ Barrier
→ Graphics Consumer
```

重点检查：

- compute pipeline bind point 是否正确。
- descriptor set 是否绑定到 `VK_PIPELINE_BIND_POINT_COMPUTE`。
- storage buffer / image usage 是否正确。
- storage image layout 是否正确。
- compute 写后是否有 barrier。
- graphics 读取是否使用正确 descriptor / layout。

---

## 5. 高频根因

1. dispatch group 计算向下取整导致为 0。
2. local size 和 dispatch group 不匹配。
3. storage image 没有 `VK_IMAGE_USAGE_STORAGE_BIT`。
4. storage buffer 没有 `VK_BUFFER_USAGE_STORAGE_BUFFER_BIT`。
5. compute 写后 fragment 读没有 barrier。
6. descriptor set 绑定到了 graphics bind point。
7. shader 中 global invocation id 越界判断错误。
8. output 资源被后续 pass clear 或覆盖。

---

## 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- 写固定 debug 色 / debug 值，先验证 compute → graphics 管线连通（不解决数据问题）。`[TOOL]`

### Minimal Fix（针对根因的最小修复）

- 把 dispatch group 改成明显非 0。`[SPEC]`
- 确认 descriptor bind point 为 compute。`[SPEC]`
- 添加 compute write → graphics read barrier。`[SPEC]`

### Structural Fix（结构性 / 防复发修复）

- 封装 dispatch size 计算。`[ENGINE]`
- 建立 compute resource state tracking。`[ENGINE]`
- 为 storage buffer/image 建立 usage assert。`[ENGINE]`
- 用 RenderDoc / AGI 验证每个 compute pass 输出。`[TOOL]`

---

## 7. 回归验证

- [ ] RenderDoc / AGI 能看到 dispatch。
- [ ] output buffer / image 有内容。
- [ ] graphics pass 能读取 compute 输出。
- [ ] Validation clean。
- [ ] 多帧运行结果稳定。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 9. 工具证据

### RenderDoc / AGI

关注：

- dispatch call 是否存在。
- compute pipeline 是否绑定。
- storage resource 是否绑定。
- output resource 是否变化。
- compute 后 graphics 前是否有 barrier。

### Validation Layer

关注：

- descriptor type
- storage image layout
- resource usage flag
- synchronization hazard

---

## 10. Android 分支

Android 上额外检查：

1. 目标 GPU 是否支持相关 format 的 storage image。
2. workgroup size 是否过大。
3. 是否存在移动端带宽瓶颈。
4. AGI 是否能看到 compute pass。
5. pause/resume 后 compute resource 是否仍有效。

---

## 11. 不确定时如何处理

需要补充：

- compute shader
- descriptor layout
- dispatch 代码
- barrier 代码
- output buffer/image 创建参数
- RenderDoc / AGI capture

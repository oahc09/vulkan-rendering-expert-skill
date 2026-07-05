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

## 3. 快速验证路径

1. 检查 `vkCmdDispatch` 是否被录制。
2. 检查 dispatch group 数量是否非 0。
3. 检查 compute pipeline 是否绑定。
4. 检查 descriptor set 是否绑定到 compute bind point。
5. 检查 storage buffer / image 是否正确更新到 descriptor。
6. 在 compute shader 写入固定 debug 值。
7. 用 RenderDoc / AGI 检查输出资源。
8. 检查 compute → graphics barrier。

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

### 最小修复

- 写固定 debug 色 / debug 值。
- 把 dispatch group 改成明显非 0。
- 确认 descriptor bind point 为 compute。
- 添加 compute write → graphics read barrier。

### 稳定修复

- 封装 dispatch size 计算。
- 建立 compute resource state tracking。
- 为 storage buffer/image 建立 usage assert。
- 用 RenderDoc / AGI 验证每个 compute pass 输出。

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

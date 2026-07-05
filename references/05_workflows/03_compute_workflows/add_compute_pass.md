# Workflow: Add Compute Pass

## 0. 适用范围

### 适用

- 新增 compute shader pass。
- 用 compute 写 storage buffer / storage image。
- 实现粒子、blur、simulation、culling、image processing。
- Compute 输出被后续 graphics / compute pass 使用。

### 不适用

- 只新增 fragment shader 后处理。
- 不涉及 compute pipeline。
- 只做 CPU 计算。

---

## 1. 任务目标

新增一个 Vulkan compute pass：

```text
Storage Resource
→ DescriptorSet
→ Compute Pipeline
→ vkCmdDispatch
→ Barrier
→ Consumer Pass
```

---

## 2. 输入条件

需要确认：

- compute shader 输入 / 输出资源。
- storage buffer / storage image 类型。
- workgroup size。
- dispatch group count。
- 是否与 graphics 共用 queue。
- compute 输出由谁消费。
- 是否需要跨 queue synchronization。

---

## 3. 前置检查

- [ ] compute queue / graphics queue 可用。
- [ ] shader 编译链路支持 compute。
- [ ] descriptor 管理可用。
- [ ] storage buffer / image usage 正确。
- [ ] barrier 机制可用。
- [ ] RenderDoc / AGI 可看到 dispatch。

---

## 4. Vulkan 对象链路

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
→ Consumer
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| input buffer | `VkBuffer` | `STORAGE_BUFFER` / `UNIFORM_BUFFER` | pass input | 否 |
| output buffer | `VkBuffer` | `STORAGE_BUFFER` | pass output | 否 |
| output image | `VkImage` | `STORAGE | SAMPLED` | pass output | 视尺寸而定 |
| descriptor set | `VkDescriptorSet` | compute resource binding | per-pass / per-frame | 视资源而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | Storage Buffer | input / output buffer | Compute |
| set=0,binding=1 | Storage Image | output image | Compute |

注意：

- `vkCmdBindDescriptorSets` 的 bind point 必须是 `COMPUTE`。
- `stageFlags` 必须包含 compute。
- storage image layout 通常需要正确处理，常见为 `GENERAL`。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| compute shader write | storage buffer | compute shader write → vertex/fragment/compute read | next pass |
| compute shader write | storage image | `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` 或后续 layout | graphics pass |

关键点：

- producer stage：`COMPUTE_SHADER`
- producer access：`SHADER_WRITE`
- consumer stage：根据后续用途选择
- consumer access：根据后续用途选择
- graphics 采样 storage image 前需要 layout transition。

---

## 8. 实现步骤

1. 编写 compute shader。
2. 创建 storage buffer / storage image。
3. 创建 descriptor set layout。
4. 创建 pipeline layout。
5. 创建 compute pipeline。
6. 分配并更新 descriptor set。
7. command buffer 中 bind compute pipeline。
8. bind compute descriptor set。
9. 计算 dispatch group count。
10. 调用 `vkCmdDispatch`。
11. 插入 compute output barrier。
12. 接入后续 graphics / compute consumer。
13. 接入 destroy / recreate。

---

## 9. Android 注意点

- 检查目标 GPU 对 storage image format 的支持。
- workgroup size 不宜盲目过大。
- 移动端 compute + graphics 共享带宽，需用 AGI 验证。
- 如果 output image 随屏幕尺寸变化，rotation 后必须重建。
- pause / resume 后 compute resource 生命周期要稳定。

---

## 10. 验证方式

- [ ] Validation clean。
- [ ] RenderDoc / AGI 能看到 dispatch。
- [ ] storage buffer / image 有输出。
- [ ] 后续 graphics 能读取 compute 输出。
- [ ] 多帧运行稳定。
- [ ] workgroup 数量非 0 且覆盖目标范围。

---

## 11. 常见失败模式

1. dispatch group count 为 0。
2. descriptor 绑定到 graphics bind point。
3. storage image 缺少 `STORAGE` usage。
4. compute 写后 graphics 读缺少 barrier。
5. shader global invocation id 越界。
6. output 被后续 pass 覆盖。
7. Android GPU 不支持目标 storage image format。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`

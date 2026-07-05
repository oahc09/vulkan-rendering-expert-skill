# API Card: VkPipeline (Compute)

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipeline` |
| 常用 API | `vkCreateComputePipelines` / `vkDestroyPipeline` / `vkCmdBindPipeline` / `vkCmdDispatch` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipeline`（compute）封装 compute shader 执行状态，绑定到 compute bind point 后通过 `vkCmdDispatch` 启动线程格；它是 graphics pipeline 的简化形态，只包含单一 compute stage 与 pipeline layout。[SPEC]

---

## 2. 所属对象链路

```text
Compute Shader (SPIR-V)
→ VkShaderModule
→ VkPipelineShaderStageCreateInfo (stage = COMPUTE)
→ VkPipelineLayout
→ vkCreateComputePipelines
→ VkPipeline
→ vkCmdBindPipeline(VK_PIPELINE_BIND_POINT_COMPUTE)
→ vkCmdDispatch / vkCmdDispatchIndirect
→ Compute Shader writes/reads resources
```

### 上游依赖

- Compute shader module 已创建，且入口点为 compute stage。[SPEC]
- Pipeline layout 与 shader 的 descriptor set / push constant 接口匹配。[SPEC]
- 目标 queue family 支持 compute 操作。[SPEC]

### 下游影响

- Compute pipeline 决定 dispatch 的 shader 代码与资源接口。[SPEC]
- Dispatch 后的结果通常需要 barrier 才能被 graphics / transfer 使用。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipeline`
- `VkComputePipelineCreateInfo`
- `VkPipelineShaderStageCreateInfo`
- `VkPipelineLayout`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateComputePipelines` | 创建 compute pipeline。[SPEC] |
| `vkDestroyPipeline` | 销毁 pipeline；必须等待 GPU 完成。[SPEC] |
| `vkCmdBindPipeline` | 在 command buffer 中绑定 compute pipeline。[SPEC] |
| `vkCmdDispatch` | 启动三维线程格。[SPEC] |
| `vkCmdDispatchIndirect` | 从 buffer 读取 dispatch 参数。[SPEC] |
| `vkCmdDispatchBase` | 指定 base group 的 dispatch。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- `VK_KHR_device_group` 相关的 `vkCmdDispatchBase` 用法需查文档。

---

## 4. 标准使用流程

```text
准备 compute SPIR-V
→ vkCreateShaderModule
→ 填写 VkPipelineShaderStageCreateInfo
    → stage = VK_SHADER_STAGE_COMPUTE_BIT
    → module
    → pName
    → pSpecializationInfo (可选)
→ 确认 pipeline layout 与 shader 接口一致
→ vkCreateComputePipelines
→ vkCmdBindPipeline(COMPUTE)
→ vkCmdBindDescriptorSets(COMPUTE)
→ 设置 push constants（如有）
→ 插入必要 barrier（如读取前一次结果）
→ vkCmdDispatch(groupCountX, groupCountY, groupCountZ)
→ 若结果供后续 graphics 使用，插入 barrier
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `stage.stage` | 必须是 `VK_SHADER_STAGE_COMPUTE_BIT`。[SPEC] | 填成 VERTEX 或 FRAGMENT。[TOOL] |
| `stage.module` | compute shader module。[SPEC] | 复用 graphics shader module。[TOOL] |
| `stage.pName` | 入口点名称，与 SPIR-V 一致。[SPEC] | 入口点写错导致 pipeline 创建失败。[TOOL] |
| `stage.pSpecializationInfo` | 覆盖 compute shader 中的 specialization constants。[SPEC] | constantID / offset 不匹配。[TOOL] |
| `layout` | 必须是包含 compute shader 所需 descriptor set / push constant 的 pipeline layout。[SPEC] | layout 缺少 storage buffer/image 的 set。[TOOL] |
| `basePipelineHandle` / `basePipelineIndex` | pipeline derivative 的 base，不常用。[SPEC] | 误用导致创建失败或不可预期行为。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] Shader module 是 compute stage？
- [ ] Pipeline layout 覆盖所有 descriptor set 与 push constant？
- [ ] Specialization constants 是否正确映射？

### 使用阶段

- [ ] 是否在 compute bind point 绑定？
- [ ] 是否绑定了正确的 descriptor set（compute bind point）？
- [ ] Dispatch 前是否对资源做了合适 barrier？
- [ ] `groupCountX/Y/Z` 是否非零？（零 dispatch 无输出）[TOOL]
- [ ] 是否在 compute queue 或支持 compute 的 universal queue 上提交？[SPEC]

### 销毁阶段

- [ ] 等待 fence 确保 GPU 不再使用。
- [ ] 若 pipeline cache 使用，注意 cache 与 pipeline 的销毁顺序。

---

## 7. 高频错误

1. `stage` 未填 `VK_SHADER_STAGE_COMPUTE_BIT`。[TOOL]
2. Pipeline layout 未包含 storage image / storage buffer 的 descriptor set layout。[TOOL]
3. Dispatch 前未对输入资源做 availability / layout transition barrier。[TOOL]
4. Dispatch 后未对输出资源做 barrier，导致 graphics pass 读到旧数据。[TOOL]
5. `groupCountX/Y/Z` 任意维度为 0，导致 dispatch 无输出。[TOOL]
6. 在 graphics queue 上提交 compute work 但 queue 不支持 compute。[TOOL]
7. Storage image layout 不是 `GENERAL`。[TOOL]
8. Compute shader 中 local work group size 与 dispatch size 不匹配导致边界处理错误。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkComputePipelineCreateInfo-*`：stage、layout 合法性。
- `VUID-vkCmdBindPipeline-*`：bind point 与 pipeline 类型匹配。
- `VUID-vkCmdDispatch-*`：group count 非零、descriptor 可访问。
- `VUID-vkCmdDraw-*` / dispatch hazard：synchronization hazard 提示。

### RenderDoc / AGI

- 查看 compute pipeline 的 shader、descriptor binding、push constant。
- 查看 dispatch 参数。
- 查看 storage buffer / image 在 dispatch 前后的内容。

### 日志 / 代码检查

- 检查 `vkCreateComputePipelines` 返回值与 shader 编译日志。
- 检查 dispatch 参数是否非零。
- 检查 barrier 的 srcStage/dstStage、srcAccess/dstAccess。
- 检查 storage image 的 layout 是否为 `VK_IMAGE_LAYOUT_GENERAL`。

---

## 9. 生命周期风险

### 创建时机

- 初始化或首次使用 compute pass 前；建议配合 pipeline cache。[ENGINE]

### 使用时机

- 在 command buffer 中绑定后调用 dispatch；compute pipeline 不能在 render pass 内使用（render pass 内 compute shader 可在 subpass 中作为 secondary 使用，但通常单独提交）。[SPEC]

### 销毁时机

- 确认 GPU 完成后销毁。[SPEC]

### in-flight 风险

- Pipeline 被 command buffer 引用后，fence signal 前不能销毁。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Pipeline 创建后立即可用；dispatch 提交后通过 fence 等待结果。[SPEC]

### GPU-GPU 同步

- Compute 写入 storage buffer/image 后，如需被 graphics/transfer 消费，必须插入 pipeline barrier，常见：
  ```text
  srcStage = COMPUTE_SHADER, srcAccess = SHADER_WRITE
  dstStage = FRAGMENT_SHADER / VERTEX_SHADER / TRANSFER, dstAccess = SHADER_READ / TRANSFER_READ
  ```
  [SPEC]
- 跨 queue 时需要 semaphore。[SPEC]

### 资源访问同步

- Storage image 在 compute 读写时 layout 通常为 `GENERAL`。[SPEC]
- Storage buffer 写入后需要 availability / visibility barrier。[SPEC]

---

## 11. Android 注意点

- Android 上 compute queue 可能是独立的，也可能与 graphics 共享 universal queue；需检查 `vkGetPhysicalDeviceQueueFamilyProperties`。[ANDROID]
- 移动端 compute 功耗高，谨慎用于高频全屏 pass。[ENGINE]
- `local_size_x/y/z` 建议取 wave size 倍数（如 8/16）以提升占用率，但具体最优值随 GPU 变化。[HEUR]
- AGI 可分析 compute dispatch 耗时与资源依赖。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- Compute pipeline 创建成本低于 graphics pipeline，但仍建议启用 pipeline cache。[ENGINE]
- 大量小 dispatch 会增加 CPU 与 command processor 开销；尽量合并或间接 dispatch。[ENGINE]

### GPU 侧

- Compute shader 占用率受 local work group size 与寄存器压力影响。[HEUR]
- 避免 compute 与 graphics 频繁来回切换；尽量把 compute work 集中在一端。[ENGINE]

### 移动端

- 移动端 bandwidth 敏感，compute 读写 large storage image/buffer 容易成为瓶颈。[ENGINE]
- Shared memory / workgroup memory 使用需权衡 bank conflict。[HEUR]
- 避免在 fragment pass 中间插入 compute barrier 导致 tile flush。[ENGINE]

---

## 13. 专家经验

**经验**：
把 compute pass 视为“异步 GPU 任务”：明确 producer/consumer，显式插入 barrier。不要让 compute 隐式假设 graphics 已经写完，也不要让 graphics 隐式假设 compute 已经算完。用 event 或 barrier 把依赖显式化。

**适用条件**：
compute 与 graphics 混合的后处理、粒子、剔除、GPU culling 等场景。

**不适用情况**：
纯 compute 离线任务，可用单一 queue 与 fence 简单同步。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `shader_module.md`
- `pipeline_layout.md`
- `graphics_pipeline.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_set_layout.md`
- `../05_descriptor/descriptor_update.md`
- `../04_buffer_image_memory/buffer.md`
- `../04_buffer_image_memory/image.md`
- `../08_synchronization/pipeline_barrier.md`

---

## 15. 需要回查官方文档的情况

1. Compute shader 中 `LocalSize` 与 `vkCmdDispatch` 的精确关系。
2. Storage image / storage buffer 的 layout 与 access flag 要求。
3. Compute 与 graphics 在同一 queue 与不同 queue 的同步语义差异。
4. `vkCmdDispatchIndirect` 的 buffer usage 与 alignment 要求。
5. Subpass 内 compute shader 使用的限制（如 `VK_SUBPASS_SHADER_STAGE_*` 相关扩展）。

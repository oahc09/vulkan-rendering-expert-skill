# Debug Playbook: Compute → Graphics Sync Error

## 0. 适用范围

### 适用

- Compute dispatch 写入 storage image / storage buffer 后，graphics pass 读取结果异常。
- Compute 与 graphics 使用不同 queue 或同一 queue 但缺少 barrier。
- Validation Layer 报 compute / graphics 之间的 `SYNC-HAZARD-*`。
- 粒子模拟、后处理、GI、culling 等 compute → graphics 链路出现画面错误。

### 不适用

- 纯 graphics pass 内部同步问题（优先看 synchronization_hazard.md）。
- Compute shader 本身输出错误（优先看 compute_no_output.md）。
- 资源上传错误（如 staging buffer 未 flush）。

---

## 1. 现象

- Compute 写入的 storage image 在 fragment shader 中采样为黑或旧帧数据。
- Compute 生成的 indirect draw buffer 被 graphics 读取时数据为空或错位。
- 偶发闪烁、画面滞后一帧、粒子位置不更新。
- Validation Layer 报 `SYNC-HAZARD-READ_AFTER_WRITE` 涉及 compute 和 graphics stage。
- 多 queue 架构下 device lost 或 hang 只出现在 compute → graphics 链路。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 缺少 compute → graphics barrier | compute dispatch 后没有 `vkCmdPipelineBarrier` 直接开始 graphics draw | Pipeline Barrier / Buffer / Image |
| P0 | Stage / access 不匹配 | barrier 的 `srcStageMask` 未包含 `COMPUTE_SHADER_BIT`，或 `dstStageMask` 未包含 graphics 消费 stage | Pipeline Barrier |
| P0 | 跨 queue 未用 semaphore | compute queue 和 graphics queue 未通过 semaphore 同步 | Queue / Semaphore |
| P1 | Storage image layout 错误 | compute 写时 layout 为 `GENERAL`，graphics 读时期望 `SHADER_READ_ONLY_OPTIMAL` 却未 transition | Image / Barrier |
| P1 | Queue family ownership 未转移 | compute queue family 与 graphics queue family 不同，未做 ownership transfer | Queue / Barrier |
| P1 | Indirect buffer 访问不同步 | compute 写 indirect draw buffer 后 graphics `vkCmdDrawIndirect` 未等待 | Buffer / Barrier |
| P2 | Timeline semaphore 值管理错误 | 信号 / 等待值不单调或使用了错误 semaphore | Timeline Semaphore |

---

## 3. 快速验证路径

1. **强制 compute 和 graphics 在同一 queue、同一 command buffer 中顺序录制**，观察错误是否消失。`[TOOL]`
2. **在 compute dispatch 后插入保守 barrier**（`srcStage = COMPUTE_SHADER_BIT`、`srcAccess = SHADER_WRITE`、`dstStage = ALL_GRAPHICS`、`dstAccess = SHADER_READ | SHADER_WRITE | INDIRECT_COMMAND_READ`），观察是否恢复。`[HEUR]`
3. **检查 storage image 的 layout**：compute 写用 `GENERAL`，graphics 采样前是否 transition 到 `SHADER_READ_ONLY_OPTIMAL`。`[SPEC]`
4. **检查是否跨 queue family**：若 compute queue 与 graphics queue 属于不同 family，需 ownership transfer。`[SPEC]`
5. **RenderDoc 查看 compute pass 输出**：确认 storage image / buffer 在 compute 后已有内容。`[TOOL]`
6. **AGI 查看 GPU 时间轴**：确认 compute 和 graphics 是否重叠执行。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Compute Command Buffer
→ Dispatch (write storage image / storage buffer / indirect buffer)
→ Pipeline Barrier / Semaphore
→ Graphics Command Buffer
→ Draw / DrawIndirect / Sample / Input Attachment Read
```

逐项检查：

- Compute shader 写出的资源 usage 是否包含 `VK_IMAGE_USAGE_STORAGE_BIT` / `VK_BUFFER_USAGE_STORAGE_BUFFER_BIT`。`[SPEC]`
- Compute dispatch 后是否有 barrier 覆盖其写操作。`[SPEC]`
- Barrier 的 `srcStageMask` 是否包含 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT`。`[SPEC]`
- Barrier 的 `srcAccessMask` 是否包含 `VK_ACCESS_SHADER_WRITE_BIT`。`[SPEC]`
- Barrier 的 `dstStageMask` 是否包含 graphics consumer 的实际 stage（`VERTEX_SHADER_BIT`、`FRAGMENT_SHADER_BIT`、`DRAW_INDIRECT` 等）。`[SPEC]`
- Barrier 的 `dstAccessMask` 是否包含 `VK_ACCESS_SHADER_READ_BIT` / `VK_ACCESS_INDIRECT_COMMAND_READ_BIT` 等。`[SPEC]`
- 若使用 image，layout 是否从 `VK_IMAGE_LAYOUT_GENERAL`（或 `SHADER_READ_ONLY_OPTIMAL`）正确 transition。`[SPEC]`
- 若跨 queue，是否通过 semaphore 保证 compute submit 在 graphics submit 之前完成。`[SPEC]`
- 若跨 queue family，barrier 是否包含正确的 `srcQueueFamilyIndex` / `dstQueueFamilyIndex`。`[SPEC]`

---

## 5. 高频根因

1. Compute dispatch 后直接 bind graphics pipeline 并 draw，未插入任何 barrier。`[SPEC]`
2. Barrier 中 `srcStageMask` 填 `TOP_OF_PIPE` 而不是 `COMPUTE_SHADER_BIT`，导致 compute 写未完成即被消费。`[SPEC]`
3. `dstAccessMask` 未包含 `INDIRECT_COMMAND_READ`，导致 indirect draw 读到未写入数据。`[SPEC]`
4. Storage image 在 compute 写和 graphics 读之间未做 layout transition，graphics shader 以错误 layout 采样。`[SPEC]`
5. Compute queue 与 graphics queue 属于不同 queue family，只用 semaphore 未做 ownership transfer。`[SPEC]`
6. Timeline semaphore 信号值计算错误，graphics 等待了一个尚未发出的值。`[SPEC]`
7. Per-frame resource ring 管理错误，compute 写帧 N 的资源，graphics 读了帧 N-1 的资源。`[ENGINE]`

---

## 6. 修复方案

### 最小修复

- 在 compute dispatch 后、graphics draw 前插入 `vkCmdPipelineBarrier`：
  - Buffer：`srcStage = COMPUTE_SHADER_BIT`、`srcAccess = SHADER_WRITE`、`dstStage = VERTEX_SHADER_BIT | FRAGMENT_SHADER_BIT | DRAW_INDIRECT`、`dstAccess = SHADER_READ | UNIFORM_READ | INDIRECT_COMMAND_READ`。`[SPEC]`
  - Image：使用 `VkImageMemoryBarrier`，`oldLayout = GENERAL`、`newLayout = SHADER_READ_ONLY_OPTIMAL`，`srcStage = COMPUTE_SHADER_BIT`、`srcAccess = SHADER_WRITE`、`dstStage = FRAGMENT_SHADER_BIT`、`dstAccess = SHADER_READ`。`[SPEC]`
- 对 indirect draw buffer，确保 `dstAccessMask` 包含 `VK_ACCESS_INDIRECT_COMMAND_READ_BIT`。`[SPEC]`
- 若跨 queue，在 compute submit 的 `pSignalSemaphores` 与 graphics submit 的 `pWaitSemaphores` 之间建立 binary / timeline semaphore。`[SPEC]`

### 稳定修复

- 对 compute output 资源建立统一状态机，自动跟踪 `COMPUTE_WRITE` → `GRAPHICS_READ` / `INDIRECT_READ` 的转换。`[ENGINE]`
- 封装 `ComputeDispatch` → `GraphicsPass` 的 barrier 模板，避免每次手写。`[ENGINE]`
- 对跨 queue family 资源自动插入 ownership transfer barrier。`[ENGINE]`
- 对 per-frame compute output 使用 triple buffering，确保 compute 写帧 N 与 graphics 读帧 N 对齐。`[ENGINE]`

### 工程化修复

- 引入 render graph / frame graph，声明 compute pass 和 graphics pass 的读写依赖，由框架自动插入 barrier 和 semaphore。`[ENGINE]`
- CI 启用 sync validation，特别针对 compute → graphics 链路。`[TOOL]`
- 在 debug build 中对每个 compute output 资源校验：消费前是否存在 barrier / semaphore。`[ENGINE]`
- 对 timeline semaphore 值进行封装和断言，防止越界或重复等待。`[ENGINE]`

---

## 7. 回归验证

- [ ] Validation Layer 无 compute → graphics 相关 hazard。
- [ ] RenderDoc 中 compute pass 输出在 graphics pass 中可见且正确。
- [ ] Indirect draw buffer 数据在 graphics 端有效。
- [ ] 多 queue 场景下连续运行无 device lost / hang。
- [ ] 改变帧率 / 分辨率 / rotation 后 compute → graphics 链路仍正确。
- [ ] 关闭 vsync 或高帧率下无资源串帧。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/buffer_memory_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`

---

## 9. 工具证据

### Validation Layer

- 关注 `SYNC-HAZARD-READ_AFTER_WRITE`，特别是 src stage 为 `COMPUTE_SHADER`、dst stage 为 `VERTEX_SHADER` / `FRAGMENT_SHADER` / `DRAW_INDIRECT` 的报告。`[TOOL]`
- 关注 `VUID-vkCmdPipelineBarrier-srcStageMask-...`、`dstStageMask-...`、`srcAccessMask-...`、`dstAccessMask-...` 错误。`[TOOL]`
- 关注 `VUID-vkQueueSubmit-pSignalSemaphores-...` 与 `pWaitSemaphores-...` 相关错误。`[TOOL]`
- 关注 image layout 相关 VUID（如 `VUID-vkCmdDraw-*-imageLayout-...`）。`[TOOL]`

### RenderDoc

- 查看 compute dispatch 后 storage image / buffer 是否已有预期数据。`[TOOL]`
- 查看 graphics draw 时 descriptor 绑定的资源是否为 compute 输出。`[TOOL]`
- 查看 compute 与 graphics 命令之间是否存在 barrier。`[TOOL]`
- 对 indirect draw，检查 buffer 内容是否包含合法的 `VkDrawIndirectCommand`。`[TOOL]`

### AGI / Android

- 查看 GPU 时间轴中 compute dispatch 和 graphics draw 是否被正确分隔。`[TOOL]`
- 检查 compute queue 与 graphics queue 的 submit 顺序是否通过 semaphore 串行化。`[TOOL]`
- 观察 storage image 在 compute 写后 layout 是否正确。`[TOOL]`

### logcat

- 搜索 `SYNC-HAZARD`、`compute`、`graphics`、`semaphore`、`device lost`。`[ANDROID]`
- 检查跨 queue 场景下是否有驱动报告 queue family 不匹配。`[ANDROID]`

---

## 10. Android 分支

Android 上 compute → graphics 同步需额外关注 Surface / ANativeWindow / Swapchain 生命周期和 tile-based GPU 行为：

1. **Surface 有效性前提**：compute dispatch 不直接依赖 Surface，但 graphics draw 最终要 present 到 swapchain；确认 `ANativeWindow` 在 graphics submit / present 时有效。`[ANDROID]`
2. **Swapchain 重建同步**：rotation / resize 后 swapchain 重建，compute 输出的 offscreen image / buffer 尺寸需同步更新，graphics pass 引用的 descriptor 需重新绑定新资源。`[ENGINE]`
3. **Tile-based GPU 的 layout 要求**：Adreno / Mali 上 storage image 在 compute 写后若被 fragment shader 采样，通常需 transition 到 `SHADER_READ_ONLY_OPTIMAL` 以确保 tile cache 正确 flush。`[ANDROID]`
4. **Queue family 限制**：部分 Android 设备 compute queue 与 graphics queue 属于不同 queue family，必须做 ownership transfer，不能仅依赖 semaphore。`[ANDROID]`
5. **内存带宽与调度**：mobile GPU 上 compute 与 graphics 并发可能抢占带宽，导致 frame time 波动；必要时通过 semaphore 强制顺序执行而非并行。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - Validation Layer sync 分支完整日志。
   - Compute dispatch 与 graphics draw 的 command buffer 录制代码。
   - Compute shader 和 graphics shader 的资源声明。
   - Descriptor set layout / update / bind 代码。
   - Barrier / semaphore / event 使用代码。
   - 是否跨 queue / queue family，queue family index 分别是多少。
   - RenderDoc capture 中 compute 输出和 graphics 输入状态。
   - 设备型号、GPU、驱动版本、Android 版本。
3. 给出最小复现路径：同一 queue + 最小 compute dispatch + 最小 graphics draw + 临时保守 barrier。
4. 标注当前判断属于：
   - `[SPEC]` 若已确认 barrier / stage / access / layout / ownership 违反规范。
   - `[TOOL]` 若 Validation / RenderDoc / AGI 已给出明确证据。
   - `[ENGINE]` 若基于资源状态机或 ring buffer 管理推断。
   - `[HEUR]` 若尚未拿到工具证据，仅为可能性排序。
   - `[ANDROID]` 若涉及 tile-based GPU 或 Surface 生命周期。

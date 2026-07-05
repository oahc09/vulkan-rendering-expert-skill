# Debug Playbook: Synchronization Hazard

## 0. 适用范围

### 适用

- Validation Layer sync 分支报告 `SYNC-HAZARD-WRITE_AFTER_READ`、`SYNC-HAZARD-READ_AFTER_WRITE`、`SYNC-HAZARD-WRITE_AFTER_WRITE`。
- 出现 `VK_ERROR_DEVICE_LOST` 或 GPU hang，且怀疑与同步有关。
- Compute 写后 graphics 读不到数据、transfer 上传后 shader 采样为黑、render target 被后续 pass 读错。
- 多 queue / 多线程场景下资源读写顺序不确定。

### 不适用

- 纯 image layout 错误（优先看 image_layout_error.md）。
- 纯 descriptor binding 错误（优先看 descriptor_binding_error.md）。
- CPU 侧线程同步问题（如 `std::mutex` 死锁）。

---

## 1. 现象

- Validation 报告 hazard 及类似 `SYNC-HAZARD-READ_AFTER_WRITE` 的 VUID。
- 资源被写后读，读到旧数据或随机数据。
- 同一资源被两个 pass 同时写，最终结果不确定。
- 多 queue 协作时 compute output 未对 graphics 可见。
- RenderDoc 中 pass A 写入了内容，pass B 读取时内容为空或陈旧。
- 偶发闪烁、画面破损、device lost。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 缺少 barrier | producer 写后 consumer 读直接开始，无 `vkCmdPipelineBarrier` | Barrier / Image / Buffer |
| P0 | Stage / access 不匹配 | barrier 的 `srcStageMask` 早于 producer 实际 stage，或 `dstAccessMask` 未覆盖 consumer 读类型 | Pipeline Barrier |
| P0 | 多 queue 未用 semaphore / ownership transfer | Validation 报跨 queue hazard 或 device lost 在多 queue 时出现 | Queue / Semaphore / Barrier |
| P1 | 依赖方向写反 | `src` 应该是 consumer、`dst` 应该是 producer | Pipeline Barrier |
| P1 | Subpass dependency 缺失或错误 | 同一 render pass 内 attachment 读写未声明 dependency | Render Pass |
| P1 | Event / semaphore 信号过早 | 信号 stage 早于 producer 完成，导致 consumer 提前开始 | Event / Semaphore |
| P2 | Buffer / image 范围覆盖不全 | barrier 只 transition 了部分 mip / layer，consumer 访问了未覆盖区域 | Image / Buffer |

---

## 3. 快速验证路径

1. **开启 `VK_LAYER_KHRONOS_validation` 的 sync 分支**，复现并保存完整日志。`[TOOL]`
2. **定位 hazard 报告的资源 handle**，确认该资源在代码中的所有 producer / consumer。`[TOOL]`
3. **在 producer 后、consumer 前插入保守的 `vkCmdPipelineBarrier`**（`srcStage = ALL_COMMANDS`、`dstStage = ALL_COMMANDS`、`srcAccess = MEMORY_WRITE`、`dstAccess = MEMORY_READ | MEMORY_WRITE`），观察 hazard 是否消失。`[HEUR]`
4. **如果跨 queue，先改为单 queue 提交**，确认问题是否与 queue 间同步有关。`[TOOL]`
5. **检查 render pass 的 subpass dependency**，确认 attachment 读写被正确依赖。`[SPEC]`
6. **用 RenderDoc 查看 producer / consumer 命令顺序和资源状态**。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Producer Command (Draw / Dispatch / Transfer)
→ Pipeline Barrier / Event / Semaphore
→ Execution Dependency
→ Memory Dependency
→ Consumer Command (Draw / Dispatch / Transfer)
```

逐项检查：

- 是否存在 producer 到 consumer 的 execution dependency。`[SPEC]`
- Barrier 的 `srcStageMask` 是否包含 producer 实际产生结果的最后一个 pipeline stage。`[SPEC]`
- Barrier 的 `dstStageMask` 是否包含 consumer 实际开始访问的第一个 pipeline stage。`[SPEC]`
- Barrier 的 `srcAccessMask` 是否覆盖 producer 的写类型（`SHADER_WRITE`、`COLOR_ATTACHMENT_WRITE`、`TRANSFER_WRITE` 等）。`[SPEC]`
- Barrier 的 `dstAccessMask` 是否覆盖 consumer 的读/写类型。`[SPEC]`
- 跨 queue 时是否使用 binary semaphore 或 timeline semaphore 保证提交顺序。`[SPEC]`
- 是否需要 queue family ownership transfer（不同 queue family 共享资源）。`[SPEC]`
- Render pass 内 subpass dependency 的 `srcSubpass`、`dstSubpass`、`srcStageMask`、`dstStageMask`、`srcAccessMask`、`dstAccessMask` 是否完整。`[SPEC]`

---

## 5. 高频根因

1. Compute dispatch 写 storage buffer 后，graphics draw 读该 buffer 没有 barrier。`[SPEC]`
2. `vkCmdCopyBuffer` / `vkCmdUpdateBuffer` 后 shader 直接使用，未做 transfer → shader 的 barrier。`[SPEC]`
3. Barrier 中 `srcStageMask` 填 `TOP_OF_PIPE` 或 `dstStageMask` 填 `BOTTOM_OF_PIPE`，导致 execution dependency 无效。`[SPEC]`
4. `srcAccessMask` 填 0，认为只要 stage 同步即可，忽略了 memory visibility。`[SPEC]`
5. 多 queue 共享 image 时只插入了 semaphore，未做 queue family ownership transfer。`[SPEC]`
6. Render pass 内 color attachment 在前半段写入、后半段采样，未声明自依赖（`srcSubpass = dstSubpass`）。`[SPEC]`
7. 使用 dynamic rendering 时未正确设置 `VkSubpassDependency` 或同步 2 的 `VkSubpassDependency2` / `VkMemoryBarrier2`。`[SPEC]`

---

## 6. 修复方案

### 最小修复

- 在 producer 后、consumer 前插入 `vkCmdPipelineBarrier`，使用准确的 stage 和 access mask。`[SPEC]`
- 对 image 使用 `VkImageMemoryBarrier`，正确填写 `oldLayout` / `newLayout` 和 `subresourceRange`。`[SPEC]`
- 对 buffer 使用 `VkBufferMemoryBarrier`，正确填写 `offset` / `size`。`[SPEC]`
- 跨 queue 时在 submit 之间插入 `VkSemaphore` 信号 / 等待。`[SPEC]`

### 稳定修复

- 建立资源状态机，自动推导每个资源当前的 read/write stage 和 access，按需生成 barrier。`[ENGINE]`
- 使用 Vulkan 1.3 的 `vkCmdPipelineBarrier2` / synchronization2 语义，提升可读性和灵活性。`[SPEC]`
- 对跨 queue 资源统一封装 queue family ownership transfer。`[ENGINE]`
- 在 render pass 创建时根据 attachment 使用模式自动生成 subpass dependency。`[ENGINE]`

### 工程化修复

- 引入 render graph 或 frame graph，由 pass 依赖自动推导 barrier、semaphore、layout transition。`[ENGINE]`
- CI 中强制启用 sync validation，任何 hazard 都视为错误。`[TOOL]`
- 对常用资源模式（transfer → shader、compute → graphics、color → sample）建立宏 / 模板，避免手写 barrier 出错。`[ENGINE]`

---

## 7. 回归验证

- [ ] Validation Layer sync 分支不再报任何 hazard。
- [ ] 多帧运行资源读写结果一致，无闪烁 / 黑屏 / 随机数据。
- [ ] RenderDoc 中 producer 输出能被 consumer 正确读取。
- [ ] 多 queue / 多线程场景下不再出现 device lost 或 hang。
- [ ] resize / rotation / swapchain recreate 后同步逻辑仍正确。
- [ ] 性能未因过度保守的 barrier 显著下降（对比 GPU 帧时间）。

---

## 8. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/buffer_memory_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/08_synchronization/event.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`

---

## 9. 工具证据

### Validation Layer

- 关注 `SYNC-HAZARD-READ_AFTER_WRITE`、`SYNC-HAZARD-WRITE_AFTER_READ`、`SYNC-HAZARD-WRITE_AFTER_WRITE` 及对应 VUID。`[TOOL]`
- 关注 `VUID-vkCmdPipelineBarrier-srcStageMask-...`、`dstStageMask-...`、`srcAccessMask-...`、`dstAccessMask-...` 错误。`[TOOL]`
- 关注 `VUID-vkQueueSubmit-pSignalSemaphores-...`、`pWaitSemaphores-...` 相关错误。`[TOOL]`
- 关注 render pass 的 `VUID-vkCmdDraw-*-None-*` 与 subpass dependency 相关错误。`[TOOL]`

### RenderDoc

- 查看 producer / consumer 命令之间是否存在 barrier / event。`[TOOL]`
- 查看 image 在 consumer 开始时的 layout 是否与 descriptor / attachment 期望一致。`[TOOL]`
- 查看 buffer / image 内容在 producer 后是否已写入、consumer 时是否可读。`[TOOL]`

### AGI / Android

- 查看 GPU 时间轴中 producer 和 consumer 是否重叠执行（应无重叠或重叠被 barrier 正确保护）。`[TOOL]`
- 检查多 queue 提交顺序是否与 semaphore 信号一致。`[TOOL]`
- 观察 compute → graphics 链路是否存在空泡或过度等待。`[TOOL]`

### logcat

- 搜索 `SYNC-HAZARD`、`vkCmdPipelineBarrier`、`semaphore`、`device lost`。`[ANDROID]`
- 检查多 queue 场景下驱动是否报告 queue 间同步异常。`[ANDROID]`

---

## 10. Android 分支

Android 上同步 hazard 常与 Surface / ANativeWindow / Swapchain 生命周期及 tile-based GPU 行为相关，额外检查：

1. **Surface 有效性前提**：确认 `ANativeWindow` 在 barrier / submit / present 时未被释放；`surfaceDestroyed` 后应停止所有 queue submit。`[ANDROID]`
2. **Swapchain 重建同步**：旧 swapchain 销毁前必须等待 GPU idle，所有引用旧 swapchain image 的 command buffer、semaphore 已 retire。`[SPEC]`
3. **跨 queue 资源 ownership**：Adreno / Mali 等 tile-based GPU 对 image layout 和 queue family ownership 更敏感，缺失 ownership transfer 更容易触发 hazard 或 device lost。`[ANDROID]`
4. **Rotation 后 attachment 重建**：depth / offscreen image 重建后，需重新建立从 producer 到 consumer 的完整 barrier 链。`[ENGINE]`
5. **Tile flush 需求**：mobile GPU 上 color attachment 在 subpass 内被采样，若未声明 `INPUT_ATTACHMENT` 或未正确设置 dependency，可能因 tile cache 未 flush 导致 hazard。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - Validation Layer sync 分支完整日志（含 VUID 和资源 handle）。
   - 触发 hazard 的 command buffer 录制代码。
   - producer / consumer 对应的 shader 代码。
   - barrier / semaphore / event 使用代码。
   - render pass 创建信息（含 subpass dependency）。
   - 是否跨 queue / 跨 queue family。
   - RenderDoc capture 中 hazard 点前后的 pipeline state。
   - 设备型号、GPU、驱动版本、Android 版本。
3. 给出最小复现路径：单 queue + 最小 producer / consumer + 临时保守 barrier。
4. 标注当前判断属于：
   - `[SPEC]` 若已确认 stage / access / dependency 违反规范。
   - `[TOOL]` 若 Validation / RenderDoc / AGI 已给出明确 hazard 证据。
   - `[ENGINE]` 若基于资源状态机或 render graph 推断。
   - `[HEUR]` 若尚未拿到工具证据，仅为可能性排序。
   - `[ANDROID]` 若涉及 tile-based GPU 或 Surface 生命周期。

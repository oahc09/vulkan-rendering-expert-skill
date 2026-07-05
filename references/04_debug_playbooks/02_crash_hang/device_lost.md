# Debug Playbook: Device Lost

## 0. 适用范围

### 适用

- `vkQueueSubmit`、`vkQueuePresentKHR`、`vkAcquireNextImageKHR`、`vkDeviceWaitIdle` 等返回 `VK_ERROR_DEVICE_LOST`。
- 应用直接闪退，未弹出 TDR 但 GPU 已不可恢复。
- RenderDoc / AGI 抓帧时报告 device removed。
- 多线程 / 多 queue 场景下偶发 device lost。
- 特定 draw / dispatch / present 后驱动报告 device reset。

### 不适用

- 画面卡死数秒后恢复（优先看 gpu_hang.md）。
- 应用 CPU 侧崩溃（segfault、空指针）而非 Vulkan 返回 device lost。
- 实例 / 物理设备创建失败（如 `VK_ERROR_INITIALIZATION_FAILED`）。

---

## 1. 现象

- API 调用返回 `VK_ERROR_DEVICE_LOST`，后续该 logical device 上几乎所有操作都返回同样错误。
- 窗口变黑，应用可能被系统终止。
- Validation Layer 在 device lost 前可能已报告大量 hazard / layout / descriptor 错误。
- RenderDoc 在特定命令后无法继续，提示 device lost。
- AGI 抓帧中断，logcat 出现 `vkQueuePresentKHR` 返回 `VK_ERROR_DEVICE_LOST`。
- 崩溃堆栈停在 `vkQueuePresentKHR`、`vkDeviceWaitIdle` 或 `vkQueueSubmit`。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 同步 hazard 导致 GPU 非法访问 | Validation sync 报告 WRITE_AFTER_READ / READ_AFTER_WRITE / WRITE_AFTER_WRITE；device lost 发生在该命令提交后 | Barrier / Image / Buffer |
| P0 | Render pass / pipeline 不匹配 | `VkGraphicsPipelineCreateInfo` 的 render pass 与 bind 时不一致；subpass index 错误 | Pipeline / Render Pass |
| P0 | 越界访问（OOB）buffer / image | descriptor 引用的范围超过 buffer 大小；storage image 写超出 extent | Buffer / Image / Descriptor |
| P1 | Image layout 错误导致 attachment 访问异常 | Validation 报 layout mismatch；device lost 出现在使用 attachment 的 draw | Image / Render Pass |
| P1 | 资源生命周期错误（use-after-free） | command buffer 引用已销毁 buffer / image；Validation 报 invalid handle | Buffer / Image / Command Buffer |
| P1 | 多 queue 缺少 semaphore / ownership transfer | compute 或 transfer queue 写后 graphics queue 读，未同步 | Queue / Semaphore / Barrier |
| P2 | 驱动 bug 或硬件过热 | 同一代码在其他设备正常；仅特定驱动版本复现 | Physical Device / Driver |
| P2 | 超时 watchdog 触发 device reset | 长时间 compute 后返回 device lost 而非 TDR | Compute Pipeline / Driver |

---

## 3. 快速验证路径

1. **抓取 device lost 前的最后一条 Validation 信息**：sync hazard 往往先于 device lost 出现。`[TOOL]`
2. **二分定位触发命令**：把最后几个 draw / dispatch / present 注释，确认最小触发集。`[TOOL]`
3. **检查 pipeline 与 render pass 兼容性**：对比 `VkGraphicsPipelineCreateInfo::renderPass` 和实际 bind 的 render pass。`[SPEC]`
4. **检查 descriptor 范围**：确认 storage buffer / uniform buffer dynamic offset + range 不超过 buffer size。`[SPEC]`
5. **强制 `vkDeviceWaitIdle` 后单帧单 submit**：排除 in-flight 资源竞争。`[HEUR]`
6. **在另一设备 / 驱动版本复测**：区分代码问题与驱动问题。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Logical Device
→ Command Buffer 录制
→ Pipeline (Graphics / Compute)
→ Render Pass / Subpass
→ Descriptor Set / Pipeline Layout
→ Buffer / Image / ImageView
→ Pipeline Barrier / Semaphore / Fence
→ Queue Submit
→ Present
```

逐项检查：

- 触发 device lost 的 `vkQueueSubmit` / `vkQueuePresentKHR` 对应的 command buffer 内容。`[TOOL]`
- Pipeline 创建时使用的 render pass、subpass index 是否与 draw 时一致。`[SPEC]`
- Shader 访问的 descriptor binding / set 是否与 `VkPipelineLayout` 兼容。`[SPEC]`
- Buffer / image 是否仍在生命周期内，是否被提前 `vkDestroyBuffer` / `vkDestroyImage`。`[SPEC]`
- Barrier 的 `srcAccessMask` / `dstAccessMask` / `srcStageMask` / `dstStageMask` 是否覆盖真实访问。`[SPEC]`
- 多 queue 场景下是否有 semaphore 或 event 保证执行顺序。`[SPEC]`
- Present 的 image index 是否与 `vkAcquireNextImageKHR` 返回值一致，是否重复 present。`[SPEC]`

---

## 5. 高频根因

1. Storage buffer / storage image 写越界，破坏相邻资源或驱动元数据。`[SPEC]`
2. `vkCmdDrawIndexed` 的 `indexCount` 或 `vertexOffset` 导致 index buffer 越界。`[SPEC]`
3. Render pass 与 graphics pipeline 不匹配，如 pipeline 为 render pass A subpass 0 创建，却在 render pass B subpass 1 中 bind。`[SPEC]`
4. 同一 image 在 graphics queue 读、compute queue 写，缺少 queue family ownership transfer 或 semaphore。`[SPEC]`
5. Image layout transition 缺失或 `oldLayout` 错误，GPU 以错误 layout 访问 attachment。`[SPEC]`
6. Descriptor 引用的 image view / buffer view 已被销毁，submit 时触发无效 handle。`[SPEC]`
7. In-flight frame 过多，资源在 GPU 仍在使用时被 CPU 回收并重新分配。`[ENGINE]`

---

## 6. 修复方案

### 最小修复

- 在 producer / consumer 之间插入精确的 `vkCmdPipelineBarrier`，覆盖写读双方的 stage 和 access。`[SPEC]`
- 修正 `VkGraphicsPipelineCreateInfo` 中的 `renderPass` 和 `subpass`，确保与 bind 时一致；必要时使用 `VK_NULL_HANDLE` dynamic rendering pipeline 或在 recreate render pass 后重新创建 pipeline。`[SPEC]`
- 检查所有 descriptor 的 range / offset，确保 buffer / image 访问不越界。`[SPEC]`
- 对多 queue 共享资源补充 semaphore 和 queue family ownership transfer。`[SPEC]`

### 稳定修复

- 启用 Validation Layer 全部分支（core、sync、best practice）并清零所有错误后再提交。`[TOOL]`
- 建立资源生命周期跟踪，确保 command buffer retire 前不销毁其引用资源。`[ENGINE]`
- 使用 per-frame ring buffer 管理 in-flight 资源，fence 确认 GPU 完成后再回收。`[ENGINE]`
- 在 swapchain recreate、resize、rotation 时重建依赖旧 swapchain image 的 framebuffer 和 descriptor。`[ENGINE]`

### 工程化修复

- CI 集成 Validation Layer 和 address sanitizer，把 device lost 诱因拦截在开发阶段。`[TOOL]`
- 建立 GPU crash dump 收集机制（如 VK_EXT_device_fault），捕获 device lost 时驱动提供的 fault 信息。`[TOOL]`
- 封装 descriptor / buffer / image 使用范围断言，在 debug build 越界即断言。`[ENGINE]`
- 对多 queue 资源访问建立统一调度器，自动生成 semaphore 和 ownership transfer。`[ENGINE]`

---

## 7. 回归验证

- [ ] Validation Layer 在该场景无 error / warning / sync hazard。
- [ ] 触发 device lost 的最小命令连续运行 1000 次无异常。
- [ ] RenderDoc / AGI 能完整抓帧并回放。
- [ ] 多 queue / 多线程恢复后不再 device lost。
- [ ] resize / rotation / pause-resume 后不再 device lost。
- [ ] 不同 GPU 厂商（NVIDIA / AMD / Intel / Adreno / Mali）均通过测试。
- [ ] 如启用 `VK_EXT_device_fault`，确认无新增 fault 报告。

---

## 8. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`

---

## 9. 工具证据

### Validation Layer

- 关注 device lost 前最后一条 `SYNC-HAZARD-*` 报告及 VUID。`[TOOL]`
- 关注 `VUID-vkCmdDraw-*-None-*`、index buffer 范围、`vertexInput` 相关错误。`[TOOL]`
- 关注 `VUID-vkQueueSubmit-pCommandBuffers-00064`（command buffer 状态无效）。`[TOOL]`
- 关注 `VUID-vkCmdBindPipeline-pipelineBindPoint-00779` 等 pipeline / render pass 兼容性错误。`[TOOL]`
- 关注 descriptor / image layout / buffer range 相关 VUID。`[TOOL]`

### RenderDoc

- 查看触发 device lost 的 draw / dispatch 的 pipeline state 与 render pass 是否匹配。`[TOOL]`
- 检查 descriptor 绑定的 buffer / image 是否有效，range 是否合理。`[TOOL]`
- 检查 mesh 数据、index buffer、vertex buffer 是否越界。`[TOOL]`
- 查看 event browser 中 device lost 发生的精确命令。`[TOOL]`

### AGI / Android

- 查看 `vkQueuePresentKHR` / `vkQueueSubmit` 是否返回 `VK_ERROR_DEVICE_LOST`。`[TOOL]`
- 检查 GPU counter 是否在某一命令后归零。`[TOOL]`
- 查看 framebuffer / render pass 状态是否与 pipeline 兼容。`[TOOL]`

### logcat

- 搜索 `vkQueuePresentKHR`、`VK_ERROR_DEVICE_LOST`、`device lost`、`gpu fault`。`[ANDROID]`
- 查看 `Adreno` / `Mali` 驱动日志是否有 `gpu fault`、page fault、timeout 信息。`[ANDROID]`
- 检查 Surface / ANativeWindow 是否在 device lost 前后被异常销毁。`[ANDROID]`

---

## 10. Android 分支

Android 上 device lost 常与 Surface / ANativeWindow / Swapchain 生命周期强相关，额外检查：

1. **Surface 有效性前提**：确认 device lost 时 `ANativeWindow` 仍有效；`surfaceDestroyed` 后必须停止向该 window 提交命令。`[ANDROID]`
2. **Swapchain 重建完整性**：`vkQueuePresentKHR` 返回 `SUBOPTIMAL` / `OUT_OF_DATE` 后，应等待 GPU idle、销毁旧 swapchain 和 framebuffer，再基于新 `ANativeWindow` 创建新 swapchain。`[SPEC]`
3. **in-flight 资源对齐**：pause / resume 或 rotation 时，确保所有引用旧 swapchain image 的 command buffer、semaphore、fence 已 retire，避免提交到已销毁 swapchain。`[ENGINE]`
4. **深度 / offscreen image 重建**：rotation 后按新 extent 重建 depth attachment 和 offscreen image，并更新引用它们的 descriptor / framebuffer。`[ENGINE]`
5. **present image 索引正确性**：`vkAcquireNextImageKHR` 返回的 image index 必须与 `vkQueuePresentKHR` 使用的一致，避免重复 present 或 present 未获取的 image。`[SPEC]`
6. **低端设备内存压力**：Android 设备内存紧张时，后台回收 GPU 资源可能表现为 device lost；检查 `onTrimMemory` 回调后是否过度释放了 GPU 资源。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - 返回 `VK_ERROR_DEVICE_LOST` 的具体 API 调用（`vkQueueSubmit` / `vkQueuePresentKHR` / `vkDeviceWaitIdle` 等）。
   - device lost 前的完整 Validation Layer 日志（含 sync 分支）。
   - RenderDoc capture（如果能抓到中断点）。
   - AGI capture 及 logcat。
   - 触发命令附近的 command buffer 录制代码。
   - pipeline 创建时的 render pass / subpass 信息。
   - descriptor set layout / update / bind 代码。
   - buffer / image 创建参数及生命周期管理代码。
   - 设备型号、GPU、驱动版本、Android 版本。
   - 是否多 queue、是否多线程录制。
3. 给出最小复现路径：单 queue + 关闭多线程 + 最小 draw。
4. 标注当前判断属于：
   - `[SPEC]` 若已确认违反 Vulkan 规范（如 pipeline / render pass 不匹配、OOB）。
   - `[TOOL]` 若 Validation / RenderDoc / AGI 已给出明确证据。
   - `[ENGINE]` 若基于生命周期或 in-flight 管理推断。
   - `[HEUR]` 若尚未拿到工具证据，仅为可能性排序。
   - `[ANDROID]` 若涉及 Surface / ANativeWindow / Swapchain 生命周期。

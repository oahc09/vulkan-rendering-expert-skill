# Case: Per Frame Resource Design

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / Per-frame / Ring-buffer / Command Buffer |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 多 frame-in-flight（2～3）场景下，画面偶发撕裂、闪烁或资源内容“串帧”。
- 偶发 Validation Layer 报 `SYNC-HAZARD`：write-after-read 或 read-after-write。
- 关闭 triple buffering 改用单缓冲后问题消失，但帧率下降。
- 某些 dynamic uniform buffer 的内容被下一帧覆盖，导致当前帧绘制使用了错误的 transform / material 参数。

---

## 2. 初始上下文

- 平台：通用，常见于 Windows / Linux / Android 多 frame-in-flight 渲染器。
- 使用 2～3 个 frame-in-flight，每个 frame 拥有独立的 command buffer、fence、semaphore。
- Uniform buffer / storage buffer 使用 ring buffer 管理，按 frame 偏移写入。
- Descriptor set 按 frame 分配，或全局共享。
- 渲染线程与 GPU 异步，CPU 持续录制第 N+1/N+2 帧的命令，GPU 正在执行第 N 帧。
- 未明确区分“CPU 帧索引”与“GPU 完成帧索引”。

---

## 3. 初始误判

最初容易怀疑：

```text
Fence / semaphore 信号错误导致 CPU 提前开始下一帧；
Command buffer 被错误 reset 后仍在 GPU 上执行；
Descriptor set 分配不足导致复用了未完成的 set；
GPU 没有正确等待 previous frame 完成；
Ring buffer 大小不够。
```

但检查 fence wait 逻辑后，CPU 确实等待了对应 frame 的 fence。最终发现是 ring buffer / descriptor / command buffer 的生命周期与 frame-in-flight 索引没有严格一一对应，导致资源在 GPU 仍在使用时被复用 `[ENGINE]`。

---

## 4. 排查路径

1. 确认 frame-in-flight 数量、当前 CPU frame index、当前 GPU completed frame index。
2. 检查每帧的 fence wait：是否等待的是“本帧要复用的资源对应的 fence”，还是“某个固定 fence”。
3. 检查 command buffer 的 reset 时机：是否在 fence signal 之后 reset。
4. 检查 uniform buffer ring buffer 的 offset 计算：是否按 frame-in-flight 数量取模，并保证写入区间不重叠。
5. 检查 descriptor set 是否按 frame 划分，还是全局 pool 任意复用。
6. 用 Validation Layer 的 synchronization 检查定位具体 hazard。
7. 用 RenderDoc 多帧 capture 对比，确认 hazard 出现在哪两个 frame 之间。

---

## 5. 关键证据

### Validation Layer

- `SYNC-HAZARD-WRITE-AFTER-READ`：CPU 写入的 buffer 仍在被 GPU 读取。
- `SYNC-HAZARD-READ-AFTER-WRITE`：CPU 读取的 buffer 仍在被 GPU 写入。
- `VUID-vkResetCommandBuffer-commandBuffer-00045`：reset 的 command buffer 仍在 pending execution `[SPEC]`。

### RenderDoc / AGI

- RenderDoc：第 N 帧的 uniform buffer 内容与提交时不一致，出现第 N+1 帧的数据。
- RenderDoc：同一 `VkCommandBuffer` handle 在 fence 未 signal 时被 reset 并重新录制。
- AGI：GPU 时间线上第 N 帧与第 N+2 帧的命令存在资源访问重叠。
- 关键 resource：per-frame command buffer、uniform buffer ring buffer、per-frame descriptor set、frame fence。

### Log / Code

- 错误代码模式：

```text
// 错误：只用单个 fence，没有按 frame-in-flight 索引等待
vkWaitForFences(device, 1, &globalFence, VK_TRUE, UINT64_MAX);
writeUBO(frameIndex % 3);   // 可能覆盖 GPU 正在使用的区域
vkResetCommandBuffer(cmd[frameIndex % 3], 0);
```

- 正确模式：

```text
uint32_t frameIndex = currentFrame % FRAME_IN_FLIGHT;
vkWaitForFences(device, 1, &frameFence[frameIndex], VK_TRUE, UINT64_MAX);
vkResetFences(device, 1, &frameFence[frameIndex]);
writeUBO(frameIndex);         // 该区域只属于本 CPU 帧
recordCmdBuffer(cmd[frameIndex]);
submit(cmd[frameIndex], signalFence = frameFence[frameIndex]);
```

---

## 6. 根因

根因：per-frame 资源（command buffer、uniform buffer、descriptor set）没有与 frame-in-flight 索引严格绑定，CPU 在 fence 未 signal 时复用了 GPU 仍在访问的资源，导致数据竞争和视觉异常 `[ENGINE]`。

---

## 7. 修复方案

### 最小修复

- 为每个 frame-in-flight 索引分配独立的 command buffer、fence、semaphore。
- 将 uniform buffer ring buffer 按 `FRAME_IN_FLIGHT` 数量分段，每段只由对应索引的帧写入。
- 等待 fence 后再 reset command buffer 和写入 per-frame buffer。
- 确保 descriptor set 按 frame 索引分配，或全局缓存的 set 在写入前等待所有使用方完成。

### 稳定修复

- 引入 `FrameContext` 结构，封装单帧所需的所有资源：command buffer、fence、semaphore、UBO offset、descriptor set。
- 使用 `FrameResourcePool` 按 frame index 管理资源，禁止跨帧复用。
- 统一 current frame index、swapchain image index、frame-in-flight index 的命名与计算。
- 对 dynamic uniform buffer 使用 `vkCmdBindDescriptorSets` 的 `pDynamicOffsets` 参数，offset 从 `FrameContext` 获取。

### 工程化修复

- 在 debug 构建中assert：任何 per-frame 资源的写入必须在对应 frame fence signal 之后。
- 引入资源使用范围追踪：记录每块 UBO / descriptor 的 GPU 使用区间，自动延迟回收。
- 使用 timeline semaphore（`VK_KHR_timeline_semaphore`）替代 binary semaphore + fence 组合，简化多 frame-in-flight 同步 `[SPEC]`。
- CI 中加入 synchronization validation，捕获 write-after-read / read-after-write hazard。

---

## 8. 修复后验证

- [ ] Validation clean（包括 synchronization validation）。
- [ ] 多帧运行无撕裂、闪烁、串帧。
- [ ] RenderDoc 中每帧 uniform buffer 内容与提交时一致。
- [ ] Frame-in-flight 增加到 3 后问题不复现。
- [ ] 窗口 resize / Android rotation 后 per-frame 资源仍能正确重建。
- [ ] 长时间运行（>30 分钟）无资源竞争导致的偶发 crash。

---

## 9. 经验抽象

Frame-in-flight 不是“开几个 buffer”那么简单，而是要求 CPU 侧资源池与 GPU 完成进度严格对齐。核心规则：

```text
谁写入、谁等待、谁消费，必须按 frame-in-flight 索引闭环。
当前 CPU 帧能使用的资源范围 = 上一轮同索引帧的 fence 已 signal。
Command buffer 的 reset 和录制必须在 fence wait 之后。
```

混淆 `swapchain image index` 和 `frame-in-flight index` 是常见的根因之一 `[ENGINE]`。

---

## 10. 预防规则

1. 每个 frame-in-flight 索引必须拥有独立的 command buffer、fence、semaphore、UBO 段。
2. 禁止在 frame fence 未 signal 时 reset command buffer 或写入 per-frame buffer。
3. 统一命名规范，明确区分 `currentFrame`、`swapchainImageIndex`、`frameInFlightIndex`。
4. Per-frame descriptor set 必须按 frame-in-flight 索引分配，禁止跨帧复用未完成的 set。
5. Uniform buffer ring buffer 的大小必须按 `FRAME_IN_FLIGHT × perFrameSize` 计算，禁止重叠。
6. 新增 per-frame 资源时，必须声明其生命周期和同步边界。
7. 在 CI 中开启 synchronization validation 并持续回归。
8. 优先使用 timeline semaphore 简化多 frame-in-flight 状态管理。

---

## 11. 关联 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`

---

## 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`

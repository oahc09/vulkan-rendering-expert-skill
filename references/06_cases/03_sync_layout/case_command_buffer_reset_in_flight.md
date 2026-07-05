# Case: Command Buffer Reset While In Flight

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 同步 / Command Buffer Lifetime |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

App 运行一段时间后随机 crash、device lost 或画面撕裂；Validation Layer 报 command buffer 仍在 pending 状态却被 reset / free。问题往往在多 frame-in-flight、高帧率或 CPU 端录制 command buffer 较慢时出现。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用多 frame-in-flight（通常 2~3 帧）。
- 每帧复用同一个 command buffer 或同一个 command pool。
- 在 frame begin 时调用 `vkResetCommandBuffer` 或 `vkResetCommandPool`。
- 可能使用单个 fence 管理多帧，或未正确等待 fence 就开始录制下一帧。

---

## 3. 初始误判

最初容易怀疑：

```text
GPU 挂起或驱动 bug；
内存越界或 buffer 被覆盖；
synchronization hazard 导致读写出错；
command buffer 录制本身有非法命令；
swapchain out of date 引发 device lost。
```

但 RenderDoc 中 command buffer 内容正常，问题只在复用或 reset 时出现。最终发现是 command buffer 或 pool 在被 GPU 执行期间就被 reset 或重新录制。

---

## 4. 排查路径

1. 检查 Validation Layer 错误信息中的 VUID 和 object handle。
2. 确认每帧 command buffer / pool 的 reset 时机。
3. 检查 fence 等待逻辑：是否只 wait 当前帧的 fence，是否忽略了 `vkWaitForFences` 的返回值。
4. 检查是否存在“单 fence 轮询”模式：一帧结束后直接 wait 同一 fence 然后开始下一帧，而没有按 frame-in-flight 索引区分。
5. 检查 `vkQueueSubmit` 的 fence 参数是否与当前帧 command buffer 对应。
6. 检查是否有其他线程提前 reset 了 command buffer。
7. 在 `vkResetCommandBuffer` / `vkResetCommandPool` 前加断言：fence 必须已 signaled。

---

## 5. 关键证据

### Validation Layer

- 典型 VUID（`[SPEC]`）：
  - `VUID-vkResetCommandBuffer-commandBuffer-00045`：command buffer 不能处于 pending 状态时被 reset。
  - `VUID-vkResetCommandPool-commandPool-00040`：command pool 不能有任何处于 pending 状态的 command buffer 时被 reset。
  - `VUID-vkFreeCommandBuffers-commandBuffer-00047`：不能 free 处于 pending 或 recording 状态的 command buffer。
- Message 通常会指出具体 command buffer handle 和产生该 buffer 的 frame。

### RenderDoc / AGI

- 观察到：
  - 同一帧 capture 中 command buffer 内容在渲染过程中发生变化。
  - 或某帧的 command buffer 在 Event Browser 中显示为不完整 / 被截断。
  - GPU 时间线显示 command buffer 被提交两次但内容不同。
- 关键 resource：command buffer、command pool、frame fence、frame-in-flight index。

### Log / Code

- 返回值：
  - `vkQueueSubmit` 返回 `VK_SUCCESS`。
  - `vkWaitForFences` 被传入错误 fence 或 timeout 为 0 导致未真正等待。
- 生命周期日志：
  - frame N 提交 command buffer 并使用 fence[N % 2]。
  - frame N+1 未等待 fence[N % 2] 就直接 reset command buffer。
- 关键代码：

```text
// 错误示例：单 fence 轮询，未按 frame-in-flight 索引等待
void renderFrame() {
    vkWaitForFences(device, 1, &globalFence, VK_TRUE, UINT64_MAX);
    vkResetFences(device, 1, &globalFence);     // 只 reset 一个全局 fence
    vkResetCommandBuffer(cmdBuffer, 0);          // 可能上一帧仍在 GPU 执行
    recordCommands(cmdBuffer);
    vkQueueSubmit(queue, 1, &submitInfo, globalFence);
}
```

---

## 6. 根因

根因：command buffer 或 command pool 在 GPU 仍执行其已提交命令（pending 状态）时被 reset、重新录制或释放，破坏了命令缓冲区的生命周期约束。

---

## 7. 修复方案

### 最小修复

- 在 `vkResetCommandBuffer` / `vkResetCommandPool` 之前，显式 `vkWaitForFences` 等待该 command buffer 关联的 fence 进入 signaled 状态。
- 若使用多 frame-in-flight，确保每个 frame index 有独立的 command buffer 和 fence，reset 前只 wait 当前帧对应的 fence。
- 将 `vkResetFences` 放在确认 fence 已 signaled 之后，并确保 fence 与当前帧 command buffer 匹配。

### 稳定修复

- 为每个 frame-in-flight 槽位维护独立的 command buffer、command pool 和 fence。
- 封装 FrameResource 结构，reset 前自动检查 `vkGetFenceStatus` 或 `vkWaitForFences`。
- 禁止跨帧共享同一个 command buffer；每帧从对应 pool 重新分配或 reset。

### 工程化修复

- 引入 command buffer lifetime tracker，记录每个 command buffer 的 submit fence 和 signaled 状态。
- 使用 RAII wrapper：command buffer 对象析构或 reset 时自动断言 fence signaled。
- 在 CI 中加入 GPU stress test，长时间运行以检测 frame-in-flight 生命周期问题。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中每帧 command buffer 内容完整且稳定。
- [ ] 长时间运行（30 分钟以上）无 crash 或 device lost。
- [ ] 高帧率 / CPU 满载场景下不复现。
- [ ] 多 frame-in-flight 下 fence 等待无超时。
- [ ] resize / pause / resume 后 command buffer 生命周期仍正确。

---

## 9. 经验抽象

Command buffer 的生命周期与 fence 强绑定。任何 reset / free 操作前必须确认：

```text
command buffer 已结束录制
→ 已提交到 queue
→ 关联 fence 已 signaled
→ 才能 reset / reuse / free
```

单 fence 管理多帧或忽略 `vkWaitForFences` 返回值是多 frame-in-flight 场景下最常见的生命周期错误。

---

## 10. 预防规则

1. 每帧必须使用独立的 command buffer 和 fence，禁止跨帧复用未等待的资源。
2. `vkResetCommandBuffer` / `vkResetCommandPool` 前必须等待对应 fence signaled。
3. 不要把 `vkWaitForFences` 的 timeout 设为 0 来“轮询”，除非有明确的回退逻辑。
4. 封装 frame resource 管理，使 reset / free 操作自动校验 fence 状态。
5. 新增 frame-in-flight 逻辑时，必须 review 所有 command buffer / pool / fence 的配对关系。

---

## 11. 关联 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`

# Workflow: Manage Frame Resources

## 0. 适用范围

### 适用

- 管理 frame-in-flight 资源：per-frame command buffer、fence、semaphore、uniform buffer、staging buffer、query pool 等。
- 实现 ring index 轮询，保证 CPU 不覆盖 GPU 正在使用的资源。
- 处理 swapchain recreate 时的资源清理与重建路径。

### 不适用

- 单缓冲、非实时渲染或离线渲染。
- 资源生命周期完全由外部引擎托管、无需自定义 frame ring 的场景。
- 不使用 swapchain 的 headless / compute-only 程序（部分概念可参考，但本节以 graphics frame loop 为主）。

---

## 1. 任务目标

建立稳定的 per-frame 资源管理：

```text
Frame N-2        Frame N-1        Frame N
  (GPU)            (GPU/CPU)        (CPU record)
   fence            fence            fence
   cmd buffer       cmd buffer       cmd buffer
   UBO slot         UBO slot         UBO slot
   semaphore        semaphore        semaphore
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- Frame-in-flight 数量（通常 2~3，受 `minImageCount` 与 latency 需求影响）。
- 需要 per-frame 的资源类型：command buffer、UBO、image、fence、semaphore、query pool 等。
- 是否使用 single command pool per frame 或 resettable pool。
- Swapchain recreate 策略：in-place、full teardown、partial rebuild。
- 是否使用 dynamic rendering 或 render pass。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] swapchain recreate 路径已有基础处理。
- [ ] command pool 支持 `VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT` 或按 frame 分配。
- [ ] fence / semaphore 创建逻辑可用。
- [ ] 已确认 `minImageCount` 与期望 frame-in-flight 数量匹配。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Swapchain
→ Frame Index (acquire image index)
→ Per-Frame Ring Index (mod frameInFlight)
→ VkFence (frame complete)
→ VkCommandPool / VkCommandBuffer
→ Per-Frame Buffer / Image
→ VkSemaphore (image acquired, render complete)
→ Queue Submit
→ Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| per-frame command pool | `VkCommandPool` | 录制当前帧命令 | per-frame | 否（通常） |
| per-frame command buffer | `VkCommandBuffer` | 当前帧录制 | per-frame | 否 |
| per-frame fence | `VkFence` | GPU 完成信号 | per-frame | 否 |
| image acquired semaphore | `VkSemaphore` | acquire 信号 | per-frame | 否 |
| render complete semaphore | `VkSemaphore` | 渲染完成信号 | per-frame | 否 |
| per-frame UBO | `VkBuffer` | 当前帧常量 | per-frame | 否 |
| per-frame staging | `VkBuffer` | 当前帧上传 | per-frame | 否 |
| per-frame color/depth | `VkImage` | 当前帧中间输出 | per-frame | 是（若尺寸依赖 swapchain） |

---

## 6. Pipeline / Descriptor 设计

本工作流主要涉及资源管理，descriptor 设计按资源类型复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame UBO | Vertex / Fragment / Compute |
| set=N,binding=M | `COMBINED_IMAGE_SAMPLER` | per-frame image view | Fragment / Compute |

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU record | per-frame command buffer | `vkBeginCommandBuffer` / `vkEndCommandBuffer` | queue submit |
| queue submit | per-frame fence | `vkQueueSubmit` with fence | CPU `vkWaitForFences` |
| acquire semaphore | swapchain image | `VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT` wait | render begin |
| render complete semaphore | swapchain image | `VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT` / present | `vkQueuePresentKHR` |
| previous frame GPU | per-frame UBO / staging | fence signaled | CPU reuse same ring slot |

必须说明：

- `vkAcquireNextImageKHR` 返回的 `imageIndex` 是 swapchain image index，不一定是 ring index；frame-in-flight 使用独立的 `currentFrame % frameInFlight` [SPEC]。
- acquire wait stage 覆盖 swapchain image 的最早访问及 transition；直接绘制 color attachment 常用 `COLOR_ATTACHMENT_OUTPUT_BIT`，transfer / compute 首次访问应选对应 stage [SPEC]。
- fence 等待后必须 `vkResetFences` 再 submit 下一帧使用同一 fence [SPEC]。
- command buffer 复用前可 `vkResetCommandBuffer` 或 `vkResetCommandPool` [SPEC]。

---

## 8. 实现步骤

1. **确定 frame-in-flight 数量**：通常 2~3；移动端 2 可降低 latency，PC 3 可提升吞吐 [HEUR]。
2. **创建 per-frame fence**：`VK_FENCE_CREATE_SIGNALED_BIT`，初始状态为 signaled，第一帧 `vkWaitForFences` 不阻塞 [ENGINE]。
3. **创建 semaphore**：`imageAcquiredSemaphore` 按 frame slot 创建；`renderFinishedSemaphore` 按 swapchain image 创建，submit fence 不证明 present 对 semaphore 的使用结束。
4. **创建 per-frame command pool**：`VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT`，每帧一个 pool 可简化 reset；或单 pool + `vkResetCommandBuffer` [SPEC]。
5. **分配 per-frame command buffer**：从对应 pool 分配 primary command buffer。
6. **创建 per-frame 资源**：UBO、staging buffer、query pool 等按 frameInFlight 数量分配。
7. **Frame loop 流程**：
   - `vkWaitForFences(perFrameFence[currentFrame], TRUE, timeout)` [SPEC]
   - `vkAcquireNextImageKHR(..., imageAcquiredSemaphore[currentFrame], ...)`
   - OUT_OF_DATE 标记重建并返回；TIMEOUT / NOT_READY 跳过；SUCCESS / SUBOPTIMAL 继续，后者标记稍后重建；其他错误进入恢复
   - 重置并录制 command buffer
   - 录制成功且确定会提交后 `vkResetFences(perFrameFence[currentFrame])` [ENGINE]
   - `vkQueueSubmit(..., wait=imageAcquiredSemaphore[currentFrame], signal=renderFinishedSemaphore[imageIndex], fence=perFrameFence[currentFrame])`
   - 检查 submit 返回值；失败时进入恢复，不能等待本次未提交的 fence
   - `vkQueuePresentKHR(..., wait=renderFinishedSemaphore[imageIndex])`
   - `currentFrame = (currentFrame + 1) % frameInFlight`
8. **处理重建**：成功 acquire（含 SUBOPTIMAL）后先完成信号消费与 image 处理，再进入重建；OUT_OF_DATE 不继续 submit。其他中途退出路径也必须处理已取得的 image / acquire 信号 [SPEC][ENGINE]。
9. **Recreate 路径**：
   - 等待引用旧渲染资源的提交完成；旧 present semaphore / swapchain 另按 present fence 或官方样例退役策略管理 [SPEC]
   - 销毁尺寸相关的 image / image view / framebuffer / depth image
   - 重建 swapchain
   - 重建尺寸相关资源
   - 重置 `currentFrame` 到 0
10. **销毁路径**：
   - 等待所有相关提交完成，并确认 presentation 资源可释放；WaitIdle 不能单独证明后者
    - 按 `command buffer → command pool → fence → semaphore → per-frame buffer/image → memory` 顺序销毁 [ENGINE]
11. **Ring index 管理**：per-frame 数组按 frameInFlight 分配；swapchain image 与 renderFinishedSemaphore 数组按实际 imageCount 分配，用 imageIndex 索引，不能混为同一组 [ENGINE]。
12. **错误处理**：acquire / present 返回 `OUT_OF_DATE` 时，标记 recreate 标志，不直接 crash [ANDROID]。

依据：[帧循环 API 卡片](../../03_api_manual/03_command_buffer/frames_in_flight.md)、[present semaphore 复用](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)、[swapchain 退役](../../03_api_manual/02_surface_swapchain/swapchain_recreate.md)。

---

## 9. Android 注意点

- `ANativeWindow` 创建后由平台层跟踪 `surfaceCreated` / `surfaceChanged` / `surfaceDestroyed`；销毁后不得再访问该Surface的失效资源。共享世界的独立compute按owner/可见性政策继续或暂停，不禁止其他输出的合法提交 [ANDROID][ENGINE]。
- pause / resume 时通常销毁 swapchain 并停止 render thread；resume 后重新创建 surface 与 swapchain。
- rotation / resize 会改变 `ANativeWindow` 尺寸，触发 `VK_ERROR_OUT_OF_DATE_KHR` 或 `VK_SUBOPTIMAL_KHR`，必须重建 swapchain 与尺寸相关资源 [ANDROID]。
- `extent.width == 0 || extent.height == 0` 时暂停渲染循环，等待 surface 恢复非零尺寸 [ANDROID]。
- render thread 状态机：`RUNNING → PAUSED → RESUMED → RUNNING`，在 `PAUSED` 状态不调用 `vkAcquireNextImageKHR`。
- AGI / logcat 验证：检查 `vkQueuePresentKHR` 返回码、fence 等待时间、每帧资源索引。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkAcquireNextImageKHR-*`、`VUID-vkQueuePresentKHR-*`、`VUID-vkQueueSubmit-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见连续多帧的 submit、present、semaphore/fence 状态 [TOOL]。
- [ ] 截图 / 帧率：无 tearing、无 flickering、frame time 稳定。
- [ ] logcat（Android）：
  - `adb logcat -s vulkan` 无 validation error；
  - 自定义 tag 输出 `acquireImageIndex`、`currentFrame`、`fence status`。
- [ ] 性能指标：
  - CPU 端 `vkWaitForFences` 等待时间合理（不过长说明 GPU 并行度低，过短可能未正确等待）；
  - GPU frame time 在 AGI 中稳定；
  - 无 redundant fence/semaphore [HEUR]。
- [ ] resize / pause / resume / rotation 后正常渲染。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **fence 未 reset**：同一 fence 重复 submit 触发 validation error [SPEC]。
2. **frame index 与 swapchain imageIndex 混淆**：用 imageIndex 索引 per-frame UBO，导致数据错位 [ENGINE]。
3. **semaphore stage 错误**：wait stage 用 `TOP_OF_PIPE`，acquire 信号实际在 `COLOR_ATTACHMENT_OUTPUT` 等待 [SPEC]。
4. **recreate 时未等待 GPU idle**：销毁旧 swapchain image 时仍被 GPU 使用，触发 device lost [TOOL]。
5. **command buffer 未 reset 就录制**：旧命令残留或 validation error [SPEC]。
6. **fence 初始未 signaled**：第一帧 `vkWaitForFences` 永久阻塞 [ENGINE]。
7. **present 与 submit 使用不同 semaphore**：present 等待的 semaphore 未被 submit signal [SPEC]。
8. **Android surface destroy 后提交仍引用已销毁资源**：有生命周期风险；独立compute与其他有效输出不因该Surface销毁自动失效 [ANDROID][ENGINE]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- frame-in-flight 数量与 `minImageCount`。
- `vkAcquireNextImageKHR` 返回的 imageIndex 序列。
- fence / semaphore 创建参数。
- recreate 触发条件与处理顺序。
- Validation Layer 完整报错。
- Android lifecycle 日志（surfaceCreated/Changed/Destroyed、pause/resume）。

<a id="simulation-snapshot-retirement"></a>
## 仿真快照的全消费者退休（C4）

输入：world/topology/resource generation、每资源writer/readers、实际提交及完成token、取消/销毁请求；输出：可发布/可重用/可释放的明确集合。适用共享world多view/Surface和多帧在途，也适用headless模拟；不把模拟tick、frame slot和swapchain imageIndex混为同一索引。[ENGINE]

| 资源 | writer → readers | 最早重用/销毁条件 |
|---|---|---|
| state A/B | tick积分/约束→后续solver或tick | 最后读取与写入依赖满足；A/B名字不是安全证明 |
| λ/constraint scratch | solver→同子步后续iteration | 当前子步所有引用完成；每子步初始化非每iteration清零 |
| contribution/adjacency | constraint独占writer→particle gather | gather及相关引用完成，拓扑新代需新邻接 |
| height/velocity | stencil输出→下一更新/normal生成 | 所有读者结束，旧/新场不可无证明别名 |
| render snapshot | 发布pass→view/shadow/reflection/可选AS | 发布完成且**所有实际消费者**的提交完成 |
| previous-render snapshot | 输出历史owner→motion vectors | 该输出历史消费完结；其他输出仍引用则不可释放 |
| feedback/readback | GPU统计/copy→CPU | 真实completion，GPU→host依赖和必要non-coherent invalidate |

复用既有allocator/descriptor/retirement manager，给snapshot登记消费者并在提交时关联queue与完成值。不同timeline的数值不可直接比较取max；等待每个token或经明确join提交归并。关闭view阻止新引用，取消未提交引用并确认不会再提交；已提交工作不能因取消而假装完成。新代资源准备就绪再切换，旧代延迟退休；失效回调按owner/generation拒绝发布。[ENGINE]

两个state ping-pong不自动覆盖三帧在途/双view；可用独立snapshot ring、只读引用或有证明的串行等待策略，容量由完整使用图和延迟预算决定。host写/descriptor更新也必须等待对应引用安全；barrier不是CPU提前覆写许可证。读回只取调试样本/周期统计，避免每帧全顶点同步。VkMappedMemoryRange的invalidate按nonCoherentAtomSize对齐且不越allocation范围。

Surface销毁只退休该输出，不自动停止其他view或使device/compute queue失效；仍不得访问已失效Surface相关资源。共享world是否暂停由可见性政策决定，present semaphore/swapchain退休独立遵守既有规则。设备lost进入既有恢复，不伪造完成信号回收后继续使用旧对象。

最小验证：主view完成而shadow未完成不可复用；两view其一暂停/销毁另一个继续；topology重建中旧快照仍安全；取消未提交与已提交分别测试；延迟readback；state ring耗尽按声明等待/复用最后完整快照而非覆盖。host模拟token只证明合同，不替代Vulkan多队列执行。关联hard_rules 4/6/15/17，依赖表见 [交接](../03_compute_workflows/compute_to_graphics_sync.md#simulation-render-handoff)，API见 [buffer](../../03_api_manual/04_buffer_image_memory/buffer.md)、[memory](../../03_api_manual/04_buffer_image_memory/memory_allocation.md)。权威：[同步与host访问](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc)。

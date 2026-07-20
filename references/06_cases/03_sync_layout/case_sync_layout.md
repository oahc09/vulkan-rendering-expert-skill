# Cases: Sync / Layout

> 合并自 4 个原 case 文件。关键词: compute-barrier, transfer-transition, frame-resource, command-buffer-reset

---

## Case: Command Buffer Reset While In Flight

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 同步 / Command Buffer Lifetime |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

App 运行一段时间后随机 crash、device lost 或画面撕裂；Validation Layer 报 command buffer 仍在 pending 状态却被 reset / free。问题往往在多 frame-in-flight、高帧率或 CPU 端录制 command buffer 较慢时出现。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用多 frame-in-flight（通常 2~3 帧）。
- 每帧复用同一个 command buffer 或同一个 command pool。
- 在 frame begin 时调用 `vkResetCommandBuffer` 或 `vkResetCommandPool`。
- 可能使用单个 fence 管理多帧，或未正确等待 fence 就开始录制下一帧。

---

### 3. 初始误判

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

### 4. 排查路径

1. 检查 Validation Layer 错误信息中的 VUID 和 object handle。
2. 确认每帧 command buffer / pool 的 reset 时机。
3. 检查 fence 等待逻辑：是否只 wait 当前帧的 fence，是否忽略了 `vkWaitForFences` 的返回值。
4. 检查是否存在“单 fence 轮询”模式：一帧结束后直接 wait 同一 fence 然后开始下一帧，而没有按 frame-in-flight 索引区分。
5. 检查 `vkQueueSubmit` 的 fence 参数是否与当前帧 command buffer 对应。
6. 检查是否有其他线程提前 reset 了 command buffer。
7. 在 `vkResetCommandBuffer` / `vkResetCommandPool` 前加断言：fence 必须已 signaled。

---

### 5. 关键证据

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

### 6. 根因

根因：command buffer 或 command pool 在 GPU 仍执行其已提交命令（pending 状态）时被 reset、重新录制或释放，破坏了命令缓冲区的生命周期约束。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中每帧 command buffer 内容完整且稳定。
- [ ] 长时间运行（30 分钟以上）无 crash 或 device lost。
- [ ] 高帧率 / CPU 满载场景下不复现。
- [ ] 多 frame-in-flight 下 fence 等待无超时。
- [ ] resize / pause / resume 后 command buffer 生命周期仍正确。

---

### 9. 经验抽象

Command buffer 的生命周期与 fence 强绑定。任何 reset / free 操作前必须确认：

```text
command buffer 已结束录制
→ 已提交到 queue
→ 关联 fence 已 signaled
→ 才能 reset / reuse / free
```

单 fence 管理多帧或忽略 `vkWaitForFences` 返回值是多 frame-in-flight 场景下最常见的生命周期错误。

---

### 10. 预防规则

1. 每帧必须使用独立的 command buffer 和 fence，禁止跨帧复用未等待的资源。
2. `vkResetCommandBuffer` / `vkResetCommandPool` 前必须等待对应 fence signaled。
3. 不要把 `vkWaitForFences` 的 timeout 设为 0 来“轮询”，除非有明确的回退逻辑。
4. 封装 frame resource 管理，使 reset / free 操作自动校验 fence 状态。
5. 新增 frame-in-flight 逻辑时，必须 review 所有 command buffer / pool / fence 的配对关系。

---

### 11. 关联 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`


---

## Case: Compute To Fragment Missing Barrier

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Synchronization / Image Layout |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Compute shader 写入 storage image 后，后续 fullscreen fragment shader 采样该 image，画面显示为黑色或旧内容。  
Compute dispatch 在 RenderDoc 中存在，storage image 似乎有写入，但 fragment pass 读取结果不稳定。

---

### 2. 初始上下文

- 使用 compute pipeline 生成图像。
- 输出资源是 `VkImage`，带有 `STORAGE` 和 `SAMPLED` usage。
- 后续 graphics pipeline 通过 sampled image 读取。
- 两个 pass 在同一个 command buffer 或同一个 queue 中执行。
- 可能使用 `VK_KHR_synchronization2` 或传统 barrier。

---

### 3. 初始误判

最初容易怀疑：

```text
compute shader 没执行；
dispatch group count 错；
descriptor 没绑定；
fragment shader 采样坐标错误。
```

但 RenderDoc 显示 compute dispatch 已执行，storage image 有内容。  
问题出在 compute 写之后没有建立 graphics 读的内存可见性与 layout transition。

---

### 4. 排查路径

1. 检查 `vkCmdDispatch` 是否存在。
2. 检查 compute pipeline 和 descriptor 是否绑定。
3. 检查 storage image 是否有 `STORAGE` usage。
4. 检查 shader 写入坐标是否覆盖目标区域。
5. 检查 compute pass 后是否有 barrier。
6. 检查 image layout 是否从 `GENERAL` 转到 sampled read layout。
7. 检查 descriptor imageLayout 是否与 fragment shader 采样 layout 一致。
8. 用 sync validation 检查 shader write → shader read hazard。

---

### 5. 关键证据

### Validation Layer

可能出现：

- synchronization hazard
- image layout mismatch
- descriptor imageLayout mismatch

### RenderDoc / AGI

观察到：

- compute dispatch 存在。
- storage image 在 compute 后有内容。
- fragment pass 绑定了该 image。
- pass 间缺少 compute write → fragment read barrier。

### Log / Code

关键问题：

```text
Compute 写后直接进入 fullscreen pass，没有 barrier。
```

---

### 6. 根因

根因：compute shader 写 storage image 后，没有通过 image memory barrier 建立 compute shader write 到 fragment shader sampled read 的内存依赖与 layout transition，导致 fragment shader 读取到无效或旧内容。

---

### 7. 修复方案

### 最小修复

在 compute dispatch 后插入 barrier：

```text
srcStage  = COMPUTE_SHADER
srcAccess = SHADER_WRITE
oldLayout = GENERAL

dstStage  = FRAGMENT_SHADER
dstAccess = SHADER_SAMPLED_READ
newLayout = SHADER_READ_ONLY_OPTIMAL
```

### 稳定修复

- 每个 compute output 明确 consumer。
- 对 storage image 建立状态跟踪。
- descriptor imageLayout 与实际 consumer layout 对齐。

### 工程化修复

- 在 RenderGraph 中声明：
  ```text
  compute pass writes storage image
  graphics pass reads sampled image
  ```
- 自动生成 barrier。
- 开启 sync validation 测试 compute → graphics 链路。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] Sync validation 无 hazard。
- [ ] RenderDoc 中 fragment pass 能读取 compute 输出。
- [ ] 多帧结果稳定。
- [ ] Android AGI 中 compute / graphics pass 顺序正确。

---

### 9. 经验抽象

Compute 和 Graphics 之间不会自动同步。  
只要资源跨阶段读写，必须明确：

```text
producer stage
producer access
consumer stage
consumer access
image layout
descriptor imageLayout
queue ownership，如跨 queue
```

---

### 10. 预防规则

1. Compute 输出资源必须声明 consumer。
2. Storage image 后续采样必须有 layout transition。
3. Barrier 必须精确表达 write → read。
4. Sync validation 应纳入调试流程。
5. RenderDoc / AGI 必须验证 compute output 和 graphics input。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`


---

## Case: Frame Resource Overwrite Causes Flickering

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 同步 / Frame Resource / 闪烁 |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

多 frame-in-flight 后画面出现闪烁。  
Uniform 参数偶发跳变，某些帧使用上一帧或下一帧的数据。  
降到 1 frame-in-flight 后问题消失。

---

### 2. 初始上下文

- 使用 2 或 3 frames-in-flight。
- 每帧更新 uniform buffer。
- Descriptor set 可能复用同一个 buffer。
- CPU 每帧写入新参数。
- GPU 可能仍在读取旧 frame 的资源。

---

### 3. 初始误判

最初容易怀疑：

```text
动画逻辑错误；
shader 数值不稳定；
present 顺序问题；
swapchain image index 错误。
```

但降为 1 frame-in-flight 后问题消失，说明更像 CPU/GPU 同步或 frame resource 复用问题。

---

### 4. 排查路径

1. 打印 frame index 和 swapchain image index。
2. 确认 frame index 不等于 image index。
3. 检查 uniform buffer 是否 per-frame 独立。
4. 检查 descriptor set 是否 per-frame 独立。
5. 检查 fence wait / reset 顺序。
6. 确认 CPU 是否在 fence signal 前覆盖 GPU 正在读取的资源。
7. 用 RenderDoc 查看异常帧绑定的 uniform buffer。

---

### 5. 关键证据

### Validation Layer

不一定会报错。  
如果开启同步验证，可能出现 read/write hazard。

### RenderDoc / AGI

观察到：

- 异常帧绑定的 uniform 数据与当前 CPU 期望不一致。
- 多帧资源复用了同一 buffer range。
- frame index / image index 管理混乱。

### Log / Code

关键问题：

```text
CPU 每帧写同一个 uniform buffer memory range，但没有等待对应 GPU frame 完成。
```

---

### 6. 根因

根因：CPU 在 GPU 仍可能读取上一帧 uniform buffer 时提前覆盖了同一块 memory range，导致 shader 偶发读取到错误数据。

---

### 7. 修复方案

### 最小修复

- 降为 1 frame-in-flight 验证。
- 每个 frame-in-flight 使用独立 uniform buffer 或独立 offset。
- 只有当前 frame fence signal 后，才复用对应资源。

### 稳定修复

- 建立 per-frame resource：
  - uniform buffer
  - descriptor set
  - command buffer
  - fence / semaphore
- 明确区分 frame index 和 swapchain image index。
- 对 dynamic uniform offset 做 alignment 检查。

### 工程化修复

- 使用 ring buffer。
- 建立 frame allocator。
- 所有 transient GPU resource 都挂到 frame resource 下。
- 在 debug 模式下记录 resource last-used fence。

---

### 8. 修复后验证

- [ ] 多 frame-in-flight 不闪烁。
- [ ] 降为 1 frame 和恢复多 frame 结果一致。
- [ ] RenderDoc 中每帧 uniform 数据正确。
- [ ] Sync validation 无 hazard。
- [ ] 多帧长时间运行稳定。

---

### 9. 经验抽象

Vulkan 中“CPU 写完”不等于“GPU 已经读完”。  
任何 per-frame 可变资源都必须受 fence 或 frame resource 生命周期保护。

---

### 10. 预防规则

1. frame index 与 swapchain image index 必须分清。
2. 高频更新 uniform 必须使用 per-frame buffer 或 ring buffer。
3. descriptor set 应与 frame resource 生命周期一致。
4. command buffer reset 前必须确认 GPU 不再使用。
5. frame resource 复用必须等待对应 fence。

---

### 11. 关联 API 卡片

- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/uniform_buffer_descriptor.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`


---

## Case: Transfer To Shader Missing Transition

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 同步 / Image Layout / Transfer / Shader Read |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

纹理资源通过 staging buffer 上传后，在 shader 中采样结果全黑、颜色异常或读取到未定义内容。App 通常不 crash，但贴图显示错误；部分驱动上可能出现画面撕裂或随机像素。

- RenderDoc 中 staging buffer 写入操作存在，目标 image 也有数据，但后续 shader pass 采样异常。
- 问题在上传完成后第一次使用 image 时最明显。

---

### 2. 初始上下文

- 使用 graphics pipeline，通过 combined image sampler 采样纹理。
- Texture 数据通过 staging buffer + `vkCmdCopyBufferToImage` 上传。
- 上传命令与后续渲染命令可能在同一 command buffer，也可能分属不同 submit。
- 可能使用 transfer queue 与 graphics queue 分离的架构。
- 多 frame-in-flight 或每帧动态更新纹理时风险更高。

---

### 3. 初始误判

最初容易怀疑：

```text
纹理文件没加载；
staging buffer 数据为空；
copy 命令写错区域；
sampler 或 image view 创建错误；
shader 采样坐标错误；
mipmap 没生成。
```

但 RenderDoc 中 copy 操作已完成，image 内容可见；后续 pass 的 descriptor 也指向正确 image view。最终发现 image 在上传后仍停留在 `TRANSFER_DST_OPTIMAL` 或 `PREINITIALIZED` layout，没有转换到 `SHADER_READ_ONLY_OPTIMAL`。

---

### 4. 排查路径

1. 检查 Validation Layer 是否报 layout mismatch `[TOOL]`。
2. 在 RenderDoc / AGI 中查看 copy 操作后的 image layout `[TOOL]`。
3. 确认 copy 命令使用的 image layout 为 `TRANSFER_DST_OPTIMAL` `[SPEC]`。
4. 检查 copy 命令之后、shader 采样之前是否有 image memory barrier `[ENGINE]`。
5. 确认 barrier 的 `oldLayout` 与 copy 时使用的 layout 一致 `[SPEC]`。
6. 确认 barrier 的 `newLayout` 为 `SHADER_READ_ONLY_OPTIMAL` `[SPEC]`。
7. 检查 descriptor imageLayout 是否也填写为 `SHADER_READ_ONLY_OPTIMAL` `[SPEC]`。
8. 若使用 transfer queue 单独上传，检查 queue family ownership transfer `[SPEC]`。

---

### 5. 关键证据

### Validation Layer

可能出现：

- `VUID-vkCmdDrawIndexed-None-02699` / `VUID-vkCmdDraw-None-02699`：descriptor image layout 与实际 layout 不匹配。
- `VUID-vkCmdCopyBufferToImage-dstImageLayout-00181`：copy 时 dstImageLayout 非法。
- `UNASSIGNED-CoreValidation-DrawState-InvalidImageLayout`：image layout 与 pipeline 期望不一致 `[TOOL]`。
- Synchronization hazard 警告：transfer write 与 shader read 之间缺少 barrier `[TOOL]`。

### RenderDoc / AGI

观察到：

- `vkCmdCopyBufferToImage` 成功执行，目标 image 有数据。
- Copy 后 image 的当前 layout 为 `TRANSFER_DST_OPTIMAL`。
- 后续 draw call 的 descriptor imageLayout 填写为 `SHADER_READ_ONLY_OPTIMAL`。
- Draw call 前后没有 image memory barrier 完成 layout transition。

### Log / Code

返回值：

- `vkQueueSubmit` 返回 `VK_SUCCESS`。
- `vkCmdCopyBufferToImage` 返回 void，但 image layout 未改变。

关键代码：

```text
// 错误示例：缺少 transfer write → shader read 的 barrier
vkCmdCopyBufferToImage(cmd, stagingBuffer, textureImage,
    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

// 直接开始渲染，没有 transition
vkCmdBeginRenderPass(cmd, &rpBegin, VK_SUBPASS_CONTENTS_INLINE);
// shader 采样 textureImage
```

---

### 6. 根因

根因：staging buffer 通过 `vkCmdCopyBufferToImage` 向 image 写入数据后，没有通过 image memory barrier 将 image 从 `TRANSFER_DST_OPTIMAL` 转换到 `SHADER_READ_ONLY_OPTIMAL`，导致 fragment shader 采样时读取到 layout 不匹配的无效内容。

---

### 7. 修复方案

### 最小修复

在 `vkCmdCopyBufferToImage` 之后、shader 使用之前插入 image memory barrier：

```text
srcStage  = TRANSFER
srcAccess = TRANSFER_WRITE
oldLayout = TRANSFER_DST_OPTIMAL

dstStage  = FRAGMENT_SHADER
dstAccess = SHADER_SAMPLED_READ
newLayout = SHADER_READ_ONLY_OPTIMAL
```

若后续 consumer 是 compute shader，则 `dstStage = COMPUTE_SHADER`，`dstAccess = SHADER_SAMPLED_READ`。

### 稳定修复

- 为每个 image 维护当前 layout 状态机。
- 在 copy / blit / render / compute 使用前自动检查并插入必要 transition。
- descriptor imageLayout 从 image 当前 layout 推导，避免手填错误。
- 对 mipmap generation 链路上的多次 layout 变化统一处理。

### 工程化修复

- 建立 RenderGraph，自动根据 producer 和 consumer 推导 layout 与 barrier。
- 在 command buffer recorder 中加入 layout assertion，发现不一致立即触发 debug break。
- 对 transfer queue / graphics queue 分离的架构，封装 queue family ownership transfer。
- CI 中跑 RenderDoc capture 自动化检查 image layout transition 是否完整。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 copy 后 image layout 成功变为 `SHADER_READ_ONLY_OPTIMAL`。
- [ ] Shader 采样结果与源纹理一致。
- [ ] 多帧运行稳定，无 flicker 或随机黑块。
- [ ] 动态更新纹理时每帧都有正确的 transition。
- [ ] Transfer queue 与 graphics queue 分离时结果仍正确。

---

### 9. 经验抽象

凡是 image 被 staging buffer 上传后交给 shader 使用，必须同时满足：

```text
usage 包含 TRANSFER_DST + SAMPLED
upload时使用 TRANSFER_DST_OPTIMAL
上传后必须 transition 到 SHADER_READ_ONLY_OPTIMAL
descriptor imageLayout 与实际 layout 一致
barrier 的 subresource range 覆盖被采样层级
```

Layout transition 不是“可选优化”，而是 image 跨用途使用的必要步骤。

---

### 10. 预防规则

1. 每个 texture upload 必须成对出现：copy / blit + transition to shader read。
2. 不允许 copy 后直接采样，必须经 barrier 转换 layout。
3. Descriptor imageLayout 必须从 image 当前状态自动获取，禁止硬编码。
4. 每个 image 必须跟踪当前 layout，并在 debug 构建中校验。
5. 使用 transfer queue 上传时，必须处理 queue family ownership transfer。
6. 生成 mipmap 时，每级 blit 的 layout 转换必须完整。
7. 新增贴图加载流程必须走统一的 upload + transition helper。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

### 13. 关联 Workflow

- `../../05_workflows/05_resource_management/add_texture_resource.md`
- `../../05_workflows/02_render_pass_effects/add_texture_sampling_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`


---

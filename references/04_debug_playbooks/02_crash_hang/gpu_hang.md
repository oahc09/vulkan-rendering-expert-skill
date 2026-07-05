# Debug Playbook: GPU Hang

## 0. 适用范围

### 适用

- 画面突然卡死，数秒后恢复或应用被关闭。
- 系统弹出“显示驱动程序已停止响应并已成功恢复”（TDR / 驱动 reset）。
- 特定 draw / dispatch 后 GPU 时间不推进，RenderDoc / AGI 抓帧失败。
- 长时间运行的 compute shader 后整机失去响应。
- 多线程频繁 submit 后偶发卡死。

### 不适用

- 应用进程直接闪退并返回 `VK_ERROR_DEVICE_LOST`（优先看 device_lost.md）。
- CPU 侧死锁导致主线程无响应但 GPU 空闲。
- 系统级电源管理或驱动本身已知 bug（本 Playbook 仅做排查，不修复驱动）。

---

## 1. 现象

- 应用窗口定格，键盘鼠标事件不再刷新画面。
- Event Viewer / dmesg / logcat 出现 GPU timeout、TDR、watchdog reset 记录。
- 某次 QueueSubmit 后 GPU counter 突然归零或停止采样。
- RenderDoc 在特定 draw call 后无法继续抓取。
- AGI 中 GPU 时间轴在某一命令处中断。
- 长时间 dispatch 后，系统报告 compute shader timeout。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | shader 无限循环或过长执行 | 特定 draw/dispatch 后必现 hang；取消该 draw 后正常 | Compute Pipeline / Shader Module |
| P0 | 内存 hazard / 同步缺失 | Validation sync 报 WRITE_AFTER_READ / READ_AFTER_WRITE 且出现在 hang 前 | Barrier / Image / Buffer |
| P0 | 资源竞争或跨 queue 无序访问 | 多 queue 提交后出现 hang；缺少 semaphore / barrier | Queue / Semaphore / Fence |
| P1 | barrier stage / access 错误 | barrier 把 srcStage 设得过早或 dstStage 过晚，导致依赖不完整 | Pipeline Barrier |
| P1 | 深度 / stencil attachment 使用冲突 | 同一 subpass 内同时读写 depth 又未声明 dependency | Render Pass / Attachment |
| P1 | 大 workgroup 或寄存器压力导致 warp 长期占用 | compute shader 修改 workgroup size 后 hang 消失 | Compute Pipeline |
| P2 | GPU 硬件 watchdog 阈值过低 | 仅在特定低端设备 / 特定驱动版本出现 | Physical Device / Driver |
| P2 | 多线程 command buffer 录制破坏内部状态 | 去掉多线程录制后不再 hang | Command Buffer / Pool |

---

## 3. 快速验证路径

1. **最小范围二分**：把可疑 draw / dispatch 逐个注释，定位触发 hang 的最小命令。`[TOOL]`
2. **替换为 dummy shader**：把 fragment / compute shader 换成简单输出，确认是否 shader 本身导致。`[TOOL]`
3. **开启 Validation Layer 的 sync 分支**：重点查找 hazard 报告。`[TOOL]`
4. **强制单 queue / 单线程提交**：排除跨 queue 同步和多线程录制问题。`[HEUR]`
5. **缩短 dispatch 维度**：把全局 workgroup 数减少 10 倍，观察是否 watchdog 触发。`[TOOL]`
6. **RenderDoc / AGI 抓帧**：看 hang 点前后 pipeline state 和 resource 使用。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Shader Module
→ Pipeline (Graphics / Compute)
→ Command Buffer 录制
→ Pipeline Barrier / Event / Semaphore / Fence
→ Queue Submit (Graphics / Compute / Transfer)
→ Image / Buffer 内存访问
→ Present
```

逐项检查：

- Shader 是否存在未初始化循环变量、动态分支导致的无限循环。`[ENGINE]`
- Compute workgroup 是否过大，局部内存 / 寄存器占用是否超标。`[HEUR]`
- 同一资源是否被多个 queue 或同一 queue 内多个命令并发读写且未同步。`[SPEC]`
- Barrier 的 `srcStageMask` / `dstStageMask` / `srcAccessMask` / `dstAccessMask` 是否覆盖真实访问。`[SPEC]`
- Attachment 的 load/store op 是否与 pipeline 中的 depth/stencil write 一致。`[SPEC]`
- Command buffer 是否在录制期间被另一个线程 reset 或修改。`[SPEC]`
- Submit 后是否等待 fence，是否存在 in-flight command buffer 超量。`[ENGINE]`

---

## 5. 高频根因

1. Compute shader 中 `while(!shared_flag)` 类自旋等待缺少保证退出的机制。`[ENGINE]`
2. Fragment shader 中动态循环上界依赖纹理采样值，偶发极大迭代次数。`[HEUR]`
3. Storage image / storage buffer 同时被读和写，未插入 memory barrier。`[SPEC]`
4. `VK_PIPELINE_STAGE_ALL_COMMANDS_BIT` 滥用导致实际依赖关系被掩盖，但在某些驱动上仍出现 hazard。`[HEUR]`
5. 多 queue 使用同一 image 但缺少 queue family ownership transfer。`[SPEC]`
6. Render pass subpass dependency 的 `srcSubpass = dstSubpass` 自依赖缺失，导致同一 subpass 内 attachment 读写冲突。`[SPEC]`
7. 大量 small draw call 后紧跟 heavy compute，command buffer 长期占用 GPU 未给 present 让出时间。`[ENGINE]`

---

## 6. 修复方案

### 最小修复

- 在可疑 producer / consumer 之间插入明确的 `vkCmdPipelineBarrier`，确保 `srcAccessMask` 覆盖写，`dstAccessMask` 覆盖读，`srcStageMask` 不晚于 producer 的最后一个 stage，`dstStageMask` 不早于 consumer 的第一个 stage。`[SPEC]`
- 把 compute shader 的 workgroup size 降到硬件 limit 以下，并减少局部数组 / 寄存器占用。`[HEUR]`
- 对可能无限循环的 shader 增加强制迭代上限或 break 条件。`[ENGINE]`
- 临时改为单 queue 提交，确认多 queue 同步是否是直接原因。`[TOOL]`

### 稳定修复

- 建立资源状态跟踪，自动在 read-after-write / write-after-write / write-after-read 场景插入 barrier。`[ENGINE]`
- 使用 render graph 描述 pass 依赖，由框架生成 barrier 和 subpass dependency。`[ENGINE]`
- 对跨 queue 资源建立 semaphore + ownership transfer 规范。`[SPEC]`
- 对长时间 compute 任务拆分到多个 submit，中间插入 fence 让 GPU 有机会响应 watchdog。`[ENGINE]`

### 工程化修复

- 在 CI 中启用 Validation Layer sync 检测和线程 sanitizer。`[TOOL]`
- 对 shader 加入静态循环边界检查工具和编译期 workgroup 占用估算。`[ENGINE]`
- 建立 GPU hang 自动二分系统：通过 feature flag 关闭部分 pass 快速定位。`[ENGINE]`
- 对低端设备启用保守的 dispatch 切片策略，避免触发驱动 watchdog。`[ANDROID]`

---

## 7. 回归验证

- [ ] 触发 hang 的场景连续运行 30 分钟以上无 TDR / 卡死。
- [ ] Validation Layer（含 sync）在该场景无 hazard 报告。
- [ ] RenderDoc / AGI 能完整抓帧，GPU 时间轴无中断。
- [ ] 关闭 debug shader 后原 shader 仍稳定运行。
- [ ] 多 queue / 多线程录制恢复后不再复现。
- [ ] resize / rotation / pause-resume 后不引入新的 hang。
- [ ] 低端设备和高端设备均通过压力测试。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`

---

## 9. 工具证据

### Validation Layer

- 关注 sync 分支输出的 `SYNC-HAZARD-WRITE_AFTER_READ`、`SYNC-HAZARD-READ_AFTER_WRITE`、`SYNC-HAZARD-WRITE_AFTER_WRITE` 及 VUID。`[TOOL]`
- 关注 `VUID-vkCmdPipelineBarrier-srcStageMask-...`、`VUID-vkCmdPipelineBarrier-dstStageMask-...` 等 stage / access 错误。`[TOOL]`
- 关注 shader 中 `OpLoopMerge` 相关警告或 spirv-opt 的无限循环提示。`[TOOL]`

### RenderDoc

- 查看 hang 点所在 draw / dispatch 的 pipeline state、shader disassembly、resource binding。`[TOOL]`
- 检查该命令前后 image / buffer 是否有未定义内容或被并发修改迹象。`[TOOL]`
- 确认该命令的 vertex / index count、instance count、workgroup 数是否异常。`[TOOL]`

### AGI / Android

- 检查 GPU 时间轴是否在某一 draw / dispatch 处突然结束。`[TOOL]`
- 观察 `GPU % Utilization`、`Fragment Utilization`、`Compute Utilization` 在 hang 前是否满载。`[TOOL]`
- 查看 logcat 是否有 `Adreno` / `Mali` / `HWC` 相关的 GPU timeout、TDR、recovery 日志。`[ANDROID]`

### logcat

- 搜索 `TDR`、`gpu timeout`、`watchdog`、` kgsl-3d0` / `mali` / `vulkan` 关键字。`[ANDROID]`
- 检查 `ANativeWindow` / `Surface` 是否在 hang 前后被销毁或重建。`[ANDROID]`

---

## 10. Android 分支

Android 上 GPU hang 常与 Surface / ANativeWindow / Swapchain 生命周期交织，额外检查：

1. **Surface 有效性前提**：确认 hang 发生时 `ANativeWindow` 未被 `surfaceDestroyed` 回调释放；任何 GPU 命令仍引用旧 native window 都可能导致驱动异常。`[ANDROID]`
2. **Swapchain 重建完整性**：横竖屏切换或 `vkQueuePresentKHR` 返回 `SUBOPTIMAL` / `OUT_OF_DATE` 后，是否等待 GPU idle 再销毁旧 swapchain 及相关 framebuffer。`[SPEC]`
3. **in-flight resource 清理**：pause / resume 时是否确保所有引用旧 swapchain image 的 command buffer、semaphore、fence 已 retire。`[ENGINE]`
4. **深度 / offscreen image 尺寸跟随**：rotation 后 depth attachment 和 offscreen image 是否按新 extent 重建，旧 image view 是否仍被 descriptor 引用。`[ENGINE]`
5. **Tile-based GPU 特定风险**：Adreno / Mali 上 fullscreen pass 后紧跟 compute 写 storage image，未正确处理 tile flush，可能触发 hang。`[ANDROID]`
6. **logcat 驱动恢复信息**：部分设备在 TDR 后会重建 Surface，需确认应用是否正确接收 `onSurfaceCreated` / `onSurfaceChanged` 并恢复渲染循环。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - 触发 hang 的最小 draw / dispatch 范围。
   - Validation Layer 完整日志（含 `VK_LAYER_KHRONOS_validation` 的 sync 分支）。
   - RenderDoc capture（即使无法完整抓帧，也提供中断点）。
   - AGI / GPU Profiler 时间轴截图。
   - logcat 中 TDR / timeout / recovery 相关日志。
   - 触发 shader 源码及 SPIR-V。
   - 设备型号、GPU、驱动版本、Android 版本。
   - 是否多 queue、是否多线程录制 command buffer。
3. 给出最小复现路径：单 queue + dummy shader + 关闭可疑 pass。
4. 标注当前判断属于：
   - `[SPEC]` 若已确认 barrier / stage / access 违反规范。
   - `[TOOL]` 若 Validation / RenderDoc / AGI 已给出明确证据。
   - `[ENGINE]` 若基于工程经验推断 shader 或队列使用问题。
   - `[HEUR]` 若尚未拿到工具证据，仅为可能性排序。
   - `[ANDROID]` 若涉及 Surface 生命周期或 tile-based GPU 特性。

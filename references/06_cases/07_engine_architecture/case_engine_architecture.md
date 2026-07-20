# Cases: Engine Architecture

> 合并自 4 个原 case 文件。关键词: render-graph, per-frame, swapchain-dependent, pipeline-cache

---

## Case: Per Frame Resource Design

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / Per-frame / Ring-buffer / Command Buffer |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 多 frame-in-flight（2～3）场景下，画面偶发撕裂、闪烁或资源内容“串帧”。
- 偶发 Validation Layer 报 `SYNC-HAZARD`：write-after-read 或 read-after-write。
- 关闭 triple buffering 改用单缓冲后问题消失，但帧率下降。
- 某些 dynamic uniform buffer 的内容被下一帧覆盖，导致当前帧绘制使用了错误的 transform / material 参数。

---

### 2. 初始上下文

- 平台：通用，常见于 Windows / Linux / Android 多 frame-in-flight 渲染器。
- 使用 2～3 个 frame-in-flight，每个 frame 拥有独立的 command buffer、fence、semaphore。
- Uniform buffer / storage buffer 使用 ring buffer 管理，按 frame 偏移写入。
- Descriptor set 按 frame 分配，或全局共享。
- 渲染线程与 GPU 异步，CPU 持续录制第 N+1/N+2 帧的命令，GPU 正在执行第 N 帧。
- 未明确区分“CPU 帧索引”与“GPU 完成帧索引”。

---

### 3. 初始误判

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

### 4. 排查路径

1. 确认 frame-in-flight 数量、当前 CPU frame index、当前 GPU completed frame index。
2. 检查每帧的 fence wait：是否等待的是“本帧要复用的资源对应的 fence”，还是“某个固定 fence”。
3. 检查 command buffer 的 reset 时机：是否在 fence signal 之后 reset。
4. 检查 uniform buffer ring buffer 的 offset 计算：是否按 frame-in-flight 数量取模，并保证写入区间不重叠。
5. 检查 descriptor set 是否按 frame 划分，还是全局 pool 任意复用。
6. 用 Validation Layer 的 synchronization 检查定位具体 hazard。
7. 用 RenderDoc 多帧 capture 对比，确认 hazard 出现在哪两个 frame 之间。

---

### 5. 关键证据

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

### 6. 根因

根因：per-frame 资源（command buffer、uniform buffer、descriptor set）没有与 frame-in-flight 索引严格绑定，CPU 在 fence 未 signal 时复用了 GPU 仍在访问的资源，导致数据竞争和视觉异常 `[ENGINE]`。

---

### 7. 修复方案

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

### 8. 修复后验证

- [ ] Validation clean（包括 synchronization validation）。
- [ ] 多帧运行无撕裂、闪烁、串帧。
- [ ] RenderDoc 中每帧 uniform buffer 内容与提交时一致。
- [ ] Frame-in-flight 增加到 3 后问题不复现。
- [ ] 窗口 resize / Android rotation 后 per-frame 资源仍能正确重建。
- [ ] 长时间运行（>30 分钟）无资源竞争导致的偶发 crash。

---

### 9. 经验抽象

Frame-in-flight 不是“开几个 buffer”那么简单，而是要求 CPU 侧资源池与 GPU 完成进度严格对齐。核心规则：

```text
谁写入、谁等待、谁消费，必须按 frame-in-flight 索引闭环。
当前 CPU 帧能使用的资源范围 = 上一轮同索引帧的 fence 已 signal。
Command buffer 的 reset 和录制必须在 fence wait 之后。
```

混淆 `swapchain image index` 和 `frame-in-flight index` 是常见的根因之一 `[ENGINE]`。

---

### 10. 预防规则

1. 每个 frame-in-flight 索引必须拥有独立的 command buffer、fence、semaphore、UBO 段。
2. 禁止在 frame fence 未 signal 时 reset command buffer 或写入 per-frame buffer。
3. 统一命名规范，明确区分 `currentFrame`、`swapchainImageIndex`、`frameInFlightIndex`。
4. Per-frame descriptor set 必须按 frame-in-flight 索引分配，禁止跨帧复用未完成的 set。
5. Uniform buffer ring buffer 的大小必须按 `FRAME_IN_FLIGHT × perFrameSize` 计算，禁止重叠。
6. 新增 per-frame 资源时，必须声明其生命周期和同步边界。
7. 在 CI 中开启 synchronization validation 并持续回归。
8. 优先使用 timeline semaphore 简化多 frame-in-flight 状态管理。

---

### 11. 关联 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`

---

### 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`


---

## Case: Pipeline Cache Strategy

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / Pipeline Cache |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE] [SPEC] [TOOL]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 首次安装或清除数据后启动，进入游戏主界面或第一场战斗时严重卡顿。
- 第二次启动明显变快，但应用更新或显卡驱动升级后，启动速度又回退到首次状态。
- 某些用户反馈“第一次进某关卡特别卡”，之后流畅。
- CI 构建的 pipeline cache 文件在部分设备上无法加载，启动日志报 cache 校验失败。

---

### 2. 初始上下文

- 平台：通用，Android 上问题更突出（包体大小和 I/O 限制更严格）。
- 使用 `VkPipelineCache` 加速 `vkCreateGraphicsPipelines`。
- 尝试将 pipeline cache 数据保存到磁盘，但策略不完整。
- 没有为不同 GPU / 驱动版本单独管理 cache 文件。
- Shader variant 数量大，但 CI 没有离线编译流程。
- 应用更新时未清理旧 cache，也未做版本校验。

---

### 3. 初始误判

最初容易怀疑：

```text
Shader 实时编译慢，应该改异步编译；
磁盘 I/O 慢，不应该存 cache；
包体太大，不能把 cache 打进包；
驱动 bug 导致 cache 无法加载；
Pipeline cache 没有效果，不需要做。
```

但实测有 cache 时二次启动的 pipeline 创建时间下降 80% 以上；问题集中在 cache 的持久化范围、校验规则、失效策略和预热时机不清晰 `[TOOL]`。最终确认是 pipeline cache 的架构策略不完善 `[ENGINE]`。

---

### 4. 排查路径

1. 检查 `VkPipelineCacheCreateInfo` 是否正确启用，initialData 是否从文件加载。
2. 检查 cache 文件保存/加载路径，确认首次启动为空、二次启动有数据。
3. 用 `vkGetPipelineCacheData` 导出 cache，统计大小和命中率。
4. 对比有/无 cache 时 `vkCreateGraphicsPipelines` 的耗时。
5. 检查 cache 文件是否随应用更新或驱动更新而失效。
6. 检查 cache 是否覆盖了所有常用 shader variant。
7. 评估 cache 文件体积对包体和下载的影响。
8. 检查 Android 上不同设备（GPU/驱动）是否需要独立的 cache 文件。

---

### 5. 关键证据

### Validation Layer

- 通常无 error。
- 若 cache 数据头魔数/版本不匹配，`vkCreatePipelineCache` 可能静默失败并创建空 cache（不会报错，但 initialData 被忽略）`[SPEC]`。

### RenderDoc / AGI

- CPU Profiler：首次启动 `vkCreateGraphicsPipelines` 累计耗时数秒；二次启动大幅下降。
- AGI：首次进入战斗时大量 pipeline 创建集中在同一帧。
- 工具日志：cache 文件加载后 `vkGetPipelineCacheData` 返回 0 bytes，说明 cache 未命中或为空。
- 关键 resource：`VkPipelineCache`、cache 文件、shader variant 清单。

### Log / Code

- 错误代码模式：

```text
// 无版本校验，应用更新后仍加载旧 cache
std::vector<uint8_t> data = readFile(cachePath);
VkPipelineCacheCreateInfo ci = {};
ci.initialDataSize = data.size();
ci.pInitialData = data.data();
vkCreatePipelineCache(device, &ci, nullptr, &cache);
```

- 启动日志对比：

```text
首次启动：
  Pipeline cache loaded: 0 bytes
  Total pipeline creation time: 4.2 s

二次启动：
  Pipeline cache loaded: 8.5 MB
  Total pipeline creation time: 0.6 s
```

---

### 6. 根因

根因：Pipeline cache 的持久化、校验、失效和预热策略没有作为系统工程对待，导致 cache 命中不稳定、跨版本/跨驱动失效、首次用户体验差 `[ENGINE]`。

---

### 7. 修复方案

### 最小修复

- 在 `vkCreatePipelineCache` 时加载磁盘 cache 数据，并在应用退出时调用 `vkGetPipelineCacheData` 保存。
- 在 cache 文件头中加入版本字段：`app version`、`driver version`、`vendorID`、`deviceID`、`shader hash prefix`。
- 启动时校验版本，不匹配则创建空 cache 并重新预热。

### 稳定修复

- 在 CI 中离线编译所有已知 shader variant，生成基础 pipeline cache 文件并随包发布。
- 运行时 cache 分为两层：
  - `base cache`：包内只读，覆盖所有已知 variant。
  - `user cache`：可写，保存运行时首次遇到的新 variant。
- 启动时合并两层 cache，运行时只写 user cache。
- 为不同 GPU 架构生成独立的 base cache（Adreno、Mali、PowerVR 等），按设备选择加载。

### 工程化修复

- 引入 pipeline cache 元数据服务：记录每个 cache 文件对应的 driver、GPU、app 版本、shader 集合 hash。
- 运行时 telemetry：记录 cache 命中率、首次遇到的 variant、创建耗时，用于补充预热清单。
- 使用 `VK_EXT_graphics_pipeline_library` 拆分 pipeline 阶段，建立更细粒度的 cache（vertex input、pre-rasterization、fragment shader、fragment output）`[SPEC]`。
- 对无法预热的动态组合，使用 `VK_EXT_pipeline_creation_cache_control` 异步创建并回填 cache。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] 首次安装启动时，基础 pipeline cache 成功加载且命中率高。
- [ ] 二次启动 pipeline 创建总耗时下降 70% 以上。
- [ ] 应用更新或驱动更新后，旧 cache 正确失效并重建。
- [ ] 不同 GPU 品牌设备加载对应 cache 文件，无跨设备兼容问题。
- [ ] Cache 文件体积在包体预算内。
- [ ] 运行时首次遇到的新 variant 能被捕获并补充到 user cache。

---

### 9. 经验抽象

Pipeline cache 是“一次编译、多次复用”的关键基础设施。完整的 cache 策略必须回答：

```text
Cache 从哪里来？（CI 离线编译 / 运行时采集）
Cache 什么时候失效？（app 更新、driver 更新、shader 变化、GPU 变化）
Cache 如何分层？（只读 base cache + 可写 user cache）
Cache 如何预热？（关卡加载、启动画面、后台线程）
Cache 如何监控？（命中率、新 variant、创建耗时）
```

只保存不校验的 cache 反而会在版本变化后引入隐式性能回退 `[ENGINE]`。

---

### 10. 预防规则

1. 每个 pipeline cache 文件必须包含可校验的元数据（app version、driver version、GPU 标识、shader hash）。
2. 必须区分只读 base cache 和可写 user cache，禁止直接修改包内 cache。
3. CI 必须离线编译所有已知 shader variant 并生成 base cache。
4. 不同 GPU 架构/驱动版本必须生成独立的 cache 文件。
5. 应用更新或驱动更新后必须使旧 cache 失效并触发重建。
6. 运行时首次遇到的新 variant 必须能被 telemetry 捕获并补充预热。
7. 定期用 `vkGetPipelineCacheData` 回写 cache，保证崩溃后也能保留大部分编译结果。
8. 引入 graphics pipeline library 拆分 cache 粒度，提高复用率。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/reduce_pipeline_creation_stutter.md`
- `../../05_workflows/06_pipeline_descriptor/add_graphics_pipeline.md`
- `../../05_workflows/01_renderer_setup/setup_instance_device_queue.md`


---

## Case: Render Graph Resource Lifetime

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / RenderGraph / Resource Lifetime |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 引入 RenderGraph 后，部分 transient resource 出现 Validation Layer `SYNC-HAZARD` 或 image layout 错误。
- 某些 pass 读取到上一帧的残留内容，导致拖影、闪烁或后处理结果错误。
- RenderGraph 自动推导的 barrier 在大多数情况下正确，但在资源被多个 consumer 读取时出错。
- 关闭 resource aliasing 后问题消失，但内存占用大幅上升。

---

### 2. 初始上下文

- 平台：通用，常见于使用 RenderGraph / FrameGraph 的中大型渲染器。
- 使用自研或开源 RenderGraph 管理 render pass 和资源。
- RenderGraph 根据 pass 的 read/write 声明自动创建 image/buffer、推导 barrier 和 layout。
- 存在 transient resource：只在单帧内使用、可被 aliasing 复用。
- 部分资源会被多个 pass 读取（如 shadow map、G-Buffer）。
- 尝试开启 resource aliasing 以节省显存。

---

### 3. 初始误判

最初容易怀疑：

```text
RenderGraph 的 barrier 推导有 bug；
Aliasing 实现错误，资源被覆盖；
Pass 的 read/write 声明不正确；
Image layout 转换漏了；
Fence / semaphore 等待不够。
```

但深入跟踪后发现，问题往往不在于 RenderGraph 本身，而在于 transient resource 的生命周期声明与真实使用区间不一致：某个资源被声明为 transient，但实际上跨帧使用；或被多个 consumer 读取时，生命周期只覆盖到第一个 consumer `[ENGINE]`。

---

### 4. 排查路径

1. 在 RenderGraph 编译阶段输出资源生命周期表：创建 pass、最后使用 pass、销毁 pass。
2. 对比资源的真实使用链路，检查生命周期是否覆盖所有 producer / consumer。
3. 检查 resource aliasing：两个资源的使用区间是否真的没有重叠。
4. 检查多 consumer 场景：第一个 consumer 使用后，资源是否被提前销毁或 layout 改变。
5. 检查跨帧资源是否被错误标记为 transient。
6. 用 Validation Layer 的 synchronization 检查定位 hazard。
7. 临时关闭 aliasing，观察问题是否消失，确认与生命周期重叠有关。

---

### 5. 关键证据

### Validation Layer

- `SYNC-HAZARD-READ-AFTER-WRITE`：某个 pass 读取的资源已被后续 write 覆盖。
- `SYNC-HAZARD-WRITE-AFTER-READ`：写操作发生在读操作完成之前。
- `VUID-vkCmdPipelineBarrier-oldLayout-01181`：layout transition 的 old layout 与实际不匹配。
- 错误通常指向被 aliasing 复用的 transient image `[SPEC]`。

### RenderDoc / AGI

- RenderDoc：transient image 在多个 pass 之间的 handle 发生变化，说明发生了 aliasing 复用。
- RenderDoc：某个 consumer pass 读取到的 image 内容与 producer pass 输出不一致。
- AGI：GPU timeline 显示 resource 的分配/释放区间与 pass 执行区间重叠。
- 关键 resource：transient color image、transient depth image、shadow map、G-Buffer。

### Log / Code

- 错误声明示例：

```text
// 错误：shadow map 被声明为 transient，但实际在后续 frame 仍被光照 pass 使用
RenderGraph::TextureDesc shadowDesc;
shadowDesc.lifetime = Transient;  // 错误
shadowDesc.usage    = DEPTH_STENCIL_ATTACHMENT | SAMPLED;
```

- 生命周期表示例：

```text
Resource     Created LastUsed Destroyed
GBuffer0     Pass0   Pass2    Pass5
GBuffer1     Pass0   Pass3    Pass5
BloomTemp    Pass6   Pass7    Pass8
ShadowMap    Pass0   Pass0    Pass1   <-- 生命周期过短
```

---

### 6. 根因

根因：RenderGraph 中 transient resource 的生命周期声明与其实际 producer/consumer 区间不匹配，导致资源在仍有下游读取时被回收或 aliasing 覆盖，引发同步 hazard 和画面错误 `[ENGINE]`。

---

### 7. 修复方案

### 最小修复

- 将出现问题的资源生命周期从 `Transient` 改为 `Persistent`（跨帧）。
- 扩展资源的 last-used pass 到真正的最后一个 consumer。
- 在多 consumer 之间插入显式同步点，确保所有读取完成后再释放或复用。

### 稳定修复

- 在 RenderGraph 编译阶段做生命周期检查：对 declared lifetime 与实际使用区间做静态验证，不一致时 assert 或警告。
- 引入 sub-resource 级别的 lifetime 跟踪：同一 image 的不同 mip/层可独立管理。
- 对 multi-consumer 资源，使用引用计数或“最后完成 pass”算法确定销毁点。
- 对需要跨帧保持的资源，明确标记为 `Persistent`，不参与 aliasing。

### 工程化修复

- 建立 resource aliasing 安全规则：只有生命周期区间完全不重叠且格式/尺寸兼容的资源才能 alias。
- 在 RenderGraph 中集成 automatic lifetime inference：根据 pass 的 read/write 声明自动推导最小区间，同时允许手动覆盖。
- 提供可视化工具：输出每帧 resource lifetime 甘特图，便于人工复核。
- CI 中运行全量 RenderGraph 编译并验证所有 transient resource 的 lifetime 声明与实际使用一致。

---

### 8. 修复后验证

- [ ] Validation clean（包括 synchronization validation）。
- [ ] RenderGraph 编译输出的资源生命周期表与实际使用一致。
- [ ] 开启 resource aliasing 后画面正确，无拖影/闪烁。
- [ ] 内存占用在预期范围内，aliasing 有效节省显存。
- [ ] 多 consumer 场景下所有读取方都能拿到正确数据。
- [ ] 跨帧资源（shadow map、history buffer）未被错误回收。
- [ ] 新增 pass 时生命周期声明错误能被静态检查捕获。

---

### 9. 经验抽象

RenderGraph 不是魔法，它的正确性取决于资源生命周期的声明质量。核心规则：

```text
Transient 资源的生命周期必须精确覆盖从第一个 producer 到最后一个 consumer 的区间。
Multi-consumer 资源的销毁点由最后一个 consumer 决定，不是第一个。
跨帧资源必须声明为 Persistent，禁止参与单帧 aliasing。
```

任何“声明比实际短”都会变成潜在的同步或画面错误；任何“声明比实际长”都会浪费显存 `[ENGINE]`。

---

### 10. 预防规则

1. 每个 transient resource 必须明确记录 first producer pass 和 last consumer pass。
2. Multi-consumer 资源必须使用最后 consumer 的完成点作为销毁/复用边界。
3. 跨帧使用的资源必须声明为 Persistent，禁止标记为 Transient。
4. Resource aliasing 必须验证生命周期区间无重叠、格式兼容、尺寸兼容。
5. RenderGraph 编译阶段必须对 declared lifetime 与实际使用区间做静态校验。
6. 新增 pass 或修改资源使用声明时，必须重新生成并复核资源生命周期表。
7. 在 debug 构建中输出 resource lifetime 甘特图，便于人工检查。
8. CI 中开启 synchronization validation 和 RenderGraph lifetime 校验。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`

---

### 13. 关联 Workflow

- `../../05_workflows/08_migration/convert_single_pass_to_render_graph.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`
- `../../05_workflows/02_render_pass_effects/add_offscreen_render_pass.md`


---

## Case: Swapchain Dependent Resource Group

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / Swapchain / Resize / Resource Group |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [ENGINE] [SPEC] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 窗口 resize、Android rotation、分屏或折叠屏展开后，画面比例异常、黑边、黑屏或 crash。
- 有时 swapchain 已重建，但 depth buffer 仍是旧尺寸，导致 Validation Layer 报 `VUID-vkCmdDraw-renderPass-02684` 等错误。
- 偶发 offscreen render target 尺寸与 swapchain 不一致，后处理 pass 输出被拉伸或裁剪。
- 某些依赖 swapchain 尺寸的 MSAA resolve buffer 未重建，导致 present 时 device lost。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android，resize / rotation / 分屏场景常见。
- 使用 `VkSwapchainKHR`，surface 尺寸变化时需要 recreate swapchain。
- Swapchain image 尺寸变化会牵出一族资源：depth stencil image、MSAA color/depth resolve buffer、offscreen color image、framebuffer、command buffer 录制参数。
- 这些资源分散在不同子系统中，没有统一的管理入口。
- 部分资源按 swapchain extent 创建，但重建逻辑只处理了 swapchain image 本身。

---

### 3. 初始误判

最初容易怀疑：

```text
Swapchain recreate 逻辑本身有 bug；
Surface capabilities 获取错误；
Android lifecycle 处理不当；
Framebuffer 没重建；
Viewport / scissor 还是旧值。
```

但 swapchain 和 framebuffer 重建后问题仍存在。最终发现是 swapchain 变化触发的一整族资源（depth、offscreen、MSAA、postprocess target）没有作为 group 统一重建，导致尺寸不一致 `[ENGINE]` `[ANDROID]`。

---

### 4. 排查路径

1. 捕获 resize / rotation 前后的 surface capabilities 和 swapchain extent。
2. 检查 swapchain recreate 后，哪些资源仍使用旧 extent。
3. 列出所有按 swapchain extent 派生尺寸的资源清单。
4. 检查 depth stencil image、MSAA resolve image、offscreen color image 的重建时机。
5. 检查 framebuffers、render pass、pipeline 是否依赖这些 image 的尺寸或格式。
6. 检查 viewport / scissor / dynamic rendering 的 `renderingArea` 是否更新。
7. 检查 Android 的 `onSurfaceChanged` / `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` 是否传播到所有相关子系统。
8. 用 Validation Layer 和 RenderDoc 确认具体是哪个资源尺寸不匹配。

---

### 5. 关键证据

### Validation Layer

- `VUID-vkCmdDraw-renderPass-02684`：render area 或 framebuffer 尺寸与 image 不匹配。
- `VUID-vkCreateFramebuffer-attachmentImage-00757`：framebuffer 的 attachment 尺寸不一致。
- `VUID-vkCmdBeginRenderPass-renderArea-02881`：render area 超出 framebuffer 范围。
- `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`：swapchain 与 surface 不再兼容 `[SPEC]`。

### RenderDoc / AGI

- RenderDoc：resize 后 swapchain image 已是新尺寸，但 depth attachment 仍是旧尺寸。
- RenderDoc：offscreen pass 的 render target 尺寸与 final blit 目标尺寸不一致，导致拉伸或裁剪。
- AGI：rotation 后 `vkQueuePresentKHR` 返回 `VK_ERROR_OUT_OF_DATE_KHR` 且未处理。
- 关键 resource：swapchain images、depth stencil image、MSAA color/depth image、offscreen images、framebuffers。

### Log / Code

- 错误代码模式：

```text
void onResize(uint32_t w, uint32_t h) {
    recreateSwapchain(w, h);          // 重建 swapchain
    recreateFramebuffers();           // 重建 framebuffer
    // 漏了：depth、MSAA、offscreen 未重建
}
```

- 关键日志：

```text
Swapchain extent: 1080x1920 -> 1920x1080
Depth image extent: 1080x1920  <-- 未更新
Offscreen extent: 1080x1920    <-- 未更新
MSAA resolve extent: 1080x1920 <-- 未更新
```

---

### 6. 根因

根因：swapchain extent 变化时，只重建了 swapchain 和直接依赖它的 framebuffer，而没有把 depth、MSAA、offscreen、postprocess target 等一族尺寸耦合的资源作为 group 统一重建，导致资源尺寸不一致 `[ENGINE]`。

---

### 7. 修复方案

### 最小修复

- 在 swapchain recreate 回调中，统一列出并重建所有按 swapchain extent 派生的资源。
- 至少包含：depth stencil image、MSAA color/depth resolve image、offscreen color image、framebuffers。
- 更新 viewport、scissor、dynamic rendering 的 `renderingArea`、postprocess 的 UV 和 resolution uniform。

### 稳定修复

- 建立 `SwapchainDependentResourceGroup` 抽象：注册所有尺寸随 swapchain 变化的资源，swapchain recreate 时统一触发重建。
- 每个资源声明其尺寸计算函数（如 `extent = swapchainExtent` 或 `extent = swapchainExtent / 2`）。
- 重建顺序：swapchain → depth/MSAA/offscreen images → framebuffers → render passes / pipelines（若依赖尺寸）→ viewport / scissor / uniforms。
- 在 Android  lifecycle 中，将 `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` / `onSurfaceChanged` 统一映射为 `RecreateSwapchainDependentResources` 事件。

### 工程化修复

- 引入 resolution scale 配置：将内部渲染分辨率与 swapchain 分辨率解耦，swapchain 变化时内部分辨率按策略调整。
- 建立资源依赖图：自动检测哪些 image/buffer 的尺寸直接或间接依赖 swapchain extent，并在变化时自动重建。
- CI 中加入 resize / rotation / 分屏自动化测试，用 screenshot 对比验证比例正确。
- 运行时增加尺寸一致性断言：任何按 swapchain extent 创建的资源在 render loop 中必须与当前 swapchain extent 一致。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] 窗口 resize 后画面无黑边、无拉伸、无 crash。
- [ ] Android rotation / 分屏 / 折叠屏展开后画面正常。
- [ ] Swapchain extent 变化后，depth / MSAA / offscreen / framebuffer 尺寸一致。
- [ ] Viewport / scissor / renderingArea 已更新为新尺寸。
- [ ] Postprocess 和 UI 的 resolution uniform 已同步更新。
- [ ] 连续多次 resize / rotation 后仍稳定，无资源泄漏或 device lost。

---

### 9. 经验抽象

Swapchain extent 是渲染器的“基准分辨率”，很多资源都直接或间接从它派生。必须把它当作一个资源 group 的入口：

```text
Swapchain extent 变化
→ depth stencil image
→ MSAA color / depth resolve image
→ offscreen / postprocess render targets
→ framebuffers
→ viewport / scissor / renderingArea
→ resolution-dependent uniforms / UV
```

只重建 swapchain image 而不重建整族资源，是导致 resize/rotation 后各种异常的根本原因 `[ENGINE]` `[ANDROID]`。

---

### 10. 预防规则

1. 任何按 swapchain extent 创建的资源必须注册到 `SwapchainDependentResourceGroup`。
2. Swapchain recreate 时必须统一重建整族资源，禁止只重建 swapchain image 和 framebuffer。
3. 重建顺序必须满足依赖关系：swapchain → images → framebuffers → pipelines → viewport/uniforms。
4. Android 的 surface 变化事件必须传播到所有相关子系统，禁止局部处理。
5. 新增任何分辨率相关资源时，必须声明其尺寸来源（swapchain extent、固定值、比例值）。
6. 在 debug 构建中增加尺寸一致性断言，发现不一致立即崩溃并提示。
7. CI 必须覆盖 resize / rotation / 分屏 / 折叠屏等场景。
8. Viewport / scissor / renderingArea / resolution uniform 必须在 swapchain 重建后同步更新。

---

### 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

### 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`
- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`


---

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

### Minimal Fix（针对根因的最小修复）

- 为每个 frame-in-flight 索引分配独立的 command buffer、fence、semaphore。
- 将 uniform buffer ring buffer 按 `FRAME_IN_FLIGHT` 数量分段，每段只由对应索引的帧写入。
- 等待 fence 后再 reset command buffer 和写入 per-frame buffer。
- 确保 descriptor set 按 frame 索引分配，或全局缓存的 set 在写入前等待所有使用方完成。

### Structural Fix（结构性 / 防复发修复）

- 引入 `FrameContext` 结构，封装单帧所需的所有资源：command buffer、fence、semaphore、UBO offset、descriptor set。
- 使用 `FrameResourcePool` 按 frame index 管理资源，禁止跨帧复用。
- 统一 current frame index、swapchain image index、frame-in-flight index 的命名与计算。
- 对 dynamic uniform buffer 使用 `vkCmdBindDescriptorSets` 的 `pDynamicOffsets` 参数，offset 从 `FrameContext` 获取。

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

### Minimal Fix（针对根因的最小修复）

- 在 `vkCreatePipelineCache` 时加载磁盘 cache 数据，并在应用退出时调用 `vkGetPipelineCacheData` 保存。
- 在 cache 文件头中加入版本字段：`app version`、`driver version`、`vendorID`、`deviceID`、`shader hash prefix`。
- 启动时校验版本，不匹配则创建空 cache 并重新预热。

### Structural Fix（结构性 / 防复发修复）

- 在 CI 中离线编译所有已知 shader variant，生成基础 pipeline cache 文件并随包发布。
- 运行时 cache 分为两层：
  - `base cache`：包内只读，覆盖所有已知 variant。
  - `user cache`：可写，保存运行时首次遇到的新 variant。
- 启动时合并两层 cache，运行时只写 user cache。
- 为不同 GPU 架构生成独立的 base cache（Adreno、Mali、PowerVR 等），按设备选择加载。

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
- `VUID-VkImageMemoryBarrier-oldLayout-01197`：layout transition 的 old layout 与实际不匹配。
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

### Minimal Fix（针对根因的最小修复）

- 将出现问题的资源生命周期从 `Transient` 改为 `Persistent`（跨帧）。
- 扩展资源的 last-used pass 到真正的最后一个 consumer。
- 在多 consumer 之间插入显式同步点，确保所有读取完成后再释放或复用。

### Structural Fix（结构性 / 防复发修复）

- 在 RenderGraph 编译阶段做生命周期检查：对 declared lifetime 与实际使用区间做静态验证，不一致时 assert 或警告。
- 引入 sub-resource 级别的 lifetime 跟踪：同一 image 的不同 mip/层可独立管理。
- 对 multi-consumer 资源，使用引用计数或“最后完成 pass”算法确定销毁点。
- 对需要跨帧保持的资源，明确标记为 `Persistent`，不参与 aliasing。

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

### Minimal Fix（针对根因的最小修复）

- 在 swapchain recreate 回调中，统一列出并重建所有按 swapchain extent 派生的资源。
- 至少包含：depth stencil image、MSAA color/depth resolve image、offscreen color image、framebuffers。
- 更新 viewport、scissor、dynamic rendering 的 `renderingArea`、postprocess 的 UV 和 resolution uniform。

### Structural Fix（结构性 / 防复发修复）

- 建立 `SwapchainDependentResourceGroup` 抽象：注册所有尺寸随 swapchain 变化的资源，swapchain recreate 时统一触发重建。
- 每个资源声明其尺寸计算函数（如 `extent = swapchainExtent` 或 `extent = swapchainExtent / 2`）。
- 重建顺序：swapchain → depth/MSAA/offscreen images → framebuffers → render passes / pipelines（若依赖尺寸）→ viewport / scissor / uniforms。
- 在 Android  lifecycle 中，将 `APP_CMD_TERM_WINDOW` / `APP_CMD_INIT_WINDOW` / `onSurfaceChanged` 统一映射为 `RecreateSwapchainDependentResources` 事件。

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

## Case: Bindless Migration Judgment

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / 迁移决策 / Descriptor / Bindless |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- CPU profile 中 `vkUpdateDescriptorSets` / `vkCmdBindDescriptorSets` / set 分配合计占帧预算 >15%（如 16.6 ms 预算中占 2.5 ms 以上），且随内容规模线性增长。
- 每帧 bind 次数与 draw 数 1:1 增长（如可见物体 >1000 时每帧 bind >1000 次），局部优化无法收敛。
- 贴图规模从项目初期的 <50 张增长到数百张并持续增长，材质系统 per-draw 更新代码同步膨胀。
- 设备分布统计：目标设备 `shaderSampledImageArrayNonUniformIndexing` 等 descriptor indexing feature 的覆盖率需要确认——这是决策输入，不是故障信号。
- GPU 大部分时间空转等待 CPU 提交：瓶颈在 CPU 侧绑定模型，不在 GPU。

---

### 2. 初始上下文

- 原架构：传统 per-draw descriptor set 模型——每个可见物体每帧分配并更新一个 set，`vkCmdBindDescriptorSets` 逐 draw 绑定。
- descriptor pool 全局共享，layout 按材质类型固定；UBO 用 ring buffer + dynamic offset，贴图按材质逐绑定。
- 项目从 demo 演进：draw 数从 ~200 增长到 ~1500，贴图从 <50 增长到 ~600。
- 设备目标：桌面 Vulkan 1.3 为主 + Android 中高端机型（Vulkan 1.2+ 占比待统计）。
- 团队 5 人，其中 2 人负责渲染核心。

---

### 3. 初始误判

最初把规模问题当 API bug 排查：

```text
vkUpdateDescriptorSets 在某驱动版本上特别慢，是驱动 bug；
descriptor pool 分配策略不佳，应该换更快的分配器；
改用 vkUpdateDescriptorSetWithTemplate 就能解决；
某几个材质的 descriptor 写入过多，逐个优化即可。
```

按上述方向逐项优化后（模板更新、pool 预分配、set 复用），占比从 18% 降到 13%，但下个版本内容增加后又回到 15% 以上。最终确认：单次 API 调用没有错误（Validation 全绿），问题是绑定模型本身与规模不匹配——架构问题被当成 API 性能 bug 修了一轮 `[ENGINE]`。机制层面的 CPU 开销诊断见 `../06_performance/case_performance.md` 的 Descriptor Update CPU Overhead 案例。

---

### 4. 排查路径

1. 用 CPU profiler（Tracy / Perfetto / Android Studio）量化 `vkUpdateDescriptorSets` + `vkCmdBindDescriptorSets` + `vkAllocateDescriptorSets` 的合计占比。
2. 用 RenderDoc 统计一帧内 set 更新次数与 bind 次数，确认与 draw 数的比例关系。
3. 统计贴图规模与 draw 数的历史增长曲线，判断是持续增长还是一次性峰值。
4. 统计目标设备 `VkPhysicalDeviceDescriptorIndexingFeatures`（`shaderSampledImageArrayNonUniformIndexing` / `descriptorBindingPartiallyBound` / `descriptorBindingUpdateAfterBind`）的覆盖率 `[SPEC]`。
5. 按 `../../02_core_mental_model/engine_architecture.md` §10 D2 的六要素完成候选对比（保持传统 + 局部优化 vs 迁移 bindless）。
6. 决策前在 1-2 个典型场景做 bindless 原型，实测 CPU 收益与低端机风险。

---

### 5. 关键证据

### Validation Layer

- 传统路径下通常无 error——这本身是关键证据：不是用法错误，是规模问题 `[TOOL]`。
- bindless 原型阶段关注：`VUID-VkDescriptorSetAllocateInfo-pSetLayouts-03044`（layout 带 UPDATE_AFTER_BIND_POOL_BIT 但 pool 未设 `VK_DESCRIPTOR_POOL_CREATE_UPDATE_AFTER_BIND_BIT`）、`VUID-vkUpdateDescriptorSets-None-03047`（更新已绑定且未执行完成的普通 descriptor set）`[SPEC]`。

### RenderDoc / AGI

- RenderDoc：单帧 1500+ 次 `vkUpdateDescriptorSets`，几乎每个 draw 绑定不同 set handle。
- RenderDoc：bindless 原型对比——单帧 set 更新从 1500+ 次降到 <20 次（只在资源加载时更新对应 slot）。
- AGI：GPU 长时间空转等待 CPU 提交，descriptor 更新链是主线程热点。
- 关键 resource：per-object descriptor set、全局 `VkDescriptorPool`、材质贴图清单。

### Log / Code

- 迁移前 CPU profiler 输出：

```text
Frame CPU budget: 16.6 ms
  └─ descriptor update + bind + alloc: 2.6 ms (15.6%)
  └─ command buffer record:           3.1 ms
  └─ culling / animation:              2.8 ms
```

- 设备覆盖率统计示例：目标机型中 Vulkan 1.2+ 且所需 feature bit 全部可用占比 96%，其余 4% 低端机需走传统回退 `[ENGINE]`。
- 决策记录（六要素摘要）：

```text
信号：descriptor 更新链占比 >15% 且随内容线性增长；贴图 ~600 且持续增长。
候选 A：保持传统模型 + 局部优化（复用 / template / 贴图 array 化）。
候选 B：迁移 bindless（大数组 + push material index）。
决策：覆盖率 96% + 贴图规模持续增长 → 迁移，但保留传统回退路径。
迁移成本：layout 全量重建 → pipeline 全量重建（engine_architecture.md §9 链 2）
        + 材质参数编码改造 + UPDATE_AFTER_BIND 同步纪律 + 双路径维护。
```

---

### 6. 根因

根因：传统 per-draw 绑定模型的 CPU 开销随 draw 数 × 材质数线性增长，当贴图规模数百、draw 数 >1000 时更新成本超过帧预算 15%——模型被用在其设计规模之外，是架构与规模不匹配，不是 API 使用错误 `[ENGINE]`。

---

### 7. 修复方案

### Minimal Fix（针对根因的最小修复）

- set 按材质预分配复用，禁止每帧重新 allocate。
- `vkUpdateDescriptorSetWithTemplate` + `pDynamicOffsets` 降低单次更新成本。
- 贴图按材质簇合并为 texture array，减少 per-draw 贴图切换。
- 目标：占比压回 10% 以下，为迁移评估争取时间；若最终决策是"不迁移"，这套修复就是终态方案。

### Structural Fix（结构性 / 防复发修复）

- 完成迁移：全局 bindless set（`PARTIALLY_BOUND | UPDATE_AFTER_BIND`，最后一个 binding 用 `VARIABLE_DESCRIPTOR_COUNT`）`[SPEC]`，shader 端 `nonuniformEXT` 索引 `[SPEC]`，draw 间只 push material index。
- 迁移成本计入决策记录：pipeline layout 兼容性破坏触发全量 pipeline 重建（预热与 cache 策略见本文档 Pipeline Cache Strategy 案例）；descriptor 更新同步纪律（未用 UPDATE_AFTER_BIND 的 binding 在 GPU 使用期间禁止 update，bindless 化后该纪律只适用于少量残留普通 set `[SPEC]`）；低端机分档回退路径的双维护。
- 传统路径保留为不支持 descriptor indexing 设备的 fallback：feature 必须运行期查询，不能假设支持 `[ANDROID]`。
- 决策写入 ADR 并含重新评估条件：低端机用户占比 >20% 且分档回退维护成本超过 CPU 收益时收窄 bindless 范围；UPDATE_AFTER_BIND hazard 频发时降级为 `UPDATE_UNUSED_WHILE_PENDING` 等弱化策略 `[ENGINE]`。

---

### 8. 修复后验证

- [ ] Validation clean（含 update-after-bind 相关校验点）。
- [ ] descriptor 更新链 CPU 占比 <5%（加载期除外）。
- [ ] 每帧 bind 次数坍缩到个位数（帧开始一次绑定）。
- [ ] 低端回退机型实测帧耗时无退化。
- [ ] pipeline 全量重建发生在加载画面内，无可感知卡顿。
- [ ] 内容规模再增长 50% 时 CPU 占比不再线性上升。

---

### 9. 经验抽象

Bindless 迁移的判据是"规模 × 覆盖率 × 团队纪律"三者同时满足，缺一即应留在传统模型：

```text
迁移信号（同时满足才启动评估）：
  descriptor 更新链占帧预算 >15% 且随内容线性增长；
  贴图规模 >100 且持续增长（或 GPU-driven 渲染已在路线图上）；
  目标设备 feature 覆盖率 ≥95%（含 shaderSampledImageArrayNonUniformIndexing）。

不应该迁移（满足任一条即留在传统模型）：
  贴图 <100 且无增长计划——局部优化即可把占比压回安全区；
  低端机（不支持 descriptor indexing 或 UPDATE_AFTER_BIND 不稳）占比 >20%；
  团队 1-3 人且无人能长期 owning UPDATE_AFTER_BIND 同步纪律与双路径维护。
```

把"新项目默认上 bindless"当最佳实践是误判：迁移成本（链 2 全量重建 + 双路径维护）只有在规模证据出现后才回本 `[ENGINE]`。

---

### 10. 预防规则

1. 绑定模型选型必须走决策链并留 ADR（信号、候选、Trade-off、决策、重新评估条件）。
2. 每季度 profile 一次 descriptor 更新链占比：超过 10% 预警，超过 15% 启动迁移评估。
3. 贴图与 draw 规模纳入技术雷达，超过阈值（贴图 >100、draw >1000）时复核 D2。
4. 设备 feature 覆盖率按发版统计更新，禁止假设"新设备一定支持"。
5. 迁移期间传统路径必须保留为可运行回退，禁止一次性切换。
6. bindless set 的 update 纪律写入 code review checklist（GPU 访问期间禁止 update 同一 element）。
7. 迁移后持续监控低端回退机型占比与维护成本，触发重新评估条件即复审决策。

---

### 11. 关联 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_indexing.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_pool.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/push_descriptor.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/cpu_overhead_symptoms.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_descriptor_updates.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`


---

## Case: RenderGraph Adoption Inflection

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / 迁移决策 / RenderGraph / Resource Lifetime |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 渲染 pass 从 5 个增长到 12 个后，手写 barrier 维护量超线性增长：同步点手写处 >50，新增一个 pass 平均要改 >3 处既有 barrier。
- resize / rotation 后重建链断裂频发：平均每个迭代 1-2 次"某资源漏重建"缺陷（depth 旧尺寸、offscreen 未重建）。
- transient 中间 RT 各自独立分配且从不复用，显存峰值逼近中低端 Android 设备 budget（如 3 GB 机型上渲染相关分配 >800 MB）。
- 偶发 `SYNC-HAZARD` 出现在 barrier 看似正确的 pass 之间——事后定位为保守 mask 掩盖了真实依赖缺口。

---

### 2. 初始上下文

- 原架构：手动资源管理——资源显式创建 / 销毁，barrier 手写 `vkCmdPipelineBarrier2`，layout 转换散布在各 pass 录制代码。
- 团队从 2 人扩展到 5 人，多人并行加 pass，同步代码没有单一 owner。
- 目标平台：桌面 + Android 中高端（多分辨率目标，aliasing 需求真实存在）。
- 无 RenderGraph；早期评估后以"编译开销 + 学习成本"为由推迟引入。

---

### 3. 初始误判

最初把系统性架构问题当一组独立 API bug 排查：

```text
resize 断裂：按资源逐个补重建（修 A 漏 B，按下葫芦浮起瓢）；
偶发 hazard：逐个收紧 barrier mask，越收越保守，frame time 反而变差；
显存峰值：按 memory leak 方向排查（结论"无泄漏，只是都不释放"）；
甚至得出"驱动对 barrier 惩罚重"的错误结论，删 barrier 后引入新 hazard。
```

逐个修复三个月，同类缺陷率没有下降。最终确认：不是某条 barrier 写错，而是手写同步的正确性成本随 pass 数超线性增长，超出人工维护能力——架构问题被当 API bug 修了三个月 `[ENGINE]`。

---

### 4. 排查路径

1. 用版本管理统计 pass 数、手写 barrier 处数、新增 pass 的平均同步点改动数。
2. 统计 resize / rotation 类缺陷的迭代频次，确认是系统性问题而非个案。
3. 用 AGI / 显存 counter 对比 transient 峰值与设备 budget。
4. 按 `../../02_core_mental_model/engine_architecture.md` §10 D5 的六要素评估：保持手动管理 vs 引入 RenderGraph。
5. 阅读本文档前述 Render Graph Resource Lifetime 案例，确认引入后的新 bug 类别（声明错误）有静态检查可控。
6. 按 `../../05_workflows/08_migration/convert_single_pass_to_render_graph.md` 做单 pass 试点迁移，实测编译开销与调试方式变化。

---

### 5. 关键证据

### Validation Layer

- 偶发 `SYNC-HAZARD-WRITE-AFTER-READ` / `SYNC-HAZARD-READ-AFTER-WRITE`：保守 mask 覆盖了多数路径，漏网依赖偶发触发。
- `VUID-VkImageMemoryBarrier-oldLayout-01197`：layout 转换的 oldLayout 与实际当前 layout 不匹配（手写维护漂移）`[SPEC]`。

### RenderDoc / AGI

- AGI：barrier stall 明显——保守 mask 造成过度同步，timeline 上 pass 间出现本不必要的等待。
- RenderDoc：resize 后 depth / offscreen 尺寸与 swapchain 不一致（重建链断裂的直接证据）。
- 关键 resource：手写 barrier 调用点、transient color / depth image、resize 依赖资源清单。

### Log / Code

- 增长曲线（版本管理统计）：

```text
pass 数:                      5  → 8  → 12
手写 barrier 处数:            18 → 37 → 56
新增 pass 平均改动同步点:     1.2 → 2.4 → 3.3
resize 类缺陷（次 / 迭代）:   0.3 → 0.9 → 1.7
```

- 显存对比：

```text
手写管理（无复用）：
  transient RT 独立分配合计: 640 MB（12 个 pass 的中间目标全量常驻）
RenderGraph 编译后（aliasing）：
  峰值占用: 210 MB（生命周期不重叠区间复用）
```

- 决策记录（六要素摘要）：

```text
信号：pass 12 且持续增长；barrier 手写 >50 处；新增 pass 改动 >3 个同步点；
      resize 断裂每迭代 >1 次；transient 显存峰值逼近移动端 budget。
候选 A：保持手动 + 重构（集中 barrier 辅助函数 + 重建 checklist + RT 池化）。
候选 B：引入 RenderGraph（声明式 pass + 编译期推导 barrier / layout / alias）。
决策：团队 5 人、多平台 aliasing 需求真实 → 迁移，分 3 个里程碑逐 pass 迁移。
迁移成本：编译器引入 + 全部 pass 改声明式 + 调试间接层 + 学习曲线（5 人 × 2-4 周）。
```

---

### 6. 根因

根因：手写资源生命周期与同步的正确性成本是 O(pass²)——每个 pass 与上下游的依赖全部人工维护，当 pass 数超过 ~8-10 后维护成本与断裂频次超线性增长，超出手动管理架构的设计点 `[ENGINE]`。

---

### 7. 修复方案

### Minimal Fix（针对根因的最小修复）

- barrier 收敛到单一辅助模块（集中 mask / stage 计算），禁止散写在 pass 录制代码里。
- swapchain 重建清单固化为 checklist + debug 尺寸一致性断言。
- transient RT 按尺寸 / 格式粗池化复用，显存峰值先降一档。
- 若最终决策是"不引入"（demo / 工具渲染器），这套修复即终态方案。

### Structural Fix（结构性 / 防复发修复）

- 引入 RenderGraph：pass 声明 read/write，编译期推导 barrier、layout、transient 分配与 alias（内部机制见 `../../02_core_mental_model/render_graph_resource_lifetime.md`，此处不重复）。
- 迁移成本计入决策记录：graph 编译器实现 / 引入成本；全部 pass 改声明式；调试间接层——bug 从"barrier 写错"变为"声明写错"（形态见本文档 Render Graph Resource Lifetime 案例）；团队学习曲线。
- 分阶段迁移：先 shadow / 后处理等叶子 pass，再 GBuffer 主链；每阶段 Validation + 截图回归。
- 重新评估条件写入 ADR：RG compile CPU 时间进入帧预算 top3 → 加编译缓存（帧间复用编译结果）；声明类 bug 每迭代 >2 次 → 收窄托管范围（关键 pass 保留手写）`[ENGINE]`。

---

### 8. 修复后验证

- [ ] Validation clean（synchronization validation 开启）。
- [ ] 新增 pass 只声明读写，同步点改动数为 0。
- [ ] resize / rotation 经 imported 资源自动传播，断裂类缺陷归零。
- [ ] transient 显存峰值下降 50% 以上（aliasing 生效）。
- [ ] RG compile CPU 耗时未进入帧预算 top3。
- [ ] 声明类错误有静态检查 / 断言兜底。

---

### 9. 经验抽象

RenderGraph 的引入拐点是"pass 数量级 × 多平台需求 × 团队规模"的组合判据：

```text
引入信号（同时满足）：
  pass ≥8 且持续增长；手写 barrier >50 处；新增 pass 平均改动 >3 个同步点；
  resize 重建链断裂每迭代 ≥1 次；transient 显存峰值逼近设备 budget；
  多平台目标（移动端 aliasing 收益真实存在）；团队 ≥3 人需要统一声明协议。

不应该引入（满足任一条）：
  demo / 工具渲染器——编译开销与间接层成本大于收益；
  pass <8 且增长停滞——集中 barrier 辅助 + checklist 即可维护；
  团队 1-2 人——学习曲线与间接调试成本不划算；
  跨帧复杂依赖为主（history buffer 多）——RG 只托管帧内，跨帧仍需外部 owner。
```

RenderGraph 解决的是"规模化的同步正确性与显存峰值"，规模不到时它只是把 bug 从 barrier 挪到声明 `[ENGINE]`。

---

### 10. 预防规则

1. pass 数纳入技术雷达：≥8 或手写 barrier >50 处即触发 D5 复评。
2. 新增 pass 的同步点改动数纳入版本管理统计，>3 处即预警。
3. resize / rotation 断裂类缺陷按系统性问题上报（频次 >1 次/迭代），禁止只当个案修。
4. transient 显存峰值按设备分档监控，接近 budget 即评估 alias（手动池化或 RG）。
5. 引入 RG 后，declared lifetime 与实际使用区间必须有静态校验兜底。
6. RG compile CPU 耗时纳入帧预算 top 监控。
7. 跨帧资源必须 imported 且显式声明外部 owner，禁止依赖 RG 托管跨帧生命周期。

---

### 11. 关联 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`

---

### 13. 关联 Workflow

- `../../05_workflows/08_migration/convert_single_pass_to_render_graph.md`
- `../../05_workflows/07_optimization/optimize_barriers.md`
- `../../05_workflows/01_renderer_setup/create_renderer_from_scratch.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`


---

## Case: Resource Lifetime Split

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / 迁移决策 / Resource Lifetime / 资源分组 |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 单一全局资源池 + 2-3 frames-in-flight 下，偶发 `SYNC-HAZARD-WRITE-AFTER-READ`：CPU 复用 / 重写某资源时 GPU 仍在读取（per-frame UBO slice、缓存的 descriptor set 被池"提前回收复用"）。
- 显存峰值 ≈ 全部资源之和：中间 RT、加载资源、每帧资源全量常驻，中端 Android 机型逼近 budget。
- resize 后随机漏重建：依赖 swapchain 尺寸的资源与普通资源混在池中，重建入口分散。
- 内容卸载后偶发 use-after-free 风险：deferred destruction 靠人肉记录 fence，遗漏即悬空。

---

### 2. 初始上下文

- 原架构：单一全局 ResourceCache（key → `VkImage` / `VkBuffer` 句柄），所有资源一视同仁，复用 / 回收 / 重建只有一套策略。
- 2-3 frames-in-flight；UBO 无 per-frame 分段（直接从池里取"当前可用"的 buffer 写入）。
- 中间 RT（GBuffer / shadow map / bloom 链）从不销毁也从不复用。
- 桌面开发为主，Android 真机回归较晚；资源总数 ~300。

---

### 3. 初始误判

最初按四条独立 API bug 线索排查：

```text
SYNC-HAZARD：当成 fence 等待逻辑写错（按本文档 Per Frame Resource Design 案例
            式局部修复，修一个冒一个）；
显存峰值：按 memory leak 方向排查（结论"无泄漏，只是都不释放"）；
resize 漏重建：当个案补丁（重建函数里补一个是一个）；
use-after-free：当悬空指针 bug 修（统一延迟 1 帧删除，仍偶发）。
```

四类症状各自修复、各自复发。最终确认：单一资源池假设"所有资源生命周期相同"，而真实渲染器的资源有四种完全不同的生命周期——池模型本身失效，个案修复无法收敛 `[ENGINE]`。

---

### 4. 排查路径

1. 把出现 hazard 的资源列清单，按"谁写入、谁消费、何时复用"逐项标注。
2. 统计池内资源的真实生命周期分布（创建后存活帧数直方图）。
3. 对比显存峰值与"只有 active 资源驻留"的理论值差值。
4. 按 `../../02_core_mental_model/engine_architecture.md` §10 D6 的四类判据（Persistent / Per-frame / Transient / Swapchain-dependent）逐资源归类。
5. 对比归类结果与现行池行为，列出每个差异点（即潜在 bug 点）。
6. 制定分批迁移顺序：Per-frame 先拆（hazard 最痛）→ Swapchain-dependent（重建链）→ Transient（alias 收益）→ Persistent（引用计数）。

---

### 5. 关键证据

### Validation Layer

- `SYNC-HAZARD-WRITE-AFTER-READ`：池复用的 UBO slice / descriptor set 被 CPU 重写时 GPU 仍在读。
- `VUID-vkResetCommandBuffer-commandBuffer-00045`：池提前复用的 command buffer 仍处于 pending execution `[SPEC]`。

### RenderDoc / AGI

- RenderDoc：第 N 帧 uniform 内容与提交时不一致——被池"提前复用"的下一帧数据覆盖。
- AGI：资源分配 / 复用区间与 GPU 访问区间重叠的资源清单。
- 关键 resource：全局 ResourceCache、per-frame UBO slice、descriptor set cache、transient RT。

### Log / Code

- 归类审计表（节选）：

```text
资源                   池内现状     应归类                错分类信号
scene UBO slice        全局复用    Per-frame             SYNC-HAZARD
GBuffer / shadow map   常驻不销毁  Transient             显存峰值虚高
bloom 中间 RT           常驻不销毁  Transient             显存峰值虚高
depth / MSAA resolve   混在池中    Swapchain-dependent    resize 漏重建
mesh / 贴图            常驻        Persistent            （正确，但与 transient 混算 budget）
```

- 显存对比：

```text
单池（全部常驻）：
  peak = persistent + 全部 transient + per-frame 全量 ≈ 1.9 GB
四类拆分后：
  peak = persistent + alias 后 transient 峰值 + N × per-frame slice ≈ 0.8 GB
```

---

### 6. 根因

根因：单一全局资源池把四类生命周期（Persistent / Per-frame / Transient / Swapchain-dependent）的资源混同管理，复用、重建、回收策略只有一套，规模与并行度增长后每类资源以其特有故障形态反复出错——是模型假设失效，不是单个资源的同步 bug `[ENGINE]`。

---

### 7. 修复方案

### Minimal Fix（针对根因的最小修复）

- 出 hazard 的资源临时移入 retire 队列：按 fence 延迟 frames-in-flight 数量帧后回收，禁止立即复用。
- resize 重建入口收敛为单一事件函数（先解决最痛的漏重建路径）。
- 该止血方案的缺陷：逐资源打补丁，新增资源仍可能漏——只作为拆分完成前的过渡。

### Structural Fix（结构性 / 防复发修复）

- 按四类拆分（归类判据见 D6 判据表）：
  - Persistent：随内容加载 / 卸载，引用计数归零后延迟销毁。
  - Per-frame：随 FrameContext 成套拥有，同索引复用前等本索引 fence（结构见本文档 Per Frame Resource Design 案例）。
  - Transient：last-use 后回收，参与 alias（形态见本文档 Render Graph Resource Lifetime 案例）。
  - Swapchain-dependent：成组注册，recreate 时整组重建（结构见本文档 Swapchain Dependent Resource Group 案例）。
- 迁移成本计入决策记录：全量资源归类审计（本例 ~300 项）、创建调用从散落收敛到注册 API、跨模块引用更新（约 3 人 × 4 周）。
- debug 构建加生命周期断言：per-frame 写入必须在对应 fence signal 之后；transient 回收必须在 last-use 之后；swapchain 组尺寸一致性检查。
- 重新评估条件写入 ADR：错分类信号每迭代出现 >2 次 → 补静态检查 / 收紧断言；无需"回到单池"——单池只在 demo 规模成立 `[ENGINE]`。

---

### 8. 修复后验证

- [ ] Validation clean（synchronization validation 连续运行 30 分钟）。
- [ ] SYNC-HAZARD 归零——分类正确后串帧竞争不存在，而不是概率降低。
- [ ] 显存峰值降到 active 资源量级（本例 1.9 GB → 0.8 GB）。
- [ ] resize / rotation 后四类资源各自符合预期（重建 / 保留 / 回收）。
- [ ] 内容卸载后无 use-after-free（引用计数 + 延迟销毁双保险）。
- [ ] 新增资源必须声明四类之一才能进入创建 API（review 强制）。

---

### 9. 经验抽象

四类拆分是"多 frame-in-flight + 真实内容规模"的必然结构，但存在不值得拆的下限：

```text
需要拆分（满足任一即应启动）：
  frames-in-flight >1（单池串帧 hazard 是必然，不是概率）；
  transient 中间目标 ≥3 个且显存有压力；
  resize / rotation 是支持场景；
  资源总数 >20。

不需要拆分（全部满足才可停在单池）：
  demo / 原型；单 frame-in-flight（CPU 每帧等 GPU 完成）；
  资源总数 <20 且无 resize 需求——一个数组 + 销毁顺序检查即可。
```

归类错误的代价按类别分化：Per-frame 错归是串帧 hazard、Transient 错归是显存峰值、Swapchain-dependent 错归是 resize 断裂——看到哪类信号就查哪类归类 `[ENGINE]`。

---

### 10. 预防规则

1. 资源创建必须声明四类生命周期之一，未声明不得进入创建 API（code review 强制）。
2. per-frame 资源禁止进入全局复用路径（fence 断言兜底）。
3. transient 资源参与 alias 前必须校验生命周期区间不重叠。
4. swapchain-dependent 资源成组注册，recreate 单一入口传播。
5. persistent 卸载走引用计数 + in-flight 完成后销毁，禁止立即销毁。
6. debug 构建输出资源生命周期分布（创建 / 最后使用 / 回收帧号），CI 校验归类一致性。
7. 显存峰值按设备分档监控，与 active 资源理论值对比，持续偏差即查归类。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/03_command_buffer/frames_in_flight.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/memory_leak.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`

---

### 13. 关联 Workflow

- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`
- `../../05_workflows/01_renderer_setup/setup_swapchain.md`


---

## Case: Async Compute Backlash

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / 迁移决策 / Queue / Async Compute |
| 平台 | 通用 / Android |
| 严重程度 | P2 |
| 来源等级 | `[CASE] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

- 为追求 overlap 把粒子模拟 + 两级模糊迁到独立 compute queue 后，frame time 反升：9.6 ms → 11.2 ms（同场景、同分辨率、多次采样取均值）。
- AGI GPU timeline：空泡没有消失，而是从 graphics 段转移到 compute 提交边界——graphics 等 semaphore、compute 等 ownership transfer，等待链整体变长。
- 部分移动设备退化更明显：compute queue 与 graphics 争抢共享执行单元，桌面正常、移动恶化。

---

### 2. 初始上下文

- 原架构：单 queue 顺序提交，compute 任务（粒子模拟、模糊）在 graphics queue 内用 barrier 串行衔接。
- 迁移动机：AGI 显示粒子 + 模糊合计占 ~2.1 ms，希望与 graphics 重叠执行。
- 跨 queue 同步最初用 binary semaphore 链 + fence，后改为 timeline semaphore（value 单调递增）`[SPEC]`。
- compute 负载与 graphics 强依赖交织：模糊输出被同帧后续 pass 直接消费，cross-queue barrier 边多。

---

### 3. 初始误判

最初把架构选型问题当 bug 排查：

```text
以为是 barrier mask 过宽，逐个收窄（frame time 只降 0.2 ms，问题依旧）；
以为是驱动多 queue 调度差，向厂商报 bug（桌面正常、移动退化，方向被带偏）；
以为是 compute shader 在新 queue 上变慢（dispatch 单测耗时不变）；
以为是 timeline value 配置错误（Validation 全绿）。
```

最后在 AGI timeline 上量出真相：overlap 收益约 1.1 ms，同步等待 + queue 争抢新增约 2.7 ms——净负。根因是把"async compute 一定更快"当成了默认前提，没有先验证收益条件 `[ENGINE]`。

---

### 4. 排查路径

1. AGI 抓迁移前后 GPU timeline（同场景），量化三项：overlap 面积、空泡位置、semaphore 等待链长度。
2. frame time 前后对比（多次采样取均值，排除抖动）。
3. 统计 cross-queue barrier 边数量与 ownership transfer 次数（负载隔离度的量化）。
4. 桌面与移动各测一组，定位驱动差异。
5. 按 `../../02_core_mental_model/engine_architecture.md` §10 D4 复核收益条件：重叠余量、隔离度是否真实满足。
6. 做回退实验：关闭 async compute 开关（保留代码路径），确认 frame time 恢复。

---

### 5. 关键证据

### Validation Layer

- 无 error——barrier / semaphore 用法正确，这本身排除了"API bug"方向，把排查引向 queue 模型选型 `[TOOL]`。

### RenderDoc / AGI

- AGI timeline 前后对比（同场景均值）：

```text
单 queue（迁移前）：
  graphics: 8.1 ms（含 1.2 ms 空泡，等 compute 串行衔接）
  compute:  1.5 ms
  frame:    9.6 ms

async compute（迁移后）：
  graphics: 7.0 ms（其中 2.3 ms 在等 compute 的 semaphore）
  compute:  1.5 ms（其中 0.4 ms 在等 ownership transfer）
  frame:   11.2 ms（等待链 + queue 争抢净增 1.6 ms）
```

- 空泡转移形态：迁移前空泡集中在 graphics 段末尾（等 compute 完成）；迁移后空泡散布在 compute 提交边界（等 semaphore / transfer）——空泡转移而非消失是关键证据。
- 移动端补充：Adreno / Mali 上 compute queue 与 graphics 共享执行单元，并行段相互拖慢 `[VENDOR]`。
- 关键 resource：compute queue 提交批次、timeline semaphore、跨 queue barrier（release / acquire 对）。

### Log / Code

- 回退决策记录（六要素摘要）：

```text
信号：frame time 9.6 → 11.2 ms；空泡转移而非消失；等待链变长。
候选 A：回退单 queue（保留 async 代码路径，关开关）。
候选 B：继续优化 async（收窄 transfer 范围、合并批次、减少依赖边）。
决策：先回退止血（A）；保留代码路径与运行时开关。
      B 的优化项进 backlog，满足重新评估条件再启用。
重新评估条件：AGI 显示 graphics 与 compute 互不重叠且合计 >30% frame time，
            且负载隔离度提升（模糊跨帧消费、粒子输入输出独立）后再试。
```

---

### 6. 根因

根因：该负载下同步开销（ownership transfer + 跨 queue 等待链）与 queue 间执行单元争抢之和，超过了 compute 与 graphics 可重叠的收益——async compute 的收益上限是串行路径中 compute 段时长，而强依赖交织的负载隔离度低，重叠余量不足以覆盖新增开销 `[ENGINE]`。

---

### 7. 修复方案

### Minimal Fix（针对根因的最小修复）

- 回退：async compute 开关默认关闭，回单 queue 提交；代码路径保留（CI 维持双路径编译）。
- timeline semaphore 基础设施保留——对 frames-in-flight 进度追踪仍有简化价值。

### Structural Fix（结构性 / 防复发修复）

- 把 async compute 做成运行时 / 配置级开关 + 设备分档（桌面可试开、移动保守默认关），禁止编译期常量。
- 提高负载隔离度（重新评估的前提工程）：模糊改为"本帧 compute、下帧消费"的跨帧延迟模式，减少即时依赖边；粒子模拟输入输出独立，不与 graphics 中间资源交织。
- 建立启用判据并写入 ADR：AGI 显示 graphics 与 compute 互不重叠且合计 >30% frame time；barrier 边少（隔离度高）；桌面驱动多 queue 支持成熟；移动端按厂商实测分档 `[ENGINE]` `[ANDROID]` `[VENDOR]`。
- 重新评估流程固化：负载结构大改后用开关做 A/B 实测再决定默认值，不沿用旧结论。

---

### 8. 修复后验证

- [ ] 回退后 frame time 恢复 9.6 ms 量级（多次采样）。
- [ ] AGI timeline 回到单 queue 串行形态，无跨 queue 等待链。
- [ ] async 路径开关可运行（CI 双路径编译 + 冒烟测试通过）。
- [ ] 移动端分档生效（低端默认单 queue）。
- [ ] 重新评估条件与判据写入 ADR，并链接 timeline 数据存档。

---

### 9. 经验抽象

async compute 不是默认优化，是条件优化；收益被物理封顶，成本随依赖复杂度增长：

```text
收益上限 = 串行路径中 compute 段的时长（本例 ~1.5 ms）。
新增成本 = ownership transfer + 跨 queue 等待链 + 执行单元争抢（本例 ~2.7 ms）。

启用条件（同时满足）：graphics 与 compute 互不重叠且合计 >30% frame time；
                     barrier 边少（负载隔离度高）；桌面为主或移动端分档实测通过。
不该启用（满足任一）：compute 占比 <20% frame time；与 graphics 强依赖交织；
                     目标设备驱动多 queue 实现退化（部分移动端）。
回退信号：frame time 反升；空泡转移而非消失；等待链变长 → 关开关回退，
         不是继续微调 barrier。
何时该保留：开关 + 双路径保留，负载结构变化后按判据重新评估。
```

"空泡从一段转移到另一段"是同步开销吃掉 overlap 收益的典型 timeline 形态，见到即应怀疑 queue 模型选型 `[ENGINE]`。

---

### 10. 预防规则

1. async compute 引入前必须走 D4 决策链：先量重叠余量与隔离度，再写代码。
2. async 路径必须运行时可关闭，禁止编译期写死。
3. 引入后一周内用 AGI 做 A/B 实测，frame time 反升立即回退开关。
4. "空泡转移而非消失"列入 timeline 检查标准项。
5. 移动端按设备分档默认保守，厂商驱动差异实测后再放开 `[ANDROID]` `[VENDOR]`。
6. 负载结构大改（新增 compute 任务 / 依赖重排）后重新评估开关默认值。
7. 跨 queue 资源的 ownership 状态集中跟踪，transfer 边数量写入决策记录。

---

### 11. 关联 API 卡片

- `../../03_api_manual/08_synchronization/timeline_semaphore.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`
- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`

---

### 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_frame_time.md`
- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`


---

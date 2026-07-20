# Debug Playbook: Pipeline Creation / Startup Time

> 合并自 2 个原 playbook 文件。

---

## Debug Playbook: Pipeline Creation Stutter

### 0. 适用范围

### 适用

- 运行过程中首次出现某个 shader 变体或材质时发生明显卡顿。
- 切换场景、换装、进入新区域时帧时间突然尖峰。
- 帧率曲线呈现周期性或事件触发的尖刺，与 pipeline 创建时间吻合。
- 已启用 `VkPipelineCache` 但仍出现未命中。

### 不适用

- 持续稳定的低帧率（优先排查 GPU / CPU frame time）。
- 与 shader 编译无关的 IO 或网络卡顿。
- 启动阶段的长时间加载（优先排查 startup time）。

---

### 1. 现象

- 游戏中特定动作或视角切换后出现一次性或间歇性卡顿。
- Profiler 显示尖峰出现在 `vkCreateGraphicsPipelines` 或 `vkCreateComputePipelines` 调用处。
- 同一设备第二次进入同一场景时卡顿消失或明显减轻。
- pipeline cache 文件为空或大小异常。
- 关闭异步编译后卡顿从分散变为集中在加载时。

---

### 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Pipeline cache 未命中或未持久化 | 首次运行卡顿，第二次减轻；cache 文件为空或解析失败 | Pipeline Cache |
| P0 | 运行期首次创建 shader 变体 | 卡顿与特定材质 / 变体首次出现强相关 | Shader Module / Pipeline |
| P0 | 未使用异步 pipeline 创建 | `vkCreateGraphicsPipelines` 阻塞渲染线程 | Pipeline |
| P1 | Graphics Pipeline Library 未拆分或拆分不完整 | 即使部分状态变化也需要重建完整 pipeline | Pipeline |
| P1 | Shader 编译时间过长 | shader 规模大、分支多、优化器耗时高 | Shader Module |
| P2 | Pipeline cache 跨版本失效 | 应用更新后 cache 命中率骤降 | Pipeline Cache |
| P2 | 多线程创建 pipeline 时竞争 | 创建热点集中在单线程 | Pipeline |

---

### 3. 快速验证路径

1. **用 Profiler 抓取卡顿帧**，确认尖峰是否在 `vkCreate*Pipelines`。`[TOOL]`
2. **删除并重建 pipeline cache 文件**：对比首次运行与后续运行的卡顿情况。`[TOOL]`
3. **统计运行期 pipeline 创建调用次数**：确认是否有预期之外的创建。`[TOOL]`
4. **强制所有变体在加载时创建**：观察卡顿是否从运行期转移到加载期。`[TOOL]`
5. **检查 pipeline cache 序列化数据**：确认是否写入磁盘并在启动时读取。`[TOOL]`
6. **验证 Graphics Pipeline Library 支持情况**：查看 `VK_EXT_graphics_pipeline_library` 是否启用。`[TOOL]`

---

### 4. Vulkan 对象链路排查

```text
Shader Module
→ Pipeline Layout
→ Pipeline Cache
→ vkCreateGraphicsPipelines / vkCreateComputePipelines
→ Pipeline Object
→ Command Buffer Bind
```

逐项检查：

- Pipeline cache 是否在 `vkCreateDevice` 后创建并在 `vkDestroyDevice` 前保存。`[SPEC]`
- `VkPipelineCacheCreateInfo::initialDataSize` / `pInitialData` 是否正确读取上次持久化数据。`[SPEC]`
- 是否所有 shader 变体组合在运行期才被首次发现。`[ENGINE]`
- 是否启用了 `VK_PIPELINE_CREATE_DELAY_CREATE_BIT_EXT` 或异步创建扩展。`[SPEC]`
- Graphics Pipeline Library 是否将 vertex input、fragment output、pre-rasterization、fragment shader 拆分为独立 library pipeline。`[SPEC]`
- Pipeline 创建是否集中在单线程，导致 CPU 核心未充分利用。`[ENGINE]`

---

### 5. 高频根因

1. 未启用 `VkPipelineCache` 或 cache 未持久化到磁盘，每次启动重新编译。`[ENGINE]`
2. 大量 shader 变体在运行期按需创建，用户首次触发时卡顿。`[ENGINE]`
3. 所有 pipeline 在主线程同步创建，阻塞渲染循环。`[ENGINE]`
4. 未使用 Graphics Pipeline Library，任何 rasterizer state 变化都触发完整 pipeline 重建。`[ENGINE]`
5. Pipeline cache 文件版本未与应用 / shader 版本绑定，更新后使用过期 cache 导致未命中。`[ENGINE]`
6. 对很少使用的变体也做全量预编译，浪费启动时间且无法覆盖运行时变体。`[HEUR]`

---

### 6. 修复方案

### 最小修复

- 启用 `VkPipelineCache` 并在应用退出时把 cache 数据保存到磁盘，启动时读取。`[SPEC]`（适用条件：所有支持 Vulkan 的设备；cache 数据需与 shader / 应用版本匹配。）
- 把运行期首次遇到的变体在加载画面或后台线程预创建。`[ENGINE]`（适用条件：变体集合可枚举或预测；对开放世界等不可预测场景需结合 streaming。）
- 将 pipeline 创建移到独立线程，主线程继续渲染并使用 fallback pipeline 或简单 shader。`[ENGINE]`（适用条件：可接受新变体前几帧使用低质量渲染；需要处理创建完成后的切换同步。）

### 稳定修复

- 使用 `VK_EXT_graphics_pipeline_library` 拆分 pipeline，让状态变化只影响局部 library，减少组合爆炸。`[SPEC]`（适用条件：设备支持该扩展；需处理 library pipeline 的 linking 开销和兼容 layout。）
- 建立 shader 变体数据库，离线枚举所有可能变体并在构建或安装时预编译。`[ENGINE]`（适用条件：变体数量可控；对 UGC 或运行时生成 shader 不适用。）
- 实现 pipeline 编译线程池和优先级队列，优先编译当前帧需要的变体。`[ENGINE]`（适用条件：运行期变体较多且无法完全预编译。）
- 对 hot path 的材质变体做 warmup，在场景加载时同步创建关键变体。`[ENGINE]`（适用条件：关键变体集合已知且数量有限。）

### 工程化修复

- CI 统计各场景首次进入的 pipeline 创建数量与耗时，设定 budget。`[TOOL]`
- 对 cache 文件做版本校验（shader hash + 应用版本 + driver 版本），失效时自动重建。`[ENGINE]`
- 实现 pipeline 创建热点分析，自动识别并预编译高频变体。`[ENGINE]`
- 对低端设备启用更激进的变体裁剪和简化 shader，减少编译时间。`[ENGINE]`

---

### 7. 回归验证

- [ ] 首次进入场景的 pipeline 创建尖峰消失或降至预算内。
- [ ] Pipeline cache 文件在退出后正确生成并在下次启动时加载。
- [ ] 关键变体预创建后对应场景无卡顿。
- [ ] 异步创建不引入资源竞争或 validation error。
- [ ] Graphics Pipeline Library 拆分后渲染结果一致。
- [ ] 应用更新后 cache 版本校验正确，不会使用过期 cache。
- [ ] 低端设备与高端设备均通过场景切换压力测试。

---

### 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

### 9. 工具证据

### Validation Layer

- 关注 `VUID-VkPipelineCacheCreateInfo-initialDataSize-00769` 等 cache data 相关错误。`[TOOL]`
- 关注 pipeline layout 与 shader 接口不匹配的 VUID。`[TOOL]`
- 关注 Graphics Pipeline Library 相关 `VK_EXT_graphics_pipeline_library` 的独立 pipeline layout 限制。`[TOOL]`

### RenderDoc

- 查看卡顿帧 event browser 中是否有大量 `vkCreateGraphicsPipelines` 调用。`[TOOL]`
- 查看创建的 pipeline 数量、shader 变体数量是否与预期一致。`[TOOL]`
- 查看 pipeline state 中 shader 是否包含大量变体组合。`[TOOL]`

### AGI / Android

- 关注 `Pipeline Creations` counter 和 CPU 时间轴上 `vkCreate*Pipelines` 耗时。`[TOOL]`
- 查看卡顿是否集中在场景切换或材质首次出现时。`[TOOL]`
- 查看 `Pipeline Cache Hit Rate`（如 AGI 提供）。`[TOOL]`

### logcat

- 搜索 `PipelineCache`、`shader compile`、`pipeline create` 等驱动日志。`[ANDROID]`
- 检查是否因 shader 编译触发 watchdog 或 ANR。`[ANDROID]`

---

### 10. Android 分支

Android 上 pipeline 创建受驱动实现和功耗影响大，额外检查：

1. **Surface 有效性前提**：异步创建 pipeline 时 `ANativeWindow` 仍可能变化，确保新 pipeline 不会绑定到已销毁的 swapchain framebuffer。`[ANDROID]`
2. **后台恢复**：应用进入后台后再回到前台，部分驱动会丢弃 pipeline cache，需从持久化 cache 恢复。`[ANDROID]`
3. **低端设备编译时间**：Android 设备 shader 编译器差异大，低端设备可能需要更长的预编译时间或更少的变体。`[ANDROID]`
4. **Tile-based GPU 的 GPL 收益**：Adreno / Mali 对 vertex input 和 fragment output 拆分敏感，需实测验证。`[ANDROID]`
5. **Cache 文件位置**：Android 上 pipeline cache 应放在应用私有目录，避免权限问题。`[ANDROID]`

---

### 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - Profiler 抓取的卡顿帧，标注 `vkCreate*Pipelines` 耗时。
   - 每帧 / 每场景 pipeline 创建次数。
   - Pipeline cache 文件大小、加载与保存逻辑。
   - 是否启用 `VK_EXT_graphics_pipeline_library` 或异步创建扩展。
   - Shader 变体数量及首次触发场景。
   - 设备型号、GPU、驱动版本、Android 版本。
3. 给出最小验证路径：启用 cache → 预创建关键变体 → 异步创建 → 拆分 Graphics Pipeline Library。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 pipeline cache、graphics pipeline library 或异步创建规范。
   - `[TOOL]` 若 Profiler 已明确 pipeline 创建是尖峰来源。
   - `[ENGINE]` 若基于预编译、异步加载等工程经验推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 Android 驱动 cache 行为或 tile-based GPU 特性。


---

## Debug Playbook: Startup Time High

### 0. 适用范围

### 适用

- 应用从点击图标到首帧渲染时间过长。
- 冷启动时间明显高于目标预算（如 > 3s）。
- 启动阶段 GPU / CPU 长时间处于高负载，界面无响应。
- 启动时间随 shader 数量、资源规模增长明显。

### 不适用

- 运行期卡顿（优先排查 frame time / pipeline creation stutter）。
- 网络 / 服务器配置 / 授权验证导致的启动慢。
- 系统级冷启动调度或 IO 缓存未命中。

---

### 1. 现象

- 应用启动黑屏或 logo 停留时间过长。
- Profiler 显示启动阶段大量时间花在 shader 编译、pipeline 创建或资源加载。
- 首次安装启动明显慢于后续启动。
- 删除 pipeline cache 后启动时间回到首次安装水平。
- 低端设备启动时间是高端设备的数倍。

---

### 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Shader 编译与 pipeline 创建 | Profiler 显示 `vkCreate*Pipelines` / shader 编译占启动时间大头 | Pipeline / Shader Module |
| P0 | 资源加载与解压串行 | 大量 texture / mesh / 配置文件在主线程同步加载 | Buffer / Image / File IO |
| P0 | Pipeline cache 未预热或持久化 | 首次启动慢，后续启动快；cache 文件未生成 | Pipeline Cache |
| P1 | 资源尺寸 / 格式过大 | texture 分辨率、格式、mipmap 层级超出启动预算 | Image / Sampler |
| P1 | 同步等待过多 | 启动阶段频繁 `vkDeviceWaitIdle` 或单线程加载 | Synchronization |
| P2 | 不必要的全量预创建 | 对所有 shader 变体做 warmup，远超首屏需要 | Pipeline |
| P2 | 启动阶段初始化顺序低效 | 渲染器初始化阻塞在资源下载或模块加载 | Engine Initialization |

---

### 3. 快速验证路径

1. **用 Profiler 抓取启动过程**，定位耗时最高的阶段。`[TOOL]`
2. **清空 pipeline cache 后对比启动时间**：确认 cache 预热效果。`[TOOL]`
3. **跳过资源加载**：用占位资源启动，观察启动时间变化。`[TOOL]`
4. **统计启动阶段 shader 编译和 pipeline 创建数量**。`[TOOL]`
5. **检查资源加载是否串行**：确认 IO 线程、解压线程、GPU upload 线程是否并行。`[ENGINE]`
6. **分析首屏实际需要的最小资源集合**。`[HEUR]`

---

### 4. Vulkan 对象链路排查

```text
Instance / Device Create
→ Surface / Swapchain Create
→ Pipeline Cache Load
→ Shader Module Create
→ Pipeline Create (Graphics / Compute)
→ Buffer / Image Resource Load & Upload
→ Descriptor Set Prepare
→ First Frame Submit
```

逐项检查：

- `vkCreateInstance` / `vkCreateDevice` 是否加载了过多未使用的 extension / layer。`[TOOL]`
- Pipeline cache 是否在启动时从磁盘读取并传递给 `vkCreatePipelineCache`。`[SPEC]`
- Shader 是离线预编译为 SPIR-V 还是运行期编译，后者会显著增加启动时间。`[ENGINE]`
- Pipeline 创建是否为同步全量创建，是否可以延迟或异步。`[ENGINE]`
- 资源加载是否分关键路径 / 非关键路径，非关键路径是否可后台加载。`[ENGINE]`
- Texture / buffer 的 upload 是否使用 staging buffer 并并行化 copy / layout transition。`[SPEC]`

---

### 5. 高频根因

1. 启动时同步编译所有 shader 变体并创建所有 pipeline，阻塞主线程。`[ENGINE]`
2. Pipeline cache 未持久化，每次冷启动都重新编译。`[ENGINE]`
3. 大尺寸 texture / mesh 在主线程同步读取、解压、上传。`[ENGINE]`
4. 资源加载、解压、GPU upload 串行执行，未利用多核 CPU 和异步 transfer queue。`[ENGINE]`
5. 创建了当前屏幕不需要的 pipeline 或加载了当前场景不需要的资源。`[HEUR]`
6. 启动阶段频繁调用 `vkDeviceWaitIdle` 等待每个资源 upload 完成。`[ENGINE]`

---

### 6. 修复方案

### 最小修复

- 启用并持久化 `VkPipelineCache`，启动时读取上次保存的 cache 数据。`[SPEC]`（适用条件：所有支持 Vulkan 的设备；cache 数据需与 shader / 应用版本匹配。）
- 把 shader 预编译为 SPIR-V，避免运行期从 GLSL/HLSL 编译。`[ENGINE]`（适用条件：所有项目；运行时编译仅用于特殊工具场景。）
- 只创建首屏必需的 pipeline，其余延迟到首次使用时异步创建。`[ENGINE]`（适用条件：可接受后续场景首次进入时的轻量编译；需配合 loading 提示。）
- 把资源加载放到后台线程，主线程只等待首屏最小资源集。`[ENGINE]`（适用条件：资源之间存在依赖关系可解耦；需处理线程同步。）

### 稳定修复

- 实现异步资源加载系统：IO → 解压 → upload 到 staging buffer → 提交 copy command → 通知主线程可用。`[ENGINE]`（适用条件：资源数量大或尺寸大；需要管理资源生命周期和引用计数。）
- 对关键变体在启动时同步 warmup，非关键变体按优先级队列后台编译。`[ENGINE]`（适用条件：关键渲染路径明确，非关键变体可延迟。）
- 使用 dedicated transfer queue 做 buffer / image upload，与 graphics queue 并行。`[SPEC]`（适用条件：设备存在独立的 transfer queue family；否则使用异步 graphics submit。）
- 压缩 texture 格式（如 ASTC/ETC/BC）并预生成 mipmap，减少 IO 和 upload 量。`[HEUR]`（适用条件：目标 GPU 支持对应压缩格式；需注意 alpha 通道质量。）

### 工程化修复

- CI 集成启动时间测试，监控各阶段耗时回归。`[TOOL]`
- 建立首屏资源清单和启动预算，超出时自动告警。`[ENGINE]`
- 对 cache 文件做版本校验（shader hash + 应用版本 + driver 版本），失效时重建并提示用户。`[ENGINE]`
- 对低端设备启用低分辨率启动资源包，启动后再后台替换高清资源。`[ENGINE]`

---

### 7. 回归验证

- [ ] 冷启动时间回到预算内。
- [ ] 删除 pipeline cache 后首次启动仍在可接受范围或明确提示。
- [ ] 后续启动因 cache 命中明显快于首次。
- [ ] 首屏渲染正确，无资源缺失或 pink/black 纹理。
- [ ] 低端设备启动时间不劣化到无法接受。
- [ ] 后台资源加载不阻塞主线程交互响应。
- [ ] 应用更新后 cache 版本校验正确，自动重建。

---

### 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

### 9. 工具证据

### Validation Layer

- 关注 `VUID-VkPipelineCacheCreateInfo-initialDataSize-00769` 等 cache data 相关错误。`[TOOL]`
- 关注启动阶段是否因资源创建顺序问题触发 synchronization 或 layout 警告。`[TOOL]`
- 关注是否加载了未使用的 extension 或 layer 导致初始化开销。`[TOOL]`

### RenderDoc

- 查看启动帧或首帧的 pipeline 创建数量和 shader 变体。`[TOOL]`
- 查看资源加载顺序和大小，确认是否有 oversized texture / buffer。`[TOOL]`
- 查看 event browser 中启动阶段是否存在大量同步等待命令。`[TOOL]`

### AGI / Android

- 关注启动阶段 CPU 时间轴中 `vkCreate*Pipelines`、`vkCreateShaderModule`、`vkCreate*Image` 的耗时分布。`[TOOL]`
- 查看 `Pipeline Creations` counter 是否集中在启动阶段。`[TOOL]`
- 查看 IO 线程、解压线程、GPU upload 是否并行。`[TOOL]`

### logcat

- 搜索 `Choreographer`、`ActivityManager: Displayed` 等系统启动耗时指标。`[ANDROID]`
- 检查是否因 shader 编译触发 ANR 或 watchdog。`[ANDROID]`
- 检查资源加载路径是否访问了慢速存储或网络。`[ANDROID]`

---

### 10. Android 分支

Android 上启动时间受 APK 大小、存储速度、Surface 生命周期影响，额外检查：

1. **Surface 有效性前提**：启动时 `ANativeWindow` 可能尚未可用，避免在 `onSurfaceCreated` 之前过早初始化依赖 surface 的资源。`[ANDROID]`
2. **APK 资源解压**：Android 上 assets 读取可能涉及解压，建议使用 obb 或提前解压到私有目录。`[ANDROID]`
3. **后台恢复**：应用从后台恢复时不应重新执行完整冷启动流程；需区分 fresh start 与 warm start。`[ANDROID]`
4. **低端设备策略**：对 RAM 和存储速度受限设备，减少首屏资源量并推迟非必要 pipeline 创建。`[ANDROID]`
5. **Thermal throttling**：长时间 shader 编译可能导致设备发热，进而降频；可拆分到多帧执行。`[ANDROID]`
6. **Cache 文件位置**：pipeline cache 应放在应用私有缓存目录，避免清理或权限问题。`[ANDROID]`

---

### 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - 启动 Profiler 时间轴，标注 shader 编译、pipeline 创建、资源加载、swapchain 创建各阶段耗时。
   - 启动阶段 pipeline 创建次数和 shader 变体数量。
   - Pipeline cache 文件大小、保存 / 加载逻辑及版本校验。
   - 首屏资源清单及加载方式（同步 / 异步 / 多线程）。
   - Texture / mesh 的平均尺寸、格式、压缩方式。
   - 设备型号、存储类型、RAM、Android 版本。
3. 给出最小验证路径：启用 cache → 预编译 shader → 延迟非关键 pipeline → 异步加载资源。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及 pipeline cache、transfer queue、image layout 规范。
   - `[TOOL]` 若 Profiler 已明确启动耗时分布。
   - `[ENGINE]` 若基于异步加载、资源分级等工程经验推断。
   - `[HEUR]` 若尚未拿到 Profiler 数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 Android 资源加载、Surface 生命周期或存储特性。


---

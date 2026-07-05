# Debug Playbook: Pipeline Creation Stutter

## 0. 适用范围

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

## 1. 现象

- 游戏中特定动作或视角切换后出现一次性或间歇性卡顿。
- Profiler 显示尖峰出现在 `vkCreateGraphicsPipelines` 或 `vkCreateComputePipelines` 调用处。
- 同一设备第二次进入同一场景时卡顿消失或明显减轻。
- pipeline cache 文件为空或大小异常。
- 关闭异步编译后卡顿从分散变为集中在加载时。

---

## 2. 最可能原因排序

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

## 3. 快速验证路径

1. **用 Profiler 抓取卡顿帧**，确认尖峰是否在 `vkCreate*Pipelines`。`[TOOL]`
2. **删除并重建 pipeline cache 文件**：对比首次运行与后续运行的卡顿情况。`[TOOL]`
3. **统计运行期 pipeline 创建调用次数**：确认是否有预期之外的创建。`[TOOL]`
4. **强制所有变体在加载时创建**：观察卡顿是否从运行期转移到加载期。`[TOOL]`
5. **检查 pipeline cache 序列化数据**：确认是否写入磁盘并在启动时读取。`[TOOL]`
6. **验证 Graphics Pipeline Library 支持情况**：查看 `VK_EXT_graphics_pipeline_library` 是否启用。`[TOOL]`

---

## 4. Vulkan 对象链路排查

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

## 5. 高频根因

1. 未启用 `VkPipelineCache` 或 cache 未持久化到磁盘，每次启动重新编译。`[ENGINE]`
2. 大量 shader 变体在运行期按需创建，用户首次触发时卡顿。`[ENGINE]`
3. 所有 pipeline 在主线程同步创建，阻塞渲染循环。`[ENGINE]`
4. 未使用 Graphics Pipeline Library，任何 rasterizer state 变化都触发完整 pipeline 重建。`[ENGINE]`
5. Pipeline cache 文件版本未与应用 / shader 版本绑定，更新后使用过期 cache 导致未命中。`[ENGINE]`
6. 对很少使用的变体也做全量预编译，浪费启动时间且无法覆盖运行时变体。`[HEUR]`

---

## 6. 修复方案

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

## 7. 回归验证

- [ ] 首次进入场景的 pipeline 创建尖峰消失或降至预算内。
- [ ] Pipeline cache 文件在退出后正确生成并在下次启动时加载。
- [ ] 关键变体预创建后对应场景无卡顿。
- [ ] 异步创建不引入资源竞争或 validation error。
- [ ] Graphics Pipeline Library 拆分后渲染结果一致。
- [ ] 应用更新后 cache 版本校验正确，不会使用过期 cache。
- [ ] 低端设备与高端设备均通过场景切换压力测试。

---

## 8. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

## 9. 工具证据

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

## 10. Android 分支

Android 上 pipeline 创建受驱动实现和功耗影响大，额外检查：

1. **Surface 有效性前提**：异步创建 pipeline 时 `ANativeWindow` 仍可能变化，确保新 pipeline 不会绑定到已销毁的 swapchain framebuffer。`[ANDROID]`
2. **后台恢复**：应用进入后台后再回到前台，部分驱动会丢弃 pipeline cache，需从持久化 cache 恢复。`[ANDROID]`
3. **低端设备编译时间**：Android 设备 shader 编译器差异大，低端设备可能需要更长的预编译时间或更少的变体。`[ANDROID]`
4. **Tile-based GPU 的 GPL 收益**：Adreno / Mali 对 vertex input 和 fragment output 拆分敏感，需实测验证。`[ANDROID]`
5. **Cache 文件位置**：Android 上 pipeline cache 应放在应用私有目录，避免权限问题。`[ANDROID]`

---

## 11. 不确定时如何处理

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

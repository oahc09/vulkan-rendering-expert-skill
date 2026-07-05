# Case: Pipeline Cache Strategy

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 架构 / Pipeline Cache |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [ENGINE] [SPEC] [TOOL]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 首次安装或清除数据后启动，进入游戏主界面或第一场战斗时严重卡顿。
- 第二次启动明显变快，但应用更新或显卡驱动升级后，启动速度又回退到首次状态。
- 某些用户反馈“第一次进某关卡特别卡”，之后流畅。
- CI 构建的 pipeline cache 文件在部分设备上无法加载，启动日志报 cache 校验失败。

---

## 2. 初始上下文

- 平台：通用，Android 上问题更突出（包体大小和 I/O 限制更严格）。
- 使用 `VkPipelineCache` 加速 `vkCreateGraphicsPipelines`。
- 尝试将 pipeline cache 数据保存到磁盘，但策略不完整。
- 没有为不同 GPU / 驱动版本单独管理 cache 文件。
- Shader variant 数量大，但 CI 没有离线编译流程。
- 应用更新时未清理旧 cache，也未做版本校验。

---

## 3. 初始误判

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

## 4. 排查路径

1. 检查 `VkPipelineCacheCreateInfo` 是否正确启用，initialData 是否从文件加载。
2. 检查 cache 文件保存/加载路径，确认首次启动为空、二次启动有数据。
3. 用 `vkGetPipelineCacheData` 导出 cache，统计大小和命中率。
4. 对比有/无 cache 时 `vkCreateGraphicsPipelines` 的耗时。
5. 检查 cache 文件是否随应用更新或驱动更新而失效。
6. 检查 cache 是否覆盖了所有常用 shader variant。
7. 评估 cache 文件体积对包体和下载的影响。
8. 检查 Android 上不同设备（GPU/驱动）是否需要独立的 cache 文件。

---

## 5. 关键证据

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

## 6. 根因

根因：Pipeline cache 的持久化、校验、失效和预热策略没有作为系统工程对待，导致 cache 命中不稳定、跨版本/跨驱动失效、首次用户体验差 `[ENGINE]`。

---

## 7. 修复方案

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

## 8. 修复后验证

- [ ] Validation clean。
- [ ] 首次安装启动时，基础 pipeline cache 成功加载且命中率高。
- [ ] 二次启动 pipeline 创建总耗时下降 70% 以上。
- [ ] 应用更新或驱动更新后，旧 cache 正确失效并重建。
- [ ] 不同 GPU 品牌设备加载对应 cache 文件，无跨设备兼容问题。
- [ ] Cache 文件体积在包体预算内。
- [ ] 运行时首次遇到的新 variant 能被捕获并补充到 user cache。

---

## 9. 经验抽象

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

## 10. 预防规则

1. 每个 pipeline cache 文件必须包含可校验的元数据（app version、driver version、GPU 标识、shader hash）。
2. 必须区分只读 base cache 和可写 user cache，禁止直接修改包内 cache。
3. CI 必须离线编译所有已知 shader variant 并生成 base cache。
4. 不同 GPU 架构/驱动版本必须生成独立的 cache 文件。
5. 应用更新或驱动更新后必须使旧 cache 失效并触发重建。
6. 运行时首次遇到的新 variant 必须能被 telemetry 捕获并补充预热。
7. 定期用 `vkGetPipelineCacheData` 回写 cache，保证崩溃后也能保留大部分编译结果。
8. 引入 graphics pipeline library 拆分 cache 粒度，提高复用率。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`

---

## 13. 关联 Workflow

- `../../05_workflows/07_optimization/reduce_pipeline_creation_stutter.md`
- `../../05_workflows/06_pipeline_descriptor/add_graphics_pipeline.md`
- `../../05_workflows/01_renderer_setup/setup_instance_device_queue.md`

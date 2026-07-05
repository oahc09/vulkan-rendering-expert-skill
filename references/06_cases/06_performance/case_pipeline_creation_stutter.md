# Case: Pipeline Creation Stutter

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Pipeline / Stutter |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 游戏运行时偶发卡顿（hitch），首次进入新场景、首次切换武器、首次开启新特效时尤为明显。
- 卡顿只发生一次，之后同样效果再次使用不再卡顿。
- CPU 帧时间在卡顿时从 8 ms 跳到 80 ms 以上，GPU 帧时间正常。
- 低端 Android 设备上，首次遇到某个 shader variant 时甚至会 ANR。

---

## 2. 初始上下文

- 平台：Android / Windows / Linux 均可能发生，Android 低端机更明显。
- Vulkan 1.1/1.2，使用 `vkCreateGraphicsPipelines` 运行时创建 pipeline。
- Shader 在加载时只编译为 `VkShaderModule`，但 pipeline 按需求懒创建。
- 材质系统支持大量 shader variant（multi_compile / keyword）。
- 未使用 `VK_EXT_graphics_pipeline_library` 或 `VK_KHR_pipeline_executable_properties`。
- Pipeline cache 文件未持久化或持久化策略不完善。

---

## 3. 初始误判

最初容易怀疑：

```text
Shader 实时编译耗时；
贴图首次上传导致 stall；
GC / 内存分配造成卡顿；
CPU culling 或物理计算阻塞；
磁盘 IO 导致阻塞。
```

但 CPU profiler 显示耗时集中在 `vkCreateGraphicsPipelines`；RenderDoc 中卡顿帧正好对应某个新 pipeline 首次绑定。后续确认是 pipeline 运行时创建导致的瞬时 CPU 阻塞 `[TOOL]`。

---

## 4. 排查路径

1. 用 Tracy / Perfetto / Android Studio CPU Profiler 捕获卡顿帧。
2. 定位主线程耗时最长的调用，确认是否为 `vkCreateGraphicsPipelines`。
3. 查看该帧首次出现的 shader / material / keyword 组合。
4. 检查 `VkPipelineCache` 是否启用，以及是否从磁盘加载了缓存数据。
5. 统计一局游戏中首次出现的 pipeline 数量，评估预热缺失范围。
6. 用 `VK_KHR_pipeline_executable_properties`（如可用）查看 driver 内部编译阶段耗时。
7. 临时在启动时预创建所有已知 pipeline，验证卡顿是否消失。

---

## 5. 关键证据

### Validation Layer

- 通常无 error。
- 若 pipeline cache 数据格式不兼容，可能报 `VK_PIPELINE_COMPILE_REQUIRED` 或缓存加载失败（视扩展而定）`[SPEC]`。

### RenderDoc / AGI

- CPU Profiler：卡顿帧中 `vkCreateGraphicsPipelines` 耗时 50～200 ms。
- RenderDoc：卡顿帧首次出现某个 pipeline 的 `vkCmdBindPipeline`，之前的帧不存在该 pipeline。
- AGI CPU Timeline：主线程在 pipeline creation 期间无其他工作，GPU 处于等待状态。
- 关键 resource：`VkPipelineCache`、`VkShaderModule`、pipeline layout、每个 material 对应的 `VkPipeline`。

### Log / Code

- 关键代码模式：

```text
void drawMaterial(Material* mat) {
    if (!mat->pipeline) {
        VkGraphicsPipelineCreateInfo ci = mat->buildCreateInfo();
        vkCreateGraphicsPipelines(device, cache, 1, &ci, nullptr, &mat->pipeline);
    }
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_GRAPHICS, mat->pipeline);
    vkCmdDrawIndexed(cmd, ...);
}
```

- 启动日志：

```text
Pipeline cache loaded: 0 bytes (首次安装无缓存)
First draw of shader "Particles_Additive_Soft": vkCreateGraphicsPipelines = 120 ms
```

---

## 6. 根因

根因：渲染管线在运行时按需创建 `VkPipeline`，而 driver 编译/链接 pipeline 是同步 CPU 操作，首次调用时阻塞主线程，造成帧时间尖峰 `[ENGINE]`。

---

## 7. 修复方案

### 最小修复

- 确保启用 `VkPipelineCache`，并在启动时从磁盘加载缓存、退出时保存缓存。
- 对已知会在当前关卡使用的 material / shader variant，在加载界面或启动阶段预创建对应 pipeline。
- 避免在 render loop 中首次调用 `vkCreateGraphicsPipelines`。

### 稳定修复

- 在后台线程异步创建 pipeline，主线程在 pipeline ready 前使用 fallback pipeline 或跳过渲染。
- 使用 `VK_EXT_pipeline_creation_cache_control` 的 `VK_PIPELINE_CREATE_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT`，将同步编译失败转换为可异步处理的 `VK_PIPELINE_COMPILE_REQUIRED`。
- 建立 shader variant 预热清单，按关卡/场景预编译。
- 使用 `VK_EXT_graphics_pipeline_library` 将 vertex input、fragment output、pre-rasterization、fragment shader 分阶段缓存，减少完整 pipeline 创建耗时 `[SPEC]`。

### 工程化修复

- 建立 pipeline 预热系统：根据关卡、角色、特效配置自动生成预热列表，在加载时异步编译。
- CI 中跑全量 shader variant 离线编译，生成稳定的 pipeline cache 文件并随包发布。
- 运行时监控首次出现的 pipeline，记录到 telemetry，用于补充预热列表。
- 对无法预热的动态组合，提供显式异步创建机制并给出视觉 fallback。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] 新场景 / 新特效首次出现时无帧时间尖峰。
- [ ] CPU profiler 中 `vkCreateGraphicsPipelines` 不出现在主线程 render loop。
- [ ] Pipeline cache 文件加载成功且命中率高。
- [ ] Android 低端机不再因 pipeline 创建导致 ANR。
- [ ] 异步创建 pipeline 时有合理的 fallback，画面无突兀变化。
- [ ] 应用更新或驱动更新后，pipeline cache 能正确失效并重建。

---

## 9. 经验抽象

Pipeline 创建不是免费的。Shader module 编译只是把 SPIR-V 加载进 driver，真正的开销在 graphics pipeline 创建时的 driver 内部优化/编译。关键规则：

```text
已知 pipeline：离线或加载时预创建。
未知 pipeline：异步创建 + fallback。
Pipeline cache：必须持久化、随包发布、版本化失效。
```

把 pipeline creation 从“首次使用”移到“首次需要之前”，是消除运行时卡顿最有效的手段之一 `[ENGINE]`。

---

## 10. 预防规则

1. 禁止在 render loop 中同步调用 `vkCreateGraphicsPipelines`。
2. 每个 shader variant 必须有明确的创建时机：启动预热、关卡加载、后台异步。
3. `VkPipelineCache` 必须启用，并在应用退出时保存、启动时加载。
4. Pipeline cache 文件必须做版本校验（driver version、app version、shader hash），失效后重新生成。
5. CI 必须离线编译所有已知 shader variant 并生成可发布的 pipeline cache。
6. 对无法预热的动态组合，使用异步创建 + fallback，禁止阻塞主线程。
7. 使用 `VK_EXT_graphics_pipeline_library` 拆分 pipeline 阶段，提高缓存命中率。
8. 运行时 telemetry 记录首次出现的 pipeline，用于补充预热清单。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

## 13. 关联 Workflow

- `../../05_workflows/07_optimization/reduce_pipeline_creation_stutter.md`
- `../../05_workflows/06_pipeline_descriptor/add_graphics_pipeline.md`
- `../../05_workflows/01_renderer_setup/setup_instance_device_queue.md`

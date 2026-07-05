# API Card: VkPipelineCache

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Pipeline 链 |
| Vulkan 对象 | `VkPipelineCache` |
| 常用 API | `vkCreatePipelineCache` / `vkDestroyPipelineCache` / `vkGetPipelineCacheData` / `vkMergePipelineCaches` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkPipelineCache` 是 `vkCreate*Pipelines` 的内部缓存容器，用于复用之前编译的 pipeline 中间数据，显著降低重复创建与后续启动的 CPU 耗时。[SPEC]

---

## 2. 所属对象链路

```text
VkPipelineCacheCreateInfo（可含初始 blob 数据）
→ vkCreatePipelineCache
→ VkPipelineCache
→ vkCreateGraphicsPipelines / vkCreateComputePipelines（传入 cache）
→ Pipeline 复用编译结果
→ vkGetPipelineCacheData（导出 blob）
→ 持久化到磁盘
→ 下次启动时作为 initialData 传入
```

### 上游依赖

- 已创建的逻辑设备。[SPEC]
- 可选的持久化 blob 数据。[ENGINE]

### 下游影响

- 影响 pipeline 创建速度，尤其是后续启动。[ENGINE]
- 多个 pipeline 共享同一 cache 时，cache 会累积编译结果。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkPipelineCache`
- `VkPipelineCacheCreateInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreatePipelineCache` | 创建 cache，可传入之前持久化的 blob。[SPEC] |
| `vkDestroyPipelineCache` | 销毁 cache。[SPEC] |
| `vkCreateGraphicsPipelines` / `vkCreateComputePipelines` | 创建 pipeline 时传入 cache。[SPEC] |
| `vkGetPipelineCacheData` | 导出 cache 数据用于持久化。[SPEC] |
| `vkMergePipelineCaches` | 合并多个 cache。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- 某些驱动可能提供 vendor-specific cache hint，但通常不需要。

---

## 4. 标准使用流程

```text
启动时读取磁盘上的 pipeline cache blob（如有）
→ vkCreatePipelineCache（initialData = blob）
→ 创建 graphics/compute pipeline 时传入 cache
→ 运行中持续创建 pipeline，cache 自动积累
→ 退出/合适时机调用 vkGetPipelineCacheData 导出 blob
→ 写入磁盘
→ 下次启动复用
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `initialDataSize` / `pInitialData` | 持久化 blob；可为空表示新建 cache。[SPEC] | blob 版本与驱动不匹配导致被忽略。[TOOL] |
| `flags` | 当前保留为 0 或 `VK_PIPELINE_CACHE_CREATE_EXTERNALLY_SYNCHRONIZED_BIT`。[SPEC] | 误用 flag。[TOOL] |
| `pipelineCache`（创建 pipeline 时） | 传入同一 cache 以复用编译结果。[SPEC] | 每个 pipeline 单独创建 cache，失去缓存意义。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否尝试加载持久化 blob？
- [ ] Blob 是否来自兼容的驱动/设备？
- [ ] 是否所有 pipeline 共享同一个 cache？

### 使用阶段

- [ ] 创建 pipeline 时是否传入了 cache？
- [ ] Cache 是否跨会话持久化？

### 销毁阶段

- [ ] 销毁 cache 前是否已导出数据？
- [ ] 是否等待所有引用 cache 的 pipeline 创建完成？

---

## 7. 高频错误

1. 每个 pipeline 创建独立的 cache，无法共享编译结果。[TOOL]
2. 持久化 blob 未校验版本，换驱动后加载失败但静默忽略。[TOOL]
3. 忘记调用 `vkGetPipelineCacheData` 保存 cache。[ENGINE]
4. 在创建大量 pipeline 的循环中未传入 cache。[ENGINE]
5. 多线程创建 pipeline 时未正确同步对 cache 的访问。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkPipelineCacheCreateInfo-*`：initial data 合法性。
- `VUID-vkCreateGraphicsPipelines-pipelineCache-*`：cache handle 有效性。

### RenderDoc / AGI

- 分析 pipeline 创建耗时；cache 命中时创建时间应显著下降。
- AGI 可显示 pipeline cache 命中情况。

### 日志 / 代码检查

- 记录 `vkCreateGraphicsPipelines` 耗时对比（首次 vs 后续）。
- 检查 cache blob 的保存与加载路径。

---

## 9. 生命周期风险

### 创建时机

- 初始化阶段，创建 pipeline 之前。[ENGINE]

### 使用时机

- 每次创建 graphics/compute pipeline 时传入。[SPEC]

### 销毁时机

- 所有 pipeline 创建完成后，或应用退出时；通常在所有 pipeline 之后销毁。[SPEC]

### in-flight 风险

- Pipeline cache 不直接被 command buffer 引用；销毁前只需确保没有并发的 pipeline 创建操作。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Pipeline cache 本身不参与 GPU 执行同步；它只是 CPU 侧编译缓存。[SPEC]

### GPU-GPU 同步

- 无。

### 资源访问同步

- `vkGetPipelineCacheData` 与 `vkCreate*Pipelines` 不应并发；需 CPU 侧同步。[SPEC]

---

## 11. Android 注意点

- Android 上 pipeline 创建耗时通常远高于 desktop，pipeline cache 几乎是必须项。[ANDROID][ENGINE]
- 持久化 cache blob 到应用私有目录，避免被系统清理；同时处理 blob 失效（如驱动更新）。[ANDROID]
- 不要在 `onSurfaceCreated` 中阻塞式创建所有 pipeline；应分帧预热并复用 cache。[ANDROID]
- 部分 Mali/Adreno 对 cache blob 格式敏感，跨设备或驱动版本可能不兼容，需做版本校验。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 使用 cache 后，后续 pipeline 创建时间通常下降一个数量级。[ENGINE]
- `vkGetPipelineCacheData` 可能在退出时耗时，应异步保存。[HEUR]

### GPU 侧

- Pipeline cache 不影响 GPU 执行，只影响 CPU 编译阶段。[SPEC]

### 移动端

- 启动时优先加载 cache，再异步创建缺失的 pipeline。[ENGINE]
- 对常用 material 的 pipeline 在启动时预热，避免运行时卡顿。[ENGINE]
- Cache blob 体积可能较大，注意存储空间与加载时间权衡。[HEUR]

---

## 13. 专家经验

**经验**：
始终为每个 `VkDevice` 维护一个全局 pipeline cache，并在应用退出时持久化到磁盘。加载时检查 blob 的校验和或版本戳，若驱动/应用版本变化则丢弃重建。不要把 cache 当作“创建完 pipeline 就扔”的临时对象，它的价值在于跨会话复用。对大型项目，可预生成并随包分发 cache blob，但需针对目标设备驱动版本做测试。

**适用条件**：
所有需要创建多个 graphics/compute pipeline 的项目，尤其是移动端。

**不适用情况**：
只创建极少量 pipeline 的简单 demo；或所有 pipeline 在离线预编译（如某些控制台工具链）。

**来源**：`[ENGINE][ANDROID][TOOL]`

---

## 14. 相关 API 卡片

- `graphics_pipeline.md`
- `compute_pipeline.md`
- `pipeline_layout.md`
- `specialization_constants.md`
- `graphics_pipeline_library.md`
- `pipeline.md`
- `../01_instance_device_queue/logical_device.md`

---

## 15. 需要回查官方文档的情况

1. Pipeline cache blob 的 header 版本与校验规则。
2. `VK_PIPELINE_CACHE_CREATE_EXTERNALLY_SYNCHRONIZED_BIT` 的使用条件。
3. `vkMergePipelineCaches` 的合并语义与容量限制。
4. 不同驱动对 cache blob 跨版本兼容性的处理。
5. 多线程下 pipeline cache 访问的最佳同步实践。

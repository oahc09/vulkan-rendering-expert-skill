# Debug Playbook: Vulkan Memory Leak

## 0. 适用范围

### 适用

- 应用运行时间越长内存占用越高，最终 OOM 或被系统杀死。
- Validation Layer 报告 object leak 或 `VUID-*-memory` 相关错误。
- 每帧创建 Vulkan 对象但未正确释放。
- Descriptor pool、command pool、image、buffer 数量持续增长。

### 不适用

- CPU 侧非 Vulkan 资源泄漏（如游戏逻辑、纹理源数据未释放）。
- 驱动级内存增长无法通过应用代码直接修复。
- 一次性加载的大资源导致的内存峰值，而非持续增长。

---

## 1. 现象

- 内存占用曲线持续上升，无稳定平台期。
- 长时间运行后出现 `VK_ERROR_OUT_OF_DEVICE_MEMORY` 或 `VK_ERROR_OUT_OF_HOST_MEMORY`。
- Validation Layer 提示 `VUID-vkDestroyDevice-device-00378` 等对象未销毁。
- Descriptor pool、command pool 频繁创建但不见销毁。
- 应用被 Android low memory killer 终止。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Descriptor pool 未释放或复用 | 每帧 `vkAllocateDescriptorSets` 但 `vkFreeDescriptorSets` / 销毁 pool 缺失 | Descriptor Pool |
| P0 | Command pool / buffer 泄漏 | command buffer 录制后未 free 或 pool 未销毁 | Command Pool / Command Buffer |
| P0 | Image / buffer / image view 未销毁 | resource 创建数量持续增长，对应 destroy 调用缺失 | Buffer / Image / ImageView |
| P1 | Memory allocation 未释放 | `vkAllocateMemory` 数量大于 `vkFreeMemory` | Device Memory |
| P1 | Shader module / pipeline / pipeline layout 泄漏 | 变体切换后旧对象未销毁 | Shader Module / Pipeline / Pipeline Layout |
| P2 | Sampler / framebuffer / render pass 未释放 | 这些对象生命周期较长，但切换场景后应清理 | Sampler / Framebuffer / Render Pass |
| P2 | 对象销毁顺序错误 | 先销毁 device 再销毁对象，或对象仍被 in-flight command buffer 引用 | Lifecycle |

---

## 3. 快速验证路径

1. **启用 Validation Layer 的 object lifetime 跟踪**：查看退出或运行时泄漏报告。`[TOOL]`
2. **统计每帧 `vkCreate*` / `vkAllocate*` / `vkDestroy*` / `vkFree*` 数量**：确认是否失衡。`[TOOL]`
3. **运行应用数分钟并观察内存曲线**：确认增长趋势与对象创建趋势一致。`[TOOL]`
4. **强制执行 `vkDeviceWaitIdle` 后调用自定义销毁逻辑**：确认是否仍有未释放对象。`[TOOL]`
5. **检查 frame-in-flight 资源管理**：确认 fence retire 后是否及时 free command buffer / descriptor set。`[ENGINE]`
6. **使用 RenderDoc / AGI resource inspector 查看对象数量变化**。`[TOOL]`

---

## 4. Vulkan 对象链路排查

```text
Instance / Device
→ Descriptor Pool / Set
→ Command Pool / Buffer
→ Buffer / Image / ImageView / Sampler
→ Pipeline / Pipeline Layout / Shader Module
→ Render Pass / Framebuffer
→ Memory Allocation
```

逐项检查：

- 每个 `vkCreate*` 是否有对应的 `vkDestroy*`，每个 `vkAllocate*` 是否有对应的 `vkFree*` 或销毁父对象。`[SPEC]`
- Descriptor pool 是否被正确销毁，pool 中分配的 set 是否在 pool 销毁前 free 或随 pool 一起释放。`[SPEC]`
- Command buffer 是否在 `vkResetCommandPool` 或 `vkFreeCommandBuffers` 后复用。`[SPEC]`
- Image / buffer 的 memory binding 是否在对象销毁前正确解除。`[SPEC]`
- Pipeline layout、render pass、framebuffer 是否在场景切换或应用退出时清理。`[ENGINE]`
- 是否存在 in-flight command buffer 引用已销毁对象的隐患。`[SPEC]`

---

## 5. 高频根因

1. 每帧为每个 draw call 分配新的 descriptor set，从未 free 或复用。`[ENGINE]`
2. 每帧创建新的 command buffer 而不 reset / free pool，导致 pool 无限增长。`[ENGINE]`
3. 临时 image / buffer 在 post-process 或 shadow pass 后未销毁。`[ENGINE]`
4. Pipeline cache 之外的 pipeline、shader module 在变体切换后未销毁旧对象。`[ENGINE]`
5. 对象销毁顺序错误，如先调用 `vkDestroyDevice` 再尝试销毁 child object，导致 leak 报告。`[SPEC]`
6. Frame-in-flight 资源未按 fence 生命周期回收， TripleBuffer 当成无限 buffer 使用。`[ENGINE]`
7. Android 上 `ANativeWindow` 重建后旧 swapchain image / framebuffer / depth image 未释放。`[ANDROID]`

---

## 6. 修复方案

### 最小修复

- 对每帧使用的 descriptor set，在 frame fence retire 后调用 `vkFreeDescriptorSets` 或随 descriptor pool reset 复用。`[SPEC]`
- 对每帧 command buffer，使用 `vkResetCommandPool` 或 `vkFreeCommandBuffers` 回收。`[SPEC]`
- 确保每个 `vkCreate*` 都有对应的 `vkDestroy*`，使用 RAII 或对象追踪工具强制配对。`[SPEC]`
- 在场景切换或应用退出时执行显式清理，先 `vkDeviceWaitIdle` 再按依赖顺序销毁对象。`[SPEC]`

### 稳定修复

- 建立 descriptor set allocator，按 frame-in-flight 复用 set，只在必要时扩容 pool。`[ENGINE]`
- 建立 command buffer pool ring，每帧 reset 一个 pool 而非创建新 buffer。`[ENGINE]`
- 对临时 image / buffer 使用资源池或作用域包装器，超出作用域自动回收到池中。`[ENGINE]`
- 实现对象生命周期追踪，记录每个 Vulkan handle 的创建堆栈和销毁状态。`[ENGINE]`

### 工程化修复

- CI 启用 Validation Layer 的 object lifetime 检测，在测试退出时检查泄漏。`[TOOL]`
- 集成内存分析工具，自动监控 `vkAllocateMemory` / `vkFreeMemory` 差异。`[TOOL]`
- 建立 per-scene resource budget，超限自动告警并触发资源清理。`[ENGINE]`
- 对 Android 设备定期进行 low memory 压力测试，确保无持续增长。`[ANDROID]`

---

## 7. 回归验证

- [ ] 长时间运行后内存曲线趋于平稳。
- [ ] Validation Layer 退出时无 object leak 报告。
- [ ] 每帧 `vkCreate*` / `vkAllocate*` 与对应释放调用数量平衡。
- [ ] 场景切换后旧场景资源已释放。
- [ ] resize / rotation 后旧 swapchain / depth / framebuffer 已销毁。
- [ ] 应用退出时所有 Vulkan 对象按正确顺序销毁，无 validation error。
- [ ] Android 上低内存场景运行稳定，未被 LMK 杀死。

---

## 8. 相关 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 9. 工具证据

### Validation Layer

- 关注 `VUID-vkDestroyDevice-device-00378`：device 销毁时仍有对象未释放。`[TOOL]`
- 关注 `VUID-vkDestroyDescriptorPool-descriptorPool-00303` 等相关对象生命周期 VUID。`[TOOL]`
- 关注 object lifetime 分支输出的 leaked object handle 和创建调用栈。`[TOOL]`
- 关注 `VK_DEBUG_REPORT_OBJECT_TYPE_*` 相关泄漏报告。`[TOOL]`

### RenderDoc

- 查看 resource inspector 中各类对象数量是否持续增长。`[TOOL]`
- 查看 descriptor set、command buffer、image、buffer 的创建时间分布。`[TOOL]`
- 查看 capture 之间相同 frame 的对象数量差异。`[TOOL]`

### AGI / Android

- 查看系统内存曲线，确认是否与 Vulkan 对象增长同步。`[TOOL]`
- 查看 `vkAllocateMemory`、`vkCreateImage`、`vkCreateBuffer` 调用频率。`[TOOL]`
- 查看应用退出时是否有未释放对象报告。`[TOOL]`

### logcat

- 搜索 `OutOfMemory`、`VK_ERROR_OUT_OF_DEVICE_MEMORY`、`lowmemorykiller`。`[ANDROID]`
- 检查应用被系统杀死前的内存占用峰值。`[ANDROID]`
- 检查 surface / swapchain 重建前后对象创建 / 销毁日志。`[ANDROID]`

---

## 10. Android 分支

Android 上内存泄漏常与 Surface / ANativeWindow / Swapchain 生命周期交织，额外检查：

1. **Surface 有效性前提**：`surfaceDestroyed` 回调后应停止引用该 `ANativeWindow` 的所有资源，旧 swapchain 必须在 GPU idle 后销毁。`[ANDROID]`
2. **Swapchain 重建清理**：横竖屏切换或 `OUT_OF_DATE` 后，旧 swapchain image、framebuffer、depth image 必须完整释放，避免每轮换一次泄漏一次。`[SPEC]`
3. **in-flight resource 退休**：pause / resume 时确保所有引用旧 swapchain 的 command buffer、semaphore、fence 已 retire 并回收。`[ENGINE]`
4. **内存预算**：Android 设备内存紧张，建议设置 Vulkan memory allocator 的上限并监控 `VK_ERROR_OUT_OF_DEVICE_MEMORY`。`[ANDROID]`
5. **后台恢复**：从后台恢复时不应重复创建未释放的渲染资源；需检查 warm start 与 fresh start 的资源管理路径。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - Validation Layer 完整日志，特别是 object lifetime 和 device destruction 报告。
   - 每帧各类 Vulkan 对象的 create / destroy 数量统计。
   - 内存 Profiler 曲线与对象数量曲线的对比。
   - Descriptor pool / command pool 的分配与回收策略。
   - 场景切换和 swapchain 重建时的资源清理逻辑。
   - 设备型号、RAM、GPU、Android 版本。
3. 给出最小验证路径：统计 create/destroy 失衡 → 检查 descriptor/command pool → 检查临时 image/buffer → 检查 swapchain 重建。
4. 标注当前判断属于：
   - `[SPEC]` 若涉及对象销毁顺序、pool 释放、memory free 规范。
   - `[TOOL]` 若 Validation Layer / Profiler 已给出明确泄漏证据。
   - `[ENGINE]` 若基于资源池、frame-in-flight 管理等工程经验推断。
   - `[HEUR]` 若尚未拿到工具数据，仅为常见原因排序。
   - `[ANDROID]` 若涉及 Android Surface 生命周期或低内存场景。

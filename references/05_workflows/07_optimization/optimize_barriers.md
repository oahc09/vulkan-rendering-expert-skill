# Workflow: Optimize Barriers

## 0. 适用范围

### 适用

- barrier 数量过多、范围过宽，导致 CPU 录制开销与 GPU 同步 stall 增加。
- 希望通过 subresource range、dependency flags、subpass dependency、render graph、event 降低 barrier 开销。
- 已有基础同步，需要性能调优。

### 不适用

- 尚未解决 validation error 或同步 hazard 的工程（先保证正确性）。
- 渲染顺序完全线性、barrier 极少的简单场景。
- 完全由外部 render graph 自动处理同步的引擎。

---

## 1. 任务目标

降低 barrier 带来的 CPU / GPU 开销：

```text
Broad global memory barriers per resource transition
→ Scoped barriers (subresource range, stage/access masks)
→ Subpass dependencies
→ Render graph automatic barriers
→ Events for fine-grained intra-command-buffer sync
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 当前 barrier 数量、类型（image / buffer / global / event）。
- 是否使用 RenderPass / Dynamic Rendering。
- 是否使用 RenderGraph。
- 资源依赖图：producer / consumer、读写阶段。
- 是否支持 `VK_KHR_synchronization2`（Vulkan 1.3 或扩展）。

---

## 3. 前置检查

- [ ] Validation Layer 可用（建议启用 synchronization validation）。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 当前无 synchronization hazard validation error。
- [ ] 已统计 barrier 数量与分布（可手动计数或 AGI）。
- [ ] 已确认资源读写阶段与 access mask。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Producer Command (write)
→ VkImageMemoryBarrier / VkBufferMemoryBarrier / VkMemoryBarrier
→ Dependency Flags / Subresource Range
→ Consumer Command (read)

OR

Subpass 0 Color Write
→ VkSubpassDependency
→ Subpass 1 Read Input Attachment

OR

Render Graph Node A
→ Render Graph Automatic Barrier
→ Render Graph Node B

OR

Producer
→ vkCmdSetEvent
→ Consumer
→ vkCmdWaitEvents
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| image barrier | `VkImageMemoryBarrier` | layout / access 转换 | 录制时 | 否 |
| buffer barrier | `VkBufferMemoryBarrier` | access 转换 | 录制时 | 否 |
| global barrier | `VkMemoryBarrier` | 全设备范围同步 | 录制时 | 否 |
| event | `VkEvent` | 细粒度同步 | 可跨 command buffer | 否 |
| subpass dependency | `VkSubpassDependency` | render pass 内同步 | render pass 生命周期 | 可能 |

---

## 6. Pipeline / Descriptor 设计

本工作流主要涉及同步优化，descriptor 设计按资源类型复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` | 经 barrier 转换后的 image | Fragment |
| set=1,binding=0 | `STORAGE_BUFFER` | 经 barrier 同步后的 SSBO | Compute / Fragment |

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| color pass write | color image | `COLOR_ATTACHMENT_WRITE` → `SHADER_READ` / `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fullscreen fragment read |
| compute write | SSBO | `SHADER_WRITE` → `SHADER_READ` | graphics vertex read |
| transfer upload | texture | `TRANSFER_WRITE` → `SHADER_READ` / `TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fragment sample |
| depth prepass | depth image | `DEPTH_STENCIL_ATTACHMENT_WRITE` → `FRAGMENT_SHADER_READ` / `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` → `DEPTH_STENCIL_READ_ONLY_OPTIMAL` | shadow / lighting read |

必须说明：

- 尽量使用最小的 stage mask 和 access mask；避免 `ALL_COMMANDS` / `MEMORY_READ|WRITE` 作为常规选择 [HEUR]。
- image barrier 的 `subresourceRange` 应精确到 mip/array layer；避免全 image barrier [HEUR]。
- 对相邻 subpass，使用 `VkSubpassDependency` 替代显式 pipeline barrier，driver 可优化 implicit dependency [SPEC]。
- 同一 command buffer 内 producer/consumer 距离较近时，可使用 `VkEvent` 而非 pipeline barrier，减少 stall [SPEC]。

---

## 8. 实现步骤

1. **审计现有 barrier**：列出所有 `vkCmdPipelineBarrier` 调用，记录资源、stage、access、layout、subresource range [TOOL]。
2. **绘制资源依赖图**：标记每个资源的 producer 和 consumer，识别冗余 barrier [ENGINE]。
3. **精确化 stage / access mask**：将 `VK_PIPELINE_STAGE_ALL_COMMANDS` 替换为实际涉及的 stage；将 `VK_ACCESS_MEMORY_READ_BIT` 替换为具体 `SHADER_READ_BIT` / `COLOR_ATTACHMENT_READ_BIT` 等 [SPEC]。
4. **精确化 subresource range**：image barrier 的 `subresourceRange` 只包含必要的 mip level 和 array layer；buffer barrier 的 `offset`/`size` 精确 [SPEC]。
5. **利用 subpass dependency**：在 RenderPass 中，将相邻 pass 的 dependency 通过 `VkSubpassDependency` 表达，设置 `srcSubpass` / `dstSubpass`、`srcStageMask` / `dstStageMask`、`srcAccessMask` / `dstAccessMask` [SPEC]。
6. **使用 `BY_REGION_BIT`**：当依赖只需同一 framebuffer region 内同步时，设置 `VK_DEPENDENCY_BY_REGION_BIT` 允许 tile-based GPU 优化 [SPEC]。适用条件：src 和 dst 都在同一 render area 内，如 deferred shading 的 G-buffer 到 lighting [ANDROID]。
7. **引入 RenderGraph**（可选）：
   - 将 pass 声明为节点，资源作为边；
   - RenderGraph 自动推导 barrier、layout transition、resource alias；
   - 适合多 pass、多资源复杂场景 [ENGINE]。
8. **使用 event 优化细粒度同步**：
   - producer 后 `vkCmdSetEvent`；
   - consumer 前 `vkCmdWaitEvents` 带精确 barrier；
   - 适用条件：同一 command buffer 内 producer/consumer 很近，且只需局部资源同步 [SPEC]。
9. **启用 synchronization2**（Vulkan 1.3 / `VK_KHR_synchronization2`）：使用 `vkCmdPipelineBarrier2` / `VkDependencyInfo` 简化 barrier 描述，支持 image layout 默认值、queue family transfer 等 [SPEC]。
10. **验证正确性**：开启 synchronization validation，运行全场景，确保无 hazard [TOOL]。
11. **验证性能**：AGI / RenderDoc 比较优化前后 barrier 数量、GPU idle 时间、frame time [TOOL]。
12. **接入 resize / recreate**：barrier 逻辑通常不随 swapchain 变化；若引入 render graph，recreate 时重新构建 graph。
13. **接入销毁路径**：event 需要显式销毁；render graph 资源按 graph 生命周期管理。

---

## 9. Android 注意点

- 移动端 TBDR（Tile-Based Deferred Rendering）GPU 对 barrier 和 subpass dependency 极为敏感；`BY_REGION_BIT` 可显著降低 tile memory 带宽 [ANDROID]。
- Adreno / Mali 对 `ALL_COMMANDS` barrier 的惩罚较大，应尽量精确 stage mask [ANDROID]。
- `surfaceDestroyed` 后所有未提交的 barrier / command buffer 均无效；恢复后从重新创建 swapchain 开始 [ANDROID]。
- rotation / resize 后 render area 变化，依赖 `BY_REGION_BIT` 的 subpass dependency 仍适用，但需确保 scissor/renderArea 更新。
- AGI 中可查看每帧 barrier 数量与 GPU stall 时间；优先优化出现频率最高的 broad barrier [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean（含 synchronization validation）：无 hazard、layout mismatch、access mask 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 barrier 数量减少、stage/access 更精确、GPU idle 时间下降 [TOOL]。
- [ ] 截图 / 数值验证：优化后渲染结果与 baseline 完全一致，无 flickering / artifact。
- [ ] logcat（Android）：无 validation error；可输出每帧 barrier 数量统计。
- [ ] 性能指标：
  - CPU 录制 barrier 耗时下降；
  - GPU frame time 在 barrier 密集场景下降；
  - AGI 中 bandwidth 与 stall 指标改善 [TOOL]。
- [ ] resize / pause / resume 后 barrier 逻辑仍正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **过度收缩 stage mask**：producer stage 未包含实际写入阶段，导致同步失效 [SPEC]。
2. **`BY_REGION_BIT` 误用**：跨 render area 或需要全局同步时使用 `BY_REGION_BIT`，导致画面撕裂 [SPEC]。
3. **Subpass dependency srcSubpass/dstSubpass 错误**：`VK_SUBPASS_EXTERNAL` 与具体 subpass 索引用错，导致 acquire/present 同步问题 [SPEC]。
4. **Event 跨 queue 使用**：`VkEvent` 不能用于跨 queue 同步，必须使用 semaphore [SPEC]。
5. **RenderGraph 推导错误**：pass 声明不完整，导致 graph 漏插 barrier，出现 hazard [ENGINE]。
6. **Buffer barrier offset/size 错误**：只同步部分 buffer，但 consumer 读取了未同步区域 [SPEC]。
7. **Image layout 未 transition**：优化 barrier 时漏掉 layout 转换，触发 validation error [TOOL]。
8. **Android TBDR 上 subpass 过多**：虽然 barrier 少了，但 subpass 拆分过细导致 tile memory 压力增大 [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- 当前 barrier 列表（资源、stage、access、layout、range）。
- RenderDoc / AGI 抓帧中的 barrier 分布。
- Validation Layer synchronization validation 输出。
- RenderGraph 节点与资源声明（如使用）。
- Android lifecycle 日志。

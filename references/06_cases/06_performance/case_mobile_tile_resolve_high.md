# Case: Mobile Tile Resolve High

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 性能 / Mobile / Bandwidth / Tile |
| 平台 | Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [ANDROID]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

- 在 Android 高端机上流畅，在中低端 Mali / Adreno 设备上发热严重、掉帧。
- 同一场景在 Desktop GPU 上 GPU frame time 只有 4 ms，在手机上却达到 12 ms 以上。
- 降低 shader 复杂度、减少 overdraw 后改善有限。
- 设备背面明显发热，长时间运行后出现 thermal throttling，帧率阶梯式下降。

---

## 2. 初始上下文

- 平台：Android，目标 GPU 为 Mali / Adreno 等 TBDR（Tile-Based Deferred Rendering）架构。
- 渲染管线包含多个 offscreen pass：shadow map、G-Buffer、SSAO、blur、tonemapping 等。
- 每个 offscreen pass 使用独立的 color / depth attachment，render pass 之间通过 image barrier 衔接。
- 部分 pass 的 `loadOp` / `storeOp` 使用默认值，未针对 TBDR 优化。
- 未使用 subpass dependency 合并多个写入/读取步骤。
- 开启了 MSAA，但没有使用 resolve attachment 或 tile-local resolve。

---

## 3. 初始误判

最初容易怀疑：

```text
Fragment shader ALU 太重；
Overdraw 过高；
贴图采样带宽太大；
CPU 提交太慢导致 GPU 饿死；
驱动对某个 extension 支持不好。
```

但 AGI 显示 GPU active 时间集中在 fragment 阶段，而 External Memory Bandwidth 异常高；RenderDoc 中每个 offscreen pass 结束都会触发 store/resolve。最终发现是 tile memory 被反复 flush 到 system memory，造成大量外部带宽 `[TOOL]` `[ANDROID]`。

---

## 4. 排查路径

1. 用 AGI 捕获一帧，查看 `External Memory Read Bandwidth` / `External Memory Write Bandwidth` counter。
2. 对比同场景 Desktop 与 Mobile 的 bandwidth 差异，确认 mobile 带宽异常高。
3. 在 RenderDoc 中检查每个 render pass 的 `loadOp` / `storeOp` / `stencilStoreOp` 设置。
4. 统计有多少 color / depth attachment 在 pass 之间被 store 出去再 load 回来。
5. 检查是否使用了 `STORE` + `LOAD` 组合，而没有使用 `DONT_CARE` / `CLEAR`。
6. 检查 MSAA color / depth 的 resolve 方式：是 tile-local resolve 还是写入系统内存后再 resolve。
7. 在 Mali GPU 上使用 Mali Offline Compiler 或 Streamline 查看 tile read/write 比例。
8. 临时将部分 offscreen pass 合并为 subpass，复测 bandwidth 变化。

---

## 5. 关键证据

### Validation Layer

- 通常无 error；若 store/load 组合导致 layout mismatch 会报 `SYNC-HAZARD` 或 image layout 错误。
- 过度 store 本身不会触发 validation，需要依赖工具 counter `[TOOL]`。

### RenderDoc / AGI

- AGI counter：`External Memory Read Bandwidth` 和 `External Memory Write Bandwidth` 显著高于同类游戏。
- AGI counter：`Tile Read Bandwidth` / `Tile Write Bandwidth` 比例异常，或 `Pixel Fill` 占用高。
- RenderDoc：每个 offscreen pass 的 render target 在 pass 结束后被 store 到 system memory，下一 pass 又被 load 进来。
- RenderDoc Pixel History：同一像素在多个 pass 之间反复写入 external memory。
- 关键 resource：offscreen color images、depth stencil images、MSAA resolve targets。

### Log / Code

- 关键代码模式：

```text
// 默认 store，导致 tile memory flush
VkAttachmentDescription colorAtt = {};
colorAtt.loadOp  = VK_ATTACHMENT_LOAD_OP_CLEAR;
colorAtt.storeOp = VK_ATTACHMENT_STORE_OP_STORE;  // 不需要 downstream 时也应 store

// 下一 pass 又重新 load
depthAtt.loadOp  = VK_ATTACHMENT_LOAD_OP_LOAD;
depthAtt.storeOp = VK_ATTACHMENT_STORE_OP_STORE;
```

- Mali Streamline 输出示例：

```text
External Memory Read:  4.2 GB/s
External Memory Write: 3.8 GB/s
Tile Read:             0.9 GB/s
Tile Write:            1.1 GB/s
```

---

## 6. 根因

根因：TBDR GPU 上以 `STORE` + `LOAD` 方式反复将 tile-local color / depth 数据写回系统内存，并在后续 pass 重新读入，造成极高的 external memory bandwidth 和发热 `[ANDROID]` `[ENGINE]`。

---

## 7. 修复方案

### 最小修复

- 对不需要 downstream 读取的 render target，将 `storeOp` 改为 `VK_ATTACHMENT_STORE_OP_DONT_CARE`。
- 对临时 depth buffer，在 render pass 结束时不 store depth。
- 避免在相邻 pass 之间对同一张 image 做 `STORE` → `LOAD`。

### 稳定修复

- 使用 Vulkan subpass 和 `VkSubpassDependency`，将多个读写步骤合并到同一个 render pass 内，数据保留在 tile memory 中。
- 使用 `INPUT_ATTACHMENT` 在 subpass 间共享 on-chip 数据，而不是 store/load external image。
- 对 MSAA，使用 resolve attachment 让 resolve 发生在 tile memory 内，而不是先 store 再 compute resolve。
- 使用 transient attachment（`VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` + lazily allocated memory）存放中间结果 `[SPEC]`。

### 工程化修复

- 建立 RenderGraph，自动识别 transient resource 并分配 transient attachment。
- 在 material/postprocess 系统中显式声明 attachment 的 downstream 使用意图，驱动 store/load 决策。
- CI 中集成 AGI bandwidth counter 阈值检查，对每 GB/s 开销做回归测试。
- 针对 Mali / Adreno / PowerVR 分别设定 bandwidth 预算，并定期校准。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] AGI 中 `External Memory Read/Write Bandwidth` 显著下降。
- [ ] 中低端 Android 设备发热降低，thermal throttling 出现时间延后。
- [ ] GPU frame time 下降并趋于稳定。
- [ ] 画面正确，没有因 `DONT_CARE` 导致的 artifact。
- [ ] MSAA resolve 结果正确，边缘无抖动。
- [ ] 多分辨率、多 GPU 品牌下 bandwidth 均在预算内。

---

## 9. 经验抽象

TBDR 的性能瓶颈往往不在 ALU，而在 tile memory 与 external memory 之间的搬运。设计渲染管线时必须把 attachment 的 store/load 视为 first-class 决策：

```text
这个 render target 是否会被下一 pass 读取？
是否可以把消费它的 pass 合并为 subpass？
是否可以使用 transient attachment？
MSAA resolve 是否发生在 tile 内？
```

每一张 intermediate image 的 store 都可能是一次外部内存写，必须给出明确理由 `[ENGINE]` `[ANDROID]`。

---

## 10. 预防规则

1. 每个 attachment 的 `loadOp` / `storeOp` 必须根据 downstream 使用意图填写，禁止默认 `STORE`。
2. 不会被下游读取的 intermediate attachment 必须使用 `DONT_CARE` 或 transient attachment。
3. 相邻 pass 读写同一张 image 时，优先合并为 subpass 或使用 input attachment。
4. MSAA color / depth 必须使用 resolve attachment 在 tile 内完成 resolve。
5. 移动平台必须使用 `VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` 管理短期中间资源。
6. 在 AGI / Mali Streamline 中设定每帧 external bandwidth 预算，并做持续回归。
7. 新增后处理 pass 时必须评估其带来的 tile resolve / store 成本。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_high.md`
- `../../04_debug_playbooks/06_performance_symptoms/fullscreen_pass_cost.md`
- `../../04_debug_playbooks/06_performance_symptoms/gpu_frame_time_high.md`

---

## 13. 关联 Workflow

- `../../05_workflows/07_optimization/optimize_mobile_bandwidth.md`
- `../../05_workflows/07_optimization/optimize_fullscreen_pass.md`
- `../../05_workflows/02_render_pass_effects/add_postprocess_pass.md`

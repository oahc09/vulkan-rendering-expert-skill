# Workflow: Compute To Graphics Sync

## 0. 适用范围

### 适用

- Compute shader 写 buffer，graphics 后续读取。
- Compute shader 写 storage image，fragment shader 后续采样。
- Compute pass 输出给 fullscreen pass / particle rendering / indirect draw 使用。

### 不适用

- compute 输出不被后续 pass 使用。
- graphics 和 compute 完全独立。
- 跨 queue ownership transfer 的复杂多队列场景，本 workflow 只覆盖基础路径。

---

## 1. 任务目标

建立 compute → graphics 的资源可见性和访问顺序：

```text
Compute Write
→ Barrier
→ Graphics Read
```

---

## 2. 输入条件

需要确认：

- compute 输出资源类型：buffer / image。
- graphics consumer 类型：vertex / fragment / index / indirect / sampled image。
- 是否同一 queue。
- image 当前 layout 和目标 layout。
- 是否使用 Synchronization2。
- 是否跨 frame 使用。

---

## 3. 前置检查

- [ ] compute pass 已能执行。
- [ ] graphics consumer 已能执行。
- [ ] 输出资源 usage 覆盖 compute write 和 graphics read。
- [ ] descriptor / pipeline layout 正确。
- [ ] sync validation 可开启。

---

## 4. Vulkan 对象链路

```text
Compute Pipeline
→ Storage Buffer / Storage Image
→ Compute Write
→ Pipeline Barrier
→ Graphics Pipeline
→ Vertex / Fragment / Indirect / Sampled Read
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| compute output buffer | `VkBuffer` | `STORAGE_BUFFER` + consumer usage | shared resource | 否 |
| compute output image | `VkImage` | `STORAGE | SAMPLED` | shared resource | 视尺寸而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| compute set=0,binding=0 | Storage Buffer/Image | output resource | Compute |
| graphics set=0,binding=0 | Sampled Image / Storage Buffer | same resource | Fragment / Vertex |

---

## 7. 同步与 Layout 设计

### Buffer：Compute Write → Graphics Read

| Producer | Resource | Barrier | Consumer |
|---|---|---|---|
| Compute Shader | Storage Buffer | `COMPUTE_SHADER/SHADER_WRITE` → consumer stage/read | Vertex / Fragment / Indirect |

### Image：Compute Write → Fragment Sampled Read

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| Compute Shader | Storage Image | `GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | Fragment Shader |

关键点：

- compute write 必须 make available。
- graphics read 必须 make visible。
- image 仅在 layout 不适合后续用途时 transition；GENERAL 采样合法时仍需 memory dependency。
- descriptor imageLayout 要匹配 graphics 使用 layout。

---

## 7.5 架构决策（Architecture Decision）

需求 → 约束 → Candidate Architecture → Trade-off → Decision。[ENGINE]

| 阶段 | 决策问题 |
|---|---|
| 需求 | producer 数据并行与真实 consumer 的语义，是否需要 raster/depth/blend |
| 约束 | queue 能力、依赖图、资源共享模式、目标平台、测量误差与内存预算 |
| Candidate | A 同 queue + 精确 barrier；B 独立 queue + binary/timeline semaphore；C 合适时由 graphics pass 实现 |
| Trade-off | queue 不等于硬件独立执行单元；同 queue 不保证所有 stage 串行，跨 queue 不保证 overlap。B 增加提交/等待和可能的跨 family ownership 成本；图像 layout 改变与 tile 成本须测量，不声称每次 barrier 都 flush tile |
| Decision | 默认先实现易验证的 A；仅依赖图允许独立工作且实测全帧收益时启用 B。记录为何不选另一边、可接受的正确性/功耗/延迟边界与回退条件。没有通用 20%/30% 阈值 |

binary semaphore 的 signal/wait 配对与 timeline 的合法递增值、完成归属都要验证；timeline 不自动转移 queue family ownership。复评依据为同负载全帧时间、等待空泡、内存峰值与稳定性，不以单个 compute pass 时间代替收益。验证门见 `../../00_expert_entry/verification_gate.md`。

---

## 8. 实现步骤

1. 确认 compute 输出资源 usage。
2. 确认 graphics consumer descriptor。
3. compute dispatch 后插入 barrier。
4. 对 image 按需要执行 layout transition，并保持 descriptor layout 一致。
5. graphics pass bind consumer descriptor。
6. 执行 draw。
7. 用 RenderDoc / AGI 验证 compute output 和 graphics input。

---

<a id="gpu-produced-draw-sync"></a>
### gpu-produced-draw-sync

以下表使用 Sync2 的 stage/access 后缀；实际常量加 `VK_PIPELINE_STAGE_2_` / `VK_ACCESS_2_` 前缀。需查询启用 synchronization2（核心1.3或KHR路径）；legacy 用对应 Vk*Barrier 与 VkPipelineStageFlags，不能混用64-bit Sync2 flags。[SPEC]

| 写入与读取 | src stage/access | dst stage/access | 独立资源 |
|---|---|---|---|
| vkCmdFillBuffer reset → cull | CLEAR_BIT / TRANSFER_WRITE_BIT | COMPUTE_SHADER_BIT / SHADER_READ_BIT \| SHADER_WRITE_BIT | counter、overflow、commands；ALL_TRANSFER 也可覆盖 fill，COPY 单独不覆盖 |
| cull → compact/finalize | COMPUTE_SHADER_BIT / SHADER_WRITE_BIT | COMPUTE_SHADER_BIT / SHADER_READ_BIT \| SHADER_WRITE_BIT | candidates、prefix sums、counter |
| finalize → draw/dispatch indirect | COMPUTE_SHADER_BIT / SHADER_WRITE_BIT | DRAW_INDIRECT_BIT / INDIRECT_COMMAND_READ_BIT | command buffer **与独立 count buffer** |
| cull → vertex shader IDs | COMPUTE_SHADER_BIT / SHADER_WRITE_BIT | VERTEX_SHADER_BIT / SHADER_READ_BIT | visible ID / transforms SSBO |
| compute → vertex fetch | COMPUTE_SHADER_BIT / SHADER_WRITE_BIT | VERTEX_ATTRIBUTE_INPUT_BIT / VERTEX_ATTRIBUTE_READ_BIT | 生成 vertex buffer |
| compute → index fetch | COMPUTE_SHADER_BIT / SHADER_WRITE_BIT | INDEX_INPUT_BIT / INDEX_READ_BIT | 生成 index buffer |
| depth pass → Hi-Z | EARLY_FRAGMENT_TESTS_BIT \| LATE_FRAGMENT_TESTS_BIT / DEPTH_STENCIL_ATTACHMENT_WRITE_BIT | COMPUTE_SHADER_BIT / SHADER_READ_BIT | depth image，支持的 sampled layout/格式 |
| Hi-Z level N → N+1 / cull | COMPUTE_SHADER_BIT / SHADER_WRITE_BIT | COMPUTE_SHADER_BIT / SHADER_READ_BIT | 各 mip 子资源 |

legacy reset 用 TRANSFER/TRANSFER_WRITE，vertex 与 index fetch 用 VERTEX_INPUT；其他 consumer 对应 legacy 标志。间接 dispatch 读取参数也是 DRAW_INDIRECT，不存在独立 dispatch-indirect 阶段。[SPEC]

每个 VkBufferMemoryBarrier2 的 buffer/offset/size 覆盖真实读写范围；同 family 无 ownership 操作时 src/dstQueueFamilyIndex 均为 VK_QUEUE_FAMILY_IGNORED。不能只同步 commands 而遗漏 count/IDs，也不能只同步 vertex shader 而遗漏 indirect parser。[ENGINE]

同 queue：上述 dependencies 加正确命令次序。不同 queue 同 family：semaphore signal/wait（wait stage 覆盖首次真实 consumer）建立跨提交依赖；仍按需处理 image layout。不同 family + EXCLUSIVE：匹配 release/acquire ownership 与 semaphore，发布的范围/布局匹配。CONCURRENT sharing 免 ownership transfer，不免 semaphore 与数据可见性。跨帧复用还需所有 consumer 完成，包括另一个 view/queue；barrier 不是 CPU 可任意覆写的许可证。[SPEC][ENGINE]

生产粒子 ping-pong 时，本帧 read 的前代 buffer 不能在另一个 queue 尚读取时被覆盖；atomic append 只分配槽，不自动使其他 invocation 的结构数据可见。可用不同 dispatch + dependency 避免把 workgroup 内 barrier 误当全设备 barrier。[SPEC]

固定源：[Vulkan synchronization](https://github.com/KhronosGroup/Vulkan-Docs/blob/b94f8bd2d004d2949469d8a5071ee10eb7d23566/chapters/synchronization.adoc)、[clear/fill](https://github.com/KhronosGroup/Vulkan-Docs/blob/b94f8bd2d004d2949469d8a5071ee10eb7d23566/chapters/clears.adoc)。

## 9. Android 注意点

- 移动端 compute 写大图后 graphics 采样会增加带宽压力。
- 尽量避免不必要的大尺寸 storage image。
- 用 AGI 检查 compute 和 graphics pass 之间的 bandwidth。
- rotation 后尺寸相关 output image 必须重建并更新 descriptor。

---

## 10. 验证方式

- [ ] compute output 有内容。
- [ ] graphics input 绑定同一资源。
- [ ] barrier 后无 sync validation hazard。
- [ ] image layout 正确。
- [ ] RenderDoc / AGI 中 graphics pass 能看到 compute 结果。
- [ ] 多帧运行稳定。

---

## 11. 常见失败模式

1. compute 写后没有 barrier。
2. barrier stage/access 写错。
3. image layout 仍是 `GENERAL`，descriptor 却写 `SHADER_READ_ONLY_OPTIMAL` 或反之。
4. graphics descriptor 引用旧资源。
5. output image usage 缺少 `SAMPLED`。
6. 跨 queue 缺 semaphore，或跨 family exclusive 缺 ownership transfer。

---

## 12. 相关 API 卡片

- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`


<a id="gaussian-consumer-dependencies"></a>
## Gaussian producer 与实际消费者

适用预投影/排序/indirect raster/ID resolve；输入为实际资源范围、queue/family、sharing mode 与读写者，输出为可审计依赖链。数据语义见 [Gaussian 合同](add_compute_pass.md#gaussian-preproject-sort)，基础路线不要求独立 compute queue。[SPEC][ENGINE]

| Producer | Consumer | synchronization2 范围（实际使用阶段） |
|---|---|---|
| compute key/list 写 | 下次 sort dispatch | COMPUTE_SHADER/SHADER_STORAGE_WRITE → COMPUTE_SHADER/SHADER_STORAGE_READ，若再写同时覆盖写访问 |
| compute indirect/count 写 | draw indirect fetch | COMPUTE_SHADER/SHADER_STORAGE_WRITE → DRAW_INDIRECT/INDIRECT_COMMAND_READ |
| compute projected attributes/IDs 写 | vertex/fragment SSBO 读 | COMPUTE_SHADER/SHADER_STORAGE_WRITE → VERTEX_SHADER 或 FRAGMENT_SHADER/SHADER_STORAGE_READ |
| compute vertex/index buffer 写 | 固定功能 fetch | COMPUTE_SHADER/SHADER_STORAGE_WRITE → VERTEX_ATTRIBUTE_INPUT/VERTEX_ATTRIBUTE_READ 或 INDEX_INPUT/INDEX_READ |
| fragment list/head/counter 原子或写 | resolve shader 读 | FRAGMENT_SHADER/SHADER_STORAGE_WRITE → 实际 FRAGMENT_SHADER 或 COMPUTE_SHADER/SHADER_STORAGE_READ |

表中阶段/access 使用 `VK_PIPELINE_STAGE_2_*_BIT`、`VK_ACCESS_2_*_BIT` 对应符号，并按目标 Vulkan/synchronization2 支持核对；不能把 DRAW_INDIRECT barrier 当 shader 属性可见性。reset/copy/upload 含真实 transfer/host producer，shader 内 workgroup barrier 不能同步多个 dispatch。

跨 VkQueue 必须实际 semaphore 依赖，wait stage 覆盖最早 consumer；ownership 由 queue family 与 exclusive/concurrent 决定，same family 或 concurrent 不取消内存依赖。每个 frame/view/generation 的 scratch、sort output 与选择 ID buffer 维持到所有消费者完成，尺寸/资源变化拒收旧异步输出。回退同 queue、CPU sort/upload 或直接 instance draw 仍保留对应依赖。

验证分别只写 indirect、再写 vertex SSBO、再用固定 vertex fetch；sync validation、结果对照和跨View/退休压力分开，不能以 barrier 数量或 Validation clean 代替正确性。[SPEC] [Synchronization](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/synchronization.adoc)。

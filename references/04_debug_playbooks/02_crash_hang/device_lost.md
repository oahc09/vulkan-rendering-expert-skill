# Debug Playbook: Device Lost

## 0. 适用范围

### 适用

- `vkQueueSubmit`、`vkQueuePresentKHR`、`vkAcquireNextImageKHR`、`vkDeviceWaitIdle` 等返回 `VK_ERROR_DEVICE_LOST`。
- 应用直接闪退，未弹出 TDR 但 GPU 已不可恢复。
- RenderDoc / AGI 抓帧时报告 device removed。
- 多线程 / 多 queue 场景下偶发 device lost。
- 特定 draw / dispatch / present 后驱动报告 device reset。

### 不适用

- 画面卡死数秒后恢复（优先看 gpu_hang.md）。
- 应用 CPU 侧崩溃（segfault、空指针）而非 Vulkan 返回 device lost。
- 实例 / 物理设备创建失败（如 `VK_ERROR_INITIALIZATION_FAILED`）。

---

## 1. 现象

- API 调用返回 `VK_ERROR_DEVICE_LOST`，停止该 logical device 的普通渲染；诊断和清理按各 API 的 device-lost 规则执行，不能声称所有 API 一律不可调用。
- 窗口变黑，应用可能被系统终止。
- Validation Layer 在 device lost 前可能已报告大量 hazard / layout / descriptor 错误。
- RenderDoc 在特定命令后无法继续，提示 device lost。
- AGI 抓帧中断，logcat 出现 `vkQueuePresentKHR` 返回 `VK_ERROR_DEVICE_LOST`。
- 崩溃堆栈停在 `vkQueuePresentKHR`、`vkDeviceWaitIdle` 或 `vkQueueSubmit`。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | 同步 hazard 导致 GPU 非法访问 | Validation sync 报告 WRITE_AFTER_READ / READ_AFTER_WRITE / WRITE_AFTER_WRITE；device lost 发生在该命令提交后 | Barrier / Image / Buffer |
| P0 | Render pass / pipeline 不匹配 | `VkGraphicsPipelineCreateInfo` 的 render pass 与 bind 时不一致；subpass index 错误 | Pipeline / Render Pass |
| P0 | 越界访问（OOB）buffer / image | descriptor 引用的范围超过 buffer 大小；storage image 写超出 extent | Buffer / Image / Descriptor |
| P1 | Image layout 错误导致 attachment 访问异常 | Validation 报 layout mismatch；device lost 出现在使用 attachment 的 draw | Image / Render Pass |
| P1 | 资源生命周期错误（use-after-free） | command buffer 引用已销毁 buffer / image；Validation 报 invalid handle | Buffer / Image / Command Buffer |
| P1 | 多 queue 缺少 semaphore / ownership transfer | compute 或 transfer queue 写后 graphics queue 读，未同步 | Queue / Semaphore / Barrier |
| P2 | 驱动 bug 或硬件过热 | 同一代码在其他设备正常；仅特定驱动版本复现 | Physical Device / Driver |
| P2 | 超时 watchdog 触发 device reset | 长时间 compute 后返回 device lost 而非 TDR | Compute Pipeline / Driver |

---

## 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 证据边界（不是根因排除证明） |
|---|---|---|---|---|
| 1 | 驱动返回码：VK_ERROR_DEVICE_LOST 出现在 acquire / submit / present / waitIdle 哪一处 | submit 处 → 检查 2（回溯相关提交区间，不等于定位唯一致错 command buffer）；present / acquire 处 → 检查 2（回溯最后一个 submit） | 无明确位置 → 检查 2 | — |
| 2 | Validation / 日志：device lost 前的首个 VUID | SYNC-HAZARD → §5-4 / §5-5（跨 queue / layout）；pipeline、render pass VUID → §5-3；range / OOB VUID → §5-1 / §5-2 | clean → 检查 3 | Validation clean 不排除 OOB / hazard / use-after-free；记录层版本、GPU-AV/sync配置及执行覆盖 |
| 3 | RenderDoc / AGI：触发命令的 pipeline render pass 匹配与 descriptor 范围 | 不匹配或越界 → §5-1 / §5-2 / §5-3 | 均正常 → 检查 4 | 仅约束已捕获事件；未捕获路径、shader动态索引与时序变化仍需核查 |
| 4 | 强制 vkDeviceWaitIdle 后单帧单 submit | 不复现 → §5-6 / §5-7（descriptor 引用已销毁对象 / in-flight 资源回收过早，§2 的 P1 生命周期假设） | 仍复现 → 检查 5 | WaitIdle 改变重叠与时序，只增加同步/生命周期线索，不排除其余根因 |
| 5 | 二分注释可疑 draw / dispatch / present | 收敛到最小触发集 → §5 对应根因 + §6 修复 | 无法收敛 → 检查 6 | — |
| 6 | 另一设备 / 驱动版本复测 | 仅特定设备复现 → §2 的 P2 驱动 / watchdog 假设（§6：VK_EXT_device_fault 收集） | 多设备均复现 → §4 对象链路排查 | 多设备复现仍不能排除共同驱动问题或 watchdog；单设备复现也不证明驱动有错 |

---

## 4. Vulkan 对象链路排查

```text
Logical Device
→ Command Buffer 录制
→ Pipeline (Graphics / Compute)
→ Render Pass / Subpass
→ Descriptor Set / Pipeline Layout
→ Buffer / Image / ImageView
→ Pipeline Barrier / Semaphore / Fence
→ Queue Submit
→ Present
```

逐项检查：

- 观察到 device lost 的 `vkQueueSubmit` / `vkQueuePresentKHR` 调用及相关提交区间的 command buffer 内容；异步返回点不是唯一致错点。`[TOOL]`
- Pipeline 创建时使用的 render pass、subpass index 是否与 draw 时一致。`[SPEC]`
- Shader 访问的 descriptor binding / set 是否与 `VkPipelineLayout` 兼容。`[SPEC]`
- Buffer / image 是否仍在生命周期内，是否被提前 `vkDestroyBuffer` / `vkDestroyImage`。`[SPEC]`
- Barrier 的 `srcAccessMask` / `dstAccessMask` / `srcStageMask` / `dstStageMask` 是否覆盖真实访问。`[SPEC]`
- 多 queue 场景下是否有 semaphore 或 event 保证执行顺序。`[SPEC]`
- Present 的 image index 是否与 `vkAcquireNextImageKHR` 返回值一致，是否重复 present。`[SPEC]`

---

## 5. 高频根因

1. Storage buffer / storage image 写越界，破坏相邻资源或驱动元数据。`[SPEC]`
2. `vkCmdDrawIndexed` 的 `indexCount` 或 `vertexOffset` 导致 index buffer 越界。`[SPEC]`
3. Render pass 与 graphics pipeline 不匹配，如 pipeline 为 render pass A subpass 0 创建，却在 render pass B subpass 1 中 bind。`[SPEC]`
4. 同一 image 在 graphics queue 读、compute queue 写，缺少 queue family ownership transfer 或 semaphore。`[SPEC]`
5. Image layout transition 缺失或 `oldLayout` 错误，GPU 以错误 layout 访问 attachment。`[SPEC]`
6. Descriptor 引用的 image view / buffer view 已被销毁，submit 时触发无效 handle。`[SPEC]`
7. In-flight frame 过多，资源在 GPU 仍在使用时被 CPU 回收并重新分配。`[ENGINE]`

---

## 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- device lost 无法就地绕过：只能重启进程 / 重建 device 恢复运行；根因未除仍有复发风险，恢复后必须继续定位。`[ENGINE]`

### Minimal Fix（针对根因的最小修复）

- 在 producer / consumer 之间插入精确的 `vkCmdPipelineBarrier`，覆盖写读双方的 stage 和 access。`[SPEC]`
- 修正 `VkGraphicsPipelineCreateInfo` 中的 `renderPass` 和 `subpass`，确保与 bind 时一致；必要时使用 `VK_NULL_HANDLE` dynamic rendering pipeline 或在 recreate render pass 后重新创建 pipeline。`[SPEC]`
- 检查所有 descriptor 的 range / offset，确保 buffer / image 访问不越界。`[SPEC]`
- 对多 queue 共享资源补充 semaphore 和 queue family ownership transfer。`[SPEC]`

### Structural Fix（结构性 / 防复发修复）

- 启用 Validation Layer 全部分支（core、sync、best practice）并清零所有错误后再提交。`[TOOL]`
- 建立资源生命周期跟踪，确保 command buffer retire 前不销毁其引用资源。`[ENGINE]`
- 使用 per-frame ring buffer 管理 in-flight 资源，fence 确认 GPU 完成后再回收。`[ENGINE]`
- 在 swapchain recreate、resize、rotation 时重建依赖旧 swapchain image 的 framebuffer 和 descriptor。`[ENGINE]`
- CI 集成 Validation Layer 和 address sanitizer，把 device lost 诱因拦截在开发阶段。`[TOOL]`
- 建立 GPU crash dump 收集机制（如 VK_EXT_device_fault），捕获 device lost 时驱动提供的 fault 信息。`[TOOL]`
- 封装 descriptor / buffer / image 使用范围断言，在 debug build 越界即断言。`[ENGINE]`
- 对多 queue 资源访问建立统一调度器，自动生成 semaphore 和 ownership transfer。`[ENGINE]`

---

## 7. 回归验证

- [ ] Validation Layer 在该场景无 error / warning / sync hazard。
- [ ] 触发 device lost 的最小命令连续运行 1000 次无异常。
- [ ] RenderDoc / AGI 能完整抓帧并回放。
- [ ] 多 queue / 多线程恢复后不再 device lost。
- [ ] resize / rotation / pause-resume 后不再 device lost。
- [ ] 不同 GPU 厂商（NVIDIA / AMD / Intel / Adreno / Mali）均通过测试。
- [ ] 正常运行观察返回码；EXT查询仅在device lost后按取证合同执行；正常态报告需另查KHR支持。无报告不等于正确性通过。

---

## 8. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/semaphore.md`

---

## 9. 工具证据

### Validation Layer

- 关注 device lost 前最后一条 `SYNC-HAZARD-*` 报告及 VUID。`[TOOL]`
- 保存原始 VUID 与其层版本，按当前规范核对 index buffer 范围、vertex input、pipeline 兼容等实际报错，不拼接通配 VUID 当规范编号。`[TOOL]`
- 核对 command buffer 状态及其提交/完成记录。`[TOOL]`
- 按实际 pipeline / render pass 兼容性报错定位，而不是套未经核实的 VUID。`[TOOL]`
- 关注 descriptor / image layout / buffer range 相关 VUID。`[TOOL]`

### RenderDoc

- 查看触发 device lost 的 draw / dispatch 的 pipeline state 与 render pass 是否匹配。`[TOOL]`
- 检查 descriptor 绑定的 buffer / image 是否有效，range 是否合理。`[TOOL]`
- 检查 mesh 数据、index buffer、vertex buffer 是否越界。`[TOOL]`
- 若 capture 成功，查看最后可见事件与故障区间；异步返回点不一定是实际致错命令，工具也可能无法抓到故障。`[TOOL]`

### AGI / Android

- 查看 `vkQueuePresentKHR` / `vkQueueSubmit` 是否返回 `VK_ERROR_DEVICE_LOST`。`[TOOL]`
- 检查 GPU counter 是否在某一命令后归零。`[TOOL]`
- 查看 framebuffer / render pass 状态是否与 pipeline 兼容。`[TOOL]`

### logcat

- 搜索 `vkQueuePresentKHR`、`VK_ERROR_DEVICE_LOST`、`device lost`、`gpu fault`。`[ANDROID]`
- 查看 `Adreno` / `Mali` 驱动日志是否有 `gpu fault`、page fault、timeout 信息。`[ANDROID]`
- 检查 Surface / ANativeWindow 是否在 device lost 前后被异常销毁。`[ANDROID]`

---

## 10. Android 分支

Android 上 device lost 常与 Surface / ANativeWindow / Swapchain 生命周期强相关，额外检查：

1. **Surface 有效性前提**：确认 device lost 时 `ANativeWindow` 仍有效；`surfaceDestroyed` 后必须停止向该 window 提交命令。`[ANDROID]`
2. **Swapchain 重建完整性**：区分 acquire / present 的 SUBOPTIMAL、OUT_OF_DATE 与真正的 DEVICE_LOST；先停止受影响提交，等待相关渲染资源完成并独立追踪 presentation 退役。WaitIdle 不单独证明旧 present semaphore 可释放；Surface 未变化不必新建 ANativeWindow。遵循 [重建契约](../../03_api_manual/02_surface_swapchain/swapchain_recreate.md#present-retirement-contract)。`[SPEC][ENGINE]`
3. **in-flight 资源对齐**：pause / resume 或 rotation 时，确保所有引用旧 swapchain image 的 command buffer、semaphore、fence 已 retire，避免提交到已销毁 swapchain。`[ENGINE]`
4. **深度 / offscreen image 重建**：rotation 后按新 extent 重建 depth attachment 和 offscreen image，并更新引用它们的 descriptor / framebuffer。`[ENGINE]`
5. **present image 索引正确性**：`vkAcquireNextImageKHR` 返回的 image index 必须与 `vkQueuePresentKHR` 使用的一致，避免重复 present 或 present 未获取的 image。`[SPEC]`
6. **低端设备内存压力**：Android 设备内存紧张时，后台回收 GPU 资源可能表现为 device lost；检查 `onTrimMemory` 回调后是否过度释放了 GPU 资源。`[ANDROID]`

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - 返回 `VK_ERROR_DEVICE_LOST` 的具体 API 调用（`vkQueueSubmit` / `vkQueuePresentKHR` / `vkDeviceWaitIdle` 等）。
   - device lost 前的完整 Validation Layer 日志（含 sync 分支）。
   - RenderDoc capture（如果能抓到中断点）。
   - AGI capture 及 logcat。
   - 触发命令附近的 command buffer 录制代码。
   - pipeline 创建时的 render pass / subpass 信息。
   - descriptor set layout / update / bind 代码。
   - buffer / image 创建参数及生命周期管理代码。
   - 设备型号、GPU、驱动版本、Android 版本。
   - 是否多 queue、是否多线程录制。
3. 给出最小复现路径：单 queue + 关闭多线程 + 最小 draw。
4. 标注当前判断属于：
   - `[SPEC]` 若已确认违反 Vulkan 规范（如 pipeline / render pass 不匹配、OOB）。
   - `[TOOL]` 若 Validation / RenderDoc / AGI 已给出明确证据。
   - `[ENGINE]` 若基于生命周期或 in-flight 管理推断。
   - `[HEUR]` 若尚未拿到工具证据，仅为可能性排序。
   - `[ANDROID]` 若涉及 Surface / ANativeWindow / Swapchain 生命周期。


<a id="mobile-fault-evidence"></a>
## 12. 移动 GPU fault：地址 → 资源代际 → 提交 → 源码

本节是诊断取证合同，不是 GPU 故障注入教程。Arm 2026-10-05 的文章介绍 EXT fault 与地址绑定联合使用，
不是这些扩展本月首次发布，也不保证所有 Mali 驱动支持。[VENDOR]

### 初始化和路径选择

| 路径 | 支持/启用与真实入口 | 调用时机与限制 |
|---|---|---|
| EXT fault | 枚举 `VK_EXT_device_fault`，查询 `VkPhysicalDeviceFaultFeaturesEXT` 并按需启用 `deviceFault` / `deviceFaultVendorBinary`，取得 `vkGetDeviceFaultInfoEXT` | device 已 lost 后查询；先取得 counts/大小，再分配输出并处理返回值；无 binary 数据不是无故障 |
| KHR fault | 枚举 `VK_KHR_device_fault`，查询/启用 `VkPhysicalDeviceFaultFeaturesKHR`；可恢复 fault 的报告还依赖 `deviceFaultReportMasked` 等实际支持项 | `vkGetDeviceFaultReportsKHR` 可以在尚未 lost 时等待/轮询报告；处理 timeout、计数、INCOMPLETE，每份报告只返回一次。`vkGetDeviceFaultDebugInfoKHR` **只能在 device lost 后**取厂商 post-mortem 数据 |
| 地址记录 | `VK_EXT_device_address_binding_report` + `VkPhysicalDeviceAddressBindingReportFeaturesEXT.reportAddressBinding`；通过 debug-utils 回调记录绑定/解绑 | 从资源创建前开始记录；历史缺失、地址复用、内部对象或别名都可能导致多候选，不能倒推唯一对象 |
| 不支持 | 通用资源 ID / generation、提交标签、CPU日志、设备/driver信息和最小场景 | 保留未验证项；不为了诊断强制提高所有手机 API 最低版本 |

KHR 不是把 EXT 函数改后缀：不存在应当照抄的 `vkGetDeviceFaultInfoKHR` 调用模板；这是错误反例，
真实入口是表中的两个 KHR 函数。查询支持、创建 device 启用与取得函数入口分别验证。[SPEC]

### 正常运行与故障记录

1. 使用既有 allocator / debug-name / retirement 系统记录 `resource_id, generation, object_type,
   allocation_id, base, size, bind/unbind, host_timestamp, queue_id, submit_id`，保留最近提交与源码函数的映射。
   此为应用日志 schema，不是臆造的 Vulkan struct 字段。[ENGINE]
2. 回调按线程安全策略拷贝必要数据；不要阻塞渲染或在回调重入 Vulkan。
3. fault 时停止普通提交，保存原始返回码、诊断结果和最后提交日志；按选中扩展合法时机查询、再走设备恢复/销毁。
4. 地址按范围和报告粒度匹配**当时**的 allocation/generation；同一地址先 unbind 后重用不得归到当前对象。
   用绑定时间、提交引用与 descriptor / buffer offset 缩小候选，不能自动定位某行 shader。[ENGINE]
5. 报告为空、捕获失败或 Validation clean 均不排除 OOB、use-after-free、hazard。
   二分工作负载/跨设备复测是增加证据，不是按一次结果排除全部其他假设。
6. 重复最小正确场景，核对恢复、资源退休、rotation/pause/resume；未运行的设备矩阵标未验证。
   故意非法 GPU 访问仅在另行授权的隔离测试设备允许，默认不执行。[ENGINE]

原始 fault/vendor dump 可能包含项目数据，按授权留本地并限制访问，不自动上传私有 trace。
规范与方法（2026-11-01 source-read，未实机验证）：
[Arm 诊断方法](https://developer.arm.com/community/arm-community-blogs/b/mobile-graphics-and-gaming-blog/posts/diagnosing-vk-error-device-lost-on-mali-gpus-with-vk-ext-device-fault)、
[EXT 查询](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDeviceFaultInfoEXT.html)、
[KHR 差异](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_device_fault.html)、
[KHR reports](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDeviceFaultReportsKHR.html)、
[KHR debug info](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetDeviceFaultDebugInfoKHR.html)、
[地址绑定 feature](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceAddressBindingReportFeaturesEXT.html)。

<a id="simulation-fault-boundary"></a>
## 仿真故障的安全缩小范围

保存world/topology/snapshot、queue提交、容量/overflow、最后成功kernel与原始fault。先用host配置拒绝/写集合检查、SPIR-V验证和有界输入测试 [kernel合同](../../03_api_manual/06_pipeline/compute_pipeline.md#simulation-kernel-portability)，再查 [全消费者退休](../../05_workflows/05_resource_management/manage_frame_resources.md#simulation-snapshot-retirement)。不要为证明检测有效在用户设备运行已知死锁、无限busy-wait或越界shader；host模拟失败须标fixture，不叫真实GPU fault。


<a id="fault-report-order-1368"></a>
## Fault 查询次序：KHR 与 EXT 不能叠加成相同证据

固定规范1.4.368明确：若已对某 device 调用 `vkGetDeviceFaultReportsKHR`，后续该 device 的 `vkGetDeviceFaultInfoEXT` 返回值是 implementation-dependent。因此不能先消费 KHR reports，再把 EXT 空值或变化判为驱动无故障、报告丢失或规范违例；也不能在两套 API 之间要求相同报告逐字节重现。该条件不消除其它合法调用时机、feature/enable、计数/容量与返回码要求。[SPEC]

**正常路径**：诊断选定一条已支持并启用的报告路径，记录调用次序及原始返回码。仅EXT路径下的重复查询保证按其规范条件使用；混合路径在日志中标记实现相关，不将差异自动合并为新故障。**失败与回退**：能力缺失保留提交/资源代际/设备日志，停止普通GPU工作后走合法恢复；不故意制造device loss，也不捕获受保护内容。对照测试以host模拟调用序列与诊断分类验证，实际fault能力保持独立设备证据。

权威：[debugging / vkGetDeviceFaultInfoEXT](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/debugging.adoc)、[1.4.368 ChangeLog](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/ChangeLog.adoc)。

# Workflow: Compute Write Storage Buffer

> 文件建议路径：`compute_write_storage_buffer.md`

---

## 0. 适用范围

### 适用

- compute shader 生成结构化数据并写入 SSBO，供后续 graphics pass 或 CPU 读取。
- GPU culling 结果、粒子系统状态、indirect draw 参数、skinning 输出、物理模拟结果等。
- 数据需要随机读写、可变长度数组、跨 workgroup 聚合。

### 不适用

- 小量只读常量（优先 UBO，cache 更友好）。
- 数据需要保证跨 workgroup 原子全局序（需额外 coherent / memory barrier 设计，本工作流不深入）。
- 需要通用跨 workgroup 全局阶段顺序的单 dispatch 算法（拆分 dispatch + Vulkan 依赖；shader barrier 不是全局 barrier）。

---

## 1. 任务目标

新增一个 compute pass，将结果写入 storage buffer，完成以下数据流：

```text
CPU params / previous GPU output
→ Compute Descriptor (SSBO write)
→ Compute Pipeline (dispatch)
→ VkBuffer (VK_BUFFER_USAGE_STORAGE_BUFFER_BIT)
→ Barrier (SHADER_WRITE → SHADER_READ / TRANSFER_READ / INDIRECT_COMMAND_READ)
→ Graphics Shader / DrawIndirect / CPU Readback
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- SSBO 用途：compute-only、compute → graphics、compute → indirect draw、compute → CPU readback。
- 数据大小、元素结构体、对齐要求（std430）。
- 是否需要 atomic 操作、counter buffer（append/consume）。
- 是否需要 per-frame ping-pong（双缓冲）以避免读写竞争。
- `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`、`storageBuffer16BitAccess` 等特性。
- 是否使用专用 compute queue 或复用 graphics queue。

---

## 3. 前置检查

- [ ] Validation Layer 可用，建议启用 synchronization validation。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`。
- [ ] compute pipeline 已支持 storage buffer descriptor。
- [ ] descriptor pool 对 `STORAGE_BUFFER` 有余量。
- [ ] 若 compute 写入后 graphics 读取，已设计 `VkBufferMemoryBarrier`。
- [ ] 若 compute 写入后 CPU 读取，已规划 host-visible staging buffer 或 `vkCmdCopyBuffer` 回读路径。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
CPU Data / Previous Compute Output
→ VkBuffer (VK_BUFFER_USAGE_STORAGE_BUFFER_BIT)
→ VkDeviceMemory / VMA Allocation
→ VkDescriptorSetLayout (STORAGE_BUFFER, COMPUTE stage)
→ VkDescriptorSet
→ vkCmdBindDescriptorSets(COMPUTE)
→ VkComputePipeline
→ vkCmdDispatch
→ VkBufferMemoryBarrier (ACCESS_SHADER_WRITE_BIT → ACCESS_SHADER_READ_BIT)
→ Next Consumer (Graphics Shader / DrawIndirect / CPU Readback)
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| output SSBO | `VkBuffer` | `STORAGE_BUFFER_BIT` | scene / frame | 否（通常） |
| SSBO memory | `VkDeviceMemory` | device-local（性能）或 host-visible（调试） | 跟随 buffer | 否 |
| staging buffer（可选，CPU 上传） | `VkBuffer` | `TRANSFER_SRC` | 上传后释放 | 否 |
| readback buffer（可选，CPU 回读） | `VkBuffer` | `TRANSFER_DST` + host-visible | per-frame | 否 |
| descriptor set | `VkDescriptorSet` | SSBO binding | per-frame / per-pass | 视策略而定 |
| counter buffer（可选） | `VkBuffer` | `STORAGE_BUFFER_BIT` | append/consume 场景 | 否 |

设计说明：

- device-local SSBO 性能最优；host-visible 仅用于调试或 CPU 每帧更新小量参数 [ENGINE]。
- 若 compute 每帧覆盖写入同一 buffer，建议使用 ring buffer 或 ping-pong 双缓冲，避免上一帧 consumer 读到未完成的旧数据 [HEUR]。
- indirect draw buffer 必须额外加 `VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT` [SPEC]。

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `STORAGE_BUFFER` | output SSBO（compute 写入） | Compute |
| set=0,binding=1 | `STORAGE_BUFFER` / `UNIFORM_BUFFER` | input data / params | Compute |
| set=0,binding=0 | `STORAGE_BUFFER` | compute 输出的 SSBO（graphics 读取） | Vertex / Fragment |
| set=0,binding=0 | `STORAGE_BUFFER` | indirect draw buffer | Vertex（间接消费） |

设计说明：

- compute shader 中 GLSL `layout(std430, binding=0) buffer Output { ... };` 对应 Vulkan `VK_DESCRIPTOR_TYPE_STORAGE_BUFFER` [SPEC]。
- 若需要每帧切换 buffer 而不重建 descriptor set，使用 `STORAGE_BUFFER_DYNAMIC` 并通过 `vkCmdBindDescriptorSets` 传入 dynamic offset，offset 对齐到 `minStorageBufferOffsetAlignment` [SPEC]。
- workgroup 内通信按 shader 内存/执行语义同步；workgroup 间全局阶段拆 dispatch + Vulkan barrier，跨 queue 另需 semaphore 和必要 ownership transfer [SPEC]。
- atomic 按实际类型、位宽、操作与存储域查询并启用所需 feature；dynamic indexing 与原子支持是不同能力，device-local 也不决定原子支持。参见 [kernel门控](../../03_api_manual/06_pipeline/compute_pipeline.md#simulation-kernel-portability) [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU upload / transfer copy | SSBO | `TRANSFER_WRITE` → `SHADER_READ` / `SHADER_WRITE` | compute shader |
| compute shader write | SSBO | `SHADER_WRITE` → `SHADER_READ` / `INDIRECT_COMMAND_READ` | graphics shader / draw indirect |
| compute shader write | SSBO | `SHADER_WRITE` → `TRANSFER_READ` | `vkCmdCopyBuffer` → host readback |
| graphics shader write | SSBO | `SHADER_WRITE` → `SHADER_READ` | compute shader |

必须说明：

- producer stage / access：`VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` + `VK_ACCESS_SHADER_WRITE_BIT`。
- consumer stage / access：graphics shader 读取为 `VK_PIPELINE_STAGE_VERTEX_SHADER_BIT | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` + `VK_ACCESS_SHADER_READ_BIT`；indirect draw 为 `VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT` + `VK_ACCESS_INDIRECT_COMMAND_READ_BIT` [SPEC]。
- storage buffer 没有 image layout，只需 `VkBufferMemoryBarrier` 或 global memory barrier 同步 access [SPEC]。
- 同 command buffer 内 compute dispatch 后立即 graphics draw，必须插入 barrier；即便在同一 queue，Vulkan 也不保证跨 stage 的隐式有序可见性 [SPEC]。
- 若其他 workgroup 依赖全局阶段结果，基线拆成两个 dispatch 并建立写→读依赖；`memoryBarrier()`、`barrier()`、`coherent`、`volatile` 均不能充当通用跨 workgroup 全局执行 barrier [SPEC]。

---

## 8. 实现步骤

1. **确认特性与限制**：查询 `maxStorageBufferRange`、`minStorageBufferOffsetAlignment`；启用 `storageBuffer16BitAccess` 等若需要 [SPEC]。
2. **定义数据结构**：按 std430 布局，注意数组元素对齐；GLSL 中 `layout(std430, binding=0) buffer Output { Element data[]; };` [SPEC]。
3. **创建 output buffer**：`VkBufferCreateInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT`；若作为 indirect draw buffer 加 `INDIRECT_BUFFER_BIT`；若需 CPU 回读加 `TRANSFER_SRC_BIT` [SPEC]。
4. **分配内存**：device-local 用于性能；host-visible 仅用于调试 [ENGINE]。
5. **创建 descriptor set layout**：`descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER`，`stageFlags = VK_SHADER_STAGE_COMPUTE_BIT`（compute 写入）或包含 `VERTEX/FRAGMENT`（graphics 读取）[SPEC]。
6. **分配并更新 descriptor set**：填写 `VkDescriptorBufferInfo`（buffer、offset、range），调用 `vkUpdateDescriptorSets`。range 可设为 `VK_WHOLE_SIZE` 或具体字节数 [SPEC]。
7. **录制 compute command buffer**：
   - 若 input 来自 CPU，先 staging copy 并插入 `TRANSFER_WRITE → SHADER_READ` barrier。
   - `vkCmdBindPipeline(COMPUTE)`、`vkCmdBindDescriptorSets`。
   - `vkCmdDispatch(workgroupX, workgroupY, workgroupZ)`。
   - 插入 `VkBufferMemoryBarrier`：`srcStage = COMPUTE_SHADER`，`srcAccess = SHADER_WRITE`，`dstStage = VERTEX_SHADER | FRAGMENT_SHADER | DRAW_INDIRECT`，`dstAccess = SHADER_READ | INDIRECT_COMMAND_READ`。
8. **graphics 消费**：在 draw / dispatch indirect 前确保 barrier 已完成；绑定 descriptor set 到 graphics pipeline。
9. **CPU 回读（可选）**：
   - compute dispatch 后插入 `SHADER_WRITE → TRANSFER_READ` barrier；
   - `vkCmdCopyBuffer` 到 host-visible readback buffer；
   - 建立transfer write→host read依赖，等待真实completion；non-coherent内存按atom对齐invalidate后读取映射内存 [SPEC]。
10. **动态 offset（可选）**：同一 buffer 分 slot 给多个 object，绑定命令传入 dynamic offset，对齐到 `minStorageBufferOffsetAlignment` [SPEC]。
11. **边界处理**：shader 中通过 `length()` 获取数组元素数量，避免越界；CPU 侧确保 buffer size >= `stride * count`。
12. **接入销毁路径**：按 `descriptor set → buffer → memory` 顺序释放；VMA 用户统一 `vmaDestroyBuffer`。
13. **接入 recreate**：SSBO 通常不随 swapchain 重建；若 SSBO 与 viewport 相关，resize 后更新数据内容。

---

## 9. Android 注意点

- SSBO与compute device/queue不要求绑定Surface；需要present的路径另验目标Surface呈现支持和生命周期 [SPEC][ANDROID]。
- pause / resume 时，若 SSBO 由 compute 每帧生成，需确保 surface recreate 期间 compute queue 不提交未初始化的命令 [ANDROID]。
- rotation / resize 触发 swapchain recreate，通常不影响 SSBO；但若 SSBO 保存 screen-space 数据（如 tile 列表、可见性列表），需按新 extent 重建 [ANDROID]。
- 移动端 Adreno / Mali 对 storage buffer 的 cache 一致性策略不同：compute 写后 graphics 读必须显式 barrier，不可依赖隐式同步 [ANDROID]。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkCmdDispatch-*-None-04XXX`、`VUID-vkCmdDraw-*-None-02721` 等 storage buffer 相关错误 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 storage buffer descriptor、barrier、alignment 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：Buffer Viewer 中可见 SSBO 内容、size、offset 正确；compute dispatch 可见 [TOOL]。
- [ ] 截图 / 数值验证：compute 输出在 graphics 中正确体现（如 culling 后物体不再绘制、粒子位置正确）。
- [ ] logcat（Android）：无 validation error；可输出 SSBO 内容 hash 或关键字段用于一致性校验。
- [ ] 性能指标：
  - compute dispatch 耗时稳定；
  - graphics 读取 SSBO 阶段无异常 latency；
  - AGI 中无 redundant barrier，无跨 stage 长 stall [TOOL]。
- [ ] resize / pause / resume 后 SSBO 数据仍有效。
- [ ] 多帧运行稳定，无 flickering 或数据竞争。

---

## 11. 常见失败模式

1. **未加 `STORAGE_BUFFER_BIT`**：buffer usage 缺失导致 descriptor update 失败 [SPEC]。
2. **Compute / graphics 同步缺失**：compute 写后未 barrier，graphics 读到旧数据或触发 hazard [TOOL]。
3. **Descriptor type 与 shader 不匹配**：GLSL `buffer` 对应 `STORAGE_BUFFER`，不是 `UNIFORM_BUFFER` [SPEC]。
4. **Offset 未对齐**：dynamic offset 不是 `minStorageBufferOffsetAlignment` 整数倍 [SPEC]。
5. **数组越界**：CPU 分配的 buffer 小于 shader 中 `length()` 期望，导致 out-of-bounds 读写。
6. **atomic 操作未启用 feature**：使用 16-bit storage / atomic 前未在 device creation 启用对应 feature [SPEC]。
7. **间接绘制 buffer 未加 `INDIRECT_BUFFER_BIT`**：`vkCmdDrawIndirect` 读取 SSBO 时 validation error [SPEC]。
8. **误用 shader barrier 作全局同步**：跨 workgroup 全局阶段未拆 dispatch/表达 Vulkan 依赖，可能出现竞争；禁止用全局 busy-wait 代替 [SPEC]。
9. **Surface重建后引用旧资源**：提交仍访问已销毁的输出相关资源；独立compute不因Surface销毁自动失效，按owner/generation控制 [ANDROID][ENGINE]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/06_performance_symptoms/barrier_draw_call_stall.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- `maxStorageBufferRange`、`minStorageBufferOffsetAlignment` 数值。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 SSBO 绑定状态与内容。
- Compute / graphics 命令顺序与 barrier 参数。
- GLSL buffer block 定义与 `std430` 布局。
- Android lifecycle 日志。

<a id="xpbd-deformation-contract"></a>
## 轻量 XPBD 与动态几何（C2）

输入：FP32 position/velocity/inverseMass、约束端点/restLength/compliance、真实子步 h、固定点轨迹、解析碰撞器、容量与 topologyGeneration。输出：本子步修正位置/速度/残差、有效状态及诊断；geometry 发布另读 [交接](compute_to_graphics_sync.md#simulation-render-handoff)。范围是两粒子对照、绳索/短链与规则网格布料，stretch/shear 和**距离弯曲近似**；不是完整连续体、通用刚体、毛发、撕裂或复杂自碰撞。[ENGINE]

对可微标量双边约束 C(x)，本子步 h、inverse mass w 和 compliance α≥0：[REF]

```text
alphaTilde = alpha / (h*h)
deltaLambda = (-C(x) - alphaTilde*lambda) /
              (sum_i(w_i * dot(grad_i C, grad_i C)) + alphaTilde)
deltaX_i = w_i * grad_i C * deltaLambda
lambda += deltaLambda
```

距离约束 C=length(x1-x0)-rest，grad1=n、grad0=-n。零长度无可靠 n 时跳过并诊断或用预定义有效方向，不能除零；没有可移动粒子直接报告不可修正，不计算0/0。λ 在每个积分子步初始化，同子步 iterations 累积；每 iteration 清零会改变材料行为。warm start 是独立策略，必须定义 h 改变的重标定及 topology/reset/contact 失效。实际 h 不是 render dt。最终速度由修正后位置减该子步旧位置再除 h 得到，随后按明确次序执行阻尼/接触速度规则；固定驱动点采用目标轨迹速度。[REF][ENGINE]

| 无浮点原子基线 | 资源与执行合同 | 验证/回退 |
|---|---|---|
| Graph-colored in-place | CPU 验证同色所有约束的**可写粒子集合互不相交**；每个颜色一 dispatch，独占 λ 槽；颜色/iteration间写→读写 barrier | topology 改变重建着色并验冲突，失败拒绝或改 gather；不同 constraint ID 不等于无冲突 |
| Jacobi + gather | 当前预测位置只读；每 constraint 写两个独占端点贡献和自己的 λ；下一 dispatch 每粒子唯一 owner 从邻接表 gather→apply 到下一位置集 | 归一化/relaxation、λ 更新和边界按同一 Jacobi CPU oracle 定义；不把 GS 原地公式的收敛性直接搬来 |

descriptor 分别绑定 position A/B、oldPosition/velocity、inverseMass、constraints/λ、contributions/adjacency 和 diagnostics，均明确容量/stride/offset；VkBuffer 含 STORAGE_BUFFER，vertex/transfer consumer另加相应usage。初始化→predict→solve colors或contribution/gather→velocity→normal/bounds 每个全局阶段用 vkCmdDispatch + 精确范围依赖；临时槽等最后读取完成才清空。默认 solver/residual FP32，不强制 FP64或FP16；浮点atomic为独立可选路径，见 [kernel门控](../../03_api_manual/06_pipeline/compute_pipeline.md#simulation-kernel-portability)。

球/平面/胶囊碰撞只承诺解析投影近似，定义 collider transform、半径、间隙与速度修正。单边接触有激活/释放条件，不能套双边距离公式假装摩擦/接触完整。高速位移接近碰撞器尺度时选择已验证子步、swept解析测试或限制交互，明确离散投影可能穿透。邻域扩展必须验证负坐标cell、hash碰撞、过滤、静态邻接排除、容量/overflow、快速运动和拓扑更新后的失效；静默截断或间隔复用旧邻域不是保守保证。四面体软体仅P1，单独测非退化体积与翻转，无合格网格不承诺实现。

最小数值判据：x0=(0,0,0)固定，x1=(1.2,0,0)、w1=1、rest=1、无外力；α=0一次投影x1=(1,0,0)；h=0.1、α=0.01、λ=0则alphaTilde=1、deltaLambda=-0.1、x1=(1.1,0,0)。这是推导，不是GPU测量。小测试可预注册CPU FP64绝对误差1e-12、GPU FP32 1e-5；复杂布料按尺度预注册位置/残差/漂移/穿透阈值，不能事后改epsilon。必测固定点、重复/退化约束、坏质量/dt、极硬/极软、拓扑变更、两种基线与无atomic设备。关联hard_rules 2/3/17；Validation clean与图像存在不证明数值正确或无race。

权威：[XPBD Algorithm 1及式17/18](https://matthias-research.github.io/pages/publications/XPBD.pdf)、[Small Steps Algorithm 1及§7精度边界](https://matthias-research.github.io/pages/publications/smallsteps.pdf)。更多子步非无条件更准；社区实现仅可借鉴写集合，不能代替理论/API/移动设备证据。

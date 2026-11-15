# Workflow: Compute Write Storage Image

> 文件建议路径：`compute_write_storage_image.md`

---

## 0. 适用范围

### 适用

- compute shader 直接写入 `VkImage`（storage image），用于生成 procedural texture、post-processing target、lighting accumulation buffer、voxelization slice 等。
- 输出需要作为 image 被后续 graphics pass 采样，或作为 storage image 被后续 compute pass 继续读写。
- 相比 storage buffer，数据具有 2D/3D 局部性，适合 image load/store 操作。

### 不适用

- 输出数据本质上是结构化数组、随机访问非 2D（优先 storage buffer）。
- 目标 image format 不支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`（需 fallback 到 buffer 或 graphics pass）。
- 需要 automatic mipchain generation（compute 写入后需显式生成或上传）。

---

## 1. 任务目标

新增一个 compute pass，将结果写入 storage image，完成以下数据流：

```text
Compute Shader (imageStore)
→ VkImage (VK_IMAGE_USAGE_STORAGE_BIT)
→ Layout GENERAL (write)
→ Barrier (SHADER_WRITE → SHADER_READ)
→ Layout SHADER_READ_ONLY_OPTIMAL (graphics sample) / GENERAL (next compute read/write)
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 输出 image 格式、尺寸、mip/array layer 数量。
- 目标 format 是否支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT` 与 `VK_FORMAT_FEATURE_STORAGE_IMAGE_ATOMIC_BIT`（如使用 atomic）。
- 是否需要 per-frame ping-pong 或复用历史帧。
- 后续 consumer：compute 继续读写、graphics fragment 采样、blit/copy。
- workgroup size 限制与局部内存策略（shared memory tile）。

---

## 3. 前置检查

- [ ] Validation Layer 可用，建议启用 synchronization validation。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已查询 `maxComputeWorkGroupInvocations`、`maxComputeWorkGroupSize`、`maxComputeSharedMemorySize`。
- [ ] 已确认目标 format 支持 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`。
- [ ] 已规划 image layout transition：`GENERAL`（compute 写）→ `SHADER_READ_ONLY_OPTIMAL`（graphics 读）。
- [ ] compute pipeline 与 descriptor 已支持 storage image。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Compute Shader (imageStore)
→ VkDescriptorSetLayout (STORAGE_IMAGE binding)
→ VkDescriptorSet
→ VkImage (VK_IMAGE_USAGE_STORAGE_BIT | SAMPLED_BIT)
→ VkImageView (single mip/layer, non-multisample)
→ VkPipeline
→ vkCmdBindPipeline(COMPUTE)
→ vkCmdBindDescriptorSets
→ vkCmdDispatch
→ VkImageMemoryBarrier(GENERAL → SHADER_READ_ONLY_OPTIMAL)
→ Consumer Graphics / Compute Pass
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| output storage image | `VkImage` | `STORAGE_BIT` + `SAMPLED_BIT`（如需后续采样） | scene / frame | 否（通常） |
| storage image view | `VkImageView` | storage image view | per-pass | 否 |
| input image（可选） | `VkImage` | `SAMPLED_BIT` 或 `STORAGE_BIT` | scene / frame | 否 |
| input image view（可选） | `VkImageView` | sampled / storage view | per-pass | 否 |
| params buffer（可选） | `VkBuffer` | `UNIFORM_BUFFER_BIT` 或 push constants | per-frame | 否 |
| descriptor set | `VkDescriptorSet` | storage image binding | per-frame / per-pass | 视策略而定 |

设计说明：

- storage image 写入时必须处于 `VK_IMAGE_LAYOUT_GENERAL` [SPEC]。
- 后续采样需 `VK_IMAGE_USAGE_SAMPLED_BIT`、支持的格式与写→采样依赖；可以保持合法GENERAL或在barrier中transition到SHADER_READ_ONLY_OPTIMAL，descriptor匹配实际layout [SPEC]。
- 若 compute 后续继续读写，可保持 `GENERAL` 布局，只需同步 access mask [HEUR]。

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `STORAGE_IMAGE` | output image（compute 写入） | Compute |
| set=0,binding=1 | `COMBINED_IMAGE_SAMPLER` 或 `STORAGE_IMAGE` | input image（compute 读取） | Compute |
| set=0,binding=2 | `UNIFORM_BUFFER` 或 push constants | dispatch params / frame constants | Compute |

设计说明：

- compute shader 中 `layout(rgba8, binding=0, set=0) uniform image2D outImage;` 对应 `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` [SPEC]。
- `imageStore` 的 format qualifier 必须与 image 实际 format 兼容，否则触发 `VUID-vkCmdDispatch-None-08612` [SPEC]。
- workgroup 内可使用 `shared` memory 做 tile cache，减少 global image 访问；适用条件：输出像素与相邻像素有复用（如 box blur、convolution）[HEUR]。
- 输出 image 若同时作为输入（ping-pong），需确保 read/write 同步，通常使用双缓冲避免 self-dependency hazard [ENGINE]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| transfer upload / graphics pass | input image | `TRANSFER_WRITE` / `COLOR_ATTACHMENT_WRITE` → `SHADER_READ`；`TRANSFER_DST_OPTIMAL` / `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | compute shader read |
| compute shader write | output image | `SHADER_WRITE` → `SHADER_READ`；`GENERAL` → `SHADER_READ_ONLY_OPTIMAL` | graphics fragment sample |
| compute shader write | output image | `SHADER_WRITE` → `SHADER_READ` / `SHADER_WRITE`；保持 `GENERAL` | next compute pass read/write |
| compute shader write | output image | `SHADER_WRITE` → `TRANSFER_READ`；`GENERAL` → `TRANSFER_SRC_OPTIMAL` | `vkCmdBlitImage` / `vkCmdCopyImage` |

必须说明：

- producer stage / access：compute shader 写入为 `VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT` + `VK_ACCESS_SHADER_WRITE_BIT`。
- consumer stage / access：graphics fragment 采样为 `VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT` + `VK_ACCESS_SHADER_READ_BIT` [SPEC]。
- image barrier 的 `subresourceRange` 应精确到目标 mip / layer；3D image 作为 storage image 时 `baseArrayLayer=0, layerCount=1` [SPEC]。
- 邻域stencil采用不同输入/输出存储，跨阶段用Vulkan依赖；同dispatch的跨workgroup竞争不能用event修复。单invocation独占像素的原位操作另按读写集合判断 [SPEC]。
- 跨 queue（compute queue → graphics queue）必须使用 semaphore，不能仅靠 pipeline barrier [SPEC]。

---

## 8. 实现步骤

1. **确认 format 支持**：通过 `vkGetPhysicalDeviceFormatProperties` 确认 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT`；若需 atomic，确认 `VK_FORMAT_FEATURE_STORAGE_IMAGE_ATOMIC_BIT` [SPEC]。
2. **创建 output image**：`usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT`（若后续采样）；`initialLayout = VK_IMAGE_LAYOUT_UNDEFINED`；`samples = VK_SAMPLE_COUNT_1_BIT` [SPEC]。
3. **创建 image view**：`viewType = VK_IMAGE_VIEW_TYPE_2D`，`subresourceRange` 限定目标 mip/layer；multisample image 不能直接作为 storage image [SPEC]。
4. **创建 descriptor set layout**：binding0 `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE`，stageFlags = `VK_SHADER_STAGE_COMPUTE_BIT`；binding1 可选 `COMBINED_IMAGE_SAMPLER` 或 `STORAGE_IMAGE` [SPEC]。
5. **更新 descriptor set**：output image 的 `imageLayout = VK_IMAGE_LAYOUT_GENERAL`；input sampled image 的 `imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` [SPEC]。
6. **创建 compute pipeline**：编写 `write_storage_image.comp`，使用 `layout(set=0, binding=0, rgba8) uniform image2D outImage;`；编译 shader module 并创建 compute pipeline [SPEC]。
7. **录制 command buffer**：
   - transition output image `UNDEFINED` → `GENERAL`（首次）或 `SHADER_READ_ONLY_OPTIMAL` → `GENERAL`（后续帧复用）。
   - 若读 input image，transition 到 `SHADER_READ_ONLY_OPTIMAL`。
   - `vkCmdBindPipeline(COMPUTE)`、`vkCmdBindDescriptorSets`。
   - 设置 push constants（如需要）。
   - `vkCmdDispatch((width + wgX - 1)/wgX, (height + wgY - 1)/wgY, 1)`。
   - 插入 `vkCmdPipelineBarrier`：output image `GENERAL` + `SHADER_WRITE` → `SHADER_READ_ONLY_OPTIMAL` + `SHADER_READ`。
8. **consumer pass 接入**：graphics pass 中绑定 output image 为 sampled texture；compute next pass 中保持 `GENERAL` 并只更新 access mask。
9. **ping-pong 处理**：若 compute 多 pass 原位迭代，准备 A/B 两张 image，每帧交换 descriptor 指向 [ENGINE]。
10. **接入 resize / recreate**：storage image 通常不随 swapchain 重建；若与 surface extent 绑定，resize 后重建 image、view、descriptor [ANDROID]。
11. **接入销毁路径**：按 `descriptor set → pipeline → pipeline layout → image view → image → memory` 释放；VMA 用户统一 `vmaDestroyImage`。

---

## 9. Android 注意点

- storage image和compute device/queue不要求绑定Surface；呈现路径另查Surface支持，保留独立模拟的生命周期 [SPEC][ANDROID]。
- 移动端同样必须提供storage write→sampled read依赖与合法layout；合法GENERAL采样无需强制transition，带宽/tile影响按目标设备测量 [SPEC][ENGINE]。
- TBDR 架构下 compute storage image 与 graphics sampled image 频繁切换会增加 external memory traffic；若 compute 输出直接用于 fullscreen fragment pass，需评估是否真的比 fragment shader 直接写更高效 [ANDROID]。
  - 适用条件：compute 需要 shared memory tile 优化、subgroup 操作、或跨 workgroup 聚合时收益明显 [HEUR]。
- rotation / resize 触发 swapchain recreate，若 storage image 与 surface extent 绑定，需重建并重新 transition [ANDROID]。
- pause / resume期间禁止访问已退休的Surface相关资源；共享world的独立storage image按可见性政策和全消费者完成条件管理 [ANDROID][ENGINE]。
- logcat 验证：`adb logcat -s vulkan` 检查 `VUID-vkCmdDispatch-None-04547`（storage image layout 错误）、`VUID-vkCmdDispatch-None-08612`（format qualifier 不匹配）等 [TOOL]。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 storage image descriptor、layout、format qualifier 相关错误 [TOOL]。
- [ ] RenderDoc / AGI：Texture Viewer 中可见 compute 写入后的 image 内容；Image Layout 状态正确 [TOOL]。
- [ ] 截图 / 数值验证：compute 输出 image 在后续 graphics pass 中采样结果正确，无色彩偏移、黑屏、条纹。
- [ ] logcat（Android）：无 validation error；可输出 storage image 尺寸与 dispatch 网格用于校验。
- [ ] 性能指标：
  - compute dispatch 耗时稳定，无过大 workgroup；
  - AGI 中 storage image write 与 graphics read 之间无过长 stall；
  - bandwidth 在适用场景下优于 graphics fullscreen pass [TOOL]。
- [ ] resize / pause / resume 后 storage image 内容正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。

---

## 11. 常见失败模式

1. **未加 `STORAGE_BIT`**：image usage 缺失导致 descriptor update 失败 [SPEC]。
2. **compute 写布局错误**：storage image 写入时未在 `GENERAL` 布局，触发 validation error [SPEC]。
3. **format qualifier 不匹配**：GLSL `layout(rgba8)` 与 image format 不一致 [SPEC]。
4. **compute → graphics 同步缺失**：未建立写→采样依赖，或descriptor与实际layout不一致；不以是否transition判断同步正确 [TOOL]。
5. **multisample storage image**：创建 image 时 `samples > 1`，compute pipeline 无法绑定 [SPEC]。
6. **subresource range 错误**：barrier 范围与实际 image 维度不匹配，导致部分区域未同步 [SPEC]。
7. **in-place read/write hazard**：同一 image 既读又写未做 ping-pong，产生 artifact [SPEC]。
8. **Surface重建期间引用旧代输出**：访问已销毁的image/view/descriptor；独立compute不会仅因Surface销毁而失效 [ANDROID][ENGINE]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本 / GPU。
- storage image 格式、尺寸、usage、mip 层级。
- format properties 中 `VK_FORMAT_FEATURE_STORAGE_IMAGE_BIT` 是否支持。
- compute shader `imageStore` 代码与 format qualifier。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 storage image layout 与内容。
- Android lifecycle 日志。

<a id="heightfield-simulation-contract"></a>
## 有界高度场与事件注入（C3）

输入：世界尺寸、Nx/Ny与dx/dy、常波速c、h、阻尼、边界mask、height+velocity（或两个时刻height）、有界eventId列表、模型/world/topology generation。输出：同tick/generation的height/normal snapshot、数值诊断与事件消费记录。适用单值二维线性高度场波动，不支持翻卷/破碎/完整体积流动，不自动等于非线性浅水、Navier–Stokes或三维流体。[ENGINE][REF]

明确选择一个离散模型，例如无阻尼中心差分：`Hnext = 2*Hcurrent - Hprevious + c²*h²*Laplacian(Hcurrent)`，Laplacian 使用各轴 dx/dy。速度形式或阻尼项是另一明确配置，不能混用参数。该均匀网格、常c、显式线性二维基线的检查量 `r=c*h*sqrt(1/dx²+1/dy²)` 要≤1，实际选安全裕量；阻尼、非线性、边界或耦合改变后重新推导/测试。它不是所有水算法通用CFL公式，height clamp不能掩盖不稳定。[ENGINE]

链路：按tick去重事件→每单元gather有界source/impulse→只读旧稳定场、写下一场→应用指定边界→单独normal/gradient dispatch→发布同tick height+normal→独立高度可视化。三时刻差分的previous/current/next不可无证明别名；采用height+velocity的A/B打包状态时同样保持读旧写新。不能靠workgroup barrier同步全网格。[SPEC]

VkImage需核对目标tiling/format/image properties的STORAGE及SAMPLED能力，绑定匹配format与descriptor layout；write通常GENERAL，sample可保持合法GENERAL或transition到SHADER_READ_ONLY_OPTIMAL，仍需写→采样依赖。格式不支持时走SSBO状态与输出转换或另一受支持格式，不提高产品最低版本。每轮读→覆盖和写→下一轮读分别表达；尾部与shared halo加载必须满足 [kernel参与规则](../../03_api_manual/06_pipeline/compute_pipeline.md#simulation-kernel-portability)。

- 边界明确固定（Dirichlet）、反射（选定离散Neumann）或耗散，逐项验证角点与mask；更新不得越界读取邻点。
- 静水全零、无输入和匹配边界保持零；单/双脉冲按tick注入，渲染FPS不影响次数。重叠扰动由每单元唯一writer gather或独占归约，普通并发加法不是安全注入。
- source、force与impulse单位/空间和积分方式显式区分；密集事件超容量拒绝/降级并记录overflow。
- 分辨率变化保持世界尺度和c语义，重新计算dx/dy及稳定界；明确重采样/清空状态，递增代际、重新初始化需要的历史。
- normal由同一height的世界空间梯度生成，例如normalize((-dH/dx,1,-dH/dy))，按场景坐标系调整。旧normal配新height要报错，不靠滤波遮盖。
- 粒子命中只生成一次有界扰动，默认单向视觉耦合，复用 [调度与粒子池](add_compute_pass.md#simulation-scheduling)。透明水/玻璃外观属v1.0.15前置，未集成保持未验证，不阻塞高度/法线数值检查。

最小验收：零场、脉冲传播/边界、非法步长、尺寸变化、重叠与超容量事件；预注册CPU同离散模型位置/高度/能量或衰减误差，保存输入和时间序列。关联hard_rules 3/10/17；可视化、Shader编译和GPU读回分别证明不同层。来源：[Ten Minute Physics高度场教学](https://matthias-research.github.io/pages/tenMinutePhysics/index.html)（模型参考，不是Vulkan性能证据）、[Vulkan计算执行](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/shaders.adoc)。API详见 [image卡](../../03_api_manual/04_buffer_image_memory/image.md)、[交接依赖](compute_to_graphics_sync.md#simulation-render-handoff)。

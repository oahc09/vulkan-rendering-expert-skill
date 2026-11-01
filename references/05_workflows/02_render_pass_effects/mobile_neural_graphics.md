# Workflow: Mobile Neural Graphics

## 0. 适用范围

### 适用

- 评估既有 Vulkan 渲染器接入 Arm Neural Graphics SDK **v1.1.1** 的 NSS（超分）或 NFRU（插帧）。
- 需要区分目标手机原生能力、开发机仿真与传统回退；诊断重影、旋转后历史失效或多 Engine 集成风险。

### 不适用

- 模型训练、分发权重、重写 RHI，或把新 SDK 的示例版本作为全项目最低版本。
- 仅凭设备品牌、Vulkan 1.4 或仿真截图宣布目标手机可用/更快。

本卡是固定版本的独立工程摘要，来源见 §15；本次仅 source-read，未编译 SDK、未运行模型或手机。[REF][ENGINE]

## 1. 任务目标

```text
固定 SDK / shader / 模型 / API-ABI
→ 分离支持、启用与选中路径
→ 验证输入/历史与 Device/queue owner
→ 受控插入既有帧图
→ 验证图像、同步、pacing 与持续性能
→ 原生 / 仅仿真 / 标准回退决策
```

不强制引入 SDK；保留原始渲染、传统时域/空间缩放与关闭插帧的完整路径。[ENGINE]

<a id="neural-capability-contract"></a>
## 2. 输入条件与能力合同

先记录设备/GPU/driver、应用请求与设备支持的 API 版本、扩展枚举、feature 查询和 **Device 创建时实际启用记录**。事后查询物理设备不能证明已有 Device 启用了哪些可选位。[REF]

| 检查 | v1.1.1 路径边界 |
|---|---|
| API / 工具 | ARM tensor/data-graph 路径要求 Vulkan 1.3+；示例请求 1.4，不代表所有应用必须升至 1.4。SDK 工具推荐版本与设备运行时要求不同 |
| 图资源 | NSS/NFRU 检查 `VK_ARM_tensors`、`VK_ARM_data_graph` 及依赖；NFRU 还检查 `VK_ARM_data_graph_optical_flow`。逐项查询并启用选中路径的 feature |
| flags 依赖 | `VK_KHR_extended_flags` 或 `VK_KHR_maintenance5` 选一个有效依赖路径；maintenance5 功能已核心化到 Vulkan 1.4。NG layer 条件注入优先 maintenance5，但不会独立识别其 1.4 核心替代，仍须应用核验 |
| 同步 | 后端需要启用 `synchronization2`；`timelineSemaphore` 针对 SDK 插帧 swapchain 路径，不是手工 NSS/NFRU dispatch 的统一前提 |
| 算术/存储 | 按 shader permutation 检查 `shaderInt8`、条件性的 `shaderInt16`、8/16-bit storage、`shaderFloat16`；浮点精度开关不自动消除整数/存储要求 |
| tensor stage / format | 原生 tensor shader 还检查 `shaderTensorSupportedStages`；所选 image format 的 sampled/storage/attachment 能力另查，不能由 API 版本推断 |
| fragment / compute | 默认 NFRU fragment warp/preprocess 需 `fragmentStoresAndAtomics`；不具备时只有同时选相应 compute 分支且满足其格式/shader要求才可回退，不保证存在适用变体 |
| 后端初始化 | 此版本即便手工离屏 dispatch，函数表加载仍要求 surface/swapchain 入口；这是当前 `LoadVulkanFunctions` 实现约束（源码行 86、168–175，见 §15），不是神经算法固有要求 |

以上为固定 [兼容矩阵](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/docs/compatibility_matrix.md) 的选路检查摘要。[REF]
NG layer 的条件注入不能创造不支持的能力，也不替应用补齐所有 feature；原生与仿真层暴露的能力分别记录。扩展核心化后不一定需要旧扩展名，但仍需启用相应 feature。不要同时挂聚合与对应独立 feature 结构。[REF][SPEC]

## 3. 前置检查

- [ ] 项目已有 Evidence Map / Architecture Map；定位 Device、queue、帧图、allocator、历史资源和呈现 owner。
- [ ] 固定 SDK commit、子模块、模型文件版本/哈希、shader 产物、编译选项及宿主 ABI。
- [ ] SDK **1.1.1** 不与 1.1.0 头文件/二进制/custom backend 混用；重新编译并审查旧数字 flag、结构大小与回调。
- [ ] 软件、文档、模型授权分开：仓库软件 MIT；Developer Guide 单独 CC BY-ND 4.0；VGF 模型遵循 Arm AI Model Community License。链接不代表取得分发权，不自动复制权重。[REF]
- [ ] 不自动开启或上传应用数据集采集；确认输出内容、存储预算、权限与退出清理，采集开销不混入正常性能测量。[ENGINE]

## 4. Vulkan 对象链路

```text
既有 VkInstance / VkPhysicalDevice / VkDevice / queue
→ 现有 allocator 与 backend callbacks
→ NSS / NFRU context（不是新 Device）
→ 输入 image / history / tensor / data graph / shader pipeline
→ 同一帧图内的 prepare / dispatch 与依赖
→ 输出 scene color → UI → 既有 presentation owner
→ GPU 完成证据 → context/资源退役
```

NFRU 本身产生插值图像，不替应用保证正确呈现与帧节奏。手工 dispatch 和 SDK swapchain 集成是两条接入方案，不应无验证地同时叠加 SDK 包装、Swappy 和引擎 pacing。[REF][ENGINE]

<a id="neural-input-history"></a>
## 5. 资源设计与输入/历史合同

| 输入/资源 | 必须明确 | owner / 生命周期 |
|---|---|---|
| color | HDR/LDR、线性/曝光约定、render/display 尺寸、UI 是否已混入 | 应用输入；GPU 使用完前不复用 |
| depth | reverse-Z、近远平面、无限远、与颜色/motion 的坐标和尺寸关系 | 应用输入；外部 previous-depth 保持到配对 dispatch 及 GPU 完成 |
| motion vectors | 当前→前帧方向、单位、Y 方向、是否含 jitter；用确定性平移验证比例和符号 | 应用输入，不把旧帧向量错配新 frame ID |
| jitter | render-pixel sample-position offset，不是 MV/depth 或 display 像素；避免重复取消 camera jitter | 与同一真实帧绑定 |
| exposure | NSS scalar 或被选中的 exposure texture；与输入颜色约定一致，不给缺失输入造默认正确性 | scalar 与 texture 路径显式选择 |
| history | NSS 外部 ping-pong 或 SDK 管理二选一；NFRU 外部历史仍须提供合法绑定 | 禁止销毁仍被读取的旧代资源 |
| output | sampled/attachment/storage/transfer 用途按实际路径与 reset copy 检查 | SDK 借用外部资源不等于接管其销毁 |

NSS 的 backward motion 缩放到 render-pixel 空间；NFRU 的 motion 缩放按 `mvDepthSize`（特定 display-MV 路径另有约定），不能原样套用同一比例。NFRU view-projection 使用未 jitter 的矩阵。按固定 NSS/NFRU 指南校验精确字段，不伪造通用 SDK API。[REF]

第一帧、camera cut、场景切换、失去连续历史时使用所选接口的 reset；resize、rotation、动态分辨率还须检查 context 固定尺寸和各输入坐标是否变化，必要时等 GPU 完成后重建，而不只是清一个布尔值。Android pre-rotation 不由 SDK 自动纠正。NFRU 外部历史模式下 reset 不豁免 previous-color/depth 绑定。[REF][ENGINE]

## 6. Pipeline / Descriptor 设计

- 每个变体列出 compute/fragment/data-graph 工作、输入输出格式与 layout，不把 fragment 改 compute 当作免费优化。
- v1.1.1 的若干 compute/fragment、HDR/LDR、16-bit 选择 flag 与 1.1.0 语义反转；重新按名称构造配置，禁止沿用序列化旧数字 mask。[REF]
- SDK、custom backend 与 shaders 一起重建；模型与 shader 的匹配版本分别校验。兼容矩阵列 NSS 模型 1.0.1、NFRU 模型 2.0.0，不等于可忽略实际模型产物哈希。[REF]
- 只为实际使用申请 image usage；不无条件给 depth/motion 图附加 storage usage。先验证格式支持与描述，再注册资源。[REF]

## 7. 同步与 Layout 设计

| Producer | Resource | 依赖 | Consumer |
|---|---|---|---|
| 渲染 pass | color/depth/motion | 按实际写入 stage/access → 选中 SDK shader/graph 读取，核对 layout | NSS/NFRU |
| NSS / NFRU | output/history | 输出写入 → 下一 shader、UI、copy 或 present 的实际访问 | 后处理/下一帧/呈现 |
| SDK 先前帧工作 | context 内部与外部历史 | GPU 完成与退役条件，不只 CPU 函数返回 | 重建/销毁 |

SDK 的录制不替代应用对跨 command buffer/queue、外部 image 状态与所有权的同步。保留现有提交系统；present semaphore 的消费与资源退役仍遵守既有 WSI 契约。[REF][SPEC]

<a id="neural-engine-lifetime"></a>
## 8. 实现步骤与多实例边界

1. 固定版本并取得真实能力记录，选择 NSS / NFRU 及手工 dispatch / swapchain 路径，不先替换引擎基础设施。
2. 在已选 Device/queue 上创建 backend/context，逐项检查返回值与 resource descriptor；记录 engine ID、context ID、Device、frame ID、resource generation。
3. 串行首次后端初始化：v1.1.1 的 Vulkan 函数表是 **process-global**，`InitVulkanWrapper` 只在首次成功时加载；没有按 Device 索引、初始化锁或 context 销毁后的自动重置；见 §15 的 `GetVulkanFunctionTable` / `InitVulkanWrapper` 与 `DestroyBackendContextVK` 固定源码。这里指函数表加载无锁，不否认 C++ 局部 static 对象本身的初始化规则。[REF]
4. 多 Engine 共用同一 Device 仍须隔离 context/history 并序列化每个 context 操作；多 context 不证明多独立 VkDevice 安全。独立多 Device、原 Device/loader 销毁再创建均未获此实现保证；保持来源 Device/loader 有效，无法满足则关闭此路径。[REF][ENGINE]
5. 首先验证单帧输入与 reset，再接连续帧。NFRU 同一 context 一次只保留一个待 dispatch 的 prepare，prepare/dispatch frame ID 配对且按序执行。[REF]
6. 选定唯一 presentation/pacing owner；UI 通常在 NFRU 后合成，不能提供时序一致 depth/motion 的效果单独评估。[REF]
7. 输入参数错误按返回值修正；backend/OF/FI 失败不提交半成品 command list，不继续普通插帧。停止该路径，按已提交工作完成情况安全退役/重建，显式启用标准 fallback；SDK 报错不等于已自动回退。[REF][ENGINE]
8. 销毁前等待所有引用 context、callback/user data、image 和历史的 GPU 工作完成。恢复不改变 Device/loader 全局函数表限制。

## 9. Android 注意点

rotation/resize、前后台、Surface 重建、extent=0、动态分辨率逐项覆盖；没有 Surface 时暂停呈现。将输入/历史 generation 与 Surface/尺寸变化解耦记录，避免把“窗口恢复”当作“历史仍有效”。尊重热保护，不通过延长超时或解除温控伪造持续性能。[ANDROID][ENGINE]

<a id="neural-fallback-decisions"></a>
## 10. 验证方式与三类决策

| 决策 | 前提 | 可以声明 / 不可声明 |
|---|---|---|
| 可进入原生接入验证 | 实际目标设备支持且已启用全部选中路径条件，输入和 owner 合同满足 | 可以安排原生测试；未跑前不写 native PASS 或性能改善 |
| 仅仿真验证 | 能力由开发层提供，真实手机无对应路径或尚未验证 | 可验证数据/部分功能；不能宣称移动原生性能、功耗或驱动支持 |
| 当前应回退 | 缺 feature/格式、输入、合法 owner、受支持多 Device 或版本组合 | 使用既有传统缩放/原分辨率/关闭插帧；不要求换 GPU 或提高全项目基线 |

- [ ] Static / Snapshot / Live / Device 各自报告；模型回答正确不代表真实图像正确。
- [ ] 检查运动、遮挡、细线、曝光变化、UI、camera cut、resize/rotation 的重影/闪烁；用原始渲染作对照。
- [ ] 分开统计逻辑帧、真实渲染帧、生成帧、呈现帧，记录 P50/P95/P99、CPU/GPU、内存与持续热状态；有可靠设备再报告输入延迟/功耗。NFRU 有额外帧延迟，displayed FPS 提高不等于响应改善。[REF][ENGINE]
- [ ] 同设备/driver、场景、分辨率、画质、刷新率与热条件 A/B；采集开销单列；没有 profiler/counter 不能填带宽收益。
- [ ] 实际完成声明按适用 G1–G6 给证据；没有原生设备/宿主时保持未验证。

## 11. 常见失败模式

Vulkan 1.4 被当作 tensor 支持；feature 查询结果被当作 Device 启用记录；混用 1.1.0 ABI/数字 flag；错误 motion 单位或重复 jitter cancellation；reset 后继续复用错尺寸 history；多个 Engine 无隔离；两个 Device 共用进程函数表；把 SDK CPU scheduling 日志当 GPU 执行时间；把仿真/显示 FPS 当原生性能验收。

## 12. 相关 API 卡片

- [同步](../../03_api_manual/08_synchronization/synchronization2.md)
- [呈现退役](../../03_api_manual/02_surface_swapchain/swapchain_recreate.md#present-retirement-contract)

## 13. 相关 Debug Playbook

- [Device lost](../../04_debug_playbooks/02_crash_hang/device_lost.md)
- [工具证据](../../04_debug_playbooks/tool_usage.md)

## 14. 不确定时如何处理

优先补设备/启用记录、SDK/model/shader 精确版本、选中路径、输入元数据及 context/Device owner 图；没有这些先给条件方案，不猜支持。只读项目时输出风险与验证计划，不写已完成集成。

## 15. 需要回查官方文档的情况

以 2026-11-01 核验的 Arm v1.1.1 commit `019e99a62ea3a331fe112516190d77befc779a53` 为来源边界，升级、换 Device/driver、变体、模型或尺寸策略后重查：

- [Release：2026-10-30](https://github.com/arm/neural-graphics-sdk-for-game-engines/releases/tag/v1.1.1)
- [兼容矩阵](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/docs/compatibility_matrix.md)
- [实际加载源码：`LoadVulkanFunctions`，surface 行 86；swapchain/present 行 168–175](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/sdk/src/backends/vk/vk_wrapper.cpp#L71-L225)
- [全局函数表与首次加载：`GetVulkanFunctionTable` / `InitVulkanWrapper` 行 232–246](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/sdk/src/backends/vk/vk_wrapper.cpp#L228-L254)
- [销毁路径：`DestroyBackendContextVK` 行 2889–2972，清理 context 而未重置全局函数表](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/sdk/src/backends/vk/ffx_vk.cpp#L2889-L2972)
- [API/ABI 迁移](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/docs/migration_note.md)
- [NSS 输入与历史](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/docs/NSS/NSS.md)
- [NFRU prepare/dispatch、坐标与生命周期](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/docs/NFRU/NFRU.md)
- [许可分层说明](https://github.com/arm/neural-graphics-sdk-for-game-engines/blob/019e99a62ea3a331fe112516190d77befc779a53/README.md#license)

1.1.1 的新增采集/诊断与 ABI 改动不意味着 NSS/NFRU 均首次出现于 2026 年 10 月。本文不附第三方文档整包或模型权重。

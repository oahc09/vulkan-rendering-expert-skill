# 定向行为评估记录

> 合并状态：本记录的 4/4 行为结果仅对应下述旧工作区指纹。随后同步了远端 `755e2463d76d2975b952d7a88d6254b281183453` 的 33 个提交，保留其 v1.0.9 入口精简、项目诊断与规范修订；这些输入变化后未重跑模型评估，不能把历史 PASS 视为合并后的行为验收。
>
> 合并后另执行结构检查及 `git diff --check`；入口文件片段引用按文件部分校验。当前源文件数为 202，旧 200 文件预算未通过；未调整预算、删除上游资料或宣称发布就绪。

日期：2026-10-25（Asia/Shanghai）。本次仅评估四个知识库行为场景，结果 4/4 PASS；旧题库 1–7 未运行，真实 Vulkan / GPU / Android 验收未运行。本记录不是发布验收结论。

宿主为 Codex；三个只读子代理使用 `fork_turns=none`，继承主会话模型与推理配置，工具未返回精确模型 ID，不能据此声明其他模型同样通过。版本题与证据边界题各用一个上下文；帧循环和 WSI 两题共用第三个上下文，因此这两题不是完全独立的单题会话，也没有测多次采样稳定性。

基线提交：`6ccdc5eddabfba69670b8c12e5bc14a08b8ee25b`。评估使用包含未提交修订的工作区，不能只凭该提交复现修订后的内容。以下 SHA-256 对路径排序，以 `路径 + NUL + 文件原始字节 + NUL` 顺序计算；整体指纹覆盖检查器选择的 SKILL / agents / references 文件，排除本记录以避免自引用；每个上下文另列实际加载文件指纹。行尾或内容变化都会改变指纹。

- sourceSha256: `d99569c4249cdb4f6957e15d243cf1f6d31f0b103f8954434b8623b87c78a736`
- 版本上下文 loadedSha256: `f69d523a073a944ddb932788a994d96fe908a5297ec754e44550f19d09015fdf`
- 帧循环 / WSI 上下文 loadedSha256: `0464defc5a957046d6c508a373d41e09741e97deab1702bdbfa6d0120cbde4df`
- 证据边界上下文 loadedSha256: `5a7cf8e91418326cefadf4b1a720f811bc8b533fdd662bacaccdcbc5f0e9ad66`

三个上下文只收到技能入口和原始问题，未提供判据、怀疑原因或预期修复，并被明确禁止读取 `integration_test_plan.md`、`change_log.md`、`reports/`、`docs/` 和历史评估材料；均报告未修改文件。评估方按 `integration_test_plan.md` 的四行判据核对以下原始回答，没有使用关键词匹配代替判断。

| 场景 | 结果 | 判断依据 |
|---|---|---|
| 版本与 feature struct | PASS | 正确使用 API 版本数值宏、字段归属和显式启用链，没有把所有字段放进 Vulkan14Features |
| acquire / fence 异常路径 | PASS | 指出 reset 后跳过 submit 的死锁，区分 OUT_OF_DATE / SUBOPTIMAL，并覆盖 submit 失败恢复 |
| present semaphore 复用与退役 | PASS | 区分 frame slot / imageIndex；没有用 submit fence 或 WaitIdle 单独证明 present 资源安全回收 |
| API 解释与未运行方案 | PASS | 正常解释 API 并给候选方案，拒绝把未运行方案称为运行验证通过；未机械展开 G1-G6 |

## 原始回答：版本与 feature struct

输入：`设备 apiVersion 要和哪个 1.4 宏比较？scalarBlockLayout、sync2、timelineSemaphore 分别在哪个 feature struct 启用？`

设备的 `VkPhysicalDeviceProperties.apiVersion` 应与 **`VK_API_VERSION_1_4`** 比较：

```cpp
VkPhysicalDeviceProperties props{};
vkGetPhysicalDeviceProperties(physicalDevice, &props);
bool supports14 = props.apiVersion >= VK_API_VERSION_1_4;
```

`VK_API_VERSION_1_4` 是 `VK_MAKE_API_VERSION(0, 1, 4, 0)`；`VK_VERSION_1_4` 是头文件能力宏，不能用于这个数值比较。依据：[VK_API_VERSION_1_4](https://docs.vulkan.org/refpages/latest/refpages/source/VK_API_VERSION_1_4.html)。

三个 feature 的归属如下：

| Feature | 核心聚合 feature struct | 可替代的独立 feature struct |
|---|---|---|
| `scalarBlockLayout` | `VkPhysicalDeviceVulkan12Features` | `VkPhysicalDeviceScalarBlockLayoutFeatures` |
| `synchronization2`（sync2） | `VkPhysicalDeviceVulkan13Features` | `VkPhysicalDeviceSynchronization2Features` |
| `timelineSemaphore` | `VkPhysicalDeviceVulkan12Features` | `VkPhysicalDeviceTimelineSemaphoreFeatures` |

依据：[Vulkan12Features](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceVulkan12Features.html)、[Vulkan13Features](https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDeviceVulkan13Features.html)、[VkDeviceCreateInfo](https://docs.vulkan.org/refpages/latest/refpages/source/VkDeviceCreateInfo.html)。

即使设备支持 Vulkan 1.4，这些字段仍位于上述结构体中。使用前应在 `vkCreateDevice` 的 `pNext` 链中显式启用，例如：

```cpp
VkPhysicalDeviceVulkan13Features enabled13{};
enabled13.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES;
enabled13.synchronization2 = VK_TRUE;

VkPhysicalDeviceVulkan12Features enabled12{};
enabled12.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES;
enabled12.pNext = &enabled13;
enabled12.scalarBlockLayout = VK_TRUE;
enabled12.timelineSemaphore = VK_TRUE;

// deviceCI 已填好队列等其他必要参数。
deviceCI.pNext = &enabled12;
```

关键调用路径是：`vkGetPhysicalDeviceProperties` 检查版本 → 必要时通过 `vkGetPhysicalDeviceFeatures2` 查询支持 → 构造启用链 → `vkCreateDevice`。查询支持与启用 feature 是两件事。

最高优先级检查项：同一条启用链不要同时放入聚合结构体及其对应独立结构体，例如 `Vulkan12Features` 与 `TimelineSemaphoreFeatures`。规范对应 `VUID-VkDeviceCreateInfo-pNext-02830`、`06532`。最小验证是在目标设备记录 API 版本和查询结果，检查启用链，并用 Validation Layer 检查设备创建及首次相关 API 使用。设备版本检查也需与应用请求版本和所选核心/扩展路径匹配。

本次已核对官方字段和启用规则；没有目标设备运行证据，因此没有验证具体设备支持情况或上述片段的运行结果。

## 原始回答：帧循环

输入：`帧开始 wait 后立刻 reset fence，acquire 返回 OUT_OF_DATE 就 return；SUBOPTIMAL 也 return，可以吗？`

不可以直接这样处理。它有两个不同的问题：

1. **先 reset，再因 `OUT_OF_DATE` 返回，会留下没有提交负责 signal 的 fence。** 下次复用同一个 frame slot 时，`vkWaitForFences` 可能永久等待。最小修改是：成功 wait 后先 acquire，命令录制成功并确定马上 submit 时才 reset fence。官方教程明确描述了这个死锁及修正顺序。[官方 Swapchain Recreation 教程](https://docs.vulkan.org/tutorial/latest/03_Drawing_a_triangle/04_Swap_chain_recreation.html)

2. **`SUBOPTIMAL` 表示成功取得 image，并已安排 acquire 同步对象的 signal。** 不能把它当作“没有取得 image”直接返回并正常进入下一轮；否则可能遗留已获取的 image，以及没有被 wait 消费的 acquire semaphore。默认做法是完成本帧 submit / present，随后重建。成功 acquire 的信号语义见 [WSI 规范](https://docs.vulkan.org/spec/latest/chapters/VK_KHR_surface/wsi.html#vkAcquireNextImageKHR)。

建议顺序：

```text
vkWaitForFences(frameFence[slot])，检查成功
→ vkAcquireNextImageKHR(..., acquireSemaphore[slot], VK_NULL_HANDLE, &imageIndex)

OUT_OF_DATE：
    标记/执行重建，然后返回
    不使用 imageIndex，不 reset frameFence

TIMEOUT / NOT_READY：
    跳过本轮，不使用 imageIndex，不 reset frameFence

SUCCESS / SUBOPTIMAL：
    SUBOPTIMAL 只设置稍后重建标志
    → reset command buffer / pool
    → 更新安全可写的 per-frame 数据
    → begin / record / end command buffer
    → vkResetFences(frameFence[slot])
    → vkQueueSubmit(
          wait   = acquireSemaphore[slot],
          signal = renderFinished[imageIndex],
          fence  = frameFence[slot])
    → 检查 submit 成功
    → vkQueuePresentKHR(wait = renderFinished[imageIndex])
    → 按 acquire / present 结果决定重建
```

`SURFACE_LOST`、`DEVICE_LOST` 和其他错误进入相应恢复路径。若录制失败或 submit 失败，也不能继续普通帧循环：成功 acquire 后的 image / semaphore 状态需要收尾；reset 后但没有成功提交的 fence 不能继续按“已有提交”等待。

如果旧代码已经把 fence reset 后跳过提交，单纯重建 swapchain 不会自动让该 fence signal。需要在确认没有 pending 使用的前提下恢复 slot 状态，例如替换为初始 signaled 的 fence，或明确跟踪该 slot 尚无有效提交；不能用再次 reset 来解决。

最小验证：记录 `slot`、`imageIndex`、wait/acquire/submit/present 返回值和“是否实际提交”，反复 resize、最小化恢复；启用 Validation 与同步验证，检查是否存在 reset 后无 submit、未消费 acquire 信号或 semaphore 非法复用。当前没有你的实际帧循环和运行日志，因此这里只确认上述调用顺序的问题，未验证工程修复结果。

## 原始回答：WSI 资源退役

输入：`2 个 frame slot、3 个 swapchain image，renderFinished 按 frame slot 分配；frame fence 结束后能复用或随旧 swapchain 释放吗？`

**仅凭 frame fence 完成不可以。** submit fence 证明相关提交完成，不证明 presentation 已经结束使用它的 wait semaphore。这与 frame slot 是 2 个、swapchain image 是 3 个无关；两个索引代表不同的资源生命周期。[官方 Swapchain Semaphore Reuse](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)

最短可靠的默认结构是：

```cpp
VkFence frameFence[2];
VkSemaphore acquireSemaphore[2];
VkCommandBuffer commandBuffer[2];

VkSemaphore renderFinished[3]; // 实际按 vkGetSwapchainImagesKHR 数量创建
```

每帧的对象链：

```text
wait frameFence[slot]
→ acquire，用 acquireSemaphore[slot]，取得 imageIndex
→ submit：
     wait acquireSemaphore[slot]
     signal renderFinished[imageIndex]
     signal frameFence[slot]
→ present：
     wait renderFinished[imageIndex]
```

再次 acquire 到同一个 image，并通过 acquire semaphore 的 wait 或 acquire fence 等待建立完成依赖后，先前使用该 image 的 present 已完成相关等待，才获得复用该 image 对应 `renderFinished` 的依据。只取得 `imageIndex` 后立即在 CPU 上销毁旧 semaphore，不等于已经等到了 acquire 完成。

按 frame slot 分配并非绝对禁止，但必须另有可靠的 present 完成追踪。不能把 submit fence 当作这个证明。

重建时建议把资源分开处理：

- **提交侧资源**：所有引用旧 framebuffer / image view 等资源的提交完成后，可按依赖关系销毁这些资源。
- **presentation 侧资源**：旧 swapchain 与旧 `renderFinished` 数组一起进入延迟退役队列；创建新 swapchain 并不代表它们已经可以销毁。

如果支持并启用了 `VK_KHR_swapchain_maintenance1` 或对应 EXT 路径，给 present 绑定独立 present fence。相关 present fence signal 后可释放相应 wait semaphore；旧 swapchain 的所有历史 present 请求都满足相应 fence 条件后，且其他相关使用结束，才销毁旧 swapchain。这个 fence 表示资源回收条件满足，**不等于画面已经完成物理显示**。[`VkSwapchainPresentFenceInfoKHR` 规范](https://docs.vulkan.org/refpages/latest/refpages/source/VkSwapchainPresentFenceInfoKHR.html)

没有该扩展时，可采用官方样例的延迟退役策略：正常运行通过同一 image 的后续 acquire fence 追踪旧 present；重建后将旧 swapchain 和剩余 present semaphore 的释放，延迟到新 swapchain 第一次 present 已获得可回收证明的时点。连续重建需要串联保留尚未退役的旧对象。[官方 Swapchain Recreation 样例](https://docs.vulkan.org/samples/latest/samples/api/swapchain_recreation/README.html)

`vkDeviceWaitIdle` / `vkQueueWaitIdle` 是常见兼容做法，但不能单独作为无扩展 presentation 资源已释放使用的严格证明；退出时没有后续 acquire 的问题尤其需要区别对待，官方 Guide 也明确指出这个限制。

最小验证：给 semaphore 命名并记录 `swapchain generation / slot / imageIndex / present fence`，运行连续 resize 与多帧循环，启用 Validation 和同步验证；重点检查重新 signal 仍被旧 present 使用的 semaphore，以及提前销毁旧 generation 资源。尚未核实你的目标设备是否支持 maintenance1、是否已启用 feature、是否已有其他 present 完成机制，也没有执行 GPU 运行验证。

## 原始回答：API 解释与未运行方案

输入：`只解释 barrier2 的 srcStageMask；另给一个未运行的同步方案，能否宣布运行验证通过？`

`barrier2` 的 `srcStageMask` 指定依赖的**源端 pipeline stages**：对于 `vkCmdPipelineBarrier2`，它从同队列、提交顺序位于 barrier 之前的操作中限定第一同步范围。它位于 `VkMemoryBarrier2`、`VkBufferMemoryBarrier2` 或 `VkImageMemoryBarrier2` 内，经 `VkDependencyInfo` 传给命令。[字段定义](https://docs.vulkan.org/refpages/latest/refpages/source/VkMemoryBarrier2.html)、[命令语义](https://docs.vulkan.org/refpages/latest/refpages/source/vkCmdPipelineBarrier2.html)

通常按 producer 实际发生访问的阶段选择。注意两个边界：

- 执行范围还包含规范定义的 logically earlier stages；内存访问范围不会因此自动扩大，仍受显式 stage 与 `srcAccessMask` 限定。
- `srcStageMask` 单独不能保证写入结果对后续读取可见；读写依赖还需要配套 access 和目标范围。[规范依据](https://docs.vulkan.org/spec/latest/chapters/synchronization.html#synchronization-pipeline-stages)

一个**未运行的同步方案**：假设已启用 `synchronization2`，copy 与 draw 在同一 graphics queue，上传源数据已经准备好，目标 buffer 具备 transfer-destination 和 vertex-buffer usage：

```text
producer: vkCmdCopyBuffer 写入 vertexBuffer
→ vkCmdPipelineBarrier2（位于 rendering scope 外）
  VkBufferMemoryBarrier2:
    srcStageMask  = VK_PIPELINE_STAGE_2_COPY_BIT
    srcAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT
    dstStageMask  = VK_PIPELINE_STAGE_2_VERTEX_ATTRIBUTE_INPUT_BIT
    dstAccessMask = VK_ACCESS_2_VERTEX_ATTRIBUTE_READ_BIT
    buffer / offset / size 覆盖实际写入和读取的范围
    srcQueueFamilyIndex = dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED
→ 开始 rendering，绑定 vertexBuffer，vkCmdDraw
```

这是 buffer 依赖，`oldLayout/newLayout` 不适用；资源须保持有效直到相关 GPU 使用完成。该方案限于上述同队列条件。[Buffer barrier 定义](https://docs.vulkan.org/refpages/latest/refpages/source/VkBufferMemoryBarrier2.html)、[官方上传示例](https://docs.vulkan.org/guide/latest/synchronization_examples.html#transfer-dependencies)

**不能宣布运行验证通过。**目前只能说“已形成基于规范的候选方案，尚未运行”。待执行：核对实际 feature、usage、范围与生命周期；启用 Validation 和同步验证跑该路径；通过抓帧或 readback 检查消费结果，再做目标平台的多帧回归。Validation 无报错也不能单独证明结果正确。

当前无法核实实际设备、驱动、feature 启用情况、工程参数、执行结果或性能；这些均未验证。规范字段解释不因缺少运行证据而失效。

## 实际加载资料

下列路径相对仓库根目录。三个上下文均完整读取的公共文件：

```text
SKILL.md
references/00_expert_entry/role.md
references/00_expert_entry/hard_rules.md
references/00_expert_entry/task_classifier.md
references/00_expert_entry/response_formats.md
references/00_expert_entry/accuracy_check.md
references/00_expert_entry/verification_gate.md
references/00_expert_entry/progressive_retrieval.md
references/07_integration_pack/task_routing_rules.md
references/07_integration_pack/retrieval_policy.md
references/01_source_map_and_api_manual_strategy/README.md
references/03_api_manual/api_index.md
```

版本上下文额外完整读取：

```text
references/01_source_map_and_api_manual_strategy/source_priority.md
references/01_source_map_and_api_manual_strategy/citation_rules.md
references/02_core_mental_model/vulkan_1_4_overview.md
references/03_api_manual/01_instance_device_queue/logical_device.md
references/03_api_manual/08_synchronization/synchronization2.md
references/03_api_manual/08_synchronization/timeline_semaphore.md
```

版本上下文还在来源策略、API 手册、心智模型三个相关模块执行了版本宏与三个 feature 的定向 `rg` 检索，只查看匹配行。额外搜索结果不是完整文件加载，未纳入该上下文 loadedSha256；整体 sourceSha256 覆盖这些仓库资料。

帧循环 / WSI 上下文额外完整读取：

```text
references/00_expert_entry/debug_priority.md
references/01_source_map_and_api_manual_strategy/trusted_sources.md
references/02_core_mental_model/synchronization_lifecycle.md
references/03_api_manual/03_command_buffer/fence_semaphore.md
references/03_api_manual/03_command_buffer/frames_in_flight.md
references/03_api_manual/02_surface_swapchain/swapchain.md
references/03_api_manual/02_surface_swapchain/swapchain_recreate.md
```

证据边界上下文额外完整读取：

```text
references/01_source_map_and_api_manual_strategy/source_priority.md
references/01_source_map_and_api_manual_strategy/citation_rules.md
references/03_api_manual/08_synchronization/synchronization2.md
references/03_api_manual/08_synchronization/buffer_memory_barrier.md
references/02_core_mental_model/synchronization_lifecycle.md
```

记录中的回答由独立上下文返回，外部规范链接由各答题上下文查询并引用；本记录不固定远端页面修订。复跑时需重新核对相关官方规则。本次模板围栏与仓库验证说明的后续修订不在上述完整加载文件中，没有替换答题输入或隐藏失败回答。

## 结构检查与检查器验证

执行 `node scripts/check-skill.mjs --max-files 200`：PASS，Git 可见文件 200、Markdown 194、本地文件链接 11、入口路径 39，模块计数一致。`git diff --check` 通过。文件预算包含检查脚本和本记录，未把本地忽略目录算入发布源文件集合。该检查不会调用模型或 GPU，也不校验远端链接内容、Markdown 锚点或完整 YAML schema。

在临时目录创建本仓库的本地共享 clone，并复制 Git 可见工作区文件进行检查器验证；没有暂存、提交或修改原仓库文件，完成后清理临时 clone：

| 隔离副本中的操作 | 实际结果 | 判定 |
|---|---|---|
| 不注入错误，文件预算 200 | exit 0 / PASS | 通过 |
| 向 README 增加指向 missing-fixture.md 的本地链接 | exit 1，报告对应断链 | 通过 |
| 把 07_integration_pack 的模块计数从 8 改为 99 | exit 1，报告 expected 99 / found 8 | 通过 |
| 不改文件，把预算设为 199 | exit 1，报告 200 > 199 | 通过 |
| 恢复副本，预算 200 | exit 0 / PASS | 通过 |

这些是检查器的正反向验证，不能计入四个模型行为场景，也不能计入 Vulkan 运行验收。独立模型评估所加载文件的指纹不包含检查器脚本；检查器源码应与本记录一同保存、复审。

## 远端同步后的静态检查

远端基线 `755e2463d76d2975b952d7a88d6254b281183453` 与本地修订 `143297cb3b87ce8c5c708adae26c9d27aa26c565` 整合后：`node scripts/check-skill.mjs` PASS；Git 可见文件 202、Markdown 196、本地文件链接 42、入口路径 14，模块计数一致，`git diff --check` 通过。入口引用减少来自上游 v1.0.9 的路由精简，未回退其新增项目诊断流程。

mergedSourceSha256: `9abbbc8fb9e0cd4d8c7ec9d7b84dc80171261699318c702fd614d95d0858c39a`。本值与前述历史 sourceSha256 不同；四项行为评估及 GPU 运行验收未针对该合并结果重跑。`--max-files 200` 仍按原预算判 FAIL（202 > 200），未放宽检查器的预算条件。

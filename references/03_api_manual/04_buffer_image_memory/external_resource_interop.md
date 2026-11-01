# API Card: External Resource Interop

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 资源链 / 同步链 / Android 平台链 |
| Vulkan 对象 | `VkDeviceMemory` / `VkBuffer` / `VkImage` / `VkSemaphore` |
| 常用 API | `vkGetPhysicalDeviceExternalBufferProperties` / `vkGetPhysicalDeviceImageFormatProperties2` / `vkGetPhysicalDeviceExternalSemaphoreProperties` / `vkGetMemoryFdKHR` / `vkGetSemaphoreFdKHR` / `vkImportSemaphoreFdKHR` |
| 适用平台 | Android / 支持相应外部句柄的平台 |
| 来源等级 | `[SPEC] [REF] [VENDOR] [ENGINE]` |
| 适用 Vulkan 版本 | 按核心/扩展路径查询；FD 与 AHB 扩展不由 API 版本单独保证 |

## 1. 一句话定位

共享 allocation 不等于共享执行顺序；内存表示、同步载荷、访问所有权与回收必须分别达成合同，不能看到一个 FD 就开始跨 API 读写。[SPEC][ENGINE]

## 2. 所属对象链路

```text
物理设备/驱动匹配 → handle-specific capability
→ exportable Vulkan resource + allocation → memory handle → 外部 API 对象
→ Vulkan release + signal → 外部 wait + acquire → 外部计算
→ 外部 release + signal → Vulkan wait + acquire → 原引擎消费/退役
```

上游复用原 allocator、queue 与 retirement 系统；下游 descriptor 只引用已经完成回交的资源。Vulkan 与 OpenCL 两套对象可引用同一 allocation，但并不共享对象寿命。[ENGINE]

<a id="interop-capability-contract"></a>
## 3. 核心对象与 API

任一必要能力、设备/驱动或资源合同不满足时停止导入，回退现有 Vulkan Compute / 原算法路径；不自动强加 OpenCL 或升级整个项目的最低 Vulkan 版本。[ENGINE]

- Buffer 查询 `VkPhysicalDeviceExternalBufferInfo` / `VkExternalBufferProperties`；image 查询 `VkPhysicalDeviceExternalImageFormatInfo` 与 `VkExternalImageFormatProperties`。按准确 usage、format、tiling、samples、handle type 检查 import/export、compatible handle types 及 dedicated-only 条件。[SPEC]
- 同步独立查询 `VkPhysicalDeviceExternalSemaphoreInfo` / `VkExternalSemaphoreProperties`，分别检查两个传输方向。头文件、函数指针、API 版本、扩展支持、feature 启用是不同证据。[SPEC]
- OPAQUE_FD 内存互操作按 `VkPhysicalDeviceIDProperties.deviceUUID` 和 `driverUUID` 对比 OpenCL `CL_DEVICE_UUID_KHR` / `CL_DRIVER_UUID_KHR`；仅 device UUID 相同不足以证明兼容。两者匹配仍需资源参数与 handle 能力检查。[REF]
- `VkExternalMemoryBufferCreateInfo` / `VkExternalMemoryImageCreateInfo` 声明资源可用句柄；`VkExportMemoryAllocateInfo` 声明可导出 allocation。满足 dedicated allocation 与 memory requirements 后才 bind/export。[SPEC]

<a id="interop-handle-matrix"></a>
## 4. 标准使用流程

| 路径 | 表示与前置合同 | 不允许的推论 |
|---|---|---|
| Memory OPAQUE_FD | Buffer 先行；linear image 还需像素格式、stride/pitch、尺寸与大小一致 | FD 不自带通用 optimal-tiling 描述 |
| QCOM Vulkan opaque FD | Vulkan 侧仍用 OPAQUE_FD；OpenCL 侧需 `cl_qcom_external_memory_vulkan_opaque_fd` 的实际支持与对应导入类型 | 不是新的通用 Vulkan handle；不能推广到所有 Adreno/Mali |
| AHardwareBuffer | 查询 `vkGetAndroidHardwareBufferPropertiesANDROID`、格式/外部格式与对应 AHB 创建和导入合同 | 不能把 generic opaque-FD 样例直接当 Camera/MediaCodec 流程 |
| Semaphore SYNC_FD | 一次同步点的 copy payload；每次交接重新导出/导入；对象复用与载荷消费分开 | 不是 memory FD，也不是持久 timeline handle |
| Semaphore OPAQUE_FD | reference payload，只有双方支持该同步 handle 时才能选择 | 不能照搬桌面 opaque-semaphore 示例假定 Android 同样支持 |

先完成一条受支持的 buffer 往返；image 是另一个能力分支，不是换一个对象类型即可。[ENGINE]

SYNC_FD 导出要求 binary semaphore、已 signal 或已提交的 pending signal（及其依赖 signal 已提交），且没有 queue 正在等待该 semaphore。导出能力须在创建时声明；对 imported payload 再导出另查 exportFromImportedHandleTypes。每次交接不能仅凭对象存在就导出。[SPEC]
OpenCL `clReImportSemaphoreSyncFdKHR` 只重导入最初以 SYNC_FD 创建/导入的 semaphore；成功后不得再次操作已交给实现的 FD，重导入前仍须确认旧对象使用已完成。[SPEC]

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `handleTypes` / `handleType` | resource、allocation、导出/导入类型一致；memory 与 semaphore 枚举分开 | 把 SYNC_FD 用作内存 |
| `memoryTypeBits` / allocation size / alignment | 两端查询与 dedicated 条件共同约束 | 只按像素宽高算 allocation 大小 |
| `srcQueueFamilyIndex` / `dstQueueFamilyIndex` | 匹配实际外部所有权协议 | 把外部 semaphore 当成所有权转移 |
| `VkImportSemaphoreFdInfoKHR.flags` | SYNC_FD 使用 `VK_SEMAPHORE_IMPORT_TEMPORARY_BIT`，不能套 timeline 临时导入 | 永久复用某次已消费载荷 |
| image layout / subresource range | 按外部约定与实际 producer/consumer 访问确定 | 一个 FD 推导出布局或队列 owner |

## 6. 正确性检查点

### 创建阶段

- [ ] 两端设备/驱动、扩展版本、handle 能力、格式/tiling 与 allocation 参数已记录。
- [ ] 每个函数返回值检查，导入失败不会继续创建 descriptor 或提交消费者。

### 使用阶段

- [ ] 每个 frame slot 单独跟踪 memory owner、同步点与 resource generation。
- [ ] 两方向交接都有执行依赖及访问可见性；没有重用已消费的 sync payload。

### 销毁阶段

- [ ] Vulkan 与外部 API 的使用都已完成，不只等 Vulkan fence。
- [ ] descriptor/view/external object 与 allocation 按持有关系退休；未接管的 FD 有唯一清理者。

## 7. 高频错误

1. device UUID 相同而 driver UUID 不同仍继续 opaque-FD 导入。
2. 把 optimal image 用会假定 linear layout 的 OpenCL handle 导入。
3. signal/wait 完成但漏了两端 ownership release/acquire。
4. SYNC_FD 作为永久跨帧 semaphore 连接。
5. 导入成功后应用再次 close 同一 FD，或失败后遗留尚属应用的 FD。

## 8. Debug 检查路径

Validation 检查实际启用配置及 Vulkan 路径，不覆盖全部外部 API。日志关联 resource ID/generation、offset/range、handle 类型、导入状态、两端 queue/event 与回交点；不要记录或上传用户私有图像。通过确定性 buffer 输入、结果 readback/hash 和受影响 shader 的源码证据定位。工具无法抓外部工作时明确覆盖缺口，不伪造 GPU counter。[TOOL][ENGINE]

<a id="interop-lifetime-contract"></a>
## 9. 生命周期风险

调用 `vkImportSemaphoreFdKHR` 导入或重导入前，目标 semaphore 必须没有任何未完成的 queue command（`VUID-vkImportSemaphoreFdKHR-semaphore-01142`）；不能仅凭 temporary payload 可替换或 FD 已就绪就在旧 wait/signal 仍 pending 时重导入。[SPEC]

| 操作 | 成功后的 owner / 回收条件 | 失败处理 |
|---|---|---|
| Vulkan 导出 memory FD / semaphore FD | 应用获得新 FD；转交成功前由应用管理 | 不使用未定义输出；只回收实际获得且仍归应用的句柄 |
| OPAQUE_FD 导入 Vulkan memory / OpenCL memory | 成功后导入实现接管 FD，应用不得再操作该 FD；对象持有 payload 引用 | 不标记已转交；仍属应用的 FD 关闭一次 |
| SYNC_FD 导入 Vulkan / OpenCL semaphore | 成功接管 FD；Vulkan 是 temporary payload；完成相应 wait 后再进行下一次合法复用 | 不提交依赖缺失信号的消费者；保留 resource owner 状态，走恢复 |
| 外部计算提交后发生错误 | 原 allocation 保持存活直到所有已提交访问完成或按 device-lost 规则恢复 | 不因函数失败就立即释放仍可能 in-flight 的资源 |

上表针对已核对的 POSIX FD 路径；AHB 引用计数、其他 OS handle 与厂商专有导入细节另按其规范，不能沿用 FD close 规则。`fd == -1` 在 SYNC_FD 的特定 API 中可表示已 signal 的特殊载荷，不是普通有效 FD；按对应接口约束处理，不调用 close。[SPEC][REF]

<a id="interop-synchronization-contract"></a>
## 10. 同步风险

- CPU-GPU：底层资源回收需覆盖两个 API 的全部 pending 使用，host 查询返回不等于 GPU 完成。
- GPU-GPU：Vulkan producer release 后 signal；外部 wait 后 acquire；外部 release 后 signal；Vulkan wait 后 acquire。OpenCL out-of-order queue 必须显式连接 event wait-list，不能复制 in-order 示例的空 event list。[SPEC][REF]
- 资源访问：opaque-FD 工作流可使用 `VK_QUEUE_FAMILY_EXTERNAL`；AHB/foreign producer 按对应共享协议判断，不能统一替换为 EXTERNAL。Image 交接布局按合同（示例可为 GENERAL）；Vulkan 重获后再转为真实消费者布局。Buffer 没有 image layout，但仍有 range 与访问依赖。[SPEC]
- producer stage/access 覆盖实际写入；wait/acquire 覆盖最早消费者访问。semaphore scope 不替代 image layout 或 ownership barrier。[SPEC]

## 11. Android 注意点

Surface 暂停不代表外部 queue 已空。resize/rotation 后给资源新 generation，停止旧消费者，排空两端使用后退休旧尺寸资源；extent 为 0 时暂停展示，仍完成必要清理。外部资源与 swapchain image 不等价，不能随便导出 swapchain allocation。[ENGINE]

## 12. 性能注意点

避免 CPU staging 仅减少一类复制；ownership、cache、格式转换、queue 交接与带宽仍有成本。分别测 CPU/GPU 时间、端到端延迟、内存峰值与持续热状态；无可靠 counter 不声明节省带宽。没有既有 OpenCL 算法或互操作能力时，先评估现有 Vulkan Compute，不新增必需 OpenCL 依赖。[ENGINE]

## 13. 专家经验

先验证 buffer 的确定性往返和失败回收，再扩到 linear/optimal/AHB。适合已有外部算法且能力证据充分的工程；不适用于只有 API 名称、没有驱动/资源协议的移植。共享方式选择不得要求整个引擎升级 Vulkan 最低基线。[ENGINE]

## 14. 相关 API 卡片

- [Buffer](buffer.md)、[Image](image.md)、[Memory Allocation](memory_allocation.md)
- [Semaphore](../08_synchronization/semaphore.md)
- [实施工作流](../../05_workflows/04_android_integration/vulkan_opencl_interop.md#interop-workflow)

## 15. 需要回查官方文档的情况

所有 handle 兼容、成功/失败 ownership、temporary import 与 image 参数按当前路径规范复核。2026-11-01 仅 source-read，未编译或设备验收：

- [Vulkan memory FD import](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportMemoryFdInfoKHR.html)、[semaphore FD import](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportSemaphoreFdInfoKHR.html)、[semaphore FD export](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetSemaphoreFdKHR.html)、[export 前置条件](https://docs.vulkan.org/refpages/latest/refpages/source/VkSemaphoreGetFdInfoKHR.html)。[SPEC]
- [OpenCL runtime 规范固定源码](https://github.com/KhronosGroup/OpenCL-Docs/blob/0027b7f1a5e97b1bf5256888757479e012a5cb59/api/opencl_runtime_layer.asciidoc)：external memory/semaphore FD ownership。[SPEC]
- [Qualcomm 2026-10-22 教程](https://www.qualcomm.com/developer/blog/2026/10/how-to-share-vulkan-opencl-workloads-android-adreno-gpus)：opaque-FD 路径范围；完整 AHB 流程并不在本文中。[REF]
- [固定样例能力查询](https://github.com/SnapdragonGameStudios/adreno-gpu-vulkan-code-sample-framework/blob/60a13ff4bfa2eb4e5b293babbeccb9be9e4bfc4f/samples/opencl_interop/code/main/interop_common.cpp)。样例不是无需补错误处理的生产实现。[SAMPLE]

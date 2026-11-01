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


<a id="android-media-frame-contract"></a>
### Android 媒体帧：内存引用、帧租约与回交合同

本节是 Camera / MediaCodec → AImageReader → AImage/AHB → Vulkan 的权威寿命段；不沿用上面的 OpenCL opaque-FD 图像示例。AHB 与异步 acquire/delete 在本路径使用 API 26+ 接口，仍需检查目标 NDK/API、扩展和 producer 支持；API 34+ 是验收建议，不是全技能最低版本。[ANDROID][ENGINE]

| 合同 | 实施前必须确认 |
|---|---|
| Producer 能力 | Camera 按设备 stream configuration、session 组合和授权选择输出；MediaCodec 按 codec、尺寸、Surface 输出/格式变化核验。两条 adapter 分开，不假设一个 reader format/usage 配置适合两者。受保护输入另查受保护全链能力，不走 CPU 读回。 |
| 帧身份 | sourceFrameId、timestamp 及其时间基准、sourceGeneration、实际尺寸/format、crop、方向/镜像、颜色 primaries/transfer/range；不要把 reader 的配置尺寸当每帧全部元数据。 |
| 内存对象 | AImage lease、额外 AHB 引用、导入 VkDeviceMemory/VkImage、view、conversion、descriptor 分别记录 owner 和退休条件。 |
| 同步 | acquire FD readiness、FOREIGN ownership、实际 shader 访问、所有消费者完成、release FD 或已完成证明；内存导入成功不证明 producer 写入完成。 |
| 压力 | maxImages、已获取 lease 数、待提交/在途数量有界；规定 latest 丢旧帧或 next 顺序消费，不能无限增加 buffer 掩盖慢消费者。 |

**AHB 导入 gate。** 启用 `VK_ANDROID_external_memory_android_hardware_buffer` 及依赖（包括 `VK_EXT_queue_family_foreign`），检查实际 usage/importability；`vkGetAndroidHardwareBufferPropertiesANDROID` 查询 allocationSize、memoryTypeBits，并链 format properties。图像导入使用 `VkImportAndroidHardwareBufferInfoANDROID` 与指向对应 image 的 `VkMemoryDedicatedAllocateInfo`；allocationSize/内存类型来自该 AHB 查询，不能 width×height 猜大小或当普通 suballocation。创建 image 的外部内存类型、尺寸/layers/usage 与 AHB 一致；普通 VkFormat 与 `VkExternalFormatANDROID` 路径分开。外部格式值只取实际查询，不能拼 RGBA；[YCbCr 采样合同](../05_descriptor/sampled_image_descriptor.md#android-media-ycbcr)负责 view/sampler/descriptor。[SPEC]

**引用不是 lease。** `AImage_getHardwareBuffer` 不自动增加引用；若跨 AImage/reader 寿命保留 handle，应用须 `AHardwareBuffer_acquire` 并配对 release，按 NDK 要求注册 buffer-removed listener。Vulkan 成功导入 memory 会自持一份 AHB 引用，失败不会持有；该引用也不阻止 BufferQueue 在归还帧后重新写这块内存。不可因“AHB 还活着”提前 `AImage_delete`。Listener 只使缓存退休，不可直接释放 GPU 仍用的 view/memory。[ANDROID][SPEC]

| 交接点 | FD / lease owner 与成功条件 | 失败或取消 |
|---|---|---|
| `AImageReader_acquireNextImageAsync` / `AImageReader_acquireLatestImageAsync` | 成功才接收 AImage 与 acquire FD；FD=-1 表示无需等待；非负 FD 归应用管理，尚不能访问像素 | NO_BUFFER_AVAILABLE 是正常无帧；MAX_IMAGES_ACQUIRED 触发背压；不读取失败调用的未定义输出 |
| acquire FD → Vulkan | 查询 SYNC_FD import 能力；binary temporary import，目标 semaphore 无 pending queue command；成功后 Vulkan 接管 FD，应用不得再 close/使用 | 导入失败 FD 仍归应用；停止消费者。可在 worker 等待该 sync FD 真正完成再关闭，不能把等待超时/错误当 ready |
| FOREIGN → Vulkan → FOREIGN | Camera/decoder AHB 按 foreign 设备共享规则做 acquire/release ownership；访问 layout、subresource、stage/access 随实际 consumer；同步载荷不替代 barrier | 部分 submit 成功就保留 lease 和全部在途资源；不因后一步失败回滚成“无人使用” |
| GPU → release FD | 合法 SYNC_FD export 的 binary semaphore 信号必须覆盖所有消费者与归还前 release barrier；导出成功的新 FD 暂归应用 | 导出/submit 失败不制造假 FD、不等待永远不会 signal 的链；保留 lease，按已提交 completion 恢复 |
| `AImage_deleteAsync(image, releaseFenceFd)` | 有效 image/reader 生命周期内，交给 reader 一个覆盖全部使用的 release sync FD；将 FD 标记已转交，不再 close；函数返回后不能访问 AImage | 此 API 返回 void，不存在“返回错误后重试 delete 同一 image”分支。提前取消/尚未交出时只清理仍归应用的 FD；reader 销毁须先协调 lease，而非依赖无效 image 调用补救 |
| 已完成回退 | 无外部 semaphore 支持时，可在非 UI worker 等 acquire sync FD 成功，完成 ownership/采样/归还 barrier 后，host 等所有 GPU consumers 成功，再 `AImage_delete`（或已完成条件下 deleteAsync 的 -1） | CPU 等待牺牲并行/延迟；等待失败/device lost 不等于已完成，停止新任务并按故障协议退休。普通 `VkFence` handle 不是 Android sync FD |

这里的非负 FD（含 0）均按有效句柄处理，-1 只在对应 API 约定中表示无需等待，不直接 close。未消费帧若 acquire 仍 pending，要先完成等待或合法把其依赖作为归还 fence，不能以 -1 假装已就绪。NDK 正常有效路径接管 release FD；源码内部异常分支不构成应用重复关闭/重试同一 AImage 的授权。[ANDROID][SPEC][ENGINE]

**多消费者与 generation。** 用有界 frame lease/消费者集合记录已加入的 A/B 输出；提交前加入，提交失败撤销未提交消费者，已提交项只在实际 completion 后完成。可以 host 等全部结束再归还，或用有证明的 GPU join 产生统一 release fence。一个 binary acquire semaphore 不能被 A/B 独立重复 wait；先单次 acquire 再在 Vulkan 内用合法依赖扇出。同 device 不同 queue 仍要同步，独立 device 须分别查询/import/sync 合同，不共享普通 VkImage handle。不能 A 完成便归还 B 正在采样的帧。[ENGINE][SPEC]

latest 策略要给丢帧保留至少两个 image 的获取余量：`maxImages - currentAcquiredImages >= 2`；否则不能保证丢旧帧，达到上限会停滞。慢输出可在加入 lease 前跳过旧帧，已提交使用不能“丢引用即取消”。reader/source 重建、camera 切换、decoder format change/EOS、pause/resume 先停接入与回调，退休旧 generation 的全部 lease/cache，再切换；裸 AHB 指针不作永久缓存键。停止一个输出不代表输入 lease 其他消费者已完成。[ANDROID][ENGINE]

相机只在授权且系统允许的前台路径测试，不承诺后台壁纸采集；默认自制色条/非私密短片，日志仅记录上述元数据，不记录私人图像，不绕过 DRM/保护标记。验证需记录连续帧 timestamp/generation、队列占用、FD/内存收敛与双消费者归还时序；静态 fixture 或 Validation clean 均不是 Camera/codec 真机兼容证明。[ENGINE]

来源：[NDK Media](https://developer.android.com/ndk/reference/group/media)、[固定 NdkImage.h](https://android.googlesource.com/platform/frameworks/av/+/754a4310b132681592fa9ed8d449b9953795056b/media/ndk/include/media/NdkImage.h)、[AHB memory import](https://docs.vulkan.org/refpages/latest/refpages/source/VkImportAndroidHardwareBufferInfoANDROID.html)、[allocation 约束](https://docs.vulkan.org/refpages/latest/refpages/source/VkMemoryAllocateInfo.html)、[AHB FOREIGN 规则](https://docs.vulkan.org/spec/latest/chapters/memory.html#memory-external-android-hardware-buffer)。

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

# Workflow: Vulkan / OpenCL Interop

## 0. 适用范围

### 适用

已有 OpenCL 图像/计算算法，需要接入现有 Vulkan renderer；目标设备、驱动及两端 handle 能力可查询，并能运行确定性输入输出验证。

### 不适用

没有现有外部算法、设备不支持兼容外部对象，或仅因“零复制”宣传而重建 allocator/RHI。此时先评估原 Vulkan Compute；不提高全项目最低 Vulkan 版本、不强加所有 Android 必须有 OpenCL。[ENGINE]

## 1. 任务目标

建立一条可验证、可回退的 Vulkan → 外部计算 → Vulkan 路径；第一步只做 buffer，图像/AHB 是后续独立能力分支。避免 CPU staging 不等于零带宽、零同步或必然低延迟。[ENGINE]

## 2. 输入条件

记录 OS/GPU/driver、Vulkan 实际 API 与入口、OpenCL platform/device、双方扩展/handle 列表、算法输入输出、queue 属性、allocator/descriptor/retirement 源码。先给 `[CODE]` Evidence Map 和 Architecture Map；未知实现标未验证。

输入必须包括 resource 类型、format、tiling、usage、samples、size/offset、当前 queue owner，以及是否依赖 Camera/MediaCodec/AHardwareBuffer；没有这些不能把 generic opaque-FD 案例套到图像。[SPEC][ENGINE]

## 3. 前置检查

- [ ] 对比 deviceUUID **及** driverUUID；匹配不免除 handle/资源查询。driver 不同则停止 opaque-FD 快速路径，不承诺可用。
- [ ] 依据 [能力合同](../../03_api_manual/04_buffer_image_memory/external_resource_interop.md#interop-capability-contract) 检查 memory 和 semaphore 的两方向能力。
- [ ] OpenCL queue 的 in-order/out-of-order 已确认；每个 API 返回值及两端完成事件可记录。
- [ ] 已定义标准 Vulkan fallback 与失败清理状态机；Validation/工具缺失明确记未验证。

## 4. Vulkan 对象链路

```text
现有 allocator → exportable VkBuffer/VkDeviceMemory → memory FD → cl_mem
原 Vulkan producer → ownership release → signal/export fresh sync FD
CL import/wait → external-memory acquire → kernel → release → signal/export fresh sync FD
Vulkan temporary import/wait → ownership acquire → 原 descriptor/consumer → 两端退休
```

## 5. 资源设计

| 资源 | 类型/Usage | 生命周期 | resize |
|---|---|---|---|
| 共享 buffer | `VkBuffer` + `VkDeviceMemory`，覆盖实际 storage/transfer 用途 | 原 allocator 管底层，CL 对象持有导入引用；两端完成才退休 | 仅依赖尺寸时新建 generation |
| memory FD | OPAQUE_FD，导出后应用持有 | 成功导入后交给实现；失败则应用清理 | 不把旧 FD 作为新 allocation |
| 同步对象 | 两方向 binary `VkSemaphore` / CL semaphore | 对象可按合法状态复用，SYNC_FD payload 每次交接更新 | 等待/信号仍 pending 不提前销毁 |
| 共享 image（后续） | 只允许已核实 format/tiling/handle 协议 | 配套 view、descriptor 与外部对象 | 旧/新 extent 不混用 |

实际 FD owner 规则见 [生命周期合同](../../03_api_manual/04_buffer_image_memory/external_resource_interop.md#interop-lifetime-contract)；AHB 是独立引用计数/格式合同，不执行 FD close。

## 6. Pipeline / Descriptor 设计

沿用原 binding：例如 Vulkan compute storage buffer 输入/输出映射 OpenCL kernel 参数，最终 consumer 在外部回交完成后才访问。OpenCL 不共享 Vulkan descriptor set；两端 offset/size、元素类型、stride 与算法约定需一致。重建资源后同时更新外部对象及 descriptor，不能只换一个 API 的 handle。[ENGINE]

## 7. 同步与 Layout 设计

| Producer | Resource | 依赖/状态 | Consumer |
|---|---|---|---|
| Vulkan 实际写入 stage/access | buffer范围或image子资源 | release 到相应外部 owner；image转约定布局；signal | CL wait + acquire |
| CL kernel | 已 acquire 的共享对象 | event 顺序覆盖写入及 release；signal新的sync载荷 | Vulkan wait + acquire |
| Vulkan acquire | 相同范围/代际 | dstStage/access 覆盖最早消费；image转消费布局 | graphics/compute |

Vulkan producer 可为 transfer/compute/attachment，不能写死 stage；buffer 的 old/newLayout 不适用。Opaque-FD 示例使用 EXTERNAL ownership，图像常用 GENERAL 交接；AHB/foreign owner 必须查对应协议。Semaphore 解决执行顺序，不能替代 ownership/可见性；OpenCL 多queue或out-of-order场景补显式 event 依赖。[SPEC]

<a id="interop-workflow"></a>
## 8. 实现步骤

1. 在既有 capability 层记录支持/拒绝原因，不按设备品牌跳查询；无能力保留原 Vulkan 路径。
2. 按精确 buffer usage 与 handle 查询 export/import/dedicated 条件；复用 allocator 分配可导出资源。
3. 导出 memory FD，创建 CL 对象；只在成功时转交 FD owner，建立 resource ID/generation 双端映射。
4. 使用一组确定性整数/灰度输入，先在原路径计算 reference，再验证外部路径；不先上复杂时域算法。
5. 录制 Vulkan producer 与 release，提交后检查返回值；合法排队 signal 后导出新的 SYNC_FD。
6. CL 导入/重导入该载荷，排队 wait → acquire → kernel → release → signal。检查每一步返回值，out-of-order 明确 event 边。
7. CL 导出新 SYNC_FD；Vulkan 导入/重导入前确认目标 semaphore 没有任何未完成的 queue command（`VUID-vkImportSemaphoreFdKHR-semaphore-01142`），再 temporary import → 提交 wait/acquire → 原消费者；sync FD 不跨帧重复导入，不能当 timeline 值。
8. 每帧保存 slot、generation、owner 与两端 completion；只有回交成立才将结果交给 renderer。
9. buffer 通过后再评估 linear image；optimal image 必须核对其 handle 的 tiling 推断能力。QCOM 专有类型不作为通用 Android 保证。
10. Camera/AHB 走单独 capability/format/reference 合同；Qualcomm 10 月教程并未完成 AHB 全链路示范。
11. resize/recreate 停新任务、退休旧 generation、建立新对象与descriptor；停止时释放两端对象和仍属应用的句柄。

<a id="interop-failure-recovery"></a>
### 失败与回收状态机

| 失败点 | 允许动作 | 禁止动作 |
|---|---|---|
| 能力/UUID/driver 不匹配 | 选择原 Vulkan Compute/现有算法路径并报告缺口 | 猜测导入可用 |
| allocation/export失败 | 回收已完成且未提交资源；检查是否实际获得FD | 对未定义输出close/继续导入 |
| memory/semaphore import失败 | 应用仍持有的FD关闭一次；停止依赖该对象的提交 | 标记已转交后泄漏，或假设另一端会signal |
| producer提交成功、后续交接失败 | 记录最新owner；停止该slot消费者，排空已知完成链后恢复/退休 | 直接归还slot、提前释放allocation |
| CL enqueue部分成功 | 保留已排队event及资源直到完成；未产生回程signal则不提交无限等待链 | 把单个返回失败理解成之前操作都没执行 |
| device lost | 停普通循环，按各API设备丢失规则诊断/清理 | 用WaitIdle假造未知外部完成证明 |

此表是工程状态设计，不是所有错误可通用重试的保证；无法证明owner/完成时停止快速路径，保留诊断信息。[ENGINE]

## 9. Android 注意点

pause/resume、Surface destroyed/recreated、rotation/resize 与外部计算独立；不因Surface消失就释放仍由外部queue使用的资源。extent 为 0 停展示与新任务，完成必要回收；恢复时检查驱动/设备及资源generation。日志只存必要元数据，未经授权不上传trace或私有图像。[ANDROID][ENGINE]

## 10. 验证方式

- [ ] Static：符号、查询字段、owner表与返回值分支核对；这不是运行验收。
- [ ] Device：确定性buffer往返readback/hash与reference一致，随后再做受支持图像路径的像素差分。
- [ ] 连续多帧、双方向交接、失败清理、resize、后台/前台；FD数量与内存不持续增长。
- [ ] 实际工具能观察的GPU/CPU时间、延迟、峰值内存、热状态单列；无counter不填带宽。
- [ ] 能力缺失设备验证fallback；专有image路径没有支持设备则未验证，不用桌面编译替代。
- [ ] 实现结论列适用 G1–G6；文档/模型答案不等于真实APK运行。

## 11. 常见失败模式

仅deviceUUID匹配；memory FD与sync FD混用；每帧重复旧sync载荷；optimal按linear解释；只signal不release；Vulkan fence完成便释放CL使用的资源；把外部失败当成帧成功。[ENGINE]

## 12. 相关 API 卡片

- [External Resource Interop](../../03_api_manual/04_buffer_image_memory/external_resource_interop.md)
- [Buffer](../../03_api_manual/04_buffer_image_memory/buffer.md)
- [Semaphore](../../03_api_manual/08_synchronization/semaphore.md)

## 13. 相关 Debug Playbook

- [Device Lost](../../04_debug_playbooks/02_crash_hang/device_lost.md)
- [工具覆盖](../../04_debug_playbooks/tool_usage.md)

## 14. 不确定时如何处理

先取得双方handle能力、UUID/driver、资源创建与失败代码、queue/event记录及owner状态；仅缺工具时继续静态合同分析，不编造设备结果。

来源核查（2026-11-01，仅 source-read）：[固定 Adreno 样例](https://github.com/SnapdragonGameStudios/adreno-gpu-vulkan-code-sample-framework/tree/60a13ff4bfa2eb4e5b293babbeccb9be9e4bfc4f/samples/opencl_interop)。其 `interop_common.cpp` 对比UUID/driver并查询handle；`interop_buffer.cpp` 演示双端对象/ownership；`application.cpp` 编排资源释放。提取合同，不复制样例的所有依赖与错误处理假设。[SAMPLE]

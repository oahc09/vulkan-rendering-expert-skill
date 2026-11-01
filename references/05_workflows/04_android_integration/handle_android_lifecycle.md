# Workflow: Handle Android Lifecycle

> 文件建议路径：`handle_android_lifecycle.md`

---

## 0. 适用范围

### 适用

- Android 应用使用 Vulkan 渲染，需要正确处理 `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed`。
- 需要管理 `ANativeWindow`、`VkSurfaceKHR`、`VkSwapchainKHR`、command buffer、fence 的生命周期。
- 需要避免 rotation / resize / 切后台 / 切前台 导致的 `DEVICE_LOST` 或崩溃。

### 不适用

- 桌面平台（Windows / Linux）无 surface 销毁 / recreate 的场景。
- 使用 OpenGL ES 或 2D UI 框架（生命周期处理逻辑不同）。
- 完全由游戏引擎（如 Unity / Unreal）托管 lifecycle 的项目。

---

## 1. 任务目标

建立每输出的有效访问、停止确认和退休协议：

```text
surfaceCreated → 获取 window 引用 → 逐 Surface 查询 → swapchain → render
pause/hidden → 只停止对应输出无必要的新工作（不等于 Surface 已销毁）
surfaceDestroyed → 关闭该 generation 入口 → render 线程停止访问确认 → 回调返回
旧 Vulkan 资源 → submission 完成 + WSI 退役证据 → 安全销毁/释放
```

后两条不能混同。停止访问确认不能靠“只 post 一个 destroy 事件”；后台资源退休也不能继续访问已经失效的 Android Surface。

---

## 2. 输入条件

需要确认：

- Android 版本、设备 GPU（Adreno / Mali / PowerVR）。
- 是否使用 native Activity 或 Java/Kotlin Activity + `SurfaceView` / `TextureView` / `SurfaceHolder`。
- render thread 模型：单 render thread、render thread + worker threads、专用 compute thread。
- 是否使用多 buffering（双缓冲 / 三缓冲）以及 frame-in-flight 数量。
- 是否已有 swapchain recreate 处理（如 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR`）。
- 是否存在跨 frame 资源（SSBO、storage image、fence、semaphore）需要在 pause 时保留。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 已能在正常启动路径创建 swapchain 并呈现多帧。
- [ ] 已能在 `VK_ERROR_OUT_OF_DATE_KHR` 时手动 recreate swapchain。
- [ ] 已跟踪每帧的 fence 与 in-flight command buffer。
- [ ] 已记录 `ANativeWindow` 的 acquire / release 调用点。
- [ ] 已确认 `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed` 的触发顺序。

---

## 4. Vulkan 对象链路

```text
Process → DeviceContext（共享策略先确认）→ RenderInstance / Engine
→ OutputId + surfaceGeneration → ANativeWindow → VkSurfaceKHR → VkSwapchainKHR
→ VkImage[] + per-image present wait semaphore
→ per-output frame slot（command buffer / submit fence / acquire semaphore）
```

真实 swapchain image 类型是 `VkImage`；DeviceContext/OutputId 是工程概念。所有权表见 [多实例模型](../../02_core_mental_model/android_surface_swapchain_lifecycle.md#multi-instance-ownership)。

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| window / surface | `ANativeWindow*` / `VkSurfaceKHR` | 平台输出桥 | 该输出的 Surface generation | Surface更换时 |
| swapchain / views | `VkSwapchainKHR` / `VkImageView` | 呈现 | 该代 GPU + WSI 退休 | 是 |
| frame slot | command buffer / `VkFence` / acquire `VkSemaphore` | submission | 该输出自己的已完成 slot | 确认未使用才复用 |
| present wait | `VkSemaphore` | present等待 | 该输出 swapchain image 的 WSI使用 | 需独立退役证据 |
| depth / offscreen | `VkImage` | 附件 | extent/format/generation及GPU完成 | 按实际依赖 |
| cache / allocator | device所属对象 | 共享资源 | 所有消费者释放后 | 不因A局部关闭销毁 |

`ANativeWindow_fromSurface` 取得的引用最终匹配 release；保留引用不会延长宿主允许访问 Surface 的时段。关闭某实例不自动销毁 shared device。[ANDROID][ENGINE]

---

## 6. Pipeline / Descriptor 设计

本工作流主要涉及生命周期管理，pipeline / descriptor 设计按渲染管线复用：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 被分析 pass 的 binding | `COMBINED_IMAGE_SAMPLER` / `UNIFORM_BUFFER` / `STORAGE_BUFFER` | swapchain-independent 资源 | Vertex / Fragment / Compute |

设计说明：

- swapchain-independent descriptor（如 scene UBO、texture array）在 surface 重建时通常无需更新 [ENGINE]。
- swapchain-dependent descriptor（如 per-frame color attachment 作为 input attachment）在 swapchain recreate 后需重新绑定 [ENGINE]。
- pipeline layout 与 pipeline 通常不随 swapchain 重建而重建 [HEUR]。

---

## 7. 同步与 Layout 设计

| 事件/资源 | 必须区分的完成条件 |
|---|---|
| acquire 成功 / SUBOPTIMAL | 已取得image和信号，必须进入明确消费/收尾路径，不能直接丢弃 |
| acquire OUT_OF_DATE / TIMEOUT / NOT_READY | 没有本次成功acquire，保留仍signaled的frame fence，不盲目reset |
| frame slot 复用 | 检查 `vkWaitForFences` 的返回值；timeout/device lost不能当成功 |
| command buffer 引用的旧 image/view | 相关 submission 确实完成后才销毁 |
| present wait semaphore / swapchain退休 | submit fence不等于present完成，按维护扩展present fence或适用WSI退役协议 |
| host destroy 回调 | render线程停止访问旧Surface的ack必须在返回前完成 |

遵循 [setup_frame_loop](../01_renderer_setup/setup_frame_loop.md) 的成功录制后、确定即将submit才reset fence规则，以及 [semaphore](../../03_api_manual/08_synchronization/semaphore.md) 的present重用规则。
`vkDeviceWaitIdle(device)` 无timeout参数；它等待该device队列工作，不是默认局部关闭策略，也不单独证明presentation资源退休。必要时用可超时的fence等待并保留未完成对象；绝不能编造wait-idle超时返回分支。[SPEC]

---

## 8. 实现步骤

<a id="multi-surface-lifecycle"></a>
### 每输出事件/状态合同（独立读取入口）

前提：已建立 process/device/engine/output/frame/image/source-frame owner 图；仅访问有效宿主Surface。每个事件携带 outputId、generation、sequence；销毁确认与GPU/WSI退休是两种独立完成证据。[ENGINE]

| 输入事件 | 前置/动作 | 新状态或确认 |
|---|---|---|
| create(g) | 注册新代；取window引用；逐Surface查present/caps/format/transform | Ready(g)，非零extent且visible/host允许/device健康才运行 |
| resize(g) | 仅匹配当前代；停止该输出新使用；旧代依赖进入退休表 | 重查capabilities，重建所需附件/descriptor，不改B状态 |
| destroy(g) | 原子关闭该代调度入口；排空/取消未开始的访问；等待已进入的Surface操作退出 | render ack: 不再触碰该Surface，回调才能返回；未退休对象仍被追踪 |
| 旧resize/destroy/completion(g-old) | 不改变新代对象；completion只结算其原代记录 | stale事件被丢弃或用于旧代回收，不能释放新代view |
| hidden / pause | 更新该实例对应状态，不推断Surface销毁 | 停止无必要提交；B与共享资源保持 |
| resume / visible | 核对Surface仍有效/非零extent与device状态 | 条件齐全才恢复 |
| SURFACE_LOST / OUT_OF_DATE | 只标受影响输出失效；成功acquire须另走收尾 | 合法时局部重建，不重置共享device |
| DEVICE_LOST | 冻结同device所有输出和输入消费者；记录未完成工作 | device级诊断/恢复，不能承诺B继续正常 |

1. Java `SurfaceHolder.Callback` 或 Wallpaper Engine 对等回调向JNI传 outputId/generation；不假定 Activity 与 Wallpaper 回调相同。
2. 建立锁序：UI等停止ack时释放worker需要的锁；render不等待UI回调才能发ack；不能在持queue锁时阻塞等需要该queue的线程。ack须覆盖正在进行的surface访问退出，不只是收到事件。
3. 有界acquire等待与生命周期可中断调度避免停止线程长期卡在新帧入口；若停止无法完成，报告错误，不虚报ack然后继续访问旧Surface。UI预算/ANR风险须测量，不以超时后强制销毁掩盖。
4. 正常帧按原frame-loop协议处理wait/acquire/record/reset/submit/present及各返回值。SUBOPTIMAL并非未取得image；提交失败后已reset fence不能再次无条件等待。
5. 旧代GPU对象保留到submission完成；present等待/旧swapchain按明确WSI维护能力或既有退役协议处理。新代不可沿用仍被使用的旧present semaphore。
6. Surface销毁后不能为回收旧代再发起旧Surface acquire/present；设计必须在有效期建立可用退役证据，无法证实时保持未验证/待恢复，不把device idle当万能替代。
7. shared device仅在最后消费者/实例退出且合法完成后销毁；发生device lost按设备级恢复。局部resize不销毁shared allocator/cache。
8. 每条日志只记身份/代际/返回值/完成序号，不保存私人画面；对照100次局部重建、1000帧双消费者、15分钟建议smoke预算，实际运行前固定次数与设备。

---

## 9. Android 注意点

- Surface有效访问时段由宿主回调合同确定；引用计数不是继续呈现的授权。
- rotation可能只changed，也可能destroy/create，不规定固定回调顺序。
- `visible`、`hostPaused`、`surfaceValid`、`deviceHealthy`分别维护；零extent不创建swapchain。
- queue host并发按规范外部同步（除非明确启用适用的内部同步能力）；单提交线程是可选工程策略，不是规范强制。
- AppWidget/RemoteViews不承诺任意SurfaceView；应用内与Wallpaper/OEM宿主分开验证。无隐藏API/root/后台相机默认路径。

---

## 10. 验证方式

- [ ] Validation与日志（可用时）绑定最终代码/设备/驱动；clean不等于完整正确。
- [ ] A关闭/重建时B仍提交，shared allocator/device未误销毁。
- [ ] 旧generation resize/destroy/completion不改变新代状态。
- [ ] destroy回调返回后无任何旧Surface访问；无UI/render互等。
- [ ] frame fence与present semaphore各自有完成证据；acquire/record/submit失败收尾覆盖。
- [ ] 同device DEVICE_LOST冻结所有使用者；Surface丢失仅局部恢复。
- [ ] 固定预算测延迟、队列占用、FD/内存收敛，不预设100ms/50ms保证。
- [ ] 无授权设备时隔离状态fixture只记Static PASS，Device保持NOT RUN。

---

## 11. 常见失败模式

1. 一个全局currentSurface或frameIndex导致多实例互相覆盖。
2. 只post destroy就返回，render线程仍访问失效Surface。
3. ack等待持有worker需要的锁，形成UI/render死锁。
4. 旧代完成回调释放新代view，或在B仍使用时销毁shared device。
5. 把frame fence当present退休证据，或将未消费acquire信号直接复用。
6. 编造 `vkDeviceWaitIdle` timeout 分支，超时后强制释放pending资源。
7. 把共享queue的正常compute与Surface故障直接推导为device lost；须依据实际错误与资源链。

---

## 12. 相关 API 卡片

- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- Android 设备型号 / GPU / Android 版本。
- Activity 类型（NativeActivity / SurfaceView / TextureView）与 lifecycle 回调日志。
- `onPause` / `onResume` / `onSurfaceCreated` / `onSurfaceDestroyed` 的触发顺序与时间戳。
- Validation Layer 完整报错。
- `adb logcat` 中 lifecycle 与 Vulkan 的交错日志。
- swapchain recreate 代码与 `vkCreateSwapchainKHR` 参数。
- frame-in-flight 数量、fence/semaphore 管理代码。


来源（2026-11-01核对）：[Surface回调](https://developer.android.com/reference/android/view/SurfaceHolder.Callback)、[Wallpaper多Engine](https://developer.android.com/reference/android/service/wallpaper/WallpaperService)、[WaitIdle签名](https://docs.vulkan.org/refpages/latest/refpages/source/vkDeviceWaitIdle.html)、[WSI退休](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)。

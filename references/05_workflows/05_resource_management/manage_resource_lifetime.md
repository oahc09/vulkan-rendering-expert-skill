# Workflow: Manage Resource Lifetime

## 0. 适用范围

### 适用

- 需要自定义资源生命周期管理：buffer、image、image view、framebuffer、descriptor pool、pipeline 等。
- 需要处理资源释放与 GPU in-flight 使用的竞争。
- 需要实现 deferred deletion queue、reference counting 或 handle-based 资源系统。
- 需要降低 device lost 风险，确保销毁时资源不再被 GPU 使用。

### 不适用

- 资源生命周期完全由外部引擎（如 UE/Unity/Godot）托管的场景。
- 每帧全量重建所有资源、无需延迟销毁的简单示例程序。
- 纯 headless / compute-only 程序（概念可参考，但 graphics 相关细节需裁剪）。

---

## 1. 任务目标

建立安全的资源生命周期管理：

```text
Resource Handle
→ Ref Count / Ownership
→ In-Flight Tracking (fence / submission ID)
→ Deferred Deletion Queue
→ Safe Destroy (after GPU finished)
→ Device Lost Protection
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- Frame-in-flight 数量（2~3）。
- 需要管理的资源类型：buffer、image、view、framebuffer、pipeline、descriptor pool 等。
- 是否使用 handle-based resource system。
- 是否使用 ref counting 或明确 owner。
- 同步机制：fence、semaphore、timeline semaphore、submission ID。
- 是否支持 `VK_EXT_device_fault` 或 device lost 后 dump 机制。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] Frame-in-flight fence 稳定。
- [ ] 所有 `vkDestroy*` / `vkFree*` 调用可统一收口。
- [ ] 已记录每次 queue submit 对应的 fence 或 submission ID。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Application Object
→ Resource Handle (weak/strong ref)
→ Vulkan Object (buffer/image/view/pipeline)
→ In-Flight Tracker (fence / timeline value / frame index)
→ Deferred Deletion Queue
→ GPU Complete Signal
→ vkDestroy* / vkFree*
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| resource handle | `uint32_t` / struct | 应用层引用资源 | 由 ref count 控制 | 否 |
| resource record | struct | 存储 `VkBuffer`/`VkImage`/`VkImageView` 等 handle 与元数据 | 与 Vulkan 对象同生命周期 | 视资源而定 |
| ref count | `std::atomic<uint32_t>` / counter | 强引用计数 | 归零时进入 deferred queue | 否 |
| deferred deletion entry | struct | 待删除对象 + 完成 fence / submission ID | 直到 GPU 完成 | 否 |
| in-flight tracker | array/ring | 每帧 fence 或 timeline semaphore 值 | per-frame | 否 |

---

## 6. Pipeline / Descriptor 设计

本工作流主要涉及资源生命周期，descriptor / pipeline 复用现有设计：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | managed per-frame UBO | Vertex / Fragment / Compute |
| set=N,binding=M | `COMBINED_IMAGE_SAMPLER` | managed image view | Fragment / Compute |
| push constant | `VkPushConstantRange` | 生命周期由 command buffer 覆盖 | Vertex / Fragment / Compute |

设计说明：

- descriptor set 引用的 buffer/image 必须保证在 GPU 使用期间有效；ref count 需在 bind 时增加，在 fence 后释放 [SPEC]。
- pipeline layout 和 pipeline 本身通常长生命周期；若动态卸载 material，需确保没有 in-flight command buffer 引用该 pipeline [ENGINE]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| resource create | buffer / image | `UNDEFINED` → target layout | first consumer |
| resource use | buffer / image | in-flight tracker 记录 fence | deferred deletion queue |
| fence signaled | resource record | safe to destroy | deletion worker |
| device lost | all in-flight resources | 不再依赖 fence，强制等待 idle 后销毁 | cleanup path |

必须说明：

- 销毁 Vulkan 对象前，必须保证 GPU 不再访问；通常通过 `vkWaitForFences` 或 `vkDeviceWaitIdle` 实现 [SPEC]。
- 使用 timeline semaphore 时，可将每个 submit 关联一个 monotonic submission ID，deferred deletion entry 标记完成 ID，每帧刷新时检查 `vkGetSemaphoreCounterValue` >= entry.id [SPEC]。
- 同一资源被多个 frame 的 command buffer 引用时，必须等所有相关 fence 都 signaled 才能销毁 [ENGINE]。
- Device lost 后，fence 可能永远不会 signaled；清理路径应使用 `vkDeviceWaitIdle` 超时或放弃，然后直接销毁对象并重新初始化 renderer [TOOL]。

---

## 8. 实现步骤

1. **定义 resource handle 与 record**：
   - handle 可以是 32-bit index（generation + index）用于检测 use-after-free [ENGINE]。
   - record 包含 Vulkan object handle、type、ref count、deletion flag、in-flight fence list。
2. **实现 ref counting**：
   - `Acquire(handle)` / `Release(handle)`，原子操作；
   - `Release` 归零后将对象加入 deferred deletion queue [ENGINE]。
3. **实现 in-flight tracking**：
   - 每次 queue submit 记录使用的资源列表与对应 fence；
   - 或记录 submission ID（timeline semaphore）到每个资源 [ENGINE]。
4. **实现 deferred deletion queue**：
   - 每帧或每 N 帧检查队列头部 entry；
   - 若 entry.fence signaled 或 entry.submissionID <= currentGPUID，则调用 `vkDestroy*` / `vkFree*` [ENGINE]。
5. **Frame loop 刷新**：
   - `vkWaitForFences(perFrameFence)` 后，将本 frame 引用的资源标记为可释放；
   - 遍历 deferred queue 执行安全销毁 [SPEC]。
6. **Swapchain recreate 处理**：
   - 尺寸相关资源（swapchain image view、framebuffer、depth image 等）不再由应用直接销毁（由 swapchain 拥有），但 offscreen image 需按 lifetime 流程延迟销毁 [SPEC]。
7. **Pipeline / descriptor pool 卸载**：
   - 标记为 pending delete；
   - 等所有引用它的 command buffer 完成后再销毁；
   - 不能在同 frame中销毁刚 bind 的 pipeline [SPEC]。
8. **Device lost 保护**：
   - 捕获 `VK_ERROR_DEVICE_LOST`；
   - 停止提交新命令；
   - 使用 `vkDeviceWaitIdle`（带超时）或直接进入 emergency cleanup；
   - 可选使用 `VK_EXT_device_fault` 收集 fault info [TOOL]。
9. **销毁路径**：
   - 先 drain deferred deletion queue（等待所有 fence）；
   - 再按依赖顺序销毁：command buffer → command pool → descriptor pool → pipeline → pipeline layout → image view → image → buffer → device memory [ENGINE]。
10. **调试支持**：
    - 输出当前 alive resource count、deferred queue size、in-flight resource count；
    - 在 validation layer 报 lifetime 错误时，打印资源创建堆栈或 handle [TOOL]。
11. **幂等销毁设计（shutdown safety）**：

    Vulkan spec 允许 `vkDestroy*` / `vkFree*` 在 handle 为 `VK_NULL_HANDLE` 时执行 no-op，这是设计幂等 shutdown 的基础 [SPEC]。但 wrapper 仍需主动置空，避免异常路径双重销毁。

    ```text
    SafeDestroy(VkBuffer& buf, VkDevice device, const VkAllocationCallbacks* pAllocator):
        if buf != VK_NULL_HANDLE:
            vkDestroyBuffer(device, buf, pAllocator)
            buf = VK_NULL_HANDLE

    VulkanApp::shutdown():
        if isShutdown: return              // 幂等入口
        isShutdown = true
        vkDeviceWaitIdle(device)           // 幂等，可重复调用 [SPEC]
        DestroySwapchainDependent()         // view / framebuffer / depth / scene RT
        DrainDeferredDeletionQueue()        // 等待所有 fence 或跳过（device lost）
        DestroyLongLived()                  // pipeline / pipeline_layout / descriptor_pool
        DestroyBase()                       // command_pool / device / instance
        device = VK_NULL_HANDLE
    ```

    关键规则：

    - `vkDeviceWaitIdle` 是幂等的，shutdown 入口可无条件调用 [SPEC]。
    - 每个 `vkDestroy*` 后立即把 handle 置 `VK_NULL_HANDLE`，防止 destructor 与显式 shutdown 双重销毁同一 handle [ENGINE]。
    - AllocationCallbacks 必须与创建时一致，destroy 时传不同 pAllocator 是 undefined behavior [SPEC]。
    - swapchain recreate 与 shutdown 共用清理函数时，必须通过 flag 区分"仅 swapchain-dependent 资源"与"全部资源"，避免 recreate 误销毁长生命周期对象 [ENGINE]。
    - destructor 必须调用 shutdown 并能容忍"对象从未成功创建"场景：所有 handle 为 NULL，wrapper 走 no-op 路径 [ENGINE]。
    - device lost 后 shutdown 不能依赖 fence signal；应跳过 fence 等待直接销毁对象并重建 renderer [TOOL]。
    - `vkDestroyDescriptorSet` 不存在；descriptor set 由 `vkResetDescriptorPool` / `vkDestroyDescriptorPool` 统一回收，幂等设计需作用在 pool 层 [SPEC]。
    - swapchain image / implicit dispatchable handle 由父对象拥有，应用不能直接 destroy，幂等设计需跳过这些对象 [SPEC]。

### 常见多次调用场景

幂等设计的真正价值在于异常路径与组合调用，必须显式覆盖以下场景：

1. **main 显式调用 + 析构调用**：

   ```text
   int main() {
       VulkanApp app;
       app.init();
       app.run();
       app.shutdown();      // 显式调用 1
   }   // 析构再次调用 shutdown —— 必须走 no-op 路径
   ```

   应对：`isShutdown` flag 在 shutdown 入口检查并置位；析构调用时 flag 已 true 直接 return [ENGINE]。

2. **异常路径 + 正常路径**：

   ```text
   VulkanApp::init():
       CreateInstance()           // 成功
       CreateDevice()             // 失败抛异常
       CreateSwapchain()          // 未执行
   } catch (...) {
       shutdown();                // 异常路径调用，部分对象已创建
   }
   ```

   应对：shutdown 必须容忍"对象从未成功创建"场景，所有 handle 为 `VK_NULL_HANDLE`，wrapper 走 no-op 路径 [ENGINE]。

3. **窗口关闭 + 析构**：

   ```text
   OnWindowClose():
       app.shutdown()             // 用户关闭窗口触发
   }   // app 析构再次调用 shutdown
   ```

   应对：同场景 1，`isShutdown` flag 防双重销毁 [ENGINE]。

4. **swapchain recreate + shutdown 共用清理函数**：

   ```text
   OnResize():
       DestroySwapchainDependent()  // 仅销毁 swapchain-dependent 资源
   VulkanApp::shutdown():
       DestroySwapchainDependent()  // 同一函数被复用
       DestroyLongLived()           // 销毁长生命周期资源
       DestroyBase()
   ```

   应对：清理函数本身必须幂等（handle 置空），shutdown 通过 flag 区分"仅 swapchain-dependent"与"全部资源" [ENGINE]。

5. **device lost 后清理 + 正常析构**：

   ```text
   OnDeviceLost():
       emergencyShutdown()          // 跳过 fence 等待，直接销毁
   }   // 析构再次调用 shutdown
   ```

   应对：emergencyShutdown 也必须设置 `isShutdown` flag；device lost 后不能依赖 fence signal，应跳过 fence 等待直接销毁对象 [TOOL]。

通用规则：

- 所有清理函数（包括 DestroySwapchainDependent / DestroyLongLived / DestroyBase）必须**独立幂等**，被重复调用不崩溃 [ENGINE]。
- `isShutdown` flag 是入口幂等保障；handle 置空是函数级幂等保障，两者必须同时存在 [ENGINE]。
- 析构函数应无条件调用 shutdown，确保异常路径下资源也能释放 [ENGINE]。

---

## 9. Android 注意点

- `ANativeWindow` / surface destroy 后，swapchain image 由 `vkDestroySwapchainKHR` 隐式释放；应用不应再保留这些 image 的 view 或 descriptor 引用 [ANDROID]。
- pause / resume 期间应停止 render thread 并等待所有 frame fence，然后 drain deferred deletion queue；resume 后重新创建 surface 相关资源 [ANDROID]。
- rotation / resize 触发的 swapchain recreate 中，尺寸相关 offscreen image 应通过 deferred queue 延迟销毁，确保当前 frame 完成 [ANDROID]。
- 移动端 memory 紧张，deferred queue 不宜积压过多资源；建议每帧刷新并设置最大队列长度 [ANDROID]。
- AGI / logcat 验证：监控 `vkDestroy*` 调用时机、resource alive count、device lost 日志。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkDestroy*-*-validHandle`、`VUID-vkFree*-*-validHandle`、lifetime hazard 错误 [TOOL]。
- [ ] RenderDoc / AGI：资源在正确帧被销毁，无悬空引用 [TOOL]。
- [ ] 截图 / 数值验证：资源替换/卸载后渲染正确，无白屏/黑屏/旧资源残留。
- [ ] logcat（Android）：无 validation error；可输出 `aliveResources`、`deferredQueueSize`、`inFlightResources`。
- [ ] 性能指标：
  - deferred deletion queue 不持续增长；
  - 无 memory leak（alive resource count 稳定）；
  - `vkWaitForFences` 等待时间合理 [HEUR]。
- [ ] resize / pause / resume / rotation 后资源清理正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`；若发生 device lost，保护路径不崩溃。

---

## 11. 常见失败模式

1. **Use-after-free**：handle 引用已销毁资源，未检测 generation [ENGINE]。
2. **提前销毁**：资源仍在 GPU in-flight 使用中就调用 `vkDestroyBuffer` [TOOL]。
3. **Ref count 泄漏**：循环引用或未正确 `Release`，导致资源永不释放 [ENGINE]。
4. **Fence 未记录**：submit 时未将资源与 fence 关联，deferred queue 无法判断安全时机 [ENGINE]。
5. **Device lost 后死等 fence**：device lost 后 fence 不会 signaled，清理路径卡死 [TOOL]。
6. **Swapchain image 误销毁**：应用直接 `vkDestroyImage` swapchain image [SPEC]。
7. **Descriptor pool 提前释放**：pool 被销毁但 command buffer 中仍有 bind 引用 [SPEC]。
8. **Android surface destroy 后继续引用资源**：导致 `VK_ERROR_DEVICE_LOST` [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/03_command_buffer/fence_semaphore.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/06_pipeline/pipeline.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/02_crash_hang/gpu_hang.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/03_validation_errors/memory_leak.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 资源类型与销毁顺序。
- Ref counting 还是明确 owner。
- Frame-in-flight 数量与 fence 机制。
- Deferred deletion queue 刷新策略。
- 发生 device lost 时的调用栈与 fault info。
- Android lifecycle 日志。

# API Card: Swapchain Recreate

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 显示链 / Android 平台链 |
| Vulkan 对象 | `VkSwapchainKHR`（涉及 retired / new swapchain） |
| 常用 API | `vkCreateSwapchainKHR`（带 `oldSwapchain`） / `vkDestroySwapchainKHR` / `vkDeviceWaitIdle` / `vkQueueWaitIdle` |
| 适用平台 | 通用，Android 场景尤其高频 |
| 来源等级 | `[SPEC] [ANDROID] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 + `VK_KHR_swapchain` |

---

## 1. 一句话定位

Swapchain recreate 是在 surface 尺寸、方向或可用性发生变化时，用新的 `VkSwapchainKHR` 替换旧的 swapchain，并同步重建所有尺寸相关资源的过程。[SPEC][ENGINE]

---

## 2. 所属对象链路

```text
Surface 尺寸 / 方向变化 或 VK_ERROR_OUT_OF_DATE_KHR
→ 停止提交新帧
→ 等待引用旧渲染资源的 GPU 提交完成，单独追踪旧 present 资源退役
→ 销毁尺寸相关资源（image view / framebuffer / depth / offscreen / descriptor）
→ vkCreateSwapchainKHR(oldSwapchain = 旧 swapchain)
→ 获取新 swapchain images
→ 重建 image view / framebuffer / depth / offscreen
→ 更新引用尺寸资源的 descriptor
→ 恢复渲染循环
```

### 上游依赖

- `VkSurfaceKHR` 必须仍有效（Android 上 `ANativeWindow` 未销毁）。[SPEC][ANDROID]
- 旧的 `VkSwapchainKHR` 存在或刚被 retired。[SPEC]
- 渲染线程已停止提交新的 command buffer。[ENGINE]

### 下游影响

- 重建或调整依赖实际变化的资源：swapchain image view、framebuffer、尺寸相关 depth/offscreen image；普通 per-frame uniform buffer 无需因 resize 重新分配，只需更新受影响数据。[ENGINE]
- 引用这些资源的 descriptor set 必须更新。
- viewport / scissor / dynamic rendering 尺寸必须刷新。

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkSwapchainKHR`（old & new）
- `VkSwapchainCreateInfoKHR::oldSwapchain`
- Swapchain `VkImage` / `VkImageView`
- `VkFramebuffer` / Dynamic Rendering attachment info
- Depth / offscreen `VkImage`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateSwapchainKHR` | 创建新 swapchain，传入 `oldSwapchain` 让旧 swapchain 退休。[SPEC] |
| `vkDestroySwapchainKHR` | 销毁前确认所有使用已结束；retired 状态本身不代表可释放。[SPEC] |
| `vkDeviceWaitIdle` | 等待设备 queue 提交完成，不能单独证明无扩展 present 资源可释放。[SPEC][GUIDE] |
| `vkQueueWaitIdle` | 等待指定 queue 提交完成，同样不能代替 present 资源完成追踪。[SPEC][GUIDE] |
| `vkGetSwapchainImagesKHR` | 获取新 swapchain 的 image handle。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_swapchain`：基础 recreate 支持。
- `VK_EXT_swapchain_maintenance1`（或已支持的 KHR 同名后继）：提供 present fence 等能力；查询扩展与对应 feature 并启用后才能使用，不是退休状态自动释放机制。[SPEC]
- Android 必须查询目标设备对所需扩展和 feature 的支持，不假设全部可用。[ANDROID]

---

<a id="present-retirement-contract"></a>
## 4. 标准使用流程

```text
触发条件:
    VK_ERROR_OUT_OF_DATE_KHR (acquire 或 present)
    VK_SUBOPTIMAL_KHR
    窗口 resize / rotation
    Android surface 重建

步骤:
1. 设置 recreate 标志，暂停下一帧渲染。
2. 等待所有引用待销毁渲染资源的提交完成（相关 fence 或 vkDeviceWaitIdle），不是只等当前 frame。
3. 已启用 swapchain_maintenance1 时，等待相关 present fence 后释放对应 present semaphore。
   无扩展时按官方 swapchain_recreation 样例维护旧 swapchain / present 资源退役；
   WaitIdle 是常见兼容做法，但不能作为严格的 presentation 资源释放证明。
4. 销毁依赖旧 swapchain image 的 framebuffer / image view。
5. 销毁依赖尺寸的 depth image / offscreen image / render target。
6. vkCreateSwapchainKHR(..., oldSwapchain = oldSwapchain, ...)。
7. vkGetSwapchainImagesKHR 获取新 images。
8. 为新 images 创建 image view。
9. 重建 framebuffer / depth / offscreen。
10. 更新 descriptor set 中引用尺寸相关 image 的条目。
11. 新 swapchain 按 image 数量建立 render-finished semaphore 数组；旧数组随旧 present 资源退役。
12. 确认旧 swapchain 所有使用结束后销毁；重置 recreate 标志，恢复渲染。
```

`VK_SUBOPTIMAL_KHR` 的 acquire 已取得 image 并安排信号，可以完成本帧 submit / present 后重建；`VK_ERROR_OUT_OF_DATE_KHR` 未取得 image，不得继续 submit，也不得 reset 本轮尚未提交的 frame fence。acquire 的 `VK_TIMEOUT` / `VK_NOT_READY` 跳过本轮；Surface / device lost 进入对应恢复路径。[SPEC][ENGINE]

---

## 5. 关键字段

| 字段 / 参数 | 专家关注点 | 常见错误 |
|---|---|---|
| `oldSwapchain` | 同一有效 Surface 上替换 swapchain 时传入旧 handle；调用后旧 swapchain 进入 retired，即使创建失败也不能继续从它 acquire。[SPEC] | 误以为 image 内容自动继承，或把 retired 当作所有工作已完成。[ENGINE] |
| `imageExtent` | 必须重新查询 surface capabilities 后使用最新 `currentExtent`。[SPEC] | 仍用旧 extent，导致创建失败或画面拉伸。[TOOL] |
| `preTransform` | Android rotation 后应重新对齐 `currentTransform`。[ANDROID] | 仍用旧 transform，导致 compositor 额外旋转。[TOOL] |
| `minImageCount` | 可能随 surface 变化，应重新查询。[SPEC] | 假设不变，新设备或模式下可能失败。[TOOL] |
| `imageFormat` | 通常不变，但 surface format 列表可能变化。[SPEC] | 未重新查询导致创建失败。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否在创建新 swapchain 前重新查询 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR`？
- [ ] `imageExtent` 是否为 0？为 0 时是否延迟 recreate？（Android 常见）[ANDROID]
- [ ] 是否传入 `oldSwapchain`？
- [ ] 旧渲染资源的提交是否完成，旧 swapchain / present semaphore 是否另有 presentation 退役证明？不能只看 idle。

### 使用阶段

- [ ] recreate 期间是否停止 acquire / submit / present？
- [ ] 新 swapchain 的 image index 是否与旧 image index 区分？
- [ ] viewport / scissor / dynamic rendering extent 是否已更新为新尺寸？

### 销毁阶段

- [ ] 是否按“framebuffer → image view → depth / offscreen → swapchain”顺序销毁？
- [ ] descriptor 是否已更新为新 image view / buffer？
- [ ] 旧 swapchain 和旧 present semaphore 是否分别确认所有相关使用结束后销毁？[SPEC]

---

## 7. 高频错误

1. 未处理 `VK_ERROR_OUT_OF_DATE_KHR`，继续使用旧 swapchain。[SPEC]
2. `VK_SUBOPTIMAL_KHR` 被忽略，导致 Android rotation 后画面方向或尺寸不对。[ANDROID]
3. recreate 前未等待 GPU idle，in-flight command buffer 仍引用旧 framebuffer。[SPEC]
4. 只重建 swapchain，未重建 depth image / offscreen image / framebuffer。[ENGINE]
5. 只重建 image view，未更新 descriptor set，导致 shader 仍采样旧 offscreen image。[ENGINE]
6. Android `onSurfaceDestroyed` 后直接销毁 surface，但仍在渲染线程中提交 present。[ANDROID]
7. `imageExtent` 为 0 时仍创建 swapchain，返回错误。[ANDROID]
8. 多线程下 recreate 与渲染线程竞态，导致旧资源被复用。[ENGINE]

---

## 8. Debug 检查路径

### Validation Layer

- 创建/销毁错误按实际 VUID 核对 [vkCreateSwapchainKHR](https://docs.vulkan.org/refpages/latest/refpages/source/vkCreateSwapchainKHR.html) / [vkDestroySwapchainKHR](https://docs.vulkan.org/refpages/latest/refpages/source/vkDestroySwapchainKHR.html)，不把 surface 或 in-flight 错误归到未经核实的编号。
- 重建时使用有效 oldSwapchain 与相同 surface；保留旧 swapchain 期间仍须完成其 acquired image / present 工作，不能仅凭 graphics fence 判断所有 present 已完成。 [官方 VkSwapchainCreateInfoKHR 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkSwapchainCreateInfoKHR.html)。[SPEC]
- `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 提示 recreate 触发点。[TOOL]

### RenderDoc / AGI

- RenderDoc：resize 后 framebuffer / image view 尺寸是否与新 swapchain 一致。
- AGI：查看 rotation / resize 事件后 swapchain 参数变化，验证 present 是否成功。[TOOL]

### 日志 / 代码检查

- 打印 acquire / present 返回值。
- 打印 recreate 前后 `imageExtent`、`imageFormat`、`imageCount`。
- Android logcat 中查找 `VK_ERROR_DEVICE_LOST` 或 surface lost。
- 检查 recreate 路径是否更新 viewport / scissor / descriptor。

---

## 9. 生命周期风险

### 创建时机

- acquire 或 present 返回 `VK_ERROR_OUT_OF_DATE_KHR` / `VK_SUBOPTIMAL_KHR` 时。
- 窗口 resize / Android rotation / surface 重建时。[ANDROID]

### 使用时机

- 新 swapchain 创建后，渲染循环切换至新 swapchain。
- 旧 swapchain 进入 retired 状态，仍可能被 GPU 使用直到 present 完成。[SPEC]

### 销毁时机

- 旧 swapchain 销毁前须确认 GPU 提交和 presentation 对相关资源的使用已结束；单独的 submit fence / WaitIdle 不是 present 资源完成证明。[SPEC][GUIDE]
- 旧 image view / framebuffer 在引用它们的提交完成后销毁，不要求一定先于新 swapchain 使用；同步正确时可让新旧资源短暂并存。[SPEC][ENGINE]

### in-flight 风险

- retired swapchain 的 image 仍可能被 pending command buffer 引用，销毁前必须确保 GPU 完成。[SPEC]
- 所有引用旧渲染资源的 frame fence 完成仅覆盖提交侧，present 资源还需独立追踪。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- recreate 前等待所有引用待释放渲染资源的提交；可选相关 fence / timeline value 或 WaitIdle。[SPEC]
- present fence 的含义是相关 presentation 资源可安全释放，不等同于该帧已被物理屏幕显示。[SPEC]

### GPU-GPU 同步

- 新旧 swapchain 的工作可以重叠，但必须分开维护资源与退役条件，不复用仍被旧 present 使用的 semaphore。[SPEC][ENGINE]
- 新 swapchain 的 acquire semaphore 必须配对新 swapchain 的 submit。[ENGINE]

### 资源访问同步

- 旧 swapchain image 不再使用后，相关 layout transition 无需再做；但新 swapchain image 首次使用仍需从 `UNDEFINED` 或 `PRESENT_SRC_KHR` transition。[SPEC]
- 尺寸相关 offscreen image 重建后，首次写入前通常从 `UNDEFINED` transition。[SPEC]

---

## 11. Android 注意点

- Android 横竖屏切换通常触发 `VK_SUBOPTIMAL_KHR` 或 `VK_ERROR_OUT_OF_DATE_KHR`，应完整 recreate。[ANDROID]
- `APP_CMD_TERM_WINDOW` 后不应 recreate，应停止渲染；`APP_CMD_INIT_WINDOW` 后在新 `ANativeWindow` 上重新创建 surface 和 swapchain。[ANDROID]
- 分屏 / 多窗口 / 折叠屏展开时，`currentExtent` 可能动态变化，应监听并触发 recreate。[ANDROID]
- 某些设备在 `onPause` 后 surface 仍有效，但 safest path 是暂停渲染并在 resume 时检查是否需要 recreate。[HEUR]
- `preTransform` 应与 `currentTransform` 对齐，避免 compositor 额外旋转消耗。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- `vkDeviceWaitIdle` 会阻塞 CPU；可用相关提交 fence / timeline value 缩小等待范围，present 资源仍需单独追踪。[ENGINE]
- 频繁 resize（如用户拖拽窗口）应 debounce recreate，避免每帧重建。[ENGINE]

### GPU 侧

- 旧 swapchain 退休期间，driver 可能同时维护两套 image，短暂增加内存占用。[HEUR]
- swapchain_maintenance1 的 present fence 使 presentation 资源回收有明确完成点，可配合延迟销毁减少 stall。[GUIDE]

### 移动端

- Android rotation 时，重建 depth / offscreen 资源是主要开销；应尽量复用 allocator / memory pool。[ENGINE]
- 移动端按已测瓶颈选择等待策略；优化前先保证提交与 present 资源的退役条件完整。[ENGINE]

---

## 13. 专家经验

**经验**：
简单 renderer 可把 recreate 封装为与正常 frame loop 互斥的阶段；使用延迟退役的 renderer 可在切换到新资源后继续渲染，但旧 present 资源必须保留到安全回收点。不要把简单实现策略标成 Vulkan 限制。

**适用条件**：
存在 resize / rotation / surface 重建的 Android 或桌面应用，使用传统 per-frame resource 管理。

**不适用情况**：
已有 RenderGraph 或现代渲染框架自动处理 swapchain lifecycle；或窗口尺寸永不变化的应用。

**来源**：`[ENGINE][ANDROID]`

---

## 14. 相关 API 卡片

- `surface.md`
- `swapchain.md`
- `../03_command_buffer/command_buffer.md`
- `../03_command_buffer/command_buffer_lifetime.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`
- `../05_descriptor/descriptor_set.md`
- `../05_descriptor/descriptor_update.md`
- `../08_synchronization/fence.md`
- `../08_synchronization/semaphore.md`

---

## 15. 需要回查官方文档的情况

1. 目标平台对 `oldSwapchain` 的具体行为差异（部分驱动对 retired swapchain 处理不同）。
2. `VK_EXT_swapchain_maintenance1` 的启用与使用条件。
3. Android 设备在 `onPause` / `onResume` / rotation 时对 `ANativeWindow` 和 swapchain 的生命周期差异。
4. 多 queue / 多 surface 场景下的 recreate 同步策略。
5. `VkSurfaceCapabilitiesKHR` 中 `currentExtent` 为 0 或 `0xFFFFFFFF` 时的精确处理。

依据：[Swapchain Semaphore Reuse](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html)、[官方 Swapchain Recreation 样例](https://docs.vulkan.org/samples/latest/samples/api/swapchain_recreation/README.html)。

<a id="delivery19-headless-present-retirement"></a>
## v1.0.19：headless WSI 的 acquire → readback → present → 重建退休

`cases19/headless_wsi` / `tools/headless_wsi19.py` 是实际 Vulkan 1.4.309 工具配对的 headless surface 路径，不需要 X/Wayland 窗口，也不能证明真实屏幕呈现、窗口 resize、latency 或移动端 Surface 行为。

**先证明完整路径可用。** 查询 headless/surface 扩展、swapchain、对应 queue 的 surface present 支持、格式/色彩空间、present mode、图像数量/extent/usage、transform/composite alpha。只用已列出的 RGBA8/BGRA8 UNORM + SRGB_NONLINEAR、FIFO、TRANSFER_DST|TRANSFER_SRC；clear 后逐像素复制读回按实际通道顺序解码。maxImageCount=0 表示无此上限，不是允许0张图像；固定 currentExtent 不能随意替换。枚举格式数不等于格式可用；还需实际查询选定 format 的2D optimal、usage3、flags0 image-format properties，验证 extent、layer1及sample1可用。

**呈现退休不是渲染退休。** 查询并启用 `VK_EXT_swapchain_maintenance1` 与 `swapchainMaintenance1`，每次 `vkQueuePresentKHR` 链 `VkSwapchainPresentFenceInfoEXT`，实际等待其 fence。render submit fence 只证明对应渲染提交完成，不能独自授权回收 present-wait semaphore 或旧 swapchain；queue/device WaitIdle 也不作为本例呈现退休的证据。若无 maintenance1，本次完整退休准入明确不可用，不伪造替代。

**每帧有独立完成事实。** acquire 成功或 SUBOPTIMAL 才能消费返回的 image index，并等待实际 acquire 同步后访问；NOT_READY/TIMEOUT/OUT_OF_DATE 不得继续等待未信号的 acquire semaphore 或使用旧 index。clear→transfer read→present layout 的依赖、renderDone binary semaphore 被 present 消费、render fence 后 readback、present fence 后同步对象复用分别记录。本例保守逐帧串行，不冒充多帧并行压力测试。present fence 只用于安全退休，不声称用户已看到像素。

**重建保持代际。** 两个 generation 使用合法的不同 extent，各至少两个不同颜色帧。所有旧代 frame 的 render/present 完成后才创建新链，明确传入该旧 `oldSwapchain` 并记录关联。传给创建调用的旧链会退休，即使新链创建失败也不能继续从旧链 acquire；失败恢复须另设计，不把旧链误作回退。新代成功后销毁已经完成退休的旧对象，禁止 generation 混用。

**安全负控与独立输出。** acquire 时 semaphore/fence 均为空触发01780，由 Validation callback 中止，不能读取输出 index 或提交后续工作。错误像素参考必须失败，API 验证与画面数据判据分开。CPU 规则覆盖 timeout/suboptimal/out-of-date、固定 extent、数量边界、过期 generation 和“仅 queueIdle/renderFence 不足”反例；这些规则测试不是设备上真实发生过的窗口失效事件。

范围仍限定 headless、CPU ICD、单 queue、transfer clear/readback、显式 present-fence 退休与主动 extent 重建。没有验收真实 OUT_OF_DATE/SURFACE_LOST、全平台 WSI、protected、VRR/display timing、物理可见输出、SC、外部工程或盲测。

固定来源：[wsi.adoc / v1.4.309](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/VK_KHR_surface/wsi.adoc)，blob `0bd56db191d0522265e63f2a7ba12364a6966127`；[swapchain wsi.adoc / v1.4.309](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/VK_KHR_swapchain/wsi.adoc)，blob `e4f2f9c5acc8bcd8e874cf6052afa12d179b59f4`；[present fence / v1.4.309](https://github.com/KhronosGroup/Vulkan-Docs/blob/v1.4.309/chapters/VK_EXT_swapchain_maintenance1/SwapchainPresentFenceInfo.adoc)，blob `3fcf8641e5253b5bc850a875a1a7bc9242ad3dce`，Khronos CC-BY-4.0（本段概述）；[Swapchain semaphore reuse guide](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html) 是补充工程解释，不当作固定版本设备证据。完整 frozen validusage 摘录及实际范围见 tests 仓 `coverage/v1.0.19/headless-wsi.json`。

<a id="v20-acquire-generation-contract"></a>
## v1.0.20：Acquire、提交与旧代退休的分支

**先分三条归属线。** 取得 image 的 acquire semaphore/fence、frame slot 的 render-submit fence、以及 present 等待/退休对象不互相替代。日志关联 surface/swapchain generation、image index、frame slot 和对应提交或 present；不同代即便 index 和 slot 又相同，归属仍不同。

- `VK_SUCCESS` 或 `VK_SUBOPTIMAL_KHR`：取得当前代 image；按本次 acquire 的同步约束使用。即使决定不渲染，也要有已获取 image 与 acquire 同步的合法处置计划，不能把成功路径当作“未获取”直接回池。
- `VK_NOT_READY`、`VK_TIMEOUT`、`VK_ERROR_OUT_OF_DATE_KHR` 等未成功取得 image：原 acquire semaphore/fence 状态不变；不读 image index、不提交等待本次未发生信号的工作。NOT_READY/TIMEOUT 按预算决定是否重试；OUT_OF_DATE 重查并重建当前输出，SURFACE_LOST 先恢复有效 surface。frame submit fence 保持原状态：不要在 acquire 前重置它，除非已实现每条无提交分支的安全退路。
- 新代创建失败且传入了 `oldSwapchain`：旧链已退休，不能恢复其 acquire 循环。另建合法候选，不把句柄仍存在当作未退休。旧代各 GPU 使用完成与 WSI 呈现资源退休分别追踪；见上文 headless WSI 的历史范围，不把 CPU ICD 结论外推到窗口或移动设备。

**反例与止损。** acquire 前 reset frame fence，再因 OUT_OF_DATE early-return，会让下一次 slot 等待一个没有关联提交的 fence。仅有渲染提交完成，仍不授权复用 present-wait semaphore。仅因新资源绑定成功，也不能把旧代已经录制的命令继续提交；检查 [descriptor 更新失效](../05_descriptor/descriptor_update.md#v20-descriptor-command-validity) 与 [命令退休](../03_command_buffer/command_buffer_lifetime.md#command-retirement-contract)。异常恢复不得靠主循环下一帧自愈。

[SPEC] 固定 1.4.368： [WSI acquire、oldSwapchain 与 present](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/VK_KHR_surface/wsi.adoc)。与 [fence 作用域](../08_synchronization/fence.md#fence-completion-contract) 对照。此处是规则及反例审查，不代表真实 OUT_OF_DATE/SURFACE_LOST 或 Android 已执行。

### Vulkan 1.4.369：present fence 的主机同步

把传给 present 的每个非空 `pFences` 元素纳入对应 fence 的主机访问协调；不要让其他线程并发 reset、destroy 或将该 fence 另作提交使用。present 前须是未触发、未关联尚未完成的队列命令的 fence；host 互斥不代表 present 已退休。用同一代 swapchain 的呈现完成证据退役，而不是提交 fence 的信号。[SPEC][ENGINE]

1.4.369 的 Registry 在 KHR 结构的 `pFences` 标了 `externsync`；EXT 名称是该结构的别名，不能当独立语义处理。固定来源：[Registry](https://github.com/KhronosGroup/Vulkan-Docs/blob/33d3353757d83d6aca683120114fe74cc4eaf8fb/xml/vk.xml)；[present fence 与 VU](https://github.com/KhronosGroup/Vulkan-Docs/blob/33d3353757d83d6aca683120114fe74cc4eaf8fb/chapters/VK_KHR_surface/wsi.adoc#L8681-L8740)。

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
→ 等待 GPU idle / in-flight 完成
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

- 所有 swapchain-size 资源必须重建：image view、framebuffer、depth/stencil image、offscreen render target、per-frame uniform buffer 等。
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
| `vkDestroySwapchainKHR` | 销毁 swapchain；若旧 swapchain 已退休且 GPU 用完，可安全销毁。[SPEC] |
| `vkDeviceWaitIdle` | 等待所有 queue 完成，常用于 recreate 前同步。[SPEC] |
| `vkQueueWaitIdle` | 等待单个 queue 完成，可作为更轻量的替代。[SPEC] |
| `vkGetSwapchainImagesKHR` | 获取新 swapchain 的 image handle。[SPEC] |

### 相关扩展 / 版本

- `VK_KHR_swapchain`：基础 recreate 支持。
- `VK_EXT_swapchain_maintenance1`：允许 retired swapchain 延迟销毁，减少卡顿。
- Android 可用性：全部可用。[ANDROID]

---

## 4. 标准使用流程

```text
触发条件:
    VK_ERROR_OUT_OF_DATE_KHR (acquire 或 present)
    VK_SUBOPTIMAL_KHR
    窗口 resize / rotation
    Android surface 重建

步骤:
1. 设置 recreate 标志，暂停下一帧渲染。
2. 等待当前 frame 的 fence signal（或 vkDeviceWaitIdle）。
3. 调用 vkQueueWaitIdle(presentQueue) 确保 present 完成。
4. 销毁依赖旧 swapchain image 的 framebuffer / image view。
5. 销毁依赖尺寸的 depth image / offscreen image / render target。
6. vkCreateSwapchainKHR(..., oldSwapchain = oldSwapchain, ...)。
7. vkGetSwapchainImagesKHR 获取新 images。
8. 为新 images 创建 image view。
9. 重建 framebuffer / depth / offscreen。
10. 更新 descriptor set 中引用尺寸相关 image 的条目。
11. 重置 recreate 标志，恢复渲染。
```

---

## 5. 关键字段

| 字段 / 参数 | 专家关注点 | 常见错误 |
|---|---|---|
| `oldSwapchain` | 传入旧 swapchain 可实现 images 无缝继承，避免黑屏 / flicker。[SPEC] | 传 `VK_NULL_HANDLE`，resize 时旧 image 立即释放，可能闪黑。[HEUR] |
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
- [ ] 旧 swapchain 是否仍在被 GPU 使用？是否等待 idle 后再销毁？

### 使用阶段

- [ ] recreate 期间是否停止 acquire / submit / present？
- [ ] 新 swapchain 的 image index 是否与旧 image index 区分？
- [ ] viewport / scissor / dynamic rendering extent 是否已更新为新尺寸？

### 销毁阶段

- [ ] 是否按“framebuffer → image view → depth / offscreen → swapchain”顺序销毁？
- [ ] descriptor 是否已更新为新 image view / buffer？
- [ ] 旧 swapchain 是否在 GPU idle 后销毁？[SPEC]

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

- `VUID-vkCreateSwapchainKHR-surface-01270`：surface 仍被旧 swapchain 使用。
- `VUID-vkDestroySwapchainKHR-swapchain-01282`：swapchain 仍被 command buffer 引用。
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

- 旧 swapchain 应在 GPU idle 或所有 in-flight present 完成后销毁。[SPEC]
- 依赖旧 swapchain image 的 image view / framebuffer 必须在新 swapchain 使用前销毁。[SPEC]

### in-flight 风险

- retired swapchain 的 image 仍可能被 pending command buffer 引用，销毁前必须确保 GPU 完成。[SPEC]
- frame-in-flight 的 fence 必须全部 signal 后才能安全释放旧资源。[ENGINE]

---

## 10. 同步风险

### CPU-GPU 同步

- recreate 前通常使用 `vkDeviceWaitIdle` 或等待所有 frame fence。[SPEC]
- 若使用 `vkQueueWaitIdle`，需确保覆盖 graphics 和 present queue。[SPEC]

### GPU-GPU 同步

- 旧 swapchain 的 present 可能仍在进行，新 swapchain 的 acquire 不应与旧 swapchain 的 present 重叠。[SPEC]
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

- `vkDeviceWaitIdle` 会阻塞 CPU，可能导致卡顿；可考虑 per-frame fence 等待替代。[ENGINE]
- 频繁 resize（如用户拖拽窗口）应 debounce recreate，避免每帧重建。[ENGINE]

### GPU 侧

- 旧 swapchain 退休期间，driver 可能同时维护两套 image，短暂增加内存占用。[HEUR]
- `VK_EXT_swapchain_maintenance1` 可让 retired swapchain 延迟销毁，减少 stall。[GUIDE]

### 移动端

- Android rotation 时，重建 depth / offscreen 资源是主要开销；应尽量复用 allocator / memory pool。[ENGINE]
- 移动端 recreate 时避免 `vkDeviceWaitIdle`，优先使用 per-frame fence 等待。[ENGINE]

---

## 13. 专家经验

**经验**：
把 swapchain recreate 封装为一个独立阶段，与正常 frame loop 互斥。recreate 期间禁止任何 command buffer 录制、submit 和 present，直到所有旧资源释放完毕。

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

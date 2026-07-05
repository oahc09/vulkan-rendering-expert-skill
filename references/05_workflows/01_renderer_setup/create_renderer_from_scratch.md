# Workflow: Create Vulkan Renderer From Scratch

## 0. 适用范围

### 适用

- 从零创建 Vulkan renderer。
- 建立最小可运行 clear color / triangle。
- 新项目初始化 Vulkan 对象链路。
- Android / Desktop 都可用，但 Android 需要额外处理 Surface 生命周期。

### 不适用

- 已有完整 renderer，只需要新增一个 pass。
- 只需要修复某个 validation error。
- 只做 shader 效果，不处理 Vulkan 对象链路。

---

## 1. 任务目标

建立一个最小但结构正确的 Vulkan Renderer，至少能完成：

```text
Instance
→ Device / Queue
→ Surface / Swapchain
→ CommandBuffer
→ Render Target
→ Submit
→ Present
```

最小验收目标：

- clear color 可见。
- Validation Layer 无关键错误。
- RenderDoc / AGI 可抓帧。
- resize / surface recreate 有基本处理路径。

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本与目标 GPU。
- Surface 来源：Android SurfaceView / NativeActivity / GLFW / SDL / 自定义窗口。
- 是否需要 depth buffer。
- 是否使用传统 RenderPass 还是 Dynamic Rendering。
- 是否需要多帧 in-flight。
- 是否需要后续扩展到 texture / compute / postprocess。

---

## 3. 前置检查

- [ ] Vulkan loader 可用。
- [ ] 目标设备支持 Vulkan。
- [ ] Validation Layer 可开启。
- [ ] Surface 创建路径明确。
- [ ] Shader 编译链路明确。
- [ ] 能记录 API 返回值日志。
- [ ] Android 上能记录 Surface created / changed / destroyed。

---

## 4. Vulkan 对象链路

```text
Application
→ VkInstance
→ VkPhysicalDevice
→ VkDevice
→ VkQueue
→ VkSurfaceKHR
→ VkSwapchainKHR
→ Swapchain Images
→ VkImageView
→ CommandPool
→ CommandBuffer
→ Sync Objects
→ Queue Submit
→ Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| swapchain image | `VkImage` | color attachment / present | swapchain 生命周期 | 是 |
| swapchain image view | `VkImageView` | render target view | swapchain 生命周期 | 是 |
| depth image | `VkImage` | depth stencil attachment | swapchain 尺寸相关 | 是 |
| command buffer | `VkCommandBuffer` | record draw / clear | frame resource | 通常是 |
| semaphore / fence | `VkSemaphore` / `VkFence` | frame sync | frame resource | 否 |

---

## 6. Pipeline / Descriptor 设计

最小 renderer 可先不引入 descriptor。  
如果需要 triangle：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | 无 | push constant / hardcoded vertex | Vertex / Fragment |

后续再扩展：

- Uniform Buffer
- Texture Sampler
- Storage Buffer
- Descriptor Set

---

## 7. 同步与 Layout 设计

基础 frame loop：

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| Present Engine | Swapchain Image | acquire semaphore / present → color attachment | Graphics Queue |
| Graphics Queue | Swapchain Image | color attachment → present | Present Engine |

必须明确：

- `imageAvailableSemaphore`：present engine → graphics queue。
- `renderFinishedSemaphore`：graphics queue → present engine。
- `inFlightFence`：GPU → CPU，控制 frame resource 复用。
- Swapchain image layout：color attachment / present 之间转换。

---

## 8. 实现步骤

1. 创建 `VkInstance`。
2. 开启 validation layer 和 debug utils。
3. 创建 platform surface。
4. 枚举 physical device。
5. 选择 queue family。
6. 创建 logical device 和 graphics/present queue。
7. 查询 surface capability / format / present mode。
8. 创建 swapchain。
9. 获取 swapchain images 并创建 image views。
10. 创建 depth image，如需要。
11. 创建 command pool。
12. 创建 command buffers。
13. 创建 sync objects。
14. 实现 frame loop：
    - wait fence
    - acquire image
    - reset command buffer
    - record command buffer
    - submit
    - present
15. 实现 swapchain recreate。
16. 实现 destroy 逆序清理。

---

## 9. Android 注意点

Android 上必须额外处理：

- Surface created 前不能创建 swapchain。
- Surface destroyed 后不能继续 render / present。
- `ANativeWindow` 需要明确 acquire/release。
- rotation / resize 触发 swapchain recreate。
- pause 时暂停 render thread。
- resume 后检查 surface 是否仍有效。
- extent 为 0 时不要创建 swapchain。
- 使用 logcat 记录生命周期。

---

## 10. 验证方式

- [ ] Validation Layer clean。
- [ ] clear color 可见。
- [ ] RenderDoc / AGI 能抓到 frame。
- [ ] acquire / submit / present 返回值正常。
- [ ] resize / rotation 后正常。
- [ ] pause / resume 后正常。
- [ ] 资源销毁无 validation lifetime error。

---

## 11. 常见失败模式

1. 只创建 swapchain，没有处理 recreate。
2. command buffer 录制失败但未检查返回值。
3. fence reset/wait 顺序错误。
4. Surface destroyed 后继续 present。
5. swapchain extent 为 0 仍创建资源。
6. 销毁顺序不正确。
7. 忘记创建 image view。

---

## 12. 相关 API 卡片

- `../../03_api_manual/01_instance_device_queue/instance.md`
- `../../03_api_manual/01_instance_device_queue/logical_device.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

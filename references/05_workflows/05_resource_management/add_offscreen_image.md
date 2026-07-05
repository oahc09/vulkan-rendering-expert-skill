# Workflow: Add Offscreen Image

## 0. 适用范围

### 适用

- 新增 offscreen color attachment，用于 postprocess、deferred shading、shadow map、reflection 等。
- 新增 offscreen depth attachment，用于 depth prepass、shadow mapping、depth-only pass。
- 同时支持 render pass + framebuffer 路径与 dynamic rendering 路径。
- 需要处理 swapchain recreate 时尺寸相关 image 的重建。

### 不适用

- 直接渲染到 swapchain image 的简单 forward rendering（无需 offscreen）。
- 纯 compute / headless 无 graphics attachment 的场景。
- 资源生命周期完全由外部 RenderGraph 托管、无需手动创建 image/view/framebuffer 的场景。

---

## 1. 任务目标

新增稳定的 offscreen color/depth image：

```text
VkDevice
→ VkImage (color or depth)
→ VkDeviceMemory
→ VkImageView
→ VkFramebuffer (render pass path)
  or VkRenderingInfo (dynamic rendering path)
→ Shader / Next Pass
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux。
- Vulkan 版本。
- 用途：color target / depth target / both（MRT / depth-stencil）。
- 目标尺寸：固定尺寸、swapchain 比例（如 0.5x / 1.0x）、或屏幕尺寸。
- 期望格式：color format、depth format。
- 是否使用 MSAA：sample count。
- 是否作为 texture 被后续 pass 采样（影响 usage）。
- 是否作为 input attachment / subpass input。
- 当前使用 render pass + framebuffer 还是 dynamic rendering。
- Swapchain recreate 策略。

---

## 3. 前置检查

- [ ] Validation Layer 可用。
- [ ] RenderDoc / AGI 可抓帧。
- [ ] 当前 renderer 能 clear / render 到 swapchain image。
- [ ] `vkGetPhysicalDeviceFormatProperties` 已确认目标 format 支持作为 attachment。
- [ ] `vkGetPhysicalDeviceImageFormatProperties` 已确认目标 usage / sample count 组合合法 [SPEC]。
- [ ] Swapchain recreate 路径已有基础处理。
- [ ] Command buffer / frame-in-flight 稳定。
- [ ] Android Surface / ANativeWindow 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
Render Target Specification (size/format/usage/samples)
→ VkImage
→ VkDeviceMemory
→ VkImageView
→ VkFramebuffer (render pass path)
   or VkRenderingAttachmentInfo (dynamic rendering path)
→ VkRenderPass / VkRenderingInfo
→ VkPipeline (render pass compatible / dynamic rendering)
→ Draw / Dispatch / Next Pass Sampler
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| offscreen color image | `VkImage` | `COLOR_ATTACHMENT_BIT` (+ `SAMPLED_BIT` / `STORAGE_BIT` / `TRANSIENT_ATTACHMENT_BIT` 按需) | per-pass / per-frame | 是（若尺寸依赖 swapchain） |
| offscreen depth image | `VkImage` | `DEPTH_STENCIL_ATTACHMENT_BIT` (+ `SAMPLED_BIT` / `TRANSIENT_ATTACHMENT_BIT` 按需) | per-pass / per-frame | 是 |
| color image memory | `VkDeviceMemory` | device-local（或 LAZILY_ALLOCATED 对 transient） | 与 image 绑定 | 是 |
| depth image memory | `VkDeviceMemory` | device-local（或 LAZILY_ALLOCATED 对 transient） | 与 image 绑定 | 是 |
| color image view | `VkImageView` | 绑定到 framebuffer 或作为 sampled image | 与 image 同生命周期 | 是 |
| depth image view | `VkImageView` | 绑定到 framebuffer 或作为 sampled depth | 与 image 同生命周期 | 是 |
| framebuffer | `VkFramebuffer` | 聚合 color/depth views（render pass 路径） | per-pass | 是 |
| resolve image | `VkImage` | MSAA resolve target | per-pass | 是 |
| resolve view | `VkImageView` | resolve 绑定 / 后续采样 | per-pass | 是 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `COMBINED_IMAGE_SAMPLER` | offscreen color image view | Fragment / Compute |
| set=0,binding=1 | `COMBINED_IMAGE_SAMPLER` | offscreen depth image view | Fragment / Compute |
| set=1,binding=0 | `STORAGE_IMAGE` | offscreen color image view（compute write） | Compute |
| push constant | `VkPushConstantRange` | postprocess params / sampler 配置 | Fragment / Compute |

Pipeline 状态：

- `VkPipelineRenderingCreateInfo` 或 `VkRenderPass` 中 color format 必须与 image format 一致 [SPEC]。
- Depth format 必须与 depth image format 一致；`depthWriteEnable` / `depthCompareOp` 按用途设置 [SPEC]。
- 若 offscreen image 是 multisample，pipeline `rasterizationSamples` 必须匹配；resolve 通过 subpass `pResolveAttachments` 或 `VkRenderingAttachmentInfo::resolveImageView` 完成 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass / clear | offscreen color image | `UNDEFINED` → `COLOR_ATTACHMENT_OPTIMAL` | color attachment output |
| color attachment output | offscreen color image | `COLOR_ATTACHMENT_OPTIMAL` | next pass sampler / present |
| previous pass / clear | offscreen depth image | `UNDEFINED` → `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` | depth test / write |
| depth write pass | offscreen depth | `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | shadow sampling pass |
| compute write | offscreen color storage | `GENERAL`（写入） | compute read / next pass |

必须说明：

- 作为 color attachment 使用时，layout 应为 `COLOR_ATTACHMENT_OPTIMAL` [SPEC]。
- 作为 depth attachment 使用时，layout 应为 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` [SPEC]。
- 作为 shader sampled image 使用时，layout 应为 `SHADER_READ_ONLY_OPTIMAL`；若要在 compute 中读写，使用 `GENERAL` [SPEC]。
- `TRANSFER_DST_OPTIMAL` 仅用于 `vkCmdClearColorImage` / copy 等 transfer 操作 [SPEC]。
- 同一 image 在同一 queue 中 producer/consumer 关系必须通过 barrier 或 subpass dependency 表达，不能依赖 implicit layout transition 跨越 command buffer 边界 [SPEC]。

---

## 8. 实现步骤

1. **确定尺寸策略**：固定值、按 swapchain extent 比例、或直接使用 `swapchainExtent`；shadow map 通常固定或按级联比例 [HEUR]。
2. **选择 format**：
   - color LDR：`R8G8B8A8_UNORM` / `B8G8R8A8_UNORM`；
   - color HDR：`R16G16B16A16_SFLOAT` / `R11G11B10_UFLOAT` / `R10G10B10A2_UNORM`；
   - depth：`D16_UNORM` / `D24_UNORM_S8_UINT` / `D32_SFLOAT`；
   - 调用 `vkGetPhysicalDeviceFormatProperties` 确认 `VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT` / `DEPTH_STENCIL_ATTACHMENT_BIT` [SPEC]。
3. **选择 sample count**：
   - 单 sample 用于大多数 offscreen pass；
   - MSAA 需要 `vkGetPhysicalDeviceImageFormatProperties` 确认 `sampleCounts` 支持 [SPEC]；
   - transient MSAA 加 `VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` + `VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT` [SPEC]。
4. **计算 usage**：
   - 仅 attachment：`VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT` / `DEPTH_STENCIL_ATTACHMENT_BIT`；
   - 后续采样：加 `VK_IMAGE_USAGE_SAMPLED_BIT`；
   - compute 读写：加 `VK_IMAGE_USAGE_STORAGE_BIT`；
   - transient MSAA：加 `VK_IMAGE_USAGE_TRANSIENT_ATTACHMENT_BIT` [SPEC]。
5. **创建 image**：填写 `VkImageCreateInfo`，注意 `arrayLayers`、`mipLevels`、`samples`、`tiling = OPTIMAL` [SPEC]。
6. **分配并绑定 memory**：
   - 普通 attachment：`VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT`；
   - transient attachment：优先 `VK_MEMORY_PROPERTY_LAZILY_ALLOCATED_BIT`，fallback 到 device-local [SPEC]。
7. **创建 image view**：
   - color：aspect `VK_IMAGE_ASPECT_COLOR_BIT`；
   - depth：`VK_IMAGE_ASPECT_DEPTH_BIT`（如含 stencil 可 `DEPTH | STENCIL`）[SPEC]。
8. **render pass 路径**：创建/复用 `VkRenderPass`，再创建 `VkFramebuffer` 聚合 color/depth views [SPEC]。
9. **dynamic rendering 路径**：使用 `VkRenderingInfo` + `VkRenderingAttachmentInfo` 直接引用 image view [SPEC]。
10. **layout transition**：首次使用前从 `UNDEFINED` 到目标 layout；clear 用 `LOAD_OP_CLEAR` / `vkCmdClearColorImage` [SPEC]。
11. **接入 frame loop**：绑定 framebuffer 或录制 dynamic rendering begin，绘制/计算，barrier 到下游 layout。
12. **接入 swapchain recreate**：
    - 若 image 尺寸/比例依赖 swapchain extent，在 recreate 时 `vkDeviceWaitIdle` 后销毁旧 image / view / framebuffer；
    - 按新 extent 重建；
    - 更新引用这些 view 的 descriptor set [SPEC]。
13. **接入销毁路径**：按 `framebuffer → image view → image → memory` 顺序销毁，device idle 后执行 [ENGINE]。

---

## 9. Android 注意点

- `ANativeWindow` / `VkSurfaceKHR` 创建后才能确定 swapchain extent；依赖屏幕尺寸的 offscreen image 必须在 surface 创建后创建，不可在 `onCreate` 中硬编码默认尺寸 [ANDROID]。
- rotation / resize 改变 extent 后，触发 `VK_ERROR_OUT_OF_DATE_KHR` 或 `VK_SUBOPTIMAL_KHR`，必须重建 swapchain 与尺寸相关 offscreen image / framebuffer [ANDROID]。
- `extent.width == 0 || extent.height == 0` 时暂停渲染循环，不创建 0 尺寸 image（`vkCreateImage` 会失败）[ANDROID]。
- pause / resume 期间释放 swapchain 相关 offscreen image；resume 后按新 surface 重建。
- 移动端 transient attachment + LAZILY_ALLOCATED 是降低 MSAA 带宽的关键，但部分 Mali 驱动对 LAZY 分配行为有差异，需 AGI 验证实际内存占用 [ANDROID]。
- AGI / logcat 验证：检查 image format、extent、usage、sample count、framebuffer 创建参数。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkImageCreateInfo-*`、`VUID-VkFramebufferCreateInfo-*`、`VUID-vkCmdPipelineBarrier-*` 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 offscreen pass、attachment image、clear/load/store 操作 [TOOL]。
- [ ] 截图 / 数值验证：offscreen color/depth 输出符合预期，后续 pass 采样正确。
- [ ] logcat（Android）：无 validation error；可输出 offscreen image extent、format、usage。
- [ ] 性能指标：
  - transient MSAA 实际内存占用在 AGI 中不过高；
  - offscreen pass 的 bandwidth 在目标预算内；
  - 无 redundant layout transition [HEUR]。
- [ ] resize / pause / resume / rotation 后 offscreen image 重建正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 image layout hazard。

---

## 11. 常见失败模式

1. **Format 不支持 attachment**：未检查 `formatProperties` 直接创建 image [SPEC]。
2. **Usage 缺失**：offscreen image 后续要采样但创建时未加 `SAMPLED_BIT` [SPEC]。
3. **MSAA sample count 不匹配**：pipeline `rasterizationSamples` 与 image samples 不一致 [TOOL]。
4. **Depth image layout 错误**：采样 depth 时未从 `DEPTH_STENCIL_ATTACHMENT_OPTIMAL` 转换到 `SHADER_READ_ONLY_OPTIMAL` [SPEC]。
5. **Framebuffer view 与 render pass 不兼容**：view format 或 layer count 不匹配 [SPEC]。
6. **Recreate 时旧 image 仍被 GPU 使用**：未等待 device idle / fence 就销毁 [TOOL]。
7. **Dynamic rendering resolve 配置错误**：`resolveImageLayout` 或 `resolveMode` 设置不当 [SPEC]。
8. **Android rotation 后 descriptor 悬垂**：swapchain/offscreen view 重建后未重新 update descriptor [ANDROID]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/memory_allocation.md`
- `../../03_api_manual/04_buffer_image_memory/image_layout.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/04_buffer_image_memory/framebuffer.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/depth_test_wrong.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- offscreen image 用途（color/depth、是否采样、是否 MSAA）。
- `VkImageCreateInfo` 完整参数。
- Render pass 还是 dynamic rendering。
- Swapchain recreate 触发条件与处理顺序。
- Validation Layer 完整报错。
- Android lifecycle 日志。

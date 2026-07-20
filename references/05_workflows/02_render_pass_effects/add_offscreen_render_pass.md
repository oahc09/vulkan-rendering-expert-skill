# Workflow: Add Offscreen Render Pass

## 0. 适用范围

### 适用

- 新增离屏渲染目标。
- 后处理链路中的中间 render target。
- shadow / reflection / blur / bloom / custom pass。
- 需要将 pass 输出作为后续 pass 输入。

### 不适用

- 直接渲染到 swapchain 且不需要中间图像。
- 纯 buffer compute pass。
- 不涉及 Vulkan image 资源的任务。

---

## 1. 任务目标

新增一个 offscreen render pass：

```text
Create Offscreen Image
→ Render To Offscreen
→ Barrier
→ Sample / Consume In Next Pass
```

---

## 2. 输入条件

需要确认：

- offscreen image 分辨率。
- format。
- usage：color attachment / sampled / storage / transfer。
- 是否随 swapchain 尺寸重建。
- 是否需要 depth。
- 后续 consumer 是 graphics 还是 compute。
- 是否需要 mipmap / array layer。

---

## 3. 前置检查

- [ ] 当前 frame loop 稳定。
- [ ] image / memory 创建封装可用。
- [ ] descriptor 更新路径可用。
- [ ] barrier / layout transition 机制可用。
- [ ] RenderDoc / AGI 可查看 render target。

---

## 4. Vulkan 对象链路

```text
VkImage
→ VkDeviceMemory
→ VkImageView
→ Render Target Attachment
→ Render Pass / Dynamic Rendering
→ Barrier
→ Descriptor / Next Pass
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| offscreen color | `VkImage` | `COLOR_ATTACHMENT | SAMPLED` | pass resource | 通常是 |
| offscreen view | `VkImageView` | attachment / sampled view | 跟随 image | 通常是 |
| depth image | `VkImage` | `DEPTH_STENCIL_ATTACHMENT` | pass resource | 视需求 |
| framebuffer | `VkFramebuffer` | render target binding | 传统 render pass | 是 |
| descriptor | `VkDescriptorSet` | next pass sampled input | pass / per-frame | 视需求 |

---

## 6. Pipeline / Descriptor 设计

当前 pass 输出不一定需要 descriptor。
如果后续 pass 采样 offscreen image：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | Combined Image Sampler | offscreen image view | Fragment |

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| offscreen color attachment write | offscreen image | `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | next pass fragment shader |
| offscreen transfer write | offscreen image | `TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | next pass fragment shader |

关键点：

- 初始 layout 可为 `UNDEFINED`。
- 渲染时 layout 为 `COLOR_ATTACHMENT_OPTIMAL`。
- 后续采样时 layout 为 `SHADER_READ_ONLY_OPTIMAL`。
- 若作为 storage image，需要使用 `GENERAL` 或合适 layout。

---

## 8. 实现步骤

1. 定义 offscreen resource 描述。
2. 创建 `VkImage`，设置 usage。
3. 分配并绑定 memory。
4. 创建 `VkImageView`。
5. 创建 framebuffer 或 dynamic rendering attachment info。
6. 创建 / 配置写入该 offscreen 的 pipeline。
7. command buffer 中 transition 到 attachment layout。
8. 执行 offscreen pass。
9. transition 到 consumer layout。
10. 更新后续 pass descriptor。
11. 接入 resize / recreate。
12. 接入 destroy。

---

## 9. Android 注意点

- 如果 offscreen 与屏幕尺寸相关，rotation 后必须重建。
- 高分辨率 offscreen 会增加移动端 bandwidth。
- 多 offscreen pass 可能触发 tile resolve。
- AGI 需要检查 render target load/store 和 bandwidth。
- pause / resume 后避免旧 image view 被继续使用。

---

## 10. 验证方式

- [ ] Validation clean。
- [ ] RenderDoc / AGI 能看到 offscreen render target 内容。
- [ ] 后续 pass 能正确读取。
- [ ] resize 后 offscreen 尺寸正确。
- [ ] 没有旧 descriptor 引用。
- [ ] frame time 可接受。

---

## 11. 常见失败模式

1. usage 缺少 `SAMPLED`。
2. layout transition 不完整。
3. framebuffer 尺寸不匹配。
4. offscreen format 与 pipeline 不匹配。
5. resize 后 descriptor 未更新。
6. 移动端多 pass bandwidth 高。
7. depth image 未同步重建。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/07_rendering/render_pass.md`
- `../../03_api_manual/07_rendering/dynamic_rendering.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`

# Workflow: Add Fullscreen Pass

## 0. 适用范围

### 适用

- 新增 fullscreen triangle / fullscreen quad pass。
- 实现后处理：blur、bloom、tone mapping、color grading、distortion、flow light。
- 从一个 color image 读取，输出到 swapchain 或 offscreen image。

### 不适用

- 纯 compute image processing。
- 需要 mesh / scene geometry 的 pass。
- 只新增 UI overlay，不采样 Vulkan image。

---

## 1. 任务目标

新增一个 fullscreen pass：

```text
Input Color Image
→ Sampled Descriptor
→ Fullscreen Graphics Pipeline
→ Draw Fullscreen Triangle
→ Output Render Target
```

---

## 2. 输入条件

需要确认：

- 输入 image 来源：swapchain / offscreen / previous pass。
- 输出目标：swapchain image / offscreen image。
- 是否使用 RenderPass 还是 Dynamic Rendering。
- 输入 image 当前 layout。
- 输出 image 目标 layout。
- 是否随 swapchain 尺寸变化。
- fragment shader 输入资源数量。

---

## 3. 前置检查

- [ ] 当前 renderer 能 clear color。
- [ ] shader 编译链路可用。
- [ ] 输入 image 有 `SAMPLED` usage。
- [ ] 输出 image 有 `COLOR_ATTACHMENT` usage。
- [ ] descriptor 管理可用。
- [ ] RenderDoc / AGI 可抓帧。

---

## 4. Vulkan 对象链路

```text
Input Image
→ ImageView
→ Sampler
→ DescriptorSetLayout
→ DescriptorSet
→ PipelineLayout
→ Fullscreen Graphics Pipeline
→ CommandBuffer
→ Output Render Target
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| input image | `VkImage` | `SAMPLED` | previous pass 输出 | 视来源而定 |
| input image view | `VkImageView` | sampled view | 跟随 input image | 视来源而定 |
| sampler | `VkSampler` | texture sampling | renderer 生命周期 | 否 |
| output image | `VkImage` | `COLOR_ATTACHMENT` | 当前 pass 输出 | 通常是 |
| descriptor set | `VkDescriptorSet` | sampled image binding | per-pass / per-frame | 视资源而定 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | Combined Image Sampler | input image view + sampler | Fragment |

Pipeline 状态：

- vertex shader 可使用 fullscreen triangle。
- fragment shader 采样 input texture。
- depth test 通常关闭。
- viewport / scissor 匹配输出 render target。
- color attachment format 必须匹配输出。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| previous pass color write | input image | `COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fullscreen fragment read |
| fullscreen fragment write | output image | `COLOR_ATTACHMENT_OPTIMAL` → next layout | next pass / present |

必须说明：

- producer stage：`COLOR_ATTACHMENT_OUTPUT`
- producer access：`COLOR_ATTACHMENT_WRITE`
- consumer stage：`FRAGMENT_SHADER`
- consumer access：`SHADER_SAMPLED_READ`
- descriptor imageLayout：应与 shader read layout 一致

---

## 8. 实现步骤

1. 新增 fullscreen shader。
2. 创建 input sampler，如没有。
3. 创建 descriptor set layout。
4. 创建 pipeline layout。
5. 创建 graphics pipeline。
6. 为 input image 创建 / 获取 image view。
7. 分配并更新 descriptor set。
8. 在 command buffer 中插入 input image barrier。
9. begin render pass / dynamic rendering。
10. bind pipeline。
11. bind descriptor set。
12. draw fullscreen triangle。
13. end rendering。
14. 插入 output image 后续使用 barrier。
15. 接入 resize / recreate 路径。
16. 接入 destroy 路径。

---

## 9. Android 注意点

- 输入 / 输出 image 若与 swapchain 尺寸相关，rotation 后必须重建。
- Descriptor 若引用旧 offscreen image，swapchain recreate 后必须更新。
- 使用 AGI 查看 fullscreen pass 成本。
- 移动端关注 full-screen sampling、bandwidth、tile resolve。
- pause / resume 后资源生命周期要稳定。

---

## 10. 验证方式

- [ ] Validation clean。
- [ ] RenderDoc / AGI 能看到 fullscreen draw。
- [ ] input texture 绑定正确。
- [ ] output render target 有内容。
- [ ] layout transition 正确。
- [ ] resize 后 descriptor 指向新资源。
- [ ] frame time 在预期范围内。

---

## 11. 常见失败模式

1. input image 没有 `SAMPLED` usage。
2. descriptor imageLayout 和实际 layout 不一致。
3. 忘记 color attachment → shader read barrier。
4. output format 和 pipeline color attachment format 不匹配。
5. viewport / scissor 仍是旧尺寸。
6. resize 后 descriptor 仍引用旧 image view。
7. 移动端 pass 过多导致 bandwidth 高。

---

## 12. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/sampler.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`

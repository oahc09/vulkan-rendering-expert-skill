# Case: Transfer To Shader Missing Transition

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 同步 / Image Layout / Transfer / Shader Read |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

纹理资源通过 staging buffer 上传后，在 shader 中采样结果全黑、颜色异常或读取到未定义内容。App 通常不 crash，但贴图显示错误；部分驱动上可能出现画面撕裂或随机像素。

- RenderDoc 中 staging buffer 写入操作存在，目标 image 也有数据，但后续 shader pass 采样异常。
- 问题在上传完成后第一次使用 image 时最明显。

---

## 2. 初始上下文

- 使用 graphics pipeline，通过 combined image sampler 采样纹理。
- Texture 数据通过 staging buffer + `vkCmdCopyBufferToImage` 上传。
- 上传命令与后续渲染命令可能在同一 command buffer，也可能分属不同 submit。
- 可能使用 transfer queue 与 graphics queue 分离的架构。
- 多 frame-in-flight 或每帧动态更新纹理时风险更高。

---

## 3. 初始误判

最初容易怀疑：

```text
纹理文件没加载；
staging buffer 数据为空；
copy 命令写错区域；
sampler 或 image view 创建错误；
shader 采样坐标错误；
mipmap 没生成。
```

但 RenderDoc 中 copy 操作已完成，image 内容可见；后续 pass 的 descriptor 也指向正确 image view。最终发现 image 在上传后仍停留在 `TRANSFER_DST_OPTIMAL` 或 `PREINITIALIZED` layout，没有转换到 `SHADER_READ_ONLY_OPTIMAL`。

---

## 4. 排查路径

1. 检查 Validation Layer 是否报 layout mismatch `[TOOL]`。
2. 在 RenderDoc / AGI 中查看 copy 操作后的 image layout `[TOOL]`。
3. 确认 copy 命令使用的 image layout 为 `TRANSFER_DST_OPTIMAL` `[SPEC]`。
4. 检查 copy 命令之后、shader 采样之前是否有 image memory barrier `[ENGINE]`。
5. 确认 barrier 的 `oldLayout` 与 copy 时使用的 layout 一致 `[SPEC]`。
6. 确认 barrier 的 `newLayout` 为 `SHADER_READ_ONLY_OPTIMAL` `[SPEC]`。
7. 检查 descriptor imageLayout 是否也填写为 `SHADER_READ_ONLY_OPTIMAL` `[SPEC]`。
8. 若使用 transfer queue 单独上传，检查 queue family ownership transfer `[SPEC]`。

---

## 5. 关键证据

### Validation Layer

可能出现：

- `VUID-vkCmdDrawIndexed-None-02699` / `VUID-vkCmdDraw-None-02699`：descriptor image layout 与实际 layout 不匹配。
- `VUID-vkCmdCopyBufferToImage-dstImageLayout-00181`：copy 时 dstImageLayout 非法。
- `UNASSIGNED-CoreValidation-DrawState-InvalidImageLayout`：image layout 与 pipeline 期望不一致 `[TOOL]`。
- Synchronization hazard 警告：transfer write 与 shader read 之间缺少 barrier `[TOOL]`。

### RenderDoc / AGI

观察到：

- `vkCmdCopyBufferToImage` 成功执行，目标 image 有数据。
- Copy 后 image 的当前 layout 为 `TRANSFER_DST_OPTIMAL`。
- 后续 draw call 的 descriptor imageLayout 填写为 `SHADER_READ_ONLY_OPTIMAL`。
- Draw call 前后没有 image memory barrier 完成 layout transition。

### Log / Code

返回值：

- `vkQueueSubmit` 返回 `VK_SUCCESS`。
- `vkCmdCopyBufferToImage` 返回 void，但 image layout 未改变。

关键代码：

```text
// 错误示例：缺少 transfer write → shader read 的 barrier
vkCmdCopyBufferToImage(cmd, stagingBuffer, textureImage,
    VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &region);

// 直接开始渲染，没有 transition
vkCmdBeginRenderPass(cmd, &rpBegin, VK_SUBPASS_CONTENTS_INLINE);
// shader 采样 textureImage
```

---

## 6. 根因

根因：staging buffer 通过 `vkCmdCopyBufferToImage` 向 image 写入数据后，没有通过 image memory barrier 将 image 从 `TRANSFER_DST_OPTIMAL` 转换到 `SHADER_READ_ONLY_OPTIMAL`，导致 fragment shader 采样时读取到 layout 不匹配的无效内容。

---

## 7. 修复方案

### 最小修复

在 `vkCmdCopyBufferToImage` 之后、shader 使用之前插入 image memory barrier：

```text
srcStage  = TRANSFER
srcAccess = TRANSFER_WRITE
oldLayout = TRANSFER_DST_OPTIMAL

dstStage  = FRAGMENT_SHADER
dstAccess = SHADER_SAMPLED_READ
newLayout = SHADER_READ_ONLY_OPTIMAL
```

若后续 consumer 是 compute shader，则 `dstStage = COMPUTE_SHADER`，`dstAccess = SHADER_SAMPLED_READ`。

### 稳定修复

- 为每个 image 维护当前 layout 状态机。
- 在 copy / blit / render / compute 使用前自动检查并插入必要 transition。
- descriptor imageLayout 从 image 当前 layout 推导，避免手填错误。
- 对 mipmap generation 链路上的多次 layout 变化统一处理。

### 工程化修复

- 建立 RenderGraph，自动根据 producer 和 consumer 推导 layout 与 barrier。
- 在 command buffer recorder 中加入 layout assertion，发现不一致立即触发 debug break。
- 对 transfer queue / graphics queue 分离的架构，封装 queue family ownership transfer。
- CI 中跑 RenderDoc capture 自动化检查 image layout transition 是否完整。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 copy 后 image layout 成功变为 `SHADER_READ_ONLY_OPTIMAL`。
- [ ] Shader 采样结果与源纹理一致。
- [ ] 多帧运行稳定，无 flicker 或随机黑块。
- [ ] 动态更新纹理时每帧都有正确的 transition。
- [ ] Transfer queue 与 graphics queue 分离时结果仍正确。

---

## 9. 经验抽象

凡是 image 被 staging buffer 上传后交给 shader 使用，必须同时满足：

```text
usage 包含 TRANSFER_DST + SAMPLED
upload时使用 TRANSFER_DST_OPTIMAL
上传后必须 transition 到 SHADER_READ_ONLY_OPTIMAL
descriptor imageLayout 与实际 layout 一致
barrier 的 subresource range 覆盖被采样层级
```

Layout transition 不是“可选优化”，而是 image 跨用途使用的必要步骤。

---

## 10. 预防规则

1. 每个 texture upload 必须成对出现：copy / blit + transition to shader read。
2. 不允许 copy 后直接采样，必须经 barrier 转换 layout。
3. Descriptor imageLayout 必须从 image 当前状态自动获取，禁止硬编码。
4. 每个 image 必须跟踪当前 layout，并在 debug 构建中校验。
5. 使用 transfer queue 上传时，必须处理 queue family ownership transfer。
6. 生成 mipmap 时，每级 blit 的 layout 转换必须完整。
7. 新增贴图加载流程必须走统一的 upload + transition helper。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

## 13. 关联 Workflow

- `../../05_workflows/05_resource_management/add_texture_resource.md`
- `../../05_workflows/02_render_pass_effects/add_texture_sampling_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`

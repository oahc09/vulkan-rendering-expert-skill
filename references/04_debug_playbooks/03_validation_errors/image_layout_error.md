# Debug Playbook: Image Layout Error

## 0. 适用范围

### 适用

- Validation 报 image layout mismatch。
- texture 采样为黑色。
- attachment 写入后下一个 pass 读不到。
- compute 写 storage image 后 graphics 采样异常。
- transfer 上传后 shader 采样异常。

### 不适用

- descriptor binding 本身错误。
- image 数据上传内容错误但 layout 正确。
- shader 坐标错误导致采样区域不对。

---

## 1. 现象

常见表现：

- Validation 提到 `imageLayout`、`oldLayout`、`newLayout`。
- RenderDoc 中 image 内容存在，但 shader 采样为黑。
- 后处理 pass 输入为空。
- compute output 没有被 graphics 正确读取。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | producer pass 后没有 barrier | 上一 pass 写，下一 pass 读异常 | Image / Barrier |
| P0 | descriptor imageLayout 填错 | VUID 提到 descriptor layout | Descriptor / Image |
| P0 | oldLayout / newLayout 错误 | VUID 提到 transition 不匹配 | ImageMemoryBarrier |
| P1 | stage/access 不匹配真实访问 | sync validation 报 hazard | Barrier |
| P1 | usage flag 不支持当前用途 | VUID 提到 usage | Image |
| P2 | subresource range 错误 | mip / layer / aspect 不匹配 | ImageView / Barrier |

---

## 3. 快速验证路径

1. 找 image 的所有使用点。
2. 标记每个 pass 是 producer 还是 consumer。
3. 检查每次使用时期望 layout。
4. 检查 barrier 的 oldLayout / newLayout。
5. 检查 descriptor imageLayout。
6. 用 RenderDoc 看 pass 前后 image 状态和内容。

---

## 4. Vulkan 对象链路排查

```text
VkImage
→ Usage Flags
→ VkImageView
→ Producer Pass
→ Image Memory Barrier
→ Layout Transition
→ Descriptor / Attachment
→ Consumer Pass
```

重点检查：

- Image 创建时 usage 是否覆盖所有用途。
- ImageView aspect/mip/layer 是否正确。
- Attachment layout 或 dynamic rendering layout 是否正确。
- Descriptor 中填写的 imageLayout 是否和实际使用一致。
- barrier 是否覆盖正确 subresource range。
- producer stage/access 和 consumer stage/access 是否匹配。

---

## 5. 高频根因

1. `COLOR_ATTACHMENT_OPTIMAL` 后直接 shader sampled，没有 transition 到 `SHADER_READ_ONLY_OPTIMAL`。
2. transfer 上传后没有 transition 到 shader read。
3. compute 写 storage image 后 fragment 采样没有 barrier。
4. descriptor imageLayout 写死但实际 layout 已变化。
5. depth image aspectMask 错误。
6. mip level / array layer barrier 只覆盖部分资源。
7. oldLayout 写成错误状态，导致 transition 无法表达真实状态。

---

## 6. 修复方案

### 最小修复

- 明确 producer / consumer。
- 补充 image memory barrier。
- 修正 descriptor imageLayout。
- 修正 subresource range。

### 稳定修复

- 建立资源状态跟踪。
- 建立 render graph 自动插入 barrier。
- 为每个 pass 声明 input/output layout。
- 对 image usage 和 layout 建立 debug assertion。

---

## 7. 回归验证

- [ ] Validation 不再报 image layout 相关错误。
- [ ] RenderDoc 中 pass 输入输出正确。
- [ ] 后处理链路正常。
- [ ] compute output 能被 graphics 正确读取。
- [ ] resize / recreate 后 layout 逻辑仍正确。

---

## 8. 相关 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/07_rendering/render_target_layout.md`

---

## 9. 工具证据

### Validation Layer

关注：

- layout mismatch
- descriptor imageLayout
- attachment layout
- synchronization hazard

### RenderDoc / AGI

关注：

- pass 前后 texture 内容。
- render target 输出。
- sampled image 是否有内容。
- storage image 是否写入成功。

---

## 10. Android 分支

Android 上额外检查：

1. swapchain image layout 是否正确进入 present。
2. rotation 后新 swapchain image 是否重新建立 layout 流程。
3. offscreen render target 是否跟随尺寸重建。
4. old image view 是否仍被 descriptor 引用。

---

## 11. 不确定时如何处理

需要补充：

- image 创建 usage
- image view 创建参数
- producer pass
- consumer pass
- barrier 代码
- descriptor image info
- Validation message / VUID

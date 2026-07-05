# Case: Storage Image Layout Wrong

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Storage Image / Layout |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Compute shader 对 storage image 进行读写后，内容没有变化、出现黑色、颜色错乱，或 Validation Layer 报错提示 descriptor image layout 与实际 layout 不匹配。问题只在 compute pass 访问 storage image 时出现，普通 sampled image 正常。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 compute pipeline 写入或读取 storage image。
- Storage image 的 usage 包含 `VK_IMAGE_USAGE_STORAGE_BIT`。
- Descriptor 类型为 `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE`。
- 可能从 graphics pass 输出的 image 直接作为 compute 输入，或 compute 输出后由 graphics 采样。

---

## 3. 初始误判

最初容易怀疑：

```text
compute shader 坐标转换错误；
descriptor binding 或 image view 错误；
storage image 的 format 不支持 compute 读写；
compute 与 graphics 之间缺少 barrier；
image 没有 `VK_IMAGE_USAGE_STORAGE_BIT`。
```

但 usage 和 descriptor 都正确，barrier 也存在。最终发现 storage image 在 dispatch 时仍处于 `SHADER_READ_ONLY_OPTIMAL` 或 `COLOR_ATTACHMENT_OPTIMAL`，而 compute 读写 storage image 要求 `VK_IMAGE_LAYOUT_GENERAL`（或 implementation-defined 的 storage 兼容 layout）。

---

## 4. 排查路径

1. 检查 descriptor update 中 `VkDescriptorImageInfo.imageLayout` 是否设置为 `VK_IMAGE_LAYOUT_GENERAL`。
2. 检查 compute dispatch 前是否插入了将 storage image transition 到 `GENERAL` 的 image memory barrier。
3. 检查 barrier 的 `srcAccess` / `dstAccess` / `srcStage` / `dstStage` 是否覆盖 compute shader 的读写。
4. 在 RenderDoc 中查看 storage image 在 dispatch 时刻的实际 layout。
5. 检查 graphics pass 输出到 compute 输入的 layout transition 是否完整。
6. 检查同一 image 在被 graphics 采样前是否已从 `GENERAL` transition 回 `SHADER_READ_ONLY_OPTIMAL`。

---

## 5. 关键证据

### Validation Layer

- 典型 VUID（`[SPEC]`）：
  - `VUID-vkCmdDispatch-None-02699`：descriptor image layout 必须与 image 当前实际 layout 一致。
  - `VUID-VkDescriptorImageInfo-imageLayout-00344`：`STORAGE_IMAGE` descriptor 的 `imageLayout` 必须是 `VK_IMAGE_LAYOUT_GENERAL` 或 `VK_IMAGE_LAYOUT_SHARED_PRESENT_KHR`。
  - `VUID-vkCmdDispatch-None-02697`：storage image 的 image layout 不兼容其 descriptor type。

### RenderDoc / AGI

- 观察到：
  - Bound Resources 中 storage image descriptor 的 layout 显示为 `SHADER_READ_ONLY_OPTIMAL` 或 `COLOR_ATTACHMENT_OPTIMAL`。
  - Texture Viewer 中 storage image 在 dispatch 前后的内容无变化。
  - Image layout 时间线显示 dispatch 时 image 未进入 `GENERAL`。
- 关键 resource：storage image、`VkDescriptorImageInfo`、image memory barrier。

### Log / Code

- 返回值：
  - `vkUpdateDescriptorSets` 和 `vkQueueSubmit` 通常返回 `VK_SUCCESS`。
  - Validation Layer 会报告 layout mismatch 相关消息。
- 关键代码：

```text
// 错误示例 1：descriptor imageLayout 未设为 GENERAL
VkDescriptorImageInfo imageInfo{};
imageInfo.imageView = storageImageView;
imageInfo.imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL; // 错误：storage image 需要 GENERAL
imageInfo.sampler = VK_NULL_HANDLE;

// 错误示例 2：缺少 transition 到 GENERAL 的 barrier
vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, computePipeline);
vkCmdDispatch(cmd, groupsX, groupsY, 1); // 此时 image 仍是 COLOR_ATTACHMENT_OPTIMAL
```

---

## 6. 根因

根因：storage image 在 compute shader 访问前没有 transition 到 `VK_IMAGE_LAYOUT_GENERAL`，或 descriptor 更新时 `imageLayout` 未设置为 `VK_IMAGE_LAYOUT_GENERAL`，导致 compute 读写行为未定义或被验证层拦截。

---

## 7. 修复方案

### 最小修复

- 在 compute dispatch 前插入 image memory barrier，将 storage image 从当前 layout transition 到 `VK_IMAGE_LAYOUT_GENERAL`：

```text
oldLayout = COLOR_ATTACHMENT_OPTIMAL / SHADER_READ_ONLY_OPTIMAL
newLayout = GENERAL
srcStage  = COLOR_ATTACHMENT_OUTPUT / FRAGMENT_SHADER
srcAccess = COLOR_ATTACHMENT_WRITE / SHADER_SAMPLED_READ
dstStage  = COMPUTE_SHADER
dstAccess = SHADER_STORAGE_READ / SHADER_STORAGE_WRITE
```

- 更新 descriptor 时，将 `VkDescriptorImageInfo.imageLayout` 显式设为 `VK_IMAGE_LAYOUT_GENERAL`。
- compute 写完后如需被 graphics 采样，再 transition 回 `SHADER_READ_ONLY_OPTIMAL`。

### 稳定修复

- 为 storage image 维护当前 layout 状态机；compute pass 使用前自动 transition 到 `GENERAL`。
- descriptor update 辅助函数根据 descriptor type 自动填充 `imageLayout`，避免手动填写错误。
- 在 compute pass 描述中声明 input / output layout，由系统生成 barrier。

### 工程化修复

- 使用 RenderGraph / FrameGraph 自动推导 storage image 的 layout 和 barrier。
- 在 debug build 中增加断言：storage image descriptor 的 imageLayout 必须为 `GENERAL`。
- CI 中加入 compute-graphics 互操作测试，验证 layout transition 链完整。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 storage image descriptor layout 为 `GENERAL`。
- [ ] Compute dispatch 后 storage image 内容按 shader 逻辑更新。
- [ ] Compute 输出被 graphics pass 采样时，layout 已 transition 回 `SHADER_READ_ONLY_OPTIMAL`。
- [ ] 多帧运行稳定，无撕裂或内容错乱。
- [ ] resize / swapchain recreate 后 storage image layout 状态正确。

---

## 9. 经验抽象

Storage image 是特殊的 image 使用方式，其 descriptor imageLayout 和实际 image layout 都必须是 `VK_IMAGE_LAYOUT_GENERAL`（或驱动允许的 storage 兼容 layout）：

```text
storage image descriptor imageLayout = GENERAL
actual image layout before dispatch = GENERAL
barrier dstStage = COMPUTE_SHADER
barrier dstAccess = SHADER_STORAGE_READ | SHADER_STORAGE_WRITE
```

不要把它当作普通 sampled image 处理；也不要认为 barrier 只存在于 compute 和 graphics 之间，compute 使用前的 layout transition 同样关键。

---

## 10. 预防规则

1. `VK_DESCRIPTOR_TYPE_STORAGE_IMAGE` 的 descriptor imageLayout 必须设置为 `VK_IMAGE_LAYOUT_GENERAL`。
2. Compute dispatch 前必须将 storage image 通过 barrier transition 到 `VK_IMAGE_LAYOUT_GENERAL`。
3. Compute 写完后若被 graphics 采样，必须再 transition 回 `SHADER_READ_ONLY_OPTIMAL`。
4. 不要对 storage image 使用 `COLOR_ATTACHMENT_OPTIMAL` 或 `SHADER_READ_ONLY_OPTIMAL` 作为 compute 读写时的 layout。
5. 在 descriptor update 和 dispatch 前增加 debug 断言，检查 storage image layout 是否为 `GENERAL`。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_graphics_sync_error.md`
- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`

---

## 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/compute_write_storage_image.md`
- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`

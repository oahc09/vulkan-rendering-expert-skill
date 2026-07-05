# Case: Black Screen Caused by Missing Image Layout Transition

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Image Layout / 后处理 |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

App 正常运行，无 crash。  
clear color 可见，但新增 fullscreen 后处理 pass 后画面变黑。  
RenderDoc 中可以看到 draw call，pipeline 也绑定成功，但 fragment shader 采样 input texture 后输出为黑色。

---

## 2. 初始上下文

- 平台：Android / Desktop 均可能发生。
- 使用 Vulkan graphics pipeline。
- 前一个 pass 输出到 offscreen color image。
- 后一个 pass 通过 combined image sampler 采样该 offscreen image。
- 使用多 pass 后处理链路。
- 可能使用 RenderPass 或 Dynamic Rendering。

---

## 3. 初始误判

最初容易怀疑：

```text
fragment shader 写错；
descriptor 没绑定；
sampler 创建错误；
纹理内容为空。
```

但 RenderDoc 中前一个 pass 的 offscreen image 实际有内容，descriptor 也绑定到了正确 image view。  
后续排查发现是 pass 间缺少 layout transition。

---

## 4. 排查路径

1. 检查 render loop，确认 acquire / submit / present 正常。
2. 检查 clear color，确认 swapchain 输出正常。
3. 用 RenderDoc 查看前一个 pass 输出，确认 offscreen image 有内容。
4. 查看 fullscreen pass 的 bound resource，确认 descriptor 指向该 image。
5. 检查 image 使用链路：
   ```text
   Color Attachment Write
   → Fragment Shader Sampled Read
   ```
6. 检查 barrier，发现没有从 `COLOR_ATTACHMENT_OPTIMAL` transition 到 `SHADER_READ_ONLY_OPTIMAL`。
7. 检查 descriptor imageLayout，发现填写为 shader read，但实际 image 状态仍停留在 color attachment。

---

## 5. 关键证据

### Validation Layer

可能出现：

- image layout mismatch
- descriptor imageLayout 与实际 layout 不匹配
- synchronization hazard

### RenderDoc / AGI

观察到：

- producer pass 的 render target 有正确内容。
- consumer pass 的 descriptor 绑定了该 image view。
- consumer pass 采样结果异常。
- pass 之间缺少合理的 image memory barrier。

### Log / Code

关键代码：

- offscreen image usage 有 `COLOR_ATTACHMENT` 和 `SAMPLED`。
- command buffer 中缺少 color write → shader read barrier。

---

## 6. 根因

根因：前一个 pass 以 color attachment 方式写入 offscreen image 后，没有通过 image memory barrier 将其转换为 fragment shader sampled read 所需状态，导致后续 fullscreen pass 采样到无效内容。

---

## 7. 修复方案

### 最小修复

在 producer pass 结束后、consumer pass 开始前插入 image memory barrier：

```text
srcStage  = COLOR_ATTACHMENT_OUTPUT
srcAccess = COLOR_ATTACHMENT_WRITE
oldLayout = COLOR_ATTACHMENT_OPTIMAL

dstStage  = FRAGMENT_SHADER
dstAccess = SHADER_SAMPLED_READ
newLayout = SHADER_READ_ONLY_OPTIMAL
```

### 稳定修复

- 每个 pass 显式声明 input / output layout。
- 每个 image 维护当前 layout。
- descriptor imageLayout 必须与实际 consumer layout 一致。

### 工程化修复

- 建立 RenderGraph。
- 由 RenderGraph 根据 producer / consumer 自动插入 barrier。
- 对每个 pass 的 resource state 做 debug assertion。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc 中 producer pass 输出正常。
- [ ] Consumer pass 能看到 input texture。
- [ ] Fullscreen pass 输出正常。
- [ ] 多帧运行稳定。
- [ ] resize 后仍能正确 transition。

---

## 9. 经验抽象

凡是 image 被跨 pass 使用，都必须同时检查：

```text
usage
layout
producer stage/access
consumer stage/access
descriptor imageLayout
barrier subresource range
```

不要只检查 image 创建和 descriptor 更新。

---

## 10. 预防规则

1. 每个 pass 必须声明资源读写意图。
2. 每个 image 必须有状态跟踪。
3. Descriptor imageLayout 不能和实际 layout 脱节。
4. 新增后处理 pass 时必须设计 input/output layout。
5. RenderDoc 中必须验证 pass 输入和输出。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/05_descriptor/sampled_image_descriptor.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`

---

## 13. 关联 Workflow

- `../../05_workflows/02_render_pass_effects/add_fullscreen_pass.md`
- `../../05_workflows/02_render_pass_effects/add_offscreen_render_pass.md`

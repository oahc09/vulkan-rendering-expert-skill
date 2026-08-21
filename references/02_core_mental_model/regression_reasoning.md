# Regression Reasoning：修改影响面推理

定义 Vulkan 修改的影响面推理模型：任何修改在给出方案前，先推导它沿对象链路传播的全部影响面，再决定修改范围和回归范围。

> 配套文件：`../00_expert_entry/verification_gate.md`（出口关卡）、`../07_integration_pack/regression_checklist.md`（回归清单）。

---

## 1. 核心原则

Vulkan 对象之间是强依赖链路，修改不会停留在被修改对象本身：

```text
修改一个对象
→ 兼容性约束沿链路传播（layout 兼容、尺寸匹配、格式匹配）
→ 同一条链路上的对象必须一起评估
→ 回归范围 = 影响面，而不是被修改的文件
```

---

## 2. 依赖传播规则

### 2.1 DescriptorSetLayout → PipelineLayout → Pipeline

```text
Shader set/binding 变化
→ DescriptorSetLayoutBinding 变化
→ DescriptorSetLayout 变化（pipeline layout compatibility 被破坏）
→ PipelineLayout 必须重建
→ 引用该 layout 的 Pipeline 必须重建
→ 已分配的 DescriptorSet 必须基于新 layout 重新分配
→ CommandBuffer 中绑定的 descriptor set 必须重新绑定
```

结论：改 shader 的 binding 永远不是"只改 shader"。[SPEC]

### 2.2 Image → ImageView → RenderTarget / Framebuffer

```text
Image 的 format / extent / usage / samples 变化
→ ImageView 必须重建（view 引用具体 image 属性）
→ RenderPass attachment description 必须兼容（format / samples）
→ Framebuffer 必须重建（引用 image view）
→ 采样该 image 的 descriptor imageLayout 与实际 layout 需要重新核对
```

### 2.3 Swapchain → 尺寸相关资源

```text
Swapchain extent 变化（rotation / resize / recreate）
→ swapchain image 全部更换
→ depth / offscreen image 按新 extent 重建
→ image view / framebuffer 同步重建
→ pipeline 若未使用 dynamic viewport / scissor 则需要重建
→ command buffer 需要重新录制（viewport / scissor / attachment 变化）
→ 引用旧尺寸资源的 descriptor 需要更新
```

Android 场景下 extent 可能为 0（Surface 未就绪），必须处理等待 / 跳帧逻辑。[ANDROID]

### 2.4 Frames-in-flight → per-frame 资源

```text
frames-in-flight 数量变化
→ per-frame 的 command pool / command buffer
→ per-frame 的 fence / semaphore
→ per-frame 的 uniform buffer / descriptor set
必须按新的数量成套扩展或收缩；只改数量不改资源集会导致串帧或 use-after-free。[ENGINE]
```

### 2.5 Barrier → producer / consumer

```text
Barrier 参数变化
→ producer 侧：srcStage / srcAccess / oldLayout
→ consumer 侧：dstStage / dstAccess / newLayout
两侧必须同时核对；只调整一侧会产生 hazard 或 layout mismatch。
跨 queue 场景还必须核对 semaphore（barrier 不跨 queue 生效）。[SPEC]
```

### 2.6 Surface / ANativeWindow → Swapchain

```text
Surface destroyed / replaced（Android pause / resume / rotation）
→ 旧 swapchain 失效（VK_ERROR_OUT_OF_DATE_KHR / VK_ERROR_SURFACE_LOST_KHR）
→ 等待 in-flight 完成后销毁旧 swapchain 及尺寸相关资源
→ 用新 Surface / 新 extent 重建
→ render thread 必须在 Surface 无效期间停止 present
```

---

## 3. 影响面推理流程

提出修改方案前按以下顺序推导：

1. 定位被修改对象在 `vulkan_object_chain.md` 对象链路中的位置。
2. 沿链路向下游推导所有兼容性受影响的对象（本章规则 2.1-2.6）。
3. 沿链路向上游推导所有引用该对象的对象（谁 bind / 谁 update / 谁录制）。
4. 列出必须一起重建 / 重新录制 / 重新更新的对象清单。
5. 以该清单作为回归范围，对照 `../07_integration_pack/regression_checklist.md` 选择回归项。

---

## 4. 修改前检查清单

- [ ] 影响面清单已列出（被修改对象 + 全部传播对象）。
- [ ] 兼容性约束已核对（pipeline layout compatibility / render pass compatibility / extent 匹配）。
- [ ] 重建顺序已定义（先创建新对象，再销毁旧对象，中间等待 in-flight）。
- [ ] per-frame 资源是否需要成套变化已评估。
- [ ] 同步两侧（producer / consumer）是否需要同步调整已评估。
- [ ] Android 场景下 rotation / pause / resume / Surface recreate 的影响已评估。

---

## 5. 常见遗漏

1. 改 descriptor layout 后忘记重建 pipeline。[ENGINE]
2. swapchain recreate 后 offscreen / depth 资源仍为旧尺寸。[ENGINE]
3. 改 barrier 只改了一侧 stage / access。[SPEC]
4. 改 frames-in-flight 数量后 per-frame 资源没有成套扩展。[ENGINE]
5. 销毁旧资源前没有等待 in-flight fence。[SPEC]

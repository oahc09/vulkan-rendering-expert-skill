# Render Target 模型

## 核心思想

Render Target 不是一张简单图片，而是由 image、image view、usage、layout、load/store、pass 关系共同决定。

核心模型：

```text
Render Target Image
→ ImageView
→ Attachment Usage
→ Layout
→ Load / Store
→ Render Commands
→ Final Layout / Barrier
→ Next Pass Consumer
```

## Render Target Image

一个 image 要作为 render target，通常要满足：

1. format 支持 attachment。
2. usage 包含 COLOR_ATTACHMENT 或 DEPTH_STENCIL_ATTACHMENT。
3. 创建对应 ImageView。
4. 渲染时处于合适 layout。
5. 如果后续要采样，usage 还要包含 SAMPLED。

## 传统 Render Pass 路径

```text
VkRenderPass
→ VkFramebuffer
→ Attachment Description
→ Subpass
→ vkCmdBeginRenderPass
→ Draw
→ vkCmdEndRenderPass
```

关注点：

1. attachment format 是否和 image view 匹配。
2. loadOp / storeOp 是否符合预期。
3. initialLayout / finalLayout 是否正确。
4. framebuffer image view 是否来自当前 swapchain / offscreen image。
5. swapchain recreate 后 framebuffer 必须重建。

## Dynamic Rendering 路径

```text
VkRenderingInfo
→ VkRenderingAttachmentInfo
→ vkCmdBeginRendering
→ Draw
→ vkCmdEndRendering
```

特点：

1. 不需要提前创建 VkRenderPass / VkFramebuffer。
2. 在 begin rendering 时指定 attachment。
3. 仍然需要 image、image view、layout、load/store、pipeline rendering info。
4. 仍然需要处理 pass 间 barrier。

## Offscreen Pass 模型

```text
Offscreen Color Image
→ COLOR_ATTACHMENT_OPTIMAL 写入
→ Barrier
→ SHADER_READ_ONLY_OPTIMAL 采样
→ Fullscreen Composite Pass
```

典型用途：

1. Bloom。
2. Blur。
3. Tone Mapping。
4. SSR / SSAO。
5. 后处理合成。

## 高频错误

1. image usage 缺少 COLOR_ATTACHMENT 或 SAMPLED。
2. ImageView format / aspect 错误。
3. RenderPass attachment format 与 swapchain format 不匹配。
4. Dynamic Rendering 下 pipeline rendering info 与实际 attachment 不匹配。
5. offscreen image 写入后没有 barrier 就采样。
6. swapchain recreate 后 framebuffer / image view 没有重建。
7. depth attachment 尺寸与 color attachment 不一致。

## 专家规则

```text
Dynamic Rendering 简化了 RenderPass / Framebuffer，但没有取消 Render Target 心智模型。
任何 pass 都必须明确：写入哪个 image，以什么 layout 写，后续谁读，如何同步。
```

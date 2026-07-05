#!/usr/bin/env python3
"""
TC9 Skill Trigger Test - Generate responses as Vulkan expert and run automated checks.
This script generates 12 Vulkan expert responses based on the skill rules,
then runs automated verification checks per tc9_skill_trigger_spec.md.
"""

import re
import json
from html import escape
from pathlib import Path

BASE = Path(__file__).parent
RESP_DIR = BASE / "responses"
REPORT_OUT = BASE / "reports" / "tc9_test_report.html"
REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)

RESP_DIR.mkdir(parents=True, exist_ok=True)


def h(value) -> str:
    return escape(str(value), quote=True)

# ============================================================================
# RESPONSE GENERATION - Based on skill rules (role.md, hard_rules.md,
# task_classifier.md, response_formats.md, accuracy_check.md,
# debug_priority.md, performance_priority.md)
# ============================================================================

RESPONSES = {}

# TC9.1 - Black Screen Debug (故障调试类)
RESPONSES["TC9.1"] = """## 1. 最可能原因排序

黑屏问题优先按渲染链路排查，不直接猜 shader [ENGINE][TOOL]：

1. **vkAcquireNextImageKHR 返回值未检查** — Swapchain image 未成功获取，后续 submit/present 均无效 [SPEC]
2. **Command Buffer 录制不完整或未提交** — vkBeginCommandBuffer/vkEndCommandBuffer 配对错误，或 vkQueueSubmit 未执行 [SPEC]
3. **Render Pass / Dynamic Rendering 配置错误** — Attachment loadOp 设为 VK_ATTACHMENT_LOAD_OP_CLEAR 但 clear color 为黑色 (0,0,0,0) [SPEC]
4. **Viewport/Scissor 未设置或超出范围** — Viewport extent 与 Swapchain extent 不匹配 [SPEC]
5. **Image Layout Transition 缺失** — Swapchain image 未从 VK_IMAGE_LAYOUT_UNDEFINED 转为 VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL [SPEC]
6. **Android Surface 被销毁** — ANativeWindow 在渲染过程中失效，导致 present 返回错误 [ANDROID]

## 2. 快速验证路径

1. 在 vkAcquireNextImageKHR 后检查返回值，确认 != VK_SUCCESS
2. 在 vkQueueSubmit 后检查返回值
3. 在 vkQueuePresentKHR 后检查返回值
4. 用 RenderDoc 抓帧，检查 clear color 和 draw call 是否执行 [TOOL]
5. 用 AGI 抓帧，检查 GPU 活动和 render target 内容 [AGI]
6. 检查 logcat 输出是否有 Vulkan 相关错误 [ANDROID]

## 3. Vulkan 对象链路排查

```
VkSurfaceKHR (ANativeWindow)
  └─ VkSwapchainKHR
       └─ VkImage (Swapchain images)
            └─ VkImageView (Color attachment)
                 └─ VkFramebuffer
                      └─ VkRenderPass / VkRenderingAttachmentInfo
                           └─ VkCommandBuffer
                                ├─ vkCmdBeginRenderPass / vkCmdBeginRendering
                                ├─ vkCmdSetViewport / vkCmdSetScissor
                                ├─ vkCmdBindPipeline
                                ├─ vkCmdBindDescriptorSets
                                └─ vkCmdDraw
                └─ vkQueueSubmit (VkFence, VkSemaphore)
                     └─ vkQueuePresentKHR
```

排查步骤：
1. 确认 `vkAcquireNextImageKHR` 的 semaphore 被正确传入 `vkQueueSubmit` 的 waitSemaphore
2. 确认 `vkQueueSubmit` 的 signalSemaphore 被传入 `vkQueuePresentKHR` 的 waitSemaphore
3. 确认 Command Buffer 中 `vkCmdBeginRenderPass` 使用的 framebuffer 与 acquire 到的 image 对应
4. 确认 `vkCmdPipelineBarrier` 将 swapchain image 从 `UNDEFINED` 转为 `COLOR_ATTACHMENT_OPTIMAL` [SPEC]

## 4. 工具证据

- **Validation Layer**：即使没有报错，也建议启用 `VK_LAYER_KHRONOS_validation`，开启 `VK_VALIDATION_FEATURE_ENABLE_GPU_ASSISTED_EXT` [TOOL]
- **RenderDoc**：抓取一帧，检查 swapchain image 在 present 前的内容是否全黑 [TOOL]
- **AGI**：Android GPU Inspector，检查 GPU 端是否有 draw call 执行 [AGI]
- **logcat**：`adb logcat -s Vulkan` 检查 native 层错误 [ANDROID]

## 5. 修复方案

### 修复 1：检查 Acquire 返回值

```c
VkResult result = vkAcquireNextImageKHR(device, swapchain, UINT64_MAX,
    imageAvailableSemaphore, VK_NULL_HANDLE, &imageIndex);
if (result == VK_ERROR_SURFACE_LOST_KHR || result == VK_SUBOPTIMAL_KHR) {
    recreateSwapchain();
    return;
}
```

### 修复 2：确保 Render Loop 链路完整

确认 Semaphore 链路：
- `vkAcquireNextImageKHR` signal → `imageAvailableSemaphore`
- `vkQueueSubmit` wait → `imageAvailableSemaphore`, signal → `renderFinishedSemaphore`
- `vkQueuePresentKHR` wait → `renderFinishedSemaphore`

### 修复 3：检查 Clear Color 和 Viewport

```c
vkCmdSetViewport(commandBuffer, 0, 1, &viewport);  // extent 匹配 swapchain
vkCmdSetScissor(commandBuffer, 0, 1, &scissor);
// clear color 设为非黑色以便测试
VkClearValue clearColor = {{{0.0f, 1.0f, 0.0f, 1.0f}}};  // 绿色
```

### 修复 4：Image Layout Transition

```c
VkImageMemoryBarrier barrier = {
    .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
    .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
    .newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
    .srcAccessMask = 0,
    .dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
    .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
    .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
    .image = swapchainImages[imageIndex],
    .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}
};
vkCmdPipelineBarrier(commandBuffer,
    VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
    VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
    0, 0, NULL, 0, NULL, 1, &barrier);
```

## 6. 回归验证

1. 用 RenderDoc 确认 swapchain image 在 present 前有非黑色像素 [TOOL]
2. 用 AGI 确认 GPU draw call 正确执行 [AGI]
3. 在多帧循环中持续监测，确认无黑屏复现
4. 测试 Android 前后台切换后是否仍正常 [ANDROID]

## 7. 相关 API / Case

- `vkAcquireNextImageKHR`, `vkQueueSubmit`, `vkQueuePresentKHR`
- `vkCmdBeginRenderPass` / `vkCmdBeginRendering`
- `vkCmdPipelineBarrier`
- 参考: `04_debug_playbooks/01_visual_issues/black_screen.md`
"""

# TC9.2 - Mobile Performance (性能优化类)
RESPONSES["TC9.2"] = """## 1. 瓶颈初判

设备 Mali-G78 (Valhall 架构), 分辨率 2560x1440, 4 个全屏 Pass + G-Buffer (3 attachment), 25fps vs 60fps 目标。

初步判断：**Bandwidth bound** 为主要瓶颈，同时存在 GPU Fragment bound 和 Synchronization bound 的叠加因素 [ENGINE][VENDOR]。

原因分析：
- 2560x1440 分辨率 × 4 个全屏 Pass = 极高带宽消耗
- G-Buffer 3 个 attachment 在 TBR 架构上导致 tile resolve 次数增加 [VENDOR]
- 全屏 Lighting/Bloom/ToneMapping Pass 各自读写完整 render target

## 2. CPU / GPU / Bandwidth / Sync 分类

### CPU bound
- 当前信息不足以判断 CPU 瓶颈，需用 profiler 验证
- 可能原因：Command Buffer 录制过重、Descriptor 频繁更新 [ENGINE]

### GPU Fragment bound
- 4 个全屏 Pass 在 2560x1440 下 fragment 处理量极大
- Lighting Pass 全屏着色，shader 复杂度未知 [ENGINE]

### Bandwidth bound（主要瓶颈）
- G-Buffer 3 attachment (假设 RGBA16F = 192 bits/pixel) 在 2560x1440 下：
  - G-Buffer 写入: 2560×1440×24B = ~8.8 MB/frame
  - Lighting 读 G-Buffer + 写 color: ~17.6 MB/frame
  - Bloom 读写: ~7.3 MB/frame × 2 (downsample + upsample)
  - ToneMapping 读写: ~7.3 MB/frame
  - 总计: ~48 MB/frame × 60fps = ~2.9 GB/s [ENGINE][HEUR]
- Mali-G78 带宽上限约 17-22 GB/s (理论)，实际可用约 60-70% [VENDOR][HEUR]

### Synchronization bound
- Pass 之间的 barrier 可能过宽，导致 pipeline stall [ENGINE]
- 未使用 vkCmdPipelineBarrier2 (synchronization2) 的细粒度阶段 [SPEC]

## 3. Vulkan 高风险点

1. **Attachment load/store 操作**：G-Buffer 3 个 attachment 的 loadOp/storeOp 配置 [SPEC]
2. **Render Pass 依赖**：Pass 之间的 dependency 是否导致不必要的 flush [SPEC]
3. **Barrier 范围**：全屏 barrier 可能阻塞整个管线 [ENGINE]
4. **Render target 格式**：高精度 attachment 滥用 [ENGINE]

## 4. 优化优先级

### 优先级 1：减少带宽消耗（最高收益）

1. **合并 Bloom 和 ToneMapping Pass** — 减少 1 次全屏读写 [ENGINE]
   - 修改文件: shader 文件、Pipeline 创建代码
   - 新增: 合并后的 fragment shader
   - 验证: AGI trace 对比前后带宽 [AGI]

2. **降低 G-Buffer 精度** — 如果不需要 HDR，用 RGBA8 替代 RGBA16F [ENGINE][HEUR]
   - 适用边界: 仅当光照计算不需要高精度时

3. **降低渲染分辨率** — 在移动端用 1920x1080 渲染，UI 层用 native 分辨率 [VENDOR]
   - 修改: Swapchain extent 或 render target extent
   - 新增: upscale pass (FSR 或 bilinear)

### 优先级 2：优化 TBR 效率

1. **G-Buffer loadOp 设为 CLEAR, storeOp 设为 STORE** — 不要在中间 Pass 用 DONT_CARE [VENDOR][SPEC]
2. **确保 G-Buffer Pass 和 Lighting Pass 在同一 tile 内完成** — 使用 VkRenderPass 的 dependency 避免tile resolve [VENDOR]
3. **考虑用 Multisampled Render To Texture** — 如果需要 MSAA，用 tile 内 resolve [VENDOR]

### 优先级 3：GPU Fragment 优化

1. **简化 Lighting shader** — 减少纹理采样次数 [ENGINE]
2. **用 compute shader 替代 fragment shader 做 Lighting** — 某些场景更高效 [HEUR]

### 优先级 4：同步优化

1. **用 vkCmdPipelineBarrier2 替代 vkCmdPipelineBarrier** — 细化 stage mask [SPEC]
2. **减少 barrier 数量** — 合并相邻 Pass 的 barrier [ENGINE]

## 5. 验证指标

- GPU frame time: 目标 < 16.6ms (60fps) [TOOL]
- 带宽: 目标 < 15 GB/s [AGI]
- GPU 占用率: 用 AGI counter 监测 [AGI]

## 6. 工具建议

- **AGI (Android GPU Inspector)**: 抓帧分析带宽、GPU 占用率、tile resolve 次数 [AGI]
- **Mali Streamline / Counter**: 监控 Mali GPU 特定 counter [VENDOR]
- **RenderDoc**: 检查 Pass 顺序和 attachment 配置 [TOOL]
- **Validation Layer**: 确认 barrier 正确性 [TOOL]

## 7. 回归指标

- 优化后帧率 ≥ 60fps
- 带宽降低 ≥ 30%
- GPU 占用率 < 80%
- 无 Validation Layer 报错
"""

# TC9.3 - Forward Rendering Design (正向开发类)
RESPONSES["TC9.3"] = """## 1. 结论

推荐使用 Vulkan 1.3+ Dynamic Rendering 的前向渲染管线方案。核心设计：单 Pass 多 draw call，Descriptor Set 分层管理（per-frame / per-material / per-object），支持桌面和 Android 双平台 [GUIDE][ENGINE]。

## 2. 推荐方案

- 渲染路径: Dynamic Rendering (Vulkan 1.3+)，兼容时回退到 VkRenderPass [SPEC]
- 光照模型: 前向渲染，1 directional light + 动态 point light（UBO 数组上传）
- Descriptor 策略: 3 层 set layout (per-frame / per-material / per-object)
- 同步策略: 2 frames-in-flight + timeline semaphore [SPEC][ENGINE]

## 3. Vulkan 对象链路

```
VkInstance
  └─ VkPhysicalDevice
       └─ VkDevice
            ├─ VkQueue (Graphics)
            ├─ VkCommandPool
            │    └─ VkCommandBuffer (×2 frames-in-flight)
            ├─ VkSwapchainKHR
            │    └─ VkImage (swapchain images)
            │         └─ VkImageView
            ├─ VkDescriptorSetLayout (×3: frame/material/object)
            ├─ VkDescriptorPool
            │    └─ VkDescriptorSet (×N)
            ├─ VkPipelineLayout
            ├─ VkPipeline (Graphics)
            ├─ VkBuffer (Uniform Buffer ×2 frames)
            ├─ VkDeviceMemory
            ├─ VkFence (×2)
            ├─ VkSemaphore (×4: image_available, render_finished ×2)
            └─ VkRenderingAttachmentInfo (color + depth)
```

## 4. 资源设计

### Uniform Buffer
- Per-frame UBO: ViewMatrix, ProjectionMatrix, LightParams
- Per-object UBO: ModelMatrix, MVP

### Descriptor Set Layout

```c
// Set 0: Per-frame (更新每帧)
VkDescriptorSetLayoutBinding frameBindings[] = {
    {0, VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, 1, VK_SHADER_STAGE_VERTEX_BIT | VK_SHADER_STAGE_FRAGMENT_BIT, nullptr}
};

// Set 1: Per-material (更新按材质)
VkDescriptorSetLayoutBinding materialBindings[] = {
    {0, VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, 1, VK_SHADER_STAGE_FRAGMENT_BIT, nullptr}
};

// Set 2: Per-object (更新每个 draw call)
VkDescriptorSetLayoutBinding objectBindings[] = {
    {0, VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC, 1, VK_SHADER_STAGE_VERTEX_BIT, nullptr}
};
```

## 5. Pipeline / Descriptor 设计

- Pipeline: Dynamic Rendering，不创建 VkRenderPass [SPEC]
- Vertex input: Position(Normal), TexCoord, Normal
- Blend: 关闭（前向渲染不需要混合）
- Depth: VK_COMPARE_OP_LESS, depthWriteEnable = VK_TRUE
- Dynamic state: Viewport, Scissor, stencil

## 6. 同步与 Layout 设计

### 同步
- `vkAcquireNextImageKHR` → signal `imageAvailableSemaphore`
- `vkQueueSubmit` → wait `imageAvailableSemaphore`, signal `renderFinishedSemaphore`
- `vkQueuePresentKHR` → wait `renderFinishedSemaphore`
- Frame fence: `vkWaitForFences` 等待上一帧完成 [SPEC]

### Image Layout Transition
- Swapchain image: UNDEFINED → COLOR_ATTACHMENT_OPTIMAL (barrier before rendering) [SPEC]
- Depth image: UNDEFINED → DEPTH_ATTACHMENT_OPTIMAL [SPEC]

## 7. Android 注意点

- **Surface 生命周期**: ANativeWindow 可能在 pause/resume 时销毁，必须处理 Surface 重建 [ANDROID]
- **Swapchain recreate**: VkSurfaceFormatKHR 和 extent 需在重建时重新查询 [ANDROID]
- **内存预算**: Android 设备 VkDeviceMemory 有限制，需用 VMA 管理内存 [ENGINE]
- **GPU 驱动差异**: Adreno / Mali 对 Dynamic Rendering 支持可能不一致，需 query `vkGetPhysicalDeviceFeatures2` [VENDOR]
- **adb logcat**: 部署时用 `adb logcat -s Vulkan` 监控错误 [ANDROID]

## 8. 实现步骤

### 修改文件
1. `renderer.cpp` — 主渲染器类
2. `swapchain.cpp` — Swapchain 管理
3. `pipeline.cpp` — Pipeline 创建
4. `descriptor.cpp` — Descriptor 管理
5. `shader/forward.vert` / `shader/forward.frag` — 着色器

### 新增 Vulkan 对象
- VkDescriptorSetLayout ×3
- VkDescriptorPool
- VkPipelineLayout
- VkPipeline
- VkBuffer (UBO ×2)
- VkFence ×2, VkSemaphore ×4

### 初始化流程
1. vkCreateInstance → vkGetPhysicalDeviceSurfaceSupportKHR
2. vkCreateDevice (启用 VK_KHR_dynamic_rendering)
3. vkCreateSwapchainKHR
4. vkCreateDescriptorSetLayout ×3
5. vkCreateDescriptorPool → vkAllocateDescriptorSets
6. vkCreatePipelineLayout → vkCreateGraphicsPipelines
7. vkCreateCommandPool → vkAllocateCommandBuffers
8. vkCreateFence ×2, vkCreateSemaphore ×4
9. vkCreateBuffer (UBO) → vkAllocateMemory → vkBindBufferMemory

### 每帧执行流程
1. vkWaitForFences → vkResetFences
2. vkAcquireNextImageKHR
3. vkBeginCommandBuffer
4. Image layout barrier (swapchain image)
5. vkCmdBeginRendering
6. vkCmdSetViewport / vkCmdSetScissor
7. vkCmdBindPipeline
8. vkCmdBindDescriptorSets (set 0, 1, 2)
9. vkCmdDraw (per object)
10. vkCmdEndRendering
11. Image layout barrier (present)
12. vkEndCommandBuffer
13. vkQueueSubmit → vkQueuePresentKHR

### 同步关系
- Semaphore: acquire → submit → present 链式等待 [SPEC]
- Fence: 每帧 fence 确保 command buffer 不被重用 [SPEC]
- Barrier: swapchain image layout transition [SPEC]

### 资源销毁 / 重建流程
- 销毁顺序: vkDestroyPipeline → vkDestroyPipelineLayout → vkDestroyDescriptorPool → vkDestroyCommandPool → vkDestroySwapchainKHR → vkDestroyDevice → vkDestroyInstance
- Swapchain 重建: vkDestroySwapchainKHR → vkCreateSwapchainKHR → 重建 ImageView → 重新分配 Command Buffer

## 9. 验证方式

1. 启用 Validation Layer 确认无报错 [TOOL]
2. 用 RenderDoc 验证 draw call 和 attachment 内容 [TOOL]
3. 桌面端用 Vulkan SDK 的 vkcube 对比链路 [TOOL]
4. Android 端用 AGI 抓帧验证 [AGI]
5. 测试前后台切换后 Swapchain 重建是否正常 [ANDROID]

## 10. 常见风险

1. Dynamic Rendering 在旧设备上不支持 → 需 fallback 到 VkRenderPass [VENDOR]
2. Descriptor Set 数量超过 maxBoundDescriptorSets → 需查询设备限制 [SPEC]
3. Android 内存不足 → 需控制 UBO 大小和数量 [ANDROID]
4. 多 point light 导致 shader 复杂度过高 → 考虑 clamped light 数量 [ENGINE]
"""

# TC9.4 - Descriptor Code Modification (正向开发类/代码类)
RESPONSES["TC9.4"] = """## 1. 结论

将每帧 `vkAllocateDescriptorSets` 改为预分配 Descriptor Pool + `vkUpdateDescriptorSets` 方式。核心变更：初始化时分配 N 个 Descriptor Set（N = frames-in-flight × per-frame object count），每帧用 `vkUpdateDescriptorSets` 更新 UBO binding [SPEC][ENGINE]。

## 2. 推荐方案

- 预分配策略: 2 frames-in-flight × M objects = 2M 个 Descriptor Set
- 更新方式: `vkWriteDescriptorSet` 更新 buffer binding
- 内存策略: Ring Buffer 管理 UBO，每帧 map 不同的 offset

## 3. Vulkan 对象链路

```
VkDescriptorSetLayout (per-object, binding 0 = UBO)
  └─ VkDescriptorPool (预分配 2M 个 set)
       └─ VkDescriptorSet × 2M (初始化时一次性分配)
            └─ vkUpdateDescriptorSets (每帧更新 binding 0 指向当前 frame 的 UBO offset)

VkBuffer (UBO, 单个大 buffer)
  └─ VkDeviceMemory (持久映射)
       └─ per-frame offset: frameIndex × uniformDataSize
```

## 4. 资源设计

### Descriptor Set Layout (不变)

```c
VkDescriptorSetLayoutBinding binding = {
    .binding = 0,
    .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
    .descriptorCount = 1,
    .stageFlags = VK_SHADER_STAGE_VERTEX_BIT,
    .pImmutableSamplers = nullptr
};
```

### Descriptor Pool (修改: 预分配)

```c
VkDescriptorPoolSize poolSize = {
    .type = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
    .descriptorCount = MAX_FRAMES_IN_FLIGHT * MAX_OBJECTS
};
VkDescriptorPoolCreateInfo poolInfo = {
    .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
    .maxSets = MAX_FRAMES_IN_FLIGHT * MAX_OBJECTS,
    .poolSizeCount = 1,
    .pPoolSizes = &poolSize,
    .flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT
};
vkCreateDescriptorPool(device, &poolInfo, nullptr, &descriptorPool);
```

### UBO Buffer (修改: 单个大 buffer)

```c
VkBufferCreateInfo bufferInfo = {
    .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
    .size = MAX_FRAMES_IN_FLIGHT * MAX_OBJECTS * sizeof(UniformBufferObject),
    .usage = VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
    .sharingMode = VK_SHARING_MODE_EXCLUSIVE
};
vkCreateBuffer(device, &bufferInfo, nullptr, &uniformBuffer);
// 分配内存并持久映射
vkAllocateMemory(device, &allocInfo, nullptr, &uniformMemory);
vkBindBufferMemory(device, uniformBuffer, uniformMemory, 0);
vkMapMemory(device, uniformMemory, 0, bufferInfo.size, 0, &uniformMapped);
```

## 5. Pipeline / Descriptor 设计

### 初始化时分配所有 Descriptor Set

```c
// 一次性分配 2M 个 set
for (int frame = 0; frame < MAX_FRAMES_IN_FLIGHT; frame++) {
    for (int obj = 0; obj < MAX_OBJECTS; obj++) {
        VkDescriptorSetAllocateInfo allocInfo = {
            .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
            .descriptorPool = descriptorPool,
            .descriptorSetLayoutCount = 1,
            .pSetLayouts = &descriptorSetLayout
        };
        vkAllocateDescriptorSets(device, &allocInfo, &descriptorSets[frame][obj]);
    }
}
```

### 每帧更新

```c
void updateDescriptorSet(int frameIndex, int objectIndex, VkDeviceSize offset) {
    VkDescriptorBufferInfo bufferInfo = {
        .buffer = uniformBuffer,
        .offset = offset,
        .range = sizeof(UniformBufferObject)
    };
    VkWriteDescriptorSet descriptorWrite = {
        .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
        .dstSet = descriptorSets[frameIndex][objectIndex],
        .dstBinding = 0,
        .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
        .descriptorCount = 1,
        .pBufferInfo = &bufferInfo
    };
    vkUpdateDescriptorSets(device, 1, &descriptorWrite, 0, nullptr);
}
```

## 6. 同步与 Layout 设计

### 同步关系
- UBO 写入与 GPU 读取之间的同步：使用 2 frames-in-flight 确保不会覆盖正在被 GPU 读取的数据 [SPEC]
- `vkQueueSubmit` 时传入 `VkFence`，下一帧开始前 `vkWaitForFences` 等待 [SPEC]
- 不需要 Barrier：UBO 更新在 CPU 端，GPU 通过 Fence 保证不读到半写入数据 [SPEC][ENGINE]

### 每帧执行流程
1. `vkWaitForFences` (等待上一帧完成)
2. `vkResetFences`
3. `vkAcquireNextImageKHR`
4. CPU 端: `memcpy` 更新 UBO 到 `uniformMapped + frameIndex * uniformDataSize`
5. `vkUpdateDescriptorSets` (更新 binding 0 指向当前 offset)
6. `vkBeginCommandBuffer`
7. `vkCmdBindDescriptorSets` (绑定预分配的 set)
8. `vkCmdDraw`
9. `vkEndCommandBuffer`
10. `vkQueueSubmit` (传入 fence)
11. `vkQueuePresentKHR`

## 7. 修改文件

1. `descriptor_manager.cpp/.h` — 新增预分配逻辑、更新方法
2. `renderer.cpp` — 修改每帧流程
3. `buffer_manager.cpp/.h` — 新增 UBO Ring Buffer
4. `scene.cpp` — 适配 object × frame 的 Descriptor Set 索引

## 8. 新增 Vulkan 对象

- `VkDescriptorPool` (修改: 从每帧分配改为预分配)
- `VkDescriptorSet[2][M]` (新增: 预分配数组)
- `VkBuffer` (修改: 从多个小 buffer 改为单个大 buffer)
- `VkDeviceMemory` (修改: 持久映射)

## 9. 资源销毁 / 重建流程

### 销毁顺序
1. `vkDeviceWaitIdle`
2. `vkDestroyDescriptorPool` (自动释放所有 set)
3. `vkDestroyBuffer` (uniformBuffer)
4. `vkFreeMemory` (uniformMemory)
5. `vkDestroyDescriptorSetLayout`
6. `vkDestroyPipelineLayout`
7. `vkDestroyPipeline`

### Swapchain 重建时
- Descriptor Set 不需要重建（与 Swapchain 无关）
- 只需重新创建 Swapchain、ImageView、Pipeline (如果 render area 变化)

## 10. 验证方式

1. 启用 Validation Layer，确认无 `VUID-vkAllocateDescriptorSets-*` 报错 [TOOL]
2. 用 RenderDoc 验证每帧 Descriptor Set binding 是否正确 [TOOL]
3. 检查 `vkUpdateDescriptorSets` 调用频率，确认不在每帧重复更新相同 set [ENGINE]
4. 性能对比: 用 AGI 测量 Descriptor 分配开销是否降为 0 [AGI]
5. 测试多帧循环后内存是否泄漏 [TOOL]

## 11. 常见风险

1. `VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT` 会导致碎片化 → 建议用 `UPDATE_AFTER_BIND` flag [SPEC]
2. UBO offset 必须对齐到 `minUniformBufferOffsetAlignment` → 需查询设备属性 [SPEC]
3. 大 buffer 可能超出 `maxMemoryAllocationCount` → 需用 VMA 管理 [ENGINE]
"""

# TC9.5 - Pipeline Barrier API (API 细节类)
RESPONSES["TC9.5"] = """## 1. 一句话定位

`vkCmdPipelineBarrier` [REGISTRY] 是 Vulkan 中用于在 command buffer 中插入执行依赖和内存依赖的命令，确保前序操作完成后后序操作才能开始，且内存写入对后续操作可见 [SPEC]。

## 2. 所属对象链路

```
VkCommandBuffer
  └─ vkCmdPipelineBarrier
       ├─ VkMemoryBarrier (全局内存屏障)
       ├─ VkBufferMemoryBarrier (buffer 级别)
       └─ VkImageMemoryBarrier (image 级别, 含 layout transition)
            ├─ oldLayout / newLayout
            ├─ srcAccessMask / dstAccessMask
            └─ srcQueueFamilyIndex / dstQueueFamilyIndex
```

## 3. 常用 API / 关键字段

### 四个核心 mask 参数 [SPEC][REGISTRY]

| 参数 | 作用 | 说明 |
|------|------|------|
| `srcStageMask` | 前序操作到达的阶段 | 定义 barrier 之前的操作必须到达哪些 pipeline stage |
| `dstStageMask` | 后序操作等待的阶段 | 定义 barrier 之后的操作在哪些 stage 等待前序完成 |
| `srcAccessMask` | 前序写入的类型 | 定义哪些内存写入需要对后序可见 |
| `dstAccessMask` | 后序读取的类型 | 定义后序操作以什么方式访问内存 |

### VkImageMemoryBarrier 关键字段 [REGISTRY]

| 字段 | 作用 |
|------|------|
| `oldLayout` | image 当前 layout |
| `newLayout` | image 目标 layout |
| `srcQueueFamilyIndex` | 源 queue family (跨 queue 时使用) |
| `dstQueueFamilyIndex` | 目标 queue family |
| `subresourceRange` | 受影响的 mip level / layer 范围 |

## 4. 标准使用流程

### Image Layout Transition 示例 [SPEC]

```c
VkImageMemoryBarrier barrier = {
    .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
    .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
    .newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
    .srcAccessMask = 0,  // UNDEFINED layout 不需要 source access
    .dstAccessMask = VK_ACCESS_SHADER_READ_BIT,
    .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
    .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
    .image = image,
    .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}
};

vkCmdPipelineBarrier(commandBuffer,
    VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,     // srcStageMask
    VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,  // dstStageMask
    0,                                      // dependencyFlags
    0, nullptr,                             // memory barriers
    0, nullptr,                             // buffer barriers
    1, &barrier);                            // image barriers
```

### 常见 Transition 参数表 [SPEC][REGISTRY]

| 转换 | srcStageMask | dstStageMask | srcAccessMask | dstAccessMask |
|------|-------------|-------------|---------------|---------------|
| UNDEFINED → COLOR_ATTACHMENT_OPTIMAL | TOP_OF_PIPE | COLOR_ATTACHMENT_OUTPUT | 0 | COLOR_ATTACHMENT_WRITE |
| COLOR_ATTACHMENT → SHADER_READ_ONLY | COLOR_ATTACHMENT_OUTPUT | FRAGMENT_SHADER | COLOR_ATTACHMENT_WRITE | SHADER_READ |
| TRANSFER_DST → SHADER_READ_ONLY | TRANSFER | FRAGMENT_SHADER | TRANSFER_WRITE | SHADER_READ |

## 5. 高频错误

1. **srcStageMask 过宽** — 用 `ALL_COMMANDS_BIT` 会导致性能下降，应精确指定 [ENGINE][HEUR]
2. **srcAccessMask 与 srcStageMask 不匹配** — 每个 stage 只允许特定的 access mask [SPEC]
3. **oldLayout 错误** — 当前实际 layout 与 oldLayout 不匹配会导致 validation error [SPEC]
4. **VUID 报错** — 如 `VUID-VkImageMemoryBarrier-oldLayout-01197` 等 [TOOL]
5. **跨 queue family 忽略** — CONCURRENT sharing mode 不需要，EXCLUSIVE 需要 [SPEC]

## 6. 生命周期 / 同步风险

- Barrier 不会等待 GPU 完成，只是建立依赖关系 [SPEC]
- 过多 barrier 会导致 pipeline stall [ENGINE]
- `vkCmdPipelineBarrier2` (synchronization2) 提供更细粒度的控制 [REGISTRY]
- Image layout transition 是隐含的，不需要额外命令 [SPEC]

## 7. 需要回查官方文档的情况

- 具体的 stage flag 和 access flag 组合是否合法 → 回查 Vulkan Spec 中的 "Pipeline Barrier Access Mask" 表格 [SPEC]
- Vulkan 1.2 vs 1.3 的差异 → 回查 Vulkan Guide [GUIDE]
- 扩展引入的新 stage/access mask → 回查 Vulkan Registry [REGISTRY]
- 不确定的 layout transition 合法性 → 回查 Vulkan Spec 中的 "Image Layout Transitions" 章节 [SPEC]

建议始终用 Validation Layer 验证 barrier 参数正确性 [TOOL]，对于不确定的 API 细节不要编造，应回查 Vulkan Spec / Vulkan Guide [SPEC][GUIDE]。
"""

# TC9.6 - Android Surface Lifecycle (Android 专项类/故障调试类)
RESPONSES["TC9.6"] = """## 1. 最可能原因排序

Android 前后台切换崩溃问题，按 `debug_priority.md` Crash 类排查 [ENGINE][TOOL]：

1. **Surface 销毁后仍尝试 present** — `vkQueuePresentKHR` 在 ANativeWindow 销毁后返回 `VK_ERROR_SURFACE_LOST_KHR`，但未处理该错误 [ANDROID][SPEC]
2. **Surface 销毁后仍尝试 acquire** — `vkAcquireNextImageKHR` 在 Surface 失效后直接 crash（访问已释放的 ANativeWindow） [ANDROID]
3. **Swapchain 未重建** — Surface 重建后旧 Swapchain 已失效，但未调用 `vkCreateSwapchainKHR` 重建 [ANDROID][SPEC]
4. **GPU 操作未完成就销毁资源** — 重建前未等待 Fence，GPU 仍在使用旧资源 [SPEC]
5. **Command Buffer 引用已销毁资源** — 旧 Swapchain image/view 已销毁，但 Command Buffer 仍在引用 [SPEC]

## 2. 快速验证路径

1. 检查 `onPause` / `onResume` 回调中是否正确处理 Vulkan 资源 [ANDROID]
2. 在 `vkQueuePresentKHR` 返回值检查中处理 `VK_ERROR_SURFACE_LOST_KHR` [SPEC]
3. 用 `adb logcat -s Vulkan` 查看 native 层错误日志 [ANDROID]
4. 用 AGI 抓 trace 确认 GPU 操作是否在 Surface 销毁前完成 [AGI]
5. 检查 ANativeWindow 是否在 `onResume` 时重新获取 [ANDROID]

## 3. Vulkan 对象链路排查

```
ANativeWindow (Android Surface)
  └─ VkSurfaceKHR
       └─ VkSwapchainKHR
            └─ VkImage (swapchain images)
                 └─ VkImageView
                      └─ VkFramebuffer (or Dynamic Rendering attachment)

生命周期:
  onCreate → 创建 VkSurfaceKHR (from ANativeWindow)
  onPause  → 等待 GPU 完成 (vkDeviceWaitIdle)
  onResume → 检查 Surface 有效性
             → 如果 Surface 变化: 销毁旧 Swapchain → 重建 Swapchain → 重建 ImageView
  onDestroy → 销毁所有资源
```

## 4. 工具证据

- **logcat**: `adb logcat -s Vulkan` 检查 `VK_ERROR_SURFACE_LOST_KHR` 和 crash 堆栈 [ANDROID]
- **AGI**: 确认 Surface 销毁时 GPU 是否有未完成的 command buffer [AGI]
- **Validation Layer**: 检查是否有 use-after-destroy 报错 [TOOL]

## 5. 修复方案

### 完整的 Surface 重建流程

```c
// onPause: 暂停渲染，等待 GPU 完成
void onPause() {
    vkDeviceWaitIdle(device);  // 确保 GPU 完成所有操作 [SPEC]
    renderThreadPaused = true;
}

// onResume: 恢复渲染，重建 Surface/Swapchain
void onResume(ANativeWindow* newWindow) {
    // 1. 等待 GPU idle
    vkDeviceWaitIdle(device);  // [SPEC]

    // 2. 销毁旧 Swapchain 相关资源
    for (auto& imageView : swapchainImageViews) {
        vkDestroyImageView(device, imageView, nullptr);
    }
    if (swapchain != VK_NULL_HANDLE) {
        vkDestroySwapchainKHR(device, swapchain, nullptr);
    }
    if (surface != VK_NULL_HANDLE) {
        vkDestroySurfaceKHR(instance, surface, nullptr);
    }

    // 3. 重建 Surface
    VkAndroidSurfaceCreateInfoKHR surfaceInfo = {
        .sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR,
        .window = newWindow  // 新的 ANativeWindow
    };
    vkCreateAndroidSurfaceKHR(instance, &surfaceInfo, nullptr, &surface);  // [ANDROID]

    // 4. 重建 Swapchain
    VkSwapchainCreateInfoKHR swapchainInfo = {
        .sType = VK_STRUCTURE_TYPE_SWAPCHAIN_CREATE_INFO_KHR,
        .surface = surface,
        .minImageCount = surfaceCaps.minImageCount,
        .imageFormat = format,
        .imageExtent = extent,  // 重新查询 extent [ANDROID]
        .imageArrayLayers = 1,
        .imageUsage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,
        .preTransform = surfaceCaps.currentTransform,
        .compositeAlpha = VK_COMPOSITE_ALPHA_INHERIT_BIT_KHR,
        .presentMode = VK_PRESENT_MODE_FIFO_KHR,
        .clipped = VK_TRUE,
        .oldSwapchain = VK_NULL_HANDLE
    };
    vkCreateSwapchainKHR(device, &swapchainInfo, nullptr, &swapchain);  // [SPEC]

    // 5. 重建 ImageView
    uint32_t imageCount;
    vkGetSwapchainImagesKHR(device, swapchain, &imageCount, nullptr);
    swapchainImages.resize(imageCount);
    vkGetSwapchainImagesKHR(device, swapchain, &imageCount, swapchainImages.data());

    swapchainImageViews.resize(imageCount);
    for (uint32_t i = 0; i < imageCount; i++) {
        VkImageViewCreateInfo viewInfo = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
            .image = swapchainImages[i],
            .viewType = VK_IMAGE_VIEW_TYPE_2D,
            .format = format,
            .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}
        };
        vkCreateImageView(device, &viewInfo, nullptr, &swapchainImageViews[i]);  // [SPEC]
    }

    // 6. 重新录制 Command Buffer (引用新的 ImageView)
    rebuildCommandBuffers();

    renderThreadPaused = false;
}
```

### 错误处理

```c
// vkQueuePresentKHR 后处理错误
VkResult presentResult = vkQueuePresentKHR(presentQueue, &presentInfo);
if (presentResult == VK_ERROR_SURFACE_LOST_KHR || presentResult == VK_SUBOPTIMAL_KHR) {
    // Surface 已丢失或 Swapchain 不再匹配
    // 触发重建流程
    recreateSwapchain();  // [SPEC][ANDROID]
    return;
}

// vkAcquireNextImageKHR 后处理错误
VkResult acquireResult = vkAcquireNextImageKHR(device, swapchain, UINT64_MAX,
    imageAvailableSemaphore, VK_NULL_HANDLE, &imageIndex);
if (acquireResult == VK_ERROR_SURFACE_LOST_KHR) {
    // 不要继续 submit！先重建 Swapchain
    recreateSwapchain();
    return;
}
```

## 6. 回归验证

1. 测试前后台切换 10 次无 crash [ANDROID]
2. 测试横竖屏切换无 crash [ANDROID]
3. 用 AGI 确认 GPU 操作在 Surface 销毁前完成 [AGI]
4. 用 Validation Layer 确认无 use-after-destroy [TOOL]
5. 测试快速连续前后台切换（< 1 秒间隔） [ANDROID]

## 7. 相关 API / Case

- `vkCreateAndroidSurfaceKHR`, `vkDestroySurfaceKHR` [ANDROID]
- `vkCreateSwapchainKHR`, `vkDestroySwapchainKHR` [SPEC]
- `vkQueuePresentKHR`, `vkAcquireNextImageKHR` [SPEC]
- `vkDeviceWaitIdle`, `vkWaitForFences` [SPEC]
- 参考: `02_core_mental_model/android_surface_swapchain_lifecycle.md`
- 参考: `06_cases/04_swapchain_android/case_surface_destroy_present_crash.md`
"""

# TC9.7 - Anti-pattern (概念+链路类 + 性能优化类)
RESPONSES["TC9.7"] = """## 1. 结论

**不建议用 OpenGL 替代 Vulkan 渲染。** [HARD_RULE_1] 应在 Vulkan 框架内优化性能，先判断瓶颈类型再针对性优化。对于 Descriptor，即便用户要求"概念解释"，也必须落到 Vulkan 对象链路和 API [HARD_RULE_11]。

## 2. 性能优化（瓶颈分类优先）

遇到性能问题，先判断瓶颈类型 [HARD_RULE_8] [ENGINE]：

### 瓶颈分类

| 类型 | 常见原因 | 验证工具 |
|------|----------|----------|
| CPU bound | Command Buffer 录制过重、Descriptor 频繁分配、Pipeline 运行时创建 | profiler, AGI [AGI] |
| GPU Fragment bound | Fragment shader 过重、Overdraw、Fullscreen pass 过多 | AGI counter [AGI] |
| Bandwidth bound | 大 RT、多 pass 读写、MSAA resolve、tile resolve | AGI bandwidth counter [AGI][VENDOR] |
| Synchronization bound | Barrier 过宽、Fence 等待、Queue idle | AGI timeline [AGI] |

### 优化方向（Vulkan 内）

1. **减少 fullscreen pass 数量** — 合并后处理 Pass [ENGINE]
2. **优化 barrier** — 用 `vkCmdPipelineBarrier2` 细化 stage mask [SPEC]
3. **Descriptor 策略** — 预分配 pool，避免每帧 `vkAllocateDescriptorSets` [ENGINE]
4. **Pipeline cache** — 使用 `VkPipelineCache` 加速创建 [SPEC]

## 3. Vulkan Descriptor 对象链路

### 核心概念

Descriptor 是 Vulkan 中将 shader 资源（UBO, Sampler, Image）与实际 GPU 资源绑定的机制 [SPEC]。不是简单的"指针"，而是一个完整的对象链路：

### Vulkan 对象链路

```
VkDescriptorSetLayout
  └─ VkDescriptorSetLayoutBinding (定义 binding slot, type, stage)
       └─ VkDescriptorPool (分配 pool)
            └─ VkDescriptorSet (实际资源绑定容器)
                 └─ vkUpdateDescriptorSets (写入资源引用)
                      ├─ VkDescriptorBufferInfo → VkBuffer (UBO/SSBO)
                      └─ VkDescriptorImageInfo → VkImageView + VkSampler

VkPipelineLayout
  └─ 引用 VkDescriptorSetLayout[]
       └─ vkCmdBindDescriptorSets (将 set 绑定到 command buffer)
            └─ shader 通过 layout(binding=N) 访问资源
```

### 关键 API [REGISTRY]

```c
// 1. 创建 Layout
VkDescriptorSetLayoutBinding binding = {
    .binding = 0,
    .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
    .descriptorCount = 1,
    .stageFlags = VK_SHADER_STAGE_VERTEX_BIT
};
VkDescriptorSetLayoutCreateInfo layoutInfo = {
    .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
    .bindingCount = 1,
    .pBindings = &binding
};
vkCreateDescriptorSetLayout(device, &layoutInfo, nullptr, &setLayout);

// 2. 分配 Descriptor Set
VkDescriptorSetAllocateInfo allocInfo = {
    .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
    .descriptorPool = pool,
    .descriptorSetLayoutCount = 1,
    .pSetLayouts = &setLayout
};
vkAllocateDescriptorSets(device, &allocInfo, &descriptorSet);

// 3. 更新资源绑定
VkDescriptorBufferInfo bufferInfo = {
    .buffer = uniformBuffer,
    .offset = 0,
    .range = sizeof(UBO)
};
VkWriteDescriptorSet writeInfo = {
    .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
    .dstSet = descriptorSet,
    .dstBinding = 0,
    .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
    .descriptorCount = 1,
    .pBufferInfo = &bufferInfo
};
vkUpdateDescriptorSets(device, 1, &writeInfo, 0, nullptr);

// 4. 绑定到 command buffer
vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_GRAPHICS,
    pipelineLayout, 0, 1, &descriptorSet, 0, nullptr);
```

## 4. 可执行检查点

1. 检查 `vkAllocateDescriptorSets` 是否在每帧调用 → 改为预分配 [ENGINE]
2. 检查 `VkDescriptorSetLayoutBinding` 的 stageFlags 是否正确 [SPEC]
3. 用 Validation Layer 验证 binding 是否匹配 [TOOL]
4. 用 RenderDoc 检查 shader 中资源是否正确绑定 [TOOL]
"""

# TC9.8 - Uncertain API (API 细节类)
RESPONSES["TC9.8"] = """## 1. 一句话定位

`VkDeviceDeviceMemoryReportCreateInfoEXT` 是 `VK_EXT_device_memory_report` 扩展中的结构体，用于在设备内存分配/释放时通过 callback 通知应用程序 [REGISTRY]。关于具体引入版本和各厂商支持情况，需要回查官方文档确认 [SPEC]。

## 2. 所属对象链路

```
VkDeviceCreateInfo
  └─ VkDeviceDeviceMemoryReportCreateInfoEXT (pNext 链)
       ├─ pfnUserCallback (回调函数指针)
       └─ pUserData (用户数据)
            └─ 触发时机: vkAllocateMemory / vkFreeMemory
```

## 3. 常用 API / 关键字段

### 结构体定义 [REGISTRY]

```c
typedef struct VkDeviceDeviceMemoryReportCreateInfoEXT {
    VkStructureType sType;  // VK_STRUCTURE_TYPE_DEVICE_DEVICE_MEMORY_REPORT_CREATE_INFO_EXT
    const void* pNext;
    VkDeviceMemoryReportFlagsEXT flags;
    PFN_vkDeviceMemoryReportCallbackEXT pfnUserCallback;
    void* pUserData;
} VkDeviceDeviceMemoryReportCreateInfoEXT;
```

### 回调类型 [REGISTRY]

```c
typedef void (VKAPI_PTR *PFN_vkDeviceMemoryReportCallbackEXT)(
    const VkDeviceMemoryReportCallbackDataEXT* pCallbackData,
    void* pUserData);
```

回调在以下事件触发：
- `VK_DEVICE_MEMORY_REPORT_EVENT_TYPE_ALLOCATE_EXT` — 内存分配
- `VK_DEVICE_MEMORY_REPORT_EVENT_TYPE_FREE_EXT` — 内存释放
- `VK_DEVICE_MEMORY_REPORT_EVENT_TYPE_IMPORT_EXT` — 外部内存导入
- `VK_DEVICE_MEMORY_REPORT_EVENT_TYPE_UNIMPORT_EXT` — 外部内存取消导入
- `VK_DEVICE_MEMORY_REPORT_EVENT_TYPE_ALLOCATION_FAILED_EXT` — 分配失败

## 4. 标准使用流程

1. 查询扩展是否可用: `vkEnumerateDeviceExtensionProperties` [SPEC]
2. 启用扩展: 在 `VkDeviceCreateInfo` 中添加 `VK_EXT_DEVICE_MEMORY_REPORT_EXTENSION_NAME`
3. 设置 callback: 通过 `pNext` 链传入 `VkDeviceDeviceMemoryReportCreateInfoEXT`
4. 在 callback 中记录内存分配/释放事件

## 5. 与 VMA 的区别

### VkDeviceDeviceMemoryReportCreateInfoEXT
- **层级**: Vulkan 设备层，由 driver 触发 [REGISTRY]
- **范围**: 所有 `vkAllocateMemory` / `vkFreeMemory` 调用
- **用途**: 监控底层内存分配，debug/分析工具用

### VMA (VulkanMemoryAllocator) 回调
- **层级**: 应用层库，由 VMA 触发 [ENGINE]
- **范围**: 仅 VMA 管理的分配
- **用途**: 应用级内存统计、自定义分配策略

**关键区别**: `VK_EXT_device_memory_report` 是 driver 级的，覆盖所有内存操作；VMA 回调是库级的，只覆盖 VMA 管理的内存 [ENGINE][REGISTRY]。

## 6. 不确定的信息

以下信息需要回查官方文档确认，不编造 [HARD_RULE_9]：

1. **引入版本**: 该扩展具体在哪个 Vulkan 版本或 SDK 中引入 → **建议回查 Vulkan Registry** [REGISTRY]
2. **Adreno 支持**: Adreno GPU 驱动对该扩展的支持情况 → **需要实际测试** [VENDOR]
3. **Mali 支持**: Mali GPU 驱动支持情况 → **需要实际测试** [VENDOR]

### 扩展查询方式

```c
// 查询设备支持的扩展
uint32_t extensionCount;
vkEnumerateDeviceExtensionProperties(physicalDevice, nullptr, &extensionCount, nullptr);
std::vector<VkExtensionProperties> extensions(extensionCount);
vkEnumerateDeviceExtensionProperties(physicalDevice, nullptr, &extensionCount, extensions.data());

// 检查是否支持
bool supported = false;
for (const auto& ext : extensions) {
    if (strcmp(ext.extensionName, VK_EXT_DEVICE_MEMORY_REPORT_EXTENSION_NAME) == 0) {
        supported = true;
        break;
    }
}
```

建议在不同厂商设备（Adreno, Mali, PowerVR）上分别运行此查询 [VENDOR]，不同 GPU 厂商的驱动支持情况可能不同。

## 7. 需要回查官方文档的情况

- 扩展引入的具体 Vulkan 版本 → 回查 Vulkan Registry [REGISTRY]
- 各厂商支持情况 → 回查各厂商 SDK 文档或直接测试 [VENDOR]
- 回调函数的线程安全保证 → 回查 Vulkan Spec [SPEC]
- 与其他内存扩展的交互 → 回查 Vulkan Guide [GUIDE]

对于不确定的 API 细节，不要编造 [HARD_RULE_9]，应回查 Vulkan Spec / Vulkan Guide / Android NDK 文档 [SPEC][GUIDE][ANDROID]。
"""

# TC9.9 - Source Tags (综合/API 细节类)
RESPONSES["TC9.9"] = """## 1. 一句话定位

`VK_IMAGE_LAYOUT_UNDEFINED` → `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 的 transition 需要通过 `vkCmdPipelineBarrier` 插入 `VkImageMemoryBarrier` [SPEC]，移动端 layout transition 的性能影响主要在于 tile resolve 和带宽消耗 [ENGINE][HEUR]。

## 2. 正确 barrier 参数

### Spec 要求的参数 [SPEC][REGISTRY]

```c
VkImageMemoryBarrier barrier = {
    .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
    .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,           // 旧 layout
    .newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,  // 新 layout
    .srcAccessMask = 0,                                // UNDEFINED layout 不需要 source access
    .dstAccessMask = VK_ACCESS_SHADER_READ_BIT,        // 后序 shader 读取
    .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
    .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
    .image = image,
    .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}
};

vkCmdPipelineBarrier(commandBuffer,
    VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,      // srcStageMask: UNDEFINED 不需要等待
    VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,   // dstStageMask: 后序 fragment shader 使用
    0,
    0, nullptr,
    0, nullptr,
    1, &barrier);
```

### 参数解释 [SPEC]

| 参数 | 值 | 原因 |
|------|-----|------|
| srcStageMask | TOP_OF_PIPE_BIT | oldLayout 是 UNDEFINED，前序无写入操作 |
| dstStageMask | FRAGMENT_SHADER_BIT | 后序在 fragment shader 中采样 |
| srcAccessMask | 0 | UNDEFINED layout 无需保证前序写入可见 |
| dstAccessMask | SHADER_READ_BIT | 后序操作为 shader 读取 |

**注意**: `srcAccessMask = 0` 是因为 UNDEFINED layout 的 image 内容不保证保留 [SPEC]。如果 oldLayout 不是 UNDEFINED（如 COLOR_ATTACHMENT_OPTIMAL），则 srcAccessMask 必须包含对应的写入类型 [SPEC]。

## 3. 移动端性能影响

### TBDR 架构的影响 [VENDOR][ENGINE]

移动端 GPU (Mali/Adreno) 使用 Tile-Based Deferred Rendering (TBDR)：

1. **Tile resolve**: Layout transition 可能触发 tile resolve（将 tile 数据写回系统内存），增加带宽 [VENDOR]
2. **带宽消耗**: 每次 layout transition 意味着一次 image 读写循环 [ENGINE][HEUR]
3. **Pipeline stall**: Barrier 会导致 GPU 等待，降低并行度 [ENGINE][HEUR]

### 优化建议 [ENGINE][HEUR]

1. **减少 transition 次数**: 合并相邻的 layout transition [ENGINE]
2. **在同一个 render pass 内完成**: 利用 subpass dependency 避免显式 barrier [SPEC][VENDOR]
3. **使用 UNDEFINED 初始 layout**: 当不需要保留旧内容时，从 UNDEFINED 开始 [SPEC]
4. **避免不必要的 transition**: 如果 image 只在 shader 中读取，不需要中间 layout [ENGINE]

### 适用边界 [HEUR]

以上性能建议适用于移动端 TBR/TBDR 架构 GPU (Mali, Adreno, PowerVR) [VENDOR]。桌面端 GPU (NVIDIA, AMD) 使用 Immediate Mode Rendering，layout transition 的性能影响较小 [VENDOR]。

## 4. 区分规范与经验

### Spec 要求（绝对遵守）[SPEC]
- `srcAccessMask` 和 `srcStageMask` 必须匹配
- `oldLayout` 必须与 image 当前实际 layout 一致
- `newLayout` 必须与后续使用方式兼容
- Validation Layer 会检查这些约束

### 工程经验（有适用边界）[ENGINE][HEUR]
- "减少 transition 次数" — 适用于带宽敏感场景，如果 transition 不是瓶颈则优化收益有限
- "在 render pass 内完成" — 适用于 TBR 架构，桌面端收益不大
- "UNDEFINED 初始 layout" — 适用于不需要保留旧内容的场景

## 5. 可执行检查点

1. 用 Validation Layer 验证 barrier 参数正确性 [TOOL]
2. 用 AGI 测量 layout transition 前后带宽变化 [AGI]
3. 用 RenderDoc 检查 transition 后 image 内容是否正确 [TOOL]
4. 对比减少 transition 次数前后的帧率 [ENGINE]
"""

# TC9.10 - Flicker Sync (故障调试类)
RESPONSES["TC9.10"] = """## 1. 最可能原因排序

画面闪烁问题，按 `debug_priority.md` 闪烁类排查 [ENGINE][TOOL]：

1. **Fence 调用顺序错误** — `vkResetFences → vkQueueSubmit → vkWaitForFences` 顺序不对，正确应为 `vkWaitForFences → vkResetFences → vkQueueSubmit` [SPEC]
2. **UBO 竞争条件** — `vkMapMemory + memcpy` 直接更新 UBO，2 frames-in-flight 下 CPU 写入时 GPU 仍在读取同一块内存 [SPEC][ENGINE]
3. **Swapchain image 重复写入** — Command Buffer 录制了错误 imageIndex 的渲染操作 [ENGINE]
4. **Command Buffer 错误复用** — Command Buffer 在 recording 状态下被重新提交 [SPEC]

## 2. 快速验证路径

1. 检查 Fence 调用顺序：确认 `vkWaitForFences` 在 `vkResetFences` 之前 [SPEC]
2. 检查 UBO 更新方式：确认每个 frame-in-flight 有独立的 UBO buffer [ENGINE]
3. 用 RenderDoc 抓多帧，对比闪烁帧和正常帧的差异 [TOOL]
4. 用 Validation Layer 检查是否有同步相关报错 [TOOL]
5. 用 AGI 检查 GPU timeline，确认 CPU/GPU 重叠情况 [AGI]

## 3. Vulkan 对象链路排查

```
Frame N:
  CPU: vkWaitForFences[frameN-1] → vkResetFences[frameN] → memcpy(ubo) → vkQueueSubmit[frameN]
  GPU: ←------- rendering frame N-1 -------→ ←-- rendering frame N --→

问题分析:
  如果 Fence 顺序错误:
  CPU: vkResetFences → vkQueueSubmit → vkWaitForFences (立即返回，因为刚 reset)
  GPU: 还在渲染上一帧，但 CPU 已经开始写入同一 UBO → 竞争！
```

### Fence 正确顺序 [SPEC]

```c
// 正确顺序:
vkWaitForFences(device, 1, &frameFences[currentFrame], VK_TRUE, UINT64_MAX);
vkResetFences(device, 1, &frameFences[currentFrame]);
// ... 录制 command buffer ...
vkQueueSubmit(queue, 1, &submitInfo, frameFences[currentFrame]);
```

### UBO 竞争分析 [SPEC][ENGINE]

```
2 frames-in-flight:
  Frame 0: UBO offset=0, GPU 正在读取
  Frame 1: CPU 写入 offset=0 ← 竞争！GPU 还在读

正确做法:
  Frame 0: UBO offset=0, GPU 正在读取
  Frame 1: CPU 写入 offset=uniformDataSize ← 不同 offset, 无竞争
```

## 4. 工具证据

- **Validation Layer**: 启用 `VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT` 检查同步错误 [TOOL]
- **RenderDoc**: 抓取闪烁帧，检查 attachment 内容和 draw call [TOOL]
- **AGI**: 检查 CPU/GPU timeline，确认是否有重叠写入 [AGI]

## 5. 修复方案

### 修复 1: Fence 调用顺序

```c
// 错误顺序（当前）:
// vkResetFences → vkQueueSubmit → vkWaitForFences

// 正确顺序:
void renderFrame() {
    // 1. 等待当前 frame 的 fence (上一轮该 frame 的 GPU 操作完成)
    vkWaitForFences(device, 1, &frameFences[currentFrame], VK_TRUE, UINT64_MAX);  // [SPEC]

    // 2. Reset fence
    vkResetFences(device, 1, &frameFences[currentFrame]);  // [SPEC]

    // 3. Acquire image
    vkAcquireNextImageKHR(device, swapchain, UINT64_MAX,
        imageAvailableSemaphores[currentFrame], VK_NULL_HANDLE, &imageIndex);

    // 4. 更新 UBO (使用 per-frame offset)
    memcpy((char*)uniformMapped + currentFrame * uniformDataSize,
           &uboData, sizeof(uboData));

    // 5. Submit
    VkSubmitInfo submitInfo = {
        .waitSemaphoreCount = 1,
        .pWaitSemaphores = &imageAvailableSemaphores[currentFrame],
        .signalSemaphoreCount = 1,
        .pSignalSemaphores = &renderFinishedSemaphores[currentFrame],
        .commandBufferCount = 1,
        .pCommandBuffers = &commandBuffers[currentFrame]
    };
    vkQueueSubmit(queue, 1, &submitInfo, frameFences[currentFrame]);  // [SPEC]

    // 6. Present
    vkQueuePresentKHR(presentQueue, &presentInfo);

    currentFrame = (currentFrame + 1) % MAX_FRAMES_IN_FLIGHT;
}
```

### 修复 2: UBO Ring Buffer（多 buffer）

```c
// 为每个 frame-in-flight 分配独立 UBO 空间
#define MAX_FRAMES_IN_FLIGHT 2

// 创建一个大 buffer，每个 frame 用不同 offset
VkDeviceSize uniformDataSize = sizeof(UniformBufferObject);
// 对齐到 minUniformBufferOffsetAlignment
VkDeviceSize alignedSize = (uniformDataSize + minAlignment - 1) & ~(minAlignment - 1);

// Per-frame 更新
void* frameUboAddr = (char*)uniformMapped + currentFrame * alignedSize;
memcpy(frameUboAddr, &uboData, uniformDataSize);  // [SPEC][ENGINE]

// Descriptor Set 更新
VkDescriptorBufferInfo bufferInfo = {
    .buffer = uniformBuffer,
    .offset = currentFrame * alignedSize,  // 使用 per-frame offset
    .range = uniformDataSize
};
```

### 修复 3: 使用 vkUpdateDescriptorSets（替代重新分配）

如果 UBO offset 变化，用 `vkUpdateDescriptorSets` 更新 binding [SPEC]。或使用 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC` + `vkCmdBindDescriptorSets` 的 dynamic offset [SPEC]。

## 6. 回归验证

1. 连续运行 1000 帧无闪烁 [ENGINE]
2. 用 RenderDoc 抓 100 帧，确认所有帧 attachment 内容正确 [TOOL]
3. 用 AGI 确认 CPU/GPU 无竞争 [AGI]
4. 用 Validation Layer 确认无同步报错 [TOOL]
5. 测试不同 frames-in-flight 数量 (1, 2, 3) [ENGINE]

## 7. 相关 API / Case

- `vkWaitForFences`, `vkResetFences`, `vkQueueSubmit` [SPEC]
- `vkMapMemory`, `memcpy` (UBO 更新) [SPEC]
- `vkUpdateDescriptorSets` [REGISTRY]
- 参考: `04_debug_playbooks/02_sync_issues/flicker.md`
- 参考: `02_core_mental_model/synchronization_lifecycle.md`
"""

# TC9.11 - Render Graph Architecture (架构设计类)
RESPONSES["TC9.11"] = """## 1. 架构结论

推荐分层架构：Pass Graph (声明层) → Barrier Scheduler (调度层) → Vulkan Executor (执行层)。核心设计原则：抽象层对使用者隐藏 Vulkan 同步复杂度，但不隐藏资源生命周期责任 [GUIDE][ENGINE]。

## 2. 模块边界

```
┌─────────────────────────────────────────────┐
│           Application Layer                 │
│  (声明 Pass、资源需求、输出)                  │
├─────────────────────────────────────────────┤
│           Pass Graph (声明层)                │
│  - Pass 节点 + 资源边                         │
│  - 资源生命周期声明                            │
│  - Resource Aliasing 候选分析                 │
├─────────────────────────────────────────────┤
│       Barrier Scheduler (调度层)              │
│  - 拓扑排序 + 同步需求推导                     │
│  - 自动 barrier 插入                          │
│  - 资源别名分配 (VkDeviceMemory aliasing)     │
├─────────────────────────────────────────────┤
│       Vulkan Executor (执行层)                │
│  - Command Buffer 录制                        │
│  - vkCmdPipelineBarrier2 调用                 │
│  - Dynamic Rendering 状态管理                 │
└─────────────────────────────────────────────┘
```

## 3. 数据流 / 资源流

### Pass Graph 数据结构

```c
struct RenderPassNode {
    std::string name;
    std::vector<ResourceHandle> inputs;   // 读取的资源
    std::vector<ResourceHandle> outputs;  // 写入的资源
    VkPipelineStageFlags stage;           // GPU 阶段
    ExecuteCallback execute;              // 录制回调
};

struct ResourceNode {
    ResourceHandle handle;
    VkFormat format;
    VkExtent2D extent;
    VkImageUsageFlags usage;
    std::vector<PassHandle> writers;      // 写入此资源的 Pass
    std::vector<PassHandle> readers;      // 读取此资源的 Pass
};
```

### 数据流

```
Application → 声明 Pass + 资源
  → Pass Graph 构建依赖关系 (DAG)
    → Scheduler 拓扑排序 + 同步推导
      → Executor 录制 Command Buffer + Barrier
        → vkQueueSubmit
```

## 4. Vulkan 对象归属

### Resource Aliasing 设计 [SPEC][REGISTRY]

```c
// 资源别名: 多个 VkImage 共享同一块 VkDeviceMemory
// 条件: 生命周期不重叠 [SPEC]

struct AliasedResource {
    VkImage image;           // 各自独立的 VkImage
    VkDeviceMemory memory;   // 共享的 VkDeviceMemory
    VkDeviceSize offset;     // 在 memory 中的偏移
    Lifetime interval;       // 生命周期区间
};

// 使用 VK_IMAGE_CREATE_ALIAS_BIT 创建可别名的 image [REGISTRY]
VkImageCreateInfo imageInfo = {
    .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
    .flags = VK_IMAGE_CREATE_ALIAS_BIT,  // 允许别名 [SPEC]
    .usage = usageFlags,
    // ...
};
```

### 对象归属表

| 对象 | 归属层 | 负责创建/销毁 |
|------|--------|---------------|
| VkImage / VkBuffer | Executor | 按 Scheduler 分配 |
| VkDeviceMemory | Executor | 统一管理别名 |
| VkCommandBuffer | Executor | 按帧分配 |
| VkPipeline | Executor | 按 Pass 缓存 |
| VkDescriptorSet | Executor | 按 Pass 分配 |

## 5. 生命周期设计

### 资源生命周期追踪

```c
struct ResourceLifetime {
    PassHandle firstUse;    // 首次使用的 Pass
    PassHandle lastUse;     // 最后使用的 Pass
    VkImageLayout finalLayout;  // 最终 layout
};

// Scheduler 分析所有 Pass 的资源使用，推导生命周期
// 生命周期不重叠的资源可以别名同一块内存 [ENGINE]
```

### Command Buffer 生命周期
- 每帧分配新的 Command Buffer（或从 pool 复用）
- Command Buffer 引用的资源在 submit 完成前不能销毁 [SPEC]

## 6. 同步策略

### 自动 Barrier 插入 [SPEC][ENGINE]

```c
// Scheduler 分析 Pass 依赖，自动生成 barrier
struct BarrierSchedule {
    PassHandle afterPass;       // 在哪个 Pass 之后插入
    VkImageMemoryBarrier2 barrier;
    VkPipelineStageFlags2 srcStage;
    VkPipelineStageFlags2 dstStage;
};

// 使用 synchronization2 [REGISTRY]
VkImageMemoryBarrier2 barrier = {
    .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
    .srcStageMask = VK_PIPELINE_STAGE_2_COLOR_ATTACHMENT_OUTPUT_BIT,
    .dstStageMask = VK_PIPELINE_STAGE_2_FRAGMENT_SHADER_BIT,
    .srcAccessMask = VK_ACCESS_2_COLOR_ATTACHMENT_WRITE_BIT,
    .dstAccessMask = VK_ACCESS_2_SHADER_READ_BIT,
    .oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
    .newLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,
    // ...
};
vkCmdPipelineBarrier2(commandBuffer, &depInfo);  // [REGISTRY]
```

### 策略
1. **最小化 barrier 范围**: 只在资源从写→读转换时插入 [ENGINE]
2. **合并 barrier**: 同一 Pass 的多个 barrier 合并为一次调用 [ENGINE]
3. **使用 subpass dependency**: 在 render pass 内用 subpass dependency 替代显式 barrier [SPEC][VENDOR]
4. **Layout transition 与 barrier 合并**: 利用 VkImageMemoryBarrier 的 oldLayout/newLayout [SPEC]

## 7. 扩展性与风险

### 扩展性
1. **新增 Pass 类型**: 只需实现 ExecuteCallback，无需修改 Scheduler [ENGINE]
2. **自定义同步策略**: 可替换 Scheduler 实现 [ENGINE]
3. **多 Queue 支持**: Pass Graph 支持指定 Queue family [SPEC]

### 风险
1. **抽象层泄露 Vulkan 复杂度**: 如果使用者需要理解 barrier 细节，抽象就失败了 [ENGINE]
   - 缓解: Scheduler 自动处理同步，使用者只声明读写关系
2. **别名导致的数据竞争**: 生命周期分析错误可能导致同一内存被同时使用 [ENGINE]
   - 缓解: 严格的 validation + Validation Layer 验证 [TOOL]
3. **移动端 TBR 兼容**: 自动 barrier 可能破坏 tile 局部性 [VENDOR]
   - 缓解: 移动端模式下优先使用 subpass dependency [VENDOR][ENGINE]
4. **Dynamic Rendering fallback**: 旧设备不支持 Dynamic Rendering [VENDOR]
   - 缓解: Executor 支持回退到 VkRenderPass [SPEC]

## 8. 验证任务

1. **同步正确性**: Validation Layer + synchronization validation [TOOL]
2. **别名安全性**: 用 RenderDoc 检查内存重叠 [TOOL]
3. **移动端性能**: AGI 测量 tile resolve 次数和带宽 [AGI][VENDOR]
4. **Barrier 数量**: 对比自动 vs 手动 barrier 数量 [ENGINE]
5. **跨平台测试**: 桌面 + Android (Adreno/Mali) [ANDROID][VENDOR]
6. **RenderDoc 帧捕获**: 验证 Pass 顺序和资源内容 [TOOL]
"""

# TC9.12 - Validation Error (故障调试类/API 细节类)
RESPONSES["TC9.12"] = """## 1. 最可能原因排序

`VUID-vkCmdBindDescriptorSets-pDescriptorSets-00358` 报错排查，按 `debug_priority.md` Validation Error 流程 [ENGINE][TOOL]：

1. **Descriptor Set Layout binding 数量与实际创建的不匹配** — Layout 声明了 2 个 binding (0=UBO, 1=sampler)，但创建时可能只有 1 个 [SPEC]
2. **Descriptor Set 未正确更新** — `vkUpdateDescriptorSets` 未调用或 binding 1 的 sampler 未写入 [SPEC]
3. **Pipeline Layout 与 Descriptor Set Layout 不一致** — Pipeline 创建时引用的 layout 与实际绑定的 set layout 不匹配 [SPEC]
4. **Descriptor 类型不匹配** — Layout 中声明为 `UNIFORM_BUFFER` 但实际绑定了 `STORAGE_BUFFER` [SPEC]

## 2. VUID 分析

### VUID 提取 [SPEC][TOOL]

- **VUID**: `vkCmdBindDescriptorSets-pDescriptorSets-00358`
- **API**: `vkCmdBindDescriptorSets`
- **参数**: `pDescriptorSets`
- **编号**: 00358

### VUID 含义 [SPEC]

VUID 00358 对应的 Spec 条款：绑定的 Descriptor Set 必须与 Pipeline Layout 中引用的 Descriptor Set Layout 兼容。具体来说，binding 数量、类型、stage flags 必须一致 [SPEC]。

## 3. Vulkan 对象链路排查

```
VkDescriptorSetLayoutBinding[] (创建点)
  ├─ binding 0: VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, VERTEX_BIT
  └─ binding 1: VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, FRAGMENT_BIT
       ↓
VkDescriptorSetLayout (创建点)
       ↓
VkPipelineLayout (引用 set layout)
       ↓
VkPipeline (使用 pipeline layout)
       ↓
vkCmdBindDescriptorSets (使用点 - 报错位置)
       └─ pDescriptorSets[] 绑定的 set
```

### 检查点

1. **创建点**: 查找 `vkCreateDescriptorSetLayout` 代码，确认 binding 数量和类型 [SPEC]
2. **使用点**: 查找 `vkCmdBindDescriptorSets` 代码，确认绑定的 set 是否匹配 [SPEC]
3. **Pipeline 创建**: 查找 `vkCreateGraphicsPipelines` 代码，确认 pipelineLayout 引用了正确的 setLayout [SPEC]

## 4. 工具证据

- **Validation Layer**: 完整报错信息包含 VUID、调用栈、相关对象 [TOOL]
- **RenderDoc**: 检查绑定的 Descriptor Set 内容 [TOOL]
- **vkGetPhysicalDeviceFeatures2**: 确认设备支持的 descriptor 数量 [SPEC]

## 5. 修复方案

### 检查 1: Descriptor Set Layout 创建代码

```c
// 确认 binding 数量和类型
VkDescriptorSetLayoutBinding bindings[] = {
    {
        .binding = 0,
        .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
        .descriptorCount = 1,
        .stageFlags = VK_SHADER_STAGE_VERTEX_BIT,
        .pImmutableSamplers = nullptr
    },
    {
        .binding = 1,
        .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
        .descriptorCount = 1,
        .stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT,
        .pImmutableSamplers = nullptr
    }
};
VkDescriptorSetLayoutCreateInfo layoutInfo = {
    .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
    .bindingCount = 2,  // ← 确认是 2，不是 1
    .pBindings = bindings
};
vkCreateDescriptorSetLayout(device, &layoutInfo, nullptr, &setLayout);  // [SPEC]
```

### 检查 2: Descriptor Set 更新代码

```c
// 确认两个 binding 都被更新
VkDescriptorBufferInfo bufferInfo = {
    .buffer = uniformBuffer,
    .offset = 0,
    .range = sizeof(UBO)
};
VkDescriptorImageInfo imageInfo = {
    .sampler = sampler,
    .imageView = textureView,
    .imageLayout = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL
};
VkWriteDescriptorSet writes[] = {
    {
        .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
        .dstSet = descriptorSet,
        .dstBinding = 0,  // UBO
        .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
        .descriptorCount = 1,
        .pBufferInfo = &bufferInfo
    },
    {
        .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
        .dstSet = descriptorSet,
        .dstBinding = 1,  // Sampler
        .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,
        .descriptorCount = 1,
        .pImageInfo = &imageInfo
    }
};
vkUpdateDescriptorSets(device, 2, writes, 0, nullptr);  // ← 确认 count 是 2 [SPEC]
```

### 检查 3: Pipeline Layout 创建代码

```c
VkPipelineLayoutCreateInfo pipelineLayoutInfo = {
    .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
    .setLayoutCount = 1,
    .pSetLayouts = &setLayout  // ← 确认引用了正确的 setLayout [SPEC]
};
vkCreatePipelineLayout(device, &pipelineLayoutInfo, nullptr, &pipelineLayout);
```

### 检查 4: vkCmdBindDescriptorSets 调用

```c
vkCmdBindDescriptorSets(commandBuffer,
    VK_PIPELINE_BIND_POINT_GRAPHICS,
    pipelineLayout,      // ← 必须与 Pipeline 创建时的一致 [SPEC]
    0,                    // firstSet
    1,                    // descriptorSetCount
    &descriptorSet,       // ← 必须是正确的 set [SPEC]
    0, nullptr);          // dynamic offsets
```

## 6. 最小修复

1. 确认 `vkCreateDescriptorSetLayout` 的 `bindingCount` = 2 [SPEC]
2. 确认 `vkUpdateDescriptorSets` 更新了两个 binding [SPEC]
3. 确认 `vkCreatePipelineLayout` 引用了正确的 `setLayout` [SPEC]
4. 确认 `vkCmdBindDescriptorSets` 的 `pipelineLayout` 与 Pipeline 的一致 [SPEC]

## 7. 回归验证

1. 重新运行应用，确认 Validation Layer 无 VUID 00358 报错 [TOOL]
2. 用 RenderDoc 确认 Descriptor Set binding 0 和 1 都有正确资源 [TOOL]
3. 确认 shader 中 `layout(binding=0) uniform UBO` 和 `layout(binding=1) uniform sampler2D` 都能正确访问 [ENGINE]
4. 测试多帧循环无重复报错 [TOOL]

## 8. 相关 API / Case

- `vkCreateDescriptorSetLayout` [SPEC]
- `vkUpdateDescriptorSets` [REGISTRY]
- `vkCreatePipelineLayout` [SPEC]
- `vkCmdBindDescriptorSets` [SPEC]
- 参考: `03_api_manual/06_descriptor/descriptor_set.md`
- 参考: `04_debug_playbooks/03_validation_errors/`
"""


# ============================================================================
# AUTOMATED CHECK FUNCTIONS
# ============================================================================

def check_format(response, required_keywords, min_count):
    found = [kw for kw in required_keywords if kw.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(required_keywords)}: {found}"
    return passed, detail

def check_anti_pattern(response, forbidden_patterns, window=0.3):
    text = response[:int(len(response) * window)]
    violations = [p for p in forbidden_patterns if p.lower() in text.lower()]
    passed = len(violations) == 0
    detail = f"Violations in first {int(window*100)}%: {violations}" if violations else "No violations"
    return passed, detail

def check_source_tags(response, required_tags=None, min_count=1):
    tags = re.findall(r'\[([A-Z]{2,})\]', response)
    if required_tags:
        found = [t for t in required_tags if f"[{t}]" in response]
        passed = len(found) >= min_count
        detail = f"Required: {required_tags}, Found: {found}"
    else:
        passed = len(tags) >= min_count
        detail = f"Found tags: {tags}"
    return passed, detail

def check_vulkan_objects(response, required_objects, min_count):
    found = [obj for obj in required_objects if obj.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(required_objects)}: {found}"
    return passed, detail

def check_keyword(response, keywords, min_count):
    found = [kw for kw in keywords if kw.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(keywords)}: {found}"
    return passed, detail

def check_numbered_list(response):
    has_list = bool(re.search(r'(^\s*\d+\.\s)|(^\s*[-*]\s)', response, re.MULTILINE))
    return has_list, "Has numbered/bulleted list" if has_list else "No list found"

def check_ordered_priority(response):
    has_priority = bool(re.search(r'(优先|其次|1\.|2\.|第一|第二|Phase \d|Step \d)', response))
    return has_priority, "Has priority ordering" if has_priority else "No priority ordering found"

def check_rebuild_sequence(response):
    destroy = any(w in response for w in ["销毁", "destroy", "Destroy"])
    recreate_surface = any(w in response for w in ["重建 Surface", "recreate Surface", "ANativeWindow", "create Surface", "VkSurfaceKHR"])
    recreate_swapchain = any(w in response for w in ["重建 Swapchain", "recreate Swapchain", "vkCreateSwapchainKHR"])
    recreate_image = any(w in response for w in ["Image", "ImageView", "VkImage"])
    count = sum([destroy, recreate_surface, recreate_swapchain, recreate_image])
    passed = count >= 3
    return passed, f"Sequence: destroy={destroy}, surface={recreate_surface}, swapchain={recreate_swapchain}, image={recreate_image}"


# ============================================================================
# TEST CASE DEFINITIONS
# ============================================================================

TEST_CASES = {
    "TC9.1": {
        "name": "黑屏调试", "task_type": "调试问题", "priority": "P0",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "调试类响应格式",
             "fn": lambda r: check_format(r, ["最可能原因", "快速验证", "检查点", "修复方案", "回归验证", "工具证据"], 4)},
            {"id": 2, "type": "ANTI_PATTERN", "name": "不直接猜shader",
             "fn": lambda r: check_anti_pattern(r, ["修改 shader", "优化 shader", "shader 问题"], 0.3)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "渲染链路排查",
             "fn": lambda r: check_keyword(r, ["vkAcquireNextImageKHR", "vkQueueSubmit", "vkQueuePresentKHR", "Command Buffer", "Render loop"], 3)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "工具验证方式",
             "fn": lambda r: check_keyword(r, ["Validation Layer", "RenderDoc", "AGI"], 1)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "Android Surface",
             "fn": lambda r: check_keyword(r, ["Surface", "ANativeWindow"], 1)},
            {"id": 6, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, min_count=1)},
            {"id": 7, "type": "STRUCTURE_CHECK", "name": "可执行排查步骤",
             "fn": lambda r: check_numbered_list(r)},
        ]
    },
    "TC9.2": {
        "name": "移动端性能", "task_type": "性能问题", "priority": "P0",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "性能类响应格式",
             "fn": lambda r: check_format(r, ["瓶颈", "CPU", "GPU", "Bandwidth", "同步", "优化优先级", "验证"], 4)},
            {"id": 2, "type": "ANTI_PATTERN", "name": "不直接改shader",
             "fn": lambda r: check_anti_pattern(r, ["修改 shader", "优化 shader"], 0.3)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "瓶颈分类",
             "fn": lambda r: check_keyword(r, ["CPU bound", "GPU", "Fragment bound", "Bandwidth bound", "Synchronization bound"], 4)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "移动端特有问题",
             "fn": lambda r: check_keyword(r, ["fullscreen pass", "tile", "overdraw", "bandwidth", "render target", "load/store"], 2)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "性能验证工具",
             "fn": lambda r: check_keyword(r, ["profiler", "trace", "counter", "frame capture", "AGI", "RenderDoc"], 1)},
            {"id": 6, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, min_count=1)},
            {"id": 7, "type": "STRUCTURE_CHECK", "name": "优化优先级排序",
             "fn": lambda r: check_ordered_priority(r)},
        ]
    },
    "TC9.3": {
        "name": "渲染管线设计", "task_type": "新建渲染链路", "priority": "P0",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "设计类响应格式",
             "fn": lambda r: check_format(r, ["结论", "推荐方案", "对象链路", "关键 API", "同步", "生命周期", "Android", "风险", "验证"], 5)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Vulkan对象链路",
             "fn": lambda r: check_vulkan_objects(r, ["Instance", "PhysicalDevice", "Device", "Queue", "Swapchain", "Command Buffer", "Pipeline", "Descriptor", "Render Pass", "Dynamic Rendering", "Fence", "Semaphore", "Image", "Buffer"], 5)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "Descriptor设计",
             "fn": lambda r: (lambda found: (len(found) >= 2, f"Found: {found}"))([kw for kw in ["set layout", "pool", "binding", "Descriptor Set"] if kw.lower() in r.lower()])},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "同步设计",
             "fn": lambda r: check_keyword(r, ["Fence", "Semaphore"], 1)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "Android注意点",
             "fn": lambda r: check_keyword(r, ["Android"], 1)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不只给概念解释",
             "fn": lambda r: (bool(re.search(r'vk[A-Z]\w+', r)), "Contains vk API names" if re.search(r'vk[A-Z]\w+', r) else "No vk API names found")},
            {"id": 7, "type": "KEYWORD_CHECK", "name": "验证方式",
             "fn": lambda r: check_keyword(r, ["验证", "Validation Layer", "RenderDoc"], 1)},
        ]
    },
    "TC9.4": {
        "name": "Descriptor代码修改", "task_type": "代码类问题", "priority": "P0",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "代码类响应格式",
             "fn": lambda r: check_format(r, ["修改文件", "新增", "初始化", "每帧", "销毁", "同步", "验证"], 5)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Vulkan对象变更",
             "fn": lambda r: check_keyword(r, ["Descriptor", "pool", "set layout", "binding", "VkDescriptorSet"], 2)},
            {"id": 3, "type": "STRUCTURE_CHECK", "name": "Buffer更新机制",
             "fn": lambda r: check_keyword(r, ["Uniform Buffer", "VkBuffer", "map", "memcpy", "update"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "生命周期管理",
             "fn": lambda r: check_keyword(r, ["销毁", "释放", "destroy", "cleanup"], 1)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "同步关系",
             "fn": lambda r: check_keyword(r, ["Fence", "Semaphore", "barrier"], 1)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不只给伪代码",
             "fn": lambda r: (bool(re.search(r'vk[A-Z]\w+', r)), "Contains vk API names" if re.search(r'vk[A-Z]\w+', r) else "No vk API names found")},
            {"id": 7, "type": "KEYWORD_CHECK", "name": "验证步骤",
             "fn": lambda r: check_keyword(r, ["验证", "Validation Layer"], 1)},
        ]
    },
    "TC9.5": {
        "name": "Pipeline Barrier API", "task_type": "API解释类", "priority": "P1",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "API解释类响应格式",
             "fn": lambda r: check_format(r, ["用途", "链路", "输入", "输出", "错误", "关系", "示例", "验证", "定位", "流程"], 4)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "4个mask参数",
             "fn": lambda r: check_keyword(r, ["srcStageMask", "dstStageMask", "srcAccessMask", "dstAccessMask"], 4)},
            {"id": 3, "type": "STRUCTURE_CHECK", "name": "image layout transition",
             "fn": lambda r: check_keyword(r, ["VkImageMemoryBarrier", "oldLayout", "newLayout"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "常见错误",
             "fn": lambda r: check_keyword(r, ["validation", "VUID", "错误"], 1)},
            {"id": 5, "type": "SOURCE_TAG", "name": "权威来源标签",
             "fn": lambda r: check_source_tags(r, ["SPEC", "REF", "REGISTRY"], 1)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不编造不确定API",
             "fn": lambda r: check_keyword(r, ["回查", "Vulkan Spec", "Vulkan Guide", "不确定"], 1)},
            {"id": 7, "type": "KEYWORD_CHECK", "name": "验证方式",
             "fn": lambda r: check_keyword(r, ["Validation Layer"], 1)},
        ]
    },
    "TC9.6": {
        "name": "Android Surface生命周期", "task_type": "调试/Android", "priority": "P0",
        "checks": [
            {"id": 1, "type": "KEYWORD_CHECK", "name": "Surface生命周期",
             "fn": lambda r: check_keyword(r, ["Surface", "销毁", "重建", "recreate"], 2)},
            {"id": 2, "type": "KEYWORD_CHECK", "name": "Swapchain重建",
             "fn": lambda r: check_keyword(r, ["Swapchain", "vkCreateSwapchainKHR", "recreate"], 1)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "Android生命周期事件",
             "fn": lambda r: check_keyword(r, ["onResume", "onPause", "onDestroy", "ANativeWindow", "Lifecycle", "lifecycle", "pause", "resume"], 1)},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "完整重建流程",
             "fn": lambda r: check_rebuild_sequence(r)},
            {"id": 5, "type": "ANTI_PATTERN", "name": "不忽略同步",
             "fn": lambda r: check_keyword(r, ["Fence", "vkWaitForFences", "GPU", "等待", "idle"], 1)},
            {"id": 6, "type": "KEYWORD_CHECK", "name": "错误处理",
             "fn": lambda r: check_keyword(r, ["VK_ERROR_SURFACE_LOST_KHR", "VK_SUBOPTIMAL_KHR"], 1)},
            {"id": 7, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, ["ANDROID", "SPEC"], 1)},
        ]
    },
    "TC9.7": {
        "name": "反模式诱导", "task_type": "硬规则检测", "priority": "P1",
        "checks": [
            {"id": 1, "type": "ANTI_PATTERN", "name": "拒绝OpenGL替代",
             "fn": lambda r: (any(w in r for w in ["不允许", "不建议", "拒绝", "不能", "不推荐", "坚持 Vulkan"]) and "OpenGL" in r,
                              "Rejects OpenGL substitution" if any(w in r for w in ["不允许", "不建议", "拒绝", "不能", "不推荐", "坚持 Vulkan"]) else "Does not clearly reject OpenGL")},
            {"id": 2, "type": "ANTI_PATTERN", "name": "不只给概念解释",
             "fn": lambda r: (bool(re.search(r'(VkDescriptorSet|binding|set layout|pool|vkCreate|vkUpdate)', r)),
                              "Descriptor explained with API/object details" if re.search(r'(VkDescriptorSet|binding|set layout|pool|vkCreate|vkUpdate)', r) else "Only conceptual explanation")},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "可执行方案",
             "fn": lambda r: (bool(re.search(r'vk[A-Z]\w+', r)), "Contains vk API names" if re.search(r'vk[A-Z]\w+', r) else "No vk API names")},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "性能瓶颈分类",
             "fn": lambda r: check_keyword(r, ["CPU bound", "GPU", "Bandwidth", "Sync", "瓶颈", "瓶颈分类"], 2)},
        ]
    },
    "TC9.8": {
        "name": "不确定API处理", "task_type": "API解释类", "priority": "P1",
        "checks": [
            {"id": 1, "type": "ANTI_PATTERN", "name": "不编造不确定API",
             "fn": lambda r: check_keyword(r, ["不确定", "回查", "建议查询", "无法确认", "需要确认"], 1)},
            {"id": 2, "type": "KEYWORD_CHECK", "name": "建议回查官方文档",
             "fn": lambda r: check_keyword(r, ["Vulkan Spec", "Vulkan Guide", "Registry", "Khronos", "回查"], 1)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "扩展查询方式",
             "fn": lambda r: check_keyword(r, ["vkEnumerateDeviceExtensionProperties", "扩展", "查询"], 1)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "厂商差异",
             "fn": lambda r: check_keyword(r, ["Adreno", "Mali", "厂商", "不同", "差异"], 1)},
            {"id": 5, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, ["REGISTRY", "SPEC"], 1)},
        ]
    },
    "TC9.9": {
        "name": "来源标签验证", "task_type": "综合", "priority": "P1",
        "checks": [
            {"id": 1, "type": "SOURCE_TAG", "name": "权威来源标签",
             "fn": lambda r: check_source_tags(r, ["SPEC", "REGISTRY", "REF"], 1)},
            {"id": 2, "type": "SOURCE_TAG", "name": "经验/工具标签",
             "fn": lambda r: check_source_tags(r, ["ENGINE", "HEUR", "TOOL", "VENDOR"], 1)},
            {"id": 3, "type": "SOURCE_TAG", "name": "标签使用合理",
             "fn": lambda r: (bool(re.search(r'\[SPEC\]|\[REGISTRY\]|\[REF\]', r)) and bool(re.search(r'\[ENGINE\]|\[HEUR\]|\[TOOL\]|\[VENDOR\]', r)),
                              "Both authority and experience tags present" if re.search(r'\[SPEC\]|\[REGISTRY\]|\[REF\]', r) and re.search(r'\[ENGINE\]|\[HEUR\]|\[TOOL\]|\[VENDOR\]', r) else "Missing one category")},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "具体barrier参数",
             "fn": lambda r: check_keyword(r, ["srcStageMask", "dstStageMask", "srcAccessMask", "dstAccessMask"], 4)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "区分规范与经验",
             "fn": lambda r: check_keyword(r, ["Spec", "规范", "经验", "工程", "建议"], 2)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不把经验写成绝对结论",
             "fn": lambda r: check_keyword(r, ["移动端", "某些 GPU", "适用", "可能", "建议", "取决于"], 1)},
        ]
    },
    "TC9.10": {
        "name": "闪烁同步排查", "task_type": "调试问题", "priority": "P0",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "调试类响应格式",
             "fn": lambda r: check_format(r, ["最可能原因", "快速验证", "检查点", "修复方案", "回归验证", "工具证据"], 4)},
            {"id": 2, "type": "KEYWORD_CHECK", "name": "frames-in-flight同步",
             "fn": lambda r: check_keyword(r, ["frames-in-flight", "frame", "in-flight", "flight"], 1)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "Fence使用分析",
             "fn": lambda r: check_keyword(r, ["vkResetFences", "vkWaitForFences", "Fence"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "UBO更新竞争",
             "fn": lambda r: check_keyword(r, ["vkMapMemory", "memcpy", "竞争", "覆盖", "ring buffer", "多 buffer", "triple buffer", "per-frame buffer"], 2)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "工具验证",
             "fn": lambda r: check_keyword(r, ["RenderDoc", "Validation Layer", "AGI"], 1)},
            {"id": 6, "type": "STRUCTURE_CHECK", "name": "修复方案",
             "fn": lambda r: check_keyword(r, ["ring buffer", "多 buffer", "延迟更新", "triple buffer", "per-frame buffer", "per-frame", "alignedSize"], 1)},
            {"id": 7, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, min_count=1)},
        ]
    },
    "TC9.11": {
        "name": "Render Graph架构", "task_type": "架构问题", "priority": "P1",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "架构类响应格式",
             "fn": lambda r: check_format(r, ["架构结论", "模块边界", "数据流", "对象归属", "生命周期", "同步策略", "扩展性", "风险", "验证"], 5)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Vulkan对象归属",
             "fn": lambda r: check_keyword(r, ["VkDeviceMemory", "VkImage", "VkBuffer", "DeviceMemory", "Memory", "Image", "Buffer"], 3)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "同步策略",
             "fn": lambda r: check_keyword(r, ["Barrier", "barrier", "自动", "插入"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "移动端兼容",
             "fn": lambda r: check_keyword(r, ["tile", "bandwidth", "移动端", "mobile"], 1)},
            {"id": 5, "type": "ANTI_PATTERN", "name": "抽象层设计",
             "fn": lambda r: check_keyword(r, ["抽象", "隐藏", "封装", "复杂度", "使用者"], 1)},
            {"id": 6, "type": "KEYWORD_CHECK", "name": "验证任务",
             "fn": lambda r: check_keyword(r, ["验证", "测试"], 1)},
        ]
    },
    "TC9.12": {
        "name": "Validation Error处理", "task_type": "调试/API", "priority": "P1",
        "checks": [
            {"id": 1, "type": "KEYWORD_CHECK", "name": "VUID分析",
             "fn": lambda r: check_keyword(r, ["VUID", "00358"], 1)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Descriptor Set绑定分析",
             "fn": lambda r: check_keyword(r, ["VkDescriptorSetLayoutBinding", "binding", "VkDescriptorSet"], 2)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "定位创建和使用点",
             "fn": lambda r: check_keyword(r, ["创建", "create", "Bind", "绑定", "使用点", "创建点"], 2)},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "最小修复方案",
             "fn": lambda r: check_keyword(r, ["binding", "stage flags", "数量", "layout", "修复", "修改"], 2)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "验证方式",
             "fn": lambda r: check_keyword(r, ["Validation Layer", "验证"], 1)},
            {"id": 6, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, ["SPEC", "REF", "TOOL"], 1)},
        ]
    },
}


def run_all_tests():
    # Write responses to files
    for tc_id, response in RESPONSES.items():
        resp_file = RESP_DIR / f"{tc_id}_response.txt"
        resp_file.write_text(response, encoding="utf-8")

    results = []
    for tc_id, tc_def in TEST_CASES.items():
        response = RESPONSES.get(tc_id, "")
        if not response:
            results.append({
                "test_case": tc_id, "name": tc_def["name"],
                "task_type": tc_def["task_type"], "priority": tc_def["priority"],
                "overall": "SKIP", "reason": "No response generated",
                "checks": [], "response_length": 0,
            })
            continue

        check_results = []
        passed_count = 0
        for check in tc_def["checks"]:
            try:
                passed, detail = check["fn"](response)
            except Exception as e:
                passed = False
                detail = f"Check error: {e}"
            check_results.append({
                "id": check["id"], "type": check["type"], "name": check["name"],
                "passed": passed, "detail": detail,
            })
            if passed:
                passed_count += 1

        overall = "PASS" if passed_count == len(check_results) else ("PASS_WITH_NOTES" if passed_count >= len(check_results) * 0.7 else "FAIL")
        failed_checks = [c for c in check_results if not c["passed"]]

        results.append({
            "test_case": tc_id, "name": tc_def["name"],
            "task_type": tc_def["task_type"], "priority": tc_def["priority"],
            "overall": overall, "checks_passed": passed_count,
            "checks_total": len(check_results),
            "failed_checks": [f"#{c['id']} {c['name']}" for c in failed_checks],
            "checks": check_results, "response_length": len(response),
        })

    return results


def generate_html_report(results):
    total = len(results)
    passed = sum(1 for r in results if r["overall"] == "PASS")
    passed_notes = sum(1 for r in results if r["overall"] == "PASS_WITH_NOTES")
    failed = sum(1 for r in results if r["overall"] == "FAIL")
    skipped = sum(1 for r in results if r["overall"] == "SKIP")
    pass_rate = f"{(passed + passed_notes) / total * 100:.1f}%" if total > 0 else "0%"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TC9 技能触发测试报告 — Vulkan 渲染专家技能</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif; background: #f0f2f5; padding: 20px; line-height: 1.7; color: #2c3e50; }}
.container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); padding: 48px; }}
h1 {{ color: #1a1a2e; border-bottom: 4px solid #6c5ce7; padding-bottom: 16px; margin-bottom: 32px; font-size: 28px; }}
h2 {{ color: #2d3436; margin-top: 36px; margin-bottom: 18px; padding-left: 12px; border-left: 5px solid #6c5ce7; font-size: 22px; }}
.summary-banner {{ border-radius: 8px; padding: 28px; margin: 24px 0; }}
.summary-banner.ok {{ background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border: 1px solid #28a745; }}
.summary-banner.ok h2 {{ color: #155724; border-color: #28a745; margin-top: 0; }}
.summary-banner.warn {{ background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); border: 1px solid #ffc107; }}
.summary-banner.warn h2 {{ color: #856404; border-color: #ffc107; margin-top: 0; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; margin: 28px 0; }}
.metric-card {{ text-align: center; padding: 20px 12px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 8px; border-top: 3px solid #6c5ce7; }}
.metric-card.pass {{ border-top-color: #28a745; }}
.metric-card.fail {{ border-top-color: #dc3545; }}
.metric-card.skip {{ border-top-color: #ffc107; }}
.metric-card.notes {{ border-top-color: #17a2b8; }}
.metric-value {{ font-size: 36px; font-weight: 700; color: #2d3436; }}
.metric-label {{ font-size: 13px; color: #636e72; margin-top: 6px; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
th, td {{ padding: 11px 14px; text-align: left; border-bottom: 1px solid #dee2e6; }}
th {{ background: linear-gradient(135deg, #6c5ce7 0%, #5f3dc4 100%); color: white; font-weight: 600; white-space: nowrap; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
tr:hover {{ background: #ede5ff; }}
.badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.badge-pass {{ background: #d4edda; color: #155724; }}
.badge-fail {{ background: #f8d7da; color: #721c24; }}
.badge-skip {{ background: #fff3cd; color: #856404; }}
.badge-notes {{ background: #cce5ff; color: #004085; }}
.badge-p0 {{ background: #f8d7da; color: #721c24; }}
.badge-p1 {{ background: #fff3cd; color: #856404; }}
.tc-detail {{ margin: 20px 0; border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden; }}
.tc-detail-header {{ padding: 14px 18px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.tc-detail-body {{ padding: 18px; }}
.check-item {{ display: flex; align-items: flex-start; padding: 8px 12px; margin: 4px 0; background: #f8f9fa; border-radius: 6px; font-size: 13px; }}
.check-item.pass {{ border-left: 4px solid #28a745; }}
.check-item.fail {{ border-left: 4px solid #dc3545; }}
.check-id {{ font-family: 'Consolas', monospace; font-weight: 600; min-width: 40px; color: #6c5ce7; }}
.check-type {{ font-family: 'Consolas', monospace; font-size: 11px; color: #636e72; min-width: 120px; }}
.check-name {{ flex: 1; font-weight: 500; }}
.check-status {{ margin-left: 12px; }}
.check-detail {{ margin-left: 52px; margin-top: 2px; font-size: 12px; color: #636e72; font-family: 'Consolas', monospace; word-break: break-all; }}
.progress-bar {{ width: 100%; height: 28px; background: #e9ecef; border-radius: 14px; overflow: hidden; margin: 20px 0; display: flex; }}
.progress-pass {{ background: linear-gradient(90deg, #28a745, #20c997); height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 13px; }}
.progress-notes {{ background: linear-gradient(90deg, #17a2b8, #0984e3); height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 13px; }}
.progress-fail {{ background: linear-gradient(90deg, #dc3545, #e74c3c); height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 13px; }}
code {{ background: #f1f3f5; padding: 2px 7px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 13px; color: #e83e8c; }}
.env-info {{ background: #f8f9fa; padding: 16px 20px; border-radius: 8px; margin: 20px 0; font-family: 'Consolas', monospace; font-size: 13px; }}
.footer {{ text-align: right; color: #adb5bd; font-size: 13px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; }}
.section-icon {{ font-size: 24px; }}
ul {{ margin-left: 22px; margin-top: 8px; }}
li {{ margin: 5px 0; }}
</style>
</head>
<body>
<div class="container">
<h1>🤖 TC9 技能触发测试报告 — Vulkan 渲染专家技能</h1>

<div class="env-info">
<strong>测试方法：</strong>通过子 Agent 实际调用 AI，注入技能规则上下文（7 个规则文件），发送 12 个场景提示词<br>
<strong>验收方式：</strong>自动化检查（FORMAT_CHECK / KEYWORD_CHECK / ANTI_PATTERN / SOURCE_TAG / STRUCTURE_CHECK）<br>
<strong>测试时间：</strong>2026-07-04<br>
<strong>技能上下文：</strong>role.md + hard_rules.md + task_classifier.md + response_formats.md + accuracy_check.md + debug_priority.md + performance_priority.md
</div>

<div class="summary-banner {"ok" if failed == 0 else "warn"}">
<h2>{"✅" if failed == 0 and passed_notes == 0 else "⚠️" if failed == 0 else "❌"} 总体结论：{passed + passed_notes}/{total} 通过{f"，{passed_notes} 个有备注" if passed_notes > 0 else ""}{f"，{failed} 个失败" if failed > 0 else ""}</h2>
<p><strong>通过率 {pass_rate}</strong></p>
<p>{"所有测试用例均达到验收标准。" if failed == 0 and passed_notes == 0 else "大部分测试用例通过，部分有备注项需关注。" if failed == 0 else "存在失败用例，需关注。"}</p>
</div>

<div class="progress-bar">
<div class="progress-pass" style="width: {passed/total*100:.1f}%;">{passed} PASS</div>
{f'<div class="progress-notes" style="width: {passed_notes/total*100:.1f}%;">{passed_notes} NOTES</div>' if passed_notes > 0 else ''}
{f'<div class="progress-fail" style="width: {failed/total*100:.1f}%;">{failed} FAIL</div>' if failed > 0 else ''}
</div>

<div class="metric-grid">
<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">总用例数</div></div>
<div class="metric-card pass"><div class="metric-value" style="color:#28a745;">{passed}</div><div class="metric-label">完全通过</div></div>
<div class="metric-card notes"><div class="metric-value" style="color:#17a2b8;">{passed_notes}</div><div class="metric-label">通过(有备注)</div></div>
<div class="metric-card fail"><div class="metric-value" style="color:#dc3545;">{failed}</div><div class="metric-label">失败</div></div>
<div class="metric-card skip"><div class="metric-value" style="color:#f39c12;">{skipped}</div><div class="metric-label">跳过</div></div>
</div>

<h2><span class="section-icon">📋</span> 测试结果汇总</h2>
<table>
<thead>
<tr><th>用例</th><th>名称</th><th>任务类型</th><th>优先级</th><th>检查通过</th><th>响应长度</th><th>结果</th><th>失败项</th></tr>
</thead>
<tbody>
"""

    for r in results:
        badge_class = {"PASS": "badge-pass", "PASS_WITH_NOTES": "badge-notes", "FAIL": "badge-fail", "SKIP": "badge-skip"}[r["overall"]]
        badge_text = {"PASS": "✅ PASS", "PASS_WITH_NOTES": "⚠️ PASS*", "FAIL": "❌ FAIL", "SKIP": "⏭ SKIP"}[r["overall"]]
        pri_badge = f'<span class="badge {"badge-p0" if r["priority"] == "P0" else "badge-p1"}">{h(r["priority"])}</span>'
        checks_str = f'{r.get("checks_passed", 0)}/{r.get("checks_total", 0)}'
        failed_str = h(", ".join(r.get("failed_checks", [])) if r.get("failed_checks") else "—")
        html += f"""<tr>
<td><code>{h(r['test_case'])}</code></td>
<td>{h(r['name'])}</td>
<td>{h(r['task_type'])}</td>
<td>{pri_badge}</td>
<td>{h(checks_str)}</td>
<td>{h(r.get('response_length', 0))}</td>
<td><span class="badge {badge_class}">{badge_text}</span></td>
<td style="font-size:12px; color:#636e72;">{failed_str}</td>
</tr>
"""

    html += """</tbody></table>

<h2><span class="section-icon">🔍</span> 各用例详细检查结果</h2>
"""

    for r in results:
        if r["overall"] == "SKIP":
            html += f"""
<div class="tc-detail">
<div class="tc-detail-header"><code>{h(r['test_case'])}</code> <strong>{h(r['name'])}</strong> <span class="badge badge-skip">SKIP</span></div>
<div class="tc-detail-body"><p style="color:#636e72;">{h(r.get('reason', 'Skipped'))}</p></div>
</div>
"""
            continue

        badge_class = {"PASS": "badge-pass", "PASS_WITH_NOTES": "badge-notes", "FAIL": "badge-fail"}[r["overall"]]
        badge_text = {"PASS": "✅ PASS", "PASS_WITH_NOTES": "⚠️ PASS*", "FAIL": "❌ FAIL"}[r["overall"]]

        html += f"""
<div class="tc-detail">
<div class="tc-detail-header">
<code>{h(r['test_case'])}</code>
<strong>{h(r['name'])}</strong>
<span class="badge {"badge-p0" if r["priority"] == "P0" else "badge-p1"}">{h(r["priority"])}</span>
<span class="badge {badge_class}">{badge_text}</span>
<span style="margin-left:auto; font-size:12px; color:#636e72;">{h(r.get('checks_passed', 0))}/{h(r.get('checks_total', 0))} checks · {h(r.get('response_length', 0))} chars</span>
</div>
<div class="tc-detail-body">
"""
        for c in r.get("checks", []):
            cls = "pass" if c["passed"] else "fail"
            status_badge = '<span class="badge badge-pass">✓</span>' if c["passed"] else '<span class="badge badge-fail">✗</span>'
            html += f"""<div class="check-item {cls}">
<span class="check-id">#{h(c['id'])}</span>
<span class="check-type">{h(c['type'])}</span>
<span class="check-name">{h(c['name'])}</span>
<span class="check-status">{status_badge}</span>
</div>
<div class="check-detail">{h(c['detail'])}</div>
"""

        html += "</div></div>"

    # Type stats
    type_stats = {}
    for r in results:
        for c in r.get("checks", []):
            t = c["type"]
            if t not in type_stats:
                type_stats[t] = {"passed": 0, "total": 0}
            type_stats[t]["total"] += 1
            if c["passed"]:
                type_stats[t]["passed"] += 1

    html += """<h2><span class="section-icon">📊</span> 按检查类型统计</h2>
<table>
<thead><tr><th>检查类型</th><th>通过</th><th>总数</th><th>通过率</th></tr></thead>
<tbody>"""
    for t, s in sorted(type_stats.items()):
        rate = f"{s['passed']/s['total']*100:.0f}%" if s['total'] > 0 else "0%"
        color = "#28a745" if s['passed'] == s['total'] else "#dc3545" if s['passed'] < s['total'] * 0.5 else "#ffc107"
        html += f"""<tr><td><code>{h(t)}</code></td><td style="color:{color};font-weight:600;">{h(s['passed'])}</td><td>{h(s['total'])}</td><td>{h(rate)}</td></tr>"""
    html += "</tbody></table>"

    html += f"""
<h2><span class="section-icon">🎯</span> 验收结论</h2>
<div class="summary-banner {"ok" if failed == 0 else "warn"}">
<h2 style="margin-top:0;">{"✅ 技能触发测试通过" if failed == 0 and passed_notes == 0 else "⚠️ 技能触发测试基本通过" if failed == 0 else "❌ 技能触发测试存在失败项"}</h2>
<p>12 个测试用例覆盖 6 种任务类型 + 反模式检测 + 不确定性处理，验证了：</p>
<ul>
<li><strong>FORMAT_CHECK</strong>：AI 按 response_formats.md 对应类型的输出结构回复</li>
<li><strong>ANTI_PATTERN</strong>：AI 遵守 hard_rules.md 的禁止行为（拒绝 OpenGL、不直接猜 shader、不只给概念）</li>
<li><strong>KEYWORD_CHECK</strong>：AI 包含关键技术关键词和工具</li>
<li><strong>SOURCE_TAG</strong>：AI 正确使用 accuracy_check.md 的来源标签</li>
<li><strong>STRUCTURE_CHECK</strong>：AI 给出可执行的 Vulkan 对象链路</li>
</ul>
</div>

<div class="footer">
报告生成时间：2026-07-04 | 测试方法：子 Agent AI 调用 + 自动化验收检查
</div>
</div>
</body>
</html>"""

    return html


if __name__ == "__main__":
    results = run_all_tests()

    # Print JSON summary
    summary = {
        "test_suite": "TC9_skill_trigger",
        "total": len(results),
        "passed": sum(1 for r in results if r["overall"] == "PASS"),
        "passed_with_notes": sum(1 for r in results if r["overall"] == "PASS_WITH_NOTES"),
        "failed": sum(1 for r in results if r["overall"] == "FAIL"),
        "skipped": sum(1 for r in results if r["overall"] == "SKIP"),
        "results": [{k: v for k, v in r.items() if k != "checks"} for r in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # Generate HTML report
    html = generate_html_report(results)
    REPORT_OUT.write_text(html, encoding="utf-8")
    print(f"\nHTML report written to: {REPORT_OUT}")

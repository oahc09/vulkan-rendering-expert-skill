# Workflow: Port ShaderToy To Vulkan

## 0. 适用范围

### 适用

- 已有 ShaderToy 效果（单文件 `mainImage` 或 `mainVR`），希望移植到本地 Vulkan 应用。
- 需要理解 ShaderToy 内置 uniform（iTime、iResolution、iMouse、iChannel*）如何映射到 Vulkan 的 UBO / push constant / texture。
- 需要实现 fullscreen quad、framebuffer 回读、ping-pong texture 等典型 ShaderToy 模式。

### 不适用

- 需要保留 ShaderToy 在线运行环境（本工作流针对本地 Vulkan 移植）。
- 效果依赖 WebGL 特定扩展或音频输入（需额外抽象）。
- 使用 compute shader 大规模粒子/RT 效果，需要额外光线追踪或计算管线设计。

---

## 1. 任务目标

将 ShaderToy 效果移植为本地 Vulkan 渲染器，完成：

```text
ShaderToy GLSL (mainImage / iChannel / iTime / iResolution)
→ 适配 Vulkan 的 GLSL（layout set/binding、UBO/push constant）
→ SPIR-V 编译
→ VkShaderModule
→ Pipeline + Descriptor
→ Fullscreen Quad or Compute Dispatch
→ Framebuffer / Ping-Pong Texture
→ Present
```

---

## 2. 输入条件

需要确认：

- 平台：Windows / Linux / Android。
- Vulkan 版本与是否使用 dynamic rendering。
- ShaderToy 效果类型：静态图片、时间动画、多 pass、需要 feedback / 历史帧。
- 是否需要 iChannel0/iChannel1 作为 texture 输入（图片、视频、噪声、上一帧）。
- 是否需要 iMouse 交互、iDate、iFrame 等额外 uniform。
- 输出目标：swapchain、offscreen texture、或保存为图片/视频。
- 是否要求实时 60 FPS 或允许离线逐帧渲染。

---

## 3. 前置检查

- [ ] Validation Layer 已启用 [TOOL]。
- [ ] RenderDoc / AGI 可抓帧 [TOOL]。
- [ ] ShaderToy 源码可编译为 SPIR-V（需适配 `mainImage` 入口与 uniform 布局）。
- [ ] 已确认 fullscreen quad 的 vertex buffer / pipeline 可用。
- [ ] 若使用 ping-pong texture，已确认两帧之间的同步方案。
- [ ] Android 端 `ANativeWindow` / surface 生命周期可追踪。

---

## 4. Vulkan 对象链路

```text
ShaderToy GLSL
→ glslangValidator / shaderc (with Vulkan target env)
→ SPIR-V Bytecode
→ VkShaderModule (Fragment)
→ VkShaderModule (Vertex for fullscreen quad)
→ VkDescriptorSetLayout
→ VkPipelineLayout
→ VkPipeline (Graphics)
→ VkDescriptorSet
→ UBO VkBuffer (iTime, iResolution, iMouse, iFrame)
→ VkImage / VkImageView / VkSampler (iChannel0~3)
→ Ping-Pong A/B Images (if feedback needed)
→ VkCommandBuffer
→ VkFramebuffer / Dynamic Rendering
→ VkSwapchainKHR → Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| fragment shader | `VkShaderModule` | ShaderToy mainImage | effect 生命周期 | 否 |
| vertex shader | `VkShaderModule` | fullscreen quad | effect 生命周期 | 否 |
| pipeline | `VkPipeline` | fullscreen pass | effect 生命周期 | 否（通常） |
| pipeline layout | `VkPipelineLayout` | descriptor + push | renderer 生命周期 | 否 |
| descriptor set layout | `VkDescriptorSetLayout` | binding 布局 | renderer 生命周期 | 否 |
| UBO | `VkBuffer` | `UNIFORM_BUFFER` | per-frame | 否 |
| iChannel texture | `VkImage` + `VkImageView` + `VkSampler` | `SAMPLED` | 资源生命周期 | 否 |
| ping-pong A/B | `VkImage` + `VkImageView` | `COLOR_ATTACHMENT \| SAMPLED` | per-frame 交替 | 是（若绑定 surface 尺寸） |
| output render target | `VkImage` / `VkImageView` | `COLOR_ATTACHMENT` | per-frame / swapchain | 是 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` | ShaderToyGlobals（iTime, iResolution, iMouse, iFrame, iDate） | Fragment |
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | iChannel0 | Fragment |
| set=1,binding=1 | `COMBINED_IMAGE_SAMPLER` | iChannel1 | Fragment |
| set=1,binding=2 | `COMBINED_IMAGE_SAMPLER` | iChannel2 | Fragment |
| set=1,binding=3 | `COMBINED_IMAGE_SAMPLER` | iChannel3 | Fragment |
| push constant | `VkPushConstantRange` | effect-specific override / pass index | Fragment |

ShaderToy uniform 映射说明：

- `iTime` / `iTimeDelta` / `iFrame` / `iDate` / `iResolution` / `iMouse` 放入 UBO，按 `std140` 布局 [SPEC]。
- 示例 UBO 布局：

```glsl
layout(set = 0, binding = 0) uniform ShaderToyGlobals {
    vec3  iResolution;
    float iTime;
    vec4  iMouse;
    float iTimeDelta;
    int   iFrame;
    vec4  iDate;
};
```

- `iChannel0~3` 映射为 `COMBINED_IMAGE_SAMPLER`，binding 0~3；sampler wrap/filter 用 `VkSamplerCreateInfo` 配置，对应 ShaderToy 的 `WrapMode` / `Filter` [HEUR]。
- 若 ShaderToy 使用 `iChannel0` 作为上一帧输出，则将该 channel 绑定到 ping-pong 纹理中上一帧完成的那一帧 [ENGINE]。
- 小型 per-pass 参数（如 pass index）可用 push constant，避免频繁更新 UBO [HEUR]。

Vertex shader 说明：

- ShaderToy 无显式 vertex shader；本地 Vulkan 需要一个生成 fullscreen quad 的 vertex shader，location 0 输出 clip-space position，location 1 输出 UV [ENGINE]。
- Fragment shader 的 `mainImage(out vec4 fragColor, in vec2 fragCoord)` 需要包装为 `void main()`，将 `fragCoord` 从 vertex shader 传入的 UV 乘以 `iResolution.xy` 得到 [ENGINE]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| CPU update | UBO | host write → `UNIFORM_READ` | fragment shader read |
| upload copy | iChannel texture | `TRANSFER_WRITE`；`TRANSFER_DST_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | fragment shader sample |
| previous frame graphics pass | ping-pong read source | `COLOR_ATTACHMENT_WRITE` → `SHADER_READ`；`COLOR_ATTACHMENT_OPTIMAL` → `SHADER_READ_ONLY_OPTIMAL` | current frame fragment sample |
| current frame fragment write | ping-pong write target / swapchain | `COLOR_ATTACHMENT_WRITE`；`UNDEFINED` → `COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` / `SHADER_READ_ONLY_OPTIMAL` | present / next frame sample |

必须说明：

- Ping-pong 需要两帧严格串行：第 N 帧读取第 N-1 帧的结果，写入第 N 帧目标；通过 `VkFence` 保证第 N-1 帧 GPU 完成后再读取 [SPEC]。
- 每帧开始时应将 ping-pong 写目标从 `UNDEFINED` transition 到 `COLOR_ATTACHMENT_OPTIMAL`（或 `LOAD` previous content，视效果需要保留历史） [SPEC]。
- 若效果不需要历史帧反馈，可直接渲染到 swapchain image，无需 ping-pong [HEUR]。
- `iTime` 等 uniform 每帧 CPU 更新后，必须确保 UBO 在 GPU 读取前已完成 host write；使用 coherent host-visible buffer 或显式 `vkFlushMappedMemoryRanges` [SPEC]。

---

## 8. 实现步骤

1. **适配 GLSL**：
   - 将 `void mainImage(out vec4 fragColor, in vec2 fragCoord)` 包装为 `void main()`。
   - 在 vertex shader 中生成 fullscreen quad，输出 `fragCoord = uv * iResolution.xy`。
   - 添加 `layout(set=0, binding=0) uniform ShaderToyGlobals`。
   - 为 `iChannel0~3` 添加 `layout(set=1, binding=N) uniform sampler2D iChannelN`。
2. **编译 SPIR-V**：使用 `glslangValidator -V` 或 shaderc，指定 Vulkan target env [TOOL]。
3. **创建 shader module**：`vkCreateShaderModule` 加载 vertex + fragment SPIR-V [SPEC]。
4. **创建 descriptor set layout**：包含 UBO（set=0,binding=0）与 4 个 combined image sampler（set=1,binding=0~3） [SPEC]。
5. **创建 pipeline layout**：组合 descriptor set layouts 与 push constant range [SPEC]。
6. **创建 graphics pipeline**：
   - vertex input：fullscreen quad 的 position + uv。
   - input assembly：triangle list。
   - viewport/scissor 设为 dynamic state。
   - color attachment format 与输出目标一致 [SPEC]。
7. **准备资源**：
   - 创建 per-frame UBO，映射 `ShaderToyGlobals`。
   - 加载 iChannel0~3 纹理，transition 到 `SHADER_READ_ONLY_OPTIMAL`。
   - 若需要 feedback，创建两张 ping-pong image（`COLOR_ATTACHMENT \| SAMPLED`）与对应 image view [ENGINE]。
8. **创建 sampler**：根据 ShaderToy 的 wrap/filter 配置 `addressModeUVW`、`magFilter`、`minFilter`、`mipmapMode`；噪声纹理常用 `NEAREST` [HEUR]。
9. **更新 descriptor set**：每帧或初始化时写入 UBO buffer info 与 image sampler info。
10. **录制每帧命令**：
   - 更新 UBO（iTime、iResolution、iMouse、iFrame）。
   - 若使用 ping-pong，transition 上一帧输出到 `SHADER_READ_ONLY_OPTIMAL`。
   - transition 当前输出目标到 `COLOR_ATTACHMENT_OPTIMAL`。
   - begin rendering / render pass，bind pipeline、descriptor set，设置 viewport/scissor，draw fullscreen quad（3 或 6 个顶点）。
   - end rendering，transition 输出到 `PRESENT_SRC_KHR` 或 `SHADER_READ_ONLY_OPTIMAL`（若继续作为下一帧输入）。
11. **提交与 present**：`vkQueueSubmit`（signal fence/semaphore）→ `vkQueuePresentKHR`。
12. **交换 ping-pong 指针**：每帧交换 read/write image view 绑定 [ENGINE]。
13. **接入 resize / recreate**：surface 尺寸变化时，重建 swapchain 与 ping-pong image（若尺寸相关），更新 `iResolution` UBO。
14. **接入销毁路径**：按 `pipeline → pipeline layout → descriptor set layout → shader module → image view → image → sampler → buffer` 顺序销毁 [ENGINE]。

---

## 9. Android 注意点

- 创建 ping-pong image 前必须确保 `ANativeWindow` / `VkSurfaceKHR` 已创建且 surface extent 有效；ping-pong image 尺寸通常与 surface extent 绑定 [ANDROID]。
- rotation / resize 后 surface extent 可能先变为 0，必须等待有效值再重建 swapchain 与 ping-pong image [ANDROID]。
- pause / resume 时保留 shader module、pipeline、pipeline cache；swapchain 与 ping-pong image 可在 resume 后延迟重建 [ANDROID]。
- 移动端 Mali/Adreno 对 fullscreen pass 的 bandwidth 敏感；若 ShaderToy 效果包含大量 texture fetch，建议使用 half-precision 或降低 offscreen target 分辨率 [ANDROID][HEUR]。
- 触摸屏 `iMouse` 坐标需要映射到 Vulkan framebuffer 坐标，注意 Android 坐标系 Y 轴方向与 ShaderToy 可能不同 [ANDROID]。
- AGI / logcat 验证：检查 fullscreen pass 的 GPU 耗时、texture bandwidth、`vkCmdDraw` 调用次数。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-vkCreateShaderModule-*`、`VUID-VkGraphicsPipelineCreateInfo-*`、`VUID-vkCmdDraw-*`、image layout / descriptor binding 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 fullscreen quad draw、descriptor binding、UBO 内容、iChannel 纹理内容 [TOOL]。
- [ ] 截图符合预期：与 ShaderToy 在线效果逐帧一致（允许浮点精度差异）。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出每帧 UBO 数据与 ping-pong 交换状态。
- [ ] 性能指标：
  - GPU frame time 稳定，fullscreen pass 耗时在目标帧率预算内；
  - AGI 中 texture bandwidth 未因过度 sampling 而异常 [TOOL]；
  - 移动端 Mali/Adreno 无 tile bandwidth 峰值 [ANDROID]。
- [ ] resize / pause / resume / rotation 后效果正常，iResolution 与 iMouse 映射正确。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`、flickering 或历史帧撕裂。

---

## 11. 常见失败模式

1. **`mainImage` 入口未适配为 `main`**：Vulkan fragment shader 必须包含 `void main()`，直接编译 ShaderToy 源码会失败 [SPEC]。
2. **`iResolution` 未更新或单位错误**：ShaderToy 使用像素坐标，vertex shader 传入的 UV 必须乘以 `iResolution.xy` 才能得到 `fragCoord` [ENGINE]。
3. **iChannel binding 错误**：`layout(set=1, binding=N)` 与 descriptor update 不一致，导致采样黑屏 [SPEC]。
4. **Ping-pong 同步缺失**：第 N 帧未等第 N-1 帧完成就读取，导致 flickering 或撕裂 [SPEC]。
5. **UBO 布局未对齐**：`std140` 要求 vec3 后接 float 必须按 16 字节对齐；错误布局导致 iTime / iMouse 数值错乱 [SPEC]。
6. **Swapchain image layout 错误**：渲染前未从 `UNDEFINED` / `PRESENT_SRC_KHR` transition 到 `COLOR_ATTACHMENT_OPTIMAL` [TOOL]。
7. **Y 轴方向未翻转**：本地 Vulkan framebuffer 的 Y 轴与 ShaderToy 的 `fragCoord.y` 方向可能相反，导致画面上下翻转 [ENGINE]。
8. **iMouse 坐标未映射**：Android 触摸坐标未转换为 framebuffer 坐标，交互位置偏移 [ANDROID]。
9. **Noise texture filter 错误**：ShaderToy 中 `iChannel` 的噪声图通常需要 `NEAREST` 采样，误用 `LINEAR` 会导致图案模糊 [HEUR]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/06_performance_symptoms/fullscreen_pass_cost.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- ShaderToy 源码链接或完整源码。
- 目标平台 / Vulkan 版本 / 是否使用 dynamic rendering。
- 是否需要 iChannel 输入、feedback / ping-pong、离线输出。
- 适配后的 GLSL 与 SPIR-V reflection。
- Validation Layer 完整报错。
- RenderDoc / AGI 中 fullscreen pass 的 pipeline state 与 descriptor binding。
- Android lifecycle 日志与 surface extent 变化。

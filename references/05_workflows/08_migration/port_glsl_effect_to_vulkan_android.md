# Workflow: Port GLSL Effect To Vulkan Android

## 0. 适用范围

### 适用

- 已有 GLSL 效果（如滤镜、后处理、粒子、UI shader），需要移植到 Android Vulkan 项目。
- 使用 `shaderc` 在运行时或离线将 GLSL 编译为 SPIR-V。
- 需要处理 Android 特有的 surface 生命周期、YUV/sRGB、swapchain、AGI 验证。

### 不适用

- 使用 HLSL/SLANG 为主的项目（应使用 `dxc` / `slangc`）。
- 纯 OpenGL ES 项目，不涉及 Vulkan。
- 使用引擎内置材质系统，无需手动管理 shaderc / descriptor / swapchain。

---

## 1. 任务目标

将一条 GLSL 效果完整移植到 Android Vulkan，完成：

```text
GLSL Source
→ shaderc / glslang 编译为 SPIR-V
→ VkShaderModule
→ DescriptorSetLayout / PipelineLayout
→ Pipeline（graphics 或 compute）
→ Swapchain / Surface / ANativeWindow 集成
→ Command Buffer 录制
→ AGI / logcat 验证
```

---

## 2. 输入条件

需要确认：

- 平台：Android API level、目标 Vulkan 版本、是否启用 `VK_KHR_swapchain`。
- GLSL 版本（如 `#version 320 es`）与目标 Vulkan SPIR-V 环境（如 `vulkan1.0` / `vulkan1.1`）。
- shaderc 集成方式：NDK 内置 `libshaderc`、Gradle 依赖、或离线 `glslangValidator`。
- 效果类型：fullscreen pass、mesh rendering、compute postprocess。
- 输入资源：uniform 数据、texture、sampler、storage image/buffer。
- 输出目标：swapchain image、offscreen texture、storage image。
- 颜色空间：sRGB framebuffer、YUV 视频纹理、HDR surface。
- 目标设备：Adreno / Mali / 其他，是否需要 tile-based GPU 优化。

---

## 3. 前置检查

- [ ] Validation Layer 可在 Android 上启用并输出到 logcat [TOOL]。
- [ ] AGI 可连接设备抓帧 [TOOL]。
- [ ] shaderc 编译链路可用，能在 Android 运行时将 GLSL 编译为 SPIR-V，或已有离线 SPIR-V 资源 [ANDROID]。
- [ ] `ANativeWindow` 已创建并可通过 `vkCreateAndroidSurfaceKHR` 创建 `VkSurfaceKHR` [SPEC]。
- [ ] swapchain recreate 路径已处理 rotation / resize。
- [ ] descriptor pool / set layout 容量满足效果需求。
- [ ] 目标 format（如 `VK_FORMAT_R8G8B8A8_SRGB`）受物理设备支持 [SPEC]。

---

## 4. Vulkan 对象链路

```text
GLSL Source / SPIR-V
→ shaderc::Compiler (Android NDK) 或离线 glslangValidator
→ SPIR-V Bytecode
→ VkShaderModule
→ VkDescriptorSetLayout(s)
→ VkPipelineLayout
→ VkPipeline (Graphics / Compute)
→ VkDescriptorSet
→ VkSampler + VkImageView
→ VkCommandBuffer
→ VkQueue
→ VkSwapchainKHR → Present
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| shader module | `VkShaderModule` | SPIR-V 容器 | effect 生命周期 | 否 |
| descriptor set layout | `VkDescriptorSetLayout` | binding 布局 | renderer 生命周期 | 否 |
| pipeline layout | `VkPipelineLayout` | descriptor + push constant | renderer 生命周期 | 否 |
| pipeline | `VkPipeline` | 完整管线状态 | effect 生命周期 | 否（通常） |
| uniform buffer | `VkBuffer` | `UNIFORM_BUFFER` | per-frame | 否 |
| input texture | `VkImage` + `VkImageView` | `SAMPLED` / `TRANSFER_DST` | 资源生命周期 | 否 |
| output render target | `VkImage` / `VkImageView` | `COLOR_ATTACHMENT` / `STORAGE` | per-frame / swapchain | 是（若绑定 surface） |
| sampler | `VkSampler` | 采样参数 | renderer 生命周期 | 否 |
| YUV conversion | `VkSamplerYcbcrConversion` + `VkSampler` | YUV → RGB 采样 | 资源生命周期 | 否 |

---

## 6. Pipeline / Descriptor 设计

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | `UNIFORM_BUFFER` / `UNIFORM_BUFFER_DYNAMIC` | per-frame / per-draw constants | Vertex / Fragment / Compute |
| set=1,binding=0 | `COMBINED_IMAGE_SAMPLER` | effect input texture | Fragment / Compute |
| set=1,binding=1 | COMBINED_IMAGE_SAMPLER（immutable YCbCr sampler +匹配image view） | YUV视频输入；普通分离sampler行不适用于此conversion路径 | Fragment [ANDROID] |
| set=2,binding=0 | `STORAGE_IMAGE` | compute 写入目标 | Compute |
| push constant | `VkPushConstantRange` | effect params / time / intensity | Vertex / Fragment / Compute |

设计说明：

- shaderc 编译 GLSL 时，必须通过 `shaderc_compile_options_set_target_env(options, shaderc_target_env_vulkan, target_version)` 指定 Vulkan 目标环境；显式设置目标用于可复现构建，不以未经核实的编译器默认值判断生成环境 [ANDROID]。
- GLSL `layout(set=N, binding=M)` 按DescriptorSet/Binding映射到兼容的descriptor set layout；不同set可复用binding号，不同shader stage也可共享同一set/binding，类型、数组容量与stage可见性须匹配 [SPEC]。
- Android YUV采样须查询并启用samplerYcbcrConversion，创建VkSamplerYcbcrConversion；VkSamplerYcbcrConversionInfo链接到sampler与image-view创建链，descriptor-set路径使用COMBINED_IMAGE_SAMPLER和pImmutableSamplers。不是把conversion info链到descriptor set layout。[SPEC][ANDROID]
- sRGB swapchain image 使用 `VK_FORMAT_R8G8B8A8_SRGB` 时，fragment 输出无需手动 gamma encode；若输出到 linear image 再 present，需手动做 sRGB 转换 [SPEC]。

---

## 7. 同步与 Layout 设计

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| shaderc 编译 / 离线加载 | shader module | 无同步 | `vkCreateShaderModule` 后只读使用 |
| CPU uniform upload | uniform buffer | host write → `UNIFORM_READ` | vertex / fragment / compute shader |
| upload copy / decode output | input texture | `TRANSFER_WRITE` / `VIDEO_DECODE_DST` → `SHADER_READ_ONLY_OPTIMAL` | fragment shader sample [ANDROID] |
| fragment shader write | color attachment | `COLOR_ATTACHMENT_WRITE`；`COLOR_ATTACHMENT_OPTIMAL` → `PRESENT_SRC_KHR` / `SHADER_READ_ONLY_OPTIMAL` | present / next pass |
| compute shader write | storage image | `SHADER_WRITE`；`UNDEFINED` → `GENERAL` | compute / graphics sample |

必须说明：

- uniform buffer 更新使用 per-frame buffer 或 `vkCmdUpdateBuffer` + barrier；避免在 GPU 读取时 CPU 覆盖同一 buffer [SPEC]。
- YUV 纹理的 layout 通常由 external format 决定；使用 `VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL` 或 `VK_IMAGE_LAYOUT_GENERAL` 需参考 `VkAndroidHardwareBufferFormatPropertiesANDROID` [ANDROID]。
- swapchain image 在 acquire 后通常为 `VK_IMAGE_LAYOUT_UNDEFINED`，需在 rendering begin 前 transition 到 `COLOR_ATTACHMENT_OPTIMAL` [SPEC]。

---

## 8. 实现步骤

1. **确认 shaderc 集成**：
   - 运行时编译：链接 NDK `libshaderc.so`，使用 `shaderc::Compiler` 将 GLSL 源码编译为 SPIR-V [ANDROID]。
   - 离线编译：在构建脚本中调用 `glslangValidator -V -o output.spv input.glsl`，运行时直接加载 SPIR-V 文件 [TOOL]。
2. **适配 GLSL**：
   - 添加 `#version 320 es` 或 `#version 450`。
   - 使用 `layout(set=, binding=)` 替代 OpenGL 的 `binding` / `location` 隐式规则。
   - 将 `uniform vec4 uColor` 等改为 UBO 或 push constant。
   - 纹理采样使用 `sampler2D` / `sampler2DShadow`；YUV 使用 `sampler2D` + YcbcrConversion sampler [ANDROID]。
3. **创建 shader module**：调用 `vkCreateShaderModule` 加载 SPIR-V 字节码 [SPEC]。
4. **创建 descriptor set layout**：根据 shader reflection 填写 `VkDescriptorSetLayoutBinding`；YUV使用combined image sampler和pImmutableSamplers；conversion info分别链接sampler与image view创建链，不能链到descriptor set layout [SPEC]。
5. **创建 pipeline layout**：组合 descriptor set layouts 与 push constant ranges [SPEC]。
6. **创建 pipeline**：
   - graphics：配置 vertex input、rasterizer、color blend、dynamic state；color attachment format 与 swapchain / offscreen format 一致 [SPEC]。
   - compute：调用 `vkCreateComputePipelines` [SPEC]。
7. **创建/绑定资源**：
   - 上传 uniform buffer 数据并更新 descriptor。
   - 加载 input texture 并 transition 到 `SHADER_READ_ONLY_OPTIMAL`。
   - 若使用 YUV 视频纹理，创建 `VkSamplerYcbcrConversion` 与专用 sampler [ANDROID]。
8. **录制 command buffer**：
   - acquire swapchain image。
   - barrier 转换 swapchain image layout。
   - begin rendering（dynamic rendering）或 begin render pass。
   - bind pipeline、descriptor set、push constant，设置 viewport/scissor，绘制 fullscreen quad 或 mesh。
   - end rendering，transition to `PRESENT_SRC_KHR`，submit，present。
9. **接入 resize / recreate**：rotation / resize 时 surface extent 变化，重建 swapchain、framebuffer、可能重建 pipeline（format 变化时）[ANDROID]。
10. **接入 Android 生命周期**：pause 时停止渲染循环，resume 时重建 surface/swapchain，destroy 时等待 GPU idle 后销毁资源 [ANDROID]。
11. **接入销毁路径**：按 `pipeline → pipeline layout → descriptor set layout → shader module → image view → image → sampler` 顺序销毁；YUV conversion 在对应 sampler 销毁后销毁 [ENGINE]。

---

## 9. Android 注意点

- `ANativeWindow` 必须在 `vkCreateAndroidSurfaceKHR` 调用时有效；surface 销毁后不可再使用对应 swapchain [ANDROID]。
- `onSurfaceCreated` / `onSurfaceChanged` / `onSurfaceDestroyed` 回调中必须同步渲染线程状态；在 surface 销毁前等待 `vkDeviceWaitIdle` [ANDROID]。
- rotation 后 surface extent 可能先变为 0 再变为新值；必须在 extent > 0 时才创建 swapchain，零extent时暂停创建/呈现并等待有效surface extent；违反有效使用不能预测某个固定VkResult，正常调用仍检查实际返回值 [ANDROID]。
- pause / resume 时保留 `VkPipeline` / `VkPipelineCache` 可显著降低恢复耗时；swapchain image 与 surface 必须重新创建 [ANDROID]。
- Android 10+ 相机/视频输出常为 YUV，使用 `VK_EXTERNAL_MEMORY_HANDLE_TYPE_ANDROID_HARDWARE_BUFFER_BIT_ANDROID` 导入时，必须查询 `VkAndroidHardwareBufferFormatPropertiesANDROID` 获取 format 与 YUV conversion 参数 [ANDROID]。
- sRGB 输出建议直接使用 `VK_COLOR_SPACE_SRGB_NONLINEAR_KHR` swapchain color space 与 `VK_FORMAT_R8G8B8A8_SRGB` format，避免在 shader 中手动 gamma 校正 [SPEC]。
- AGI / logcat 验证：在 Mali/Adreno 上检查 shader cycle count、texture bandwidth、pipeline 绑定耗时。

---

## 10. 验证方式

- [ ] Validation Layer clean：无 `VUID-VkShaderModuleCreateInfo-*`、`VUID-VkGraphicsPipelineCreateInfo-*`、`VUID-vkCmdDraw-*`、descriptor / image layout 错误 [TOOL]。
- [ ] RenderDoc / AGI：可见 shader module、descriptor binding、pipeline state、draw/dispatch 调用 [TOOL]。
- [ ] 截图符合预期：GLSL 效果在 Android 设备上输出与参考一致。
- [ ] logcat（Android）：`adb logcat -s vulkan` 无 validation error；可输出 shaderc 编译耗时、pipeline 创建耗时、swapchain recreate 次数。
- [ ] 性能指标：
  - shaderc 运行时编译耗时在首帧预期范围内，后续复用 cache；
  - GPU frame time 在目标设备上稳定；
  - AGI 中 Mali/Adreno 的 tile bandwidth、shader cycle count 符合预期；
  - 无 redundant pipeline / descriptor bind [TOOL]。
- [ ] resize / pause / resume / rotation 后渲染正常。
- [ ] 多帧运行稳定，无 `DEVICE_LOST` 或 ANR。

---

## 11. 常见失败模式

1. **shaderc 目标环境错误**：目标环境、SPIR-V版本或语言选项与目标设备不匹配；显式配置并记录编译器版本，用目标Vulkan环境验证模块，不把未显式设置直接等同OpenGL [ANDROID]。
2. **GLSL `set/binding` 未写**：OpenGL shader 移植到 Vulkan 后缺少 `layout(set=, binding=)`，descriptor layout 不匹配 [SPEC]。
3. **YUV sampler 未专用**：视频纹理使用普通 sampler，颜色空间或 chroma 采样错误 [ANDROID]。
4. **sRGB 输出错误**：在 linear render target 上手动 gamma 后又输出到 sRGB swapchain，导致双重 gamma [SPEC]。
5. **swapchain recreate 缺失**：rotation 后 surface extent 变化未重建 swapchain，呈现拉伸或 validation error [ANDROID]。
6. **uniform buffer 数据未对齐或越界**：UBO 成员布局需符合 `std140`，动态 UBO 偏移需满足 `minUniformBufferOffsetAlignment` [SPEC]。
7. **Surface 生命周期竞争**：`onSurfaceDestroyed` 后仍在提交 command buffer，导致 crash 或 `VK_ERROR_SURFACE_LOST_KHR` [ANDROID]。
8. **运行时 shaderc 阻塞主线程**：复杂 shader 编译耗时高，应在后台线程完成或使用离线 SPIR-V [HEUR]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/06_pipeline/graphics_pipeline.md`
- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/04_buffer_image_memory/image.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`
- `../../03_api_manual/02_surface_swapchain/swapchain.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md`
- `../../04_debug_playbooks/02_crash_hang/device_lost.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`
- `../../04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标 Android API level / GPU / Vulkan 版本。
- shaderc 集成方式与编译日志。
- GLSL 源码与生成 SPIR-V 的 reflection 输出。
- Validation Layer 完整报错。
- AGI 中 shader、pipeline state、descriptor binding 截图。
- `VkSwapchainCreateInfoKHR` 参数与 surface extent 日志。
- Android lifecycle 日志（surface create/destroy、pause/resume、rotation）。

<a id="android-ycbcr-descriptor-contract"></a>

## Android YCbCr import、conversion与descriptor合同

**条件**：Vulkan1.1或VK_KHR_sampler_ycbcr_conversion路径并启用samplerYcbcrConversion；AHB另需VK_ANDROID_external_memory_android_hardware_buffer及相关依赖。调用vkGetAndroidHardwareBufferPropertiesANDROID，获取memoryTypeBits/allocationSize与VkAndroidHardwareBufferFormatPropertiesANDROID（或可用的Properties2）输出，不能由Android版本或“YUV”名字猜format。

**正常路径**：具体VkFormat受支持时核对精确format/usage/tiling能力；若format=VK_FORMAT_UNDEFINED且只能走externalFormat，将返回的非零externalFormat通过VkExternalFormatANDROID用于image与conversion创建，遵守外部格式的usage、view与sampler限制。conversion model/range/chroma offsets/components按查询、来源颜色信息与支持条件匹配，suggested字段不是所有媒体颜色空间的普遍常量。选择过滤方式时核对对应YCbCr reconstruction/filter format features。

通过VkSamplerYcbcrConversionInfo把同一个或identically-defined conversion分别接到VkSamplerCreateInfo与VkImageViewCreateInfo.pNext。descriptor-set路径必须用COMBINED_IMAGE_SAMPLER，VkDescriptorSetLayoutBinding.pImmutableSamplers提供对应sampler；更新image view时必须匹配conversion。conversion info不接在set-layout链上，不能用一个独立SAMPLER descriptor代替此绑定模型。

**容量**：具体format的descriptor pool按VkSamplerYcbcrConversionImageFormatProperties.combinedImageSamplerDescriptorCount核算，不能固定一个YUV图像只消耗一个底层descriptor。Vulkan1.4/maintenance6路径可用maxCombinedImageSamplerDescriptorCount保守配置；Android externalFormat不能查询普通format的combinedImageSamplerDescriptorCount，该路径用maxCombinedImageSamplerDescriptorCount。缺少可核实容量信息时不猜值，先确认旧目标规范/实现的容量规则或回退可查询的普通RGBA路径。

**生命周期与同步**：import、conversion和descriptor创建不是生产者完成通知；遵守AHB生产者→Vulkan→消费者的所有权/外部同步合同，不能在camera/decoder还写入时采样。保持sampler/image-view/immutable绑定对象和imported memory在所需生命周期内有效，所有相关GPU使用结束后清理，不按单一API调用顺序推断已退役。

**失败/回退**：feature、format/filter、import内存或转换匹配失败时拒绝原路径，选择经授权且支持的普通RGBA预转换资源；受保护内容不得用host读回作为回退。不能编造固定VUID返回码或把未支持计为成功导入。

**验证**：覆盖具体format/externalFormat、缺少feature、sampler-view conversion不一致、池容量不足、chroma filter不支持及producer未完成；验证色条/范围/UV顺序与validation输出，未在设备运行只记未验证。

固定依据：[YCbCr conversion](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/samplers.adoc#samplers-YCbCr-conversion)、[descriptor allocation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/descriptorsets.adoc#descriptors-allocation)、[descriptor update](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/descriptorsets.adoc#descriptors-sets-updates)、[Android external formats](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory.adoc#memory-external-android-hardware-buffer-external-formats)。[SPEC]


v1.0.17定向事实复核依据（不代表全文全域认证）：[interfaces#interfaces-resources-setandbinding](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/interfaces.adoc#interfaces-resources-setandbinding)；[samplers#samplers-YCbCr-conversion](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/samplers.adoc#samplers-YCbCr-conversion)；[fundamentals#fundamentals-validusage](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/fundamentals.adoc#fundamentals-validusage)。[SPEC]

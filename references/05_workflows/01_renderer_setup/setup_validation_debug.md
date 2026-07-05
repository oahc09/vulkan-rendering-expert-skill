# Workflow: Setup Validation Debug

## 0. 适用范围

### 适用

- 需要在 Vulkan 开发阶段启用 validation layer 与 debug utils messenger。
- 需要为 Vulkan 对象命名、在 command buffer / queue 中插入 debug label，以便 RenderDoc / AGI / validation 日志可读。
- 需要捕获 instance 创建与销毁阶段的 validation message。
- 需要配置 best practices / synchronization validation 等子功能。

### 不适用

- 发布版本（shipping build）通常应关闭 validation layer 以减少开销 [ENGINE]。
- 目标平台未安装 validation layer（如某些精简 Android 系统） [ANDROID]。
- 使用第三方框架已内置调试封装，无需手动配置 messenger。

---

## 1. 任务目标

建立 Vulkan 调试基础设施：

```text
Instance Extensions
→ VK_EXT_debug_utils
Instance Layers
→ VK_LAYER_KHRONOS_validation
VkDebugUtilsMessengerCreateInfoEXT
→ vkCreateDebugUtilsMessengerEXT
→ 回调函数输出 message
→ vkSetDebugUtilsObjectNameEXT / vkCmdBeginDebugUtilsLabelEXT
→ RenderDoc / AGI / logcat 可读
```

---

## 2. 输入条件

需要确认：

- 平台：Android / Windows / Linux / 其他。
- Vulkan 版本。
- 是否启用 validation layer（开发/调试/发布）。
- 需要捕获的 message severity：`VERBOSE` / `INFO` / `WARNING` / `ERROR` [SPEC]。
- 需要捕获的 message type：`GENERAL` / `VALIDATION` / `PERFORMANCE` / `BEST_PRACTICES` [SPEC]。
- 是否需要启用 best practices 或 synchronization validation 子功能 [TOOL]。
- 是否需要为对象命名 / 打 label。
- 日志输出目标：console、logcat（Android）、文件、IDE 输出窗口。

---

## 3. 前置检查

- [ ] `VK_EXT_debug_utils` 在 instance extension 列表中 [SPEC]。
- [ ] `VK_LAYER_KHRONOS_validation` 在 instance layer 列表中（或平台等效 layer） [TOOL]。
- [ ] 已准备 `PFN_vkCreateDebugUtilsMessengerEXT` / `PFN_vkDestroyDebugUtilsMessengerEXT` / `PFN_vkSetDebugUtilsObjectNameEXT` 等函数指针 [SPEC]。
- [ ] 已设计回调函数，处理 `VkDebugUtilsMessengerCallbackDataEXT` 中的 `messageIdName`、`pMessage`、`pObjects` [SPEC]。
- [ ] RenderDoc / AGI 可识别 debug utils label 与 object name [TOOL]。
- [ ] Android 端 logcat 可过滤 `vulkan` 或自定义 tag [ANDROID]。

---

## 4. Vulkan 对象链路

```text
VkInstanceCreateInfo
→ ppEnabledExtensionNames 包含 VK_EXT_debug_utils
→ ppEnabledLayerNames 包含 VK_LAYER_KHRONOS_validation
→ pNext 指向 VkDebugUtilsMessengerCreateInfoEXT
    → messageSeverity
    → messageType
    → pfnUserCallback
    → pUserData
→ vkCreateInstance
→ vkCreateDebugUtilsMessengerEXT
→ VkDebugUtilsMessengerEXT
→ 回调函数接收 message

关键对象命名：
VkDevice / VkQueue / VkSwapchainKHR / VkImage / VkImageView / VkBuffer / VkPipeline / VkDescriptorSet / VkRenderPass / VkFramebuffer
→ vkSetDebugUtilsObjectNameEXT
→ RenderDoc / AGI / Validation 输出显示名称

Command Buffer / Queue Label：
Render Pass / Draw / Dispatch / Barrier
→ vkCmdBeginDebugUtilsLabelEXT / vkCmdEndDebugUtilsLabelEXT
→ vkQueueBeginDebugUtilsLabelEXT / vkQueueEndDebugUtilsLabelEXT
→ 工具时间线分组
```

---

## 5. 资源设计

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| debug utils messenger | `VkDebugUtilsMessengerEXT` | 接收 validation / debug message | instance 生命周期 | 否 |
| validation layer | instance layer | API 使用校验 | instance 生命周期 | 否 |
| object name | 调试标注 | 对象可读名称 | 对象生命周期 | 否 |
| command buffer label | 调试标注 | 时间线分组 | command buffer 录制期 | 否 |
| queue label | 调试标注 | frame / submit 分组 | queue 提交期 | 否 |
| custom tag | 调试标注 | 附加自定义数据 | 对象生命周期 | 否（可选） |

---

## 6. Pipeline / Descriptor 设计

本 workflow 不直接创建 graphics/compute pipeline，但 `VkDebugUtilsMessengerCreateInfoEXT` 的 `messageType` 与 `VkValidationFeaturesEXT` 会影响 validation 对 pipeline / descriptor 的检查范围：

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| 无 | `VkValidationFeaturesEXT` 启用 `BEST_PRACTICES` | 检测 pipeline 创建、descriptor 更新中的非最优用法 [TOOL] | 全局 |
| 无 | `VkValidationFeaturesEXT` 启用 `SYNCHRONIZATION_VALIDATION` | 检测 pipeline barrier / image layout / semaphore 同步 hazard [TOOL] | 全局 |
| 无 | `VkDebugUtilsObjectNameInfoEXT` | 为 pipeline / descriptor set / layout 命名 | 调试 |

设计说明：

- `messageSeverity` 至少包含 `VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT` 和 `VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT` [GUIDE]。
- `messageType` 建议包含 `VALIDATION` 与 `PERFORMANCE`；开发后期可加入 `BEST_PRACTICES` [GUIDE]。
- 通过 `VkValidationFeaturesEXT` pNext 链可显式启用/禁用子功能；Vulkan 1.1+ 推荐 [TOOL]。

---

## 7. 同步与 Layout 设计

本 workflow 不直接操作 image layout，但 `SYNCHRONIZATION_VALIDATION` 会检查命令之间的同步关系：

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| 任意写入命令 | buffer / image | 未正确 barrier 或 layout transition | validation 报错 [TOOL] |
| acquire semaphore | swapchain image | 未等待 imageAvailableSemaphore 就写入 | `VUID-vkQueueSubmit-*-semaphore` 错误 [SPEC] |
| previous draw | color attachment | 未 transition 到 `SHADER_READ_ONLY_OPTIMAL` 就采样 | synchronization validation warning [TOOL] |

必须说明：

- debug utils label 与对象命名本身不提供同步，仅用于调试可视化 [SPEC]。
- 启用 `SYNCHRONIZATION_VALIDATION` 后，validation layer 会额外分析 command buffer 内的 hazard；可能增加 CPU 开销，开发阶段使用 [TOOL]。

---

## 8. 实现步骤

1. **确认扩展与 layer 可用**：
   - 调用 `vkEnumerateInstanceExtensionProperties` 检查 `VK_EXT_debug_utils` [SPEC]。
   - 调用 `vkEnumerateInstanceLayerProperties` 检查 `VK_LAYER_KHRONOS_validation` [SPEC]。
2. **配置 instance create info**：
   - `ppEnabledExtensionNames` 加入 `VK_EXT_debug_utils` [SPEC]。
   - `ppEnabledLayerNames` 加入 `VK_LAYER_KHRONOS_validation`（开发时） [TOOL]。
   - 创建 `VkDebugUtilsMessengerCreateInfoEXT`，填写 `messageSeverity`、`messageType`、`pfnUserCallback`、`pUserData` [SPEC]。
   - 可选创建 `VkValidationFeaturesEXT`，启用 `BEST_PRACTICES` / `SYNCHRONIZATION_VALIDATION` / `GPU_ASSISTED` 等 [TOOL]。
   - 将 `VkDebugUtilsMessengerCreateInfoEXT` 挂入 `VkInstanceCreateInfo.pNext`，以捕获 `vkCreateInstance` 和 `vkDestroyInstance` 阶段的消息 [SPEC]。
3. **创建 instance**：调用 `vkCreateInstance` [SPEC]。
4. **加载函数指针**：通过 `vkGetInstanceProcAddr` 获取 `vkCreateDebugUtilsMessengerEXT`、`vkDestroyDebugUtilsMessengerEXT`、`vkSetDebugUtilsObjectNameEXT`、`vkCmdBeginDebugUtilsLabelEXT` 等 [SPEC]。
5. **创建 debug messenger**：填写 `VkDebugUtilsMessengerCreateInfoEXT`（可与 instance 创建时相同），调用 `vkCreateDebugUtilsMessengerEXT` [SPEC]。
6. **实现回调函数**：
   - 根据 `messageSeverity` 决定输出级别（error / warning / info） [SPEC]。
   - 输出 `pCallbackData->pMessage`、`messageIdName`、对象列表 `pObjects` [SPEC]。
   - Android 端通过 `__android_log_print` 输出到 logcat [ANDROID]。
   - 生产环境可忽略非 ERROR 级别，但开发时建议保留 WARNING [GUIDE]。
7. **为关键对象命名**：
   - 对长生命周期、高价值对象调用 `vkSetDebugUtilsObjectNameEXT`：device、queues、swapchain images、pipelines、descriptor set layouts、render passes、framebuffers、command pools [ENGINE]。
   - 确保 `objectType` 与对象真实类型一致，`objectHandle` 不截断（32-bit 平台注意） [SPEC]。
8. **在 command buffer 中插入 label**：
   - 每个 render pass / 关键 draw / dispatch / barrier 范围使用 `vkCmdBeginDebugUtilsLabelEXT` / `vkCmdEndDebugUtilsLabelEXT` [TOOL]。
   - 确保 begin/end 成对、嵌套后进先出 [TOOL]。
9. **在 queue 提交前后插入 label（可选）**：
   - 使用 `vkQueueBeginDebugUtilsLabelEXT` / `vkQueueEndDebugUtilsLabelEXT` 标记 frame 边界 [TOOL]。
10. **对象标签（可选）**：使用 `vkSetDebugUtilsObjectTagEXT` 为对象附加自定义数据 [SPEC]。
11. **接入销毁路径**：
    - 在 `vkDestroyInstance` 之前调用 `vkDestroyDebugUtilsMessengerEXT` [SPEC]。
    - 保留 `VkDebugUtilsMessengerCreateInfoEXT` 在 instance pNext 中，可在 instance 销毁阶段继续捕获消息 [SPEC]。

---

## 9. Android 注意点

- Android Studio / adb logcat 中过滤 `vulkan` tag 可查看 validation message；建议在回调中追加自定义 tag 以区分来源 [ANDROID]。
- 部分 Android 设备未预装 Khronos validation layer，需通过 `android_mk` 或 Gradle 将 `libVkLayer_khronos_validation.so` 打包到 APK [ANDROID]。
- AGI 对 `VK_EXT_debug_utils` label 支持良好，可直接在 GPU 时间线上查看 frame/pass/draw 分组 [TOOL]。
- 对象命名对移动端 GPU 调试帮助很大，因为 handle 本身无意义 [ENGINE]。
- 避免在渲染循环中频繁分配对象名称字符串，减少 CPU overhead；建议使用字符串常量或池 [ENGINE]。
- `onPause` / `onResume` 不影响 debug messenger 生命周期，但 surface 销毁后不应再输出依赖 surface 对象的调试信息 [ANDROID]。
- 启用 `GPU_ASSISTED` validation 可能对移动端性能产生明显影响，仅在必要时开启 [ANDROID]。

---

## 10. 验证方式

- [ ] Validation Layer clean：回调中无 `ERROR` 级别消息；开发阶段允许 `WARNING` 但需逐一确认 [TOOL]。
- [ ] RenderDoc / AGI：Resource Inspector 中可见对象名称；Event Browser / Frame 时间线中可见 command buffer / queue label [TOOL]。
- [ ] logcat（Android）：`adb logcat -s vulkan` 或自定义 tag 可看到格式化 validation message；message 中包含 `messageIdName` 与对象名。
- [ ] 性能指标：
  - 启用 validation 后帧时间增加在预期范围（通常 10%–50%，视场景与 layer 子功能而定）；
  - 未出现因回调函数低效导致的 CPU 瓶颈；
  - 对象命名 / label 调用不造成显著开销 [TOOL]。
- [ ] 多帧运行稳定，无 `DEVICE_LOST`。
- [ ] 销毁路径无 validation error 或 crash。

---

## 11. 常见失败模式

1. **扩展未启用**：instance create info 中未加入 `VK_EXT_debug_utils`，导致 `vkCreateDebugUtilsMessengerEXT` 不可用 [TOOL]。
2. **函数指针获取错误**：未使用 `vkGetInstanceProcAddr` 或获取了错误签名的函数指针 [SPEC]。
3. **Messenger 创建时机错误**：在 `vkCreateInstance` 之后才创建 messenger，漏掉 instance 创建阶段的消息 [SPEC]。
4. **回调函数崩溃**：在回调中访问了已被销毁的 `pUserData` 或执行了非线程安全操作 [ENGINE]。
5. **objectType 填错**：导致 RenderDoc 无法显示名称或 validation message 中对象类型错误 [TOOL]。
6. **objectHandle 截断**：32-bit 平台上将 64-bit handle 强转为 32-bit 指针 [TOOL]。
7. **Label begin/end 不匹配**：command buffer 中 label 嵌套顺序错误，RenderDoc / AGI 时间线显示异常 [TOOL]。
8. **Layer 未打包（Android）**：APK 中缺少 validation layer 库，导致 layer 未启用 [ANDROID]。
9. **Severity 过滤过严**：只保留 ERROR，漏掉 WARNING / PERFORMANCE 提示 [GUIDE]。
10. **销毁顺序错误**：在 `vkDestroyInstance` 之后销毁 messenger [SPEC]。

---

## 12. 相关 API 卡片

- `../../03_api_manual/09_debug_validation/debug_utils.md`
- `../../03_api_manual/09_debug_validation/validation_layer.md`
- `../../03_api_manual/09_debug_validation/vuid_decode.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`
- `../../03_api_manual/03_command_buffer/queue_submit.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 13. 相关 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本。
- `vkEnumerateInstanceExtensionProperties` / `vkEnumerateInstanceLayerProperties` 输出。
- `VkDebugUtilsMessengerCreateInfoEXT` 的 `messageSeverity` / `messageType` 配置。
- 回调函数实现与输出样例。
- 出现 validation error 时的完整 message（含 `messageIdName`、`pMessage`、`pObjects`）。
- RenderDoc / AGI 中对象名称与 label 的显示情况。
- Android logcat 过滤输出。

---

## 15. 需要回查官方文档的情况

1. 不同 Vulkan SDK 版本中 validation layer 子功能（`BEST_PRACTICES`、`SYNCHRONIZATION_VALIDATION`、`GPU_ASSISTED`）的启用方式差异。
2. `VkDebugUtilsMessengerCallbackDataEXT` 中 `pObjects` 与 `objectCount` 的精确语义。
3. 32-bit 平台上 `VkDebugUtilsObjectNameInfoEXT.objectHandle` 的处理细节。
4. Android 打包 validation layer 的最新推荐方式（Gradle / CMake / android_mk）。
5. 不同工具（RenderDoc / AGI / Nsight / Xcode GPU Frame Capture）对 debug utils label 嵌套深度与名称长度的支持差异。

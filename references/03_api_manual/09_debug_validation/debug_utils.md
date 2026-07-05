# API Card: VK_EXT_debug_utils

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 调试链 |
| Vulkan 对象 | `VkDebugUtilsMessengerEXT` / `VkDebugUtilsObjectNameInfoEXT` / `VkDebugUtilsLabelEXT` |
| 常用 API | `vkCreateDebugUtilsMessengerEXT` / `vkDestroyDebugUtilsMessengerEXT` / `vkSetDebugUtilsObjectNameEXT` / `vkSetDebugUtilsObjectTagEXT` / `vkQueueBeginDebugUtilsLabelEXT` / `vkQueueEndDebugUtilsLabelEXT` / `vkCmdBeginDebugUtilsLabelEXT` / `vkCmdEndDebugUtilsLabelEXT` / `vkCmdInsertDebugUtilsLabelEXT` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ANDROID] [GUIDE] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 / 扩展 |

---

## 1. 一句话定位

`VK_EXT_debug_utils` 是 Vulkan 的调试标注扩展，除了输出 validation message，还支持为对象命名/打标签、在 queue 和 command buffer 中插入时间标签，使 RenderDoc / AGI / validation 日志中的对象具有可读性。[SPEC]

---

## 2. 所属对象链路

```text
VkInstance（启用 VK_EXT_debug_utils）
→ VkDebugUtilsMessengerEXT
→ vkSetDebugUtilsObjectNameEXT / vkSetDebugUtilsObjectTagEXT
→ vkQueueBeginDebugUtilsLabelEXT / vkQueueEndDebugUtilsLabelEXT
→ vkCmdBeginDebugUtilsLabelEXT / vkCmdEndDebugUtilsLabelEXT
→ RenderDoc / AGI / Validation 输出
```

### 上游依赖

- Instance 已启用 `VK_EXT_debug_utils`。[SPEC]
- 要命名的对象已创建。[SPEC]
- Debug messenger 已创建（若需接收消息）。[SPEC]

### 下游影响

- 工具中对象名称可读，便于定位资源。[TOOL]
- 事件时间线可折叠分组，便于分析帧结构。[TOOL]
- Validation message 可直接关联到具体对象与场景。[TOOL]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkDebugUtilsMessengerEXT`
- `VkDebugUtilsMessengerCreateInfoEXT`
- `VkDebugUtilsObjectNameInfoEXT`
- `VkDebugUtilsObjectTagInfoEXT`
- `VkDebugUtilsLabelEXT`
- `VkDebugUtilsMessengerCallbackDataEXT`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateDebugUtilsMessengerEXT` | 创建 messenger。[SPEC] |
| `vkDestroyDebugUtilsMessengerEXT` | 销毁 messenger。[SPEC] |
| `vkSetDebugUtilsObjectNameEXT` | 为对象设置可读名称。[SPEC] |
| `vkSetDebugUtilsObjectTagEXT` | 为对象附加自定义标签数据。[SPEC] |
| `vkQueueBeginDebugUtilsLabelEXT` | 在 queue 上开始标签范围。[SPEC] |
| `vkQueueEndDebugUtilsLabelEXT` | 结束 queue 标签范围。[SPEC] |
| `vkCmdBeginDebugUtilsLabelEXT` | 在 command buffer 中插入开始标签。[SPEC] |
| `vkCmdEndDebugUtilsLabelEXT` | 结束 command buffer 标签范围。[SPEC] |
| `vkCmdInsertDebugUtilsLabelEXT` | 在 command buffer 中插入即时标签。[SPEC] |

### 相关扩展 / 版本

- `VK_EXT_debug_utils`：现代统一调试扩展，推荐优先使用。[SPEC]
- `VK_EXT_debug_marker`：旧版调试标注扩展，已被 `VK_EXT_debug_utils` 取代。[SPEC]
- Android 是否可用：是。[ANDROID]

---

## 4. 标准使用流程

```text
vkCreateInstance 启用 VK_EXT_debug_utils
→ vkCreateDebugUtilsMessengerEXT
→ 对关键对象调用 vkSetDebugUtilsObjectNameEXT（device, queue, swapchain image, pipeline, descriptor set 等）
→ 可选对对象调用 vkSetDebugUtilsObjectTagEXT 附加自定义数据
→ 录制 command buffer 时调用 vkCmdBeginDebugUtilsLabelEXT / vkCmdEndDebugUtilsLabelEXT 标记 render pass / draw 范围
→ queue 提交前后使用 vkQueueBeginDebugUtilsLabelEXT / vkQueueEndDebugUtilsLabelEXT 标记 frame 边界
→ 在 RenderDoc / AGI 中按标签折叠时间线
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `VkDebugUtilsObjectNameInfoEXT.objectType` | 必须与对象真实类型匹配。[SPEC] | `objectType` 填错导致工具无法解析或显示错误名称。[TOOL] |
| `VkDebugUtilsObjectNameInfoEXT.objectHandle` | 64-bit handle，注意 32/64-bit 转换。[SPEC] | 在 32-bit 平台上截断 handle。[TOOL] |
| `VkDebugUtilsObjectNameInfoEXT.pObjectName` | 建议使用稳定唯一命名。[SPEC] | 重复名称导致工具混淆。[TOOL] |
| `VkDebugUtilsLabelEXT.pLabelName` | 标签名会显示在工具时间线。[SPEC] | 标签过长或嵌套过深影响可读性。[HEUR] |
| `VkDebugUtilsMessengerCreateInfoEXT.messageSeverity` | 控制 messenger 输出级别。[SPEC] | 与对象命名无关但常一起配置时误设。[TOOL] |
| `VkDebugUtilsMessengerCreateInfoEXT.messageType` | 是否启用 `PERFORMANCE` / `BEST_PRACTICES`。[SPEC] | 未启用导致漏掉最佳实践提示。[GUIDE] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否在 instance 层启用了 `VK_EXT_debug_utils`？
- [ ] 是否为关键对象设置了名称？
- [ ] `objectType` 是否与对象类型一致？
- [ ] `objectHandle` 是否正确，无截断？

### 使用阶段

- [ ] 标签是否成对出现（begin/end）？
- [ ] 嵌套标签是否满足后进先出？
- [ ] 标签名称是否表达清晰语义？

### 销毁阶段

- [ ] messenger 是否在 `vkDestroyInstance` 前销毁？
- [ ] 对象销毁后其名称是否仍被调试工具错误引用？

---

## 7. 高频错误

1. 未在 instance extension 中启用 `VK_EXT_debug_utils`。[TOOL]
2. `objectType` 填错导致 RenderDoc 无法显示名称。[TOOL]
3. `objectHandle` 在 32-bit 平台上被截断。[TOOL]
4. 标签 begin/end 不匹配或嵌套顺序错误。[TOOL]
5. 给所有对象命名造成不必要的 CPU 开销。[ENGINE]
6. 在 command buffer 标签中放动态字符串导致分配/拷贝开销。[ENGINE]
7. 误以为 object name 会影响运行期行为（它只是调试标注）。[HEUR]

---

## 8. Debug 检查路径

### Validation Layer

- 检查 `VUID-vkSetDebugUtilsObjectNameEXT-*` 等合法性。[SPEC]
- 检查 messenger 回调输出中的 object name 是否正确。[TOOL]

### RenderDoc / AGI

- RenderDoc：Resource Inspector 中查看对象名称；Event Browser 中查看 command buffer 标签。[TOOL]
- AGI：Frame 时间线中查看 queue/command buffer label，定位 frame 边界与 pass 范围。[TOOL]

### 日志 / 代码检查

- 检查 `vkSetDebugUtilsObjectNameEXT` 调用是否覆盖关键对象。
- 检查 label begin/end 是否成对。
- 检查 `objectType` 枚举值是否与对象一致。

---

## 9. 生命周期风险

### 创建时机

- Instance 创建时启用 extension。[SPEC]
- Messenger 在 instance 创建后创建。[SPEC]
- 对象名称在对象创建后、使用前设置。[SPEC]

### 使用时机

- Command buffer 标签在录制阶段插入。
- Queue 标签在 queue 提交前后使用。

### 销毁时机

- Messenger 在 `vkDestroyInstance` 前销毁。[SPEC]
- 对象名称随对象销毁而失效（工具不应在对象销毁后引用）。[HEUR]

### in-flight 风险

- Command buffer 标签被提交后，在 GPU 完成前不应修改 command buffer；但标签本身不改变资源状态。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- 对象命名是 CPU 侧操作，不涉及 GPU 同步。[SPEC]
- Queue 标签是 CPU 侧调用，但会影响工具显示的时间线。[TOOL]

### GPU-GPU 同步

- 标签命令在 command buffer 中按提交顺序执行，不引入额外同步。[SPEC]

### 资源访问同步

- 标签不影响资源状态；不要依赖标签做 barrier 或同步。[HEUR]

---

## 11. Android 注意点

- AGI 对 debug utils label 支持良好，可直接在 GPU 时间线上查看 frame/pass/draw 分组。[TOOL]
- logcat 中不会直接输出 label，但 validation message 中的 object name 会显示。[ANDROID]
- 对象命名对移动端 GPU 调试帮助很大，因为 handle 本身无意义。[ENGINE]
- 避免在渲染循环中频繁分配对象名称字符串，减少 CPU overhead。[ENGINE]

---

## 12. 性能注意点

### CPU 侧

- 对象命名和标签会增加少量 CPU 开销，通常在可接受范围；避免每帧给大量对象动态命名。[ENGINE]
- Command buffer 标签字符串拷贝会引入开销，建议使用字符串池或常量。[ENGINE]

### GPU 侧

- Debug utils 本身对 GPU 执行影响很小，但某些工具可能因标注增加 capture 大小。[HEUR]

### 移动端

- 控制标签嵌套深度，避免工具 UI 卡顿。[HEUR]
- 避免在 frame 内频繁切换 label，保持时间线清晰。[ENGINE]

---

## 13. 专家经验

**经验**：
为所有“长生命周期、高价值”对象命名：logical device、queues、swapchain images、pipelines、descriptor set layouts、render passes、framebuffers、command pools。在 command buffer 中为每个 render pass 和关键 draw/dispatch 范围加 label，使 RenderDoc / AGI 时间线一眼可读。对频繁创建/销毁的动态资源（如每帧 uniform buffer）不必逐个命名，可用 pool 或 allocator 级标签。

**适用条件**：
中大型项目、多 pass、资源数量多、团队协作。

**不适用情况**：
一次性 demo、资源极少、无工具调试需求。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `validation_layer.md`
- `vuid_decode.md`
- `../03_command_buffer/command_buffer.md`
- `../06_pipeline/graphics_pipeline.md`
- `../02_surface_swapchain/swapchain.md`

---

## 15. 需要回查官方文档的情况

1. `VkDebugUtilsObjectNameInfoEXT` 对各类 Vulkan 对象的 `objectType` 映射。
2. `vkSetDebugUtilsObjectTagEXT` 的 tag 数据大小与工具支持限制。
3. 不同工具（RenderDoc / AGI / Nsight）对 label 嵌套深度与名称长度的支持差异。
4. Best Practices layer 与 debug utils 的交互规则。
5. 32-bit 平台上 `objectHandle` 的处理细节。

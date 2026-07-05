# API Card Writing Rules

> 文件建议路径：`api_card_writing_rules.md`

---

## 1. 写作原则

1. 不复制官方文档全文。
2. 不逐字段翻译 Spec。
3. 不写无法验证的结论。
4. 所有硬规则必须有来源等级。
5. 每张卡片必须说明所属对象链路。
6. 每张卡片必须说明高频错误。
7. 每张卡片必须说明 Debug 检查路径。
8. 涉及资源访问时必须说明同步 / layout 风险。
9. 涉及 Android 时必须说明 Surface / Swapchain 生命周期。
10. 性能建议必须标注适用条件，不能绝对化。
11. 不确定 API 细节时，必须提示回查官方 Spec / Reference Page。
12. 示例代码不是必需项；如果写代码，必须说明对象生命周期和验证方式。

---

## 2. 来源等级定义

API 卡片中的 `来源等级` 必须统一使用以下标签：

```text
[SPEC]     Vulkan Specification / Reference Pages 明确要求
[GUIDE]    Vulkan Guide / Khronos Tutorial / Samples 建议
[ANDROID]  Android NDK / Android Game Vulkan / AGI 文档
[TOOL]     Validation Layer / RenderDoc / AGI 可验证
[ENGINE]   图形引擎工程经验
[HEUR]     启发式经验，需要结合项目判断
```

建议规则：

```text
硬规则必须来自 [SPEC] / [ANDROID] / [TOOL]
默认建议可以来自 [GUIDE] / [ENGINE]
性能经验必须标注 [ENGINE] 或 [HEUR]
```

---

## 3. 卡片长度建议

| 卡片类型 | 建议长度 |
|---|---|
| 简单对象卡 | 300～700 中文字 |
| 核心对象卡 | 700～1500 中文字 |
| 高风险对象卡 | 1500～2500 中文字 |
| 复杂专题卡 | 可拆分为多张卡，不建议单卡过长 |

高风险对象包括：

- Swapchain
- Command Buffer
- Image / Image Layout
- Descriptor
- Pipeline
- Barrier / Synchronization
- Android Surface / ANativeWindow
- Validation / VUID

---

## 4. API Card 编写流程

每写一张 API 卡片，按以下步骤执行：

```text
1. 判断 API 所属链路。
2. 填一句话定位。
3. 画对象链路。
4. 写标准使用流程。
5. 写关键字段。
6. 写高频错误。
7. 写 Debug 检查路径。
8. 写生命周期风险。
9. 写同步风险。
10. 写 Android 注意点。
11. 写性能注意点。
12. 标注来源等级。
13. 关联其他 API 卡片。
```

---

## 5. API Card 必须避免的问题

### 避免 1：写成教程

错误写法：

```text
Vulkan 是一个现代低开销图形 API……
```

更好写法：

```text
本卡关注 VkImage 在资源链中的角色：创建、绑定内存、创建 ImageView、layout transition、作为 attachment/sampled/storage 使用。
```

### 避免 2：只讲 API，不讲链路

错误写法：

```text
vkUpdateDescriptorSets 用于更新 descriptor set。
```

更好写法：

```text
vkUpdateDescriptorSets 处在 shader binding → descriptor layout → descriptor set → resource → shader access 链路中。
```

### 避免 3：只讲正确流程，不讲错误

每张卡片必须包含高频错误和 Debug 检查路径。

### 避免 4：把经验写成绝对规则

错误写法：

```text
移动端不能使用多 pass。
```

更好写法：

```text
移动端多 pass 可能增加 bandwidth 和 tile resolve 成本，需要结合目标 GPU、render target 尺寸、load/store 策略和 AGI counter 验证。
```

---

## 6. 与 Debug Playbook 的联动规则

API 手册要为后续 `04_debug_playbooks` 提供可引用材料。

例如：

```text
black_screen.md
应引用：
- surface.md
- swapchain.md
- command_buffer.md
- queue_submit.md
- graphics_pipeline.md
- descriptor_set.md
- image.md
```

```text
descriptor_binding_error.md
应引用：
- descriptor_set_layout.md
- descriptor_set.md
- descriptor_update.md
- pipeline_layout.md
- shader_module.md
```

```text
swapchain_recreate_crash.md
应引用：
- android_surface.md
- anativewindow.md
- swapchain.md
- swapchain_recreate.md
- command_buffer_lifetime.md
- fence.md
```

---

## 7. 首批建议编写的 API 卡片

P0 优先级：

```text
surface.md
swapchain.md
swapchain_recreate.md
command_buffer.md
queue_submit.md
image.md
image_view.md
descriptor_set.md
descriptor_update.md
pipeline_layout.md
graphics_pipeline.md
fence.md
semaphore.md
pipeline_barrier.md
synchronization2.md
validation_layer.md
debug_utils.md
vuid_decode.md
android_surface.md
anativewindow.md
```

这些卡片覆盖大多数 Vulkan 工程问题。

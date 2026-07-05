# 03_api_manual：Vulkan API 专家手册模块

## 1. 模块定位

`03_api_manual` 是 Vulkan Expert Skill 的 API 专家手册模块。

它不复制官方 Vulkan Spec，也不按字母表罗列所有 `vkXXX` API，而是按 Vulkan 工程链路组织 API 卡片。

本模块目标是让 AI 在处理 Vulkan 工程问题时，能够准确判断：

- 当前 API / 对象属于哪条 Vulkan 链路。
- 它依赖哪些上游对象。
- 它影响哪些下游对象。
- 它的生命周期风险在哪里。
- 它是否涉及同步、layout transition、descriptor、pipeline、Android surface/swapchain 等问题。
- 遇到错误时应该怎么排查和验证。

---

## 2. 模块边界

### 本模块负责

- API / Vulkan 对象的专家化整理。
- 对象链路说明。
- 标准使用流程。
- 高频错误。
- Debug 检查路径。
- 生命周期风险。
- 同步风险。
- Android 注意点。
- 性能注意点。
- 来源等级标注。

### 本模块不负责

- 完整翻译 Vulkan Spec。
- 逐字段复制官方 Reference Page。
- 编写完整教程。
- 编写完整工程代码。
- 替代官方文档查询。

---

## 3. 推荐目录结构

```text
03_api_manual/
├── README.md
├── api_card_template.md
├── api_card_writing_rules.md
├── api_index.md
├── lifecycle_index.md
├── error_index.md
│
├── 01_instance_device_queue/
├── 02_surface_swapchain/
├── 03_command_buffer/
├── 04_buffer_image_memory/
├── 05_descriptor/
├── 06_pipeline/
├── 07_rendering/
├── 08_synchronization/
├── 09_debug_validation/
└── 10_android_platform/
```

---

## 4. API Card 核心关键词

每张 API 卡片围绕 6 个关键词展开：

```text
定位
链路
流程
风险
排查
验证
```

也就是：

> 这个 API / 对象是什么、在哪条链路上、怎么用、哪里容易错、怎么排查、怎么验证。

---

## 5. 与前置模块关系

```text
00_expert_entry
定义专家行为控制。

01_source_map_and_api_manual_strategy
定义来源可信等级、引用规则和更新策略。

02_core_mental_model
定义 Vulkan 对象链路、帧生命周期、资源生命周期和同步模型。

03_api_manual
把 Vulkan API 转化成可工程落地的专家卡片。
```

模块 4 必须承接模块 2 的来源等级规则，也必须复用模块 3 的对象链路和生命周期模型。

# Tool Usage for Vulkan Debug

> 文件建议路径：`tool_usage.md`

---

## 1. Validation Layer

### 适合发现

- API valid usage 错误
- Descriptor binding 错误
- Image layout 错误
- CommandBuffer 状态错误
- 资源生命周期错误
- 部分同步 hazard
- VUID 相关问题

### 重点观察

- VUID
- object handle
- object type
- command name
- queue / command buffer state
- descriptor / image / buffer / pipeline layout 相关字段

### 使用规则

1. 调试 Vulkan 正确性问题时优先开启。
2. 不要只看最后一条错误，要从第一条错误开始处理。
3. 提取 VUID 后回查 Vulkan Spec / Reference Page。
4. Validation clean 不等于视觉和性能一定正确。

---

## 2. RenderDoc

### 适合发现

- 是否真的存在 draw call / dispatch call
- Pipeline 是否绑定
- Vertex / Index / Uniform 数据是否正确
- Descriptor 是否绑定正确资源
- Render target 是否有输出
- Texture 内容是否正确
- Pass 前后结果是否符合预期

### 重点观察

- Event Browser
- Pipeline State
- Bound Resources
- Texture Viewer
- Mesh Viewer
- Resource Inspector

### 使用规则

1. 黑屏问题优先抓一帧。
2. 先看是否有 draw call，再看 draw call 是否有像素输出。
3. 有 draw call 但无输出时，再查 viewport、scissor、depth、descriptor、shader、render target。
4. 后处理问题重点看 pass 输入和输出贴图。

---

## 3. AGI

### 适合发现

- Android GPU frame capture
- GPU counter
- 帧耗时
- bandwidth / texture sampling / fragment 负载
- Android 平台相关性能问题
- Surface / swapchain 路径异常

### 重点观察

- Frame timeline
- GPU counters
- Render pass / command buffer
- Bandwidth 相关指标
- Texture / attachment 访问情况
- Android logcat 关联信息

### 使用规则

1. Android 性能问题优先考虑 AGI。
2. 后处理成本高时重点看 fullscreen pass、render target 尺寸、load/store、bandwidth。
3. pause/resume/rotation 问题结合 logcat 和 capture 判断资源是否重建。

---

## 4. logcat / Native Log

### 适合发现

- Surface lifecycle
- ANativeWindow 状态
- Vulkan API 返回值
- swapchain recreate 路径
- pause / resume
- thread 状态
- crash stack

### 使用规则

1. Android Vulkan 问题必须保留关键 API 返回值日志。
2. surface created / changed / destroyed 必须有日志。
3. swapchain recreate 前后必须记录尺寸、format、image count。
4. crash 问题优先结合 tombstone / native stack。


## 5. 工具能力矩阵与版本留证（2026-10-17）

每次记录 SDK、VVL build/revision、RenderDoc、AGI、shader 编译器/SPIR-V Tools、OS/GPU/driver 版本。针对实际使用路径填写“支持 / 不支持 / 未核验”，不要用工具名称作保证：

| 路径 | core validation | sync validation | GPU-AV | capture/replay | descriptor 解码 | 目标设备输出对照 |
|---|---|---|---|---|---|---|
| 传统 sets / indexing | 按版本实测 | 按配置实测 | 按 shader 能力实测 | 按版本实测 | 按版本实测 | 待提供 |
| descriptor buffer | 按版本查证 | 按版本查证 | 不假设覆盖 | 不假设支持 | 不假设可读 | 待提供 |
| descriptor heap / AHB | 按版本查证 | 按版本查证 | 不假设覆盖 | 不假设支持 | 不假设可读 | 待提供 |

Validation clean 只说明当前配置、版本与执行路径没有报告已覆盖错误。捕获工具可能改变执行和时序；先检查支持列表及最小 capture/replay，再依赖其状态视图。性能结论必须来自关闭 validation/GPU-AV 的可比较运行，不能从工具启动成功推导正确性。

SDK 工具变化单独记录：[LunarG release notes](https://vulkan.lunarg.com/doc/view/latest/windows/release_notes.html) 宣布 1.4.363 引入 vkprofiles，并计划下一 SDK 移除 gen_profiles；不能把计划写成已发生。迁移前核对本地帮助、安装版本和官方命令语法，不猜 CLI 替换。

参考：[VVL GPU-AV](https://github.com/KhronosGroup/Vulkan-ValidationLayers/blob/main/docs/gpu_validation.md)、[同步验证](https://github.com/KhronosGroup/Vulkan-ValidationLayers/blob/main/docs/syncval_usage.md)。

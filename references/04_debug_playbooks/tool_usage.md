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

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


<a id="mobile-profiler-contract"></a>
## 6. 移动端采集入口与证据能力（2026-11-01）

先记录设备/OS/GPU/driver、API与启用features、工具精确版本/channel、应用构建SHA、授权/权限、
选中场景与导出格式。下表是选择协议，不是全部设备支持表。[ANDROID][TOOL]

| 工具/入口 | 可取得的证据（须实际确认） | 不能由入口存在推导 |
|---|---|---|
| Android CLI 1.1.16717390（2026-10）`android profiler systemtrace` | 已授权连接目标上的系统时序/调度 trace；参数以安装版本帮助为准 | 不自动取得 GPU bandwidth counter、逐 draw 资源或源码根因 |
| 同版本 `android profiler heapdump capture`；`android profiler session list/status/terminate` | JVM heap dump 与采集 session 管理；按用途选择，不混作 GPU 显存分析 | JVM heap 不能证明全部 native/GPU 内存；不能编造 CLI flag |
| APA System Profiler / Frame Profiler | 分别确认系统trace分析和具体frame资源/调用分析能力、stable/beta/canary版本 | 系统trace可读不等于frame replay、扩展解码或全部counter可用 |
| 既有 AGI / RenderDoc | 对实际支持的设备/API路径做最小capture/replay，再依赖相应事件/资源视图 | build成功、工具连接成功、同品牌其他设备成功均非本设备通过 |
| 无可用 profiler | 已有 logcat、CPU单调时钟、支持的GPU timestamp/query、提交ID和最小复现 | 没有counter不等于没有带宽问题；仅列待测假设，不填虚构数据 |

最小证据链：症状/设备状态 → trace时间段 → process/thread/frame → queue submission / resource ID →
源码路径/函数 → 最小改动 → 同条件 A/B。GPU counter 必须保留实际名称、单位、采样范围与可用性；
未采集时标“未取得”，不能把 system trace 推断包装成测量。[ENGINE]

默认只使用已授权本地设备与本地日志；云设备付费、账号登录和私有 trace 上传需要另行授权。
采集开销与正常性能分别报告。持续性能和生成帧口径见
[持续性能](../05_workflows/07_optimization/optimize_frame_time.md#sustained-mobile-performance)，
fault记录见 [资源级取证](02_crash_hang/device_lost.md#mobile-fault-evidence)。

来源：[CLI 10月release](https://developer.android.com/tools/agents/android-cli/release-notes)、
[2026-10-28 工具介绍](https://developer.android.com/blog/posts/android-dev-summit-26-developer-tools-performance)、
[APA release notes](https://developer.android.com/android-performance-analyzer/release-notes)。
上述为文档核验，不表示本环境安装或运行了这些工具。

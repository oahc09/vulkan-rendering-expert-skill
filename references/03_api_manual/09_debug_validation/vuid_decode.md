# API Card: VUID 解码与定位

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 调试链 |
| Vulkan 对象 | 概念（VUID / `VkDebugUtilsMessengerCallbackDataEXT`） |
| 常用 API | `vkCreateDebugUtilsMessengerEXT` / 回调数据解析 |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [GUIDE] [ENGINE]` |
| 适用 Vulkan 版本 | 通用 |

---

## 1. 一句话定位

VUID（Vulkan Unique ID）是 Vulkan 规范为每条 Valid Usage 规则分配的唯一标识符，解析 VUID 可快速定位触发条件、涉及对象与根因，是 validation layer 排错的核心入口。[SPEC]

---

## 2. 所属对象链路

```text
Validation Message
→ Message ID / VUID
→ VUID 前缀与结构解析
→ 对应 Vulkan Spec 章节
→ 触发对象与调用栈
→ 根因定位与修复
```

### 上游依赖

- Validation layer 已启用并输出消息。[SPEC]
- 应用产生触发条件的 API 调用。[SPEC]
- Debug utils messenger 已正确配置以接收完整回调数据。[TOOL]

### 下游影响

- 决定代码修复方向。[ENGINE]
- 决定同步、生命周期或参数调整策略。[ENGINE]
- 形成项目级 VUID 知识库。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- VUID 字符串（概念）
- `VkDebugUtilsMessengerCallbackDataEXT`
- `VkDebugUtilsMessengerCallbackDataEXT.pMessageIdName`
- `VkDebugUtilsMessengerCallbackDataEXT.pMessage`
- `VkDebugUtilsMessengerCallbackDataEXT.objectCount` / `pObjects`
- `VkDebugUtilsMessengerCallbackDataEXT.queueLabelCount` / `cmdBufLabelCount`

### 常用 API / 概念

| API/概念 | 作用 |
|---|---|
| VUID 编码规则 | 解析 message ID 的结构。[SPEC] |
| `vkCreateDebugUtilsMessengerEXT` | 获取带 VUID 的回调。[SPEC] |
| `VkDebugUtilsMessengerCallbackDataEXT` | 回调数据中包含 VUID、对象、标签。[SPEC] |

### 相关扩展 / 版本

- 与 `VK_EXT_debug_utils` / `VK_EXT_debug_report` 配合接收消息。[SPEC]
- 不依赖特定 Vulkan 版本。[SPEC]

---

## 4. 标准使用流程

```text
收到 validation message
→ 提取 message ID / VUID（如 VUID-vkCmdDraw-None-02674）
→ 拆分前缀：VUID- + 对象/命令- + 子对象- + 数字
→ 在 Vulkan Spec 或 validation layer 源码中检索 VUID
→ 查看触发条件与 required behavior
→ 根据 message 中 object handle / object type 定位具体对象
→ 结合 queue labels / command buffer labels 定位发生场景
→ 修复并复测
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| VUID 前缀 `VUID-` | 标识这是规范 Valid Usage ID。[SPEC] | 与实现内部 ID 混淆。[TOOL] |
| `VUID-VkXXX-vkCmdYYY-zzzzz` | 对象-命令-子对象-数字结构。[SPEC] | 只看数字忽略结构，导致检索困难。[TOOL] |
| `pMessageIdName` | 回调中的 VUID 字符串。[SPEC] | 某些旧版 layer 或特殊路径可能为空。[TOOL] |
| `pMessage` | 完整人类可读描述。[SPEC] | 不读完整消息直接搜索，遗漏上下文。[TOOL] |
| `objectCount` / `pObjects` | 关联的 Vulkan 对象。[SPEC] | 未利用 object handle 定位。[TOOL] |
| `queueLabelCount` / `cmdBufLabelCount` | 当前 queue/command buffer label。[SPEC] | 未开启 label 导致上下文缺失。[TOOL] |
| `severity` / `type` | 判断 `ERROR` / `WARNING` / `PERFORMANCE`。[SPEC] | 忽略 `PERFORMANCE` / `BEST_PRACTICES`。[GUIDE] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否启用了 debug utils messenger？
- [ ] 回调数据是否完整获取？
- [ ] 是否为关键对象设置了名称以便定位？

### 使用阶段

- [ ] 是否优先处理 `ERROR` severity？
- [ ] 是否提取并记录 VUID？
- [ ] 是否利用 object handle 和 label 定位上下文？

### 销毁阶段

- [ ] 是否需要持久化 validation log 供后续分析？

---

## 7. 高频错误

1. 只读 message 文本，不提取 VUID，导致无法精确检索规范。[TOOL]
2. 忽略 object handle，无法定位具体资源。[TOOL]
3. 未开启 command buffer label，导致无法知道错误发生在哪个 pass/draw。[TOOL]
4. 将 `WARNING` / `PERFORMANCE` 当 `ERROR` 处理，浪费时间。[ENGINE]
5. 在回调中直接崩溃而丢失后续 VUID。[ENGINE]
6. 对同一 VUID 的多次出现重复调查，未建立 VUID 知识库。[ENGINE]
7. 误把 validation layer 实现细节当规范行为。[HEUR]
8. 不重视 `VUID-undefined`，它通常表示 validation layer 无法给出精确 VUID。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- 从回调数据提取 VUID、`object type`/`handle`、labels。[TOOL]
- 按 severity 过滤，优先处理 ERROR。[TOOL]
- 在 Vulkan Spec 中搜索 VUID，查看触发条件。[SPEC]

### RenderDoc / AGI

- 用 object handle 找到对应 resource。[TOOL]
- 用 command buffer label 定位事件。[TOOL]
- 检查触发点的 pipeline / descriptor / image layout。[TOOL]

### 日志 / 代码检查

- 在代码中搜索触发 VUID 的 API 调用。
- 检查调用顺序与参数。
- 检查对象生命周期与同步。

---

## 9. 生命周期风险

### 创建时机

- VUID 解析能力在调试阶段建立，无需运行时创建。[ENGINE]

### 使用时机

- 每次收到 validation message 时解析使用。

### 销毁时机

- 无特定销毁对象，但调试配置应在 Release 中移除。[ENGINE]

### in-flight 风险

- 无。

---

## 10. 同步风险

### CPU-GPU 同步

- 解析 VUID 是离线分析，不影响同步。[HEUR]

### GPU-GPU 同步

- 不涉及。

### 资源访问同步

- VUID 常指向同步错误，但解析本身不改变同步。[HEUR]

---

## 11. Android 注意点

- Android 上 validation message 通常输出到 logcat，VUID 可能在多行日志中被截断；建议使用完整回调保存到文件。[ANDROID]
- AGI 可捕获 validation message 并与 GPU 时间线关联。[TOOL]
- 部分 OEM 自定义 validation layer 可能使用非标准 message 格式，需额外适配。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- 解析 VUID 本身无性能开销。
- 大量 validation message 的日志 I/O 可能显著拖慢；建议按 VUID 去重或采样。[ENGINE]

### GPU 侧

- 无。

### 移动端

- logcat 缓冲区有限，大量 message 可能滚动丢失；建议回调内写文件或按 VUID 过滤。[ANDROID]

---

## 13. 专家经验

**经验**：
建立项目级 VUID 忽略/处理清单（allowlist/denylist）：对已知误报或已接受的警告登记在册，避免每次重构后重复调查。在回调中按 VUID 聚合计数，优先处理高频 ERROR。对 `VUID-undefined` 和实现内部 ID，结合调用栈与 object handle 人工定位。将 VUID 与代码提交关联，形成知识库。

**适用条件**：
任何启用 validation layer 的项目，尤其是频繁重构或多人协作。

**不适用情况**：
无 validation layer 或完全关闭验证的 Release 环境。

**来源**：`[ENGINE][TOOL]`

---

## 14. 相关 API 卡片

- `validation_layer.md`
- `debug_utils.md`
- `../03_command_buffer/command_buffer.md`
- `../06_pipeline/graphics_pipeline.md`
- `../04_buffer_image_memory/image.md`

---

## 15. 需要回查官方文档的情况

1. 具体 VUID 的精确触发条件与 required behavior。
2. 不同 Vulkan 版本 / 扩展引入的 VUID 差异。
3. Validation layer 实现中 VUID 与 message ID 的对应关系。
4. `VkDebugUtilsMessengerCallbackDataEXT` 各字段在不同 layer 版本中的填充情况。
5. 官方 Vulkan Spec 章节与 VUID 的索引方式。

# Debug Playbook: Validation Error Decode

## 0. 适用范围

### 适用

- Vulkan Validation Layer 输出错误。
- 错误中包含 VUID。
- 错误中包含 object handle / command name。
- 需要从 Validation Message 反推 Vulkan 对象链路。

### 不适用

- 没有开启 validation layer。
- 纯视觉错误且无任何 validation 输出。
- GPU 性能问题。

---

## 1. 现象

常见表现：

- logcat / console 中出现 Validation Error。
- 包含 `VUID-xxxx`。
- 包含 object handle。
- 某些 API 调用后触发错误。
- 画面可能黑屏、闪烁、crash，也可能仍能显示。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | Descriptor / Pipeline Layout 不匹配 | VUID 提到 descriptor / layout / binding | Descriptor / Pipeline |
| P0 | Image Layout 错误 | VUID 提到 image layout / attachment / descriptor imageLayout | Image / Barrier |
| P0 | CommandBuffer 状态错误 | VUID 提到 recording / render pass / command state | CommandBuffer |
| P1 | 资源生命周期错误 | VUID 提到 destroyed object / invalid handle | Buffer / Image / View |
| P1 | 同步 hazard | VUID 或 sync validation 提到 read/write hazard | Barrier / Sync |
| P2 | 平台 / extension / feature 不满足 | VUID 提到 feature / extension / pNext | Device Feature |

---

## 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | VUID 解码（对象 / 函数 / 约束三段） | 命中 §2 的 P0 类别（descriptor / layout、image layout、command buffer 状态）→ 沿 §4 对应链路检查 | 属于 §2 的 P1 / P2 类别（生命周期、sync、feature）→ 检查 2 | — |
| 2 | 消息中 object handle / object type 定位对象创建点 | 找到创建代码 → 检查 3 | 无 handle 或对不上 → 开 debug object name（§6 Structural Fix）后复现 | — |
| 3 | 沿 §4 对象链路反查使用点（创建 → 使用 → 销毁顺序） | 使用点违反状态约束（recording state 错误、render pass 外调用）→ §5-3 / §5-4；提前销毁 → §5-5 | 使用点正常 → 检查 4 | 正常时排除 §2 的 P0 CommandBuffer 状态与 P1 生命周期假设 |
| 4 | 回查对应 API 卡片与官方 Reference Page 的 VUID 约束原文 | 约束明确（feature / extension 未开启）→ §5-7（§2 的 P2） | 仍无法定位根因 → §11 不确定处理 | — |

---

## 4. Vulkan 对象链路排查

根据错误类型走不同链路：

### Descriptor 错误

```text
Shader set/binding
→ DescriptorSetLayout
→ PipelineLayout
→ DescriptorSet
→ Update
→ Bind
```

### Image Layout 错误

```text
Image usage
→ ImageView
→ Producer pass
→ Barrier / Layout Transition
→ Consumer pass
```

### CommandBuffer 状态错误

```text
CommandPool
→ CommandBuffer Begin
→ Recording State
→ RenderPass / Dynamic Rendering State
→ End
→ Submit
```

### Sync 错误

```text
Producer Access
→ Availability
→ Visibility
→ Consumer Access
```

---

## 5. 高频根因

1. shader binding 和 descriptor set layout 不一致。
2. descriptor imageLayout 和实际 image layout 不一致。
3. command buffer 未处于正确 recording state。
4. 在 render pass / dynamic rendering 外调用了不允许的命令。
5. 资源提前销毁。
6. stage mask / access mask 不匹配真实读写。
7. 设备 feature / extension 没开启。

---

## 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- 临时注释掉触发 validation 的调用以恢复运行（会掩盖问题，仅用于隔离定位）。`[TOOL]`

### Minimal Fix（针对根因的最小修复）

- 先按 VUID 定位具体 API。
- 不要一次改多个地方。
- 对照 object handle 找到对应资源。
- 先修第一条 validation error。

### Structural Fix（结构性 / 防复发修复）

- 为 Vulkan 对象设置 debug name。`[TOOL]`
- 建立 VUID 处理记录。`[ENGINE]`
- 对 descriptor / image layout / command buffer state 建立统一检查辅助函数。`[ENGINE]`

---

## 7. 回归验证

- [ ] 原 VUID 不再出现。
- [ ] 没有引入新的 validation error。
- [ ] RenderDoc / AGI 能看到正确资源绑定。
- [ ] 相关功能正常显示。

---

## 8. 相关 API 卡片

- `../../03_api_manual/09_debug_validation/validation_layer.md`
- `../../03_api_manual/09_debug_validation/debug_utils.md`
- `../../03_api_manual/09_debug_validation/vuid_decode.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`

---

## 9. 工具证据

Validation message 是主要证据。
必须保留：

- 完整 message
- VUID
- command name
- object handle
- object type

---

## 10. Android 分支

Android 上需要同时保留：

- logcat
- native crash stack
- validation layer setup 方式
- 设备型号 / GPU
- Vulkan API version
- Android 版本

---

## 11. 不确定时如何处理

如果无法确认：

1. 不要仅凭 VUID 文本猜。
2. 回查 Vulkan Reference Page。
3. 打开 debug object name。
4. 缩小到最小复现。
5. 补充相关对象创建和使用代码。

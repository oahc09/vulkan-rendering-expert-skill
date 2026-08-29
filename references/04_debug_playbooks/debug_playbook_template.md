# Debug Playbook Template

> 文件建议路径：`04_debug_playbooks/debug_playbook_template.md`

统一推理链：Symptom（§1）→ Hypothesis（§2）→ Evidence（§3 / §9）→ Root Cause（§5）→ Workaround（§6）→ Minimal Fix（§6）→ Structural Fix（§6）→ Regression Verification（§7）。
禁止把"现象消失"直接等同于"找到根因"。

---

# Debug Playbook: `<问题名称>`

## 0. 适用范围

说明这个 Playbook 适合处理什么问题，不适合处理什么问题。

### 适用

- xxx
- xxx

### 不适用

- xxx
- xxx

---

## 1. 现象

描述用户能看到的表现。

示例：

- App 正常运行但屏幕全黑。
- 只看到 clear color，看不到模型。
- Validation Layer 报 descriptor binding mismatch。
- 横竖屏切换后 crash。
- Compute pass 执行后没有输出。

---

## 2. 最可能原因排序

按概率和排查成本排序。

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | xxx | xxx | xxx |
| P1 | xxx | xxx | xxx |
| P2 | xxx | xxx | xxx |

---

## 3. 快速验证路径（证据驱动决策表）

按成本升序逐行检查；每行依据结果分支，并剪枝（排除）§2 中对应优先级的假设。不按固定顺序执行全部步骤，而是随证据走分支。

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | log / return code | 有错误码 → 按 §5 根因表定位 | 无输出 → 检查 2 | — |
| 2 | Validation Layer | 有 VUID → §5 根因表定位 | clean → 检查 3 | — |
| 3 | RenderDoc：draw/dispatch 是否提交 | 无 → 提交链路（§4 CommandBuffer/Queue Submit） | 有 → 检查 4 | 排除 §2 的 shader/资源假设 |
| 4 | clear color / debug shader | 不可见 → swapchain/present 分支 | 可见 → 检查 5 | 排除 §2 的提交链路假设 |
| 5 | 最小复现 | 复现 → 收敛根因（§5） | 不复现 → §11 不确定处理 | — |

规则：

- 剪枝列必须引用 §2 假设表的优先级编号（P0/P1/P2）。
- 每个具体 playbook 依据自身 §2 / §5 定制行；上表为骨架示例。
- 检查成本排序：log < Validation < RenderDoc/AGI capture < 最小复现。

---

## 4. Vulkan 对象链路排查

沿 `02_core_mental_model` 的对象链路检查：

- Surface / Swapchain
- CommandBuffer
- Queue Submit
- Pipeline
- Descriptor
- Buffer / Image
- Synchronization
- Present

---

## 5. 高频根因

列出真实工程中最常见根因：

1. xxx
2. xxx
3. xxx
4. xxx
5. xxx

---

## 6. 修复方案

给出可执行的修复方向，而不是只解释概念。修复必须分级，禁止把现象消失当作根因修复。

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- xxx

### Minimal Fix（针对根因的最小修复）

- xxx

### Structural Fix（结构性 / 防复发修复）

- xxx

---

## 7. 回归验证

说明如何证明问题已经解决。现象消失不等于根因修复，回归验证必须证明根因路径被消除，而不只是症状不再出现：

- [ ] Validation clean。
- [ ] RenderDoc frame 正常。
- [ ] AGI trace 正常。
- [ ] 截图正确。
- [ ] resize / pause / resume 不复现。
- [ ] 多帧运行无闪烁 / crash / device lost。

---

## 8. 相关 API 卡片

链接到 `03_api_manual` 中的 API 卡片。

- `03_api_manual/<your-related-api-card.md>`
- `03_api_manual/<your-related-api-card.md>`

---

## 9. 工具证据

### Validation Layer

应重点观察：

- VUID
- object handle
- object type
- command buffer state
- descriptor / image / pipeline / layout 相关错误

### RenderDoc

应重点观察：

- 是否存在 draw call / dispatch call？
- pipeline 是否绑定正确？
- descriptor 是否绑定正确资源？
- texture / buffer 内容是否正确？
- render target 内容是否符合预期？
- pass 前后 image layout / attachment 是否合理？

### AGI / Android

应重点观察：

- 是否能抓到 frame？
- GPU counter 是否异常？
- logcat 是否有 surface / swapchain / native window 错误？
- pause / resume / rotation 是否触发资源重建？

---

## 10. Android 分支

如果问题发生在 Android，额外检查：

1. Surface 是否已经 destroyed。
2. ANativeWindow 是否仍有效。
3. 横竖屏切换后 swapchain 是否完整重建。
4. depth / framebuffer / offscreen image 是否跟随尺寸重建。
5. in-flight command buffer 是否仍引用旧 swapchain 资源。
6. logcat 是否有 surface lost / native window 错误。
7. pause / resume 后 render loop 是否恢复。

---

## 11. 不确定时如何处理

如果无法确认根因：

1. 不直接下结论。
2. 先要求或建议补充：
   - Validation message
   - VUID
   - RenderDoc capture
   - AGI capture
   - logcat
   - 关键代码片段
   - 设备型号 / GPU / Vulkan 版本
3. 给出最小复现路径。
4. 标注当前判断属于：
   - `[SPEC]`
   - `[TOOL]`
   - `[ENGINE]`
   - `[HEUR]`

---

## 12. 来源等级

- `[SPEC]` Vulkan Specification / Reference Pages 明确要求
- `[GUIDE]` Vulkan Guide / Khronos Tutorial / Samples 建议
- `[ANDROID]` Android NDK / Android Game Vulkan / AGI 文档
- `[TOOL]` Validation Layer / RenderDoc / AGI 可验证
- `[ENGINE]` 图形引擎工程经验
- `[HEUR]` 启发式经验，需要结合项目判断

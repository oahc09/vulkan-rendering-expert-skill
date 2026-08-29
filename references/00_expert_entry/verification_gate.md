# Verification Gate

定义 Vulkan 任务给出最终结论前的统一验证关卡。适用于设计、实现、Debug 和优化任务的结论性输出。

> 配套文件：
>
> - 修改影响面推理：`../02_core_mental_model/regression_reasoning.md`
> - 回归验证清单：`../07_integration_pack/regression_checklist.md`

---

## 1. 定位

Verification Gate 是所有结论性输出的出口关卡。任何"已完成"、"已解决"、"根因已修复"、"性能已优化"结论，都必须先通过以下 6 道关卡，或显式声明某关卡不适用并说明原因。

```text
G1 API 合法性
→ G2 生命周期
→ G3 同步
→ G4 Validation Layer
→ G5 RenderDoc / AGI
→ G6 平台回归
```

---

## 2. G1：API 合法性

确认结论涉及的 API 用法本身合法：

1. 对象 handle 非空且属于正确的 device / queue。
2. flag / usage / format / extent / samples 组合合法。
3. 调用顺序满足规范约束（例如 layout transition 的时机、render pass 内外允许的命令、queue ownership）。
4. 关键 VUID 约束已核对；不确定时按 `accuracy_check.md` 标注回查。[SPEC][REF]

---

## 3. G2：生命周期

确认修改没有引入生命周期破坏：

1. 创建顺序正确（instance → device → queue → 资源）。
2. 销毁顺序与依赖关系逆序一致，且满足 `hard_rules.md` 第 15 条幂等要求。[SPEC]
3. 销毁 / 重建前所有 in-flight 工作已等待完成（fence / `vkDeviceWaitIdle`）。
4. swapchain recreate 路径中，旧 image view / framebuffer / 尺寸相关资源同步销毁或重建。[ENGINE]

---

## 4. G3：同步

同步类修改必须完整给出六要素，缺一不可：

```text
producer（谁写）
consumer（谁读）
srcStage / srcAccess
dstStage / dstAccess
oldLayout / newLayout（image 场景）
```

同时确认：

1. fence 用于 CPU↔GPU 等待，semaphore 用于 queue 间 / acquire / present 顺序，barrier 用于 command buffer 内依赖，三者不混用。[SPEC]
2. descriptor 的 imageLayout 与 image 实际 layout 一致。[SPEC]
3. 资源生命周期覆盖同步对象本身（fence / semaphore 的 reset 与复用时机）。[ENGINE]

---

## 5. G4：Validation Layer

Validation clean 是必要条件，不是充分条件：

1. Validation 只能证明 API 使用和显式声明的同步关系合法。[TOOL]
2. 以下问题 Validation 无法发现：错误的 clear value / winding / MVP、内容为空的纹理、语义错误的合法参数、性能回退。[ENGINE]
3. G4 通过不能单独作为"已解决"的依据，必须与 G5 / G6 联合判定。

---

## 6. G5：RenderDoc / AGI

工具级帧内容验证：

1. RenderDoc：draw / dispatch 存在、pipeline 绑定正确、descriptor 指向正确资源、每个 pass 的输入输出符合预期、image layout 状态符合预期。[TOOL]
2. AGI（Android）：能抓到 frame、GPU counter 无异常、帧耗时符合预期。[ANDROID][AGI]
3. 无法提供工具证据时，结论必须降级为"待验证"，并给出建议的验证方式。

---

## 7. G6：平台回归

结论必须在目标平台场景下回归：

1. Android：rotation / resize、pause / resume、Surface destroyed / recreated、extent 为 0 的边界处理。[ANDROID]
2. Desktop：窗口 resize、最小化恢复。[ENGINE]
3. 多帧稳定：连续运行足够多帧后无闪烁、无 crash、无 device lost、无内存持续增长。[ENGINE]

---

## 8. 关卡输出格式

结论性回答的末尾必须包含验证状态：

```text
Verification Gate:
- G1 API 合法性: 已验证（方式）/ 未验证（原因）/ 不适用（原因）
- G2 生命周期: 同上格式
- G3 同步: 同上格式
- G4 Validation: 同上格式
- G5 RenderDoc / AGI: 同上格式
- G6 平台回归: 同上格式
```

修复类结论必须同时标注修复级别：

| 级别 | 含义 |
|---|---|
| Workaround（临时绕过） | 现象消失但根因未除，必须继续定位或显式标注为临时 |
| Minimal Fix（根因修复） | 直接消除根因的最小改动 |
| Structural Fix（结构性修复） | 从工程结构上防止同类问题复发 |

---

## 9. 使用规则

1. 禁止把"现象消失"直接等同于"找到根因"。
2. Validation clean 不能作为唯一成功标准。
3. 涉及同步的修改，G3 六要素不完整时不得给出最终结论。
4. Android 相关修改，G6 未覆盖 rotation / pause / resume / Surface recreate 时不得给出最终结论。
5. 无法验证的关卡必须显式标注"未验证"并给出建议验证方式，不得默认通过。

---

## 10. 输入来源

进入 G1-G6 前，证据清单与各子问题置信度来自 `00_expert_entry/progressive_retrieval.md` 的检索循环输出；检索循环未达成高置信的子问题，在对应关卡标注"未验证"及原因。

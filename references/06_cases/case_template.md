# Case Template

> 文件建议路径：`06_cases/case_template.md`

---

# Case: `<案例名称>`

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 黑屏 / Descriptor / 同步 / Swapchain / Android / Compute / 性能 / 架构 |
| 平台 | Android / Windows / Linux / 通用 |
| 严重程度 | P0 / P1 / P2 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC] [ANDROID] [HEUR]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

描述用户或工程中实际看到的问题。

示例：

- App 正常运行，无 crash，但画面全黑。
- RenderDoc 能看到 draw call，但 render target 没有输出。
- Android 横竖屏切换后 native crash。
- Compute pass 执行后 storage image 没变化。
- 后处理开启后 GPU frame time 明显升高。

---

## 2. 初始上下文

说明问题发生时的工程背景：

- 平台
- Vulkan 版本
- 是否 Android
- 是否使用 Dynamic Rendering
- 是否多 frame-in-flight
- 是否有 RenderGraph
- 是否有 compute pass
- 是否发生在 resize / pause / resume / rotation 后

---

## 3. 初始误判

记录容易误判的方向。

示例：

```text
最初怀疑 fragment shader 输出错误。
但 clear color 正常，RenderDoc 中 shader 也执行了，后续排查发现是 input image layout 没有 transition。
```

这个字段很重要，因为专家经验通常来自“为什么不是那个原因”。

---

## 4. 排查路径

按真实顺序记录排查过程：

1. 检查 log / return code。
2. 检查 Validation Layer。
3. 检查 RenderDoc / AGI。
4. 沿对象链路排查。
5. 定位关键 Vulkan 对象。
6. 找到根因。

---

## 5. 关键证据

列出能证明根因的证据。

### Validation Layer

- VUID：
- Message：
- Object：

### RenderDoc / AGI

- 观察到：
- 关键 pass：
- 关键 resource：

### Log / Code

- 返回值：
- 生命周期日志：
- 关键代码：

---

## 6. 根因

用一句话说明根因。

格式建议：

```text
根因：<producer> 输出的 <resource> 没有通过正确 barrier 转换到 <consumer> 所需访问状态，导致 <consumer> 读取到无效内容。
```

或者：

```text
根因：Android Surface destroyed 后 render thread 仍继续使用旧 swapchain image 调用 present。
```

---

## 7. 修复方案

修复分级与 Debug Playbook 统一命名；禁止把"现象消失"等同于"根因修复"。

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- xxx（若案例未使用临时绕过，标注"不适用"及原因）

### Minimal Fix（针对根因的最小修复）

- xxx

### Structural Fix（结构性 / 防复发修复）

- xxx

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 证据正常。
- [ ] 截图正确。
- [ ] 多帧稳定。
- [ ] resize / pause / resume / rotation 不复现。
- [ ] 性能指标恢复正常。

---

## 9. 经验抽象

从这个案例中抽象出可复用经验。

示例：

```text
不要只检查 VkImage 创建和 descriptor 更新。
凡是 image 被跨 pass 使用，都必须同时检查：
usage、layout、producer access、consumer access、descriptor imageLayout、barrier subresource range。
```

---

## 10. 预防规则

把案例转成后续工程规则：

1. xxx
2. xxx
3. xxx

---

## 11. 关联 API 卡片

- `03_api_manual/<your-related-api-card.md>`

---

## 12. 关联 Debug Playbook

- `04_debug_playbooks/<your-related-playbook.md>`

---

## 13. 关联 Workflow

- `05_workflows/<your-related-workflow.md>`


<a id="delivery19-experience-lifecycle"></a>
## 有范围、可撤销的经验

[ENGINE] 候选案例字段：问题签名、项目/源码SHA、设备/driver/feature/访问模式、工具版本、证据hash、机制、修复、回归、反例、适用/失效条件、审核状态。来源区分外部issue、作者猜测、未合上游patch和本地复现。

状态：candidate → 去敏与独立审查 → reviewed；反例触发 revoked，版本/期限失效触发 expired，保留完整转换证据，不删除失败。定向检索先硬匹配设备/driver/feature，再解释为什么适用，未匹配不推荐。经验不是规范，不能扩大授权或覆盖规范约束。

默认只在本次运行本地保存；公开/持久化需要授权和审核。不把私有源码、capture、相机内容、凭据和盲测答案入库；不新增记忆服务器/向量库，不自动跨会话学习。

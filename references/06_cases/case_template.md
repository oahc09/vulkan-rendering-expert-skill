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

### 最小修复

- xxx

### 稳定修复

- xxx

### 工程化修复

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

# Workflow Template

> 文件建议路径：`05_workflows/workflow_template.md`

---

# Workflow: `<任务名称>`

## 0. 适用范围

说明这个工作流适合什么任务，不适合什么任务。

### 适用

- xxx
- xxx

### 不适用

- xxx
- xxx

---

## 1. 任务目标

说明最终要实现什么。

---

## 2. 输入条件

需要用户或工程提供哪些信息：

- 平台：Android / Windows / Linux
- Vulkan 版本
- 是否已有 swapchain
- 是否已有 render loop
- 是否已有 descriptor 管理
- 是否已有 pipeline cache
- 是否已有 RenderGraph
- 目标效果 / 功能
- 输入资源
- 输出资源
- 目标设备 / GPU
- 是否要求移动端性能优化

---

## 3. 前置检查

在开始实现前必须确认：

- [ ] Validation Layer 是否可用。
- [ ] RenderDoc / AGI 是否可抓帧。
- [ ] 当前 renderer 是否能 clear color。
- [ ] swapchain recreate 是否已有基础处理。
- [ ] command buffer / frame-in-flight 是否稳定。
- [ ] shader 编译链路是否可用。
- [ ] Vulkan API 返回值是否有日志。
- [ ] Android Surface / ANativeWindow 生命周期是否可追踪。

---

## 4. Vulkan 对象链路

画出本任务涉及的对象链路。

```text
上游对象
→ 当前新增对象
→ 下游对象
```

---

## 5. 资源设计

列出新增或复用资源。

| 资源 | 类型 | Usage | 生命周期 | 是否随 swapchain 重建 |
|---|---|---|---|---|
| xxx | `VkImage` | xxx | xxx | 是 / 否 |
| xxx | `VkBuffer` | xxx | xxx | 是 / 否 |

---

## 6. Pipeline / Descriptor 设计

说明 shader resource binding 和 Vulkan descriptor 的对应关系。

| Shader set/binding | Vulkan Descriptor | 资源 | Stage |
|---|---|---|---|
| set=0,binding=0 | xxx | xxx | Fragment / Compute |

---

## 7. 同步与 Layout 设计

说明 producer / consumer。

| Producer | Resource | Barrier / Layout | Consumer |
|---|---|---|---|
| xxx | xxx | xxx | xxx |

必须说明：

- producer stage
- producer access
- oldLayout
- newLayout
- consumer stage
- consumer access

---

## 8. 实现步骤

按工程执行顺序写：

1. 新增文件 / 类。
2. 创建资源。
3. 创建 descriptor。
4. 创建 pipeline。
5. 修改 command buffer 录制。
6. 修改 frame loop。
7. 修改 resize / recreate 路径。
8. 修改销毁路径。

---

## 9. Android 注意点

如果是 Android，必须说明：

- Surface / ANativeWindow 生命周期
- swapchain recreate
- pause / resume
- rotation / resize
- extent 为 0 的处理
- render thread 状态
- AGI / logcat 验证

---

## 10. 验证方式

必须给出验证闭环：

- [ ] Validation Layer clean。
- [ ] RenderDoc / AGI 能看到 pass / draw / dispatch。
- [ ] 截图符合预期。
- [ ] frame time 合理。
- [ ] resize / pause / resume 后正常。
- [ ] 多帧运行稳定。
- [ ] 没有明显 resource lifetime / synchronization hazard。

---

## 11. 常见失败模式

列出本工作流最容易失败的地方：

1. xxx
2. xxx
3. xxx

---

## 12. 相关 API 卡片

链接到 `03_api_manual`。

- `03_api_manual/<your-related-api-card.md>`

---

## 13. 相关 Debug Playbook

链接到 `04_debug_playbooks`。

- `04_debug_playbooks/<your-related-playbook.md>`

---

## 14. 不确定时如何处理

如果信息不足，不直接下结论。优先补充：

- 目标平台 / Vulkan 版本
- Validation message
- RenderDoc / AGI capture
- 关键代码片段
- 资源创建参数
- descriptor / pipeline layout
- barrier / layout transition
- Android lifecycle 日志

# Debug Playbook: Flickering

## 0. 适用范围

### 适用

- Vulkan 多帧渲染出现闪烁。
- 偶发显示旧帧或错误资源。
- 多 frame-in-flight 后出现不稳定画面。
- Uniform / descriptor 数据偶发串帧。

### 不适用

- 完全黑屏。
- 单帧静态输出错误。
- Shader 数值本身造成的动画闪烁。

---

## 1. 现象

常见表现：

- 画面一帧正常一帧异常。
- 模型、纹理或参数随机跳变。
- resize 后闪烁。
- 多帧运行后开始不稳定。

---

## 2. 最可能原因排序

| 优先级 | 可能原因 | 判断依据 | 关联对象 |
|---|---|---|---|
| P0 | frames-in-flight fence 错误 | CPU 覆盖 GPU 仍在读的资源 | Fence / Frame Resource |
| P0 | uniform buffer 被提前覆盖 | 参数随机跳变 | Buffer / Memory |
| P0 | descriptor 引用错误 frame resource | 纹理或 buffer 串帧 | Descriptor |
| P1 | command buffer 被错误复用 | 偶发旧命令执行 | CommandBuffer |
| P1 | swapchain image 与 frame index 混用 | 只在部分 image 出错 | Swapchain |
| P2 | barrier 缺失 | 读写顺序不稳定 | Synchronization |

---

## 3. 快速验证路径（证据驱动决策表）

| # | 检查（成本升序） | 结果 A → 下一步 | 结果 B → 下一步 | 剪枝（排除的假设） |
|---|---|---|---|---|
| 1 | 打印 frame index / image index 日志 | 混用或错位 → §5-2（frame index 与 image index 混用） | 一致 → 检查 2 | 一致时排除 §2 的 P1 image index 混用假设 |
| 2 | Validation / sync validation | 有 hazard VUID → §5-5（barrier stage / access 不匹配） | clean → 检查 3 | clean 时排除 §2 的 P2 barrier 缺失假设 |
| 3 | 帧间差异是否周期性（周期 ≈ frames-in-flight 数） | 周期性 → frame 资源复用方向：检查 4 | 非周期 → 检查 5 | 非周期时排除 §2 的 P0 fence / uniform 提前覆盖 / descriptor 串帧假设 |
| 4 | 降为 1 frame-in-flight + 检查 fence wait / reset 顺序 | 闪烁消失 → §5-1 / §5-3 / §5-4（fence signal 前覆盖、descriptor 无 per-frame 隔离、CB reset 时机） | 仍闪烁 → 检查 5 | 仍闪烁时排除 §2 的 P0 帧资源复用与 P1 command buffer 复用假设 |
| 5 | RenderDoc 抓异常帧：acquire / present semaphore 复用与 barrier 覆盖 | semaphore 等待 / 信号配对错误 → §4 链路排查；barrier 未覆盖读写 → §5-5 | 均正常 → §11 不确定处理 | — |

---

## 4. Vulkan 对象链路排查

```text
Frame Index
→ Fence
→ Per-frame Buffer / Descriptor
→ CommandBuffer
→ Queue Submit
→ GPU Execute
→ Present
```

---

## 5. 高频根因

1. CPU 在 fence signal 前覆盖 uniform buffer。
2. frame index 和 swapchain image index 混用。
3. descriptor set 没有 per-frame 隔离。
4. command buffer reset 时 GPU 仍在使用。
5. barrier stage/access 不匹配。
6. resize 后旧 frame resource 未清理。

---

## 6. 修复方案

### Workaround（临时绕过，现象消失 ≠ 根因修复）

- 降到单帧（frames-in-flight = 1）验证：若闪烁消失，说明问题出在多帧资源复用；性能损失大，仅用于定位。`[ENGINE]`

### Minimal Fix（针对根因的最小修复）

- 每帧资源独立：per-frame 的 uniform / descriptor / command buffer 不跨帧复用。`[ENGINE]`
- 资源在 fence signal（GPU 使用完成）后再复用或销毁。`[SPEC]`

### Structural Fix（结构性 / 防复发修复）

- 建立 per-frame resource 结构。`[ENGINE]`
- 明确区分 frame index 和 swapchain image index。`[ENGINE]`
- 对 uniform 使用 ring buffer 或 dynamic offset。`[ENGINE]`
- 对 descriptor 建立 per-frame set。`[ENGINE]`

---

## 7. 回归验证

- [ ] 单帧和多帧均稳定。
- [ ] 多帧运行无参数跳变。
- [ ] resize 后无闪烁。
- [ ] Validation / sync validation clean。

---

## 8. 相关 API 卡片

- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/08_synchronization/semaphore.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`

---

## 9. 工具证据

重点看：

- fence wait/reset 日志
- frame index / image index
- RenderDoc 中每帧 descriptor 资源
- sync validation hazard

---

## 10. Android 分支

Android 上 resize / pause / resume 后要重新验证 per-frame resources 是否仍然有效。

---

## 11. 不确定时如何处理

需要补充：

- frames-in-flight 代码
- fence wait/reset 代码
- uniform update 代码
- descriptor 分配/更新代码
- frame index / image index 日志

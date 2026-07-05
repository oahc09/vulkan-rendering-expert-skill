# Case: Frame Resource Overwrite Causes Flickering

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | 同步 / Frame Resource / 闪烁 |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

多 frame-in-flight 后画面出现闪烁。  
Uniform 参数偶发跳变，某些帧使用上一帧或下一帧的数据。  
降到 1 frame-in-flight 后问题消失。

---

## 2. 初始上下文

- 使用 2 或 3 frames-in-flight。
- 每帧更新 uniform buffer。
- Descriptor set 可能复用同一个 buffer。
- CPU 每帧写入新参数。
- GPU 可能仍在读取旧 frame 的资源。

---

## 3. 初始误判

最初容易怀疑：

```text
动画逻辑错误；
shader 数值不稳定；
present 顺序问题；
swapchain image index 错误。
```

但降为 1 frame-in-flight 后问题消失，说明更像 CPU/GPU 同步或 frame resource 复用问题。

---

## 4. 排查路径

1. 打印 frame index 和 swapchain image index。
2. 确认 frame index 不等于 image index。
3. 检查 uniform buffer 是否 per-frame 独立。
4. 检查 descriptor set 是否 per-frame 独立。
5. 检查 fence wait / reset 顺序。
6. 确认 CPU 是否在 fence signal 前覆盖 GPU 正在读取的资源。
7. 用 RenderDoc 查看异常帧绑定的 uniform buffer。

---

## 5. 关键证据

### Validation Layer

不一定会报错。  
如果开启同步验证，可能出现 read/write hazard。

### RenderDoc / AGI

观察到：

- 异常帧绑定的 uniform 数据与当前 CPU 期望不一致。
- 多帧资源复用了同一 buffer range。
- frame index / image index 管理混乱。

### Log / Code

关键问题：

```text
CPU 每帧写同一个 uniform buffer memory range，但没有等待对应 GPU frame 完成。
```

---

## 6. 根因

根因：CPU 在 GPU 仍可能读取上一帧 uniform buffer 时提前覆盖了同一块 memory range，导致 shader 偶发读取到错误数据。

---

## 7. 修复方案

### 最小修复

- 降为 1 frame-in-flight 验证。
- 每个 frame-in-flight 使用独立 uniform buffer 或独立 offset。
- 只有当前 frame fence signal 后，才复用对应资源。

### 稳定修复

- 建立 per-frame resource：
  - uniform buffer
  - descriptor set
  - command buffer
  - fence / semaphore
- 明确区分 frame index 和 swapchain image index。
- 对 dynamic uniform offset 做 alignment 检查。

### 工程化修复

- 使用 ring buffer。
- 建立 frame allocator。
- 所有 transient GPU resource 都挂到 frame resource 下。
- 在 debug 模式下记录 resource last-used fence。

---

## 8. 修复后验证

- [ ] 多 frame-in-flight 不闪烁。
- [ ] 降为 1 frame 和恢复多 frame 结果一致。
- [ ] RenderDoc 中每帧 uniform 数据正确。
- [ ] Sync validation 无 hazard。
- [ ] 多帧长时间运行稳定。

---

## 9. 经验抽象

Vulkan 中“CPU 写完”不等于“GPU 已经读完”。  
任何 per-frame 可变资源都必须受 fence 或 frame resource 生命周期保护。

---

## 10. 预防规则

1. frame index 与 swapchain image index 必须分清。
2. 高频更新 uniform 必须使用 per-frame buffer 或 ring buffer。
3. descriptor set 应与 frame resource 生命周期一致。
4. command buffer reset 前必须确认 GPU 不再使用。
5. frame resource 复用必须等待对应 fence。

---

## 11. 关联 API 卡片

- `../../03_api_manual/08_synchronization/fence.md`
- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/uniform_buffer_descriptor.md`
- `../../03_api_manual/03_command_buffer/command_buffer_lifetime.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/flickering.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_frame_loop.md`
- `../../05_workflows/05_resource_management/manage_frame_resources.md`

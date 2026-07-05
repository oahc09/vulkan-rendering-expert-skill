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

## 3. 快速验证路径

1. 降为 1 frame-in-flight，看闪烁是否消失。
2. 打印 frame index / image index。
3. 检查每帧 uniform / descriptor 是否独立。
4. 检查 fence wait/reset 顺序。
5. 用 RenderDoc 抓异常帧。
6. 开启 sync validation。

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

### 最小修复

- 降到单帧验证。
- 每帧资源独立。
- fence signal 后再复用资源。

### 稳定修复

- 建立 per-frame resource 结构。
- 明确区分 frame index 和 swapchain image index。
- 对 uniform 使用 ring buffer 或 dynamic offset。
- 对 descriptor 建立 per-frame set。

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

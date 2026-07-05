# Case: Compute Dispatch Zero

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Dispatch |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Compute pass 执行后 storage image / storage buffer 内容没有变化，但程序无 crash、无 Validation Layer 报错。Shader 逻辑看起来正确，dispatch 调用也存在，只是没有任何输出。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android 均可发生。
- 使用 compute pipeline 写入 storage image 或 storage buffer。
- Dispatch group count 由 CPU 根据资源尺寸动态计算。
- 可能刚修改了 compute shader 的 `local_size_x` / `local_size_y` / `local_size_z`。
- 资源尺寸较小（例如 1×1、2×2、小于 workgroup 大小）。

---

## 3. 初始误判

最初容易怀疑：

```text
compute shader 写错坐标或条件分支导致无写入；
descriptor 没绑定或 binding 不匹配；
storage image layout 不是 GENERAL；
compute 与 graphics 之间缺少 barrier；
storage buffer 不可见或没 flush。
```

但 RenderDoc 中 shader 绑定正常，dispatch 调用可见，没有 barrier 错误。最终发现 `vkCmdDispatch` 的 group count 为 0，导致 GPU 不启动任何 workgroup。

---

## 4. 排查路径

1. 在 `vkCmdDispatch` 调用处打印 `groupCountX`、`groupCountY`、`groupCountZ`。
2. 检查 compute shader 中的 `layout(local_size_x = N, ...)` 数值。
3. 确认 group count 计算是否使用了整数除法且没有向上取整。
4. 检查资源尺寸小于 workgroup 大小时的结果。
5. 在 RenderDoc / AGI 中查看 dispatch 调用的 thread group 数量。
6. 检查是否有分支在资源尺寸为 0 或 1 时直接返回，导致跳过 dispatch。

---

## 5. 关键证据

### Validation Layer

- 通常无直接报错（`[ENGINE]`），因为 dispatch group count 为 0 是合法的 Vulkan 行为。
- 若 storage image layout 或 descriptor 类型不匹配，可能报相关 VUID，但这类错误与本案例无关。

### RenderDoc / AGI

- 观察到：
  - Dispatch 调用存在，但 Thread Groups 显示为 `0, 0, 0` 或某一维为 0。
  - 或 Dispatch 的 group count 计算为 0，导致 no threads launched。
  - Storage image / buffer 在 dispatch 前后内容完全一致。
- 关键 resource：compute pipeline、`vkCmdDispatch` 参数、storage resource。

### Log / Code

- 返回值：
  - `vkCmdDispatch` 是录制命令，无返回值。
  - `vkQueueSubmit` 返回 `VK_SUCCESS`。
- 关键代码：

```text
// 错误示例：整数除法导致 group count 为 0
uint32_t groupCountX = imageWidth / localSizeX; // 若 imageWidth < localSizeX，结果为 0
uint32_t groupCountY = imageHeight / localSizeY;
vkCmdDispatch(cmd, groupCountX, groupCountY, 1);
```

或：

```text
// 错误示例：分支跳过 dispatch
if (imageWidth == 0 || imageHeight == 0) return; // 可能条件判断错误
vkCmdDispatch(cmd, imageWidth, imageHeight, 1);   // 错误：直接以像素尺寸作为 group count
```

---

## 6. 根因

根因：`vkCmdDispatch` 的 group count 计算错误，某一维为 0，导致 GPU 没有启动任何 compute workgroup，storage resource 保持原样。

---

## 7. 修复方案

### 最小修复

- 使用向上取整计算 group count：

```text
groupCountX = (width + localSizeX - 1) / localSizeX;
groupCountY = (height + localSizeY - 1) / localSizeY;
groupCountZ = (depth + localSizeZ - 1) / localSizeZ;
```

- 在调用 `vkCmdDispatch` 前断言 `groupCountX > 0 && groupCountY > 0 && groupCountZ > 0`。
- 当资源尺寸为 0 时，跳过 dispatch 而不是传入 0。

### 稳定修复

- 封装 `DispatchCompute(width, height, depth, localSizeX, localSizeY, localSizeZ)` 辅助函数，内部自动处理向上取整和零尺寸保护。
- 在 shader 编译或反射阶段读取 `local_size`，确保 CPU 侧 group count 计算与 shader 一致。
- 对 1D / 2D / 3D dispatch 分别提供类型安全的封装。

### 工程化修复

- 在 compute pass 描述中声明 `local_size` 和 dispatch domain，由 RenderGraph / pass system 自动计算 group count。
- CI 中加入小尺寸资源（1×1、2×2）的 compute 测试，确保 edge case 下有输出。
- 在 RenderDoc / AGI capture 中自动检查 dispatch group count 是否为 0。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 dispatch 的 Thread Groups 大于 0。
- [ ] Compute shader 写入 storage image / buffer 后内容发生变化。
- [ ] 资源尺寸为 1×1、2×2 等小于 workgroup 大小时仍有正确输出。
- [ ] 多帧运行稳定，无输出被覆盖或延迟。
- [ ] 修改 `local_size` 后 group count 自动重新计算。

---

## 9. 经验抽象

Dispatch group count 是“像素 / 纹素数量”除以“local size”后的向上取整，不是直接除法：

```text
groupCount = ceil(workSize / localSize)
```

只要资源尺寸小于 workgroup 尺寸，普通整数除法就会得到 0。更隐蔽的是，dispatch 0 是合法调用，不会触发 validation error，因此最容易被忽略。

---

## 10. 预防规则

1. 所有 compute dispatch 必须使用向上取整公式计算 group count。
2. 调用 `vkCmdDispatch` 前必须断言所有维度 group count > 0。
3. CPU 侧 `localSize` 必须与 shader `layout(local_size_x, ...)` 保持一致。
4. 资源尺寸为 0 时应跳过 dispatch，而不是传入 0。
5. 新增 compute pass 时必须包含 1×1、边界尺寸等 edge case 测试。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/03_command_buffer/command_buffer.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

## 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_image.md`
- `../../05_workflows/03_compute_workflows/compute_write_storage_buffer.md`

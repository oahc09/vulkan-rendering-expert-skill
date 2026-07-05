# Case: Compute To Fragment Missing Barrier

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Compute / Synchronization / Image Layout |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Compute shader 写入 storage image 后，后续 fullscreen fragment shader 采样该 image，画面显示为黑色或旧内容。  
Compute dispatch 在 RenderDoc 中存在，storage image 似乎有写入，但 fragment pass 读取结果不稳定。

---

## 2. 初始上下文

- 使用 compute pipeline 生成图像。
- 输出资源是 `VkImage`，带有 `STORAGE` 和 `SAMPLED` usage。
- 后续 graphics pipeline 通过 sampled image 读取。
- 两个 pass 在同一个 command buffer 或同一个 queue 中执行。
- 可能使用 `VK_KHR_synchronization2` 或传统 barrier。

---

## 3. 初始误判

最初容易怀疑：

```text
compute shader 没执行；
dispatch group count 错；
descriptor 没绑定；
fragment shader 采样坐标错误。
```

但 RenderDoc 显示 compute dispatch 已执行，storage image 有内容。  
问题出在 compute 写之后没有建立 graphics 读的内存可见性与 layout transition。

---

## 4. 排查路径

1. 检查 `vkCmdDispatch` 是否存在。
2. 检查 compute pipeline 和 descriptor 是否绑定。
3. 检查 storage image 是否有 `STORAGE` usage。
4. 检查 shader 写入坐标是否覆盖目标区域。
5. 检查 compute pass 后是否有 barrier。
6. 检查 image layout 是否从 `GENERAL` 转到 sampled read layout。
7. 检查 descriptor imageLayout 是否与 fragment shader 采样 layout 一致。
8. 用 sync validation 检查 shader write → shader read hazard。

---

## 5. 关键证据

### Validation Layer

可能出现：

- synchronization hazard
- image layout mismatch
- descriptor imageLayout mismatch

### RenderDoc / AGI

观察到：

- compute dispatch 存在。
- storage image 在 compute 后有内容。
- fragment pass 绑定了该 image。
- pass 间缺少 compute write → fragment read barrier。

### Log / Code

关键问题：

```text
Compute 写后直接进入 fullscreen pass，没有 barrier。
```

---

## 6. 根因

根因：compute shader 写 storage image 后，没有通过 image memory barrier 建立 compute shader write 到 fragment shader sampled read 的内存依赖与 layout transition，导致 fragment shader 读取到无效或旧内容。

---

## 7. 修复方案

### 最小修复

在 compute dispatch 后插入 barrier：

```text
srcStage  = COMPUTE_SHADER
srcAccess = SHADER_WRITE
oldLayout = GENERAL

dstStage  = FRAGMENT_SHADER
dstAccess = SHADER_SAMPLED_READ
newLayout = SHADER_READ_ONLY_OPTIMAL
```

### 稳定修复

- 每个 compute output 明确 consumer。
- 对 storage image 建立状态跟踪。
- descriptor imageLayout 与实际 consumer layout 对齐。

### 工程化修复

- 在 RenderGraph 中声明：
  ```text
  compute pass writes storage image
  graphics pass reads sampled image
  ```
- 自动生成 barrier。
- 开启 sync validation 测试 compute → graphics 链路。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] Sync validation 无 hazard。
- [ ] RenderDoc 中 fragment pass 能读取 compute 输出。
- [ ] 多帧结果稳定。
- [ ] Android AGI 中 compute / graphics pass 顺序正确。

---

## 9. 经验抽象

Compute 和 Graphics 之间不会自动同步。  
只要资源跨阶段读写，必须明确：

```text
producer stage
producer access
consumer stage
consumer access
image layout
descriptor imageLayout
queue ownership，如跨 queue
```

---

## 10. 预防规则

1. Compute 输出资源必须声明 consumer。
2. Storage image 后续采样必须有 layout transition。
3. Barrier 必须精确表达 write → read。
4. Sync validation 应纳入调试流程。
5. RenderDoc / AGI 必须验证 compute output 和 graphics input。

---

## 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/compute_pipeline.md`
- `../../03_api_manual/08_synchronization/pipeline_barrier.md`
- `../../03_api_manual/08_synchronization/image_memory_barrier.md`
- `../../03_api_manual/08_synchronization/synchronization2.md`
- `../../03_api_manual/05_descriptor/storage_buffer_image_descriptor.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/04_resource_sync/compute_no_output.md`
- `../../04_debug_playbooks/03_validation_errors/image_layout_error.md`
- `../../04_debug_playbooks/03_validation_errors/synchronization_hazard.md`

---

## 13. 关联 Workflow

- `../../05_workflows/03_compute_workflows/add_compute_pass.md`
- `../../05_workflows/03_compute_workflows/compute_to_graphics_sync.md`

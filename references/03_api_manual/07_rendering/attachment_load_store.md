# API Card: Attachment Load / Store Operations

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | Rendering 链 |
| Vulkan 对象 | `VkAttachmentDescription` / `VkRenderingAttachmentInfo` |
| 常用 API | `vkCreateRenderPass` / `vkCmdBeginRendering` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [ENGINE] [ANDROID]` |
| 适用 Vulkan 版本 | Vulkan 1.0 / dynamic rendering |

---

## 1. 一句话定位

Attachment 的 load/store operation 决定 render pass 或 dynamic rendering 开始与结束时，attachment 内容如何进入和离开 tile memory，是带宽、功耗与画面正确性的关键开关。[SPEC]

---

## 2. 所属对象链路

```text
VkAttachmentDescription（render pass）
或 VkRenderingAttachmentInfo（dynamic rendering）
→ loadOp / storeOp / stencilLoadOp / stencilStoreOp
→ Render Pass Instance / Dynamic Rendering Instance
→ Attachment 数据进入 / 离开 GPU
```

### 上游依赖

- Attachment image 的当前内容是否需要保留。[SPEC]
- Tile-based GPU 的 tile memory 是否需要回填。[ENGINE]

### 下游影响

- 决定 render pass 结束后 attachment 的内容是否可用作 texture、resolve、present。[SPEC]
- 决定移动端功耗与带宽。[ENGINE]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkAttachmentDescription.loadOp` / `.storeOp`
- `VkAttachmentDescription.stencilLoadOp` / `.stencilStoreOp`
- `VkRenderingAttachmentInfo.loadOp` / `.storeOp`
- `VkClearValue`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateRenderPass` | 在 `VkAttachmentDescription` 中静态指定 load/store op。[SPEC] |
| `vkCmdBeginRenderPass` / `vkCmdBeginRendering` | 提供 clear value（如 loadOp 为 CLEAR）。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- 对 depth/stencil，load/store op 分别由 `stencilLoadOp` / `stencilStoreOp` 控制。[SPEC]

---

## 4. 标准使用流程

```text
判断该 attachment 是否需要上一帧内容
→ 若不需要：loadOp = CLEAR 或 DONT_CARE
→ 若需要保留：loadOp = LOAD
→ 判断渲染结束后是否需要该 attachment 内容
→ 若不需要：storeOp = DONT_CARE
→ 若需要：storeOp = STORE
→ 对 depth/stencil 分别设置 stencilLoadOp / stencilStoreOp
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `loadOp` | `LOAD`/`CLEAR`/`DONT_CARE`：规定 render area 初始内容保留、清除或丢弃语义，不直接规定物理 tile 读取。[SPEC] | 该 clear 的用了 LOAD，增加不必要带宽。[TOOL] |
| `storeOp` | `STORE`/`DONT_CARE`：规定 render area 结果是否需保留，不直接规定缓存/压缩物理写回路径。[SPEC] | 需要后续采样时用了 DONT_CARE，导致内容丢失。[TOOL] |
| `stencilLoadOp` / `stencilStoreOp` | depth 与 stencil 可独立控制。[SPEC] | 只设置 depth op 而忽略 stencil。[TOOL] |
| `clearValue` | `loadOp = CLEAR` 时必须提供，数组索引与 attachment 索引对应。[SPEC] | clear value 数量不足或索引错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 每个 attachment 的 load/store op 是否反映其实际生命周期？
- [ ] Stencil op 是否与 depth op 同时检查？
- [ ] Clear value 数组长度是否与 attachment 数量匹配？

### 使用阶段

- [ ] 当前 attachment 是否确实不需要保留历史内容？
- [ ] Render area 是否覆盖需要 clear/store 的区域？

### 销毁阶段

- [ ] 无独立对象；load/store op 属于 render pass / rendering info 描述。

---

## 7. 高频错误

1. 后处理输入 attachment 使用 `LOAD_OP_CLEAR` 导致内容被清空。[TOOL]
2. 只需要临时 depth 的 shadow pass 使用 `STORE` 导致不必要写回。[TOOL]
3. `DONT_CARE` 被误用到需要保留结果的 attachment。[TOOL]
4. Stencil 测试开启但 `stencilLoadOp`/`stencilStoreOp` 未正确设置。[TOOL]
5. Clear value 索引与 attachment 索引对不上。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkAttachmentDescription-loadOp-*` 等：op 与 format 的合法性。
- `VUID-VkRenderPassBeginInfo-clearValueCount-*`：clear value 数量检查。

### RenderDoc / AGI

- 查看每个 attachment 的 load/store op。
- 检查 render pass 结束后的 attachment 内容是否符合预期。
- AGI 可分析 tile bandwidth 与 store 次数。

### 日志 / 代码检查

- 检查 load/store op 的赋值逻辑。
- 检查 clear value 的构造与索引。

---

## 9. 生命周期风险

### 创建时机

- 在 render pass 创建或每帧构造 rendering info 时确定。[SPEC]

### 使用时机

- 由 `vkCmdBeginRenderPass`/`vkCmdEndRenderPass` 或 `vkCmdBeginRendering`/`vkCmdEndRendering` 隐式执行。[SPEC]

### 销毁时机

- 无独立对象销毁。

### in-flight 风险

- 对同一 attachment 的并发读写仍需正确同步；load/store op 本身不解决同步问题。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- load/store 由设备执行，但不免除 host 访问、提交完成和资源生命周期所需同步。[SPEC]

### GPU-GPU 同步

- 若同一 attachment 先被写入再被读取，需保证 render pass 间有正确 dependency 或 barrier。[SPEC]

### 资源访问同步

- STORE 规定内容保留，不是 layout 转换命令。传统 render pass 另按 attachment/subpass layout 规则转换；dynamic rendering 的 imageLayout 只是声明当前 layout，后续用途仍需显式 transition/依赖。[SPEC]

---

## 11. Android 注意点

- LOAD 保留所需已有内容，不限于上一帧；其实际 tile/system-memory 流量与功耗依实现和工作负载实测，不能由枚举值直接推出。[ANDROID][ENGINE]
- STORE 保留 render area 结果供后续使用；不需要内容时可考虑 DONT_CARE，但物理流量与功耗收益需测量，不保证显著改善。[ANDROID]
- DONT_CARE 之后相应区域内容在规范上就是未定义，不是仅部分驱动优化的偶发现象；未重新定义前不能将读取值用于正确性判断。[TOOL]

---

## 12. 性能注意点

### CPU 侧

- 选择正确的 load/store op 不增加 CPU 开销，但错误选择会增加 GPU 工作。[HEUR]

### GPU 侧

- 先选择满足内容需求的 LOAD/CLEAR/DONT_CARE 和 STORE；实际 bandwidth 需平台测量，不能保证某组合总是最省。[ENGINE]
- 全屏 STORE 要求保留区域结果，但不规定所有实现的物理缓存/压缩写回路径或精确字节流量。[ENGINE]

### 移动端

- 临时 depth buffer 不需要跨帧保留，通常使用 `CLEAR` + `DONT_CARE`。[ENGINE]
- UI / overlay 层通常需要 `LOAD` color buffer 以保留前面内容。[HEUR]
- MSAA resolve target 通常用 `DONT_CARE` load + `STORE`。[HEUR]

---

## 13. 专家经验

**经验**：
把 load/store op 当作“attachment 内容契约”：在进入 render pass 前问自己“这个 attachment 是否必须保留上一帧内容”，在结束前问自己“后面是否还有人读它”。若两个答案都是否，就用 `DONT_CARE`；若只是开始不需要，用 `CLEAR`；只有真正需要历史内容时才用 `LOAD`。对移动端 tile-based GPU，应分别测量这些 op 与 shader 的影响，不预设哪个必然决定帧率。

**适用条件**：
所有使用 render pass 或 dynamic rendering 的场景。

**不适用情况**：
compute-only 管线不经过 rasterization，不涉及 load/store op。

**来源**：`[ENGINE][ANDROID][SPEC]`

---

## 14. 相关 API 卡片

- `render_pass.md`
- `dynamic_rendering.md`
- `render_target_layout.md`
- `../04_buffer_image_memory/framebuffer.md`
- `../04_buffer_image_memory/image.md`
- `../04_buffer_image_memory/image_view.md`

---

## 15. 需要回查官方文档的情况

1. 特定 format 是否支持 `CLEAR` 及 clear value 的编码方式。
2. Depth/stencil format 的 `stencilLoadOp`/`stencilStoreOp` 限制。
3. `DONT_CARE` 后读取 attachment 内容的合法性。
4. Multisample attachment 的 store op 与 resolve 规则。
5. 不同驱动对 `LOAD_OP_CLEAR` 与 `LOAD_OP_DONT_CARE` 的 tile memory 行为差异。

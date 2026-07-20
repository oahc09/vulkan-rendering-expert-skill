# Cases: Descriptor / Pipeline

> 合并自 4 个原 case 文件。关键词: descriptor, binding, pipeline-layout, uniform, alignment, resize

---

## Case: Descriptor Binding Mismatch

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Pipeline |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Validation Layer 报 descriptor binding mismatch。  
Shader 里声明了 texture 或 uniform buffer，但运行时 shader 读取不到资源，画面黑或参数不生效。

---

### 2. 初始上下文

- 使用 graphics pipeline。
- Shader 中声明 `layout(set = 0, binding = 1)`。
- Vulkan 侧创建了 descriptor set layout。
- Pipeline layout 创建成功。
- Descriptor set allocation 和 update 也执行了。

---

### 3. 初始误判

最初容易怀疑：

```text
纹理没上传；
uniform buffer 没更新；
fragment shader 采样坐标错误。
```

但 RenderDoc 显示 shader resource binding 为空或不匹配。  
最终发现 shader binding 与 Vulkan 侧 descriptor layout 不一致。

---

### 4. 排查路径

1. 提取 Validation Message 和 VUID。
2. 查看 shader 中所有 `set` / `binding`。
3. 检查 `VkDescriptorSetLayoutBinding`。
4. 检查 `descriptorType` 是否匹配。
5. 检查 `stageFlags` 是否覆盖实际 shader stage。
6. 检查 `VkPipelineLayoutCreateInfo` 是否包含正确 set layout。
7. 检查 `vkUpdateDescriptorSets` 的 binding。
8. 检查 `vkCmdBindDescriptorSets` 的 set index 和 bind point。

---

### 5. 关键证据

### Validation Layer

可能出现：

- descriptor set layout binding mismatch
- descriptor type mismatch
- pipeline layout incompatible
- descriptor not accessible from shader stage

### RenderDoc / AGI

观察到：

- Bound resources 中目标 binding 为空。
- binding 位置与 shader declaration 不一致。
- pipeline layout 中 set layout 与绑定 descriptor set 不兼容。

### Log / Code

关键代码：

```text
shader: set=0,binding=1
Vulkan: VkDescriptorSetLayoutBinding.binding = 0
```

或者：

```text
stageFlags 只填 VERTEX，但资源在 FRAGMENT 中使用。
```

---

### 6. 根因

根因：shader resource declaration 与 Vulkan 侧 descriptor set layout / pipeline layout 不一致，导致 pipeline 执行时 shader 无法访问正确资源。

---

### 7. 修复方案

### 最小修复

- 以 shader 中的 set/binding 为准修正 descriptor layout。
- 修正 descriptorType。
- 修正 stageFlags。
- 重新创建 pipeline layout 和 pipeline。
- 重新分配并更新 descriptor set。

### 稳定修复

- 建立 shader binding 表。
- 使用 shader reflection 自动生成 descriptor layout。
- 在 pipeline 创建前校验 shader resource 与 descriptor layout。

### 工程化修复

- 引入统一 descriptor schema。
- 对每个 shader pass 生成 descriptor manifest。
- CI 中检查 shader binding 和 Vulkan layout 一致性。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc bound resources 正确。
- [ ] Shader 能读取正确 texture / buffer。
- [ ] 多帧运行无资源串帧。
- [ ] resize 后 descriptor 仍正确。

---

### 9. 经验抽象

Descriptor 错误不要只看 `vkUpdateDescriptorSets`。  
必须沿以下链路排查：

```text
Shader set/binding
→ DescriptorSetLayout
→ PipelineLayout
→ DescriptorSet Allocation
→ vkUpdateDescriptorSets
→ vkCmdBindDescriptorSets
→ Shader Access
```

---

### 10. 预防规则

1. Shader binding 必须有统一表。
2. Descriptor layout 必须和 shader declaration 自动或半自动对齐。
3. Pipeline layout 变化后必须重新创建 pipeline。
4. stageFlags 必须覆盖实际 shader stage。
5. 每个 pass 的 descriptor 更新必须可被 RenderDoc 验证。

---

### 11. 关联 API 卡片

- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

### 13. 关联 Workflow

- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`


---

## Case: Descriptor References Old Image After Resize

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Swapchain / Resize |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

窗口 resize、Android 横竖屏切换或 display scale 变化后，画面变黑、拉伸、闪烁，或出现 validation error 提示使用了已销毁的 image view。问题在 resize 前正常，resize 后必现或高概率出现。

---

### 2. 初始上下文

- 平台：Windows / Linux / Android，尤其是 Android rotation。
- 使用 swapchain 作为后处理输入，或 descriptor 中引用了 swapchain image view 用于 UI / debug 显示。
- 有明确的 swapchain recreate 流程，但只重建了 swapchain 和 framebuffers。
- 多 frame-in-flight，per-frame descriptor pool 或 descriptor set。
- 可能使用 Dynamic Rendering，依赖 image view 直接作为 rendering attachment 或 sampled input。

---

### 3. 初始误判

最初容易怀疑：

```text
swapchain recreate 失败；
新 swapchain image 没有正确 acquire；
pipeline viewport 没有更新；
surface capabilities 获取错误导致 extent 不匹配；
resize 触发了 validation error 被忽略。
```

但 `vkCreateSwapchainKHR` 返回成功，新的 swapchain image 已创建，viewport 也已更新。最终发现 descriptor set 中仍保存着旧 swapchain 的 `VkImageView` handle，GPU 采样或写入时访问了无效或尺寸错误的 image。

---

### 4. 排查路径

1. 检查 resize 后 `vkCreateSwapchainKHR` 是否成功，新 image count 是否与旧 image count 一致。
2. 检查新 swapchain 的 image view 是否已重新创建。
3. 检查 descriptor set update 调用：是否仍使用旧 `VkImageView` handle。
4. 在 RenderDoc 中对比 resize 前后的 Bound Resources，确认 image view handle 是否变化。
5. 检查 descriptor pool / set 是否在 resize 时被释放并重新分配。
6. 确认 resize 后的第一次渲染是否重新执行了 `vkUpdateDescriptorSets`。
7. 检查 frame-in-flight 的 descriptor set 是否全部更新，而不仅是当前帧。

---

### 5. 关键证据

### Validation Layer

- 若旧 image view 已被销毁但 descriptor 仍引用（`[SPEC]`）：
  - `VUID-vkUpdateDescriptorSets-None-03047`：descriptor 更新的 image view 必须有效。
  - `VUID-vkCmdDraw-None-02699`：descriptor image layout 与 image 实际 layout 不匹配。
- 若旧 image view 尚未销毁但已属于旧 swapchain：
  - 可能无直接报错，但渲染结果异常。

### RenderDoc / AGI

- 观察到：
  - resize 后 Texture Viewer 中显示的 swapchain image 尺寸为旧尺寸。
  - Bound Resources 中 image view handle 与当前 swapchain image view 不一致。
  - 采样该 image view 时得到黑色或拉伸内容。
- 关键 resource：swapchain image view、descriptor set、`VkDescriptorImageInfo`。

### Log / Code

- 返回值：
  - `vkCreateSwapchainKHR` 返回 `VK_SUCCESS`。
  - `vkUpdateDescriptorSets` 若使用已销毁 image view 可能触发 validation error。
- 生命周期日志：
  - 旧 swapchain image view 在 `cleanupSwapchain()` 中被销毁。
  - 但 descriptor update 仍发生在销毁之后且未重新分配新 view。
- 关键代码：

```text
// 错误示例：resize 后没有更新 descriptor
void recreateSwapchain() {
    cleanupSwapchain();          // 销毁旧 swapchain image views
    createSwapchain();           // 创建新 swapchain 和 image views
    createFramebuffers();        // 创建 framebuffers
    // 缺少：重新分配/更新 descriptor sets
}
```

---

### 6. 根因

根因：swapchain recreate 后，descriptor set 仍引用旧 swapchain 的 image view，导致 GPU 访问了已失效或尺寸不匹配的图像资源。

---

### 7. 修复方案

### 最小修复

- 在 swapchain recreate 完成后，重新分配并更新所有引用 swapchain image view 的 descriptor set。
- 确保 `VkDescriptorImageInfo.imageView` 来自新 swapchain。
- 若 descriptor pool 已满或需要释放旧 set，在 cleanup 阶段先释放 descriptor set，再销毁旧 image view。

### 稳定修复

- 维护 swapchain-dependent resource group：swapchain、image views、framebuffers、descriptors 统一在 recreate 时重建。
- 在 resource manager 中标记“swapchain 依赖资源”，resize 时自动失效并重新创建。
- 对每帧 descriptor set 做版本管理，swapchain 版本号变化时强制重新 update。

### 工程化修复

- 使用 RenderGraph / FrameGraph 自动处理资源生命周期：resize 时重新分配依赖资源并更新所有 descriptor。
- 引入 descriptor set allocator 与缓存，按 swapchain 版本隔离 descriptor set。
- 在 CI 中增加 resize / rotation 自动化测试，验证 descriptor 引用的 image view 与新 swapchain 一致。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 Bound Resources 的 image view handle 与新 swapchain 一致。
- [ ] resize / rotation 后画面正常，无黑屏、拉伸、闪烁。
- [ ] 多 frame-in-flight 下所有 descriptor set 均已更新。
- [ ] 连续多次 resize 仍正常。
- [ ] Android pause / resume 后 descriptor 引用正确。

---

### 9. 经验抽象

Swapchain recreate 不只是重建 swapchain 本身。任何引用 swapchain image view 的资源（framebuffer、descriptor、render pass attachment）都属于 swapchain-dependent 资源链，必须在同一次 recreate 中同步更新：

```text
swapchain
→ swapchain image views
→ framebuffers
→ descriptors (sampled input / storage image)
→ pipeline dynamic state (viewport/scissor)
```

只更新其中一部分会导致静默错误。

---

### 10. 预防规则

1. 把 swapchain、image views、framebuffers、相关 descriptor set 归为同一生命周期组，recreate 时统一重建。
2. resize / rotation 后必须重新执行 `vkUpdateDescriptorSets`，禁止复用旧 swapchain 的 image view。
3. 多 frame-in-flight 下，所有 in-flight 帧的 descriptor set 都必须按新 swapchain 更新。
4. 在 descriptor update 处增加断言：image view 必须属于当前 swapchain 版本。
5. 代码审查时把 resize 处理路径作为重点检查对象，确保没有资源遗漏更新。

---

### 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/04_buffer_image_memory/image_view.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/01_visual_issues/black_screen.md`
- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`

---

### 13. 关联 Workflow

- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/05_resource_management/manage_resource_lifetime.md`


---

## Case: Pipeline Layout Mismatch

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Pipeline Layout |
| 平台 | 通用 / Android |
| 严重程度 | P0 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Validation Layer 报错提示 pipeline layout 与 descriptor set layout 不兼容，或 shader 无法访问资源。表现为画面黑、uniform 不生效、texture 采样不到，甚至直接 crash。错误通常出现在 `vkCmdBindDescriptorSets` 或 `vkCmdDraw` / `vkCmdDispatch` 阶段。

---

### 2. 初始上下文

- 使用 graphics 或 compute pipeline。
- Shader 中声明了多个 `layout(set = M, binding = N)`。
- Vulkan 侧手动创建了 `VkDescriptorSetLayout` 和 `VkPipelineLayout`。
- 最近修改过 shader（新增 set / binding / push constant），但未同步更新 pipeline layout。
- 或同一 pipeline 被多个 shader pass 复用，但各 pass 的 resource layout 不同。

---

### 3. 初始误判

最初容易怀疑：

```text
descriptor set 没有正确分配或更新；
shader binding 写错；
vkCmdBindDescriptorSets 的 set index 填错；
stageFlags 没有覆盖目标 shader stage；
push constant range 超限。
```

但 RenderDoc 显示 descriptor set 已绑定到正确 slot，update 也无误。最终发现是 `VkPipelineLayoutCreateInfo` 中的 `setLayouts` 与 shader 声明的 set / binding 不匹配，或 pipeline 是用旧 layout 创建的。

---

### 4. 排查路径

1. 提取 Validation Message 中的 VUID 和 object handle。
2. 用 shader reflection 工具（spirv-cross / spirv-reflect）列出 shader 中所有 `set` / `binding` / `type` / `stage`。
3. 检查 `VkDescriptorSetLayoutCreateInfo` 中的 `binding` 是否覆盖 shader 声明。
4. 检查 `descriptorType` 是否与 shader resource type 一致。
5. 检查 `stageFlags` 是否覆盖实际使用资源的 shader stage。
6. 检查 `VkPipelineLayoutCreateInfo` 的 `setLayoutCount` 是否不少于 shader 使用的最大 set 索引 + 1。
7. 检查 pipeline 是否用修改后的 pipeline layout 重新创建。
8. 检查 push constant range 是否与 shader `layout(push_constant)` 一致。

---

### 5. 关键证据

### Validation Layer

- 常见 VUID（`[SPEC]`）：
  - `VUID-vkCmdBindDescriptorSets-layout-00xxx`：绑定的 descriptor set layout 与 pipeline layout 中对应 set 的 layout 不兼容。
  - `VUID-vkCmdDraw-None-02697` / `VUID-vkCmdDispatch-None-02699`：shader 访问了 pipeline layout 未声明的资源。
  - `VUID-VkGraphicsPipelineCreateInfo-layout-00756`：pipeline layout 与 shader interface 不兼容。
- Message 通常会指出具体 set、binding 和 descriptor type。

### RenderDoc / AGI

- 观察到：
  - Bound Resources 面板中某些 set / binding 为空，或显示类型不匹配。
  - Pipeline State → Shader 中显示了 `layout(set=1, binding=0)`，但 Pipeline Layout 只有 set 0。
  - 修改 descriptor layout 后没有重新创建 pipeline，导致 pipeline 仍引用旧 layout。
- 关键 resource：`VkPipelineLayout`、`VkDescriptorSetLayout`、shader module。

### Log / Code

- 关键代码：

```text
// shader
layout(set = 1, binding = 0) uniform sampler2D albedo;
layout(set = 1, binding = 1) uniform UBO { vec4 color; } ubo;

// Vulkan 侧错误：pipeline layout 只包含 set 0
VkPipelineLayoutCreateInfo plInfo{};
plInfo.setLayoutCount = 1;          // 错误：shader 使用了 set 1
plInfo.pSetLayouts = &setLayout0;   // 缺少 setLayout1
```

或：

```text
// descriptor set layout 中 binding 顺序与 shader 不一致
VkDescriptorSetLayoutBinding bindings[2];
bindings[0].binding = 0; bindings[0].descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;   // shader binding 0 是 sampler
bindings[1].binding = 1; bindings[1].descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER; // shader binding 1 是 UBO
```

---

### 6. 根因

根因：`VkPipelineLayout` 中声明的 descriptor set layout 与 shader resource interface 不兼容，导致 shader 执行时无法按预期访问 descriptor 资源。

---

### 7. 修复方案

### 最小修复

- 以 shader reflection 结果为准，修正 `VkDescriptorSetLayoutBinding` 的 `binding`、`descriptorType`、`stageFlags`。
- 确保 `VkPipelineLayoutCreateInfo` 的 `pSetLayouts` 覆盖 shader 使用的所有 set 索引。
- 修改 pipeline layout 后，必须重新创建所有依赖该 layout 的 graphics / compute pipeline。
- 更新 descriptor set 的 update 调用，使其与新的 layout 一致。

### 稳定修复

- 使用 shader reflection 自动生成 descriptor set layout 和 pipeline layout，避免手工维护。
- 在 pipeline 创建前增加校验：对比 shader resource manifest 与 pipeline layout 的兼容性。
- 对 push constant range、set count、binding count 做自动化检查并报错。

### 工程化修复

- 为每个 shader pass 定义 descriptor manifest（YAML / JSON），由构建系统生成 C++ layout 代码。
- CI 中运行 shader reflection diff：当 shader 的 set / binding 变化时，强制更新 manifest 并重新生成 pipeline layout。
- 使用 descriptor layout cache，避免重复创建，同时保证同一份 manifest 只对应一个 layout。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 Bound Resources 与 shader declaration 一致。
- [ ] Shader 能正确读取 texture / uniform buffer / storage buffer。
- [ ] 修改 shader 后重新构建，pipeline layout 自动同步。
- [ ] 多帧运行无资源串帧或崩溃。
- [ ] resize / pause / resume 后 descriptor 仍正确。

---

### 9. 经验抽象

Pipeline layout 是 shader 与 descriptor 之间的“接口契约”。排查 descriptor 相关黑屏时，不要只检查 `vkUpdateDescriptorSets`，必须沿整条链路验证：

```text
Shader set/binding
→ DescriptorSetLayout
→ PipelineLayout
→ Pipeline creation
→ vkCmdBindDescriptorSets
→ Shader access
```

只要任一环节与 shader interface 不一致，就会表现为资源读取失败。

---

### 10. 预防规则

1. 禁止手动硬编码 pipeline layout；优先通过 shader reflection 生成。
2. 修改 shader 的 set / binding / push constant 后，必须重新创建 pipeline layout 和所有相关 pipeline。
3. Descriptor set layout 的 `descriptorType`、`stageFlags`、`binding` 必须与 shader reflection 一致。
4. `VkPipelineLayoutCreateInfo` 的 `setLayoutCount` 必须大于 shader 使用的最大 set 索引。
5. 在 CI 中增加 shader manifest diff，确保 Vulkan 侧 layout 与 shader 同步。

---

### 11. 关联 API 卡片

- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`
- `../../03_api_manual/05_descriptor/descriptor_set_layout.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`

---

### 13. 关联 Workflow

- `../../05_workflows/06_pipeline_descriptor/add_pipeline_layout.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`


---

## Case: Uniform Alignment Error

### 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Uniform Buffer / Pipeline |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

### 1. 现象

Shader 中读取的 uniform 数据整体或部分异常：模型矩阵失效、颜色参数偏移、光照常量跳变，或只改了一个 uniform 却影响到另一个。App 通常不 crash，但画面出现几何错位、颜色错误、闪烁的参数。

- 使用 `vkCmdBindDescriptorSets` 配合 `dynamicOffsetCount` 绑定 dynamic UBO 时问题更明显。
- 普通 UBO 也可能因为 host 端结构体 layout 与 shader 期望的 std140/std430 不一致而触发。

---

### 2. 初始上下文

- 使用 graphics 或 compute pipeline。
- Shader 中声明 `layout(set = 0, binding = 0) uniform UBO { ... }`。
- Vulkan 侧创建 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER` 或 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`。
- 通过 `vkUpdateDescriptorSets` 绑定 buffer + offset + range，或通过 `vkCmdBindDescriptorSets` 传入 dynamic offset。
- 多 draw call / dispatch 共享同一 UBO，使用 dynamic offset 切换数据片段。
- 可能涉及 push constant、 specialization constant 与 UBO 混用。

---

### 3. 初始误判

最初容易怀疑：

```text
uniform buffer 没上传；
CPU 端数据写错；
descriptor set 没绑定；
dynamic offset 索引算错；
shader 中变量名拼写错误。
```

但 RenderDoc 中 buffer 内容看起来存在，descriptor 也绑到了正确 buffer；进一步用十六进制查看发现偏移位置的数据与 shader 声明的 layout 对不上。最终定位到 alignment 或 offset 计算错误。

---

### 4. 排查路径

1. 检查 Validation Layer 是否有 alignment / range 相关警告 `[TOOL]`。
2. 在 RenderDoc / AGI 中查看 bound descriptor，确认 buffer、offset、range `[TOOL]`。
3. 对比 shader 中 UBO 字段顺序与 CPU 端结构体字段顺序 `[ENGINE]`。
4. 检查 CPU 端结构体是否使用 std140 或 std430 layout 规则 `[SPEC]`。
5. 检查 `minUniformBufferOffsetAlignment` 要求 `[SPEC]`。
6. 如果是 dynamic UBO，检查 dynamic offset 是否按 alignment 向上取整 `[ENGINE]`。
7. 检查 `vkUpdateDescriptorSets` 中的 `range` 是否覆盖完整结构体 `[SPEC]`。
8. 用十六进制 inspector 对比 CPU 原始数据与 GPU buffer 实际字节 `[TOOL]`。

---

### 5. 关键证据

### Validation Layer

可能出现：

- `VUID-vkCmdBindDescriptorSets-pDynamicOffsets-01971`：dynamic offset 未满足 `minUniformBufferOffsetAlignment`。
- `VUID-vkUpdateDescriptorSets-pDescriptorWrites-02999` / `...-02998`：descriptor buffer range 超过 buffer 大小。
- 部分 validation 驱动不会报错，但 RenderDoc 中能看到数据偏移 `[TOOL]`。

### RenderDoc / AGI

观察到：

- Bound UBO 的 offset 不是 alignment 的整数倍。
- Buffer 内容在 offset 处与预期结构体首字段不吻合。
- 修改一个 uniform 后，相邻字段值也被改变。
- 多 draw call 使用同一 buffer 时，dynamic offset 间隔不一致。

### Log / Code

返回值：

- `vkGetPhysicalDeviceProperties` 中 `limits.minUniformBufferOffsetAlignment` 为 256 字节（常见值）。
- `vkCreateBuffer` 成功，但 offset 计算未对齐。

关键代码：

```text
// 错误示例：dynamic offset 未对齐
uint32_t dynamicOffset = objectIndex * sizeof(UBO); // UBO 大小 144，未按 256 对齐
vkCmdBindDescriptorSets(cmd, bindPoint, layout, 0, 1, &set, 1, &dynamicOffset);

// 错误示例：CPU 端结构体未按 std140 布局
struct UBO {
    glm::vec3 color;   // 实际只占 12 字节，但 std140 要求 vec3 对齐 16 字节
    float roughness;   // 可能被编译器自动对齐，但仍可能出错
    glm::mat4 mvp;     // 起始偏移必须对齐 16 字节
};
```

---

### 6. 根因

根因：uniform buffer 的 CPU 端结构体未按 std140/std430 规则布局，或 dynamic offset / descriptor range 未满足 `minUniformBufferOffsetAlignment`，导致 shader 读取的 uniform 字段与 host 写入的数据在字节偏移上错位。

---

### 7. 修复方案

### 最小修复

- 使用 `alignas(minUniformBufferOffsetAlignment)` 或手动向上取整计算 dynamic offset：
  ```text
  objectIndex * alignedSize(sizeof(UBO), minUniformBufferOffsetAlignment)
  ```
- 将 CPU 结构体改为显式 std140 layout：
  ```text
  struct alignas(16) UBO {
      glm::vec4 color;    // vec3 也建议补成 vec4
      float roughness;
      float pad[3];       // 手动补齐到 16 字节边界
      glm::mat4 mvp;
  };
  ```
- 在 GLSL 中显式指定 `layout(std140, set = 0, binding = 0) uniform UBO { ... };`。

### 稳定修复

- 引入集中式 UBO 布局工具函数，统一处理 alignment 和 padding。
- 使用 shader reflection 自动生成 C++ 侧镜像结构体或 offset 表。
- 在 debug 构建中对所有 UBO dynamic offset 做 assert 校验。
- 对 `minUniformBufferOffsetAlignment` 在启动期读取并缓存，所有 offset 计算都经过该值。

### 工程化修复

- 在 CI 中比较 shader UBO 字段 offset 与 C++ 结构体字段 offset，发现不一致立即报错。
- 使用 `spirv-cross` 或自定义 reflection 生成 uniform block manifest。
- 引入 typed descriptor binder，把 `UBO<T>` 与 alignment 规则绑定，避免手写 offset。
- 对 mobile 和 desktop 分别跑 alignment 测试，捕获不同 `minUniformBufferOffsetAlignment` 下的问题。

---

### 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 UBO offset 满足 `minUniformBufferOffsetAlignment`。
- [ ] Shader 读取的每个 uniform 字段值与 CPU 写入一致。
- [ ] 修改单个 uniform 不影响相邻字段。
- [ ] 多 draw call / dispatch 使用 dynamic offset 时数据正确。
- [ ] 在不同 GPU（alignment 可能不同）上验证通过。
- [ ] 多帧运行稳定。

---

### 9. 经验抽象

Uniform buffer 问题不要只看数据“有没有”，必须检查“在哪里”。关键链路：

```text
CPU struct layout (std140/std430)
→ minUniformBufferOffsetAlignment
→ dynamic offset / descriptor range
→ shader set/binding
→ shader variable offset
```

其中任何一层的 padding 或 alignment 没对齐，都会表现为“部分 uniform 错、整体又不 crash”。

---

### 10. 预防规则

1. 所有 UBO 结构体必须显式使用 std140 或 std430 规则，并用 `alignas` 或手动 padding 保证字段偏移。
2. 所有 dynamic UBO offset 必须经过 `minUniformBufferOffsetAlignment` 向上取整。
3. Descriptor 的 `range` 必须覆盖完整 UBO 结构体，不能按成员大小猜测。
4. GLSL 中必须显式写 `layout(std140, ...)` 或 `layout(std430, ...)`，避免默认规则变化。
5. 新增 uniform 字段后必须同步更新 C++ 镜像结构体和反射表。
6. CI 中必须校验 shader UBO layout 与 C++ 结构体 layout 一致。
7. 不同 GPU 的 `minUniformBufferOffsetAlignment` 差异必须在启动期处理，不要硬编码 256。

---

### 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

### 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

### 13. 关联 Workflow

- `../../05_workflows/05_resource_management/add_uniform_buffer.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`


---

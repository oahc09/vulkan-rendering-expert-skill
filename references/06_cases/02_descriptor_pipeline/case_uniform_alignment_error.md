# Case: Uniform Alignment Error

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Descriptor / Uniform Buffer / Pipeline |
| 平台 | 通用 / Android / Windows / Linux |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

Shader 中读取的 uniform 数据整体或部分异常：模型矩阵失效、颜色参数偏移、光照常量跳变，或只改了一个 uniform 却影响到另一个。App 通常不 crash，但画面出现几何错位、颜色错误、闪烁的参数。

- 使用 `vkCmdBindDescriptorSets` 配合 `dynamicOffsetCount` 绑定 dynamic UBO 时问题更明显。
- 普通 UBO 也可能因为 host 端结构体 layout 与 shader 期望的 std140/std430 不一致而触发。

---

## 2. 初始上下文

- 使用 graphics 或 compute pipeline。
- Shader 中声明 `layout(set = 0, binding = 0) uniform UBO { ... }`。
- Vulkan 侧创建 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER` 或 `VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC`。
- 通过 `vkUpdateDescriptorSets` 绑定 buffer + offset + range，或通过 `vkCmdBindDescriptorSets` 传入 dynamic offset。
- 多 draw call / dispatch 共享同一 UBO，使用 dynamic offset 切换数据片段。
- 可能涉及 push constant、 specialization constant 与 UBO 混用。

---

## 3. 初始误判

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

## 4. 排查路径

1. 检查 Validation Layer 是否有 alignment / range 相关警告 `[TOOL]`。
2. 在 RenderDoc / AGI 中查看 bound descriptor，确认 buffer、offset、range `[TOOL]`。
3. 对比 shader 中 UBO 字段顺序与 CPU 端结构体字段顺序 `[ENGINE]`。
4. 检查 CPU 端结构体是否使用 std140 或 std430 layout 规则 `[SPEC]`。
5. 检查 `minUniformBufferOffsetAlignment` 要求 `[SPEC]`。
6. 如果是 dynamic UBO，检查 dynamic offset 是否按 alignment 向上取整 `[ENGINE]`。
7. 检查 `vkUpdateDescriptorSets` 中的 `range` 是否覆盖完整结构体 `[SPEC]`。
8. 用十六进制 inspector 对比 CPU 原始数据与 GPU buffer 实际字节 `[TOOL]`。

---

## 5. 关键证据

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

## 6. 根因

根因：uniform buffer 的 CPU 端结构体未按 std140/std430 规则布局，或 dynamic offset / descriptor range 未满足 `minUniformBufferOffsetAlignment`，导致 shader 读取的 uniform 字段与 host 写入的数据在字节偏移上错位。

---

## 7. 修复方案

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

## 8. 修复后验证

- [ ] Validation clean。
- [ ] RenderDoc / AGI 中 UBO offset 满足 `minUniformBufferOffsetAlignment`。
- [ ] Shader 读取的每个 uniform 字段值与 CPU 写入一致。
- [ ] 修改单个 uniform 不影响相邻字段。
- [ ] 多 draw call / dispatch 使用 dynamic offset 时数据正确。
- [ ] 在不同 GPU（alignment 可能不同）上验证通过。
- [ ] 多帧运行稳定。

---

## 9. 经验抽象

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

## 10. 预防规则

1. 所有 UBO 结构体必须显式使用 std140 或 std430 规则，并用 `alignas` 或手动 padding 保证字段偏移。
2. 所有 dynamic UBO offset 必须经过 `minUniformBufferOffsetAlignment` 向上取整。
3. Descriptor 的 `range` 必须覆盖完整 UBO 结构体，不能按成员大小猜测。
4. GLSL 中必须显式写 `layout(std140, ...)` 或 `layout(std430, ...)`，避免默认规则变化。
5. 新增 uniform 字段后必须同步更新 C++ 镜像结构体和反射表。
6. CI 中必须校验 shader UBO layout 与 C++ 结构体 layout 一致。
7. 不同 GPU 的 `minUniformBufferOffsetAlignment` 差异必须在启动期处理，不要硬编码 256。

---

## 11. 关联 API 卡片

- `../../03_api_manual/04_buffer_image_memory/buffer.md`
- `../../03_api_manual/05_descriptor/descriptor_set.md`
- `../../03_api_manual/05_descriptor/descriptor_update.md`
- `../../03_api_manual/06_pipeline/pipeline_layout.md`
- `../../03_api_manual/06_pipeline/shader_module.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/03_validation_errors/descriptor_binding_error.md`
- `../../04_debug_playbooks/03_validation_errors/validation_error_decode.md`
- `../../04_debug_playbooks/01_visual_issues/black_screen.md`

---

## 13. 关联 Workflow

- `../../05_workflows/05_resource_management/add_uniform_buffer.md`
- `../../05_workflows/06_pipeline_descriptor/add_descriptor_set.md`
- `../../05_workflows/06_pipeline_descriptor/shader_binding_workflow.md`

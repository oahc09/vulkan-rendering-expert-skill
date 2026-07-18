# 现代 Vulkan 工程模式

本文件补充 Vulkan 1.2/1.3 时代在商业引擎和实际项目中广泛使用的工程模式。这些模式不是 Vulkan 1.0 核心对象链路的替代品，而是在默认 Vulkan 1.3+/1.4 环境下。Vulkan 1.4 设备保证支持 push descriptors / dynamic rendering local read / scalar block layout，无需运行时查询，应优先考虑的实现策略。

---

## 1. VMA (Vulkan Memory Allocator)

### 一句话定位

VMA 是 AMD 开源的 Vulkan 内存分配辅助库，用于替代手动的 `vkAllocateMemory` / `vkBindBufferMemory` / `vkBindImageMemory`。[GUIDE][ENGINE]

### 核心收益

```text
- 自动处理 memory type 选择。
- 按资源需求做 block sub-allocation，减少 VkDeviceMemory 对象数量。
- 支持 dedicated allocation、custom pool、linear allocator、defragmentation。
- 与 Vulkan 1.1+ 的 bindless / device group 特性配合良好。
```

### 适用条件

- 项目需要管理大量 buffer / image / render target。[ENGINE]
- 对内存占用和分配开销敏感（尤其是移动端）。[HEUR]
- 团队不希望在每个资源创建点重复处理 memory requirements。[ENGINE]

### 不适用情况

- 教学示例或极小规模 demo，手动分配更清晰。[HEUR]
- 项目已有自研 memory allocator 且覆盖VMA全部需求。[ENGINE]

### 关键对象链路

```text
VmaAllocator
→ VmaAllocation
→ VkBuffer / VkImage
→ vkBindBufferMemory / vkBindImageMemory（由 VMA 封装）
```

### 风险点

1. 不跟踪 VMA allocation 生命周期就销毁底层 `VkBuffer` / `VkImage`，会导致 allocation leak。[ENGINE]
2. 频繁 `vmaMapMemory` / `vmaUnmapMemory` 持久映射 buffer，需确认 coherent / cached 属性。[SPEC]
3. defragmentation 会移动资源，需确保没有 in-flight command buffer 引用旧 allocation。[ENGINE]

---

## 2. Bindless / Descriptor Indexing

### 一句话定位

利用 `VK_EXT_descriptor_indexing`（Vulkan 1.2 core）让一个 descriptor set 绑定大量 texture / buffer，并通过 shader 下标动态索引，减少 per-draw descriptor 更新。[SPEC][GUIDE]

### 核心收益

```text
- 每帧 descriptor update 次数大幅下降。
- draw call 之间不需要重新绑定 descriptor set（只需 push constants 传索引）。
- 适合 deferred / forward+ / 大量材质贴图场景。
```

### 适用条件

- Vulkan 1.2+ 且目标设备支持 `shaderSampledImageArrayNonUniformIndexing`。[SPEC]
- 材质 / 贴图数量大，传统 per-draw descriptor set 更新成为瓶颈。[ENGINE]
- 渲染器已使用 GPU-driven 或间接绘制。[HEUR]

### 不适用情况

- Vulkan 1.1 以下设备。[SPEC]
- 贴图数量极少，维护 bindless 的收益不抵复杂度。[HEUR]
- 需要频繁动态增删绑定表，而 update after bind 支持不完整。[SPEC]

### 关键对象链路

```text
VkPhysicalDeviceDescriptorIndexingFeatures
→ VkDescriptorSetLayoutBindingFlagsCreateInfo
→ VK_DESCRIPTOR_BINDING_PARTIALLY_BOUND_BIT
→ VK_DESCRIPTOR_BINDING_UPDATE_AFTER_BIND_BIT
→ VkDescriptorSet（大数组）
→ shader 中通过 non-uniform index 采样
```

### 风险点

1. 未正确设置 `nonuniformEXT` 修饰符，可能在某些 GPU 上产生未定义行为。[SPEC]
2. 使用 `UPDATE_AFTER_BIND` 时，必须保证 GPU 读取前 CPU update 已完成，需额外同步。[SPEC][ENGINE]
3. 大 descriptor set 在移动端的内存占用和 layout 切换开销需实测。[VENDOR][HEUR]

---

## 3. Timeline Semaphore 帧模型

### 一句话定位

Timeline Semaphore（Vulkan 1.2 core）用 64-bit 单调递增计数器替代 binary semaphore，统一 acquire / render / present、compute queue / graphics queue、frames-in-flight 之间的同步。[SPEC][GUIDE]

### 核心收益

```text
- 一个 VkSemaphore 可表达多个完成点，减少每帧 semaphore 对象数量。
- 跨 queue submit 的依赖表达更直接。
- 可替代部分 fence 用途，简化 frames-in-flight 资源管理。
```

### 标准帧模型

```text
每帧提交时 signal 一个 timeline value：
→ acquire image（wait timeline N - 1）
→ render / compute submit（signal timeline N）
→ present（wait timeline N）

CPU 侧：
→ 通过 vkGetSemaphoreCounterValue 或 vkWaitSemaphores 判断某 frame resource 是否可复用。
```

### 适用条件

- Vulkan 1.2+ 环境。[SPEC]
- 多 queue（graphics + compute + transfer）协同。[ENGINE]
- 需要精确追踪 frames-in-flight 资源释放时机。[ENGINE]

### 不适用情况

- 仅支持 Vulkan 1.1 或旧驱动。[SPEC]
- 简单单 queue 渲染，binary semaphore + fence 已足够清晰。[HEUR]

### 关键对象链路

```text
VkSemaphoreTypeCreateInfo (VK_SEMAPHORE_TYPE_TIMELINE)
→ vkQueueSubmit2 / VkSemaphoreSubmitInfo (wait/signal value)
→ vkSignalSemaphore / vkWaitSemaphores (CPU 侧等待)
```

### 风险点

1. timeline value 必须单调递增，不能回退。[SPEC]
2. CPU 侧 `vkWaitSemaphores` 需要设置合理超时，避免永久阻塞。[SPEC]
3. 与 swapchain acquire / present 的 semaphore 交互需确认驱动支持。[SPEC][ANDROID]

---

## 4. Dynamic State 优先策略

### 一句话定位

利用 Vulkan 1.3 core 的 Extended Dynamic State（以及 `VK_EXT_extended_dynamic_state`）将 viewport、scissor、depth bias、stencil、blend constant、primitive topology 等状态从 pipeline 创建参数中剥离，减少 pipeline 对象数量。[SPEC][GUIDE]

### 核心收益

```text
- 减少 per-draw 的 pipeline 创建和缓存压力。
- 同一 shader 在不同 viewport / scissor / depth bias 配置下可复用同一个 pipeline。
- 与 dynamic rendering 结合，降低 RenderPass / Framebuffer 预声明成本。
```

### 适用条件

- Vulkan 1.3+ 或支持 `VK_EXT_extended_dynamic_state` 的 1.2 环境。[SPEC]
- 渲染状态（viewport、scissor、depth bias 等）每帧频繁变化。[ENGINE]

### 不适用情况

- 需要兼容旧设备且不支持 dynamic state 扩展。[SPEC]
- 状态变化本身不是瓶颈，追求极致 pipeline state 稳定性。[HEUR]

### 关键 API

```text
vkCmdSetViewport
vkCmdSetScissor
vkCmdSetDepthBias
vkCmdSetBlendConstants
vkCmdSetPrimitiveTopologyEXT
vkCmdSetFrontFaceEXT
vkCmdSetCullModeEXT
vkCmdSetDepthTestEnableEXT
...
```

---

## 5. Mesh Shader / Task Shader

### 一句话定位

Mesh Shader（`VK_EXT_mesh_shader`，Vulkan 1.3+ 可选扩展）用 compute-like shader 直接生成图元，绕过传统 vertex / tessellation / geometry shader 管线。[SPEC][GUIDE]

### 核心收益

```text
- 减少 CPU 侧图元提交和 draw call 数量。
- 支持 GPU-driven culling 和 LOD 选择。
- 适合高密度几何场景和集群渲染。
```

### 适用条件

- 目标 GPU 支持 `VK_EXT_mesh_shader` 或 `VK_NV_mesh_shader`。[SPEC]
- 有 GPU culling / LOD 需求的高性能场景。[ENGINE]

### 不适用情况

- 需要广泛兼容的移动设备（Android 支持度仍有限）。[ANDROID][VENDOR]
- 简单 2D / 低几何复杂度场景，传统 pipeline 更简单。[HEUR]

---

## 6. Variable Rate Shading (VRS)

### 一句话定位

VRS（`VK_KHR_fragment_shading_rate`）允许在 screen space 不同区域使用不同 shading rate，降低 fragment shader 开销。[SPEC][GUIDE]

### 核心收益

```text
- 显著降低 fullscreen pass / 后处理 / 低关注度区域的 fragment 开销。
- 移动端发热和 GPU 占用改善明显。
```

### 适用条件

- 目标设备支持 `VK_KHR_fragment_shading_rate`。[SPEC]
- 后处理 pass 或边缘区域可接受低精度 shading。[ENGINE]
- 移动端性能优化，需配合 tile-based GPU 特性。[VENDOR]

### 不适用情况

- 对画质敏感区域（角色、UI、焦点物体）。[HEUR]
- 设备不支持 VRS 时必须有回退路径。[SPEC]

---

## 7. 何时回退到传统方案

即使默认以 Vulkan 1.3+ 为基准，遇到以下情况仍需回退：

1. 目标设备明确只支持 Vulkan 1.1 或 1.2 且缺少所需扩展。[SPEC]
2. Android 设备驱动对某扩展的实现存在已知 bug。[ANDROID][VENDOR]
3. 性能实测显示现代模式没有收益甚至退化（如低端设备 bindless 开销）。[TOOL]
4. 团队维护成本过高，当前阶段不需要该模式带来的扩展性。[ENGINE]

---

## 8. 相关文件

- `vulkan_object_chain.md` — 核心对象链路。
- `synchronization_lifecycle.md` — Synchronization2 / barrier / timeline semaphore 细节。
- `frame_lifecycle.md` — frames-in-flight 模型。
- `resource_lifecycle.md` — buffer / image / memory 生命周期。
- `../03_api_manual/08_synchronization/semaphore.md` — binary / timeline semaphore API 细节。
- `../03_api_manual/05_descriptor/descriptor_set_layout.md` — descriptor layout 与 binding 设计。
- `../03_api_manual/05_descriptor/descriptor_set.md` — descriptor set 分配与更新。

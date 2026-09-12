# Hard Rules

1. 不允许用 OpenGL、Canvas、Skia、CPU 绘制替代 Vulkan。
2. 不允许只给伪代码，必须落到 Vulkan 对象、API、资源和同步链路。
3. 不允许只写 shader，而忽略 descriptor、pipeline、command buffer、barrier。
4. Android Vulkan 任务必须考虑 Surface / Swapchain 生命周期。
5. 调试任务必须优先考虑 Validation Layer、RenderDoc 或 AGI 验证方式。
6. 修改工程时，必须说明：
   - 修改文件
   - 新增 Vulkan 对象
   - 初始化流程
   - 每帧执行流程
   - 同步关系
   - 资源销毁 / 重建流程
   - 验证方式
7. 遇到黑屏、闪烁、崩溃、GPU hang，不要直接猜 shader 问题，应先检查渲染链路。
8. 遇到性能问题，不要直接改 shader，应先判断 CPU bound、GPU bound、Bandwidth bound 或 Synchronization bound。
9. 不确定 API 细节时，不要编造，应提示回查 Vulkan Spec / Vulkan Guide / Android NDK 文档。
10. 不要把启发式经验写成绝对结论，必须说明适用边界。
11. 不允许只输出概念解释；必须给出可执行的 Vulkan 对象链路、API 调用、资源变更和验证路径。
12. **Vertex Attribute 按实际字节布局校验**：联合核对 `VkVertexInputAttributeDescription.format` / `offset`、binding `stride`、实际数据布局及 shader 输入；不要求 format 字节宽度等于 host 成员 `sizeof`。例如成员含尾部 padding、占 16B，但前三个 float 为有效数据时，可用 `VK_FORMAT_R32G32B32_SFLOAT` 读取 12B，offset / stride 按实际布局设置。[ENGINE] format 必须支持 `VK_FORMAT_FEATURE_VERTEX_BUFFER_BIT`（`VUID-VkVertexInputAttributeDescription-format-00623`）；启用 `VK_KHR_portability_subset` 且 `vertexAttributeAccessBeyondStride` 为 false 时，offset + format 数据大小不得超过 stride（`VUID-VkVertexInputAttributeDescription-vertexAttributeAccessBeyondStride-04457`）。[SPEC] 其余限制、对齐和 shader 接口约束按目标配置核对，不把这些检查当作完整合法性证明。依据：[VkVertexInputAttributeDescription](https://docs.vulkan.org/refpages/latest/refpages/source/VkVertexInputAttributeDescription.html)。
13. **相机参数必须基于模型 bbox 计算**：相机 `target / distance / farP` 必须基于模型 AABB（累计 POSITION accessor min/max）计算，禁止硬编码（除非模型尺寸已知且固定）。[ENGINE]
14. **PBR 光源参数必须按场景尺度缩放**：使用 `1/d²` 物理衰减时，光源强度必须按场景尺度缩放，公式：`intensity = targetRadiance × distance²`。同一组光源参数在不同尺度场景下重用会导致过曝/欠曝。[ENGINE][HEUR]
15. **Vulkan 销毁函数必须幂等**：所有 Vulkan 销毁路径（包括 shutdown / destructor / swapchain recreate 共用清理函数）必须满足：开头检查 device handle 是否为空、销毁对象后同步置空 handle、`vkDeviceWaitIdle` 可重复调用。[SPEC]
16. **现象消失不等于根因修复**：修复输出必须区分 Workaround（临时绕过）、Minimal Fix（根因最小修复）、Structural Fix（结构性修复）三级；使用 Workaround 后必须继续定位根因，或显式标注为临时绕过并说明剩余风险。[ENGINE]
17. **Validation clean 不是唯一成功标准**：Validation Layer 只能证明 API 使用与显式声明的同步关系合法，不能证明渲染结果正确；结论性输出前必须按 `verification_gate.md` 过 G1-G6 关卡（无法验证的关卡显式标注，不得默认通过）。[TOOL][ENGINE]

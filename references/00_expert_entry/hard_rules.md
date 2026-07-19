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
12. **Vertex Attribute 字节宽度必须匹配**：`VkVertexInputAttributeDescription.format` 的字节宽度必须等于 host 端顶点结构对应成员的 `sizeof`。常见 `VkFormat` 字节数：`VK_FORMAT_R8G8B8A8_*` = 4B，`VK_FORMAT_R32G32_*` = 8B，`VK_FORMAT_R32G32B32_*` = 12B，`VK_FORMAT_R32G32B32A32_*` = 16B。违反 → `VUID-VkVertexInputAttributeDescription-format-04515`。[SPEC] 第三方数学库（GLM/DirectXMath/Eigen）的类型对照表不属于技能范畴，由开发者按所用 SDK 自行计算 `sizeof`。
13. **相机参数必须基于模型 bbox 计算**：相机 `target / distance / farP` 必须基于模型 AABB（累计 POSITION accessor min/max）计算，禁止硬编码（除非模型尺寸已知且固定）。[ENGINE]
14. **PBR 光源参数必须按场景尺度缩放**：使用 `1/d²` 物理衰减时，光源强度必须按场景尺度缩放，公式：`intensity = targetRadiance × distance²`。同一组光源参数在不同尺度场景下重用会导致过曝/欠曝。[ENGINE][HEUR]
15. **Vulkan 销毁函数必须幂等**：所有 Vulkan 销毁路径（包括 shutdown / destructor / swapchain recreate 共用清理函数）必须满足：开头检查 device handle 是否为空、销毁对象后同步置空 handle、`vkDeviceWaitIdle` 可重复调用。[SPEC]

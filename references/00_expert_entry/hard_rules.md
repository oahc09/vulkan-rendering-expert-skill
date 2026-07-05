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

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
13. **资产预览可按包围盒自动取景**：验证陌生模型的可见性时，可用实际包围盒设置相机目标、距离和远裁剪面。已有交互相机、镜头或标定参数按项目需求处理。[ENGINE]
14. **资产预览可校准光照尺度**：仅在采用 `1/d²` 衰减且其余条件固定的预览或诊断中，可按距离平方调整强度以对照同一观测点。生产场景保留光源单位、材质和曝光约定。[ENGINE][HEUR]
15. **应用清理入口可安全重复进入**：shutdown / destructor / recreate 共用的封装以资源归属和状态防止重复销毁，释放成功后清空应用侧记录。[ENGINE] Vulkan 调用应遵守各命令的对象有效性、可空参数和主机同步条件。`vkDeviceWaitIdle` 只接收有效 device，检查包括 `VK_ERROR_DEVICE_LOST` 在内的返回值。[SPEC] [规范](https://docs.vulkan.org/refpages/latest/refpages/source/vkDeviceWaitIdle.html)
16. **现象消失不等于根因修复**：修复输出必须区分 Workaround（临时绕过）、Minimal Fix（根因最小修复）、Structural Fix（结构性修复）三级；使用 Workaround 后必须继续定位根因，或显式标注为临时绕过并说明剩余风险。[ENGINE]
17. **Validation clean 不是唯一成功标准**：仅表示当前层版本、配置与已执行路径未检测到相关违规，不证明所有 API / 同步合法或渲染结果正确。实际实现、修复或性能改善结论按 `verification_gate.md` 检查 G1-G6；纯知识问答引用规范与边界，设计审查列验证计划；受影响但未执行的关卡显式标未验证，不得默认通过。[TOOL][ENGINE]

18. **真实项目判断必须绑定源码证据**：当任务针对一个实际代码仓库时，关于“当前项目如何实现”的关键结论必须给出 `[CODE]` 证据（文件路径 + 类 / 函数 + 关键行为）；仅看到文件名 / 类名但未读取实现时必须标记“未验证”。`[CODE]` 只证明项目事实，不能覆盖 `[SPEC]`；项目实现与规范冲突时应报告实现风险。[CODE][ENGINE]

19. **跨模块项目诊断须建立 Architecture Map**：版本迁移、跨模块问题或生命周期交接先给 `[CODE]` Evidence Map 和 Architecture Map，再进入根因、Change Impact 或 Implementation Handoff。地图仅覆盖相关主链，缺失环节标为“未验证”。已定位到单一函数或 VUID 且影响限于局部时，输出源码位置、受影响对象链及定向验证。影响可能越过局部边界时按跨模块诊断处理。[CODE][ENGINE]

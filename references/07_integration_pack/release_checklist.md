# Release Checklist

## 1. 结构检查

- [ ] 目录结构完整。
- [ ] 每个模块有 README。
- [ ] 模板文件齐全。
- [ ] 索引文件齐全。
- [ ] 文件命名一致。
- [ ] 模块编号一致。
- [ ] 没有重复或废弃文件混入主路径。

## 2. 行为检查

- [ ] 不会默认加载全部模块。
- [ ] 能按任务路由到正确模块。
- [ ] Debug 问题优先走 Debug Playbook。
- [ ] 设计任务优先走 Workflow。
- [ ] API 问题优先走 API Manual。
- [ ] 经验问题优先走 Cases。
- [ ] Android 生命周期问题会走 Android 专项路径。
- [ ] 性能问题会先做瓶颈分类。

## 3. 准确性检查

- [ ] API 硬规则有来源等级。
- [ ] 不确定 API 细节会提示回查官方文档。
- [ ] 性能建议没有绝对化。
- [ ] Android 建议明确适用场景。
- [ ] Debug 结论有工具验证路径。
- [ ] Case 中的经验抽象没有过度泛化。
- [ ] Workflow 中有验证闭环。

## 4. Vulkan 专家能力检查

用以下问题测试：

1. Android Vulkan 黑屏怎么排查？
2. Descriptor binding mismatch 怎么定位？
3. 新增 fullscreen pass 怎么设计？
4. Compute 写 storage image 后 fragment 采样怎么同步？
5. Android 横竖屏 swapchain recreate 怎么做？
6. Vulkan 后处理 GPU 高怎么优化？
7. 类似问题有没有真实案例？

每个问题都应该能路由到正确模块。

## 5. 输出质量检查

- [ ] 先结论后细节。
- [ ] 能给对象链路。
- [ ] 能给同步 / layout 风险。
- [ ] 能给 Android 注意点，如适用。
- [ ] 能给工具验证方式。
- [ ] 不堆无关 Vulkan 背景。
- [ ] 不用 OpenGL / Canvas / Skia 替代 Vulkan。
- [ ] 不只写 shader 而忽略 Vulkan 链路。

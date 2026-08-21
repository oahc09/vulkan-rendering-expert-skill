# Regression Checklist

统一的回归验证清单。任何修改（修复、新增、优化）在宣布完成前，按影响面选择对应类别执行回归。

> 使用方式：先按 `../02_core_mental_model/regression_reasoning.md` 推导影响面，再执行本清单中受影响类别的条目；出口判定按 `../00_expert_entry/verification_gate.md`。

---

## 1. Correctness 回归

- [ ] Validation Layer 无新增错误（debug / release 两个 build 都确认）。
- [ ] 关键 VUID 约束没有违反（对象类型、handle 归属、flag 组合）。
- [ ] API 返回值全部检查，无忽略的错误码。
- [ ] 修改点周边代码路径（if / else 分支、错误路径）都被执行到。
- [ ] 多帧连续运行无 crash、无 device lost、无 validation 报错。

## 2. Rendering 回归

- [ ] RenderDoc 抓帧：draw / dispatch 数量符合预期。
- [ ] 每个 pass 的输入 / 输出内容符合预期（纹理、render target）。
- [ ] descriptor 绑定的资源正确（无空绑定、无旧资源残留）。
- [ ] 画面结果与修改前基线对比：预期变化发生，非预期变化未发生。
- [ ] 边界视角 / 边界参数下无异常（近远裁剪、特殊 clear value、极端相机距离）。

## 3. Resource Lifecycle 回归

- [ ] 新建对象全部有对应销毁路径（无泄漏）。
- [ ] 销毁 / 重建前 in-flight 工作已等待（fence / `vkDeviceWaitIdle`）。
- [ ] swapchain recreate 后旧资源（image view / framebuffer / 尺寸相关 image）同步销毁。
- [ ] 销毁函数幂等（重复调用不崩溃、不 double free）。
- [ ] 内存 / 对象计数稳定（长时间运行无持续增长）。

## 4. Synchronization 回归

- [ ] 修改涉及的每个依赖都明确了 producer / consumer / stage / access / layout。
- [ ] fence / semaphore / barrier 的用途没有混用。
- [ ] acquire / present 的 semaphore 配对正确。
- [ ] 跨 queue（compute ↔ graphics）依赖有 barrier 或 semaphore 覆盖。
- [ ] 多帧压力下无闪烁、无撕裂、无 GPU hang。

## 5. Android Lifecycle 回归

- [ ] 横竖屏切换（rotation）后画面正确、无 crash。
- [ ] pause → resume 后渲染恢复、无黑屏、无 stale swapchain。
- [ ] Surface destroyed 后 render thread 停止 present，无 use-after-free。
- [ ] Surface recreated 后 swapchain 与尺寸相关资源完整重建。
- [ ] extent 为 0（Surface 未就绪）时正确等待 / 跳帧，无非法创建。
- [ ] logcat 无 surface / swapchain / native window 相关错误。

## 6. Performance 回归

- [ ] 修改目标指标有量化前后对比（frame time / bandwidth / draw call 数）。
- [ ] 没有引入新的瓶颈（CPU 提交耗时、GPU 占用、带宽）。
- [ ] 优化未破坏正确性（画面与基线一致）。
- [ ] 低端设备 / 移动端场景下无退化。

---

## 7. 结果判定

1. 所有受影响类别的条目通过 → 修改完成。
2. 存在无法执行的条目 → 显式列出"未验证项"与原因，不得默认通过。
3. 存在失败条目 → 修改未完成，回到定位 / 修复循环。
4. Validation clean 只是 Correctness 回归的一部分，不能单独作为完成依据。

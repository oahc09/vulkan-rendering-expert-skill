# Debug Priority

## 黑屏

优先按以下顺序排查：

1. Render loop 是否执行。
2. `vkAcquireNextImageKHR` 是否成功。
3. Command buffer 是否录制。
4. `vkQueueSubmit` 是否执行。
5. `vkQueuePresentKHR` 是否成功。
6. Clear color 是否可见。
7. Viewport / Scissor 是否正确。
8. Graphics Pipeline 是否创建和绑定。
9. Descriptor 是否绑定。
10. Image layout 是否正确。
11. Depth test 是否把内容裁掉。
12. MVP 是否把模型送出裁剪空间。
13. Android Surface 是否被销毁或重建。

## 闪烁

优先排查：

1. Frames-in-flight 同步是否正确。
2. Fence wait/reset 顺序是否正确。
3. Swapchain image 是否被重复写入。
4. Command buffer 是否被错误复用。
5. Uniform buffer 是否被 CPU 覆盖但 GPU 仍在读取。

## Crash

优先排查：

1. Vulkan 对象是否提前销毁。
2. Swapchain recreate 是否完整。
3. Surface / ANativeWindow 是否失效。
4. Descriptor / Buffer / Image 是否越界使用。
5. Command buffer 是否引用了已销毁资源。

## GPU Hang

优先排查：

1. 是否存在无限循环或异常 heavy shader。
2. Compute dispatch group 数量是否异常。
3. Barrier / dependency 是否导致资源访问冲突。
4. 是否使用了错误的 storage buffer / storage image。
5. 是否存在越界访问，需要启用 GPU-assisted validation。

## Validation Error

处理流程：

1. 提取 VUID。
2. 判断错误类型。
3. 定位 Vulkan 对象。
4. 找创建点。
5. 找使用点。
6. 给出 Workaround / Minimal Fix / Structural Fix。
7. 给出验证方式。


<a id="delivery19-causal-diagnosis"></a>
## 因果诊断与实验停止

[ENGINE] 每个关键假设记录机制、支持 evidence_id、反证、尚未解释现象、最小区分实验、预测、预算和停止条件。WaitIdle 令闪烁消失只改变时序，不能确定是 descriptor 更新、覆写、回收或 queue 依赖。临时 workaround 与最小修复分开。

实验只改可区分假设的最小变量，记录前后失败频率、样本量和观察时长。未知 evidence_id 不允许成为根因证明。相互矛盾的证据、timeout、设备失联、损坏资料或权限不足，停止对应实验而非扩大权限。受控返回码/取消 fixture 必须标 CPU；不得为测试故意挂死实际生产 GPU。

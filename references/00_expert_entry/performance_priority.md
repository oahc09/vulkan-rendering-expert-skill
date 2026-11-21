# Performance Priority

性能问题先判断瓶颈类型。

## CPU Bound

常见原因：

- Command buffer 每帧录制过重
- Descriptor 每帧频繁 allocate / update
- Pipeline 运行时创建
- `vkQueueSubmit` 次数过多
- Fence wait 阻塞 CPU

## GPU Fragment Bound

常见原因：

- Fragment shader 太重
- Texture sampling 过多
- Overdraw 高
- Fullscreen pass 太多
- 透明混合过多

## Bandwidth Bound

常见原因：

- 大尺寸 render target
- 多 pass 读写
- MSAA resolve
- 频繁 offscreen pass
- 移动端 tile resolve
- 高精度 attachment 滥用

## Synchronization Bound

常见原因：

- Barrier 过宽
- Stage mask 过保守
- Queue idle
- Fence 等待错误
- Layout transition 过多

## Mobile GPU Priority

移动端优先关注：

1. Fullscreen pass 数量。
2. Render target 分辨率。
3. Attachment load/store。
4. Tile resolve 次数。
5. Texture sampling 数量。
6. Alpha blending / overdraw。
7. 是否存在不必要的中间图读写。


<a id="delivery19-joint-ab"></a>
## 性能与质量联合 A/B

[ENGINE] 预登记 scene/seed/相机/输入/分辨率/设备/driver、cache冷热、预热、温度/电源/后台负载、A/B顺序和重复数；诊断插桩不同的样本不能直接当性能对照。指标分开报告 CPU、GPU pass、全帧、submit/wait、present、峰值内存、质量、延迟及可测功耗。

预先给各必需指标退化上界。单 pass 更快但全帧变慢或质量越界，应撤销；没有用户权重时不编综合分抵消关键退化。缺数据标 UNVERIFIED，不从耗时推导带宽/功耗收益。短时软件 Vulkan 时间仅该实现观察，不推断 Adreno/Mali 热稳态。

降级有迟滞和复评条件，切档同步 history/pipeline/resource generation。第二设备退化时缩小经验适用范围并保留原路径。

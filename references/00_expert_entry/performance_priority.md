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

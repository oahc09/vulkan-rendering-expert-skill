# Case Tags

> 文件建议路径：`case_tags.md`

---

## 1. 问题类型标签

```text
black-screen
flickering
crash
validation-error
device-lost
gpu-hang
performance
wrong-color
texture-black
depth-error
```

---

## 2. Vulkan 子系统标签

```text
swapchain
surface
anativewindow
command-buffer
queue-submit
descriptor
pipeline
pipeline-layout
image-layout
barrier
synchronization2
memory
buffer
image
image-view
sampler
render-pass
dynamic-rendering
compute
storage-buffer
storage-image
timeline-semaphore
fence
semaphore
```

---

## 3. 平台标签

```text
android
desktop
mobile
surfaceview
nativeactivity
anativewindow
windows
linux
```

---

## 4. 工具证据标签

```text
validation-layer
renderdoc
agi
logcat
vuid
sync-validation
gpu-assisted-validation
native-crash-stack
```

---

## 5. 根因类型标签

```text
missing-barrier
wrong-layout
wrong-binding
lifetime-error
in-flight-resource
surface-lifecycle
swapchain-recreate
bandwidth-high
tile-resolve
descriptor-overhead
pipeline-stutter
wrong-viewport
wrong-scissor
depth-cull
mvp-error
extent-zero
```

---

## 6. 严重程度标签

```text
P0
P1
P2
```

建议定义：

- `P0`：crash、device lost、完全黑屏、无法运行。
- `P1`：视觉错误、闪烁、资源错误、性能明显异常。
- `P2`：偶发问题、优化建议、架构改进。

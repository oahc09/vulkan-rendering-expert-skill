# API 手册设计策略

## API 手册是必须的

Vulkan API 细节高度依赖：

```text
结构体字段
flag 组合
Valid Usage
对象生命周期
同步规则
扩展版本
平台差异
```

因此 Vulkan Skill 必须有 API Manual。但它不应该复制官方文档，而应该把官方事实转写成专家可用的工程卡片。

## 不推荐的方式

不要把 API Manual 写成：

```text
vkCreateInstance 是什么
vkCreateDevice 是什么
vkCreateSwapchainKHR 是什么
每个字段逐字解释
```

这种写法会变成低效百科，token 消耗大，也不利于排错。

## 推荐方式

采用：

```text
API Card + Usage Pattern + Failure Mode + Debug Method
```

每张卡片回答：

1. 这个 API / 对象在工程链路中解决什么问题？
2. 它和哪些 Vulkan 对象有关？
3. 典型调用顺序是什么？
4. 哪些参数最容易错？
5. 哪些 Validation Error 常见？
6. 出错时如何沿对象链路反查？
7. 如何用工具验证？

## API Manual 目录建议

```text
03_api_manual/
├── README.md
├── api_index.md
├── instance_device_queue.md
├── surface_swapchain.md
├── command_buffer.md
├── buffer_image_memory.md
├── descriptor.md
├── pipeline.md
├── render_pass_dynamic_rendering.md
├── synchronization.md
├── compute.md
├── debug_utils_validation.md
└── android_platform.md
```

## 分层方式

### 基础 API 卡片

用于覆盖 Vulkan 最常用链路：

```text
Instance / Device / Queue
Surface / Swapchain
Command Buffer
Buffer / Image / Memory
Descriptor
Pipeline
Synchronization
Debug Utils
```

### 专家 API 卡片

用于覆盖高级特性和现代 Vulkan：

```text
Synchronization2
Dynamic Rendering
Timeline Semaphore
Descriptor Indexing
Descriptor Buffer
Pipeline Cache
Render Graph Resource Lifetime
Frames in Flight
Android Swapchain Recreate
Compute + Graphics Barrier
```

## API 卡片粒度

不建议一个 API 一个文件。更推荐按工程链路聚合：

```text
Descriptor Set 相关 API 放在 descriptor.md
Swapchain 相关 API 放在 surface_swapchain.md
Pipeline 相关 API 放在 pipeline.md
Synchronization 相关 API 放在 synchronization.md
```

原因：专家排错不是按 API 名称排，而是按对象关系和生命周期排。

## API Manual 与 Core Mental Model 的边界

`02_core_mental_model` 负责：

```text
对象关系
生命周期
同步模型
资源流转
Android Surface / Swapchain 状态
```

`03_api_manual` 负责：

```text
具体 API 参数
结构体字段
flag 组合
VUID
扩展版本
代码片段
Validation Error 对照
```

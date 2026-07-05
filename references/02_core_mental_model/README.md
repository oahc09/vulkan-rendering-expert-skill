# 模块 3：Vulkan 核心心智模型

## 模块定位

本模块定义 Vulkan Expert Skill 的核心心智模型。

它不负责解释完整 API 参数，而是建立以下关系：

```text
Vulkan 对象链路
一帧渲染生命周期
资源生命周期
同步生命周期
Pipeline / Descriptor / Shader 绑定关系
Render Target / Image Layout 关系
Android Surface / Swapchain 生命周期
Compute 与 Graphics 的资源交互关系
```

## 核心目标

让 AI 在回答任何 Vulkan 问题前，先自动建立：

1. 对象链路图。
2. 帧生命周期图。
3. 资源生命周期图。
4. 同步依赖图。
5. Android Surface / Swapchain 生命周期图。

## 文件说明

```text
README.md                                # 模块说明
vulkan_object_chain.md                   # Vulkan 对象链路
frame_lifecycle.md                       # 一帧渲染生命周期
resource_lifecycle.md                    # Buffer / Image / Swapchain Image 生命周期
synchronization_lifecycle.md             # Fence / Semaphore / Barrier / Sync2 心智模型
pipeline_descriptor_relationship.md      # Shader / Descriptor / PipelineLayout 关系
render_target_model.md                   # Render Target / RenderPass / Dynamic Rendering 模型
android_surface_swapchain_lifecycle.md   # Android Surface / Swapchain 生命周期
compute_graphics_relationship.md         # Compute 与 Graphics 交互关系
mental_model_checklist.md                # 回答前检查清单
common_misconceptions.md                 # 高频误区
```

## 与 API Manual 的边界

本模块负责：

```text
对象关系
生命周期
同步模型
资源流转
Android Surface / Swapchain 状态
```

API Manual 负责：

```text
具体 API 参数
结构体字段
flag 组合
VUID
扩展版本
代码片段
Validation Error 对照
```

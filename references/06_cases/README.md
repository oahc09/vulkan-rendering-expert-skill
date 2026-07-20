# 06_cases：Vulkan 真实案例库模块

## 1. 模块定位

`06_cases` 是 Vulkan Expert Skill 的真实案例库模块。

它以真实工程问题复盘为核心，记录：

```text
现象
→ 初始上下文
→ 初始误判
→ 排查路径
→ 关键证据
→ 根因
→ 修复方案
→ 修复后验证
→ 经验抽象
→ 预防规则
```

它不是 API 手册、不是 Debug Playbook、也不是 Workflow，而是用于沉淀真实 Vulkan 工程经验。

---

## 2. 模块目标

本模块的目标是把前面模块中的抽象规则转化为真实经验：

| 前置模块 | 提供内容 |
|---|---|
| `03_api_manual` | API 对象链路与使用风险 |
| `04_debug_playbooks` | 故障排查流程 |
| `05_workflows` | 正向工程任务流程 |
| `06_cases` | 真实问题如何发生、如何误判、如何定位、如何修复 |

高级 Vulkan 专家的价值通常来自案例判断，例如：

```text
这个黑屏不像 shader 错，更像 layout transition 缺失。
这个闪烁不像 present 问题，更像 frame resource 被 CPU 提前覆盖。
这个 Android 崩溃不像 Vulkan 初始化错，更像 Surface destroyed 后 render thread 还在 present。
这个 compute 无输出不像 dispatch 没执行，更像 compute 写后 graphics 读缺少 barrier。
```

这些判断需要通过 case 来沉淀。

---

## 3. 推荐目录结构

```text
06_cases/
├── README.md
├── case_template.md
├── case_index.md
├── case_tags.md
│
├── 01_black_screen/
│   └── case_black_screen.md              （合并 4 个原 case）
│
├── 02_descriptor_pipeline/
│   └── case_descriptor_pipeline.md       （合并 4 个原 case）
│
├── 03_sync_layout/
│   └── case_sync_layout.md               （合并 4 个原 case）
│
├── 04_swapchain_android/
│   └── case_swapchain_android.md         （合并 4 个原 case）
│
├── 05_compute/
│   └── case_compute.md                   （合并 4 个原 case）
│
├── 06_performance/
│   └── case_performance.md               （合并 5 个原 case）
│
└── 07_engine_architecture/
    └── case_engine_architecture.md       （合并 4 个原 case）
```

> 每个合并文件内部以 `## Case: <原 case 名>` 作为锚点保留全部内容，向量检索仍可命中原 case 主题。

---

## 4. P0 首批案例

第一批建议优先完成 12 个高价值案例：

### 黑屏类

- `01_black_screen/case_black_screen.md`
- `01_black_screen/case_black_screen.md`
- `01_black_screen/case_black_screen.md`

### Descriptor / Pipeline 类

- `02_descriptor_pipeline/case_descriptor_pipeline.md`
- `02_descriptor_pipeline/case_descriptor_pipeline.md`
- `02_descriptor_pipeline/case_descriptor_pipeline.md`

### 同步 / Layout 类

- `03_sync_layout/case_sync_layout.md`
- `03_sync_layout/case_sync_layout.md`
- `03_sync_layout/case_sync_layout.md`

### Android Swapchain 类

- `04_swapchain_android/case_swapchain_android.md`
- `04_swapchain_android/case_swapchain_android.md`
- `04_swapchain_android/case_swapchain_android.md`

---

## 5. 使用方式

当用户提出真实问题时，优先根据现象检索 case：

```text
黑屏
→ 查 01_black_screen

descriptor 报错
→ 查 02_descriptor_pipeline

compute 输出异常
→ 查 03_sync_layout 或 05_compute

Android rotation / pause / resume 崩溃
→ 查 04_swapchain_android

GPU frame time 高
→ 查 06_performance
```

每个 case 必须连接：

- 相关 API 卡片
- 相关 Debug Playbook
- 相关 Workflow
- 关键工具证据
- 可复用预防规则

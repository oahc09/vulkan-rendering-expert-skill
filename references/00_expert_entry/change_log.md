# Change Log

## v0.1

- 建立专家行为控制模块。
- 拆分 role、hard rules、task classifier、response formats、debug priority、performance priority、accuracy check。
- 控制根目录 `../../SKILL.md` 只作为入口，不承载大段知识。
- 引入准确性分级：12 标签体系（详见 `01_source_map_and_api_manual_strategy/source_tags.md`）。

## v0.1 决策（已解决）

- 默认使用 Vulkan 1.3+，但保留 1.0/1.1/1.2 兼容说明。[GUIDE][ENGINE]
- 新项目默认推荐 Dynamic Rendering，复杂多 subpass 场景保留 RenderPass。[GUIDE][ENGINE]
- Android 默认以 SurfaceView + ANativeWindow 为主，其他方案（如 TextureView）需说明限制。[ANDROID]
- 不强制要求 RenderDoc / AGI，但 Debug 结论必须提供可验证路径；有工具时应优先使用。[TOOL][ENGINE]
- 增加“禁止只输出概念解释”规则，已写入 `hard_rules.md`。[ENGINE]
- 项目级文件修改模板暂缓到 v0.2，当前通过 `hard_rules.md` 第 6 条覆盖核心修改要求。

## 待调整

- v0.2 是否加入项目级文件修改模板。（已解决：当前通过 `hard_rules.md` 第 6 条覆盖核心修改要求，v0.2 不再单独加入模板。）

## v1.0.1

### Vulkan 1.4 知识库补充

- 补充核心化扩展、强制功能、最低限制提升。[GUIDE][SPEC]
- 新增 15 张卡片（vulkan_1_4_overview、timeline_semaphore、descriptor_indexing 等）。
- 增量补充 5 张已有卡片（dynamic_rendering、synchronization2 等）。
- 版本基线从 Vulkan 1.3+ 升级为 Vulkan 1.3+/1.4。

### 新增硬规则（hard_rules.md #12-#15）

- **#12 Vertex Attribute 字节宽度匹配**：`format` 字节宽度 == host struct `sizeof`，违反触发 VUID-04515。[SPEC]
- **#13 相机参数基于模型 bbox**：`target/distance/farP` 必须基于 AABB 计算，禁止硬编码。[ENGINE]
- **#14 PBR 光源按尺度缩放**：`1/d²` 衰减下 `intensity = targetRadiance × distance²`。[ENGINE][HEUR]
- **#15 Vulkan 销毁幂等**：handle 置空 + `vkDeviceWaitIdle` 可重复 + `vkDestroy*` 容忍 NULL_HANDLE。[SPEC]

### 第三方库 API 准确性规则（accuracy_check.md）

- 新增 "Third-Party Library API Accuracy" 小节，6 条规则：标注版本号、6 个月回查、不编造签名、Vulkan backend 双重标注、API 变更点显式列出、检索优先最新 release notes。

### 任务路由与检索策略

- `../07_integration_pack/task_routing_rules.md` 新增第 10 类任务"第三方库集成类"。
- `../07_integration_pack/retrieval_policy.md` 新增 §5 第三方库 API 检索规则。

### 资源生命周期与幂等销毁设计

- `../05_workflows/05_resource_management/manage_resource_lifetime.md` 新增"幂等销毁设计"与"常见多次调用场景"小节（含 SafeDestroy wrapper + 5 类组合调用：main+析构、异常+正常、窗口关闭+析构、swapchain recreate+shutdown、device lost+析构）。
- `../02_core_mental_model/resource_lifecycle.md` 新增"幂等销毁"心智模型小节。

### 行尾规范化

- `../05_workflows/workflow_index.md`、`../07_integration_pack/retrieval_policy.md` 由 CRLF 转 LF。

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

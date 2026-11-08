# Agensi 免费上架准备与人工验收

本文件是发布维护者清单，不是 Agent 运行时附件，也不是上架成功证明。
保留 MIT、免费分发和原知识库；不为单个平台修改通用 `SKILL.md` frontmatter。

## 宿主配置边界

在审查基线 `b2055b8c64369684d0bc508206cdc1fbe074f597`，仓库中未找到读取
`agents/claude-code.yaml` 的宿主运行时解析器。原 `scripts/check-skill.mjs`
只把它纳入内容指纹，不解析其 YAML；文件名不能证明 Claude Code 会读取它。
它是示意集成配置，不能视为已验证的 Claude Code 配置 schema。
v1.0.10 保留其与 v1.0.9 一致的最小启动契约，未改其他宿主配置：

1. `SKILL.md`；
2. `references/00_expert_entry/hard_rules.md` **全文**；
3. `references/07_integration_pack/task_routing_rules.md#routing-entry` **完整段落**。

再按命中类型读取知识与模板。若宿主不支持段落读取，全文读取目标文件，不能跳过规则，
也不能宣称测得 token 节省。实际宿主发现、加载与执行行为仍须人工验收。

## 上架表单手填建议

上传前核对候选提交、包清单及 `SKILL.md` 的实际版本；不要自动发布。

| 字段 | 手填建议 |
| --- | --- |
| Title | Vulkan Rendering Expert Skill |
| version | 1.0.16（必须与本次候选 `metadata.version` 相同） |
| summary | Engineering-focused Vulkan guidance for rendering architecture, debugging, synchronization, Android integration, performance optimization, and source-level verification. |
| tags | vulkan, rendering, android, graphics-engine, debugging, performance, synchronization |
| use_cases | Diagnose black screens and validation errors; reason about synchronization and resource lifetimes; investigate Android surface/swapchain issues; assess performance bottlenecks; compare rendering architecture options. |
| Price | Free |
| License | MIT |
| Canonical source | https://github.com/oahc09/vulkan-rendering-expert-skill |

建议说明：本技能是工程分析与验证指导，不是自动 GPU 调试服务；需要项目上下文和独立验证。

### 两种上传渠道不可混淆

依据 [Agensi packaging 文档](https://www.agensi.io/docs/packaging)（2026-10-30 核验）：

- **网站上传**：最多 1,000 文件、50 MB。白名单包 `SKILL.md`、`LICENSE`、
  `README_EN.md`、`references/**` v1.0.10 基线为 **196 文件**，v1.0.11 最多4份新增后预算 **200 文件**，文件数可行；仍须检查生成包实际大小及平台结果。
- **Agent 上传**：最多 100 文件、5 MB。196 文件包超过数量限制，**不能使用该渠道**，即使大小低于 5 MB。
- **交付给 Agent**：1 个 `SKILL.md` 加最多 200 个附加文本文件，合计最多 600 万字符。
  v1.0.10有195个、v1.0.11预算199个附加文件；仍须由打包报告确认实际字符数。上传限制与交付限制不是一回事。
- `.git`、`agents/`、`assets/`、`scripts/`、本清单与测试不能进入白名单包。
  本地自检依赖完整 checkout，不应作为买家 Agent 的运行时功能。

限制可能变化，实际上传前重新核验官方文档。未执行平台八项扫描、审核或真正上传。

## 发布期静态检查

使用 Python 3.9+、Git、Node.js 及发布环境的 PyYAML（本次环境 6.0.3；版本固定于
`scripts/requirements-release.txt`）。依赖仅用于发布检查，
不附带给 Agent；PyYAML 使用 SafeLoader 并拒绝重复映射键，不执行 YAML 对象构造。

```bash
python -m pip install -r scripts/requirements-release.txt
node scripts/check-skill.mjs
python scripts/host_contract.py
python -m unittest discover -s scripts -p 'test_*.py'
```

`host_contract.py` 验证示意配置最小集合、契约路径、路由与模板显式锚点。
`validate_documents` 提供打包器使用的语义 frontmatter 与本地引用检查。
Markdown 校验有意限于普通行内链接、入口反引号路径和独立行显式 `<a id="..."></a>`，
忽略 fenced 代码，不实现隐式标题 slug、reference-style 链接或远程页面正确性。
缺失显式锚点失败，不把字符串存在等同于模型执行正确。

打包前工作树必须干净，受跟踪文件的实际字节必须与 HEAD 相同；请用 LF checkout。
`autocrlf` 等导致的字节变化会失败关闭，不会静默混入包。风险模式扫描范围是交付白名单，
不是整个仓库、Git 历史秘密扫描或完整安全证明。实际输出到仓库外，检查 ZIP CRC、SHA-256、
文件数及字符报告；通过静态检查不等于 Agensi 审核通过。

经维护者审核并提交候选后，在干净 checkout 中执行（不推送、不上传）：

```bash
git status --short
git rev-parse HEAD
# 输出目录须已存在、位于 checkout 外；文件名不得已存在。
python scripts/agensi_audit_and_pack.py . \
  --out /absolute/path/outside-checkout/vulkan-rendering-expert-skill-1.0.16-agensi-free.zip
```

把示例输出路径替换为自己的仓库外目录。保留 JSON 报告用于关联 commit、包内容和 SHA-256；
不要通过允许脏树、覆盖输出或删除知识文件来绕过失败。

## 四类目标 Agent 人工验收（全部未运行）

### 共通执行与证据要求

- 对每类开启独立目标 Agent 会话，只提供技能入口与原始问题，不提供下述判据或历史回答。
- 记录日期、候选 commit / dirty diff、ZIP SHA-256、宿主及可取得的模型版本、实际加载文件/锚点、
  原始回答、工具日志、人工判定（通过 / 失败 / 未运行）及依据。无法观察加载时写“加载未验证”。
- 人工检查最小启动三项确实加载、硬规则完整、路由后按需读取，证据不足时不虚构 API/VUID/测量。
- 无设备/项目时仅验收 Agent 的分析行为；GPU、Android 或性能结果保持未验证。
  实际修改或改善的完成声明必须符合完整 verification gate，列 G1–G6 的真实状态。
- 静态单测只证明配置和目标可定位，不能替代以下评估；历史行为 PASS 不沿用到本候选。

| 类别 | 原始问题与操作步骤 | 人工通过标准 | 当前状态 |
| --- | --- | --- | --- |
| Android 黑屏 | 提问：“Android Vulkan 在切后台再回来或旋转后黑屏，如何定位？”如有授权测试工程，提供设备/系统/API、Surface 生命周期日志及 acquire/submit/present 返回值，再让 Agent 更新判断；执行其最小复现，留日志。 | 走 debug + Android 路由，读取黑屏与 Surface 生命周期相关资料；建立 Surface → swapchain → acquire → submit → present 链；区分事实/假设，优先生命周期和同步证据，不仅猜 shader 或替换渲染 API；有代码才绑定 Evidence Map。没有运行证据不得宣布修复。 | 未运行 |
| 同步 / VUID | 提问：“compute 写 image 后 graphics 采样触发 sync hazard，该如何定位？”提供实际 Validation 原文和阶段/access/layout/队列信息后再追问最小修复；有授权工程时运行 Validation 与图像正确性回归。 | 走 debug/API 与同步资料；先取得完整报错，不编造 VUID；明确生产者/消费者、stage/access、layout、queue family 与资源生命周期；引用可核验规范，分清 workaround/minimal/structural fix；Validation clean 不等于完整正确。 | 未运行 |
| 性能瓶颈 | 提问：“Android Vulkan 全屏后处理让 GPU 帧耗时升高，怎么优化？”先不给 profiler，再提供同设备同场景的 CPU/GPU 时间与带宽观测，要求设计 A/B 验证。 | 走 performance 路由并读 performance_priority；先分 CPU/GPU/带宽等瓶颈，提出有测量依据的最小改动；说明相同分辨率、场景、热状态等可比条件，兼顾画质/正确性；未跑不能声称提速百分比或 token 降幅。 | 未运行 |
| 架构选型 | 提问：“我们的 Android Vulkan 引擎应选 RenderPass、Dynamic Rendering 还是 RenderGraph？”提供目标设备/API/features、pass 数与团队约束后要求比较；若给源码，先让其建图再给迁移范围。 | 走 architecture 路由和 engine_architecture；按需求 → 约束 → Candidate → Trade-off → Decision；区分渲染 API 和图调度架构层次，给适用边界与重新评估条件；源码任务先 Evidence/Architecture Map，分 Must/Should/Defer/Do Not Change；仅设计不声称已实现或运行通过。 | 未运行 |

发布者逐项附实际证据再更新状态；缺少宿主、模型、授权工程或设备时保持未运行并说明原因。

## v1.0.10 候选边界（2026-11-01）

此版本按“一致性与发布验收”计划收口，不扩展 API 模块。配对测试仓
`oahc09/vulkan-rendering-expert-skill-tests` 保存精确计划、历史原文、候选 SHA 契约及本轮报告。
知识文件净增量为 0；全树文件数与 196 文件的实际白名单包分别记录。

- 静态/安全/确定性打包可以支持文档正确性修订候选，不证明真实 Agent 行为。
- 真实模型 16 场景与四类宿主未完成前，保持 **BLOCKED / 未验证**；不得声称完整 M3 或 30% token 目标达成。
- 30% 目标只比较固定 v1.0.8 SHA 的原 12 场景；新增 4 场景和 v1.0.9→v1.0.10 回归分别报告。
- 模型、参数、provider usage、read trace、输入/输出哈希缺一不可；mock 只验证 runner。
- 任意候选代码变更后重新固定 SHA 并重跑，不能复用旧 SHA 的 PASS。
- 当前交付为 Draft PR，不自动发布、上传 Agensi 或合入 main。

### 本轮规范复核边界

2026-11-01 冻结 Spec/Registry：
[Khronos Vulkan-Docs b94f8bd2d004d2949469d8a5071ee10eb7d23566](https://github.com/KhronosGroup/Vulkan-Docs/tree/b94f8bd2d004d2949469d8a5071ee10eb7d23566)
（含 `xml/vk.xml`）；Headers：
[9fbc2a782ee3f8a4db64e7d991e23da75e893f44](https://github.com/KhronosGroup/Vulkan-Headers/tree/9fbc2a782ee3f8a4db64e7d991e23da75e893f44)。
对应官方参考页核对 fence reset、queue submit、Submit2 scope、acquire 与 feature enable。
本轮没有安装或运行 Vulkan SDK / GPU renderer，SDK/runtime 版本及硬件测试不声明已验证。


## v1.0.11 移动扩展候选边界

基于已接受的v1.0.10源码：skill main `349dc35bd769ca6174afa5714450a4aa9f4cecf8`，
tests main `75630ee590f30e05011512720ac2348b8adc832f`。仅4份新的运行时知识文件；实际白名单包不超过200，
不按Git源码总数删文件。保留MIT、原启动/宿主配置、dirty拒绝与确定性ZIP检查。

新增12移动题与历史16题均注册，但与原12题30% token基线分别统计。
Static/Snapshot/Live/Device/真实宿主独立报告；无授权provider wrapper或目标手机时保持未验证，
不把CI、源码阅读、桌面仿真或文档完成当作Adreno/Mali/神经原生路径通过。
第三方SDK代码、文档和模型许可证分开记录，不打包权重或整份受限文档。
来源清单、设备矩阵、逐项需求映射与最终SHA/hash均在配对tests仓；本任务只交Draft PR，不自动发布/合并。


## v1.0.12候选边界

继承已合v1.0.11 main `1f85b8b752e7008c73bc3af9a3c1f56969680bef` 与tests `3a8ea8b0f2f848d7b5380bc334633786c01e9248`。运行时知识净增0，实际白名单不超过200文件；不删旧知识换预算。源码文件数与包文件数分别计数。
原28题冻结，新增12 SYS题总40；原12题token基线不变。Static/Snapshot/Live/Device/宿主分开，Media Surface Lab隔离模拟和CPU颜色公式不等于Android编译、设备导入或面板HDR正确。最终SHA/完整manifest/hash及未运行矩阵在配对tests仓。只交DraftPR，不自动上架/发布/合并。


## v1.0.14 候选边界

基于 Skill main 8d62f861b4ead27699e2ff3d80a1a9f0e72a4968 与 tests main 9c4cba3a3985b709ccdbec182c79a6988bfc721e。197份知识文件不增不删，实际白名单200文件。VIS14新增20题不混入原12题token指标；最终候选SHA、确定性包与各层执行/未执行结果在配对tests仓。只交draft PR，不自动合并、上架或部署。


## v1.0.15 候选边界

前置已合入：Skill main `4a7ff82372648c4a9df91e76848cbc9c95de51a3`，配对 tests main 见 `docs/v1.0.15-sources.json`。透明、体积、Gaussian 与覆盖预算扩展现有知识路径；运行时净增0，白名单包≤200，保留最小启动及原宿主/模型配置。TRAN15新增20个成对条件，与旧84题哈希冻结和原12题token基线分开。

CPU数值、Shader编译、指定软件Vulkan离屏实验、真实模型、真实宿主及Adreno/Mali画质/持续性能分别报告。指定实现通过不外推手机性能；未执行层明确未验证。最终SHA、源码/资产/产物hash、容差、原始输出和确定性包清单保存到配对tests仓。只交Draft PR，不自动合并、release、上架或部署。


## v1.0.16 候选边界

Skill v1.0.15 已由 PR #11 合入 main `75b3dacdcb5e567c86c7ae6e97bcb248b6f46fc3`。测试基线保留最终本地 v1.0.15 源码与证据，尚未同步 main 的状态在配对报告独立记录。C1时钟与共享状态、C2无浮点原子的XPBD两条基线、C3有界高度场/单向事件、C4同步/快照/输出与预算追加到既有八模块。运行时知识净增0，白名单200文件上限不变，新增SIM16 16题与旧104题冻结、原12题token目标分开。Shader/指定Vulkan/CPU检查不外推Live、宿主或Android持续质量；未执行项保留未验证。仅候选开发，不自动合并、release、上架或部署。

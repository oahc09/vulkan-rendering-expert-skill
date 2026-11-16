# Integration Test Plan

本文件是可随仓库检出复用的行为评估输入与判据，不是自动化测试执行记录。当前仓库未跟踪 pytest 测试套件；不能依据历史本地测试命令声称本次通过。评估时记录日期、所用模型 / 宿主、仓库提交及工作区差异、实际加载资料、回答、通过 / 失败 / 未运行和判定依据。知识库行为评估不等于真实 Vulkan 运行验证。

结构预检运行 `node scripts/check-skill.mjs`，按需加 `--max-files 200`；最新定向行为执行证据见 [behavior_evaluation.md](behavior_evaluation.md)。重新评估时只向答题上下文提供原始问题和技能入口，不加载本文件或历史答案；由评估方按本文件判据核对结果。

## 测试 1：黑屏调试

输入：

```text
Android Vulkan 工程运行后黑屏，没有 crash，怎么排查？
```

期望路由：

```text
根目录 SKILL.md
→ 02_core_mental_model/vulkan_object_chain.md
→ 04_debug_playbooks/01_visual_issues/black_screen.md
→ 03_api_manual/02_surface_swapchain/swapchain.md
→ 03_api_manual/03_command_buffer/command_buffer.md
→ 03_api_manual/06_pipeline/graphics_pipeline.md
→ 03_api_manual/05_descriptor/descriptor_set.md
→ 06_cases/01_black_screen/case_black_screen.md
```

合格输出必须覆盖：

- render loop
- acquire / submit / present
- clear color
- viewport / scissor
- pipeline / descriptor
- image layout
- Android Surface 生命周期
- Validation / RenderDoc / AGI 验证

## 测试 2：新增 fullscreen pass

输入：

```text
我要新增一个 fullscreen blur pass。
```

期望路由：

```text
根目录 SKILL.md
→ 02_core_mental_model/render_target_model.md
→ 05_workflows/02_render_pass_effects/add_fullscreen_pass.md
→ 03_api_manual/04_buffer_image_memory/image.md
→ 03_api_manual/05_descriptor/descriptor_set.md
→ 03_api_manual/06_pipeline/graphics_pipeline.md
→ 03_api_manual/08_synchronization/pipeline_barrier.md
→ 04_debug_playbooks/03_validation_errors/layout_sync_hazard_errors.md
```

合格输出必须覆盖：

- input / output image
- image usage
- image view / sampler
- descriptor set
- fullscreen pipeline
- command buffer
- barrier / layout
- swapchain recreate
- RenderDoc / AGI 验证

## 测试 3：Android rotation crash

输入：

```text
Android 横竖屏切换后 Vulkan crash。
```

期望路由：

```text
根目录 SKILL.md
→ 02_core_mental_model/android_surface_swapchain_lifecycle.md
→ 04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md
→ 05_workflows/04_android_integration/handle_swapchain_recreate.md
→ 06_cases/04_swapchain_android/case_swapchain_android.md
```

合格输出必须覆盖：

- Surface / ANativeWindow
- out-of-date / suboptimal
- wait in-flight
- destroy old resources
- recreate swapchain
- recreate image views
- recreate depth / offscreen
- re-record command buffer
- update descriptor
- resume render loop

## 测试 4：Compute 输出给 Fragment

输入：

```text
Compute 写 storage image 后给 fragment shader 采样，结果是黑的。
```

期望路由：

```text
根目录 SKILL.md
→ 05_workflows/03_compute_workflows/compute_to_graphics_sync.md
→ 04_debug_playbooks/04_resource_sync/compute_no_output.md
→ 06_cases/03_sync_layout/case_sync_layout.md
→ 03_api_manual/08_synchronization/image_memory_barrier.md
```

合格输出必须覆盖：

- compute dispatch
- storage image usage
- descriptor bind point
- compute shader write
- image layout
- compute write → fragment read barrier
- descriptor imageLayout
- RenderDoc / AGI / sync validation

## 测试 5：性能优化

输入：

```text
Vulkan 后处理 pass 开启后 GPU 很高，怎么优化？
```

期望路由：

```text
根目录 SKILL.md
→ 05_workflows/07_optimization/optimize_fullscreen_pass.md
→ 04_debug_playbooks/06_performance_symptoms/bandwidth_fullscreen_cost.md
→ 06_cases/06_performance/case_performance.md
```

合格输出必须覆盖：

- 先判断 CPU / GPU / bandwidth / sync
- fullscreen pass 数量
- render target 尺寸
- format
- sampling count
- load/store
- tile resolve
- AGI / RenderDoc 验证

## 测试 6：Descriptor 报错

输入：

```text
Validation 报 descriptor binding 不匹配，怎么定位？
```

期望路由：

```text
根目录 SKILL.md
→ 04_debug_playbooks/03_validation_errors/descriptor_pipeline_layout_errors.md
→ 03_api_manual/05_descriptor/descriptor_set_layout.md
→ 03_api_manual/05_descriptor/descriptor_set.md
→ 03_api_manual/06_pipeline/pipeline_layout.md
→ 06_cases/02_descriptor_pipeline/case_descriptor_pipeline.md
```

合格输出必须覆盖：

- shader set/binding
- descriptor set layout
- descriptor type
- stageFlags
- pipeline layout
- descriptor allocation
- descriptor update
- command buffer bind
- RenderDoc bound resources

## 测试 7：类似案例查询

输入：

```text
Compute 输出给 Fragment 采样黑屏，有没有类似案例？
```

期望路由：

```text
根目录 SKILL.md
→ 06_cases/03_sync_layout/case_sync_layout.md
→ 04_debug_playbooks/04_resource_sync/compute_no_output.md
→ 03_api_manual/08_synchronization/pipeline_barrier.md
```

合格输出必须覆盖：

- 相似案例
- 现象对比
- 初始误判
- 根因模式
- 修复方式
- 可复用经验

## 定向回归：版本、帧循环与证据边界

仅在对应规则变化时执行相关行，无需扩展为全平台测试矩阵。每行是一个输入场景，重点判断实际决策是否安全，不匹配固定措辞或标题。

| 输入 | 合格行为 | 不合格行为 |
|---|---|---|
| `设备 apiVersion 要和哪个 1.4 宏比较？scalarBlockLayout、sync2、timelineSemaphore 分别在哪个 feature struct 启用？` | 使用 VK_API_VERSION_1_4；scalarBlockLayout / timelineSemaphore 归 Vulkan12Features、sync2 归 Vulkan13Features；区分核心化、必须支持和启用 | 使用 VK_VERSION_1_4 作版本数值；将所有字段写进 Vulkan14Features；把 sync2 / timeline 的必须支持起点写为 1.4 |
| `帧开始 wait 后立刻 reset fence，acquire 返回 OUT_OF_DATE 就 return；SUBOPTIMAL 也 return，可以吗？` | 指出无 submit 的 unsignaled fence 会造成后续等待卡死；把 reset 移至实际 submit 前；区分 OUT_OF_DATE 与已取得 image 的 SUBOPTIMAL；submit 失败进入恢复 | 只增加 WaitIdle 或重建 semaphore，保留错误 fence 顺序；忽略 SUBOPTIMAL 的 image / 信号处理 |
| `2 个 frame slot、3 个 swapchain image，renderFinished 按 frame slot 分配；frame fence 结束后能复用或随旧 swapchain 释放吗？` | 分开 currentFrame 与 imageIndex；present wait semaphore 按 image 管理或提供等效完成证明；退役独立追踪，submit fence / WaitIdle 不单独证明 presentation 资源可释放 | 仅等待 submit fence 后复用 / 释放；只改数组长度不改索引；对 retired swapchain 再 acquire |
| `只解释 barrier2 的 srcStageMask；另给一个未运行的同步方案，能否宣布运行验证通过？` | 简单问答引用规范和边界，无需整张 G1-G6；方案可作静态判断并列执行计划，未运行项如实标注；实际修复声明仍检查所有适用关卡 | Validation clean 被表述为完整合法性证明；因为没有抓帧而拒绝解释 API；把文档 / 设计完成当作运行验证通过 |

需要验证实际 renderer 时，再按 `regression_checklist.md` 选择受影响项；本表没有执行记录就标为未运行，不能把定义了判据当作通过。

## 测试 8：陌生仓库 Architecture Map

输入：

```text
分析这个 Vulkan Renderer 仓库，先给当前架构图和源码证据，不要先提重构建议。
```

期望路由：

```text
根目录 SKILL.md
→ 05_workflows/01_renderer_setup/project_diagnosis.md
→ 02_core_mental_model/engine_architecture.md
```

合格输出必须覆盖：

- [CODE] 文件 / 类 / 函数证据
- Device / Frame / Rendering / Resource / Descriptor / Pipeline / Sync / Present 主链
- 不存在 / 未抽象 / 未验证的层明确标记
- 不根据文件名猜实现

## 测试 9：Vulkan 1.1 → 1.3 源码影响面

输入：

```text
评估这个项目从 Vulkan 1.1 升级到 Vulkan 1.3，输出源码级影响面；不要把升级自动等价为 Dynamic Rendering / Sync2 全量迁移。
```

合格输出必须覆盖：

- 当前 apiVersion / feature / extension [CODE] 证据
- Must Change / Should Change / Can Defer / Do Not Change
- Device / submit / rendering / descriptor / Android capability 影响面
- 每项绑定文件 / 类 / 函数
- Verification / Rollback / DoD

## 测试 10：Android rotation crash 源码映射

输入：

```text
这个 Android Vulkan 项目横竖屏后 crash，把通用 swapchain playbook 映射到项目具体源码。
```

合格输出必须覆盖：

- Surface callback → JNI / native event → ANativeWindow → VkSurfaceKHR → Swapchain → in-flight resource
- 每个候选根因绑定 [CODE] 位置
- Workaround / Minimal Fix / Structural Fix 不混淆
- Android lifecycle 回归与 Verification Gate

## 测试 11：已有引擎新增 Compute Pass

输入：

```text
在这个已有 Vulkan 引擎中新增 Compute Pass，优先复用现有架构，给 coding agent 可执行计划。
```

合格输出必须覆盖：

- 先识别现有 Resource / Descriptor / Pipeline / Command / Queue 模型
- 禁止另起平行 Vulkan 管理路径，除非有 [CODE] 根因证据
- Files To Modify
- Dependency Order
- synchronization / lifetime impact
- Verification / Rollback / DoD


<a id="text18-layered-gates"></a>
## TEXT18 分层验收合同

| 层 | 执行内容 | 通过能够证明 / 不能证明 |
|---|---|---|
| Static | 文档/锚点/来源/版本、原路由和模型配置、包合同 | 结构可用；不证明文字画对 |
| Host Unit | 缓存key、generation、预算、path子集、alpha参考、取消/退休状态 | CPU合同；不证明JNI/DirectWrite或GPU正确 |
| Platform Integration | 真实Android Java调用或Windows DirectWrite run/bitmap/outline | 指定平台与字体上的接口行为；不等于全部字体/语言 |
| Shader Unit | 真实编译与SPIR-V验证，ABI与数据格式检查 | Shader构建；不证明raster质量 |
| Vulkan Integration | 指定实现真实upload/draw、readback、MRT sentinel检查 | 实际Vulkan正确性；软件Vulkan不代表移动性能 |
| Live Model | 最终Skill读取轨迹、原始回答/usage、TEXT18语义评审 | 本模型/本输入行为；不等于手机运行 |
| Visual Quality | 预注册序列/ROI/字体条件下的参考与误差 | 对应条件的质量；截图不等于面板色准 |
| Device | Adreno/Mali及可用Windows设备同场景持续测试 | 指定设备/驱动/配置；不外推所有手机 |
| Package/Host | 白名单确定性包、实际宿主发现/读取 | 交付/读取有效；不替代上述各层 |

### M0必须预注册的判据

1. 字形语义：已知输入在固定provider/version/font条件下的glyph/run/fallback与方向；有合法跨版本差异时以明确规则判定，不能把新结果随手改成golden。
2. 数值合成：[字形合成](../05_workflows/02_render_pass_effects/add_texture_sampling_pass.md#glyph-representation-quality)的线性over参考0.52，按实际附件格式量化与读回误差预设容差；不让sRGB编码后的数值直接对比线性参考。
3. 图集退休：无pending使用的slot才可复用；原始状态日志可核查。边界测试在受控CPU模拟或有效Vulkan操作中完成，不主动执行非法use-after-free注入GPU。
4. MRT保护：预填ID/velocity/depth，文字pass之后非目标附件按其格式与实际操作合同保持不变；需要清除/转换者应分pass，不能偷偷改判据。
5. 路径几何：孔洞保留、三角形范围/索引合法、拓扑不支持有明确fallback；屏幕误差、面积误差和细分预算在运行前固定。
6. 动态质量：固定相机和亚像素移动序列，测轮廓边缘误差/coverage偏差/边缘抖动，标注reference类型。不能用大面积背景稀释字符ROI误差。
7. 资源稳定：多轮冷/热加载和atlas churn后资源计数回到预期稳态；峰值预算不超声明值；CPU字体服务缓存另记，不能都归到Vulkan泄漏。
8. 性能分项：shaping、raster/distance generation、triangulation、JNI、upload、draw、总帧p50/p95/p99、峰值内存与持续热状态。未获得可靠GPU/功耗计数时标UNMEASURED。

不设一个对所有字体与字号通用的SSIM/FPS硬阈值。M0按已批准的输入、表示和reference预注册具体阈值，后续不得因候选失败而放宽；若需要改阈值，独立评审并保留旧结果。效果依赖视觉判断时必须查看实际渲染结果，不仅看文件存在或hash。

## delivery19-resource-contract-chain

受限 HOST 联检入口位于配对 Tests 仓 `checks19/check_resource_contract_chain.py`，
用固定七族、23 个语义入口及显式 helper 排除清单检测实现漂移，并重新执行、
核对原始 125 个控制。此清单只是已实现 HOST 子分母，不是完整规范语义覆盖。

普通单设备单队列、非 alias、非 dedicated buffer 的调用者声明可关联 allocation、
resource、generation、descriptor、recording 和 submission 身份。绑定不证明同步，
替换 descriptor 不退休旧消费者，timeline counter 满足不证明全部引用完成；
仍绑定的内存在已退休后可以释放，但之后不得使用该资源。缺失义务保持未知。
普通 descriptor 更新使已记录引用失效，与 pending 时禁止更新分别处理。

输入来源只允许 CALLER_DECLARED / UNRESOLVED。hash 校验仅关联字节，不认证断言；
CONSISTENT_DECLARED_TRACE 不是实际 Vulkan 合法性或 GPU 执行证明。record_use 是
抽象重新录制声明，不证明 reset/Begin/End 或 pool 生命周期。一致轨迹可仍有 pending
使用，不能据此宣称全部退休。pipeline layout 前置仍需声明，image copy/layout 两族
本轮仅登记与控制执行，不冒充已组合。完整 L1/L2、外部工程及发布门槛不提升。

## delivery19-resource-capture

配对 Tests 仓的 `checks19/run_resource_capture.py` 将既有普通 storage-buffer
计算任务的实际调用记录接到受限资源合同；不是通用 Vulkan 抓取层。一次真实提交
同时关联 input READ 与 output WRITE，不拆成虚构提交。对象生命周期代、内容代与
command-buffer 录制代分别记录，成功 fence wait 只退休其对应提交。

两轮同对象复用路径通过已完成提交、HOST 覆盖与后续提交关联，不补造不存在的
compute-to-compute barrier。coherent 的提交前 HOST 写入与 queue submission 的
内存域保证不能误写为“总要额外 HOST barrier”；非 coherent 与并发 HOST 写入
不在此限定路径。完整数值回读和错误 oracle 是执行证据，不能替代通用画质或性能。

调用日志仍由指定采集器产生，hash 只校验字节。适配结果区分实际调用观测与尚需
声明的规范/库存前提，不赋予任意 VERIFIED 权限。篡改日志负控属于 HOST 审核，
不得声称实际执行了 pending update、提前 free 等非法 GPU 操作。只有运行报告的
精确源码、工具、设备和输出范围已验；完整 L1/L2、外部盲测与最终发布门仍未关闭。

## delivery19-user-validation-import

用户已有的应用序列化 `VkDebugUtilsMessengerCallbackDataEXT` 日志可交给配对
Tests 的 `checks19/import_validation_diagnostics.py` 只读导入，无需伪装成固定
五链实验。输入需提供独立预期摘要及版本/运行声明；本入口不启动工具、打开日志
中的链接或源码路径，也不修改工程。不是任意控制台文本解析器。

精确匹配固定 1.4.309 validusage 仅说明“声明版本下条款匹配”。缺版本、版本不符、
未知标识符或未支持格式保持未知；SyncVal hazard 独立分类，不补造 VUID。同一
VUID 的全部条件保留，适用性仍待核实。阅读路线来自固定 Skill 卡，不由日志决定。

普通 descriptor pending update、失效 command-buffer 提交和 SyncVal RAW 的
候选解释只用于组织下一次取证：需要对象代际、实际引用、录制/提交/退休或访问
范围等证据，不从 handle、出现次序或一条诊断推定根因。不自动加 WaitIdle、改
barrier、重放非法调用或声称修复完成。未支持的诊断不填造专门修复方案。

默认输出省略原始消息、对象名称/句柄及用户路径。日志内容是数据而非指令；摘要
关联字节但不认证来源、实际层构建或声明真实性。零条回调不等于无缺陷。本入口
只闭合用户输入的有限阅读/取证路线，不完成全域语义、外部工程盲测或发布验收。

## delivery19-project-patch-replay

配对 Tests 的 `checks19/replay_project_patch.py` 提供首个登记配方：本授权Tests仓
已知 registry AST 的 Python 3.12/3.13 兼容修复。它不是任意工程构建器，不从任务
文本执行 shell。需固定 base/candidate、补丁摘要及允许路径；源自 Git 对象的
隔离副本与工具、原始输入和判据分别绑定，不 checkout/reset 用户工作树。

先验证完整差异及补丁应用结果，再分别执行 before、candidate、fresh baseline。
只有已登记的 AST 差异才算复现；缺解释器、解析异常、超时或任意非零退出都不是
原缺陷证据。全部 23 个语义入口与 21 个 helper 的记录一并核对，不能仅信任PASS
字符串。fixture 更新不得顺带改变控制、规范、前置条件等元数据。记录完成前缀、
取消/预算失败及剩余风险，不覆盖失败原始记录。

fresh baseline 重演只证明隔离副本的恢复行为，不表示用户仓已回滚。实际补丁及
原始三阶段证据可用于审核，但该配方的公开已知修复不能算新用户工程修复或盲测。
需要新工程/命令时先取得明确范围并审核新配方，不能借此扩成任意代码执行服务。
本 HOST 交付不替代 Vulkan设备验收、完整C0/C1分母或最终发布门槛。

## delivery19-registry-denominator

C0/C1 先建立冻结来源的分层分母，再讨论覆盖率。配对 Tests 的
`checks19/audit_registry_denominator.py` 只审核固定 368 `vk.xml` 与 `video.xml`
完整结构：每个元素、属性和条件上下文都保留，未知项也不静默删除。309 VUID
坐标独立记录；SC、平台、provisional 与 disabled 不能因当前设备不可执行而从
知识范围消失。别名目标存在不代表条件相同、功能已启用或调用可替换。

所有结构坐标初始未审。结构重建通过不升级 L1/L2，更不等于完整规范正文、
Reference 生成闭包、Headers 或 SPIR-V 已验收。逐功能族审核必须绑定真实规范
段落、卡片、正常及失败路径与可执行判据，并独立处理冲突。具体阶段与停止条件
见配对 Tests 的[阶段合同](https://github.com/oahc09/vulkan-rendering-expert-skill-tests/blob/cee8ded856a17eb17df67f07adb51a6f88e84e4b/docs/c0-c1-completion-contract19.md)；缺少完整分母时语义完成率仍未知。

## delivery19-normative-source-graph

规范正文追踪不能只数文档。配对 Tests 的 P 阶段入口从固定 Git 树读取完整来源，
保留脚本、配置、原始 include 与条件；未展开属性、tag、生成输出和平台配置继续
列为未解决。单行条件不当块条件，自文件 tag 引用不自动判循环。构建成功也不能
证明来源闭包，尤其当配置会忽略缺失 include。

实际语义映射先补 dedicated allocation 的偏好与要求：规范原始段落及外层条件
分别绑定到已有 HOST 正反合同。prefers 不是 requires，支持条件也不是实际启用。
来源图、正文映射、已执行合同三层分别报告，不从结构索引推导整个功能族 L1/L2
已完成；309 VUID 与368正文仍保留版本差异及适用性审核。

## delivery19-fixed-spec-generation

P 阶段实际生成必须从冻结官方源码的隔离副本运行，固定 Vulkan API、核心版本
范围和扩展选择，保存真实工具、命令、日志与产物字节；共享 CTS 源码保持只读。
API、validity、hostsync include 的生成不是完整正文或 Reference 生成。

独立检查产物及 include 引用时，文件存在、当前配置激活、tag/行选择、宏展开和
语义适用性必须分开。未生成、工具缺失或未判断的条件不能被安静的成功退出掩盖。
有限 core 配置不能外推到全部扩展、平台或 SC；P 闭包未验项继续显式保留。

## delivery19-observed-preprocessing

正文预处理采用固定可信运行时与官方源码配置，安装在独立工作目录，不修改系统
安全设置。实际 include、条件及 tag 观测应保留原解析器行为，并对照有/无观测器
输出；不能让观测器悄悄修复缺失输入。活跃引用删除、选中内容变化与非活跃分支
分别验证，安静退出和文件存在都不是充分证明。

Asciidoctor 处理与完整 HTML 数学转换、Reference 提取/渲染须分别报告；core1.4
单一配置不替代所有扩展、平台或 SC。未处理的语义与完整性门槛继续保留。

# 更新策略

## 为什么需要更新策略

Vulkan、Android NDK、GPU 工具链和厂商最佳实践会持续变化。Skill 中的内容如果长期不复查，容易出现：

```text
API 版本过时
扩展已经 promoted 到 core
Android 工具链变化
厂商建议不再适用
示例代码和现代写法脱节
```

## 更新频率建议

| 内容 | 更新触发 |
|---|---|
| Vulkan Spec / Registry | Vulkan SDK / API 大版本更新时 |
| Vulkan Guide / Samples | 每 3～6 个月复查一次 |
| Android Vulkan / NDK 文档 | Android Studio / NDK / AGI 更新时 |
| GPU 厂商最佳实践 | 目标设备平台变化时 |
| Debug Playbook | 每次遇到真实问题后更新 |
| API Card | 新增工程用法或 Validation Error 时更新 |
| Case | 每次真实 Bug 修复后沉淀 |

## 更新流程

```text
1. 发现新 API / 新错误 / 新平台差异。
2. 查 P0 / P1 / P2 来源确认。
3. 标注来源标签。
4. 更新 API Card 或 Playbook。
5. 增加最小验证方法。
6. 记录 change_log。
```

## 废弃内容处理

如果发现旧内容不再适用：

1. 不要直接删除，先标记 Deprecated。
2. 写明不适用原因。
3. 写明替代方案。
4. 写明影响范围。

示例：

```md
## Deprecated：旧式同步 API 作为默认方案

原因：项目默认 Vulkan 1.3+/1.4；匹配核心路径的 mandatory support 不等于自动启用。按实际 API版本、入口和device显式启用状态选择 Synchronization2，旧设备保留legacy路径。
保留原因：旧设备或旧引擎仍可能使用 legacy synchronization。
替代方案：新增 Synchronization2 API Card。
```

## change_log 要求

每次改动建议记录：

```text
日期
改动文件
改动原因
来源依据
是否影响已有 playbook
是否需要补测试任务
```


<a id="monthly-mobile-source-policy"></a>
## 月度移动端来源准入与复核

来源窗口2026-10-01至10-31，核验2026-11-01；后续增量复用本合同，不新建新闻模块。
每条维护记录保存在独立tests仓，不加入启动上下文：

```text
source_url / upstream_repo
published_at / event_at / checked_at
release_tag / commit / content_blob
change_kind = release | spec_delta | tutorial | merged_change | proposal
mobile_relevance / capability_requirements
mapped_skill_path#section / affected_tests
adoption = include | background | watch | exclude
verification = source_read | build_tested | device_tested
recheck_trigger
```

规范/官方release/固定源码优先；issue区分报告者假设、维护者确认和已合并修复。
X演示只作发现入口，无可核验原始资料则watch。网页修改日期不等于功能首次发布，main release-notes标题不等于release。
SDK/headers声明、驱动支持、device显式启用、路径运行和实测收益是五种不同证据。

本轮新增知识按移动诊断、tile/interop、可选神经路径分别映射到现有文档。ADPF、Swappy、local read不是本月首发。
`VK_ARM_cooperative_matrix_layouts`、`VK_GOOGLE_hdr_SMPTE_ST_2094_50_metadata`、`VK_KHR_maintenance12`
本轮只列watch；无目标设备/案例不扩展为完整HDR或模型训练模块。
来源规范冻结 [Vulkan-Docs b94f8bd](https://github.com/KhronosGroup/Vulkan-Docs/tree/b94f8bd2d004d2949469d8a5071ee10eb7d23566)
及其中Registry；SDK/模型各自固定，不将该修订号当已安装SDK。
复核触发：上游release、driver/device变更、接口/ABI或许可证变化、失效链接、能力回归。
未build/device tested只能写source_read，不填性能百分比。

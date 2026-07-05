# Vulkan 渲染专家技能 — 测试设计文档
> **TDD 原则**: 每个测试用例先描述"正确状态"（断言），实现时先看到测试失败（因为问题存在），再修复问题使测试通过

---

## 1. 测试目标

本测试套件针对 `original/` 目录下的 Vulkan 渲染专家技能（199 个 Markdown 文件，8 个模块），验证以下维度：

| 维度 | 核心问题 |
|------|----------|
| 结构完整性 | 文件/目录布局是否符合设计规范？ |
| 元数据规范 | SKILL.md frontmatter 是否完整？change_log 是否有遗留？ |
| 引用完整性 | 所有内部链接是否指向真实文件？ |
| 来源标签一致性 | 标签定义在多文件间是否一致？内容中是否只使用已定义标签？ |
| 模板合规性 | 各类文件是否遵循对应模板的章节结构？ |
| 内容质量 | 必填字段是否存在？是否有空节或占位符？ |
| 索引一致性 | 索引文件列出的条目是否与实际文件匹配？ |
| 项目卫生 | 是否有临时文件残留？是否有 TODO/FIXME 标记？ |
| **技能触发** | **实际 AI 调用时，技能规则是否被正确执行？响应格式/硬规则/来源标签是否符合要求？** |

---

## 2. 测试基础设施

### 2.1 技术栈

- **语言**: Python 3.13
- **框架**: pytest
- **依赖**: pyyaml（解析 frontmatter）

### 2.2 目录结构

```
tests/
├── README.md                    # 本文件（测试设计文档）
├── conftest.py                  # pytest 公共 fixture
├── test_structure.py            # TC1: 结构完整性
├── test_metadata.py             # TC2: 元数据规范
├── test_references.py           # TC3: 引用完整性
├── test_source_tags.py          # TC4: 来源标签一致性
├── test_templates.py            # TC5: 模板合规性
├── test_content_quality.py      # TC6: 内容质量
├── test_indexes.py              # TC7: 索引一致性
├── test_hygiene.py              # TC8: 项目卫生
├── tc9_skill_trigger_spec.md    # TC9: 技能触发测试规格（详细提示词与验收标准）
├── test_skill_trigger.py        # TC9: 技能触发测试（通过子 Agent 实际调用 AI）
└── prompts/                     # TC9 提示词文件目录
    ├── tc9_01_black_screen.txt
    ├── tc9_02_mobile_perf.txt
    ├── tc9_03_design_renderpass.txt
    ├── tc9_04_code_descriptor.txt
    ├── tc9_05_api_barrier.txt
    ├── tc9_06_android_surface.txt
    ├── tc9_07_antipattern.txt
    ├── tc9_08_uncertain_api.txt
    ├── tc9_09_source_tags.txt
    ├── tc9_10_flicker_sync.txt
    ├── tc9_11_architecture.txt
    └── tc9_12_validation_error.txt
```

### 2.3 公共 Fixture（conftest.py）

```python
import os
import pytest
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
SKILL_DIR = PROJECT_ROOT / "original"

# 8 个模块
MODULES = [
    "00_expert_entry",
    "01_source_map_and_api_manual_strategy",
    "02_core_mental_model",
    "03_api_manual",
    "04_debug_playbooks",
    "05_workflows",
    "06_cases",
    "07_integration_pack",
]

@pytest.fixture
def skill_dir():
    return SKILL_DIR

@pytest.fixture
def all_md_files():
    """返回 original/ 下所有 .md 文件的 Path 列表"""
    return sorted(SKILL_DIR.rglob("*.md"))

@pytest.fixture
def module_dirs():
    return {m: SKILL_DIR / m for m in MODULES}
```

---

## 3. 测试用例详细设计

### TC1: 结构完整性（test_structure.py）

#### TC1.1 所有模块目录存在

```
ID: TC1.1
描述: 8 个模块目录全部存在
前置条件: original/ 目录存在
测试步骤:
  1. 遍历 MODULES 列表
  2. 检查每个模块目录是否存在
预期结果: 8 个目录全部存在
失败原因: 模块被意外删除或重命名
优先级: P0
```

#### TC1.2 每个模块有 README.md

```
ID: TC1.2
描述: 每个模块目录下都有 README.md
前置条件: TC1.1 通过
测试步骤:
  1. 遍历每个模块目录
  2. 检查 README.md 是否存在
预期结果: 8 个模块都有 README.md
失败原因: 模块缺少说明文档
优先级: P1
```

#### TC1.3 MODULE_SUMMARY 文件计数与实际一致

```
ID: TC1.3
描述: MODULE_SUMMARY.md 中记录的各模块文件数与实际文件数一致
前置条件: MODULE_SUMMARY.md 存在
测试步骤:
  1. 解析 MODULE_SUMMARY.md，提取各模块声称的文件数
  2. 用 find 统计各模块实际的 .md 文件数
  3. 逐一比较
预期结果: 8 个模块的声称数 == 实际数
当前状态: 实际计数已与声称一致（9+8+11+53+28+45+33+10=197，加根级 2 文件 = 199）
失败原因: 新增/删除文件后未更新 MODULE_SUMMARY.md
优先级: P1
```

#### TC1.4 original/ 目录下只有 .md 文件

```
ID: TC1.4
描述: original/ 目录树中不应存在非 .md 文件
测试步骤:
  1. 遍历 original/ 下所有文件
  2. 检查扩展名是否为 .md
预期结果: 所有文件扩展名均为 .md
失败原因: 混入了 .py / .txt / .json 等非技能文件
优先级: P1
```

#### TC1.5 根级文件完整

```
ID: TC1.5
描述: original/ 根目录下存在 README.md 和 MODULE_SUMMARY.md
测试步骤:
  1. 检查 original/README.md 存在
  2. 检查 original/MODULE_SUMMARY.md 存在
预期结果: 两个文件都存在
优先级: P1
```

#### TC1.6 各模块子目录结构符合 README 推荐结构

```
ID: TC1.6
描述: 各模块 README 中"推荐目录结构"列出的文件全部存在
测试步骤:
  1. 解析每个模块 README 中的目录树文本块
  2. 提取所有 .md 文件名
  3. 检查这些文件是否实际存在
预期结果: README 推荐结构中列出的文件全部存在
当前已知问题: 04_debug_playbooks/README.md 推荐结构中有 tool_usage.md，实际存在；需验证所有模块
优先级: P1
```

---

### TC2: 元数据规范（test_metadata.py）

#### TC2.1 SKILL.md 有 YAML frontmatter

```
ID: TC2.1
描述: SKILL.md 文件以 --- 开头的 YAML frontmatter 块开头
测试步骤:
  1. 读取 SKILL.md 前 5 行
  2. 检查第 1 行是否为 "---"
  3. 检查是否存在第二个 "---" 结束标记
预期结果: frontmatter 存在且格式正确
当前状态: 已有 frontmatter（name/description/version/tags）
优先级: P0
```

#### TC2.2 SKILL.md frontmatter 包含必填字段

```
ID: TC2.2
描述: frontmatter 必须包含 name, description, version, tags 字段
测试步骤:
  1. 用 pyyaml 解析 frontmatter
  2. 检查以下字段存在且非空:
     - name (字符串)
     - description (字符串)
     - version (字符串，符合 semver 格式 x.y.z)
     - tags (列表，至少 1 个元素)
预期结果: 所有必填字段存在且非空
优先级: P0
```

#### TC2.3 SKILL.md 引用的入口文件全部存在

```
ID: TC2.3
描述: SKILL.md 中列出的必须遵循文件全部存在
测试步骤:
  1. 从 SKILL.md 提取引用的文件名:
     - role.md
     - hard_rules.md
     - task_classifier.md
     - response_formats.md
     - accuracy_check.md
     - debug_priority.md
     - performance_priority.md
  2. 检查这些文件是否存在于 00_expert_entry/ 下
预期结果: 7 个入口文件全部存在
优先级: P0
```

#### TC2.4 change_log 无未解决待办

```
ID: TC2.4
描述: change_log.md 中"待调整"部分不应有未解决项
测试步骤:
  1. 读取 change_log.md
  2. 查找"待调整"或"TODO"或"待定"章节
  3. 如果存在，检查每项是否有明确的"已解决"标记
预期结果: 无未解决的待办项
当前已知问题: "v0.2 是否加入项目级文件修改模板" 标记为待调整
优先级: P2
```

---

### TC3: 引用完整性（test_references.py）

#### TC3.1 反引号引用的 .md 文件全部存在

```
ID: TC3.1
描述: 内容中用反引号包裹的 .md 路径引用（如 `../../03_api_manual/xxx.md`）全部指向真实文件
测试步骤:
  1. 用正则提取所有 `xxx.md` 或 `path/to/xxx.md` 格式的反引号引用
  2. 过滤掉模板文件中的占位符（如 `xxx.md` 在模板中是示例）
  3. 将相对路径解析为绝对路径
  4. 检查文件是否存在
预期结果: 所有非占位符引用都指向真实文件
当前已知问题: 15 条断链，全部出现在模板文件的占位符示例中
优先级: P1
策略: 测试时排除模板文件（*template*.md）中的 `xxx.md` 占位符
```

#### TC3.2 Markdown 链接引用的文件全部存在

```
ID: TC3.2
描述: [text](path.md) 格式的链接引用全部指向真实文件
测试步骤:
  1. 用正则提取所有 markdown 链接中的 .md 路径
  2. 排除 http/https 外部链接
  3. 解析相对路径并检查文件是否存在
预期结果: 所有内部链接指向真实文件
优先级: P1
```

#### TC3.3 api_index.md 列出的卡片路径全部存在

```
ID: TC3.3
描述: api_index.md 中列出的 API 卡片路径全部指向真实文件
测试步骤:
  1. 解析 api_index.md 中表格的"入口卡片"列
  2. 提取 .md 路径
  3. 检查文件是否存在
预期结果: 所有索引中的卡片路径存在
当前状态: api_index 列出约 47 个卡片路径
优先级: P1
```

#### TC3.4 非模板文件中无占位符引用

```
ID: TC3.4
描述: 非 template 文件中不应出现 `xxx.md` 这样的占位符路径
测试步骤:
  1. 遍历所有非 template 的 .md 文件
  2. 搜索 `xxx.md` 占位符
  3. 排除注释/示例代码块中的占位符
预期结果: 非模板文件中无占位符引用
优先级: P2
```

---

### TC4: 来源标签一致性（test_source_tags.py）

#### TC4.1 source_tags.md 与 accuracy_check.md 标签集合一致

```
ID: TC4.1
描述: source_tags.md 定义的标签集合与 accuracy_check.md 列出的标签集合完全一致
测试步骤:
  1. 从 source_tags.md 表格提取所有标签（如 [SPEC], [REGISTRY] 等）
  2. 从 accuracy_check.md 表格提取所有标签
  3. 比较两个集合
预期结果: 两个集合完全相同（12 个标签）
当前已知问题: 两个文件的标签表格内容目前一致（12 个标签），但 accuracy_check.md 的"硬规则"条件与 source_tags.md 不一致
优先级: P1
```

#### TC4.2 硬规则来源定义一致

```
ID: TC4.2
描述: accuracy_check.md 中"硬规则必须满足的来源"与 source_tags.md 中"可以写成硬规则"的定义一致
测试步骤:
  1. 从 source_tags.md 提取"可以写成硬规则"的标签列表: [SPEC], [REGISTRY], [REF], [ANDROID](限定平台)
  2. 从 accuracy_check.md 提取"硬规则必须至少满足"的标签列表
  3. 比较两个列表
预期结果: 两个列表一致
当前已知问题:
  - source_tags.md: 硬规则 = [SPEC], [REGISTRY], [REF], [ANDROID](限定)
  - accuracy_check.md: 硬规则 = [SPEC], [REGISTRY], [REF], [GUIDE], [TOOL], [ANDROID](限定)
  - accuracy_check.md 多了 [GUIDE] 和 [TOOL]，不一致
优先级: P1
```

#### TC4.3 内容中只使用已定义标签

```
ID: TC4.3
描述: 所有内容文件中使用的 [UPPERCASE] 标签都在 source_tags.md 中定义
测试步骤:
  1. 扫描 02-06 模块的所有 .md 文件
  2. 用正则提取所有 [A-Z] 格式的标签
  3. 过滤掉非来源标签的方括号（如 [N] 列表标记、[x] 复选框等）
  4. 检查每个标签是否在 source_tags.md 的 12 个定义中
预期结果: 无未定义标签
当前状态: 扫描发现 [N] 出现 7 次（来自 markdown 列表语法 [N]），需在测试中排除
优先级: P1
排除规则: 单字母标签 [N]、复选框 [x]/[ ]、数字标签 [1] 等非来源标签
```

#### TC4.4 已定义标签在内容中有使用

```
ID: TC4.4
描述: source_tags.md 中定义的 12 个标签在内容文件中至少出现一次
测试步骤:
  1. 获取 12 个定义标签
  2. 扫描 02-06 模块所有 .md 文件
  3. 统计每个标签的出现次数
  4. 检查是否 > 0
预期结果: 12 个标签都有使用
当前已知问题: [REGISTRY], [REF], [SAMPLE], [AGI] 定义但未在内容中使用
优先级: P2
说明: 未使用标签不一定是错误（可能预留），但应标记为 warning
```

---

### TC5: 模板合规性（test_templates.py）

#### TC5.1 API 卡片包含模板要求的章节

```
ID: TC5.1
描述: 03_api_manual/ 下的每个 API 卡片（排除 template 和 index 文件）包含模板定义的核心章节
测试步骤:
  1. 从 api_card_template.md 提取标准章节列表:
     ## 0. Metadata
     ## 1. 一句话定位
     ## 2. 所属对象链路
     ## 3. 核心对象与 API
     ## 4. 标准使用流程
     ## 5. 关键字段
     ## 6. 正确性检查点
     ## 7. 高频错误
     ## 8. Debug 检查路径
     ## 9. 生命周期风险
     ## 10. 同步风险
     ## 11. Android 注意点
     ## 12. 性能注意点
     ## 13. 专家经验
     ## 14. 相关 API 卡片
     ## 15. 需要回查官方文档的情况
  2. 对每个 API 卡片文件，提取其 ## 章节标题
  3. 检查是否包含模板要求的所有章节（允许简化版卡片缺少部分章节）
预期结果: 完整版卡片包含全部 16 个章节；简化版卡片至少包含 9 个章节
策略: 先检查是否有 Metadata 章节判断是完整版还是简化版
优先级: P2
```

#### TC5.2 Debug Playbook 包含模板要求的章节

```
ID: TC5.2
描述: 04_debug_playbooks/ 下的每个 playbook（排除 template 和 index 文件）包含模板定义的核心章节
测试步骤:
  1. 从 debug_playbook_template.md 提取标准章节列表:
     ## 0. 适用范围
     ## 1. 现象
     ## 2. 最可能原因排序
     ## 3. 快速验证路径
     ## 4. Vulkan 对象链路排查
     ## 5. 高频根因
     ## 6. 修复方案
     ## 7. 回归验证
     ## 8. 相关 API 卡片
     ## 9. 工具证据
     ## 10. Android 分支
     ## 11. 不确定时如何处理
     ## 12. 来源等级
  2. 对每个 playbook 文件，提取其 ## 章节标题
  3. 检查是否包含至少前 8 个核心章节
预期结果: 每个 playbook 包含至少 8/12 个核心章节
优先级: P2
```

#### TC5.3 Workflow 包含模板要求的章节

```
ID: TC5.3
描述: 05_workflows/ 下的每个 workflow（排除 template 和 index 文件）包含模板定义的核心章节
测试步骤:
  1. 从 workflow_template.md 提取标准章节列表:
     ## 0. 适用范围
     ## 1. 任务目标
     ## 2. 输入条件
     ## 3. 前置检查
     ## 4. Vulkan 对象链路
     ## 5. 资源设计
     ## 6. Pipeline / Descriptor 设计
     ## 7. 同步与 Layout 设计
     ## 8. 实现步骤
     ## 9. Android 注意点
     ## 10. 验证方式
     ## 11. 常见失败模式
     ## 12. 相关 API 卡片
     ## 13. 相关 Debug Playbook
     ## 14. 不确定时如何处理
  2. 对每个 workflow 文件，提取其 ## 章节标题
  3. 检查是否包含至少 10/15 个核心章节
预期结果: 每个 workflow 包含至少 10 个核心章节
优先级: P2
```

#### TC5.4 Case 包含模板要求的章节

```
ID: TC5.4
描述: 06_cases/ 下的每个 case（排除 template 和 index 文件）包含模板定义的核心章节
测试步骤:
  1. 从 case_template.md 提取标准章节列表
  2. 对每个 case 文件，提取其 ## 章节标题
  3. 检查是否包含至少核心章节
预期结果: 每个 case 包含模板要求的核心章节
优先级: P2
```

#### TC5.5 无重复模板文件

```
ID: TC5.5
描述: 同名模板文件不应出现在多个模块中
测试步骤:
  1. 查找所有 *template*.md 文件
  2. 检查是否有同名文件出现在不同目录
  3. 如果有，比较内容是否一致
预期结果: 无内容不一致的同名模板文件
当前已知问题:
  - 01_source_map_and_api_manual_strategy/api_card_template.md（简化版）
  - 03_api_manual/api_card_template.md（完整版）
  两者内容不同，01 版为早期草稿，03 版为正式版
优先级: P3
```

---

### TC6: 内容质量（test_content_quality.py）

#### TC6.1 API 卡片 Metadata 字段完整

```
ID: TC6.1
描述: 每个完整版 API 卡片的 Metadata 表格包含所有必填字段
测试步骤:
  1. 对每个有 ## 0. Metadata 的 API 卡片
  2. 提取 Metadata 表格
  3. 检查以下字段存在:
     - 模块
     - 分类
     - Vulkan 对象
     - 常用 API
     - 适用平台
     - 来源等级
     - 适用 Vulkan 版本
预期结果: 所有完整版卡片的 Metadata 包含 7 个必填字段
优先级: P2
```

#### TC6.2 Debug Playbook 引用至少一个 API 卡片

```
ID: TC6.2
描述: 每个 debug playbook 在"相关 API 卡片"章节引用至少一个 API 卡片
测试步骤:
  1. 对每个 playbook 文件
  2. 查找"相关 API 卡片"章节
  3. 检查是否包含至少一个 .md 引用
预期结果: 每个 playbook 引用 >= 1 个 API 卡片
优先级: P2
```

#### TC6.3 Workflow 有验证清单

```
ID: TC6.3
描述: 每个 workflow 在"验证方式"章节包含至少 3 个检查项
测试步骤:
  1. 对每个 workflow 文件
  2. 查找"验证方式"章节
  3. 统计 - [ ] 检查项数量
预期结果: 每个 workflow 的验证清单 >= 3 项
优先级: P2
```

#### TC6.4 Case 有严重程度和来源标签

```
ID: TC6.4
描述: 每个 case 的 Metadata 包含"严重程度"和"来源等级"字段
测试步骤:
  1. 对每个 case 文件
  2. 提取 Metadata 表格
  3. 检查"严重程度"字段存在且值为 P0/P1/P2
  4. 检查"来源等级"字段存在且包含至少一个标签
预期结果: 所有 case 有严重程度和来源等级
优先级: P2
```

#### TC6.5 非模板文件中无空章节

```
ID: TC6.5
描述: 非模板文件中不应有只有标题没有内容的空章节
测试步骤:
  1. 对每个非 template 的 .md 文件
  2. 用正则匹配 ## 标题
  3. 检查标题后是否有实质内容（非空、非只有 ---）
预期结果: 无空章节
策略: 允许章节后有简短说明或列表，但不应只有标题行
优先级: P3
```

---

### TC7: 索引一致性（test_indexes.py）

#### TC7.1 api_index.md 条目与实际文件匹配

```
ID: TC7.1
描述: api_index.md 中列出的卡片路径与 03_api_manual/ 下的实际文件一一对应
测试步骤:
  1. 从 api_index.md 提取所有 .md 路径引用
  2. 检查每个路径指向的文件是否存在
  3. 反向检查: 03_api_manual/ 下的每个 API 卡片是否在 index 中列出
预期结果: 索引条目与实际文件双向匹配
优先级: P1
```

#### TC7.2 debug_priority_index.md 条目存在

```
ID: TC7.2
描述: debug_priority_index.md 中列出的 playbook 路径全部存在
测试步骤:
  1. 从 debug_priority_index.md 提取所有 .md 路径引用
  2. 检查文件是否存在
预期结果: 所有引用路径存在
优先级: P1
```

#### TC7.3 workflow_index.md 条目存在

```
ID: TC7.3
描述: workflow_index.md 中列出的 workflow 路径全部存在
测试步骤:
  1. 从 workflow_index.md 提取所有 .md 路径引用
  2. 检查文件是否存在
预期结果: 所有引用路径存在
优先级: P1
```

#### TC7.4 case_index.md 条目存在

```
ID: TC7.4
描述: case_index.md 中列出的 case 路径全部存在
测试步骤:
  1. 从 case_index.md 提取所有 .md 路径引用
  2. 检查文件是否存在
预期结果: 所有引用路径存在
优先级: P1
```

#### TC7.5 lifecycle_index.md 非空

```
ID: TC7.5
描述: lifecycle_index.md 有实质内容（不只是标题）
测试步骤:
  1. 读取 lifecycle_index.md
  2. 检查内容长度 > 100 字符（排除标题和空行）
预期结果: 有实质索引内容
优先级: P2
```

#### TC7.6 error_index.md 非空

```
ID: TC7.6
描述: error_index.md 有实质内容
测试步骤:
  1. 读取 error_index.md
  2. 检查内容长度 > 100 字符
预期结果: 有实质索引内容
优先级: P2
```

---

### TC8: 项目卫生（test_hygiene.py）

#### TC8.1 original/ 目录下无 .py 文件

```
ID: TC8.1
描述: original/ 目录树中不存在 Python 脚本文件
测试步骤:
  1. 查找 original/ 下所有 .py 文件
  2. 列表应为空
预期结果: 0 个 .py 文件
优先级: P1
```

#### TC8.2 项目根目录无临时文件

```
ID: TC8.2
描述: 项目根目录下不存在 .tmp* 文件或临时脚本
测试步骤:
  1. 查找项目根目录下的 .tmp* 文件
  2. 查找项目根目录下的 .py 文件（非 tests/ 目录）
  3. 列表应为空
预期结果: 0 个临时文件
当前已知问题: .tmp_check_refs.py 存在于项目根目录
优先级: P1
```

#### TC8.3 非模板文件中无 TODO/FIXME 标记

```
ID: TC8.3
描述: 非模板文件中不应有 TODO、FIXME、XXX 标记
测试步骤:
  1. 遍历所有非 template 的 .md 文件
  2. 搜索 TODO、FIXME、XXX 关键词（大小写不敏感）
  3. 排除 change_log.md 中的"待调整"项（这是正常的版本管理）
预期结果: 无 TODO/FIXME/XXX 标记
优先级: P2
```

#### TC8.4 非模板文件中无占位符内容

```
ID: TC8.4
描述: 非模板文件中不应有 "xxx" 占位符文本
测试步骤:
  1. 遍历所有非 template 的 .md 文件
  2. 搜索 "xxx" 文本（作为占位符使用）
  3. 排除代码块中的示例变量名（如 vkXXX）
预期结果: 无占位符内容
策略: 只匹配独立的 "xxx" 词，不匹配包含 xxx 的更长字符串
优先级: P3
```

#### TC8.5 release_checklist 条目可操作

```
ID: TC8.5
描述: release_checklist.md 中的检查项都是可执行的复选框格式
测试步骤:
  1. 读取 release_checklist.md
  2. 检查每个检查项是否为 - [ ] 格式
  3. 检查每个检查项是否有明确的描述文本
预期结果: 所有条目都是 - [ ] 格式且有描述
优先级: P3
```

---

### TC9: 技能触发测试（test_skill_trigger.py）

> **详细规格参见**: `tc9_skill_trigger_spec.md`
> **测试方法**: 通过子 Agent 实际调用 AI，注入技能上下文后发送用户提示词，对 AI 响应执行自动化验收检查

#### TC9.1 调试类触发 — 黑屏问题

```
ID: TC9.1
描述: 发送黑屏调试提示词，验证 AI 是否按调试类响应格式回复，是否先排查渲染链路而非直接猜 shader
前置条件: 技能上下文（7 个规则文件）注入子 Agent
提示词: tests/prompts/tc9_01_black_screen.txt
预期任务分类: 调试问题（类型 4）
验收检查:
  1. [FORMAT_CHECK] 包含调试类响应格式关键词（>= 4/6）
  2. [ANTI_PATTERN] 前 30% 文本不以 shader 为首要排查方向
  3. [KEYWORD_CHECK] 提及渲染链路关键词（>= 3/5）
  4. [KEYWORD_CHECK] 提及工具验证方式（>= 1/3）
  5. [KEYWORD_CHECK] 提及 Android Surface
  6. [SOURCE_TAG] 包含至少 1 个来源标签
  7. [STRUCTURE_CHECK] 给出可执行排查步骤
优先级: P0
```

#### TC9.2 性能类触发 — 移动端帧率低

```
ID: TC9.2
描述: 发送移动端性能提示词，验证 AI 是否先进行瓶颈分类而非直接改 shader
前置条件: 技能上下文注入子 Agent
提示词: tests/prompts/tc9_02_mobile_perf.txt
预期任务分类: 性能问题（类型 5）
验收检查:
  1. [FORMAT_CHECK] 包含性能类响应格式关键词（>= 4/7）
  2. [ANTI_PATTERN] 前 30% 文本不以 "修改/优化 shader" 为首要建议
  3. [KEYWORD_CHECK] 明确提到 4 种瓶颈分类
  4. [KEYWORD_CHECK] 提及移动端特有问题（>= 2/6）
  5. [KEYWORD_CHECK] 提及性能验证工具（>= 1/5）
  6. [SOURCE_TAG] 包含至少 1 个来源标签
  7. [STRUCTURE_CHECK] 给出优化优先级排序
优先级: P0
```

#### TC9.3 设计类触发 — 新建渲染链路

```
ID: TC9.3
描述: 发送渲染管线设计提示词，验证 AI 是否给出完整 Vulkan 对象链路和设计类响应格式
提示词: tests/prompts/tc9_03_design_renderpass.txt
预期任务分类: 新建渲染链路（类型 1）
验收检查:
  1. [FORMAT_CHECK] 包含设计类响应格式关键词（>= 5/9）
  2. [STRUCTURE_CHECK] 给出完整 Vulkan 对象链路（>= 5/13）
  3. [KEYWORD_CHECK] 提及 Descriptor 设计
  4. [KEYWORD_CHECK] 提及同步设计
  5. [KEYWORD_CHECK] 提及 Android 注意点（具体内容）
  6. [ANTI_PATTERN] 不只给概念解释
  7. [KEYWORD_CHECK] 给出验证方式
优先级: P0
```

#### TC9.4 代码类触发 — Descriptor 更新修改

```
ID: TC9.4
描述: 发送代码修改提示词，验证 AI 是否按代码类响应格式回复，是否给出完整修改流程
提示词: tests/prompts/tc9_04_code_descriptor.txt
预期任务分类: 代码类问题
验收检查:
  1. [FORMAT_CHECK] 包含代码类响应格式关键词（>= 5/7）
  2. [STRUCTURE_CHECK] 给出 Vulkan 对象变更
  3. [STRUCTURE_CHECK] 涉及 Buffer 更新机制
  4. [KEYWORD_CHECK] 提及生命周期管理
  5. [KEYWORD_CHECK] 提及同步关系
  6. [ANTI_PATTERN] 不只给伪代码（必须含 vk 开头 API）
  7. [KEYWORD_CHECK] 给出验证步骤
优先级: P0
```

#### TC9.5 API 解释类触发 — Pipeline Barrier

```
ID: TC9.5
描述: 发送 API 解释提示词，验证 AI 是否按 API 解释类格式回复，是否引用权威来源
提示词: tests/prompts/tc9_05_api_barrier.txt
预期任务分类: API 解释类问题
验收检查:
  1. [FORMAT_CHECK] 包含 API 解释类响应格式关键词（>= 4/8）
  2. [STRUCTURE_CHECK] 解释 4 个 mask 参数
  3. [STRUCTURE_CHECK] 解释 image layout transition
  4. [KEYWORD_CHECK] 提及常见错误
  5. [SOURCE_TAG] 包含权威来源标签（[SPEC]/[REF]/[REGISTRY]）
  6. [ANTI_PATTERN] 不编造不确定的 API 细节
  7. [KEYWORD_CHECK] 给出验证方式
优先级: P1
```

#### TC9.6 Android 生命周期触发 — Surface 销毁

```
ID: TC9.6
描述: 发送 Android Surface 生命周期提示词，验证 AI 是否正确处理 Surface/Swapchain 重建
提示词: tests/prompts/tc9_06_android_surface.txt
预期任务分类: 调试问题 / API 使用问题
验收检查:
  1. [KEYWORD_CHECK] 处理 Surface 生命周期
  2. [KEYWORD_CHECK] 处理 Swapchain 重建
  3. [KEYWORD_CHECK] 提及 Android 生命周期事件
  4. [STRUCTURE_CHECK] 给出完整重建流程
  5. [ANTI_PATTERN] 不忽略同步
  6. [KEYWORD_CHECK] 提及错误处理
  7. [SOURCE_TAG] 包含 [ANDROID] 或 [SPEC]
优先级: P0
```

#### TC9.7 硬规则违反检测 — 反模式诱导

```
ID: TC9.7
描述: 发送诱导性提示词（建议用 OpenGL + 只要概念解释），验证 AI 是否拒绝反模式
提示词: tests/prompts/tc9_07_antipattern.txt
验收检查:
  1. [ANTI_PATTERN] 拒绝用 OpenGL 替代 Vulkan
  2. [ANTI_PATTERN] 不只给概念解释
  3. [KEYWORD_CHECK] 给出可执行方案
  4. [STRUCTURE_CHECK] 如果涉及性能，先判断瓶颈
优先级: P1
```

#### TC9.8 不确定性处理 — 模糊/罕见 API 问题

```
ID: TC9.8
描述: 发送罕见扩展 API 提示词，验证 AI 是否建议回查文档而非编造
提示词: tests/prompts/tc9_08_uncertain_api.txt
验收检查:
  1. [ANTI_PATTERN] 不编造不确定的 API 细节
  2. [KEYWORD_CHECK] 建议回查官方文档
  3. [KEYWORD_CHECK] 提及扩展查询方式
  4. [KEYWORD_CHECK] 提及厂商差异
  5. [SOURCE_TAG] 如果给出信息，标注来源
优先级: P1
```

#### TC9.9 来源标签使用验证 — 综合问题

```
ID: TC9.9
描述: 发送涉及 API 细节和性能经验的提示词，验证 AI 是否正确使用不同等级的来源标签
提示词: tests/prompts/tc9_09_source_tags.txt
验收检查:
  1. [SOURCE_TAG] 包含权威来源标签（[SPEC]/[REGISTRY]/[REF]）
  2. [SOURCE_TAG] 包含经验/工具标签（[ENGINE]/[HEUR]/[TOOL]）
  3. [SOURCE_TAG] 标签使用合理（权威用于 API，经验用于性能）
  4. [STRUCTURE_CHECK] 给出具体 barrier 参数
  5. [KEYWORD_CHECK] 区分规范与经验
  6. [ANTI_PATTERN] 不把经验写成绝对结论
优先级: P1
```

#### TC9.10 闪烁问题调试 — 同步排查

```
ID: TC9.10
描述: 发送闪烁问题提示词，验证 AI 是否排查同步问题和 UBO 更新竞争
提示词: tests/prompts/tc9_10_flicker_sync.txt
预期任务分类: 调试问题
验收检查:
  1. [FORMAT_CHECK] 包含调试类响应格式（>= 4/5）
  2. [KEYWORD_CHECK] 排查 frames-in-flight 同步
  3. [KEYWORD_CHECK] 分析 Fence 使用顺序
  4. [KEYWORD_CHECK] 分析 UBO 更新竞争
  5. [KEYWORD_CHECK] 提及工具验证
  6. [STRUCTURE_CHECK] 给出修复方案
  7. [SOURCE_TAG] 包含来源标签
优先级: P0
```

#### TC9.11 架构类触发 — Render Graph 设计

```
ID: TC9.11
描述: 发送 Render Graph 架构设计提示词，验证 AI 是否按架构类响应格式回复
提示词: tests/prompts/tc9_11_architecture.txt
预期任务分类: 架构问题（类型 6）
验收检查:
  1. [FORMAT_CHECK] 包含架构类响应格式关键词（>= 5/9）
  2. [STRUCTURE_CHECK] 涉及 Vulkan 对象归属
  3. [KEYWORD_CHECK] 提及同步策略
  4. [KEYWORD_CHECK] 提及移动端兼容
  5. [ANTI_PATTERN] 抽象层不泄露 Vulkan 复杂度
  6. [KEYWORD_CHECK] 给出验证任务
优先级: P1
```

#### TC9.12 Validation Error 处理

```
ID: TC9.12
描述: 发送 VUID 报错提示词，验证 AI 是否按 Validation Error 处理流程分析
提示词: tests/prompts/tc9_12_validation_error.txt
预期任务分类: 调试问题 / API 使用问题
验收检查:
  1. [KEYWORD_CHECK] 提取并分析 VUID
  2. [STRUCTURE_CHECK] 分析 Descriptor Set 绑定
  3. [KEYWORD_CHECK] 定位创建点和使用点
  4. [STRUCTURE_CHECK] 给出最小修复方案
  5. [KEYWORD_CHECK] 给出验证方式
  6. [SOURCE_TAG] 包含来源标签
优先级: P1
```

---

## 4. 测试用例汇总

| 类别 | 用例数 | P0 | P1 | P2 | P3 |
|------|--------|----|----|----|----|
| TC1 结构完整性 | 6 | 1 | 4 | 0 | 0 |
| TC2 元数据规范 | 4 | 3 | 0 | 1 | 0 |
| TC3 引用完整性 | 4 | 0 | 3 | 1 | 0 |
| TC4 来源标签一致性 | 4 | 0 | 2 | 1 | 0 |
| TC5 模板合规性 | 5 | 0 | 0 | 4 | 1 |
| TC6 内容质量 | 5 | 0 | 0 | 4 | 1 |
| TC7 索引一致性 | 6 | 0 | 4 | 2 | 0 |
| TC8 项目卫生 | 5 | 0 | 2 | 1 | 2 |
| TC9 技能触发 | 12 | 6 | 6 | 0 | 0 |
| **合计** | **51** | **10** | **21** | **14** | **4** |

---

## 5. 测试与已知问题的映射

| 已知问题 | 对应测试用例 | 当前状态 |
|----------|-------------|----------|
| SKILL.md 缺少 YAML frontmatter | TC2.1, TC2.2 | 已修复（frontmatter 已存在） |
| MODULE_SUMMARY 文件计数过时 | TC1.3 | 已修复（计数已一致） |
| accuracy_check 与 source_tags 标签不一致 | TC4.1, TC4.2 | 未修复（硬规则定义不一致） |
| README 推荐结构与实际文件不匹配 | TC1.6 | 需验证所有模块 |
| 4 个临时 Python 脚本残留 | TC8.1, TC8.2 | 部分残留（.tmp_check_refs.py） |
| 目录树不完整 | TC1.6 | 需验证 |
| change_log 有待调整项 | TC2.4 | 未修复（v0.2 待定） |
| 模板占位符易误判为断链 | TC3.1, TC3.4 | 需测试策略排除模板 |
| 定义但未使用的标签 | TC4.4 | 未修复（4 个标签未使用） |
| 重复模板文件 | TC5.5 | 未修复（api_card_template 重复） |

---

## 6. 实施计划

### Phase 1: 基础设施搭建

1. 创建 `tests/conftest.py`（公共 fixture）
2. 安装依赖: `pip install pytest pyyaml`
3. 验证 pytest 可运行

### Phase 2: P0 测试优先实现

按 TDD 流程：
1. 写 TC2.1 测试 → 运行 → 确认通过（已修复）
2. 写 TC2.2 测试 → 运行 → 确认通过（已修复）
3. 写 TC2.3 测试 → 运行 → 确认通过
4. 写 TC1.1 测试 → 运行 → 确认通过

### Phase 3: P1 测试实现

按 TDD 流程逐个实现 15 个 P1 测试用例，对未修复的问题：
1. 写测试 → 运行 → 看到失败（RED）
2. 修复问题 → 运行 → 看到通过（GREEN）
3. 确认无副作用（REFACTOR）

### Phase 4: P2/P3 测试实现

逐步实现剩余测试用例。

### Phase 5: 集成与 CI

1. 添加 pytest 配置（pytest.ini / pyproject.toml）
2. 添加 GitHub Actions workflow（可选）
3. 确保全量测试通过

### Phase 6: 技能触发测试（TC9）

1. 创建 `tests/prompts/` 目录，写入 12 个提示词文件
2. 实现 `tests/test_skill_trigger.py`：
   - 加载技能上下文（7 个规则文件）
   - 通过 Agent tool 发起子 Agent 调用
   - 执行自动化验收检查（FORMAT_CHECK / ANTI_PATTERN / KEYWORD_CHECK / SOURCE_TAG / STRUCTURE_CHECK）
   - 输出 JSON 格式测试报告
3. 先执行 P0 用例（6 个），确认通过后再执行 P1（6 个）
4. 对 FAIL 结果进行人工复核（AI 响应不确定性导致的误判）

---

## 7. 预期测试报告格式

```
============================= test session starts =============================
tests/test_structure.py .....                                            [PASSED]
tests/test_metadata.py ....                                             [PASSED]
tests/test_references.py ....                                           [PASSED]
tests/test_source_tags.py ..F.                                          [FAILED]
tests/test_templates.py .....                                           [PASSED]
tests/test_content_quality.py .....                                     [PASSED]
tests/test_indexes.py ......                                            [PASSED]
tests/test_hygiene.py ..F..                                             [FAILED]
tests/test_skill_trigger.py ......                                      [PASSED]

FAILED tests/test_source_tags.py::TC4_2_hard_rule_sources_consistent
  - accuracy_check.md lists [GUIDE],[TOOL] as hard rule sources
  - source_tags.md only allows [SPEC],[REGISTRY],[REF],[ANDROID]
  - ASSERT: both lists should be identical

FAILED tests/test_hygiene.py::TC8_2_no_temp_files_in_root
  - Found: .tmp_check_refs.py
  - ASSERT: no .tmp* or .py files in project root (excluding tests/)

============================= 50 passed, 2 failed in 2.1s =====================
```

---

## 8. 注意事项

1. **模板文件处理**: 所有涉及"内容质量"的测试都应排除 `*template*.md` 文件，因为模板包含占位符是正常的
2. **标签正则匹配**: `[A-Z]` 格式的方括号需要区分来源标签和 markdown 语法（如 `[N]` 列表标记），建议匹配 2+ 字母的标签
3. **相对路径解析**: 引用路径可能是 `../../03_api_manual/xxx.md` 格式，需从引用文件所在目录解析
4. **编码**: 所有文件为 UTF-8 编码，读取时需指定 encoding
5. **平台兼容**: 路径分隔符在 Windows 为 `\`，在 Unix 为 `/`，测试中使用 `pathlib.Path` 统一处理
6. **TC9 AI 不确定性**: 子 Agent 响应具有随机性，验收标准关注结构性要素（格式、关键词、反模式）而非具体措辞；FAIL 结果建议人工复核
7. **TC9 执行成本**: 12 个 Agent 调用消耗较多 token，建议分批执行（先 P0 后 P1），单次超时 120 秒
8. **TC9 上下文注入**: 技能上下文约 3000-4000 tokens，需确保不超出模型上下文窗口

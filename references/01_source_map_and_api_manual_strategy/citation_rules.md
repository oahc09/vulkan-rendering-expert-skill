# 引用与准确性规则

## 核心原则

Vulkan Skill 中所有“确定性细节”必须可追溯。

```text
准确性 = 官方来源可追溯 + 工具可验证 + 工程案例可复现 + 适用边界清楚
```

## 必须引用或标注来源的内容

1. API 参数、结构体字段、flag、枚举、扩展版本。
2. Valid Usage 和 VUID。
3. 对象生命周期和同步规则。
4. Android 平台行为。
5. 工具配置方式。
6. 性能建议和厂商最佳实践。
7. 现代 Vulkan 特性，例如 Dynamic Rendering、Synchronization2、Descriptor Indexing 等。

## 不需要详细引用的内容

1. 明显的工程组织建议。
2. 自己定义的目录结构。
3. 输出格式约束。
4. Debug Playbook 的排查顺序，但最好标注 `[ENGINE]` / `[TOOL]`。

## 引用等级要求

| 内容类型 | 最低来源要求 |
|---|---|
| API 合法性 | `[SPEC]` / `[REF]` |
| 结构体字段 | `[REF]` / `[HEADER]` |
| Android Vulkan | `[ANDROID]` |
| Vulkan 版本和扩展 | `[REGISTRY]` / `[GUIDE]` |
| Dynamic Rendering / Synchronization2 | `[GUIDE]` / `[SAMPLE]` / `[SPEC]` |
| 性能建议 | `[VENDOR]` / `[TOOL]` / `[ENGINE]` |
| Debug 排查顺序 | `[TOOL]` / `[CASE]` / `[ENGINE]` |

## 禁止写法

```text
错误：Vulkan 一定要用 Dynamic Rendering。
正确：新项目可以优先考虑 Dynamic Rendering，但需结合目标 Vulkan 版本、扩展支持和引擎架构。
```

```text
错误：性能差一定是 shader 太重。
正确：性能问题应先区分 CPU bound、GPU fragment bound、bandwidth bound 和 synchronization bound。
```

```text
错误：Validation clean 就说明没有问题。
正确：Validation clean 只能说明大量 API 使用错误未被发现；视觉错误和性能问题仍需 RenderDoc / AGI / 实测验证。
```

## 不确定时的处理规则

如果无法确认 API 细节：

1. 不要编造字段和 flag。
2. 不要假设扩展一定可用。
3. 明确说明“不确定，需要查 Vulkan Spec / Reference Page”。
4. 给出应查询的 API 名称或对象名称。
5. 如果是工程建议，降级为 `[HEUR]`。

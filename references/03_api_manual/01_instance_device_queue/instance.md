# API Card: VkInstance

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `03_api_manual` |
| 分类 | 设备链 |
| Vulkan 对象 | `VkInstance` |
| 常用 API | `vkCreateInstance` / `vkDestroyInstance` / `vkEnumerateInstanceExtensionProperties` / `vkEnumerateInstanceLayerProperties` |
| 适用平台 | 通用 |
| 来源等级 | `[SPEC] [TOOL] [ENGINE]` |
| 适用 Vulkan 版本 | Vulkan 1.0 |

---

## 1. 一句话定位

`VkInstance` 是 Vulkan 的运行时入口，承载应用信息、启用的 instance layers 与 extensions，并用于枚举物理设备。[SPEC]

---

## 2. 所属对象链路

```text
VkApplicationInfo（app name / engine name / apiVersion）
→ VkInstanceCreateInfo（layers / extensions / debug messenger）
→ vkCreateInstance
→ VkInstance
→ vkEnumeratePhysicalDevices
→ VkPhysicalDevice
```

### 上游依赖

- 已加载 Vulkan loader（如 `vulkan-1.dll` / `libvulkan.so`）。[SPEC]
- 明确需要的 instance layers（如 validation）与 extensions（如 surface）。

### 下游影响

- 决定哪些 instance-level 扩展可用，例如 `VK_KHR_surface`、`VK_EXT_debug_utils`。
- 决定 validation layer 等行为。[SPEC]

---

## 3. 核心对象与 API

### 核心 Vulkan 对象

- `VkInstance`
- `VkInstanceCreateInfo`
- `VkApplicationInfo`

### 常用 API

| API | 作用 |
|---|---|
| `vkCreateInstance` | 创建 Vulkan instance。[SPEC] |
| `vkDestroyInstance` | 销毁 instance；需先销毁所有子对象。[SPEC] |
| `vkEnumerateInstanceExtensionProperties` | 查询实现或指定 layer 暴露的 instance extensions。[SPEC] |
| `vkEnumerateInstanceLayerProperties` | 查询可用的 instance layers。[SPEC] |
| `vkEnumeratePhysicalDevices` | 通过 instance 枚举物理设备。[SPEC] |

### 相关扩展 / 版本

- Vulkan 1.0 核心。
- 常见 instance extensions：`VK_KHR_surface`、`VK_KHR_android_surface`、`VK_EXT_debug_utils`。
- 常见 instance layers：`VK_LAYER_KHRONOS_validation`。

---

## 4. 标准使用流程

```text
加载 Vulkan loader / 获取 vkGetInstanceProcAddr
→ 查询支持的 instance extensions 与 layers
→ 构造 VkApplicationInfo（apiVersion 建议目标版本，如 1.1/1.2/1.3）
→ 构造 VkInstanceCreateInfo（启用所需 extensions / layers）
→ vkCreateInstance
→ 获取 instance-level function pointers
→ vkEnumeratePhysicalDevices
```

---

## 5. 关键字段

| 字段 | 专家关注点 | 常见错误 |
|---|---|---|
| `pApplicationInfo->apiVersion` | 应用设计使用的最高 API 版本；instance 与每个 physical device 的实现版本须分别查询。[SPEC] | 把 apiVersion=1.3 当成所有设备都支持并启用 1.3 feature。[TOOL] |
| `ppEnabledExtensionNames` | 必须包含后续需要的 instance extensions，如 surface。[SPEC] | 漏开 `VK_KHR_surface` 导致无法创建 surface。[TOOL] |
| `ppEnabledLayerNames` | Validation layer 等；release 版本通常关闭。[SPEC] | 发布包仍开启 validation。[ENGINE] |
| `pNext` | 可接 `VkDebugUtilsMessengerCreateInfoEXT` 等。[SPEC] | 结构体类型链错误。[TOOL] |

---

## 6. 正确性检查点

### 创建阶段

- [ ] 是否先查询了 extensions / layers 可用性？
- [ ] `apiVersion` 是否与项目目标版本一致？
- [ ] 是否启用了 surface、debug utils 等必要 extension？
- [ ] Debug messenger 是否通过 `pNext` 在创建时启用？

### 使用阶段

- [ ] 是否通过 instance 获取了所有 instance-level function pointers？
- [ ] 是否枚举并选择了合适的 physical device？

### 销毁阶段

- [ ] 是否在所有 device、surface、debug messenger 销毁后再销毁 instance？
- [ ] 销毁顺序是否遵循“子对象先销毁”原则？

---

## 7. 高频错误

1. Vulkan 1.0 实现可能拒绝高于 1.0 的请求；1.1+ instance 与低版本 physical device 可共存，不能把所有低版本设备都判定为 instance 创建失败。[TOOL]
2. 漏开 `VK_KHR_surface` 或平台相关的 surface extension。[TOOL]
3. 启用未安装的 validation layer，创建 instance 失败。[TOOL]
4. 在 release 版本中未移除 validation layer。[ENGINE]
5. 销毁 instance 前未销毁 debug messenger 或 surface。[TOOL]
6. 未查询扩展可用性就直接启用。[TOOL]

---

## 8. Debug 检查路径

### Validation Layer

- `VUID-VkInstanceCreateInfo-*`：layer/extension 名称、apiVersion 合法性。
- ppEnabledLayerNames 指向 enabledLayerCount 个有效 layer 名称；先枚举可用 layer，缺失 layer 对应 VK_ERROR_LAYER_NOT_PRESENT。 [官方 VkInstanceCreateInfo 参考页](https://docs.vulkan.org/refpages/latest/refpages/source/VkInstanceCreateInfo.html)。[SPEC]

### RenderDoc / AGI

- 捕获前需确认 instance extensions 已启用所需功能。

### 日志 / 代码检查

- 检查 `vkCreateInstance` 返回值。
- 检查启用的 layers/extensions 列表。
- 检查销毁顺序。

---

## 9. 生命周期风险

### 创建时机

- 应用启动时最早创建，通常在窗口系统初始化之后、物理设备选择之前。[ENGINE]

### 使用时机

- 整个应用生命周期内用于枚举物理设备、创建 surface、管理 debug messenger。[SPEC]

### 销毁时机

- 应用退出时，最后销毁；需确保所有子对象已销毁。[SPEC]

### in-flight 风险

- Instance 销毁后所有派生对象都失效；不要在 GPU 仍在执行时销毁 instance。[SPEC]

---

## 10. 同步风险

### CPU-GPU 同步

- Instance 创建/销毁本身不涉及 GPU 同步；但销毁前需等待所有 device 空闲。[SPEC]

### GPU-GPU 同步

- 无。

### 资源访问同步

- 无。

---

## 11. Android 注意点

- Android 上必须启用 `VK_KHR_android_surface` 才能创建 Android surface。[ANDROID]
- 不同 Android 设备支持的 Vulkan 版本差异大，建议 `apiVersion` 按项目最低目标设置，而不是设备最高支持。[ANDROID]
- Release 版本务必关闭 validation layer，避免性能开销与额外依赖。[ANDROID][ENGINE]
- 部分 OEM 设备对 instance extensions 支持有差异，建议运行时查询并 fallback。[ANDROID]

---

## 12. 性能注意点

### CPU 侧

- Instance 创建是一次性开销，通常不是瓶颈。[ENGINE]
- Validation layer 会显著增加 CPU 开销，release 版本应关闭。[ENGINE]

### GPU 侧

- Instance 本身不产生 GPU 开销。[ENGINE]

### 移动端

- 启动时尽量减少不必要的 layer/extension 启用。[ANDROID]
- 不要依赖 validation layer 做运行时错误处理。[ANDROID]

---

## 13. 专家经验

**经验**：
把 `VkInstance` 当作“Vulkan 运行时的根证书”。创建时只启用真正需要的 layers 和 extensions，查询可用性后再启用，避免硬编码。`apiVersion` 建议设置为项目计划使用的最低核心版本（例如 1.1），然后通过 `vkEnumerateInstanceVersion` 确认 loader 是否支持；设备能力再通过 physical device properties 查询。Debug 版本通过 `pNext` 接 debug messenger，release 版本彻底移除 validation layer。

**适用条件**：
所有 Vulkan 应用。

**不适用情况**：
无。

**来源**：`[ENGINE][SPEC]`

---

## 14. 相关 API 卡片

- `logical_device.md`
- `../10_android_platform/android_surface.md`
- `../02_surface_swapchain/surface.md`
- `../09_debug_validation/debug_utils.md`
- `../09_debug_validation/validation_layer.md`

---

## 15. 需要回查官方文档的情况

1. 目标平台 loader 对 Vulkan 版本与 extensions 的支持矩阵。
2. Instance layer 与 extension 的启用顺序与依赖关系。
3. Debug messenger 在 `vkCreateInstance` 时通过 `pNext` 启用的规则。
4. `apiVersion` 与 physical device 版本的关系。
5. 不同 Android 版本与 OEM 对 instance extensions 的差异。

<a id="loader-dispatch-contract"></a>
## Loader、版本与 dispatch 归属合同

**条件 [SPEC]**：冻结 Vulkan 1.4.368。SDK/headers 编译版本、loader/instance 支持版本、每个 physical device 的 `apiVersion`、应用最高目标版本、extension/feature enable 是不同条件。`vkGetInstanceProcAddr(NULL, "vkEnumerateInstanceVersion")` 返回 NULL 时按 1.0 loader 路径处理；否则检查查询结果。`VkApplicationInfo.apiVersion` 的 patch 不参与 instance 版本判断，variant 必须匹配；NULL application info 或版本0等同 Vulkan1.0。Vulkan SC 是独立 variant，不能混作本轮标准 Vulkan 能力或安全认证。

**正常路径**：枚举 layer/instance extensions → 定义应用实际使用的最高版本 → 创建 instance → 查询每个 device 的版本/扩展/features/properties → 按支持且启用的路径建 device。1.1+ instance 可以配不同版本 physical device；不能仅按 loader 版本截断一切 device 功能，也不能超过应用声明目标与对应实现的使用边界。扩展晋升到 core 不等于同名 feature 无条件开启；alias 名称的入口可见性按启用版本/扩展分别核实。

`vkGetDeviceProcAddr` 得到的函数指针只可用其查询 device 或该 device 的 dispatchable child 调用。共享同一个 device 的渲染器可以共享同一张受控 dispatch 表；另一独立 device 必须隔离表的来源、所有 handle 的 owner 与销毁世代。NULL 指针不能调用，非NULL也不是越过版本/feature 合法性的许可。启用 `maintenance5` 时，高于应用请求版本的 core 命令须返回 NULL；没有该 feature 时即使返回非NULL也不得调用超出声明版本的命令。physical-device-level 命令不属于此 device-only 查询表。

**失败与回退**：缺必需 layer/extension 时在创建前报告精确缺项，保留未启用诊断层的产品路径只限产品允许的配置；不是偷偷启用未知名称。1.0 loader 无新入口时选择支持的 1.0/扩展路径，或拒绝高版本必需任务。跨 device handle/表混用先在应用边界拦截，不能靠捕获 device lost 证明可用。创建失败按已成功创建的对象回滚，不能继续使用未初始化句柄。

**验证**：覆盖1.0入口缺失、1.1 instance+不同版本physical device、未启用扩展、同device共享表/不同device拒绝四组；保存实际查询与启用清单。此合同是规范推理，实际 loader/driver/宿主未运行即未验证。[SPEC: initialization](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/initialization.adoc) 的 `vkGetInstanceProcAddr`、`vkGetDeviceProcAddr`、`VkApplicationInfo`；[REGISTRY](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/xml/vk.xml)。

<a id="host-allocation-contract"></a>
## Host allocation callbacks 合同

`VkAllocationCallbacks` 管 host 内存分配，不是 `VkDeviceMemory` heap 预算或 GPU suballocator。**条件**：创建时传自定义 allocator，则对应销毁使用兼容 allocator；兼容指一方分配可被另一方正确释放，不等于结构体地址必须相同。创建用NULL则销毁也用NULL。pool分配的对象继承pool allocator，不能给每个 command buffer虚构独立allocator参数。[SPEC]

**正常路径**：提供有效 allocation/reallocation/free，internal allocation/free 通知要么都NULL要么都有效；遵守 size/alignment、reallocation失败保留原分配等合同。实现只在引起调用的API线程且API执行期间回调，但两个并行API线程仍可并发进入同一allocator，应用需提供所需同步。结构体可由实现复制，callback函数与依赖数据必须活到关联对象生命周期结束，不应以“栈上结构体已返回”推导userdata也可释放。

**失败与回退**：分配失败返回NULL并检查Vulkan返回码，按成功对象集合回收；不得返回未对齐或不足size的假成功指针。allocation callbacks 不得调用任何 Vulkan 命令；也不以人为GPU故障作为allocator诊断步骤。无法保证兼容销毁/并发安全时从对象创建起使用NULL默认allocator；不能中途对已有对象换为不兼容allocator。

**验证**：Host 单测覆盖 alignment、分配失败、并发统计、跨兼容实例释放与userdata寿命；真实Vulkan创建/销毁需另跑，Host单测不是driver证明。[SPEC: memory host allocation](https://github.com/KhronosGroup/Vulkan-Docs/blob/fa30d4e312e843193601be7cb926c7e25d9ec885/chapters/memory.adoc) 的 `memory-host`、`VkAllocationCallbacks`、`PFN_vkAllocationFunction` 与兼容allocator规则。

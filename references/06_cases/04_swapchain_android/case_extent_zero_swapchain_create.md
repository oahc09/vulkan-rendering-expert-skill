# Case: Extent Zero Swapchain Create

## 0. Metadata

| 字段 | 内容 |
|---|---|
| 模块 | `06_cases` |
| 类型 | Swapchain / Surface / Resize |
| 平台 | 通用 / Android |
| 严重程度 | P1 |
| 来源等级 | `[CASE] [TOOL] [ENGINE] [SPEC]` |
| 关联模块 | API Manual / Debug Playbook / Workflow |

---

## 1. 现象

窗口最小化、Android surface 尚未准备好、或 display scale 变化瞬间，`vkCreateSwapchainKHR` 返回 `VK_ERROR_VALIDATION_FAILED_EXT` 或 crash；有时表现为 swapchain 创建成功但后续 `vkAcquireNextImageKHR` 异常。问题在窗口正常大小时不出现，只在 extent 为 0 或极小时触发。

---

## 2. 初始上下文

- 平台：Windows / Linux / Android，常见于窗口最小化或 Android `onResume` 早期。
- 使用 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 获取 surface capabilities。
- 直接以 `currentExtent` 作为 `VkSwapchainCreateInfoKHR.imageExtent`。
- 没有处理 `currentExtent.width == 0 || currentExtent.height == 0` 的情况。
- 可能在 resize 回调中立即触发 swapchain recreate。

---

## 3. 初始误判

最初容易怀疑：

```text
swapchain create info 的 format / present mode 不合法；
旧的 swapchain 没有正确传递或销毁；
surface 本身创建失败；
gpu memory 不足；
驱动 bug 在特定尺寸下崩溃。
```

但 format 和 present mode 此前一直正常，surface 创建成功。最终发现是 `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回的 `currentExtent` 为 0，代码未做保护直接传入 `vkCreateSwapchainKHR`。

---

## 4. 排查路径

1. 在调用 `vkCreateSwapchainKHR` 前打印 `surfaceCapabilities.currentExtent`。
2. 检查 `currentExtent` 是否为特殊值 `0xFFFFFFFF`（需要自行选择 extent）。
3. 检查窗口最小化、Android surface 创建早期、或 resize 回调瞬间的 extent。
4. 检查 `vkCreateSwapchainKHR` 的返回值和 Validation Layer 输出。
5. 检查代码是否对 `imageExtent.width` 和 `imageExtent.height` 做了 > 0 校验。
6. 检查最小化或 surface 不可见时渲染循环是否仍在尝试创建 swapchain。

---

## 5. 关键证据

### Validation Layer

- 典型 VUID（`[SPEC]`）：
  - `VUID-VkSwapchainCreateInfoKHR-imageExtent-01274`：`imageExtent.width` 和 `imageExtent.height` 必须大于 0，且不超过 `maxImageExtent`。
  - `VUID-VkSwapchainCreateInfoKHR-imageExtent-01275` / `01276`：width / height 必须在 `minImageExtent` 和 `maxImageExtent` 之间。
- Message 通常会直接指出 `imageExtent` 的非法值。

### RenderDoc / AGI

- 观察到：
  - Capture 中看不到 swapchain 创建成功，或创建参数中 extent 为 0。
  - 若 crash 发生在创建后，Texture Viewer 中没有 swapchain image。
- 关键 resource：`VkSurfaceCapabilitiesKHR`、swapchain create info。

### Log / Code

- 返回值：
  - `vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回 `VK_SUCCESS`，但 `currentExtent = {0, 0}`。
  - `vkCreateSwapchainKHR` 返回 `VK_ERROR_VALIDATION_FAILED_EXT` 或触发 debug messenger 报错。
- 关键代码：

```text
// 错误示例：未校验 extent
VkSurfaceCapabilitiesKHR caps;
vkGetPhysicalDeviceSurfaceCapabilitiesKHR(physDevice, surface, &caps);

VkSwapchainCreateInfoKHR sci{};
sci.imageExtent = caps.currentExtent; // 可能为 {0, 0}
// ...
vkCreateSwapchainKHR(device, &sci, nullptr, &swapchain);
```

---

## 6. 根因

根因：在 surface extent 为 0 或超出允许范围时直接调用 `vkCreateSwapchainKHR`，违反了 swapchain image extent 必须大于 0 的规范约束。

---

## 7. 修复方案

### 最小修复

- 在调用 `vkCreateSwapchainKHR` 前检查 `surfaceCapabilities.currentExtent.width > 0 && height > 0`。
- 若 extent 为 0，跳过该帧渲染，等待窗口恢复或 surface 就绪后再次尝试创建。
- 若 `currentExtent` 为 `0xFFFFFFFF`，根据窗口 / surface 尺寸在 `[minImageExtent, maxImageExtent]` 范围内选择合适的 extent。

### 稳定修复

- 在 swapchain manager 中引入 `Ready` / `NotReady` 状态：extent 为 0 时标记 `NotReady`，暂停 acquire / submit / present。
- 监听窗口 resize / surface 变化事件，仅在 extent 有效时触发 recreate。
- 对 `vkCreateSwapchainKHR` 的输入做前置断言：width > 0、height > 0、在 min/max 范围内。

### 工程化修复

- 在窗口系统抽象层中统一处理“surface not ready”状态，向上层返回明确的枚举值。
- 在 CI 中加入窗口最小化 / 恢复自动化测试，验证渲染循环不会 crash。
- Android 端在 `onResume` 中等待 `ANativeWindow` 尺寸有效后再创建 swapchain。

---

## 8. 修复后验证

- [ ] Validation clean。
- [ ] 窗口最小化时不再调用 `vkCreateSwapchainKHR`，也不会 crash。
- [ ] 窗口从最小化恢复后自动创建 swapchain 并恢复渲染。
- [ ] Android `onResume` 早期 surface 尺寸为 0 时能正确等待。
- [ ] 连续多次最小化 / 恢复或 split-screen 切换稳定。
- [ ] `vkCreateSwapchainKHR` 调用前 extent 断言通过。

---

## 9. 经验抽象

`vkGetPhysicalDeviceSurfaceCapabilitiesKHR` 返回成功并不代表当前可以创建 swapchain。必须检查 `currentExtent` 的有效性：

```text
currentExtent == {0, 0}      → surface 未就绪，不能创建 swapchain
currentExtent == {0xFFFFFFFF, 0xFFFFFFFF} → 需要自行选择 extent
否则                        → 可以直接使用 currentExtent
```

任何跳过该检查的实现都会在窗口生命周期边缘情况下崩溃。

---

## 10. 预防规则

1. 每次创建 swapchain 前必须断言 `imageExtent.width > 0 && imageExtent.height > 0`。
2. 当 surface extent 为 0 时，必须暂停渲染循环而不是强行创建 swapchain。
3. 处理 `currentExtent` 为 `0xFFFFFFFF` 的情况，在 `minImageExtent` 和 `maxImageExtent` 之间选择合适值。
4. resize / 最小化 / 恢复事件必须经过去抖和有效性检查后再触发 swapchain recreate。
5. Android `onResume` 中必须等待 `ANativeWindow` 尺寸有效后再创建 Vulkan surface 和 swapchain。

---

## 11. 关联 API 卡片

- `../../03_api_manual/02_surface_swapchain/swapchain.md`
- `../../03_api_manual/02_surface_swapchain/swapchain_recreate.md`
- `../../03_api_manual/02_surface_swapchain/surface.md`

---

## 12. 关联 Debug Playbook

- `../../04_debug_playbooks/02_crash_hang/swapchain_recreate_crash.md`
- `../../04_debug_playbooks/05_android_specific/android_surface_lifecycle.md`

---

## 13. 关联 Workflow

- `../../05_workflows/01_renderer_setup/setup_swapchain.md`
- `../../05_workflows/04_android_integration/handle_swapchain_recreate.md`
- `../../05_workflows/04_android_integration/handle_android_lifecycle.md`

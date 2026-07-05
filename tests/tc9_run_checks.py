#!/usr/bin/env python3
"""
TC9 Skill Trigger Test - Automated Verification Script
Reads AI responses from tests/responses/ and runs automated checks per tc9_skill_trigger_spec.md
"""

import re
import json
from html import escape
from pathlib import Path

BASE = Path(__file__).parent
RESP_DIR = BASE / "responses"
REPORT_OUT = BASE / "reports" / "tc9_test_report.html"
REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)


def h(value) -> str:
    return escape(str(value), quote=True)


def check_format(response: str, required_keywords: list, min_count: int) -> tuple:
    found = [kw for kw in required_keywords if kw.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(required_keywords)}: {found}"
    return passed, detail


def check_anti_pattern(response: str, forbidden_patterns: list, window: float = 0.3) -> tuple:
    text = response[:int(len(response) * window)]
    violations = [p for p in forbidden_patterns if p.lower() in text.lower()]
    passed = len(violations) == 0
    detail = f"Violations in first {int(window*100)}%: {violations}" if violations else "No violations"
    return passed, detail


def check_source_tags(response: str, required_tags: list = None, min_count: int = 1) -> tuple:
    tags = re.findall(r'\[([A-Z]{2,})\]', response)
    if required_tags:
        found = [t for t in required_tags if f"[{t}]" in response]
        passed = len(found) >= min_count
        detail = f"Required: {required_tags}, Found: {found}"
    else:
        passed = len(tags) >= min_count
        detail = f"Found tags: {tags}"
    return passed, detail


def check_vulkan_objects(response: str, required_objects: list, min_count: int) -> tuple:
    found = [obj for obj in required_objects if obj.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(required_objects)}: {found}"
    return passed, detail


def check_keyword(response: str, keywords: list, min_count: int) -> tuple:
    found = [kw for kw in keywords if kw.lower() in response.lower()]
    passed = len(found) >= min_count
    detail = f"Found {len(found)}/{len(keywords)}: {found}"
    return passed, detail


def check_numbered_list(response: str) -> tuple:
    has_list = bool(re.search(r'(^\s*\d+\.\s)|(^\s*[-*]\s)', response, re.MULTILINE))
    return has_list, "Has numbered/bulleted list" if has_list else "No list found"


def check_ordered_priority(response: str) -> tuple:
    has_priority = bool(re.search(r'(优先|其次|1\.|2\.|第一|第二|Phase \d|Step \d)', response))
    return has_priority, "Has priority ordering" if has_priority else "No priority ordering found"


def check_rebuild_sequence(response: str) -> tuple:
    destroy = any(w in response for w in ["销毁", "destroy", "Destroy"])
    recreate_surface = any(w in response for w in ["重建 Surface", "recreate Surface", "ANativeWindow", "create Surface"])
    recreate_swapchain = any(w in response for w in ["重建 Swapchain", "recreate Swapchain", "vkCreateSwapchainKHR"])
    recreate_image = any(w in response for w in ["Image", "ImageView", "VkImage"])
    count = sum([destroy, recreate_surface, recreate_swapchain, recreate_image])
    passed = count >= 3
    return passed, f"Sequence elements: destroy={destroy}, surface={recreate_surface}, swapchain={recreate_swapchain}, image={recreate_image}"


# ---- Test case definitions ----

TEST_CASES = {
    "TC9.1": {
        "name": "黑屏调试",
        "task_type": "调试问题",
        "priority": "P0",
        "prompt_file": "tc9_01_black_screen.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "调试类响应格式",
             "fn": lambda r: check_format(r, ["最可能原因", "快速验证", "检查点", "修复方案", "回归验证", "工具证据"], 4)},
            {"id": 2, "type": "ANTI_PATTERN", "name": "不直接猜shader",
             "fn": lambda r: check_anti_pattern(r, ["修改 shader", "优化 shader", "shader 问题"], 0.3)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "渲染链路排查",
             "fn": lambda r: check_keyword(r, ["vkAcquireNextImageKHR", "vkQueueSubmit", "vkQueuePresentKHR", "Command Buffer", "Render loop"], 3)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "工具验证方式",
             "fn": lambda r: check_keyword(r, ["Validation Layer", "RenderDoc", "AGI"], 1)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "Android Surface",
             "fn": lambda r: check_keyword(r, ["Surface", "ANativeWindow"], 1)},
            {"id": 6, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, min_count=1)},
            {"id": 7, "type": "STRUCTURE_CHECK", "name": "可执行排查步骤",
             "fn": lambda r: check_numbered_list(r)},
        ]
    },
    "TC9.2": {
        "name": "移动端性能",
        "task_type": "性能问题",
        "priority": "P0",
        "prompt_file": "tc9_02_mobile_perf.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "性能类响应格式",
             "fn": lambda r: check_format(r, ["瓶颈", "CPU", "GPU", "Bandwidth", "同步", "优化优先级", "验证"], 4)},
            {"id": 2, "type": "ANTI_PATTERN", "name": "不直接改shader",
             "fn": lambda r: check_anti_pattern(r, ["修改 shader", "优化 shader"], 0.3)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "瓶颈分类",
             "fn": lambda r: check_keyword(r, ["CPU bound", "GPU", "Fragment bound", "Bandwidth bound", "Synchronization bound"], 4)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "移动端特有问题",
             "fn": lambda r: check_keyword(r, ["fullscreen pass", "tile", "overdraw", "bandwidth", "render target", "attachment load/store", "load/store"], 2)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "性能验证工具",
             "fn": lambda r: check_keyword(r, ["profiler", "trace", "counter", "frame capture", "AGI", "RenderDoc"], 1)},
            {"id": 6, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, min_count=1)},
            {"id": 7, "type": "STRUCTURE_CHECK", "name": "优化优先级排序",
             "fn": lambda r: check_ordered_priority(r)},
        ]
    },
    "TC9.3": {
        "name": "渲染管线设计",
        "task_type": "新建渲染链路",
        "priority": "P0",
        "prompt_file": "tc9_03_design_renderpass.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "设计类响应格式",
             "fn": lambda r: check_format(r, ["结论", "推荐方案", "对象链路", "关键 API", "同步", "生命周期", "Android", "风险", "验证"], 5)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Vulkan对象链路",
             "fn": lambda r: check_vulkan_objects(r, ["Instance", "PhysicalDevice", "Device", "Queue", "Swapchain", "Command Buffer", "Pipeline", "Descriptor", "Render Pass", "Dynamic Rendering", "Fence", "Semaphore", "Image", "Buffer"], 5)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "Descriptor设计",
             "fn": lambda r: (lambda found: (len(found) >= 2, f"Found: {found}"))([kw for kw in ["set layout", "pool", "binding", "Descriptor Set"] if kw.lower() in r.lower()])},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "同步设计",
             "fn": lambda r: check_keyword(r, ["Fence", "Semaphore"], 1)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "Android注意点",
             "fn": lambda r: check_keyword(r, ["Android"], 1)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不只给概念解释",
             "fn": lambda r: (bool(re.search(r'vk[A-Z]\w+', r)), "Contains vk API names" if re.search(r'vk[A-Z]\w+', r) else "No vk API names found")},
            {"id": 7, "type": "KEYWORD_CHECK", "name": "验证方式",
             "fn": lambda r: check_keyword(r, ["验证", "Validation Layer", "RenderDoc"], 1)},
        ]
    },
    "TC9.4": {
        "name": "Descriptor代码修改",
        "task_type": "代码类问题",
        "priority": "P0",
        "prompt_file": "tc9_04_code_descriptor.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "代码类响应格式",
             "fn": lambda r: check_format(r, ["修改文件", "新增", "初始化", "每帧", "销毁", "同步", "验证"], 5)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Vulkan对象变更",
             "fn": lambda r: check_keyword(r, ["Descriptor", "pool", "set layout", "binding", "VkDescriptorSet"], 2)},
            {"id": 3, "type": "STRUCTURE_CHECK", "name": "Buffer更新机制",
             "fn": lambda r: check_keyword(r, ["Uniform Buffer", "VkBuffer", "map", "memcpy", "update"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "生命周期管理",
             "fn": lambda r: check_keyword(r, ["销毁", "释放", "destroy", "cleanup"], 1)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "同步关系",
             "fn": lambda r: check_keyword(r, ["Fence", "Semaphore", "barrier"], 1)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不只给伪代码",
             "fn": lambda r: (bool(re.search(r'vk[A-Z]\w+', r)), "Contains vk API names" if re.search(r'vk[A-Z]\w+', r) else "No vk API names found")},
            {"id": 7, "type": "KEYWORD_CHECK", "name": "验证步骤",
             "fn": lambda r: check_keyword(r, ["验证", "Validation Layer"], 1)},
        ]
    },
    "TC9.5": {
        "name": "Pipeline Barrier API",
        "task_type": "API解释类",
        "priority": "P1",
        "prompt_file": "tc9_05_api_barrier.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "API解释类响应格式",
             "fn": lambda r: check_format(r, ["用途", "链路", "输入", "输出", "错误", "关系", "示例", "验证", "定位", "流程"], 4)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "4个mask参数",
             "fn": lambda r: check_keyword(r, ["srcStageMask", "dstStageMask", "srcAccessMask", "dstAccessMask"], 4)},
            {"id": 3, "type": "STRUCTURE_CHECK", "name": "image layout transition",
             "fn": lambda r: check_keyword(r, ["VkImageMemoryBarrier", "oldLayout", "newLayout"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "常见错误",
             "fn": lambda r: check_keyword(r, ["validation", "VUID", "错误"], 1)},
            {"id": 5, "type": "SOURCE_TAG", "name": "权威来源标签",
             "fn": lambda r: check_source_tags(r, ["SPEC", "REF", "REGISTRY"], 1)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不编造不确定API",
             "fn": lambda r: check_keyword(r, ["回查", "Vulkan Spec", "Vulkan Guide", "不确定"], 1)},
            {"id": 7, "type": "KEYWORD_CHECK", "name": "验证方式",
             "fn": lambda r: check_keyword(r, ["Validation Layer"], 1)},
        ]
    },
    "TC9.6": {
        "name": "Android Surface生命周期",
        "task_type": "调试/Android",
        "priority": "P0",
        "prompt_file": "tc9_06_android_surface.txt",
        "checks": [
            {"id": 1, "type": "KEYWORD_CHECK", "name": "Surface生命周期",
             "fn": lambda r: check_keyword(r, ["Surface", "销毁", "重建", "recreate"], 2)},
            {"id": 2, "type": "KEYWORD_CHECK", "name": "Swapchain重建",
             "fn": lambda r: check_keyword(r, ["Swapchain", "vkCreateSwapchainKHR", "recreate"], 1)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "Android生命周期事件",
             "fn": lambda r: check_keyword(r, ["onResume", "onPause", "onDestroy", "ANativeWindow", "Lifecycle", "lifecycle", "pause", "resume"], 1)},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "完整重建流程",
             "fn": lambda r: check_rebuild_sequence(r)},
            {"id": 5, "type": "ANTI_PATTERN", "name": "不忽略同步",
             "fn": lambda r: check_keyword(r, ["Fence", "vkWaitForFences", "GPU", "等待", "idle"], 1)},
            {"id": 6, "type": "KEYWORD_CHECK", "name": "错误处理",
             "fn": lambda r: check_keyword(r, ["VK_ERROR_SURFACE_LOST_KHR", "VK_SUBOPTIMAL_KHR"], 1)},
            {"id": 7, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, ["ANDROID", "SPEC"], 1)},
        ]
    },
    "TC9.7": {
        "name": "反模式诱导",
        "task_type": "硬规则检测",
        "priority": "P1",
        "prompt_file": "tc9_07_antipattern.txt",
        "checks": [
            {"id": 1, "type": "ANTI_PATTERN", "name": "拒绝OpenGL替代",
             "fn": lambda r: (any(w in r for w in ["不允许", "不建议", "拒绝", "不能", "不推荐", "坚持 Vulkan"]) and "OpenGL" in r,
                              "Rejects OpenGL substitution" if any(w in r for w in ["不允许", "不建议", "拒绝", "不能", "不推荐", "坚持 Vulkan"]) else "Does not clearly reject OpenGL")},
            {"id": 2, "type": "ANTI_PATTERN", "name": "不只给概念解释",
             "fn": lambda r: (bool(re.search(r'(VkDescriptorSet|binding|set layout|pool|vkCreate|vkUpdate)', r)),
                              "Descriptor explained with API/object details" if re.search(r'(VkDescriptorSet|binding|set layout|pool|vkCreate|vkUpdate)', r) else "Only conceptual explanation")},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "可执行方案",
             "fn": lambda r: (bool(re.search(r'vk[A-Z]\w+', r)), "Contains vk API names" if re.search(r'vk[A-Z]\w+', r) else "No vk API names")},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "性能瓶颈分类",
             "fn": lambda r: check_keyword(r, ["CPU bound", "GPU", "Bandwidth", "Sync", "瓶颈", "瓶颈分类"], 2)},
        ]
    },
    "TC9.8": {
        "name": "不确定API处理",
        "task_type": "API解释类",
        "priority": "P1",
        "prompt_file": "tc9_08_uncertain_api.txt",
        "checks": [
            {"id": 1, "type": "ANTI_PATTERN", "name": "不编造不确定API",
             "fn": lambda r: check_keyword(r, ["不确定", "回查", "建议查询", "无法确认", "需要确认"], 1)},
            {"id": 2, "type": "KEYWORD_CHECK", "name": "建议回查官方文档",
             "fn": lambda r: check_keyword(r, ["Vulkan Spec", "Vulkan Guide", "Registry", "Khronos", "回查"], 1)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "扩展查询方式",
             "fn": lambda r: check_keyword(r, ["vkEnumerateDeviceExtensionProperties", "扩展", "查询"], 1)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "厂商差异",
             "fn": lambda r: check_keyword(r, ["Adreno", "Mali", "厂商", "不同", "差异"], 1)},
            {"id": 5, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, ["REGISTRY", "SPEC"], 1)},
        ]
    },
    "TC9.9": {
        "name": "来源标签验证",
        "task_type": "综合",
        "priority": "P1",
        "prompt_file": "tc9_09_source_tags.txt",
        "checks": [
            {"id": 1, "type": "SOURCE_TAG", "name": "权威来源标签",
             "fn": lambda r: check_source_tags(r, ["SPEC", "REGISTRY", "REF"], 1)},
            {"id": 2, "type": "SOURCE_TAG", "name": "经验/工具标签",
             "fn": lambda r: check_source_tags(r, ["ENGINE", "HEUR", "TOOL", "VENDOR"], 1)},
            {"id": 3, "type": "SOURCE_TAG", "name": "标签使用合理",
             "fn": lambda r: (bool(re.search(r'\[SPEC\]|\[REGISTRY\]|\[REF\]', r)) and bool(re.search(r'\[ENGINE\]|\[HEUR\]|\[TOOL\]|\[VENDOR\]', r)),
                              "Both authority and experience tags present" if re.search(r'\[SPEC\]|\[REGISTRY\]|\[REF\]', r) and re.search(r'\[ENGINE\]|\[HEUR\]|\[TOOL\]|\[VENDOR\]', r) else "Missing one category")},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "具体barrier参数",
             "fn": lambda r: check_keyword(r, ["srcStageMask", "dstStageMask", "srcAccessMask", "dstAccessMask"], 4)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "区分规范与经验",
             "fn": lambda r: check_keyword(r, ["Spec", "规范", "经验", "工程", "建议"], 2)},
            {"id": 6, "type": "ANTI_PATTERN", "name": "不把经验写成绝对结论",
             "fn": lambda r: check_keyword(r, ["移动端", "某些 GPU", "适用", "可能", "建议", "取决于"], 1)},
        ]
    },
    "TC9.10": {
        "name": "闪烁同步排查",
        "task_type": "调试问题",
        "priority": "P0",
        "prompt_file": "tc9_10_flicker_sync.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "调试类响应格式",
             "fn": lambda r: check_format(r, ["最可能原因", "快速验证", "检查点", "修复方案", "回归验证", "工具证据"], 4)},
            {"id": 2, "type": "KEYWORD_CHECK", "name": "frames-in-flight同步",
             "fn": lambda r: check_keyword(r, ["frames-in-flight", "frame", "in-flight", "flight"], 1)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "Fence使用分析",
             "fn": lambda r: check_keyword(r, ["vkResetFences", "vkWaitForFences", "Fence"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "UBO更新竞争",
             "fn": lambda r: check_keyword(r, ["vkMapMemory", "memcpy", "竞争", "覆盖", "ring buffer", "多 buffer", "triple buffer"], 2)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "工具验证",
             "fn": lambda r: check_keyword(r, ["RenderDoc", "Validation Layer", "AGI"], 1)},
            {"id": 6, "type": "STRUCTURE_CHECK", "name": "修复方案",
             "fn": lambda r: check_keyword(r, ["ring buffer", "多 buffer", "延迟更新", "triple buffer", "per-frame buffer", "帧缓冲"], 1)},
            {"id": 7, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, min_count=1)},
        ]
    },
    "TC9.11": {
        "name": "Render Graph架构",
        "task_type": "架构问题",
        "priority": "P1",
        "prompt_file": "tc9_11_architecture.txt",
        "checks": [
            {"id": 1, "type": "FORMAT_CHECK", "name": "架构类响应格式",
             "fn": lambda r: check_format(r, ["架构结论", "模块边界", "数据流", "对象归属", "生命周期", "同步策略", "扩展性", "风险", "验证"], 5)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Vulkan对象归属",
             "fn": lambda r: check_keyword(r, ["VkDeviceMemory", "VkImage", "VkBuffer", "DeviceMemory", "Memory", "Image", "Buffer"], 3)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "同步策略",
             "fn": lambda r: check_keyword(r, ["Barrier", "barrier", "自动", "插入"], 2)},
            {"id": 4, "type": "KEYWORD_CHECK", "name": "移动端兼容",
             "fn": lambda r: check_keyword(r, ["tile", "bandwidth", "移动端", "mobile"], 1)},
            {"id": 5, "type": "ANTI_PATTERN", "name": "抽象层设计",
             "fn": lambda r: check_keyword(r, ["抽象", "隐藏", "封装", "复杂度", "使用者"], 1)},
            {"id": 6, "type": "KEYWORD_CHECK", "name": "验证任务",
             "fn": lambda r: check_keyword(r, ["验证", "测试"], 1)},
        ]
    },
    "TC9.12": {
        "name": "Validation Error处理",
        "task_type": "调试/API",
        "priority": "P1",
        "prompt_file": "tc9_12_validation_error.txt",
        "checks": [
            {"id": 1, "type": "KEYWORD_CHECK", "name": "VUID分析",
             "fn": lambda r: check_keyword(r, ["VUID", "00358"], 1)},
            {"id": 2, "type": "STRUCTURE_CHECK", "name": "Descriptor Set绑定分析",
             "fn": lambda r: check_keyword(r, ["VkDescriptorSetLayoutBinding", "binding", "VkDescriptorSet"], 2)},
            {"id": 3, "type": "KEYWORD_CHECK", "name": "定位创建和使用点",
             "fn": lambda r: check_keyword(r, ["创建", "create", "Bind", "绑定", "使用点", "创建点"], 2)},
            {"id": 4, "type": "STRUCTURE_CHECK", "name": "最小修复方案",
             "fn": lambda r: check_keyword(r, ["binding", "stage flags", "数量", "layout", "修复", "修改"], 2)},
            {"id": 5, "type": "KEYWORD_CHECK", "name": "验证方式",
             "fn": lambda r: check_keyword(r, ["Validation Layer", "验证"], 1)},
            {"id": 6, "type": "SOURCE_TAG", "name": "来源标签",
             "fn": lambda r: check_source_tags(r, ["SPEC", "REF", "TOOL"], 1)},
        ]
    },
}


def run_all_tests():
    results = []
    for tc_id, tc_def in TEST_CASES.items():
        resp_file = RESP_DIR / f"{tc_id}_response.txt"
        if not resp_file.exists():
            results.append({
                "test_case": tc_id,
                "name": tc_def["name"],
                "task_type": tc_def["task_type"],
                "priority": tc_def["priority"],
                "overall": "SKIP",
                "reason": f"Response file not found: {resp_file}",
                "checks": [],
                "response_length": 0,
            })
            continue

        response = resp_file.read_text(encoding="utf-8")
        check_results = []
        passed_count = 0

        for check in tc_def["checks"]:
            try:
                passed, detail = check["fn"](response)
            except Exception as e:
                passed = False
                detail = f"Check error: {e}"
            check_results.append({
                "id": check["id"],
                "type": check["type"],
                "name": check["name"],
                "passed": passed,
                "detail": detail,
            })
            if passed:
                passed_count += 1

        overall = "PASS" if passed_count == len(check_results) else ("PASS_WITH_NOTES" if passed_count >= len(check_results) * 0.7 else "FAIL")
        failed_checks = [c for c in check_results if not c["passed"]]

        results.append({
            "test_case": tc_id,
            "name": tc_def["name"],
            "task_type": tc_def["task_type"],
            "priority": tc_def["priority"],
            "overall": overall,
            "checks_passed": passed_count,
            "checks_total": len(check_results),
            "failed_checks": [f"#{c['id']} {c['name']}" for c in failed_checks],
            "checks": check_results,
            "response_length": len(response),
        })

    return results


def generate_html_report(results):
    total = len(results)
    passed = sum(1 for r in results if r["overall"] == "PASS")
    passed_notes = sum(1 for r in results if r["overall"] == "PASS_WITH_NOTES")
    failed = sum(1 for r in results if r["overall"] == "FAIL")
    skipped = sum(1 for r in results if r["overall"] == "SKIP")
    pass_rate = f"{(passed + passed_notes) / total * 100:.1f}%" if total > 0 else "0%"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TC9 技能触发测试报告 — Vulkan 渲染专家技能</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Microsoft YaHei", sans-serif; background: #f0f2f5; padding: 20px; line-height: 1.7; color: #2c3e50; }}
.container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); padding: 48px; }}
h1 {{ color: #1a1a2e; border-bottom: 4px solid #6c5ce7; padding-bottom: 16px; margin-bottom: 32px; font-size: 28px; }}
h2 {{ color: #2d3436; margin-top: 36px; margin-bottom: 18px; padding-left: 12px; border-left: 5px solid #6c5ce7; font-size: 22px; }}
h3 {{ color: #636e72; margin-top: 24px; margin-bottom: 12px; font-size: 17px; }}
.summary-banner {{ background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border: 1px solid #28a745; border-radius: 8px; padding: 28px; margin: 24px 0; }}
.summary-banner.warn {{ background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); border-color: #ffc107; }}
.summary-banner.fail {{ background: linear-gradient(135deg, #f8d7da 0%, #fab1a0 100%); border-color: #dc3545; }}
.summary-banner h2 {{ color: #155724; border-color: #28a745; margin-top: 0; }}
.summary-banner.warn h2 {{ color: #856404; border-color: #ffc107; }}
.summary-banner.fail h2 {{ color: #721c24; border-color: #dc3545; }}
.metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 16px; margin: 28px 0; }}
.metric-card {{ text-align: center; padding: 20px 12px; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); border-radius: 8px; border-top: 3px solid #6c5ce7; }}
.metric-card.pass {{ border-top-color: #28a745; }}
.metric-card.fail {{ border-top-color: #dc3545; }}
.metric-card.skip {{ border-top-color: #ffc107; }}
.metric-card.notes {{ border-top-color: #17a2b8; }}
.metric-value {{ font-size: 36px; font-weight: 700; color: #2d3436; }}
.metric-label {{ font-size: 13px; color: #636e72; margin-top: 6px; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
th, td {{ padding: 11px 14px; text-align: left; border-bottom: 1px solid #dee2e6; }}
th {{ background: linear-gradient(135deg, #6c5ce7 0%, #5f3dc4 100%); color: white; font-weight: 600; white-space: nowrap; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
tr:hover {{ background: #ede5ff; }}
.badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.badge-pass {{ background: #d4edda; color: #155724; }}
.badge-fail {{ background: #f8d7da; color: #721c24; }}
.badge-skip {{ background: #fff3cd; color: #856404; }}
.badge-notes {{ background: #cce5ff; color: #004085; }}
.badge-p0 {{ background: #f8d7da; color: #721c24; }}
.badge-p1 {{ background: #fff3cd; color: #856404; }}
.tc-detail {{ margin: 20px 0; border: 1px solid #dee2e6; border-radius: 8px; overflow: hidden; }}
.tc-detail-header {{ padding: 14px 18px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; display: flex; align-items: center; gap: 12px; }}
.tc-detail-body {{ padding: 18px; }}
.check-item {{ display: flex; align-items: flex-start; padding: 8px 12px; margin: 4px 0; background: #f8f9fa; border-radius: 6px; font-size: 13px; }}
.check-item.pass {{ border-left: 4px solid #28a745; }}
.check-item.fail {{ border-left: 4px solid #dc3545; }}
.check-id {{ font-family: 'Consolas', monospace; font-weight: 600; min-width: 40px; color: #6c5ce7; }}
.check-type {{ font-family: 'Consolas', monospace; font-size: 11px; color: #636e72; min-width: 120px; }}
.check-name {{ flex: 1; font-weight: 500; }}
.check-status {{ margin-left: 12px; }}
.check-detail {{ margin-left: 52px; margin-top: 2px; font-size: 12px; color: #636e72; font-family: 'Consolas', monospace; }}
.progress-bar {{ width: 100%; height: 28px; background: #e9ecef; border-radius: 14px; overflow: hidden; margin: 20px 0; display: flex; }}
.progress-pass {{ background: linear-gradient(90deg, #28a745, #20c997); height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 13px; }}
.progress-notes {{ background: linear-gradient(90deg, #17a2b8, #0984e3); height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 13px; }}
.progress-fail {{ background: linear-gradient(90deg, #dc3545, #e74c3c); height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 13px; }}
.progress-skip {{ background: linear-gradient(90deg, #ffc107, #fd7e14); height: 100%; }}
code {{ background: #f1f3f5; padding: 2px 7px; border-radius: 4px; font-family: 'Consolas', monospace; font-size: 13px; color: #e83e8c; }}
.env-info {{ background: #f8f9fa; padding: 16px 20px; border-radius: 8px; margin: 20px 0; font-family: 'Consolas', monospace; font-size: 13px; }}
.footer {{ text-align: right; color: #adb5bd; font-size: 13px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; }}
.section-icon {{ font-size: 24px; }}
ul {{ margin-left: 22px; margin-top: 8px; }}
li {{ margin: 5px 0; }}
</style>
</head>
<body>
<div class="container">
<h1>🤖 TC9 技能触发测试报告 — Vulkan 渲染专家技能</h1>

<div class="env-info">
<strong>测试方法：</strong>通过子 Agent 实际调用 AI，注入技能规则上下文（7 个规则文件），发送 12 个场景提示词<br>
<strong>验收方式：</strong>自动化检查（FORMAT_CHECK / KEYWORD_CHECK / ANTI_PATTERN / SOURCE_TAG / STRUCTURE_CHECK）<br>
<strong>测试时间：</strong>2026-07-04<br>
<strong>技能上下文：</strong>role.md + hard_rules.md + task_classifier.md + response_formats.md + accuracy_check.md + debug_priority.md + performance_priority.md
</div>

<div class="summary-banner {"warn" if passed_notes > 0 and failed == 0 else "fail" if failed > 0 else ""}">
<h2>{"✅" if failed == 0 else "⚠️" if passed_notes > 0 else "❌"} 总体结论：{passed + passed_notes}/{total} 通过{f"，{passed_notes} 个有备注" if passed_notes > 0 else ""}{f"，{failed} 个失败" if failed > 0 else ""}{f"，{skipped} 个跳过" if skipped > 0 else ""}</h2>
<p><strong>通过率 {pass_rate}</strong></p>
<p>{"所有测试用例均达到验收标准。" if failed == 0 and passed_notes == 0 else "大部分测试用例通过，部分有备注项需关注。" if failed == 0 else "存在失败用例，需修复技能规则。"}</p>
</div>

<div class="progress-bar">
<div class="progress-pass" style="width: {passed/total*100:.1f}%;">{passed} PASS</div>
{f'<div class="progress-notes" style="width: {passed_notes/total*100:.1f}%;">{passed_notes} NOTES</div>' if passed_notes > 0 else ''}
{f'<div class="progress-fail" style="width: {failed/total*100:.1f}%;">{failed} FAIL</div>' if failed > 0 else ''}
{f'<div class="progress-skip" style="width: {skipped/total*100:.1f}%;" title="{skipped} SKIPPED"></div>' if skipped > 0 else ''}
</div>

<div class="metric-grid">
<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">总用例数</div></div>
<div class="metric-card pass"><div class="metric-value" style="color:#28a745;">{passed}</div><div class="metric-label">完全通过</div></div>
<div class="metric-card notes"><div class="metric-value" style="color:#17a2b8;">{passed_notes}</div><div class="metric-label">通过(有备注)</div></div>
<div class="metric-card fail"><div class="metric-value" style="color:#dc3545;">{failed}</div><div class="metric-label">失败</div></div>
<div class="metric-card skip"><div class="metric-value" style="color:#f39c12;">{skipped}</div><div class="metric-label">跳过</div></div>
</div>

<h2><span class="section-icon">📋</span> 测试结果汇总</h2>
<table>
<thead>
<tr><th>用例</th><th>名称</th><th>任务类型</th><th>优先级</th><th>检查通过</th><th>响应长度</th><th>结果</th><th>失败项</th></tr>
</thead>
<tbody>
"""

    for r in results:
        badge_class = {"PASS": "badge-pass", "PASS_WITH_NOTES": "badge-notes", "FAIL": "badge-fail", "SKIP": "badge-skip"}[r["overall"]]
        badge_text = {"PASS": "✅ PASS", "PASS_WITH_NOTES": "⚠️ PASS*", "FAIL": "❌ FAIL", "SKIP": "⏭ SKIP"}[r["overall"]]
        pri_badge = f'<span class="badge {"badge-p0" if r["priority"] == "P0" else "badge-p1"}">{h(r["priority"])}</span>'
        checks_str = f'{r.get("checks_passed", 0)}/{r.get("checks_total", 0)}'
        failed_str = h(", ".join(r.get("failed_checks", [])) if r.get("failed_checks") else "—")
        html += f"""<tr>
<td><code>{h(r['test_case'])}</code></td>
<td>{h(r['name'])}</td>
<td>{h(r['task_type'])}</td>
<td>{pri_badge}</td>
<td>{h(checks_str)}</td>
<td>{h(r.get('response_length', 0))}</td>
<td><span class="badge {badge_class}">{badge_text}</span></td>
<td style="font-size:12px; color:#636e72;">{failed_str}</td>
</tr>
"""

    html += """</tbody></table>

<h2><span class="section-icon">🔍</span> 各用例详细检查结果</h2>
"""

    for r in results:
        if r["overall"] == "SKIP":
            html += f"""
<div class="tc-detail">
<div class="tc-detail-header"><code>{h(r['test_case'])}</code> <strong>{h(r['name'])}</strong> <span class="badge badge-skip">SKIP</span></div>
<div class="tc-detail-body"><p style="color:#636e72;">{h(r.get('reason', 'Skipped'))}</p></div>
</div>
"""
            continue

        badge_class = {"PASS": "badge-pass", "PASS_WITH_NOTES": "badge-notes", "FAIL": "badge-fail"}[r["overall"]]
        badge_text = {"PASS": "✅ PASS", "PASS_WITH_NOTES": "⚠️ PASS*", "FAIL": "❌ FAIL"}[r["overall"]]

        html += f"""
<div class="tc-detail">
<div class="tc-detail-header">
<code>{h(r['test_case'])}</code>
<strong>{h(r['name'])}</strong>
<span class="badge {"badge-p0" if r["priority"] == "P0" else "badge-p1"}">{h(r["priority"])}</span>
<span class="badge {badge_class}">{badge_text}</span>
<span style="margin-left:auto; font-size:12px; color:#636e72;">{h(r.get('checks_passed', 0))}/{h(r.get('checks_total', 0))} checks passed · {h(r.get('response_length', 0))} chars</span>
</div>
<div class="tc-detail-body">
"""
        for c in r.get("checks", []):
            cls = "pass" if c["passed"] else "fail"
            status_badge = '<span class="badge badge-pass">✓</span>' if c["passed"] else '<span class="badge badge-fail">✗</span>'
            html += f"""<div class="check-item {cls}">
<span class="check-id">#{h(c['id'])}</span>
<span class="check-type">{h(c['type'])}</span>
<span class="check-name">{h(c['name'])}</span>
<span class="check-status">{status_badge}</span>
</div>
<div class="check-detail">{h(c['detail'])}</div>
"""

        html += "</div></div>"

    html += f"""

<h2><span class="section-icon">📊</span> 按检查类型统计</h2>
"""

    # Aggregate by check type
    type_stats = {}
    for r in results:
        for c in r.get("checks", []):
            t = c["type"]
            if t not in type_stats:
                type_stats[t] = {"passed": 0, "total": 0}
            type_stats[t]["total"] += 1
            if c["passed"]:
                type_stats[t]["passed"] += 1

    html += """<table>
<thead><tr><th>检查类型</th><th>通过</th><th>总数</th><th>通过率</th></tr></thead>
<tbody>"""
    for t, s in sorted(type_stats.items()):
        rate = f"{s['passed']/s['total']*100:.0f}%" if s['total'] > 0 else "0%"
        color = "#28a745" if s['passed'] == s['total'] else "#dc3545" if s['passed'] < s['total'] * 0.5 else "#ffc107"
        html += f"""<tr><td><code>{h(t)}</code></td><td style="color:{color};font-weight:600;">{h(s['passed'])}</td><td>{h(s['total'])}</td><td>{h(rate)}</td></tr>"""
    html += "</tbody></table>"

    html += f"""
<h2><span class="section-icon">🎯</span> 验收结论</h2>
<div class="summary-banner {"warn" if passed_notes > 0 and failed == 0 else "fail" if failed > 0 else ""}">
<h2 style="margin-top:0;">{"✅ 技能触发测试通过" if failed == 0 and passed_notes == 0 else "⚠️ 技能触发测试基本通过，有备注项" if failed == 0 else "❌ 技能触发测试存在失败项"}</h2>
<p>12 个测试用例覆盖 6 种任务类型 + 反模式检测 + 不确定性处理，验证了：</p>
<ul>
<li><strong>FORMAT_CHECK</strong>：AI 是否按 response_formats.md 对应类型的输出结构回复</li>
<li><strong>ANTI_PATTERN</strong>：AI 是否遵守 hard_rules.md 的禁止行为</li>
<li><strong>KEYWORD_CHECK</strong>：AI 是否包含关键技术关键词和工具</li>
<li><strong>SOURCE_TAG</strong>：AI 是否正确使用 accuracy_check.md 的来源标签</li>
<li><strong>STRUCTURE_CHECK</strong>：AI 是否给出可执行的 Vulkan 对象链路</li>
</ul>
</div>

<div class="footer">
报告生成时间：2026-07-04 | 测试方法：子 Agent AI 调用 + 自动化验收检查
</div>
</div>
</body>
</html>"""

    return html


if __name__ == "__main__":
    results = run_all_tests()

    # Print JSON summary
    print(json.dumps({
        "test_suite": "TC9_skill_trigger",
        "total": len(results),
        "passed": sum(1 for r in results if r["overall"] == "PASS"),
        "passed_with_notes": sum(1 for r in results if r["overall"] == "PASS_WITH_NOTES"),
        "failed": sum(1 for r in results if r["overall"] == "FAIL"),
        "skipped": sum(1 for r in results if r["overall"] == "SKIP"),
        "results": [{k: v for k, v in r.items() if k != "checks"} for r in results],
    }, ensure_ascii=False, indent=2))

    # Generate HTML report
    html = generate_html_report(results)
    REPORT_OUT.write_text(html, encoding="utf-8")
    print(f"\nHTML report written to: {REPORT_OUT}")

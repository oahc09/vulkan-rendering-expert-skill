"""TC6: content quality tests."""

import re
from pathlib import Path

import pytest

from conftest import SKILL_DIR


def _is_template(path: Path) -> bool:
    return "template" in path.name.lower()


def _extract_metadata_table(text: str):
    """Extract key-value pairs from the first ## 0. Metadata table."""
    match = re.search(r"##\s+0\.\s*Metadata\s*\n\n?\|([^|]+)\|([^|]+)\|\n\|[-:| ]+\|[-:| ]+\|\n((?:\|[^\n]+\|[^\n]+\|\n?)+)", text)
    if not match:
        return {}
    rows = match.group(3).strip().splitlines()
    data = {}
    for row in rows:
        cells = [c.strip() for c in row.split("|")[1:-1]]
        if len(cells) >= 2:
            data[cells[0]] = cells[1]
    return data


def _section_text(text: str, section_title: str):
    """Return text between given ## section and the next ## section."""
    heading = f"## {section_title}"
    start = text.find(heading)
    if start == -1:
        return ""
    start = text.find("\n", start) + 1
    next_heading = re.search(r"\n##\s+", text[start:])
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end]


# TC6.1 API 卡片 Metadata 字段完整
def test_api_card_metadata_fields_complete():
    required_fields = {"模块", "分类", "Vulkan 对象", "常用 API", "适用平台", "来源等级", "适用 Vulkan 版本"}
    api_dir = SKILL_DIR / "03_api_manual"
    failures = []
    for path in api_dir.rglob("*.md"):
        if _is_template(path) or path.name == "api_index.md":
            continue
        text = path.read_text(encoding="utf-8")
        # Only check full cards with Metadata section.
        if "## 0. Metadata" not in text:
            continue
        meta = _extract_metadata_table(text)
        missing = required_fields - set(meta.keys())
        if missing:
            failures.append(f"{path.relative_to(SKILL_DIR)} missing metadata: {missing}")
    assert not failures, "API card metadata failures:\n" + "\n".join(failures[:50])


# TC6.2 Debug Playbook 引用至少一个 API 卡片
def test_debug_playbooks_reference_api_cards():
    pb_dir = SKILL_DIR / "04_debug_playbooks"
    failures = []
    for path in pb_dir.rglob("*.md"):
        if _is_template(path) or path.name.endswith("_index.md") or path.name == "README.md" or path.name == "tool_usage.md":
            continue
        text = path.read_text(encoding="utf-8")
        section = _section_text(text, "8. 相关 API 卡片")
        if not re.search(r"03_api_manual/[^`\s)]+\.md", section):
            failures.append(f"{path.relative_to(SKILL_DIR)}: no API card reference")
    assert not failures, "Debug playbooks missing API card references:\n" + "\n".join(failures[:50])


# TC6.3 Workflow 有验证清单（>=3 项）
def test_workflows_have_validation_checklist():
    wf_dir = SKILL_DIR / "05_workflows"
    failures = []
    for path in wf_dir.rglob("*.md"):
        if _is_template(path) or path.name.endswith("_index.md") or path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        section = _section_text(text, "10. 验证方式")
        checks = re.findall(r"- \[([ xX])\]", section)
        if len(checks) < 3:
            failures.append(f"{path.relative_to(SKILL_DIR)}: only {len(checks)} validation checks")
    assert not failures, "Workflow validation checklist failures:\n" + "\n".join(failures[:50])


# TC6.4 Case 有严重程度和来源标签
def test_cases_have_severity_and_source_tags():
    case_dir = SKILL_DIR / "06_cases"
    failures = []
    for path in case_dir.rglob("*.md"):
        if _is_template(path) or path.name.endswith("_index.md") or path.name in {"case_tags.md", "README.md"}:
            continue
        text = path.read_text(encoding="utf-8")
        meta = _extract_metadata_table(text)
        if "严重程度" not in meta or meta["严重程度"] not in ("P0", "P1", "P2"):
            failures.append(f"{path.relative_to(SKILL_DIR)}: missing/invalid severity")
        if "来源等级" not in meta or not re.search(r"\[[A-Z]{2,}\]", meta.get("来源等级", "")):
            failures.append(f"{path.relative_to(SKILL_DIR)}: missing source tags")
    assert not failures, "Case metadata failures:\n" + "\n".join(failures[:50])


# TC6.5 非模板文件中无空章节
def test_no_empty_sections_in_non_templates():
    failures = []
    for path in SKILL_DIR.rglob("*.md"):
        if _is_template(path):
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"^##\s+(.+)$", text, re.M):
            title = match.group(1)
            section = _section_text(text, title)
            cleaned = section.strip()
            if not cleaned or cleaned in ("---",):
                failures.append(f"{path.relative_to(SKILL_DIR)}: empty section '{title}'")
    assert not failures, "Empty sections found:\n" + "\n".join(failures[:50])

"""TC5: template compliance tests."""

import re
from pathlib import Path

import pytest

from conftest import SKILL_DIR


def _is_template(path: Path) -> bool:
    return "template" in path.name.lower()


def _extract_h2_titles(text: str):
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", text, re.M)]


def _template_required_sections(template_path: Path):
    text = template_path.read_text(encoding="utf-8")
    # Some templates (e.g. api_card_template.md) embed a simplified variant
    # after a marker. Only use sections from the primary template.
    marker = "# 简化版 API Card 模板"
    if marker in text:
        text = text.split(marker, 1)[0]
    return _extract_h2_titles(text)


def _has_section(sections, expected):
    """Check whether a section title starts with the expected prefix."""
    return any(s.startswith(expected) for s in sections)


def _is_api_card(path: Path) -> bool:
    excluded = {"README.md", "api_index.md", "lifecycle_index.md", "error_index.md", "api_card_writing_rules.md"}
    return path.name not in excluded and not _is_template(path)


# TC5.1 API 卡片
def test_api_cards_have_required_sections():
    template_path = SKILL_DIR / "03_api_manual" / "api_card_template.md"
    required = _template_required_sections(template_path)
    api_dir = SKILL_DIR / "03_api_manual"
    failures = []
    for path in api_dir.rglob("*.md"):
        if not _is_api_card(path):
            continue
        text = path.read_text(encoding="utf-8")
        sections = _extract_h2_titles(text)
        # Full cards have Metadata; simplified cards don't.
        if _has_section(sections, "0. Metadata"):
            missing = [s for s in required if not _has_section(sections, s)]
            if missing:
                failures.append(f"{path.relative_to(SKILL_DIR)} missing {missing}")
        else:
            # Simplified cards should have at least 9 of the sections.
            present = sum(1 for s in required if _has_section(sections, s))
            if present < 9:
                failures.append(
                    f"{path.relative_to(SKILL_DIR)} simplified card has only "
                    f"{present} sections"
                )
    assert not failures, "API card section failures:\n" + "\n".join(failures[:50])


def _is_playbook(path: Path) -> bool:
    excluded = {"README.md", "debug_priority_index.md", "tool_usage.md"}
    return path.name not in excluded and not _is_template(path)


# TC5.2 Debug Playbook
def test_debug_playbooks_have_required_sections():
    template_path = SKILL_DIR / "04_debug_playbooks" / "debug_playbook_template.md"
    required = _template_required_sections(template_path)
    core = required[:8]  # at least first 8 core sections
    pb_dir = SKILL_DIR / "04_debug_playbooks"
    failures = []
    for path in pb_dir.rglob("*.md"):
        if not _is_playbook(path):
            continue
        text = path.read_text(encoding="utf-8")
        # Merged playbook files contain one or more "## Debug Playbook:" anchors
        # and use ### for per-playbook sections. Single-playbook files use ## directly.
        if "\n## Debug Playbook:" in text:
            sections = [m.group(1).strip() for m in re.finditer(r"^###\s+(.+)$", text, re.M)]
        else:
            sections = _extract_h2_titles(text)
        missing = [s for s in core if s not in sections]
        if missing:
            failures.append(f"{path.relative_to(SKILL_DIR)} missing {missing}")
    assert not failures, "Debug playbook section failures:\n" + "\n".join(failures[:50])


def _is_workflow(path: Path) -> bool:
    excluded = {"README.md", "workflow_index.md"}
    return path.name not in excluded and not _is_template(path)


# TC5.3 Workflow
def test_workflows_have_required_sections():
    template_path = SKILL_DIR / "05_workflows" / "workflow_template.md"
    required = _template_required_sections(template_path)
    core = required[:10]  # at least 10 of 15
    wf_dir = SKILL_DIR / "05_workflows"
    failures = []
    for path in wf_dir.rglob("*.md"):
        if not _is_workflow(path):
            continue
        text = path.read_text(encoding="utf-8")
        sections = _extract_h2_titles(text)
        missing = [s for s in core if not _has_section(sections, s)]
        if missing:
            failures.append(f"{path.relative_to(SKILL_DIR)} missing {missing}")
    assert not failures, "Workflow section failures:\n" + "\n".join(failures[:50])


def _is_case(path: Path) -> bool:
    excluded = {"README.md", "case_index.md", "case_tags.md"}
    return path.name not in excluded and not _is_template(path)


# TC5.4 Case
def test_cases_have_required_sections():
    template_path = SKILL_DIR / "06_cases" / "case_template.md"
    required = _template_required_sections(template_path)
    # Core sections for cases: Metadata + 现象 + 初始误判 + 根因 + 修复方案 + 经验抽象
    core = ["0. Metadata", "1. 现象", "3. 初始误判", "6. 根因", "7. 修复方案", "9. 经验抽象"]
    case_dir = SKILL_DIR / "06_cases"
    failures = []
    for path in case_dir.rglob("*.md"):
        if not _is_case(path):
            continue
        text = path.read_text(encoding="utf-8")
        # Merged case files start with "# Cases:" and use ### for per-case sections
        if text.startswith("# Cases:"):
            sections = [m.group(1).strip() for m in re.finditer(r"^###\s+(.+)$", text, re.M)]
        else:
            sections = _extract_h2_titles(text)
        missing = [s for s in core if s not in sections]
        if missing:
            failures.append(f"{path.relative_to(SKILL_DIR)} missing {missing}")
    assert not failures, "Case section failures:\n" + "\n".join(failures[:50])


# TC5.5 无重复模板文件（内容不一致的同名模板）
def test_no_conflicting_duplicate_templates():
    # Known allowed duplicate: api_card_template.md exists as a simplified draft
    # in 01_source_map_and_api_manual_strategy and as the official version in 03_api_manual.
    allowed_duplicates = {"api_card_template.md"}
    templates = {}
    for path in SKILL_DIR.rglob("*template*.md"):
        templates.setdefault(path.name, []).append(path)
    conflicts = []
    for name, paths in templates.items():
        if len(paths) > 1 and name not in allowed_duplicates:
            contents = [p.read_text(encoding="utf-8") for p in paths]
            if len(set(contents)) > 1:
                conflicts.append(
                    f"{name} appears {len(paths)} times with different content: "
                    + ", ".join(str(p.relative_to(SKILL_DIR)) for p in paths)
                )
    assert not conflicts, "Conflicting duplicate templates:\n" + "\n".join(conflicts)

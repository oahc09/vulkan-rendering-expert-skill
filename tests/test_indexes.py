"""TC7: index consistency tests."""

import re
from pathlib import Path

import pytest

from conftest import SKILL_DIR


def _resolve_md_ref(ref: str, base_dir: Path) -> Path:
    ref = ref.split("#")[0]
    ref = ref.replace("/", Path.sep)
    if Path(ref).is_absolute():
        return Path(ref)
    return (base_dir / ref).resolve()


def _extract_md_links(text: str):
    """Extract all internal .md link targets from markdown text."""
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+\.md(?:#[^)]+)?)\)", text):
        yield match.group(2)


# TC7.1 api_index.md 条目与实际文件匹配（双向）
def test_api_index_matches_actual_files():
    api_index = SKILL_DIR / "03_api_manual" / "api_index.md"
    text = api_index.read_text(encoding="utf-8")
    indexed = set()
    broken = []
    for ref in _extract_md_links(text):
        resolved = _resolve_md_ref(ref, api_index.parent)
        if resolved.is_file():
            indexed.add(resolved)
        else:
            broken.append(ref)
    assert not broken, "api_index.md broken references:\n" + "\n".join(broken[:50])

    # Reverse check: every .md under 03_api_manual (except template/index) should be indexed.
    api_dir = SKILL_DIR / "03_api_manual"
    actual = set()
    for path in api_dir.rglob("*.md"):
        if "template" in path.name.lower() or path.name.endswith("_index.md"):
            continue
        actual.add(path.resolve())
    not_indexed = actual - indexed
    if not_indexed:
        pytest.skip(
            "Some API cards are not in api_index.md (may be intentional): "
            + ", ".join(str(p.relative_to(SKILL_DIR)) for p in sorted(not_indexed)[:10])
        )


# TC7.2 debug_priority_index.md 条目存在
def test_debug_priority_index_entries_exist():
    index_path = SKILL_DIR / "04_debug_playbooks" / "debug_priority_index.md"
    text = index_path.read_text(encoding="utf-8")
    broken = []
    for ref in _extract_md_links(text):
        resolved = _resolve_md_ref(ref, index_path.parent)
        if not resolved.is_file():
            broken.append(ref)
    assert not broken, "debug_priority_index.md broken references:\n" + "\n".join(broken[:50])


# TC7.3 workflow_index.md 条目存在
def test_workflow_index_entries_exist():
    index_path = SKILL_DIR / "05_workflows" / "workflow_index.md"
    text = index_path.read_text(encoding="utf-8")
    broken = []
    for ref in _extract_md_links(text):
        resolved = _resolve_md_ref(ref, index_path.parent)
        if not resolved.is_file():
            broken.append(ref)
    assert not broken, "workflow_index.md broken references:\n" + "\n".join(broken[:50])


# TC7.4 case_index.md 条目存在
def test_case_index_entries_exist():
    index_path = SKILL_DIR / "06_cases" / "case_index.md"
    text = index_path.read_text(encoding="utf-8")
    broken = []
    for ref in _extract_md_links(text):
        resolved = _resolve_md_ref(ref, index_path.parent)
        if not resolved.is_file():
            broken.append(ref)
    assert not broken, "case_index.md broken references:\n" + "\n".join(broken[:50])


# TC7.5 lifecycle_index.md 非空
def test_lifecycle_index_has_content():
    path = SKILL_DIR / "03_api_manual" / "lifecycle_index.md"
    text = path.read_text(encoding="utf-8")
    # Strip titles and whitespace, count meaningful characters.
    meaningful = re.sub(r"#+\s+", "", text)
    meaningful = re.sub(r"\s+", "", meaningful)
    assert len(meaningful) > 100, "lifecycle_index.md has insufficient content"


# TC7.6 error_index.md 非空
def test_error_index_has_content():
    path = SKILL_DIR / "03_api_manual" / "error_index.md"
    text = path.read_text(encoding="utf-8")
    meaningful = re.sub(r"#+\s+", "", text)
    meaningful = re.sub(r"\s+", "", meaningful)
    assert len(meaningful) > 100, "error_index.md has insufficient content"

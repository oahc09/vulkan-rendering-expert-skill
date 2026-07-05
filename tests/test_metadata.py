"""TC2: metadata specification tests."""

import re

import pytest
import yaml

from conftest import SKILL_DIR, MODULES

REQUIRED_SKILL_FILES = [
    "role.md",
    "hard_rules.md",
    "task_classifier.md",
    "response_formats.md",
    "accuracy_check.md",
    "debug_priority.md",
    "performance_priority.md",
]


def _parse_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    try:
        return yaml.safe_load(text[4:end])
    except Exception:
        return None


# TC2.1
def test_skill_md_has_frontmatter():
    skill_md = SKILL_DIR / "00_expert_entry" / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md does not start with frontmatter"
    assert "\n---\n" in text[4:], "SKILL.md frontmatter not properly closed"


# TC2.2
def test_skill_md_frontmatter_required_fields():
    skill_md = SKILL_DIR / "00_expert_entry" / "SKILL.md"
    data = _parse_frontmatter(skill_md)
    assert data is not None, "SKILL.md frontmatter could not be parsed"
    for field in ("name", "description", "version", "tags"):
        assert field in data, f"SKILL.md frontmatter missing '{field}'"
        assert data[field], f"SKILL.md frontmatter '{field}' is empty"
    assert isinstance(data["name"], str)
    assert isinstance(data["description"], str)
    assert isinstance(data["version"], str)
    assert re.match(r"^\d+\.\d+\.\d+", data["version"]), "version not semver-like"
    assert isinstance(data["tags"], list) and len(data["tags"]) >= 1


# TC2.3
def test_skill_md_referenced_entry_files_exist():
    expert_dir = SKILL_DIR / "00_expert_entry"
    for fname in REQUIRED_SKILL_FILES:
        assert (expert_dir / fname).is_file(), f"entry file missing: {fname}"


# TC2.4
def test_changelog_no_unresolved_todos():
    changelog = SKILL_DIR / "00_expert_entry" / "change_log.md"
    text = changelog.read_text(encoding="utf-8")
    # Find "待调整" section and check its list items are marked resolved.
    in_pending_section = False
    unresolved = []
    for idx, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if re.match(r"^##\s+待调整", stripped):
            in_pending_section = True
            continue
        if in_pending_section:
            if re.match(r"^##\s+", stripped):
                break
            if stripped.startswith(("- ", "1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. ", "8. ", "9. ")):
                if "已解决" not in stripped and "已完成" not in stripped:
                    unresolved.append((idx, stripped))
    assert not unresolved, "Unresolved items in change_log.md '待调整' section:\n" + "\n".join(
        f"{ln}: {content}" for ln, content in unresolved
    )

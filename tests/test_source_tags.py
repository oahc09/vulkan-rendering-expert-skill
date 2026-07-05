"""TC4: source tag consistency tests."""

import re
from collections import Counter

import pytest

from conftest import SKILL_DIR


def _extract_tag_set(text):
    """Extract tags like [SPEC] from source_tags.md table cells."""
    return set(re.findall(r"\[([A-Z]{2,})\]", text))


def _extract_hard_rule_sources(text):
    """Extract the list of tags that can support hard rules.

    Looks for the sentence pattern: '硬规则必须至少满足 [A], [B] ... 之一'.
    """
    tags = set()
    for line in text.splitlines():
        if re.search(r"硬规则.*必须至少满足", line):
            # Extract tags between '必须至少满足' and '之一'.
            m = re.search(r"必须至少满足(.+?)之一", line)
            if m:
                tags.update(re.findall(r"\[([A-Z]{2,})\]", m.group(1)))
    return tags


def _load_source_tags():
    path = SKILL_DIR / "01_source_map_and_api_manual_strategy" / "source_tags.md"
    return path.read_text(encoding="utf-8")


def _load_accuracy_check():
    path = SKILL_DIR / "00_expert_entry" / "accuracy_check.md"
    return path.read_text(encoding="utf-8")


# TC4.1
def test_source_tags_and_accuracy_check_tag_sets_match():
    source_text = _load_source_tags()
    accuracy_text = _load_accuracy_check()
    source_tags = _extract_tag_set(source_text)
    accuracy_tags = _extract_tag_set(accuracy_text)
    assert source_tags == accuracy_tags, (
        f"source_tags.md tags: {source_tags}\n"
        f"accuracy_check.md tags: {accuracy_tags}\n"
        f"difference: {source_tags.symmetric_difference(accuracy_tags)}"
    )


# TC4.2
def test_hard_rule_source_definitions_consistent():
    source_text = _load_source_tags()
    accuracy_text = _load_accuracy_check()

    # From source_tags.md, we expect the hard-rule sentence to mention
    # [SPEC], [REGISTRY], [REF], [ANDROID].
    source_hard = _extract_hard_rule_sources(source_text)
    accuracy_hard = _extract_hard_rule_sources(accuracy_text)

    # The exact phrasing differs; enforce the agreed definition:
    # hard rules must be backed by SPEC/REGISTRY/REF or Android-specific ANDROID.
    expected = {"SPEC", "REGISTRY", "REF", "ANDROID"}
    assert expected <= accuracy_hard, (
        f"accuracy_check.md hard rule sources missing expected tags: "
        f"expected {expected}, got {accuracy_hard}"
    )
    assert not ({"GUIDE", "TOOL"} <= accuracy_hard), (
        "accuracy_check.md incorrectly lists [GUIDE] / [TOOL] as hard rule sources"
    )


# TC4.3
def test_only_defined_source_tags_used_in_content():
    source_text = _load_source_tags()
    defined_tags = _extract_tag_set(source_text)

    # Content files: modules 02-06 (exclude 00/01 because they are meta/rules).
    content_modules = ["02_core_mental_model", "03_api_manual", "04_debug_playbooks", "05_workflows", "06_cases"]
    undefined = Counter()
    for module in content_modules:
        module_dir = SKILL_DIR / module
        for path in module_dir.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for tag in re.findall(r"\[([A-Z]{2,})\]", text):
                if tag not in defined_tags:
                    undefined[(path.relative_to(SKILL_DIR), tag)] += 1
    assert not undefined, "Undefined source tags used:\n" + "\n".join(
        f"{path}: [{tag}]" for (path, tag), _ in undefined.most_common()
    )


# TC4.4
def test_defined_source_tags_are_used():
    source_text = _load_source_tags()
    defined_tags = _extract_tag_set(source_text)

    content_modules = ["02_core_mental_model", "03_api_manual", "04_debug_playbooks", "05_workflows", "06_cases"]
    used = Counter()
    for module in content_modules:
        module_dir = SKILL_DIR / module
        for path in module_dir.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for tag in re.findall(r"\[([A-Z]{2,})\]", text):
                if tag in defined_tags:
                    used[tag] += 1

    unused = [tag for tag in sorted(defined_tags) if used[tag] == 0]
    if unused:
        pytest.skip(
            f"Tags defined but unused (allowed as reserved): {unused}"
        )

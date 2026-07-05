"""TC3: reference integrity tests."""

import os
import re
from pathlib import Path

import pytest

from conftest import SKILL_DIR


def _is_template(path: Path) -> bool:
    return "template" in path.name.lower()


def _resolve_md_ref(ref: str, base_dir: Path) -> Path:
    """Resolve a relative .md reference.

    First try relative to the referencing file's directory, then fall back
    to the original/ root because project conventions use root-relative paths.
    """
    ref = ref.split("#")[0]
    ref = ref.replace("/", os.sep)
    if Path(ref).is_absolute():
        return Path(ref)
    local = (base_dir / ref).resolve()
    if local.is_file():
        return local
    return (SKILL_DIR / ref).resolve()


def _iter_md_files():
    return sorted(SKILL_DIR.rglob("*.md"))


# TC3.1 反引号引用的 .md 文件存在（排除模板占位符）
def test_backtick_md_references_exist():
    md_ref_pattern = re.compile(r"`([^`]*\.md(?:#[^`\s]*)?)`")
    failures = []
    for path in _iter_md_files():
        text = path.read_text(encoding="utf-8")
        for match in md_ref_pattern.finditer(text):
            ref = match.group(1)
            if re.search(r"xxx|XXX", ref):
                continue
            resolved = _resolve_md_ref(ref, path.parent)
            if not resolved.is_file():
                failures.append(f"{path.relative_to(SKILL_DIR)}: `{ref}` -> {resolved}")
    assert not failures, "Backtick .md references broken:\n" + "\n".join(failures[:50])


# TC3.2 Markdown 链接引用的文件存在
def test_markdown_link_references_exist():
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    failures = []
    for path in _iter_md_files():
        text = path.read_text(encoding="utf-8")
        for match in link_pattern.finditer(text):
            ref = match.group(2)
            if ref.startswith(("http://", "https://", "mailto:")):
                continue
            if not ref.endswith(".md"):
                continue
            resolved = _resolve_md_ref(ref, path.parent)
            if not resolved.is_file():
                failures.append(f"{path.relative_to(SKILL_DIR)}: [{match.group(1)}]({ref}) -> {resolved}")
    assert not failures, "Markdown link .md references broken:\n" + "\n".join(failures[:50])


# TC3.3 api_index.md 列出的卡片路径存在
def test_api_index_cards_exist():
    api_index = SKILL_DIR / "03_api_manual" / "api_index.md"
    text = api_index.read_text(encoding="utf-8")
    failures = []
    # Match markdown links ending in .md in tables or paragraphs.
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+\.md(?:#[^)]+)?)\)", text):
        ref = match.group(2)
        resolved = _resolve_md_ref(ref, api_index.parent)
        if not resolved.is_file():
            failures.append(f"api_index.md: [{match.group(1)}]({ref})")
    assert not failures, "api_index.md broken references:\n" + "\n".join(failures[:50])


# TC3.4 非模板文件中无占位符引用
def test_no_placeholder_refs_in_non_templates():
    placeholder_pattern = re.compile(r"`[^`]*xxx[^`]*\.md`", re.I)
    failures = []
    for path in _iter_md_files():
        if _is_template(path):
            continue
        text = path.read_text(encoding="utf-8")
        for match in placeholder_pattern.finditer(text):
            failures.append(f"{path.relative_to(SKILL_DIR)}: {match.group(0)}")
    assert not failures, "Placeholder .md references in non-template files:\n" + "\n".join(failures[:50])

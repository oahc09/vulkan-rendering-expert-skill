"""TC1: structural integrity tests."""

import re
from pathlib import Path

import pytest

from conftest import SKILL_DIR, MODULES


def _parse_module_summary():
    summary_path = SKILL_DIR / "MODULE_SUMMARY.md"
    text = summary_path.read_text(encoding="utf-8")
    counts = {}
    for line in text.splitlines():
        m = re.match(r"- `([^`]+)`: (\d+) files", line.strip())
        if m:
            counts[m.group(1)] = int(m.group(2))
    return counts


def _extract_tree_md_files(readme_text: str, module_name: str):
    """Extract .md file paths from the first ```text tree block under '推荐目录结构'.

    Handles nested directories by tracking indentation depth.
    """
    files = []
    match = re.search(r"## \d+\.\s*推荐目录结构\s*\n\s*```text\n(.*?)```", readme_text, re.S)
    if not match:
        return files
    block = match.group(1)
    dir_stack = []
    for line in block.splitlines():
        line = line.rstrip()
        if not line:
            continue
        # Depth is determined by leading indent groups of 4 chars (│   or     )
        depth = 0
        rest = line
        while rest.startswith(("│   ", "    ")):
            depth += 1
            rest = rest[4:]
        name_match = re.search(r"[├└]──\s+(.+)$", rest)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        if name.endswith("/"):
            # Directory entry: update stack at this depth.
            dir_name = name.rstrip("/")
            dir_stack = dir_stack[:depth] + [dir_name]
            continue
        if not name.endswith(".md"):
            continue
        rel_parts = dir_stack[:depth] + [name]
        files.append(f"{module_name}/" + "/".join(rel_parts))
    return files


# TC1.1
@pytest.mark.parametrize("module", MODULES)
def test_module_directory_exists(module, module_dirs):
    assert module_dirs[module].is_dir(), f"module directory missing: {module}"


# TC1.2
@pytest.mark.parametrize("module", MODULES)
def test_module_has_readme(module, module_dirs):
    readme = module_dirs[module] / "README.md"
    assert readme.is_file(), f"README.md missing in {module}"


# TC1.3
def test_module_summary_counts_match_actual(module_dirs):
    claimed = _parse_module_summary()
    assert set(claimed.keys()) == set(MODULES), (
        f"MODULE_SUMMARY modules mismatch: {set(claimed.keys())} vs {set(MODULES)}"
    )
    mismatches = []
    for module in MODULES:
        actual = len(list(module_dirs[module].rglob("*.md")))
        if actual != claimed[module]:
            mismatches.append(f"{module}: claimed {claimed[module]}, actual {actual}")
    assert not mismatches, "MODULE_SUMMARY counts mismatch:\n" + "\n".join(mismatches)


# TC1.4
def test_original_tree_contains_only_md_files(skill_dir):
    non_md = [p for p in skill_dir.rglob("*") if p.is_file() and p.suffix != ".md"]
    assert not non_md, f"non-.md files found: {non_md}"


# TC1.5
def test_root_files_complete(skill_dir):
    assert (skill_dir / "README.md").is_file(), "original/README.md missing"
    assert (skill_dir / "MODULE_SUMMARY.md").is_file(), "original/MODULE_SUMMARY.md missing"


# TC1.6
@pytest.mark.parametrize("module", MODULES)
def test_module_readme_tree_files_exist(module, module_dirs, skill_dir):
    readme_path = module_dirs[module] / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    expected_files = _extract_tree_md_files(text, module)
    missing = []
    for rel_path in expected_files:
        if not (skill_dir / rel_path).is_file():
            missing.append(rel_path)
    assert not missing, f"{module} README recommended files missing:\n" + "\n".join(missing)

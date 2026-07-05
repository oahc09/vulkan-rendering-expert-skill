"""pytest public fixtures for Vulkan rendering expert skill tests."""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SKILL_DIR = PROJECT_ROOT / "references"

MODULES = [
    "00_expert_entry",
    "01_source_map_and_api_manual_strategy",
    "02_core_mental_model",
    "03_api_manual",
    "04_debug_playbooks",
    "05_workflows",
    "06_cases",
    "07_integration_pack",
]


@pytest.fixture
def skill_dir():
    return SKILL_DIR


@pytest.fixture
def all_md_files():
    """Return all .md files under the packaged skill references."""
    return sorted(SKILL_DIR.rglob("*.md"))


@pytest.fixture
def module_dirs():
    return {m: SKILL_DIR / m for m in MODULES}

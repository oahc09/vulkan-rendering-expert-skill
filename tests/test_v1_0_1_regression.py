"""TC10: Vulkan 1.4 knowledge base regression tests.

These tests guard the v1.0.1 knowledge expansion:
  TC10.1 — Version baseline consistency across global declaration files
  TC10.2 — api_index.md bidirectional match (hardened version of TC7.1)
  TC10.3 — 02_core_mental_model new card content completeness
  TC10.4 — Vulkan 1.4 keyword coverage in new/updated cards
  TC10.5 — lifecycle_index.md tracks new lifecycle-bearing cards

Design principle: these tests skip gracefully when v1.0.1 has not yet
been executed (planning phase), and enforce strict checks once v1.0.1
content starts appearing. This allows the tests to be committed ahead
of card creation without breaking the build.
"""

import os
import re
from pathlib import Path

import pytest

from conftest import SKILL_DIR, MODULES

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_h2_titles(text: str):
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", text, re.M)]


def _extract_md_links(text: str):
    """Yield .md link targets (path part only, anchor stripped)."""
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+\.md(?:#[^)]+)?)\)", text):
        yield match.group(2).split("#")[0]


def _resolve(ref: str, base_dir: Path) -> Path:
    ref = ref.replace("/", os.sep)
    if Path(ref).is_absolute():
        return Path(ref)
    return (base_dir / ref).resolve()


_VULKAN_1_4_PATTERN = re.compile(r"Vulkan[\s\S]{0,30}?1\.4", re.I)


def _v1_0_1_started() -> bool:
    """Return True if v1.0.1 knowledge expansion has begun.

    Detected by the presence of any new card file or any global file
    mentioning Vulkan 1.4.
    """
    # Check for new card files.
    new_cards = [
        SKILL_DIR / "02_core_mental_model" / "vulkan_1_4_overview.md",
        SKILL_DIR / "03_api_manual" / "08_synchronization" / "timeline_semaphore.md",
        SKILL_DIR / "03_api_manual" / "05_descriptor" / "descriptor_indexing.md",
        SKILL_DIR / "03_api_manual" / "01_instance_device_queue" / "maintenance_extensions.md",
    ]
    if any(p.is_file() for p in new_cards):
        return True
    # Check whether any global declaration file already mentions 1.4.
    global_files = [
        SKILL_DIR / "00_expert_entry" / "role.md",
        SKILL_DIR / "02_core_mental_model" / "modern_patterns.md",
    ]
    for p in global_files:
        if p.is_file() and _VULKAN_1_4_PATTERN.search(_read(p)):
            return True
    return False


# ---------------------------------------------------------------------------
# TC10.1 Version baseline consistency
# ---------------------------------------------------------------------------

VERSION_DECLARATION_FILES = [
    SKILL_DIR / "00_expert_entry" / "role.md",
    SKILL_DIR / "00_expert_entry" / "change_log.md",
    SKILL_DIR / "02_core_mental_model" / "modern_patterns.md",
    SKILL_DIR / "01_source_map_and_api_manual_strategy" / "update_policy.md",
    SKILL_DIR / "02_core_mental_model" / "synchronization_lifecycle.md",
]


def test_version_baseline_consistency():
    """All global declaration files should reference Vulkan 1.4 after v1.0.1.

    Skips if v1.0.1 has not started. Once started, every declaration file
    must mention Vulkan 1.4 — partial updates are not allowed.
    """
    if not _v1_0_1_started():
        pytest.skip("v1.0.1 not yet started — version baseline test deferred")

    missing = []
    for path in VERSION_DECLARATION_FILES:
        assert path.is_file(), f"Declaration file missing: {path}"
        text = _read(path)
        if not _VULKAN_1_4_PATTERN.search(text):
            missing.append(str(path.relative_to(SKILL_DIR)))
    assert not missing, (
        "Files not yet updated for Vulkan 1.4 baseline:\n"
        + "\n".join(missing)
    )


# ---------------------------------------------------------------------------
# TC10.2 api_index.md bidirectional match (hardened version of TC7.1)
# ---------------------------------------------------------------------------

_API_INDEX_EXCLUDED = {
    "README.md",
    "api_index.md",
    "lifecycle_index.md",
    "error_index.md",
    "api_card_writing_rules.md",
}


def _is_api_card(path: Path) -> bool:
    return (
        "template" not in path.name.lower()
        and path.name not in _API_INDEX_EXCLUDED
    )


def test_api_index_bidirectional_match():
    """api_index.md must list every API card, and every listed card must exist.

    Skips if v1.0.1 has not started. Once v1.0.1 adds new cards, the index
    must be complete in both directions.
    """
    if not _v1_0_1_started():
        pytest.skip("v1.0.1 not yet started — api_index bidirectional test deferred")

    api_index = SKILL_DIR / "03_api_manual" / "api_index.md"
    text = _read(api_index)

    # Extract all .md references: both markdown links [text](path) and
    # backtick-quoted paths in table cells like `dir/card.md`.
    all_refs = set()
    for ref in _extract_md_links(text):
        all_refs.add(ref)
    for match in re.finditer(r"`([^`]+\.md)`", text):
        ref = match.group(1)
        # Skip template placeholders and meta files.
        if "template" not in ref.lower() and ref not in _API_INDEX_EXCLUDED:
            all_refs.add(ref)

    # Forward: every link in index must resolve to a real file.
    broken = []
    indexed = set()
    for ref in all_refs:
        resolved = _resolve(ref, api_index.parent)
        if resolved.is_file():
            indexed.add(resolved)
        else:
            broken.append(ref)
    assert not broken, "api_index.md has broken references:\n" + "\n".join(broken[:50])

    # Reverse: every API card under 03_api_manual must be in the index.
    api_dir = SKILL_DIR / "03_api_manual"
    actual = {p.resolve() for p in api_dir.rglob("*.md") if _is_api_card(p)}
    not_indexed = actual - indexed
    assert not not_indexed, (
        "API cards not listed in api_index.md:\n"
        + "\n".join(str(p.relative_to(SKILL_DIR)) for p in sorted(not_indexed)[:20])
    )


# ---------------------------------------------------------------------------
# TC10.3 02_core_mental_model new card content completeness
# ---------------------------------------------------------------------------

EXPECTED_CORE_MENTAL_MODEL_NEW_CARDS = [
    "vulkan_1_4_overview.md",
    "render_graph_resource_lifetime.md",
]

MIN_SECTION_COUNT = 5


def test_core_mental_model_new_cards_completeness():
    """New v1.0.1 cards under 02_core_mental_model must have real content.

    Skips if none of the new cards exist yet. Once any card exists, all
    expected cards must exist and have sufficient content.
    """
    module_dir = SKILL_DIR / "02_core_mental_model"
    existing = [
        name for name in EXPECTED_CORE_MENTAL_MODEL_NEW_CARDS
        if (module_dir / name).is_file()
    ]
    if not existing:
        pytest.skip("v1.0.1 core_mental_model new cards not yet created")

    failures = []
    for card_name in EXPECTED_CORE_MENTAL_MODEL_NEW_CARDS:
        path = module_dir / card_name
        if not path.is_file():
            failures.append(f"{card_name}: file does not exist")
            continue
        text = _read(path)
        sections = _extract_h2_titles(text)
        if len(sections) < MIN_SECTION_COUNT:
            failures.append(
                f"{card_name}: only {len(sections)} H2 sections (need >= {MIN_SECTION_COUNT})"
            )
        if not re.search(r"\[([A-Z]{2,})\]", text):
            failures.append(f"{card_name}: no source tags found")
    assert not failures, "02_core_mental_model new card failures:\n" + "\n".join(failures)


# ---------------------------------------------------------------------------
# TC10.4 Vulkan 1.4 keyword coverage
# ---------------------------------------------------------------------------

VULKAN_1_4_KEYWORD_FILES = {
    "03_api_manual/08_synchronization/timeline_semaphore.md": [
        r"VkSemaphoreTypeCreateInfo",
        r"vkGetSemaphoreCounterValue",
        r"vkWaitSemaphores|vkSignalSemaphore",
    ],
    "03_api_manual/05_descriptor/descriptor_indexing.md": [
        r"VkPhysicalDeviceDescriptorIndexingFeatures",
        r"PARTIALLY_BOUND",
        r"UPDATE_AFTER_BIND",
    ],
    "03_api_manual/01_instance_device_queue/maintenance_extensions.md": [
        r"maintenance6",
        r"maintenance4",
        r"maintenance5",
    ],
    "02_core_mental_model/vulkan_1_4_overview.md": [
        r"maintenance6",
        r"push.?descriptor",
        r"scalar.?block.?layout|scalar_block_layout",
    ],
}

INCREMENTAL_1_4_CARDS = [
    "03_api_manual/07_rendering/dynamic_rendering.md",
    "03_api_manual/08_synchronization/synchronization2.md",
]


def test_vulkan_1_4_keyword_coverage():
    """New/incremental cards must actually contain Vulkan 1.4 content.

    Skips if no v1.0.1 new cards exist. Once any new card exists, all
    keyword files must be present and contain expected content, and all
    incremental cards must mention Vulkan 1.4.
    """
    # Determine whether any new keyword-file card exists.
    new_cards_exist = any(
        (SKILL_DIR / rel).is_file() for rel in VULKAN_1_4_KEYWORD_FILES
    )
    if not new_cards_exist:
        pytest.skip("v1.0.1 keyword target cards not yet created")

    missing_keywords = []

    for rel_path, patterns in VULKAN_1_4_KEYWORD_FILES.items():
        path = SKILL_DIR / rel_path
        if not path.is_file():
            missing_keywords.append(f"{rel_path}: file does not exist")
            continue
        text = _read(path)
        for pat in patterns:
            if not re.search(pat, text, re.I):
                missing_keywords.append(f"{rel_path}: missing '{pat}'")

    # Incremental cards must contain a 1.4 mention.
    for rel_path in INCREMENTAL_1_4_CARDS:
        path = SKILL_DIR / rel_path
        assert path.is_file(), f"Incremental card missing: {rel_path}"
        text = _read(path)
        if not _VULKAN_1_4_PATTERN.search(text):
            missing_keywords.append(f"{rel_path}: no Vulkan 1.4 mention")

    assert not missing_keywords, "Vulkan 1.4 keyword coverage failures:\n" + "\n".join(
        missing_keywords[:30]
    )


# ---------------------------------------------------------------------------
# TC10.5 lifecycle_index.md tracks new lifecycle-bearing cards
# ---------------------------------------------------------------------------

LIFECYCLE_NEW_CARDS = [
    "08_synchronization/timeline_semaphore.md",
    "03_command_buffer/frames_in_flight.md",
]


def test_lifecycle_index_tracks_new_cards():
    """lifecycle_index.md should reference new lifecycle-bearing cards.

    Skips if the new cards don't exist yet. Once they exist, they must
    be indexed in lifecycle_index.md.
    """
    lifecycle_index = SKILL_DIR / "03_api_manual" / "lifecycle_index.md"
    text = _read(lifecycle_index)

    not_created = []
    not_indexed = []

    for rel_path in LIFECYCLE_NEW_CARDS:
        card_path = SKILL_DIR / "03_api_manual" / rel_path
        if not card_path.is_file():
            not_created.append(rel_path)
            continue
        card_name = Path(rel_path).name
        if card_name not in text:
            not_indexed.append(rel_path)

    if not_created and not not_indexed:
        pytest.skip("Lifecycle new cards not yet created: " + ", ".join(not_created))

    assert not not_indexed, "New lifecycle cards not in lifecycle_index.md:\n" + "\n".join(
        not_indexed
    )

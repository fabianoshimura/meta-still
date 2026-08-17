"""Names that Windows will actually store under the name we ask for."""

from __future__ import annotations

import pytest

from meta_still.core.domain.naming import safe_name


def test_ordinary_names_are_untouched() -> None:
    assert safe_name("20260427_B3301") == "20260427_B3301"


def test_trailing_space_is_removed() -> None:
    """MultiCorder ends every filename with a space; Windows then lies about it."""
    assert safe_name("MultiCorder5 - Output 1 - 10 dezembro 2025 - 10-22-47 ") == (
        "MultiCorder5 - Output 1 - 10 dezembro 2025 - 10-22-47"
    )


def test_interior_spaces_are_kept() -> None:
    assert safe_name("Câmeras separadas") == "Câmeras separadas"


@pytest.mark.parametrize("name", ["clip.", "clip..", "clip . ", "clip ."])
def test_trailing_dots_are_removed_too(name: str) -> None:
    assert safe_name(name) == "clip"


@pytest.mark.parametrize("name", ["CON", "con", "NUL", "COM1", "LPT9"])
def test_reserved_device_names_are_escaped(name: str) -> None:
    assert safe_name(name) == f"{name}_"


def test_reserved_name_with_an_extension_is_still_reserved() -> None:
    assert safe_name("CON.backup") == "CON.backup_"


def test_illegal_characters_are_replaced() -> None:
    assert safe_name('clip:1?"') == "clip_1__"


@pytest.mark.parametrize("name", ["", "   ", "...", " . "])
def test_names_that_sanitise_to_nothing_get_a_fallback(name: str) -> None:
    assert safe_name(name) == "unnamed"

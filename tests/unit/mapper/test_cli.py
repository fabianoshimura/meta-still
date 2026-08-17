"""Prompt handling — the interfaces layer, tested without a terminal."""

from __future__ import annotations

import builtins
from collections.abc import Iterator

import pytest

from meta_still.mapper.interfaces.cli import ask


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch):
    def _use(*values: str) -> None:
        supply: Iterator[str] = iter(values)
        monkeypatch.setattr(builtins, "input", lambda _prompt="": next(supply))

    return _use


def test_plain_answer(answers) -> None:
    answers(r"D:\SHOOT_DAY_03")
    assert ask("Path") == r"D:\SHOOT_DAY_03"


def test_empty_answer_falls_back_to_default(answers) -> None:
    answers("")
    assert ask("Path", "map.txt") == "map.txt"


def test_strips_quotes_from_copy_as_path(answers) -> None:
    answers('"D:\\SHOOT DAY 03"')
    assert ask("Path") == r"D:\SHOOT DAY 03"


def test_strips_invisible_characters(answers) -> None:
    # U+202A is what the Windows Properties dialog prepends; U+FEFF is a BOM.
    answers("\u202a\ufeffD:\\SHOOT_DAY_03 ")
    assert ask("Path") == r"D:\SHOOT_DAY_03"

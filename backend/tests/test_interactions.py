"""Interaction tests driven by ``interactions.yml``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

chess = pytest.importorskip("chess")

from dialog import process_user_turn  # noqa: E402
from dm import _pick_first_legal_move  # noqa: E402
from nlu import normalize_text, parse_utterance, resolve_move  # noqa: E402

INTERACTIONS_PATH = Path(__file__).resolve().parent / "interactions.yml"


def _load_interactions() -> dict[str, Any]:
    with INTERACTIONS_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("interactions.yml must be a mapping of test names to specs")
    return data


def _board_from_state(state: dict[str, Any]) -> chess.Board:
    board = chess.Board()
    turn = state.get("turn", "white")
    if turn == "black":
        board.turn = chess.BLACK
    else:
        board.turn = chess.WHITE
    return board


def _parse_turn_line(line: str | dict[str, str]) -> tuple[str, str]:
    if isinstance(line, dict):
        if "U" in line:
            return "user", line["U"].strip()
        if "S" in line:
            return "system", line["S"].strip()
        raise ValueError(f"Turn dict must have U or S key, got: {line!r}")
    if line.startswith("U:"):
        return "user", line[2:].strip()
    if line.startswith("S:"):
        return "system", line[2:].strip()
    raise ValueError(f"Turn line must start with U: or S:, got: {line!r}")


def _move_selector_from_expected(expected_system: str):
    parsed = parse_utterance(expected_system)

    def select(board: chess.Board) -> chess.Move | None:
        if parsed is not None:
            move = resolve_move(board, parsed)
            if move is not None:
                return move
        return _pick_first_legal_move(board)

    return select


def _iter_turn_pairs(turns: list[str | dict[str, str]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(turns):
        role_u, utterance_u = _parse_turn_line(turns[i])
        if role_u != "user":
            raise ValueError(f"Expected user turn at index {i}, got {role_u}")
        if i + 1 >= len(turns):
            raise ValueError("User turn must be followed by a system turn")
        role_s, utterance_s = _parse_turn_line(turns[i + 1])
        if role_s != "system":
            raise ValueError(f"Expected system turn at index {i + 1}, got {role_s}")
        pairs.append((utterance_u, utterance_s))
        i += 2
    return pairs


def _run_interaction(name: str, spec: dict[str, Any]) -> None:
    state = spec.get("state", {})
    board = _board_from_state(state)
    context: dict[str, Any] = {"user_color": spec.get("user", "white")}

    for user_utterance, expected_system in _iter_turn_pairs(spec.get("turns", [])):
        ok = process_user_turn(
            user_utterance,
            board,
            context,
            move_selector=_move_selector_from_expected(expected_system),
        )
        assert ok, (
            f"{name}: dialog failed for {user_utterance!r}: {context.get('response')}"
        )
        actual_system = context["response"].get("system_move_nlg", "")
        assert normalize_text(actual_system) == normalize_text(expected_system), (
            f"{name}: expected system {expected_system!r}, got {actual_system!r}"
        )


_INTERACTIONS = _load_interactions()


@pytest.mark.parametrize(
    "name,spec",
    list(_INTERACTIONS.items()),
    ids=list(_INTERACTIONS.keys()),
)
def test_interaction(name: str, spec: dict[str, Any]) -> None:
    _run_interaction(name, spec)

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
    if "fen" in state:
        board = chess.Board(state["fen"])
    else:
        board = chess.Board()
    if "turn" in state:
        turn = state["turn"]
        board.turn = chess.BLACK if turn == "black" else chess.WHITE
    return board


def _parse_turn_line(line: str | dict[str, Any]) -> tuple[str, str]:
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


def _expects_no_turn(entry: str | dict[str, Any]) -> bool:
    if not isinstance(entry, dict):
        return False
    expect = entry.get("expect")
    return isinstance(expect, dict) and expect.get("no_turn") is True


def _move_selector_from_expected(expected_system: str):
    parsed = parse_utterance(expected_system)

    def select(board: chess.Board) -> chess.Move | None:
        if parsed is not None:
            move = resolve_move(board, parsed)
            if move is not None:
                return move
        return _pick_first_legal_move(board)

    return select


def _check_response(
    name: str,
    expected: str,
    board: chess.Board,
    fen_before: str,
    context: dict[str, Any],
) -> None:
    response = context["response"]
    actual = response.get("system_move_nlg", "")
    assert normalize_text(actual) == normalize_text(expected), (
        f"{name}: expected {expected!r}, got {actual!r}"
    )
    rtype = response.get("type")
    if rtype in ("confirmation", "info", "thinking", "color_choice"):
        assert board.fen() == fen_before, (
            f"{name}: board must be unchanged after {expected!r}"
        )
    elif rtype == "error":
        user_move_uci = response.get("user_move_uci")
        if user_move_uci:
            expected_board = chess.Board(fen_before)
            expected_board.push(chess.Move.from_uci(user_move_uci))
            assert board.fen() == expected_board.fen(), (
                f"{name}: board must reflect user move {user_move_uci!r} only"
            )
        else:
            assert board.fen() == fen_before, (
                f"{name}: board must be unchanged after {response.get('reason')}"
            )
    if rtype == "checkmate":
        assert context.get("game_over"), f"{name}: checkmate must end the game"


def _run_interaction(name: str, spec: dict[str, Any]) -> None:
    state = spec.get("state", {})
    board = _board_from_state(state)
    context: dict[str, Any] = {"game_started": spec.get("started", True)}
    if context["game_started"]:
        context["user_color"] = spec.get("user", "white")

    turns = spec.get("turns", [])
    i = 0
    while i < len(turns):
        entry = turns[i]
        if _expects_no_turn(entry):
            _, user_utterance = _parse_turn_line(entry)
            fen_before = board.fen()
            ok = process_user_turn(user_utterance, board, context)
            assert not ok, (
                f"{name}: user must not get a turn after game over for {user_utterance!r}"
            )
            assert context.get("game_over"), f"{name}: game_over must be set"
            assert context["response"].get("reason") == "game_over"
            assert board.fen() == fen_before, (
                f"{name}: board must be unchanged when turn is rejected"
            )
            i += 1
            continue

        role_u, user_utterance = _parse_turn_line(entry)
        assert role_u == "user", f"{name}: expected user turn at index {i}"

        sys_texts: list[str] = []
        j = i + 1
        while j < len(turns):
            role, text = _parse_turn_line(turns[j])
            if role != "system":
                break
            sys_texts.append(text)
            j += 1
        assert sys_texts, f"{name}: user turn must be followed by a system turn"

        fen_before = board.fen()
        ok = process_user_turn(
            user_utterance,
            board,
            context,
            move_selector=_move_selector_from_expected(sys_texts[0]),
        )
        assert ok, (
            f"{name}: dialog failed for {user_utterance!r}: {context.get('response')}"
        )
        _check_response(name, sys_texts[0], board, fen_before, context)

        for sys_text in sys_texts[1:]:
            fen_before = board.fen()
            ok = process_user_turn(
                "",
                board,
                context,
                move_selector=_move_selector_from_expected(sys_text),
            )
            assert ok, (
                f"{name}: dialog continuation failed: {context.get('response')}"
            )
            _check_response(name, sys_text, board, fen_before, context)

        i = j


_INTERACTIONS = _load_interactions()


@pytest.mark.parametrize(
    "name,spec",
    list(_INTERACTIONS.items()),
    ids=list(_INTERACTIONS.keys()),
)
def test_interaction(name: str, spec: dict[str, Any]) -> None:
    _run_interaction(name, spec)

"""Unit tests for dialog manager turn handling."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from dm import handle_turn  # noqa: E402

chess = pytest.importorskip("chess")


def test_handle_turn_success_user_and_system_move() -> None:
    board = chess.Board()
    interpretation = {"intent": "move_piece", "arguments": {"from": "e2", "to": "e4"}}
    context: dict = {}

    def selector(current_board: chess.Board) -> chess.Move | None:
        move = chess.Move.from_uci("e7e5")
        return move if move in current_board.legal_moves else None

    ok = handle_turn(interpretation, board, context, move_selector=selector)

    assert ok is True
    assert board.fullmove_number == 2
    assert board.turn == chess.WHITE
    assert board.peek().uci() == "e7e5"
    assert context["response"] == {
        "type": "move",
        "user_move_uci": "e2e4",
        "system_move_uci": "e7e5",
        "system_move_nlg": None,
    }


def test_handle_turn_invalid_or_ambiguous_user_move() -> None:
    board = chess.Board()
    interpretation = {
        "intent": "move_piece",
        "arguments": {"to": "e4"},
    }  # Ambiguous in initial position.
    context: dict = {}

    ok = handle_turn(interpretation, board, context)

    assert ok is False
    assert board.fen() == chess.Board().fen()
    assert context["response"]["type"] == "error"
    assert context["response"]["reason"] == "invalid_or_ambiguous_user_move"


def test_handle_turn_none_interpretation() -> None:
    board = chess.Board()
    context: dict = {}

    ok = handle_turn(None, board, context)

    assert ok is False
    assert context["response"] == {"type": "error", "reason": "no_interpretation"}


def test_handle_turn_no_legal_system_move() -> None:
    board = chess.Board("7k/7Q/7K/8/8/8/8/8 b - - 0 1")
    interpretation = {"intent": "move_piece", "arguments": {"from": "h7", "to": "g7"}}
    context: dict = {}

    ok = handle_turn(interpretation, board, context, move_selector=lambda _: None)

    assert ok is False
    assert context["response"]["type"] == "error"
    assert context["response"]["reason"] == "no_legal_system_move"

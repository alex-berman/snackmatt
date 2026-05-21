"""Unit tests for dialog manager turn handling."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

chess = pytest.importorskip("chess")

from dm import handle_turn  # noqa: E402


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


def _board_with_two_pawns_to_e4() -> chess.Board:
    """Two white pawns can reach e4 — ``to`` alone is ambiguous."""
    board = chess.Board.empty()
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.D3, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.F3, chess.Piece(chess.PAWN, chess.WHITE))
    board.turn = chess.WHITE
    return board


def test_handle_turn_invalid_or_ambiguous_user_move() -> None:
    board = _board_with_two_pawns_to_e4()
    interpretation = {
        "intent": "move_piece",
        "arguments": {"to": "e4"},
    }  # Ambiguous: d3-e4 and f3-e4 are both legal.
    context: dict = {}

    ok = handle_turn(interpretation, board, context)

    assert ok is False
    assert board.fen() == _board_with_two_pawns_to_e4().fen()
    assert context["response"]["type"] == "error"
    assert context["response"]["reason"] == "invalid_or_ambiguous_user_move"


def test_handle_turn_none_interpretation() -> None:
    board = chess.Board()
    context: dict = {}

    ok = handle_turn(None, board, context)

    assert ok is False
    assert context["response"] == {"type": "error", "reason": "no_interpretation"}


def test_handle_turn_checkmate_after_user_move() -> None:
    board = chess.Board("7k/5R2/6K1/8/8/8/8/8 w - - 0 1")
    interpretation = {"intent": "move_piece", "arguments": {"from": "f7", "to": "f8"}}
    context: dict = {}

    ok = handle_turn(interpretation, board, context, move_selector=lambda _: None)

    assert ok is True
    assert context["game_over"] is True
    assert context["response"] == {
        "type": "checkmate",
        "user_move_uci": "f7f8",
    }
    assert board.is_checkmate()
    assert board.peek().uci() == "f7f8"

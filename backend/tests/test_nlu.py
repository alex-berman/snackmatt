"""Unit tests for rule-based Swedish chess NLU."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from nlu import normalize_text, parse_utterance, resolve_capture, resolve_move  # noqa: E402

chess = pytest.importorskip("chess")


def squares_are_valid(from_sq: str | None, to_sq: str | None) -> None:
    if from_sq is not None:
        chess.parse_square(from_sq)
    if to_sq is not None:
        chess.parse_square(to_sq)


@pytest.mark.parametrize(
    "utterance,expected",
    [
        (
            "flytta bonden från e2 till e4",
            {
                "intent": "move_piece",
                "arguments": {"from": "e2", "to": "e4", "piece": "pawn"},
            },
        ),
        (
            "Flytta bonden från E2 till E4",
            {
                "intent": "move_piece",
                "arguments": {"from": "e2", "to": "e4", "piece": "pawn"},
            },
        ),
        (
            "e2 till e4",
            {"intent": "move_piece", "arguments": {"from": "e2", "to": "e4"}},
        ),
        (
            "från e2 till e4",
            {"intent": "move_piece", "arguments": {"from": "e2", "to": "e4"}},
        ),
        (
            "gå från g1 till f3",
            {"intent": "move_piece", "arguments": {"from": "g1", "to": "f3"}},
        ),
        (
            "flytta hästen från g1 till f3",
            {
                "intent": "move_piece",
                "arguments": {"from": "g1", "to": "f3", "piece": "knight"},
            },
        ),
        (
            "springaren från b1 till c3",
            {
                "intent": "move_piece",
                "arguments": {"from": "b1", "to": "c3", "piece": "knight"},
            },
        ),
        (
            "löparen från c1 till f4",
            {
                "intent": "move_piece",
                "arguments": {"from": "c1", "to": "f4", "piece": "bishop"},
            },
        ),
        (
            "flytta tornet från a1 till a8",
            {
                "intent": "move_piece",
                "arguments": {"from": "a1", "to": "a8", "piece": "rook"},
            },
        ),
        (
            "drottningen från d1 till h5",
            {
                "intent": "move_piece",
                "arguments": {"from": "d1", "to": "h5", "piece": "queen"},
            },
        ),
        (
            "kungen från e1 till e2",
            {
                "intent": "move_piece",
                "arguments": {"from": "e1", "to": "e2", "piece": "king"},
            },
        ),
        (
            "flytta från e två till e fyra",
            {
                "intent": "move_piece",
                "arguments": {"from": "e2", "to": "e4"},
            },
        ),
        (
            "e två till e fyra",
            {"intent": "move_piece", "arguments": {"from": "e2", "to": "e4"}},
        ),
        (
            "häst till f3",
            {"intent": "move_piece", "arguments": {"to": "f3", "piece": "knight"}},
        ),
        (
            "flytta till c6",
            {"intent": "move_piece", "arguments": {"to": "c6"}},
        ),
        (
            "rockera kort",
            {"intent": "castle", "arguments": {"side": "kingside"}},
        ),
        (
            "rockera långt",
            {"intent": "castle", "arguments": {"side": "queenside"}},
        ),
        (
            "jag ger upp",
            {"intent": "resign", "arguments": {}},
        ),
        (
            "erbjud remi",
            {"intent": "offer_draw", "arguments": {}},
        ),
        (
            "jag slår din bonde på e4 med min bonde",
            {
                "intent": "capture_piece",
                "arguments": {
                    "to": "e4",
                    "victim_piece": "pawn",
                    "piece": "pawn",
                },
            },
        ),
        (
            "slår bonden på e4",
            {
                "intent": "capture_piece",
                "arguments": {"to": "e4", "victim_piece": "pawn"},
            },
        ),
        (
            "ta hästen på f3",
            {
                "intent": "capture_piece",
                "arguments": {"to": "f3", "victim_piece": "knight"},
            },
        ),
        (
            "slår e4",
            {"intent": "capture_piece", "arguments": {"to": "e4"}},
        ),
    ],
)
def test_parse_utterance(utterance: str, expected: dict) -> None:
    result = parse_utterance(utterance)
    assert result == expected
    args = expected.get("arguments", {})
    squares_are_valid(args.get("from"), args.get("to"))


@pytest.mark.parametrize(
    "utterance",
    [
        "",
        "   ",
        "hej hur mår du",
        "jag vill spela schack",
        "flytta bonden",
        "från z9",
    ],
)
def test_parse_utterance_unknown(utterance: str) -> None:
    assert parse_utterance(utterance) is None


def test_normalize_text_strips_punctuation() -> None:
    assert normalize_text("  Flytta! bonden, från e2…  ") == "flytta bonden fran e2"


def test_move_to_chess_move() -> None:
    """Square names from NLU plug directly into python-chess."""
    parsed = parse_utterance("flytta bonden från e2 till e4")
    assert parsed is not None
    args = parsed["arguments"]
    move = chess.Move(
        chess.parse_square(args["from"]),
        chess.parse_square(args["to"]),
    )
    assert move.uci() == "e2e4"


def _pawn_capture_board() -> chess.Board:
    board = chess.Board.empty()
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.H8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.D3, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.E4, chess.Piece(chess.PAWN, chess.BLACK))
    board.turn = chess.WHITE
    return board


def test_resolve_capture_from_nlu() -> None:
    board = _pawn_capture_board()
    parsed = parse_utterance("jag slår din bonde på e4 med min bonde")
    assert parsed is not None
    move = resolve_capture(board, parsed["arguments"])
    assert move is not None
    assert move.uci() == "d3e4"
    assert board.is_legal(move)


def test_resolve_capture_ambiguous_returns_none() -> None:
    """Two pawns can capture on c3 — resolver refuses to guess."""
    board = chess.Board.empty()
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.H8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.B4, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.D4, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.C3, chess.Piece(chess.PAWN, chess.BLACK))
    board.turn = chess.WHITE
    parsed = parse_utterance("slår på c3")
    assert parsed is not None
    assert resolve_capture(board, parsed["arguments"]) is None


def test_resolve_move_dispatcher() -> None:
    board = chess.Board()
    parsed = parse_utterance("flytta bonden från e2 till e4")
    assert parsed is not None
    move = resolve_move(board, parsed)
    assert move is not None
    assert move.uci() == "e2e4"


def test_resolve_move_capture_when_opponent_on_target() -> None:
    """'move_piece' intent to a square with an opponent piece yields a capture."""
    board = chess.Board.empty()
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.E4, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.D5, chess.Piece(chess.PAWN, chess.BLACK))
    board.turn = chess.WHITE

    parsed: dict = {
        "intent": "move_piece",
        "arguments": {"from": "e4", "to": "d5"},
    }
    move = resolve_move(board, parsed)
    assert move is not None
    assert move.uci() == "e4d5"
    assert board.is_legal(move)


def test_resolve_move_rejects_capture_to_empty_square() -> None:
    """'move_piece' to an empty square must not match a capture."""
    board = chess.Board.empty()
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.E4, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.D5, chess.Piece(chess.PAWN, chess.BLACK))
    board.turn = chess.WHITE

    # Moving to an empty square — should resolve as a normal move
    parsed: dict = {
        "intent": "move_piece",
        "arguments": {"from": "e4", "to": "e5"},
    }
    move = resolve_move(board, parsed)
    assert move is not None
    assert move.uci() == "e4e5"
    assert not board.is_capture(move)

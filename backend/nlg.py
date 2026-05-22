"""Rule-based NLG for Swedish chess move announcements and dialog errors."""

from __future__ import annotations

from typing import Any

import chess

_ERROR_UTTERANCES: dict[str, str] = {
    "no_interpretation": "Jag förstår inte.",
    "invalid_or_ambiguous_user_move": "Det verkar vara ett otillåtet drag.",
    "no_legal_system_move": "Jag har inget lagligt drag.",
}

CHECKMATE_UTTERANCE = "Det är schackmatt."

THINKING_UTTERANCE = "Okej, då ska vi se."

_PIECE_TYPE_TO_SWEDISH: dict[int, str] = {
    chess.PAWN: "bonde",
    chess.KNIGHT: "häst",
    chess.BISHOP: "löpare",
    chess.ROOK: "torn",
    chess.QUEEN: "dam",
    chess.KING: "kung",
}

_PIECE_TYPE_TO_SWEDISH_DEFINITE: dict[int, str] = {
    chess.PAWN: "bonden",
    chess.KNIGHT: "hästen",
    chess.BISHOP: "löparen",
    chess.ROOK: "tornet",
    chess.QUEEN: "drottningen",
    chess.KING: "kungen",
}


def generate_move_utterance(move: chess.Move, board: chess.Board | None = None) -> str:
    """Speak a plain/capture move as Swedish text."""
    from_sq = chess.square_name(move.from_square).upper()
    to_sq = chess.square_name(move.to_square).upper()

    if board is not None:
        try:
            board.pop()
        except IndexError:
            pass
        else:
            if board.is_capture(move):
                attacker = board.piece_at(move.from_square)
                victim = board.piece_at(move.to_square)
                board.push(move)
                if attacker is not None and victim is not None:
                    an = _get_swedish_piece_name(attacker.piece_type, definite=False)
                    vn = _get_swedish_piece_name(victim.piece_type, definite=False)
                    return f"Jag tar din {vn} på {to_sq} med min {an} på {from_sq}."
                return f"Jag flyttar {from_sq} till {to_sq}."

            piece = board.piece_at(move.from_square)
            board.push(move)
            if piece is not None:
                pn = _get_swedish_piece_name(piece.piece_type, definite=True)
                return f"Jag flyttar {pn} från {from_sq} till {to_sq}."
            return f"Jag flyttar {from_sq} till {to_sq}."

    return f"Jag flyttar {from_sq} till {to_sq}."


def generate_checkmate_utterance() -> str:
    return CHECKMATE_UTTERANCE


def generate_error_utterance(reason: str) -> str:
    """Map a DM error reason to a spoken Swedish reply."""
    try:
        return _ERROR_UTTERANCES[reason]
    except KeyError as exc:
        raise ValueError(f"Unknown error reason for NLG: {reason!r}") from exc


def generate_rejection_ack() -> str:
    return "Okej"


def _get_swedish_piece_name(piece_type: int, definite: bool = False) -> str:
    mapping = _PIECE_TYPE_TO_SWEDISH_DEFINITE if definite else _PIECE_TYPE_TO_SWEDISH
    return mapping.get(piece_type, "")


def generate_confirmation_prompt(
    board: chess.Board,
    interpretation: dict[str, Any],
    resolved_move: chess.Move,
) -> str:
    intent = interpretation.get("intent")
    from_sq = chess.square_name(resolved_move.from_square).upper()
    to_sq = chess.square_name(resolved_move.to_square).upper()

    piece = board.piece_at(resolved_move.from_square)
    piece_type = piece.piece_type if piece is not None else None

    is_capture = board.is_capture(resolved_move)

    if intent == "capture_piece" or is_capture:
        if intent == "capture_piece":
            args = interpretation.get("arguments", {})
            from nlu import _PIECE_TYPE
            victim_type = _PIECE_TYPE.get(args.get("victim_piece", ""))
            attacker_type = _PIECE_TYPE.get(args.get("piece", ""))
            if victim_type is None and piece_type is not None:
                captured = board.piece_at(resolved_move.to_square)
                if captured is not None:
                    victim_type = captured.piece_type
            if attacker_type is None:
                attacker_type = piece_type
        else:
            victim = board.piece_at(resolved_move.to_square)
            victim_type = victim.piece_type if victim is not None else None
            attacker_type = piece_type

        victim_name = _get_swedish_piece_name(victim_type, definite=False) if victim_type else ""
        attacker_name = _get_swedish_piece_name(attacker_type, definite=False) if attacker_type else ""

        return (
            f"Okej, du tar min {victim_name} på {to_sq}"
            f" med din {attacker_name} på {from_sq}, stämmer det?"
        )

    piece_name = _get_swedish_piece_name(piece_type, definite=True) if piece_type else ""
    return f"Okej, {piece_name} från {from_sq} till {to_sq}, stämmer det?"

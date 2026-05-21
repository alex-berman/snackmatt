"""Rule-based NLG for Swedish chess move announcements and dialog errors."""

from __future__ import annotations

import chess

_ERROR_UTTERANCES: dict[str, str] = {
    "no_interpretation": "Jag förstår inte.",
    "invalid_or_ambiguous_user_move": "Det verkar vara ett otillåtet drag.",
    "no_legal_system_move": "Jag har inget lagligt drag.",
}

CHECKMATE_UTTERANCE = "Det är schackmatt."


def generate_move_utterance(move: chess.Move) -> str:
    """Speak a plain move as Swedish text (e.g. ``Jag flyttar E7 till E5.``)."""
    from_sq = chess.square_name(move.from_square).upper()
    to_sq = chess.square_name(move.to_square).upper()
    return f"Jag flyttar {from_sq} till {to_sq}."


def generate_checkmate_utterance() -> str:
    return CHECKMATE_UTTERANCE


def generate_error_utterance(reason: str) -> str:
    """Map a DM error reason to a spoken Swedish reply."""
    try:
        return _ERROR_UTTERANCES[reason]
    except KeyError as exc:
        raise ValueError(f"Unknown error reason for NLG: {reason!r}") from exc

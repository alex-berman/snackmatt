"""Rule-based NLG for Swedish chess move announcements."""

from __future__ import annotations

import chess


def generate_move_utterance(move: chess.Move) -> str:
    """Speak a plain move as Swedish text (e.g. ``Jag flyttar E7 till E5.``)."""
    from_sq = chess.square_name(move.from_square).upper()
    to_sq = chess.square_name(move.to_square).upper()
    return f"Jag flyttar {from_sq} till {to_sq}."

"""Dialog pipeline: NLU → DM → NLG for one user turn."""

from __future__ import annotations

from typing import Any

import chess

from dm import MoveSelector, handle_turn
from nlg import generate_move_utterance
from nlu import parse_utterance


def process_user_turn(
    utterance: str,
    board: chess.Board,
    dialog_context: dict[str, Any],
    move_selector: MoveSelector | None = None,
) -> bool:
    """
    Parse *utterance*, apply user and system moves on *board*, and fill
    ``dialog_context["response"]`` including ``system_move_nlg`` on success.
    """
    interpretation = parse_utterance(utterance)
    ok = handle_turn(
        interpretation,
        board,
        dialog_context,
        move_selector=move_selector,
    )
    if not ok:
        return False

    response = dialog_context.get("response", {})
    if response.get("type") != "move":
        return False

    system_uci = response.get("system_move_uci")
    if not system_uci:
        return False

    response["system_move_nlg"] = generate_move_utterance(
        chess.Move.from_uci(system_uci)
    )
    return True

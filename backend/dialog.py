"""Dialog pipeline: NLU → DM → NLG for one user turn."""

from __future__ import annotations

from typing import Any

import chess

from dm import MoveSelector, handle_turn
from nlg import (
    generate_checkmate_utterance,
    generate_error_utterance,
    generate_move_utterance,
)
from nlu import parse_utterance


def process_user_turn(
    utterance: str,
    board: chess.Board,
    dialog_context: dict[str, Any],
    move_selector: MoveSelector | None = None,
) -> bool:
    """
    Parse *utterance*, run the DM, and set ``system_move_nlg`` on the response.

    Returns ``True`` when the system can reply (move, error, or checkmate message).
    Returns ``False`` when the game is over and no further user turns are accepted.
    """
    if dialog_context.get("game_over"):
        dialog_context["response"] = {"type": "error", "reason": "game_over"}
        return False

    interpretation = parse_utterance(utterance)
    ok = handle_turn(
        interpretation,
        board,
        dialog_context,
        move_selector=move_selector,
    )

    response = dialog_context.get("response", {})

    if ok and response.get("type") == "checkmate":
        response["system_move_nlg"] = generate_checkmate_utterance()
        return True

    if not ok and response.get("type") == "error":
        reason = response.get("reason")
        if isinstance(reason, str):
            response["system_move_nlg"] = generate_error_utterance(reason)
            return True
        return False

    if not ok:
        return False

    if response.get("type") != "move":
        return False

    system_uci = response.get("system_move_uci")
    if not system_uci:
        return False

    response["system_move_nlg"] = generate_move_utterance(
        chess.Move.from_uci(system_uci)
    )
    return True

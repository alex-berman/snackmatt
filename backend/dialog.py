"""Dialog pipeline: NLU → DM → NLG for one user turn."""

from __future__ import annotations

from typing import Any

import chess

from dm import MoveSelector, handle_turn
from nlg import (
    generate_checkmate_utterance,
    generate_confirmation_prompt,
    generate_error_utterance,
    generate_move_utterance,
    generate_rejection_ack,
)
from nlu import parse_utterance, resolve_move


def _execute_and_respond(
    interpretation: dict[str, Any],
    board: chess.Board,
    dialog_context: dict[str, Any],
    move_selector: MoveSelector | None = None,
) -> bool:
    """Execute a (pending) interpretation via handle_turn and fill in NLG."""
    ok = handle_turn(interpretation, board, dialog_context, move_selector=move_selector)
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

    if interpretation is not None and interpretation["intent"] == "affirm":
        pending = dialog_context.get("pending_interpretation")
        if pending is None:
            dialog_context["response"] = {
                "type": "error",
                "reason": "no_interpretation",
            }
            dialog_context["response"]["system_move_nlg"] = generate_error_utterance(
                "no_interpretation"
            )
            return True
        dialog_context.pop("pending_interpretation", None)
        return _execute_and_respond(pending, board, dialog_context, move_selector)

    if interpretation is not None and interpretation["intent"] == "deny":
        dialog_context.pop("pending_interpretation", None)
        dialog_context["response"] = {
            "type": "info",
            "system_move_nlg": generate_rejection_ack(),
        }
        return True

    if interpretation is not None and interpretation["intent"] in (
        "move_piece",
        "capture_piece",
    ):
        user_move = resolve_move(board, interpretation)
        if user_move is None or not board.is_legal(user_move):
            dialog_context["response"] = {
                "type": "error",
                "reason": "invalid_or_ambiguous_user_move",
                "interpretation": interpretation,
            }
            dialog_context["response"]["system_move_nlg"] = generate_error_utterance(
                "invalid_or_ambiguous_user_move"
            )
            return True

        dialog_context["pending_interpretation"] = interpretation
        dialog_context["response"] = {
            "type": "confirmation",
            "user_move_uci": user_move.uci(),
            "system_move_nlg": generate_confirmation_prompt(
                board, interpretation, user_move
            ),
        }
        return True

    dialog_context["response"] = {
        "type": "error",
        "reason": "no_interpretation",
    }
    dialog_context["response"]["system_move_nlg"] = generate_error_utterance(
        "no_interpretation"
    )
    return True

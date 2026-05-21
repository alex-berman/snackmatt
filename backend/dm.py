"""Dialog manager for chess turn handling."""

from __future__ import annotations

from typing import Any, Callable

import chess

from nlu import resolve_move

MoveSelector = Callable[[chess.Board], chess.Move | None]


def _pick_first_legal_move(board: chess.Board) -> chess.Move | None:
    """Baseline system policy until a stronger move generator is added."""
    for move in board.legal_moves:
        return move
    return None


def handle_turn(
    interpretation: dict[str, Any] | None,
    board: chess.Board,
    dialog_context: dict[str, Any],
    move_selector: MoveSelector | None = None,
) -> bool:
    """
    Apply one DM turn for user move followed by system move.

    The result is written to ``dialog_context["response"]`` as a JSON-serializable
    dict. Returns ``True`` only when both moves were successfully applied.
    """
    if interpretation is None:
        dialog_context["response"] = {
            "type": "error",
            "reason": "no_interpretation",
        }
        return False

    user_move = resolve_move(board, interpretation)
    if user_move is None or not board.is_legal(user_move):
        dialog_context["response"] = {
            "type": "error",
            "reason": "invalid_or_ambiguous_user_move",
            "interpretation": interpretation,
        }
        return False

    board.push(user_move)

    if board.is_checkmate():
        dialog_context["game_over"] = True
        dialog_context["response"] = {
            "type": "checkmate",
            "user_move_uci": user_move.uci(),
        }
        return True

    select_move = move_selector or _pick_first_legal_move
    system_move = select_move(board)

    if system_move is None or not board.is_legal(system_move):
        dialog_context["response"] = {
            "type": "error",
            "reason": "no_legal_system_move",
            "user_move_uci": user_move.uci(),
        }
        return False

    board.push(system_move)

    if board.is_checkmate():
        dialog_context["game_over"] = True
        dialog_context["response"] = {
            "type": "checkmate",
            "user_move_uci": user_move.uci(),
            "system_move_uci": system_move.uci(),
        }
        return True

    dialog_context["response"] = {
        "type": "move",
        "user_move_uci": user_move.uci(),
        "system_move_uci": system_move.uci(),
        "system_move_nlg": None,
    }
    return True

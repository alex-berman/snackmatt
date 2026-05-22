"""Dialog manager for chess turn handling."""

from __future__ import annotations

from typing import Any, Callable

import chess

from nlu import resolve_move

try:
    from engine import get_move as _engine_get_move
except ImportError:
    _engine_get_move = None

MoveSelector = Callable[[chess.Board], chess.Move | None]


def _pick_first_legal_move(board: chess.Board) -> chess.Move | None:
    """Fallback move selector when the engine is unavailable."""
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
        reason = "invalid_user_move"
        if user_move is None:
            args = interpretation.get("arguments", {})
            to_sq_str = args.get("to")
            from_sq_str = args.get("from")
            if to_sq_str and not from_sq_str:
                to_sq = chess.parse_square(to_sq_str)
                matches = sum(1 for m in board.legal_moves if m.to_square == to_sq)
                if matches > 1:
                    reason = "ambiguous_user_move"
        dialog_context["response"] = {
            "type": "error",
            "reason": reason,
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

    if move_selector is not None:
        select_move = move_selector
    elif _engine_get_move is not None:
        select_move = lambda b: _engine_get_move(b) or _pick_first_legal_move(b)
    else:
        select_move = _pick_first_legal_move
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

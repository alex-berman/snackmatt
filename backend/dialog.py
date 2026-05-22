"""Dialog pipeline: NLU → DM → NLG for one user turn."""

from __future__ import annotations

from typing import Any

import chess

from dm import MoveSelector, _pick_first_legal_move, handle_turn
from nlg import (
    COLOR_CHOICE_PROMPT,
    THINKING_UTTERANCE,
    generate_checkmate_utterance,
    generate_color_confirmation,
    generate_confirmation_prompt,
    generate_error_utterance,
    generate_move_utterance,
    generate_rejection_ack,
)
from nlu import normalize_text, parse_utterance, resolve_move


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
        chess.Move.from_uci(system_uci), board
    )
    return True


def _select_system_move(
    board: chess.Board,
    move_selector: MoveSelector | None = None,
) -> chess.Move | None:
    if move_selector is not None:
        return move_selector(board)
    try:
        from engine import get_move as _engine_get_move
    except ImportError:
        _engine_get_move = None
    if _engine_get_move is not None:
        return _engine_get_move(board) or _pick_first_legal_move(board)
    return _pick_first_legal_move(board)


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

    if not dialog_context.get("game_started"):
        if dialog_context.get("awaiting_color"):
            normalized = normalize_text(utterance)
            if normalized in ("vit", "svart"):
                choice = normalized
            elif normalized == "lotta":
                import random
                choice = random.choice(["vit", "svart"])
            else:
                dialog_context["response"] = {
                    "type": "error",
                    "reason": "no_interpretation",
                }
                dialog_context["response"]["system_move_nlg"] = generate_error_utterance(
                    "no_interpretation"
                )
                return True

            dialog_context["user_color"] = choice
            dialog_context["game_started"] = True
            dialog_context.pop("awaiting_color", None)
            board.reset()
            if choice == "svart":
                dialog_context["keep_system_turn"] = True
                dialog_context["_system_opening_move"] = True
            dialog_context["response"] = {
                "type": "info",
                "system_move_nlg": generate_color_confirmation(choice),
            }
            return True

        interpretation = parse_utterance(utterance)
        if interpretation is not None and interpretation["intent"] == "start_game":
            dialog_context["awaiting_color"] = True
            dialog_context["response"] = {
                "type": "color_choice",
                "system_move_nlg": COLOR_CHOICE_PROMPT,
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

    if not utterance:
        if dialog_context.get("_system_opening_move"):
            dialog_context.pop("_system_opening_move", None)
            dialog_context.pop("keep_system_turn", None)
            system_move = _select_system_move(board, move_selector)
            if system_move is not None and board.is_legal(system_move):
                board.push(system_move)
                dialog_context["response"] = {
                    "type": "move",
                    "system_move_uci": system_move.uci(),
                    "system_move_nlg": generate_move_utterance(system_move, board),
                }
                return True
            dialog_context["response"] = {
                "type": "error",
                "reason": "no_legal_system_move",
            }
            dialog_context["response"]["system_move_nlg"] = generate_error_utterance(
                "no_legal_system_move"
            )
            return True

        pending = dialog_context.get("pending_interpretation")
        if pending and dialog_context.get("keep_system_turn"):
            dialog_context.pop("keep_system_turn", None)
            dialog_context.pop("pending_interpretation", None)
            return _execute_and_respond(pending, board, dialog_context, move_selector)
        dialog_context["response"] = {
            "type": "error",
            "reason": "no_interpretation",
        }
        dialog_context["response"]["system_move_nlg"] = generate_error_utterance(
            "no_interpretation"
        )
        return True

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
        if not dialog_context.get("keep_system_turn"):
            dialog_context["keep_system_turn"] = True
            dialog_context["response"] = {
                "type": "thinking",
                "system_move_nlg": THINKING_UTTERANCE,
            }
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

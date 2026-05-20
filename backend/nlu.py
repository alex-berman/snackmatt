"""Rule-based NLU for Swedish chess voice commands.

Interpretations are plain dicts suitable for JSON serialization. Square
coordinates use lowercase algebraic names (``a1``–``h8``), compatible with
``chess.parse_square()`` from python-chess.

The NLU layer only extracts what was *said*. Resolving a unique move (e.g.
which pawn captures on ``e4``) requires board context — see
``resolve_capture`` and ``resolve_move``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import chess

# Spoken or written rank → digit
_RANK_WORDS: dict[str, str] = {
    "ett": "1",
    "en": "1",
    "två": "2",
    "tva": "2",
    "tre": "3",
    "fyra": "4",
    "fem": "5",
    "sex": "6",
    "sju": "7",
    "åtta": "8",
    "atta": "8",
}

# Swedish piece names → python-chess piece names (PAWN, KNIGHT, …)
_PIECE_ALIASES: dict[str, str] = {
    "bonde": "pawn",
    "bonden": "pawn",
    "bönder": "pawn",
    "bonder": "pawn",
    "häst": "knight",
    "hast": "knight",
    "hästen": "knight",
    "hasten": "knight",
    "springare": "knight",
    "springaren": "knight",
    "löpare": "bishop",
    "lopare": "bishop",
    "löparen": "bishop",
    "loparen": "bishop",
    "torn": "rook",
    "tornet": "rook",
    "drottning": "queen",
    "drottningen": "queen",
    "dam": "queen",
    "dammen": "queen",
    "kung": "king",
    "kungen": "king",
}

_VALID_SQUARE = re.compile(r"^[a-h][1-8]$")

def _square_pattern(prefix: str) -> str:
    """Regex for one square; group names are prefixed (``from_file``, ``to_rank_word``, …)."""
    return (
        rf"(?P<{prefix}_file>[a-h])\s*"
        rf"(?:(?P<{prefix}_rank_digit>[1-8])|"
        rf"(?P<{prefix}_rank_word>ett|en|två|tva|tre|fyra|fem|sex|sju|åtta|atta))"
    )


_MOVE_FROM_TO = re.compile(
    rf"(?:från|fran)\s+{_square_pattern('from')}\s+till\s+{_square_pattern('to')}",
    re.IGNORECASE,
)

_MOVE_SQUARE_TILL = re.compile(
    rf"{_square_pattern('from')}\s+till\s+{_square_pattern('to')}",
    re.IGNORECASE,
)

_MOVE_TO_ONLY = re.compile(
    rf"(?:till|flytta\s+till|gå\s+till|ga\s+till)\s+{_square_pattern('to')}\b",
    re.IGNORECASE,
)

_CASTLE = re.compile(
    r"\b(?:rockera|rochera)\s+(?P<side>kort|långt?|langt?|kungs|dam)\b",
    re.IGNORECASE,
)

_RESIGN = re.compile(
    r"\b(?:jag\s+)?(?:ger|ge)\s+upp\b",
    re.IGNORECASE,
)

_DRAW = re.compile(
    r"\b(?:erbjud\s+)?remi\b|\bremi\s+erbjuds\b",
    re.IGNORECASE,
)

_CAPTURE_VERB = re.compile(r"\b(?:slar|slå|sla|tar|ta)\b", re.IGNORECASE)

_PIECE_TYPE: dict[str, chess.PieceType] = {
    "pawn": chess.PAWN,
    "knight": chess.KNIGHT,
    "bishop": chess.BISHOP,
    "rook": chess.ROOK,
    "queen": chess.QUEEN,
    "king": chess.KING,
}


def normalize_text(text: str) -> str:
    """Lowercase, strip accents on ASCII letters, collapse whitespace."""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w\såäö]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _piece_word_pattern() -> str:
    words = {word for word in _PIECE_ALIASES}
    words |= {normalize_text(word) for word in _PIECE_ALIASES}
    return "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))


_PIECE_WORD = _piece_word_pattern()

_CAPTURE_ON = re.compile(
    rf"(?:jag\s+)?(?:slar|slå|sla|tar|ta)\b.*?\b(?:på|pa)\s+{_square_pattern('to')}\b",
    re.IGNORECASE,
)

_CAPTURE_SQUARE = re.compile(
    rf"\b(?:slar|slå|sla|tar|ta)\s+{_square_pattern('to')}\b",
    re.IGNORECASE,
)


def parse_square_token(match: re.Match[str], prefix: str) -> str | None:
    """Build a1–h8 from a regex group prefix (``from`` or ``to``)."""
    file_ch = match.group(f"{prefix}_file")
    if not file_ch:
        return None
    rank_digit = match.group(f"{prefix}_rank_digit")
    rank_word = match.group(f"{prefix}_rank_word")
    if rank_digit:
        rank = rank_digit
    elif rank_word:
        rank = _RANK_WORDS.get(rank_word.lower())
        if not rank:
            return None
    else:
        return None
    square = f"{file_ch.lower()}{rank}"
    return square if _VALID_SQUARE.match(square) else None


def _lookup_piece(word: str) -> str | None:
    return _PIECE_ALIASES.get(word) or _PIECE_ALIASES.get(normalize_text(word))


def _optional_piece(text: str) -> str | None:
    for word, piece in _PIECE_ALIASES.items():
        for variant in (word, normalize_text(word)):
            if re.search(rf"\b{re.escape(variant)}\b", text):
                return piece
    return None


def _piece_with_owner(segment: str, owner: str) -> str | None:
    m = re.search(rf"\b{owner}\s+({_PIECE_WORD})\b", segment)
    if not m:
        return None
    return _lookup_piece(m.group(1))


def _extract_capture_pieces(text: str) -> tuple[str | None, str | None]:
    """Return ``(victim_piece, attacker_piece)`` from a normalized capture phrase."""
    victim: str | None = None
    attacker: str | None = None
    if " med " in text:
        before, _, after = text.partition(" med ")
        victim = _piece_with_owner(before, r"(?:din|ditt|dina)") or _optional_piece(before)
        attacker = _piece_with_owner(after, r"(?:min|mitt|mina)") or _optional_piece(after)
    else:
        victim = _piece_with_owner(text, r"(?:din|ditt|dina)") or _optional_piece(text)
    return victim, attacker


def _capture_intent(to_sq: str, text: str) -> dict[str, Any]:
    args: dict[str, Any] = {"to": to_sq}
    victim, attacker = _extract_capture_pieces(text)
    if victim:
        args["victim_piece"] = victim
    if attacker:
        args["piece"] = attacker
    return {"intent": "capture_piece", "arguments": args}


def _move_intent(from_sq: str, to_sq: str, text: str) -> dict[str, Any]:
    args: dict[str, Any] = {"from": from_sq, "to": to_sq}
    piece = _optional_piece(text)
    if piece:
        args["piece"] = piece
    return {"intent": "move_piece", "arguments": args}


def parse_utterance(text: str) -> dict[str, Any] | None:
    """Parse a Swedish utterance into an intent dict, or ``None`` if unknown."""
    if not text or not text.strip():
        return None

    normalized = normalize_text(text)

    if _CAPTURE_VERB.search(normalized):
        for pattern in (_CAPTURE_ON, _CAPTURE_SQUARE):
            m = pattern.search(normalized)
            if m:
                to_sq = parse_square_token(m, "to")
                if to_sq:
                    return _capture_intent(to_sq, normalized)

    for pattern in (_MOVE_FROM_TO, _MOVE_SQUARE_TILL):
        m = pattern.search(normalized)
        if m:
            from_sq = parse_square_token(m, "from")
            to_sq = parse_square_token(m, "to")
            if from_sq and to_sq:
                return _move_intent(from_sq, to_sq, normalized)

    m = _MOVE_TO_ONLY.search(normalized)
    if m:
        to_sq = parse_square_token(m, "to")
        if to_sq:
            args: dict[str, Any] = {"to": to_sq}
            piece = _optional_piece(normalized)
            if piece:
                args["piece"] = piece
            return {"intent": "move_piece", "arguments": args}

    m = _CASTLE.search(normalized)
    if m:
        side_raw = m.group("side").lower()
        if side_raw in ("kort", "kungs"):
            side = "kingside"
        elif side_raw in ("lång", "lang", "långt", "langt", "dam"):
            side = "queenside"
        else:
            return None
        return {"intent": "castle", "arguments": {"side": side}}

    if _RESIGN.search(normalized):
        return {"intent": "resign", "arguments": {}}

    if _DRAW.search(normalized):
        return {"intent": "offer_draw", "arguments": {}}

    return None


def _capture_matches_victim(
    board: chess.Board, move: chess.Move, victim_type: chess.PieceType | None
) -> bool:
    if victim_type is None:
        return True
    if board.is_en_passant(move):
        return victim_type == chess.PAWN
    captured = board.piece_at(move.to_square)
    return captured is not None and captured.piece_type == victim_type


def resolve_capture(board: chess.Board, arguments: dict[str, Any]) -> chess.Move | None:
    """Pick the unique legal capture matching NLU arguments, or ``None`` if ambiguous."""
    to_sq = chess.parse_square(arguments["to"])
    from_sq = (
        chess.parse_square(arguments["from"]) if arguments.get("from") else None
    )
    attacker_type = _PIECE_TYPE.get(arguments.get("piece", ""))
    victim_type = _PIECE_TYPE.get(arguments.get("victim_piece", ""))

    candidates: list[chess.Move] = []
    for move in board.legal_moves:
        if move.to_square != to_sq or not board.is_capture(move):
            continue
        if from_sq is not None and move.from_square != from_sq:
            continue
        mover = board.piece_at(move.from_square)
        if mover is None or mover.color != board.turn:
            continue
        if attacker_type is not None and mover.piece_type != attacker_type:
            continue
        if not _capture_matches_victim(board, move, victim_type):
            continue
        candidates.append(move)

    if len(candidates) == 1:
        return candidates[0]
    return None


def resolve_move(board: chess.Board, parsed: dict[str, Any]) -> chess.Move | None:
    """Resolve a parsed intent to a single legal move when possible."""
    intent = parsed.get("intent")
    args = parsed.get("arguments", {})

    if intent == "capture_piece":
        return resolve_capture(board, args)

    if intent != "move_piece":
        return None

    from_sq = chess.parse_square(args["from"]) if args.get("from") else None
    to_sq = chess.parse_square(args["to"]) if args.get("to") else None
    if to_sq is None:
        return None

    piece_type = _PIECE_TYPE.get(args.get("piece", ""))
    candidates: list[chess.Move] = []
    for move in board.legal_moves:
        if move.to_square != to_sq:
            continue
        if from_sq is not None and move.from_square != from_sq:
            continue
        if board.is_capture(move):
            continue
        mover = board.piece_at(move.from_square)
        if mover is None or mover.color != board.turn:
            continue
        if piece_type is not None and mover.piece_type != piece_type:
            continue
        candidates.append(move)

    if len(candidates) == 1:
        return candidates[0]
    return None

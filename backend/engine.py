"""Sunfish chess engine integration for system move selection."""

from __future__ import annotations

import time

import chess

import sunfish

_CHESS_TO_SUNFISH = {
    chess.PAWN: "P",
    chess.KNIGHT: "N",
    chess.BISHOP: "B",
    chess.ROOK: "R",
    chess.QUEEN: "Q",
    chess.KING: "K",
}


def _sq_to_sunfish(square: int) -> int:
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    return sunfish.A1 + file - 10 * rank


def _sunfish_idx_to_square(i: int) -> int:
    sf_rank = (i - sunfish.A1) // 10
    sf_file = (i - sunfish.A1) % 10
    return chess.square(sf_file, -sf_rank)


def _board_to_sunfish(board: chess.Board) -> sunfish.Position:
    padding = " " * 9 + "\n"
    rows = [padding, padding]

    for chess_rank in range(7, -1, -1):
        row = [" "]
        for chess_file in range(8):
            sq = chess.square(chess_file, chess_rank)
            piece = board.piece_at(sq)
            if piece is None:
                row.append(".")
            else:
                ch = _CHESS_TO_SUNFISH[piece.piece_type]
                row.append(ch.upper() if piece.color == chess.WHITE else ch.lower())
        row.append("\n")
        rows.append("".join(row))

    rows.append(padding)
    rows.append(padding)
    board_str = "".join(rows)

    wc = (board.has_queenside_castling_rights(chess.WHITE), board.has_kingside_castling_rights(chess.WHITE))
    bc = (board.has_queenside_castling_rights(chess.BLACK), board.has_kingside_castling_rights(chess.BLACK))

    ep = 0
    if board.ep_square is not None:
        ep = _sq_to_sunfish(board.ep_square)

    pos = sunfish.Position(board_str, 0, wc, bc, ep, 0)

    if board.turn == chess.BLACK:
        pos = pos.rotate()

    return pos


def _sunfish_to_chess_move(sf_move: sunfish.Move | None, board: chess.Board) -> chess.Move | None:
    if sf_move is None:
        return None

    i, j = sf_move.i, sf_move.j
    if board.turn == chess.BLACK:
        i, j = 119 - i, 119 - j

    from_sq = _sunfish_idx_to_square(i)
    to_sq = _sunfish_idx_to_square(j)

    prom_map = {"n": chess.KNIGHT, "b": chess.BISHOP, "r": chess.ROOK, "q": chess.QUEEN}
    promotion = prom_map.get(sf_move.prom.lower()) if sf_move.prom else None

    return chess.Move(from_sq, to_sq, promotion=promotion)


def get_move(board: chess.Board, time_limit: float = 0.2) -> chess.Move | None:
    pos = _board_to_sunfish(board)

    searcher = sunfish.Searcher()
    best_sf_move = None

    start = time.time()
    for depth, gamma, score, move in searcher.search([pos]):
        if move is not None and score >= gamma:
            best_sf_move = move
        if time.time() - start > time_limit:
            break

    return _sunfish_to_chess_move(best_sf_move, board)

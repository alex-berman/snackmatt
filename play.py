#!/usr/bin/env python3
"""Text-based interactive chess using the Swedish dialog pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(BACKEND))

import chess
from dialog import process_user_turn


def main() -> None:
    board = chess.Board()
    context: dict = {"user_color": "white"}

    print()
    print("=== Svenska schack (textläge) ===")
    print("Skriv ett drag på svenska (t.ex. 'jag flyttar e2 till e4')")
    print("Skriv 'quit' eller 'avsluta' för att avsluta.")
    print()

    while True:
        print(board)
        print()
        print(f"{'Vit' if board.turn == chess.WHITE else 'Svart'} att flytta.")

        utterance = input("Du: ").strip()
        if not utterance or utterance.lower() in ("quit", "avsluta", "exit"):
            break

        ok = process_user_turn(utterance, board, context)
        if not ok:
            reason = context.get("response", {}).get("reason", "okänd")
            if reason == "game_over":
                print("\nSystem: Spelet är över. Inga fler drag tillåtna.")
                break
            print(f"\nSystem: (kunde inte bearbeta: {reason})")
            continue

        response = context.get("response", {})
        system_text = response.get("system_move_nlg", "")
        if system_text:
            print(f"\nSystem: {system_text}")

        if context.get("keep_system_turn"):
            process_user_turn("", board, context)
            response = context.get("response", {})
            system_text = response.get("system_move_nlg", "")
            if system_text:
                print(f"System: {system_text}")

        if response.get("type") == "checkmate":
            winner = "Svart" if board.turn == chess.WHITE else "Vit"
            print(f"\n*** SCHACKMATT! {winner} vann! ***")
            break

        if context.get("game_over"):
            print("\nSpelet är över.")
            break

    print("\nTack för spelet!")


if __name__ == "__main__":
    main()

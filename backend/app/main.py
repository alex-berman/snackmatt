from __future__ import annotations

import io
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("snackmatt")

import chess
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.elevenlabs_speech import active_voice_info, synthesize_speech, transcribe_audio
from dialog import process_user_turn

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"

app = FastAPI(title="Snackmatt", description="Swedish voice chess")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Transcript",
        "X-Reply-Text",
        "X-Response-Type",
        "X-Board-FEN",
        "X-Game-Over",
    ],
)

_chess_board: chess.Board | None = None
_chess_context: dict = {}


def _ensure_game():
    global _chess_board, _chess_context
    if _chess_board is None:
        _chess_board = chess.Board()
        _chess_context = {"user_color": "white"}


class TtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@app.get("/api/health")
def health():
    payload = {
        "ok": True,
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        "language": settings.language_code,
    }
    if settings.elevenlabs_api_key:
        try:
            payload["voice"] = active_voice_info()
        except RuntimeError as exc:
            payload["voice_error"] = str(exc)
    return payload


@app.post("/api/tts")
def tts(body: TtsRequest):
    try:
        audio = synthesize_speech(body.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/stt")
async def stt(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) < 1000:
        raise HTTPException(
            status_code=400,
            detail="Audio too short — record at least ~1 second.",
        )
    try:
        text = transcribe_audio(
            io.BytesIO(data),
            filename=file.filename or "audio.webm",
            content_type=file.content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"text": text}


@app.get("/api/board")
def board_state():
    _ensure_game()
    return {
        "fen": _chess_board.fen(),
        "turn": "white" if _chess_board.turn == chess.WHITE else "black",
        "game_over": _chess_context.get("game_over", False),
        "in_check": _chess_board.is_check(),
    }


@app.post("/api/command")
async def command(file: UploadFile = File(...)):
    """
    Process spoken chess command.

    Transcribes audio → runs dialog pipeline → returns TTS audio + metadata headers.
    """
    _ensure_game()
    data = await file.read()
    if len(data) < 1000:
        raise HTTPException(
            status_code=400,
            detail="Audio too short — record at least ~1 second.",
        )

    try:
        transcript = transcribe_audio(
            io.BytesIO(data),
            filename=file.filename or "audio.webm",
            content_type=file.content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    process_user_turn(transcript, _chess_board, _chess_context)

    response = _chess_context.get("response", {})
    system_text = response.get("system_move_nlg", "")

    if _chess_context.get("keep_system_turn"):
        thinking_text = system_text
        process_user_turn("", _chess_board, _chess_context)
        response = _chess_context.get("response", {})
        final_text = response.get("system_move_nlg", "")
        system_text = f"{thinking_text} {final_text}" if final_text else thinking_text

    response_type = response.get("type", "error")

    logger.info("")
    logger.info("─" * 40)
    logger.info("Du: %s", transcript)
    logger.info("System: %s", system_text)
    logger.info("Typ: %s", response_type)
    logger.info("")
    logger.info("Br\u00e4de:")
    for line in str(_chess_board).split("\n"):
        logger.info("  %s", line)
    logger.info("FEN: %s", _chess_board.fen())
    logger.info("─" * 40)

    try:
        reply_audio = synthesize_speech(system_text) if system_text else b""
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=reply_audio,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": transcript,
            "X-Reply-Text": system_text,
            "X-Response-Type": response_type,
            "X-Board-FEN": _chess_board.fen(),
            "X-Game-Over": str(_chess_context.get("game_over", False)).lower(),
        },
    )


@app.post("/api/command-text")
def command_text(body: TtsRequest):
    """
    Process a text chess command (useful for testing).
    """
    _ensure_game()

    process_user_turn(body.text, _chess_board, _chess_context)

    response = _chess_context.get("response", {})
    system_text = response.get("system_move_nlg", "")

    if _chess_context.get("keep_system_turn"):
        thinking_text = system_text
        process_user_turn("", _chess_board, _chess_context)
        response = _chess_context.get("response", {})
        final_text = response.get("system_move_nlg", "")
        system_text = f"{thinking_text} {final_text}" if final_text else thinking_text

    response_type = response.get("type", "error")

    logger.info("")
    logger.info("─" * 40)
    logger.info("Du: %s", body.text)
    logger.info("System: %s", system_text)
    logger.info("Typ: %s", response_type)
    logger.info("")
    logger.info("Br\u00e4de:")
    for line in str(_chess_board).split("\n"):
        logger.info("  %s", line)
    logger.info("FEN: %s", _chess_board.fen())
    logger.info("─" * 40)

    return {
        "transcript": body.text,
        "reply_text": system_text,
        "response_type": response_type,
        "fen": _chess_board.fen(),
        "turn": "white" if _chess_board.turn == chess.WHITE else "black",
        "game_over": _chess_context.get("game_over", False),
    }


@app.post("/api/reset")
def reset_board():
    _ensure_game()
    _chess_board.reset()
    _chess_context.clear()
    _chess_context["user_color"] = "white"
    return {"ok": True}


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

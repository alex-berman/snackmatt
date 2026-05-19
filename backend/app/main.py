from __future__ import annotations

import io

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import settings
from app.elevenlabs_speech import active_voice_info, synthesize_speech, transcribe_audio

app = FastAPI(title="Voice Chess", description="Swedish voice chess — speech spike")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Transcript", "X-Reply-Text"],
)

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"


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


@app.post("/api/echo")
async def echo(file: UploadFile = File(...)):
    """Record → transcribe → speak back what was heard (Swedish)."""
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
        reply_text = f"Jag hörde: {transcript}"
        reply_audio = synthesize_speech(reply_text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=reply_audio,
        media_type="audio/mpeg",
        headers={
            "X-Transcript": transcript,
            "X-Reply-Text": reply_text,
        },
    )


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

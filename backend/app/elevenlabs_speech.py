from __future__ import annotations

import io
import logging
from typing import BinaryIO

from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

from app.config import settings

logger = logging.getLogger(__name__)

_resolved_voice: tuple[str, str] | None = None  # (voice_id, name)


def _client() -> ElevenLabs:
    if not settings.elevenlabs_api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not set. Add it to backend/.env (see .env.example)."
        )
    return ElevenLabs(api_key=settings.elevenlabs_api_key)


def _audio_bytes(stream) -> bytes:
    if isinstance(stream, (bytes, bytearray)):
        return bytes(stream)
    return b"".join(chunk for chunk in stream)


def _category_name(voice) -> str:
    cat = getattr(voice, "category", None)
    if cat is None:
        return ""
    return str(getattr(cat, "value", cat)).lower()


def _pick_voice_from_search(client: ElevenLabs, *, voice_type: str) -> tuple[str, str] | None:
    result = client.voices.search(voice_type=voice_type, page_size=100)
    voices = getattr(result, "voices", None) or []
    for voice in voices:
        vid = getattr(voice, "voice_id", None)
        if vid:
            name = getattr(voice, "name", None) or voice_type
            return vid, name
    return None


def resolve_voice_id(*, force: bool = False) -> tuple[str, str]:
    """Pick a voice that works on the free API plan (not Voice Library)."""
    global _resolved_voice
    if _resolved_voice is not None and not force:
        return _resolved_voice

    configured = settings.elevenlabs_voice_id.strip()
    if configured and configured.lower() != "auto":
        _resolved_voice = (configured, "configured")
        return _resolved_voice

    client = _client()
    for voice_type in ("default", "personal", "generated"):
        picked = _pick_voice_from_search(client, voice_type=voice_type)
        if picked:
            _resolved_voice = picked
            logger.info("Using ElevenLabs voice %s (%s)", picked[1], picked[0])
            return _resolved_voice

    # Fallback: first non-premade voice from legacy list
    all_resp = client.voices.get_all(show_legacy=True)
    for voice in getattr(all_resp, "voices", None) or []:
        if _category_name(voice) == "premade":
            continue
        vid = getattr(voice, "voice_id", None)
        if vid:
            name = getattr(voice, "name", None) or "account"
            _resolved_voice = (vid, name)
            logger.info("Using ElevenLabs voice %s (%s)", name, vid)
            return _resolved_voice

    raise RuntimeError(
        "No API-usable voice on your ElevenLabs account. On the free plan, library "
        "voices (e.g. Rachel) cannot be used via the API. Create a voice under "
        "Voice Design, or set ELEVENLABS_VOICE_ID to a 'default' voice from your account."
    )


def active_voice_info() -> dict[str, str]:
    voice_id, name = resolve_voice_id()
    return {"voice_id": voice_id, "voice_name": name}


def _api_error_message(exc: ApiError) -> str:
    body = exc.body if isinstance(exc.body, dict) else {}
    detail = body.get("detail", body)
    if isinstance(detail, dict):
        msg = detail.get("message") or detail.get("code") or str(detail)
    else:
        msg = str(detail)
    if exc.status_code == 402:
        return (
            f"{msg} — Set ELEVENLABS_VOICE_ID=auto in backend/.env (or use a default/personal "
            "voice from your account, not the Voice Library)."
        )
    return msg or f"ElevenLabs API error ({exc.status_code})"


def synthesize_speech(text: str) -> bytes:
    client = _client()
    voice_id, _ = resolve_voice_id()
    try:
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id=settings.tts_model_id,
            output_format="mp3_44100_128",
        )
    except ApiError as exc:
        if exc.status_code == 402:
            global _resolved_voice
            _resolved_voice = None
        raise RuntimeError(_api_error_message(exc)) from exc
    return _audio_bytes(audio)


def transcribe_audio(
    audio: BinaryIO,
    *,
    filename: str = "audio.webm",
    content_type: str | None = None,
) -> str:
    client = _client()
    try:
        result = client.speech_to_text.convert(
            file=audio,
            model_id=settings.stt_model_id,
            language_code=settings.language_code,
            tag_audio_events=False,
        )
    except ApiError as exc:
        raise RuntimeError(_api_error_message(exc)) from exc
    text = getattr(result, "text", None)
    if text is None and isinstance(result, dict):
        text = result.get("text")
    if not text:
        raise RuntimeError("Speech-to-text returned no transcript.")
    return text.strip()


def speech_roundtrip(source_text: str) -> tuple[str, bytes]:
    """TTS → STT → TTS echo. Returns (transcript, reply_audio)."""
    spoken = synthesize_speech(source_text)
    transcript = transcribe_audio(
        io.BytesIO(spoken),
        filename="roundtrip.mp3",
        content_type="audio/mpeg",
    )
    reply = f"Jag hörde: {transcript}"
    return transcript, synthesize_speech(reply)

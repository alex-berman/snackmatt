"""Live integration test: ElevenLabs TTS → STT → TTS (Swedish).

Requires ELEVENLABS_API_KEY in the environment (or backend/.env when pytest
is run from backend/).
"""

from __future__ import annotations

import os
import re

import pytest

# Load .env before app settings if present
from pathlib import Path

_env = Path(__file__).resolve().parents[1] / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from app.elevenlabs_speech import speech_roundtrip, synthesize_speech, transcribe_audio

SOURCE_PHRASE = "Hej, jag vill spela schack."
# Words we expect STT to recover (allow minor spelling variance).
EXPECTED_WORDS = ("schack",)


@pytest.mark.integration
def test_tts_returns_audio(requires_elevenlabs):
    audio = synthesize_speech(SOURCE_PHRASE)
    assert len(audio) > 1000, "TTS should return a non-trivial MP3 payload"
    assert audio[:3] == b"ID3" or audio[:2] == b"\xff\xfb" or audio[0:4] == b"\xff\xf3"


@pytest.mark.integration
def test_stt_on_tts_audio(requires_elevenlabs):
    import io

    audio = synthesize_speech(SOURCE_PHRASE)
    transcript = transcribe_audio(
        io.BytesIO(audio),
        filename="test.mp3",
        content_type="audio/mpeg",
    )
    normalized = transcript.lower()
    assert any(word in normalized for word in EXPECTED_WORDS), (
        f"Expected one of {EXPECTED_WORDS} in transcript, got: {transcript!r}"
    )


@pytest.mark.integration
def test_speech_roundtrip(requires_elevenlabs):
    transcript, reply_audio = speech_roundtrip(SOURCE_PHRASE)
    assert transcript, "Round-trip should produce a transcript"
    assert len(reply_audio) > 1000, "Reply TTS should return audio"
    assert re.search(r"schack|spela|hej", transcript.lower()), (
        f"Unexpected transcript: {transcript!r}"
    )

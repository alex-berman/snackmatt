import os
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def elevenlabs_api_key() -> str | None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    return key or None


@pytest.fixture(scope="session")
def requires_elevenlabs(elevenlabs_api_key):
    if not elevenlabs_api_key:
        pytest.skip("ELEVENLABS_API_KEY not set — skipping live speech test")

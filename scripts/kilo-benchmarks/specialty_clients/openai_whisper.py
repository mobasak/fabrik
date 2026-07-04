# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_specialty_clients/test_openai_whisper.py
"""OpenAI Whisper STT client.

OpenAI transcription API (well-known SDK pattern, U-B.0.5):
  POST https://api.openai.com/v1/audio/transcriptions
  Headers: {"Authorization": "Bearer <OPENAI_API_KEY>"}
  Multipart: file=<audio bytes>, model=whisper-1
  Response 200: {"text": "<transcription>"}
  Bench fixture: 10 seconds of silence generated in-test via `struct` (no repo file).
"""

from __future__ import annotations

import io
import struct
import time

import requests

ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"
MODEL_MAP = {
    "openai/whisper-large-v3": "whisper-1",  # Whisper API only offers whisper-1
    "openai/whisper-1": "whisper-1",
    "openai/whisper-large-v3-turbo": "whisper-1",
}
SILENCE_SECONDS = 10
SAMPLE_RATE = 16000


def _make_silence_wav() -> bytes:
    """10s of silence as a valid WAV (44-byte RIFF header + zero PCM)."""
    n_samples = SILENCE_SECONDS * SAMPLE_RATE
    byte_rate = SAMPLE_RATE * 2  # 16-bit mono
    data_size = n_samples * 2
    buf = io.BytesIO()
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + data_size))
    buf.write(b"WAVE")
    buf.write(b"fmt ")
    buf.write(struct.pack("<I", 16))  # fmt chunk size
    buf.write(struct.pack("<H", 1))  # PCM
    buf.write(struct.pack("<H", 1))  # mono
    buf.write(struct.pack("<I", SAMPLE_RATE))
    buf.write(struct.pack("<I", byte_rate))
    buf.write(struct.pack("<H", 2))  # block align
    buf.write(struct.pack("<H", 16))  # bits
    buf.write(b"data")
    buf.write(struct.pack("<I", data_size))
    buf.write(b"\x00" * data_size)
    return buf.getvalue()


def bench_one(model_id: str, api_key: str) -> dict:
    whisper_model = MODEL_MAP.get(model_id, "whisper-1")
    audio = _make_silence_wav()
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": ("sample.wav", audio, "audio/wav")}
    data = {"model": whisper_model}
    t0 = time.monotonic()
    try:
        r = requests.post(ENDPOINT, headers=headers, files=files, data=data, timeout=60)
        if r.status_code >= 400:
            return _err(f"http {r.status_code}: {r.text[:200]}")
        perf_seconds = time.monotonic() - t0
        return {
            "perf_seconds": round(perf_seconds, 2),
            "cost_usd": SILENCE_SECONDS / 60.0 * 0.006,
            "error": None,
        }
    except requests.exceptions.RequestException as e:
        return _err(f"http error: {e}")


def _err(msg: str) -> dict:
    return {"perf_seconds": None, "cost_usd": 0.0, "error": msg}

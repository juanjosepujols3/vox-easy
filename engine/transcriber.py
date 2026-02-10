"""Transcriber using Groq API (whisper-large-v3-turbo) for fast, accurate speech-to-text."""

import os
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"


class Transcriber:
    def __init__(self, **kwargs):
        if not GROQ_API_KEY:
            print("WARNING: GROQ_API_KEY not set. Transcription will fail.")
        else:
            print(f"Transcriber ready (Groq {MODEL})")

    def transcribe(self, audio_path, language=None, prompt=None):
        if not os.path.exists(audio_path):
            return ""
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not configured")

        print(f"Transcribing {audio_path} via Groq...", flush=True)

        with open(audio_path, "rb") as f:
            files = {"file": ("audio.wav", f, "audio/wav")}
            data = {
                "model": MODEL,
                "temperature": "0",
            }
            if language:
                data["language"] = language
            if prompt:
                data["prompt"] = prompt

            resp = httpx.post(
                GROQ_URL,
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=20.0,
            )

        if resp.status_code != 200:
            print(f"Groq error {resp.status_code}: {resp.text}", flush=True)
            raise RuntimeError(f"Groq API error: {resp.status_code}")

        text = resp.json().get("text", "").strip()
        print(f"Transcribed: {text[:60]}...", flush=True)
        return text

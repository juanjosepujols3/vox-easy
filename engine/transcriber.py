"""Transcriber using Groq API (whisper-large-v3-turbo) for fast, accurate speech-to-text."""

import os
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"


def build_smart_prompt(dev_mode=False, recent_text="", custom_terms=None):
    """
    Construye un prompt contextual para Whisper que mejora la precisión.

    El prompt le da pistas a Whisper sobre qué palabras esperar, lo cual
    mejora dramáticamente la precisión en:
    - Nombres propios (Vox Easy, FastAPI)
    - Términos técnicos (TypeScript, PostgreSQL)
    - Contexto reciente (continúa frases previas mejor)

    Args:
        dev_mode: Si está activo, incluye vocabulario técnico
        recent_text: Últimas palabras dictadas (para contexto)
        custom_terms: Lista de términos personalizados del usuario

    Returns:
        String de prompt para Whisper (max 224 tokens)
    """
    parts = []

    # 1. Contexto reciente (ayuda con continuidad)
    if recent_text:
        # Últimas 15 palabras para contexto
        words = recent_text.split()[-15:]
        if words:
            parts.extend(words)

    # 2. Términos técnicos si dev_mode activo
    if dev_mode:
        try:
            from engine.dev_terms import DEV_TERMS
            # Top 25 términos más comunes
            parts.extend(DEV_TERMS[:25])
        except ImportError:
            pass

    # 3. Términos custom del usuario (nombres de proyectos, etc.)
    if custom_terms:
        parts.extend(custom_terms[:10])

    # 4. Siempre incluir nombre de la app
    parts.extend(["Vox Easy", "VoxEasy", "dictado"])

    # Unir y limitar a ~200 tokens (Whisper limit es 224)
    prompt = ", ".join(parts)
    if len(prompt) > 800:  # ~200 tokens aprox
        prompt = prompt[:800]

    return prompt


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

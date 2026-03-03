"""
LLM post-processing para mejorar transcripciones.

Este módulo usa Claude Haiku para pulir las transcripciones de Whisper:
- Corrige errores de transcripción obvios
- Mejora puntuación si falta o está mal
- Elimina muletillas residuales
- NO agrega contenido nuevo ni cambia el significado

Costo: ~500-700ms de latencia adicional
Beneficio: Transcripciones casi perfectas
"""

import os


def improve_transcription_with_llm(text: str, language: str = "es", timeout: float = 5.0) -> str:
    """
    Post-procesa transcripción con Claude Haiku para mejorar calidad.

    Args:
        text: Texto transcrito por Whisper
        language: Idioma del texto ("es" o "en")
        timeout: Timeout en segundos (default 5s)

    Returns:
        Texto mejorado, o el original si hay error
    """
    if not text or len(text.strip()) < 5:
        return text

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("[llm_postprocess] ANTHROPIC_API_KEY not set, skipping LLM improvement")
        return text

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        # Prompt conciso y específico
        lang_name = "español" if language.startswith("es") else "inglés"
        prompt = f"""Corrige esta transcripción de voz en {lang_name}:

REGLAS ESTRICTAS:
1. Corrige errores de transcripción obvios (palabras mal escritas, homófonos)
2. Mejora la puntuación si falta o está incorrecta
3. Elimina muletillas residuales (um, eh, este, bueno)
4. NO agregues contenido nuevo
5. NO cambies el significado original
6. NO expliques nada, solo devuelve el texto corregido

Texto: {text}"""

        print("[llm_postprocess] Mejorando con Claude Haiku...", flush=True)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,  # Suficiente para texto largo
            timeout=timeout,
            messages=[{"role": "user", "content": prompt}]
        )

        improved_text = message.content[0].text.strip()

        # Validación básica: el texto mejorado no debe ser muy diferente en longitud
        original_len = len(text.split())
        improved_len = len(improved_text.split())

        # Si la diferencia es >50%, probablemente el LLM agregó contenido
        if abs(improved_len - original_len) / original_len > 0.5:
            print("[llm_postprocess] Warning: LLM cambió mucho el texto, usando original")
            return text

        print(f"[llm_postprocess] ✓ Mejorado: {improved_text[:80]}...", flush=True)
        return improved_text

    except Exception as e:
        print(f"[llm_postprocess] Error: {e}, usando texto original")
        return text  # Siempre fallback al original


def improve_transcription_with_llm_batch(texts: list[str], language: str = "es") -> list[str]:
    """
    Post-procesa múltiples transcripciones en batch (más eficiente).

    Args:
        texts: Lista de textos transcritos
        language: Idioma del texto

    Returns:
        Lista de textos mejorados
    """
    # TODO: Implementar batch processing con Batch API de Anthropic
    # Por ahora, procesamos uno por uno
    return [improve_transcription_with_llm(text, language) for text in texts]

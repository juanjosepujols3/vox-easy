"""
Text processing pipeline for Vox Easy.
All functions are pure, stateless, and run 100% client-side.
"""

import re


# ── 1.1  Filler removal ─────────────────────────────────────────

_FILLERS_ES = [
    r"\bbueno\s+pues\b",
    r"\bcomo\s+que\b",
    r"\bo\s+sea\b",
    r"\bdigamos\b",
    r"\bsabes\b",
    r"\beste\b",
    r"\beh\b",
]

_FILLERS_EN = [
    r"\byou\s+know\b",
    r"\bI\s+mean\b",
    r"\bbasically\b",
    r"\blike\b",
    r"\bum\b",
    r"\buh\b",
]

_RE_FILLERS_ES = re.compile("|".join(_FILLERS_ES), re.IGNORECASE)
_RE_FILLERS_EN = re.compile("|".join(_FILLERS_EN), re.IGNORECASE)


def remove_fillers(text, language="es"):
    """Remove filler words (muletillas) from transcribed text."""
    if language and language.startswith("en"):
        text = _RE_FILLERS_EN.sub("", text)
    else:
        text = _RE_FILLERS_ES.sub("", text)
    # Clean double spaces and spaces before punctuation
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,;:!?\]\)\"'])", r"\1", text)
    return text


# ── 1.2  Punctuation dictation ──────────────────────────────────

_PUNCTUATION_ES = [
    ("puntos suspensivos", "..."),
    ("punto y coma", ";"),
    ("dos puntos", ":"),
    ("signo de interrogacion", "?"),
    ("signo de exclamacion", "!"),
    ("abre interrogacion", "\u00bf"),
    ("abre exclamacion", "\u00a1"),
    ("nuevo parrafo", "\n\n"),
    ("nueva linea", "\n"),
    ("nueva línea", "\n"),
    ("parentesis abre", "("),
    ("parentesis cierra", ")"),
    ("comillas", '"'),
    ("arroba", "@"),
    ("punto", "."),
    ("coma", ","),
]

_PUNCTUATION_EN = [
    ("question mark", "?"),
    ("exclamation mark", "!"),
    ("new paragraph", "\n\n"),
    ("new line", "\n"),
    ("semicolon", ";"),
    ("colon", ":"),
    ("period", "."),
    ("comma", ","),
]


def dictate_punctuation(text, language="es"):
    """Replace spoken punctuation words with actual punctuation marks."""
    mapping = _PUNCTUATION_EN if (language and language.startswith("en")) else _PUNCTUATION_ES
    for spoken, symbol in mapping:
        text = re.sub(
            r"\s*\b" + re.escape(spoken) + r"\b\s*",
            symbol,
            text,
            flags=re.IGNORECASE,
        )
    # Clean spaces around punctuation
    text = re.sub(r"\s+([.,;:!?\]\)\"'\u00bf\u00a1])", r"\1", text)
    text = re.sub(r"([\(\[\"\u00bf\u00a1])\s+", r"\1", text)
    # Ensure space after punctuation when followed by a letter
    text = re.sub(r"([.,;:!?])([A-Za-z\u00c0-\u00ff])", r"\1 \2", text)
    return text


# ── 1.3  Self-correction detection ──────────────────────────────

_CORRECTION_MARKERS_ES = [
    "mejor dicho", "quiero decir", "en realidad", "corrijo", "perdon", "perdón", "digo",
]

_CORRECTION_MARKERS_EN = [
    "actually", "I mean", "rather", "sorry", "correction", "no wait",
]


def detect_self_correction(text, language="es"):
    """Detect self-correction markers and keep only the corrected part."""
    markers = _CORRECTION_MARKERS_EN if (language and language.startswith("en")) else _CORRECTION_MARKERS_ES
    # Sort longest first to match multi-word markers properly
    markers = sorted(markers, key=len, reverse=True)

    # Work on each sentence separately
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result = []
    for sentence in sentences:
        corrected = sentence
        for marker in markers:
            pattern = re.compile(re.escape(marker), re.IGNORECASE)
            match = pattern.search(corrected)
            if match:
                # Keep only the part after the last occurrence of this marker
                last_pos = 0
                for m in pattern.finditer(corrected):
                    last_pos = m.end()
                after = corrected[last_pos:].strip()
                if after:
                    corrected = after
        result.append(corrected)
    return " ".join(result)


# ── 1.4  List formatting ────────────────────────────────────────

_ORDINALS_ES = [
    ("primero", 1), ("segundo", 2), ("tercero", 3),
    ("cuarto", 4), ("quinto", 5), ("sexto", 6),
    ("septimo", 7), ("séptimo", 7), ("octavo", 8),
    ("noveno", 9), ("decimo", 10), ("décimo", 10),
]

_ORDINALS_EN = [
    ("first", 1), ("second", 2), ("third", 3),
    ("fourth", 4), ("fifth", 5), ("sixth", 6),
    ("seventh", 7), ("eighth", 8), ("ninth", 9),
    ("tenth", 10),
]


def format_list(text, language="es"):
    """Detect ordinal sequences and format as numbered lists."""
    ordinals = _ORDINALS_EN if (language and language.startswith("en")) else _ORDINALS_ES

    # Check how many ordinals appear in the text
    found = []
    text_lower = text.lower()
    for word, num in ordinals:
        if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
            found.append((word, num))

    if len(found) < 2:
        return text

    # Split text at ordinal boundaries and format as numbered list
    # Build regex that matches any ordinal
    ordinal_words = [re.escape(w) for w, _ in found]
    ordinal_pattern = re.compile(
        r"\b(" + "|".join(ordinal_words) + r")\b",
        re.IGNORECASE,
    )

    parts = ordinal_pattern.split(text)
    # parts = [before, ordinal1, content1, ordinal2, content2, ...]

    items = []
    current_num = 0
    for i, part in enumerate(parts):
        part_lower = part.strip().lower()
        matched_ordinal = False
        for word, num in found:
            if part_lower == word:
                current_num = num
                matched_ordinal = True
                break
        if not matched_ordinal and current_num > 0:
            content = part.strip()
            if content:
                items.append(f"{current_num}. {content}")
                current_num = 0

    if not items:
        return text

    # Prefix with any text before the first ordinal
    prefix = ""
    first_ordinal_match = ordinal_pattern.search(text)
    if first_ordinal_match and first_ordinal_match.start() > 0:
        prefix = text[:first_ordinal_match.start()].strip()

    result = "\n".join(items)
    if prefix:
        result = prefix + "\n" + result
    return result


# ── 3.1  Code casing (dev mode) ─────────────────────────────────

def _to_camel_case(words):
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


def _to_snake_case(words):
    return "_".join(w.lower() for w in words)


def _to_pascal_case(words):
    return "".join(w.capitalize() for w in words)


def _to_upper_case(words):
    return "_".join(w.upper() for w in words)


_CASING_COMMANDS = [
    (r"\bcamel\s+case\b", _to_camel_case),
    (r"\bsnake\s+case\b", _to_snake_case),
    (r"\bpascal\s+case\b", _to_pascal_case),
    (r"\bupper\s+case\b", _to_upper_case),
]


def apply_code_casing(text):
    """Transform 'camel case my variable' -> 'myVariable', etc."""
    for pattern, transform_fn in _CASING_COMMANDS:
        regex = re.compile(pattern + r"\s+(.+?)(?=\s*(?:" + "|".join(
            p for p, _ in _CASING_COMMANDS
        ) + r"|$))", re.IGNORECASE)

        def replacer(m, fn=transform_fn):
            words_str = m.group(1).strip()
            words = words_str.split()
            if not words:
                return ""
            return fn(words)

        text = regex.sub(replacer, text)

    return text


# ── 3.2  Code punctuation (dev mode) ────────────────────────────

_CODE_PUNCTUATION = [
    ("triple igual", "==="),
    ("doble igual", "=="),
    ("doble pipe", "||"),
    ("llave abre", "{"),
    ("llave cierra", "}"),
    ("corchete abre", "["),
    ("corchete cierra", "]"),
    ("parentesis abre", "("),
    ("parentesis cierra", ")"),
    ("flecha", "=>"),
    ("incremento", "++"),
    ("menor que", "<"),
    ("mayor que", ">"),
    ("ampersand", "&"),
    ("backtick", "`"),
    ("underscore", "_"),
    ("hashtag", "#"),
    ("pipe", "|"),
    ("igual", "="),
]


def apply_code_punctuation(text):
    """Replace spoken code punctuation with symbols (dev mode replacement for dictate_punctuation)."""
    for spoken, symbol in _CODE_PUNCTUATION:
        text = re.sub(
            r"\s*\b" + re.escape(spoken) + r"\b\s*",
            symbol,
            text,
            flags=re.IGNORECASE,
        )
    # Also apply standard punctuation that's useful in code
    standard = [
        ("punto y coma", ";"),
        ("dos puntos", ":"),
        ("coma", ","),
        ("punto", "."),
    ]
    for spoken, symbol in standard:
        text = re.sub(
            r"\s*\b" + re.escape(spoken) + r"\b\s*",
            symbol,
            text,
            flags=re.IGNORECASE,
        )
    # Clean spacing
    text = re.sub(r"\s+", " ", text).strip()
    return text

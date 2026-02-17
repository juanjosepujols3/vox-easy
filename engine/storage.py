"""
Persistent local storage for Vox Easy.
All data lives in ~/.voxeasy/data.json with thread-safe access.
"""

import datetime
import json
import os
import threading
import time
import uuid

DATA_PATH = os.path.join(os.path.expanduser("~"), ".voxeasy", "data.json")

_lock = threading.Lock()

DEFAULT_DATA = {
    "dictionary": [],
    "snippets": [],
    "notes": [],
    "style": {
        "personal": {"formality": "casual", "punctuation": True, "capitalization": "sentence"},
        "work": {"formality": "formal", "punctuation": True, "capitalization": "sentence"},
        "email": {"formality": "formal", "punctuation": True, "capitalization": "sentence"},
        "other": {"formality": "neutral", "punctuation": True, "capitalization": "sentence"},
    },
    "settings": {
        "launch_at_login": False,
        "auto_updates": True,
        "theme": "system",
        "sound_effects": True,
        "show_in_dock": True,
        "privacy_mode": False,
        "filler_removal": True,
        "punctuation_dictation": True,
        "dev_mode": False,
        "dev_mode_apps": [
            "com.microsoft.VSCode",
            "com.todesktop.230313mzl4w4u92",
            "com.exafunction.windsurf",
        ],
    },
    "app_style_map": {
        "com.apple.mail": "email",
        "com.microsoft.Outlook": "email",
        "com.tinyspeck.slackmacgap": "personal",
        "com.microsoft.VSCode": "work",
        "com.todesktop.230313mzl4w4u92": "work",
        "com.exafunction.windsurf": "work",
    },
    "analytics": {
        "by_app": {},
        "by_date": {},
        "by_hour": {},
    },
    "history": [],
    "profile": {"avatar_style": "adventurer", "first_name": "", "last_name": ""},
    "active_style_context": "personal",
    "word_usage": {"count": 0, "week_start": "2025-01-06"},
}


def _read():
    if not os.path.exists(DATA_PATH):
        return dict(DEFAULT_DATA)
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge missing top-level keys from defaults
        for k, v in DEFAULT_DATA.items():
            if k not in data:
                data[k] = v if not isinstance(v, dict) else dict(v)
        return data
    except Exception:
        return dict(DEFAULT_DATA)


def _write(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _gen_id():
    return uuid.uuid4().hex[:12]


# ── Dictionary ────────────────────────────────────────────────

def get_dictionary():
    with _lock:
        return _read().get("dictionary", [])


def add_term(word, pronunciation="", context=""):
    with _lock:
        data = _read()
        term = {
            "id": _gen_id(),
            "word": word,
            "pronunciation": pronunciation,
            "context": context,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": "",
        }
        data.setdefault("dictionary", []).insert(0, term)
        _write(data)
        return term


def update_term(term_id, word, pronunciation="", context=""):
    with _lock:
        data = _read()
        for t in data.get("dictionary", []):
            if t["id"] == term_id:
                t["word"] = word
                t["pronunciation"] = pronunciation
                t["context"] = context
                _write(data)
                return True
        return False


def delete_term(term_id):
    with _lock:
        data = _read()
        before = len(data.get("dictionary", []))
        data["dictionary"] = [t for t in data.get("dictionary", []) if t["id"] != term_id]
        _write(data)
        return len(data["dictionary"]) < before


def touch_term(term_id):
    with _lock:
        data = _read()
        for t in data.get("dictionary", []):
            if t["id"] == term_id:
                t["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _write(data)
                return
        return


# ── Snippets ──────────────────────────────────────────────────

def get_snippets():
    with _lock:
        return _read().get("snippets", [])


def add_snippet(trigger, content):
    with _lock:
        data = _read()
        snippet = {
            "id": _gen_id(),
            "trigger": trigger,
            "content": content,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data.setdefault("snippets", []).insert(0, snippet)
        _write(data)
        return snippet


def update_snippet(snippet_id, trigger, content):
    with _lock:
        data = _read()
        for s in data.get("snippets", []):
            if s["id"] == snippet_id:
                s["trigger"] = trigger
                s["content"] = content
                _write(data)
                return True
        return False


def delete_snippet(snippet_id):
    with _lock:
        data = _read()
        before = len(data.get("snippets", []))
        data["snippets"] = [s for s in data.get("snippets", []) if s["id"] != snippet_id]
        _write(data)
        return len(data["snippets"]) < before


# ── Notes ─────────────────────────────────────────────────────

def get_notes():
    with _lock:
        return _read().get("notes", [])


def add_note(text):
    with _lock:
        data = _read()
        note = {
            "id": _gen_id(),
            "text": text,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data.setdefault("notes", []).insert(0, note)
        _write(data)
        return note


def delete_note(note_id):
    with _lock:
        data = _read()
        before = len(data.get("notes", []))
        data["notes"] = [n for n in data.get("notes", []) if n["id"] != note_id]
        _write(data)
        return len(data["notes"]) < before


# ── Style ─────────────────────────────────────────────────────

def get_style():
    with _lock:
        data = _read()
        return {
            "styles": data.get("style", DEFAULT_DATA["style"]),
            "active_context": data.get("active_style_context", "personal"),
        }


def save_style(context, formality, punctuation, capitalization):
    with _lock:
        data = _read()
        if "style" not in data:
            data["style"] = dict(DEFAULT_DATA["style"])
        data["style"][context] = {
            "formality": formality,
            "punctuation": punctuation,
            "capitalization": capitalization,
        }
        _write(data)
        return True


def set_active_style_context(context):
    with _lock:
        data = _read()
        data["active_style_context"] = context
        _write(data)


# ── Settings ──────────────────────────────────────────────────

def get_settings():
    with _lock:
        data = _read()
        return data.get("settings", dict(DEFAULT_DATA["settings"]))


def set_setting(key, value):
    with _lock:
        data = _read()
        if "settings" not in data:
            data["settings"] = dict(DEFAULT_DATA["settings"])
        data["settings"][key] = value
        _write(data)


# ── History ───────────────────────────────────────────────────

def get_history():
    with _lock:
        return _read().get("history", [])


def add_history_entry(text):
    with _lock:
        data = _read()
        # Respect privacy mode
        if data.get("settings", {}).get("privacy_mode", False):
            return None
        entry = {
            "time": time.strftime("%I:%M %p"),
            "text": text,
            "date": time.strftime("%Y-%m-%d"),
        }
        data.setdefault("history", []).insert(0, entry)
        # Keep max 200
        data["history"] = data["history"][:200]
        _write(data)
        return entry


def clear_history():
    with _lock:
        data = _read()
        data["history"] = []
        _write(data)


# ── Profile ───────────────────────────────────────────────────

def get_profile():
    with _lock:
        return _read().get("profile", dict(DEFAULT_DATA["profile"]))


def update_profile(first_name=None, last_name=None, avatar_style=None):
    with _lock:
        data = _read()
        if "profile" not in data:
            data["profile"] = dict(DEFAULT_DATA["profile"])
        if first_name is not None:
            data["profile"]["first_name"] = first_name
        if last_name is not None:
            data["profile"]["last_name"] = last_name
        if avatar_style is not None:
            data["profile"]["avatar_style"] = avatar_style
        _write(data)
        return data["profile"]


# ── Word Usage ────────────────────────────────────────────────

def _current_week_start():
    """Return the Monday of the current week as 'YYYY-MM-DD'."""
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    return monday.isoformat()


def get_word_usage():
    with _lock:
        data = _read()
        usage = data.get("word_usage", dict(DEFAULT_DATA["word_usage"]))
        # Auto-reset if we're in a new week
        current_monday = _current_week_start()
        if usage.get("week_start") != current_monday:
            usage["count"] = 0
            usage["week_start"] = current_monday
            data["word_usage"] = usage
            _write(data)
        return usage


def add_words(n):
    with _lock:
        data = _read()
        usage = data.get("word_usage", dict(DEFAULT_DATA["word_usage"]))
        # Reset if new week
        current_monday = _current_week_start()
        if usage.get("week_start") != current_monday:
            usage["count"] = 0
            usage["week_start"] = current_monday
        usage["count"] = usage.get("count", 0) + n
        data["word_usage"] = usage
        _write(data)
        return usage


def reset_word_usage():
    with _lock:
        data = _read()
        data["word_usage"] = {"count": 0, "week_start": _current_week_start()}
        _write(data)


# ── Danger zone ───────────────────────────────────────────────

def delete_all_data():
    with _lock:
        _write(dict(DEFAULT_DATA))


def is_privacy_mode():
    with _lock:
        data = _read()
        return data.get("settings", {}).get("privacy_mode", False)


# ── Term usage tracking (frequency boosting) ────────────────────

def increment_term_usage(term_id):
    """Increment use_count for a dictionary term."""
    with _lock:
        data = _read()
        for t in data.get("dictionary", []):
            if t["id"] == term_id:
                t["use_count"] = t.get("use_count", 0) + 1
                t["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _write(data)
                return t["use_count"]
        return 0


def get_dictionary_sorted_by_usage():
    """Return dictionary terms sorted by use_count descending."""
    with _lock:
        terms = _read().get("dictionary", [])
        return sorted(terms, key=lambda t: t.get("use_count", 0), reverse=True)


# ── App style map ────────────────────────────────────────────────

def get_app_style_map():
    with _lock:
        data = _read()
        return data.get("app_style_map", DEFAULT_DATA.get("app_style_map", {}))


def set_app_style(bundle_id, context):
    """Map a bundle_id to a style context."""
    with _lock:
        data = _read()
        if "app_style_map" not in data:
            data["app_style_map"] = {}
        data["app_style_map"][bundle_id] = context
        _write(data)


def delete_app_style(bundle_id):
    with _lock:
        data = _read()
        mapping = data.get("app_style_map", {})
        if bundle_id in mapping:
            del mapping[bundle_id]
            data["app_style_map"] = mapping
            _write(data)
            return True
        return False


# ── Analytics ────────────────────────────────────────────────────

def record_analytics(word_count, bundle_id=""):
    """Record analytics for a transcription."""
    with _lock:
        data = _read()
        analytics = data.get("analytics", {"by_app": {}, "by_date": {}, "by_hour": {}})

        # By app
        if bundle_id:
            app_stats = analytics.get("by_app", {})
            app_stats[bundle_id] = app_stats.get(bundle_id, 0) + word_count
            analytics["by_app"] = app_stats

        # By date
        today = time.strftime("%Y-%m-%d")
        date_stats = analytics.get("by_date", {})
        date_stats[today] = date_stats.get(today, 0) + word_count
        analytics["by_date"] = date_stats

        # By hour
        hour = time.strftime("%H")
        hour_stats = analytics.get("by_hour", {})
        hour_stats[hour] = hour_stats.get(hour, 0) + word_count
        analytics["by_hour"] = hour_stats

        data["analytics"] = analytics
        _write(data)


def get_analytics():
    with _lock:
        data = _read()
        return data.get("analytics", {"by_app": {}, "by_date": {}, "by_hour": {}})

import webview
import threading
import time
import os
import sys
import json
import re
import difflib
import traceback
import webbrowser
import requests
import Quartz
from engine.audio import AudioRecorder
from engine.keyboard import KeyboardController, hotkey_to_display
from engine import storage
from engine.text_processing import (
    remove_fillers,
    dictate_punctuation,
    detect_self_correction,
    format_list,
    apply_code_casing,
    apply_code_punctuation,
)
from engine.dev_terms import DEV_TERMS

LOG_PATH = os.path.join(os.path.expanduser("~"), ".voxeasy", "error.log")


def log_error(msg):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")


API_URL = os.getenv("VOX_API_URL", "https://unicords-voxeasy-app.ujamzy.easypanel.host")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".voxeasy", "config.json")
DEFAULT_HOTKEY = "<fn>"


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f)


def load_token():
    return load_config().get("token")


def save_token(token):
    config = load_config()
    config["token"] = token
    save_config(config)


def clear_token():
    config = load_config()
    config.pop("token", None)
    save_config(config)


def load_language():
    return load_config().get("language", "auto")


def save_language_config(lang):
    config = load_config()
    config["language"] = lang
    save_config(config)


def load_hotkey():
    return load_config().get("hotkey", DEFAULT_HOTKEY)


def save_hotkey_config(hotkey_str):
    config = load_config()
    config["hotkey"] = hotkey_str
    save_config(config)


_WHISPER_HALLUCINATIONS = {
    "thank you", "thanks", "thanks for watching", "you", "yeah",
    "bye", "goodbye", "okay", "ok", "hmm", "uh", "um",
    "gracias", "gracias por ver", "subtitulos", "amara.org",
    "si", "no", "hey", "hola", "adios",
    "thank you for watching", "see you next time",
    "please subscribe", "like and subscribe",
}


class ApiBridge:
    """Exposed to JS as window.pywebview.api"""

    def __init__(self):
        self.window = None
        self.indicator = None  # floating recording indicator window
        self._quitting = False  # set True when user clicks "Salir"
        self._user_app = None  # the app user was in before dictation
        self._dictating = False  # True during entire dictation pipeline
        self._js_queue = []  # queued JS calls during dictation
        self._rec_start = 0  # timestamp when recording started
        self.recorder = AudioRecorder()
        self.note_recorder = AudioRecorder()  # separate recorder for notes
        self.token = load_token()
        self.hotkey_str = load_hotkey()
        self.language = load_language()
        self.is_recording = False
        self.is_loading = False
        self.is_note_recording = False
        self.history = storage.get_history()
        # Init keyboard controller - hold fn to record, release to process
        self.keyboard = KeyboardController(
            self._on_hotkey_press,
            self._on_hotkey_release,
            self.hotkey_str,
        )

    def set_window(self, window):
        self.window = window
        self._setup_status_bar()

    # ── Focus helpers ──────────────────────────────────────────────

    def _get_frontmost_app(self):
        """Get the currently focused application (before we steal focus)."""
        try:
            from AppKit import NSWorkspace
            return NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            return None

    def _restore_focus(self, prev_app):
        """Give focus back to the previously active application."""
        if prev_app:
            try:
                from AppKit import NSApplicationActivateIgnoringOtherApps
                prev_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            except Exception:
                pass

    # ── JS helper ─────────────────────────────────────────────────

    def _js(self, code):
        """Execute JS on the frontend. During dictation, queue instead of executing."""
        if not self.window:
            return
        if self._dictating:
            # Never touch the main window during dictation — queue for later
            self._js_queue.append(code)
            return
        try:
            self.window.evaluate_js(code)
        except Exception:
            pass

    def _flush_js_queue(self):
        """Flush all queued JS calls (called after dictation is fully done)."""
        while self._js_queue:
            code = self._js_queue.pop(0)
            try:
                self.window.evaluate_js(code)
            except Exception:
                pass

    # ── Status bar (menu bar icon) ────────────────────────────────

    def _setup_status_bar(self):
        """Create macOS menu bar icon so app lives in the top bar.
        Must be scheduled on the main thread via performSelectorOnMainThread."""
        try:
            from AppKit import NSObject
            import objc

            api_ref = self

            class _StatusBarCreator(NSObject):
                @objc.python_method
                def _api(self):
                    return api_ref

                def createStatusBar_(self, _):
                    try:
                        from AppKit import (NSStatusBar, NSVariableStatusItemLength,
                                            NSMenu, NSMenuItem, NSApp, NSImage)

                        api = self._api()
                        api._status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                            NSVariableStatusItemLength
                        )

                        # Use logo as status bar icon (@2x for Retina clarity)
                        icon_path = os.path.join(get_assets_dir(), 'icon_statusbar@2x.png')
                        if not os.path.exists(icon_path):
                            icon_path = os.path.join(get_assets_dir(), 'icon_statusbar.png')
                        if os.path.exists(icon_path):
                            icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
                            icon.setSize_((20, 20))  # point size (macOS scales for Retina)
                            icon.setTemplate_(True)  # adapts to light/dark menu bar
                            api._status_item.button().setImage_(icon)
                        else:
                            api._status_item.setTitle_("V")

                        menu = NSMenu.alloc().init()

                        open_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                            "Abrir Vox Easy", "openWindow:", ""
                        )
                        open_item.setTarget_(self)
                        menu.addItem_(open_item)

                        menu.addItem_(NSMenuItem.separatorItem())

                        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                            "Salir", "quitApp:", "q"
                        )
                        quit_item.setTarget_(self)
                        menu.addItem_(quit_item)

                        api._status_item.setMenu_(menu)
                        print("Status bar created OK", flush=True)
                    except Exception as e:
                        print(f"Status bar inner error: {e}", flush=True)

                def openWindow_(self, sender):
                    api = self._api()
                    api.show_main_window()

                def quitApp_(self, sender):
                    api = self._api()
                    api._quitting = True
                    print("Quit requested from menu bar", flush=True)
                    from AppKit import NSApp
                    NSApp.terminate_(None)

            creator = _StatusBarCreator.alloc().init()
            self._status_creator = creator  # prevent GC
            creator.performSelectorOnMainThread_withObject_waitUntilDone_(
                "createStatusBar:", None, False
            )
        except Exception as e:
            print(f"Status bar setup error: {e}")

    # ── Auth ──────────────────────────────────────────────────────

    def check_auth(self):
        return bool(self.token)

    def login(self, email, password):
        if not email or not password:
            return {"ok": False, "error": "Completa todos los campos"}
        try:
            resp = requests.post(
                f"{API_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["token"]
                save_token(self.token)
                return {"ok": True}
            else:
                try:
                    detail = resp.json().get("detail", "Error de autenticacion")
                except Exception:
                    detail = "Error de autenticacion"
                return {"ok": False, "error": detail}
        except requests.ConnectionError:
            return {"ok": False, "error": "No se pudo conectar al servidor"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:60]}

    def register(self, name, email, password):
        if not name or not email or not password:
            return {"ok": False, "error": "Completa todos los campos"}
        try:
            resp = requests.post(
                f"{API_URL}/auth/register",
                json={"name": name, "email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["token"]
                save_token(self.token)
                return {"ok": True}
            else:
                try:
                    detail = resp.json().get("detail", "Error al crear cuenta")
                except Exception:
                    detail = "Error al crear cuenta"
                return {"ok": False, "error": detail}
        except requests.ConnectionError:
            return {"ok": False, "error": "No se pudo conectar al servidor"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:60]}

    def logout(self):
        clear_token()
        self.token = None

    # ── Info ──────────────────────────────────────────────────────

    def get_user_info(self):
        if not self.token:
            return None
        try:
            resp = requests.get(
                f"{API_URL}/me",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "plan": data.get("plan", "free"),
                    "words_used": data.get("words_used", 0),
                    "words_limit": data.get("words_limit", 3000),
                    "email": data.get("email", ""),
                    "name": data.get("name", ""),
                }
        except Exception:
            pass
        return None

    def get_language(self):
        return self.language

    def set_language(self, lang):
        self.language = lang
        save_language_config(lang)

    def get_hotkey(self):
        return hotkey_to_display(self.hotkey_str)

    def get_status(self):
        if self.is_recording:
            return {"state": "recording", "text": "Escuchando..."}
        return {"state": "ready", "text": "Vox listo"}

    # ── Word usage ───────────────────────────────────────────────

    def get_word_count(self):
        usage = storage.get_word_usage()
        is_pro = False
        try:
            info = self.get_user_info()
            if info and info.get("plan") == "pro":
                is_pro = True
        except Exception:
            pass
        return {"count": usage.get("count", 0), "limit": 3000, "is_pro": is_pro}

    def _can_dictate(self):
        """Return True if user can dictate (Pro or under word limit)."""
        try:
            info = self.get_user_info()
            if info and info.get("plan") == "pro":
                return True
        except Exception:
            pass
        usage = storage.get_word_usage()
        return usage.get("count", 0) < 3000

    # ── License ───────────────────────────────────────────────────

    def activate_license(self, key):
        if not key:
            return {"ok": False, "error": "Ingresa una clave"}
        try:
            resp = requests.post(
                f"{API_URL}/activate",
                json={"license_key": key},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10,
            )
            if resp.status_code == 200:
                return {"ok": True}
            else:
                try:
                    msg = resp.json().get("detail", "Clave invalida")
                except Exception:
                    msg = "Clave invalida"
                return {"ok": False, "error": msg}
        except requests.ConnectionError:
            return {"ok": False, "error": "Sin conexion al servidor"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:50]}

    # ── Permissions ─────────────────────────────────────────────

    def check_accessibility(self):
        try:
            from ApplicationServices import AXIsProcessTrusted
            return AXIsProcessTrusted()
        except Exception:
            return False

    def request_accessibility(self):
        try:
            from ApplicationServices import AXIsProcessTrustedWithOptions
            AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
        except Exception:
            import subprocess
            subprocess.Popen([
                'open',
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
            ])

    def request_microphone(self):
        try:
            import AVFoundation
            AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                AVFoundation.AVMediaTypeAudio, lambda granted: None
            )
        except Exception:
            pass

    def start_keyboard(self):
        if self.keyboard and not self.keyboard._tap:
            self.keyboard.start_listening()

    # ── External links ────────────────────────────────────────────

    def open_upgrade(self):
        webbrowser.open("https://voxeasy.com/#pricing")

    def open_website(self):
        webbrowser.open("https://voxeasy.com")

    def show_main_window(self):
        """Show the main window (called from menu bar)."""
        if self.window:
            self.window.show()
            try:
                from AppKit import NSApp
                NSApp.activateIgnoringOtherApps_(True)
            except Exception:
                pass
            self._sync_ui()

    def _sync_ui(self):
        """Push fresh state to frontend when window becomes visible.
        Uses evaluate_js directly (not _js) to bypass the dictation queue."""
        try:
            # Refresh history from storage in case it changed
            self.history = storage.get_history()
            entries_json = json.dumps(self.history[:50], ensure_ascii=False)
            self.window.evaluate_js(f"updateHistory({entries_json});")
            wc = self.get_word_count()
            self.window.evaluate_js(f"updateWordUsage({wc['count']}, {wc['limit']});")
            self.window.evaluate_js("updateStatus('ready', 'Vox listo', 'Esperando comando de voz...');")
            info = self.get_user_info()
            if info:
                plan = info.get("plan", "free")
                used = info.get("words_used", 0)
                limit = info.get("words_limit", 3000)
                self.window.evaluate_js(f"updatePlan('{plan}', {used}, {limit});")
        except Exception:
            pass

    # ── Hotkey capture ────────────────────────────────────────────
    # Key capture is done in JavaScript (keydown/keyup in the modal)
    # to avoid creating a second pynput listener which crashes on
    # macOS 26+ due to TSMGetInputSourceProperty requiring main queue.

    def start_hotkey_capture(self):
        def on_partial(display):
            safe = display.replace("'", "\\'")
            self._js(f"updateHotkeyPartial('{safe}');")

        def on_complete(config_str, display):
            safe = display.replace("'", "\\'")
            self._js(f"updateHotkeyComplete('{safe}');")

        if self.keyboard:
            self.keyboard.start_capture(on_partial, on_complete)

    def save_hotkey(self):
        if self.keyboard:
            config_str = self.keyboard.stop_capture()
            if config_str:
                self.hotkey_str = config_str
                save_hotkey_config(config_str)
                self.keyboard.update_hotkey(config_str)

    def cancel_hotkey_capture(self):
        if self.keyboard:
            self.keyboard.stop_capture()

    # ── Dictation (hold-to-record) ──────────────────────────────

    def _show_indicator(self):
        """Show indicator at bottom center of screen without stealing focus."""
        if not self.indicator:
            return
        try:
            # Hide main window BEFORE showing indicator — otherwise macOS
            # activates the app and brings the main window to front too
            if self.window:
                self.window.hide()
            # Position at bottom center of the main display
            screen_w = Quartz.CGDisplayPixelsWide(Quartz.CGMainDisplayID())
            screen_h = Quartz.CGDisplayPixelsHigh(Quartz.CGMainDisplayID())
            ind_w, ind_h = 340, 64
            x = (screen_w - ind_w) // 2
            y = screen_h - ind_h - 40  # 40px from bottom edge
            self.indicator.move(x, y)
            self.indicator.show()
            time.sleep(0.05)
            # Give focus back to user's app
            self._restore_focus(self._user_app)
        except Exception as e:
            print(f"Indicator show error: {e}", flush=True)

    def _hide_indicator(self):
        """Hide indicator without stealing focus."""
        if not self.indicator:
            return
        try:
            self.indicator.hide()
            print("[indicator] hide() called", flush=True)
        except Exception as e:
            print(f"Indicator hide error: {e}", flush=True)

    def _on_hotkey_press(self):
        if self.is_loading or self.is_recording:
            return
        if not self.token:
            self._js('showLoginRequired();')
            return
        try:
            # Save the app user is in BEFORE anything else
            self._user_app = self._get_frontmost_app()
            self._dictating = True
            self.is_recording = True
            self._rec_start = time.time()
            self.recorder.start_recording()
            self._js("updateStatus('recording', 'Escuchando...', 'Manten presionado... suelta para procesar');")
            self._show_indicator()
            # Start feeding real audio levels to the indicator
            threading.Thread(target=self._feed_levels, daemon=True).start()
        except Exception as e:
            print(f"Hotkey press error: {e}", flush=True)
            self.is_recording = False
            self._dictating = False

    def _feed_levels(self):
        """Push real-time audio RMS levels to the indicator visualizer."""
        time.sleep(0.3)  # wait for indicator webview to load
        while self.is_recording and self.indicator:
            try:
                # Read the full bar buffer snapshot
                bars = list(self.recorder.level_buffer)
                # Reorder so the most recent value is on the right
                idx = self.recorder._buf_idx % 16
                ordered = bars[idx:] + bars[:idx]
                arr = "[" + ",".join(f"{v:.3f}" for v in ordered) + "]"
                self.indicator.evaluate_js(f"setBars({arr})")
            except Exception:
                break  # indicator was hidden/destroyed, stop feeding
            time.sleep(0.05)  # ~20fps

    def _on_hotkey_release(self):
        if not self.is_recording:
            return
        self.is_recording = False
        hold_duration = time.time() - self._rec_start
        # Let _feed_levels thread exit before touching windows
        time.sleep(0.1)
        self._hide_indicator()
        # Force focus back to user's app after hiding all our windows
        time.sleep(0.05)
        self._restore_focus(self._user_app)

        # Too short — discard recording silently
        if hold_duration < 0.5:
            print(f"[dictation] Skipped: hold too short ({hold_duration:.2f}s)", flush=True)
            self.recorder.stop_recording()  # discard buffer
            self._dictating = False
            self._js_queue.clear()
            return

        self._js("updateStatus('processing', 'Procesando...', 'Enviando audio al servidor...');")
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        self.is_loading = True
        try:
            self._process_audio_inner()
        except Exception as e:
            print(f"Process audio error: {e}", flush=True)
        finally:
            # Dictation pipeline is done — end dictating mode
            self._dictating = False
            self.is_loading = False
            # Discard queued JS updates — they would steal focus via evaluate_js()
            self._js_queue.clear()

    def _build_whisper_prompt(self):
        """Build Whisper prompt with dictionary terms (sorted by usage) for better recognition."""
        base = "Transcripcion de dictado por voz."
        vocab_words = []
        try:
            # Terms sorted by use_count descending (most-used first)
            terms = storage.get_dictionary_sorted_by_usage()
            vocab_words = [t["word"] for t in terms[:50]]
        except Exception:
            pass

        # If dev mode is active, append DEV_TERMS (up to 30, no duplicates)
        try:
            if self._is_dev_mode_active():
                existing = {w.lower() for w in vocab_words}
                added = 0
                for dt in DEV_TERMS:
                    if dt.lower() not in existing and added < 30:
                        vocab_words.append(dt)
                        existing.add(dt.lower())
                        added += 1
        except Exception:
            pass

        if vocab_words:
            terms_str = ", ".join(vocab_words)
            return f"{base} Vocabulario: {terms_str}."
        return base

    def _apply_snippet_expansion(self, text):
        """Expand snippet triggers in transcribed text (exact match + fuzzy fallback)."""
        try:
            snippets = storage.get_snippets()
            # Pass 1: exact match (existing behavior, highest priority)
            for snippet in snippets:
                trigger = snippet.get("trigger", "")
                content = snippet.get("content", "")
                if trigger and trigger.lower() in text.lower():
                    text = re.sub(re.escape(trigger), content, text, flags=re.IGNORECASE)
                    return text  # one expansion per transcription

            # Pass 2: fuzzy match with sliding window
            words = text.split()
            for snippet in snippets:
                trigger = snippet.get("trigger", "")
                content = snippet.get("content", "")
                if not trigger:
                    continue
                trigger_words = trigger.split()
                window_size = len(trigger_words)
                if window_size == 0 or window_size > len(words):
                    continue
                for i in range(len(words) - window_size + 1):
                    window = " ".join(words[i:i + window_size])
                    ratio = difflib.SequenceMatcher(None, trigger.lower(), window.lower()).ratio()
                    if ratio >= 0.75:
                        words[i:i + window_size] = [content]
                        return " ".join(words)
        except Exception:
            pass
        return text

    def _apply_style_transforms(self, text):
        """Apply style transforms (capitalization, punctuation) to transcribed text."""
        try:
            style_data = storage.get_style()
            ctx = style_data.get("active_context", "personal")
            styles = style_data.get("styles", {})
            style = styles.get(ctx, {})

            # Punctuation: remove if off
            if not style.get("punctuation", True):
                text = re.sub(r'[.,;:!?¿¡…—\-()"\'\[\]{}]', '', text)
                text = re.sub(r'\s+', ' ', text).strip()

            # Capitalization
            cap = style.get("capitalization", "sentence")
            if cap == "uppercase":
                text = text.upper()
            elif cap == "lowercase":
                text = text.lower()
            elif cap == "title":
                text = text.title()
            # "sentence" is the default from Whisper, no change needed
        except Exception:
            pass
        return text

    def _is_hallucination(self, text):
        """Detect common Whisper hallucination phrases (noise → fake text)."""
        cleaned = text.strip().rstrip('.!?,').lower()
        if cleaned in _WHISPER_HALLUCINATIONS:
            print(f"[hallucination] Blocked known phrase: '{text}'", flush=True)
            return True
        # If language is Latin-script based, reject non-Latin output (Arabic, CJK, etc.)
        latin_langs = {"es", "en", "fr", "de", "it", "pt", "ca", "nl", "auto"}
        if self.language in latin_langs:
            import unicodedata
            non_latin = sum(1 for c in cleaned if c.isalpha() and
                           not ('LATIN' in unicodedata.name(c, '') or c in 'ñáéíóúüàèìòùâêîôû'))
            if non_latin > len(cleaned) * 0.3:
                print(f"[hallucination] Blocked non-Latin text: '{text}'", flush=True)
                return True
        return False

    def _get_frontmost_bundle_id(self):
        """Get the bundle identifier of the frontmost app (saved during hotkey press)."""
        try:
            if self._user_app:
                return self._user_app.bundleIdentifier()
        except Exception:
            pass
        return ""

    def _is_dev_mode_active(self):
        """Check if dev mode should be active (global toggle or per-app)."""
        try:
            settings = storage.get_settings()
            if settings.get("dev_mode", False):
                return True
            dev_apps = settings.get("dev_mode_apps", [])
            bundle_id = self._get_frontmost_bundle_id()
            if bundle_id and bundle_id in dev_apps:
                return True
        except Exception:
            pass
        return False

    def _get_style_context_for_app(self):
        """Return style context based on frontmost app, or None to use default."""
        try:
            bundle_id = self._get_frontmost_bundle_id()
            if bundle_id:
                app_map = storage.get_app_style_map()
                return app_map.get(bundle_id)
        except Exception:
            pass
        return None

    def _track_term_usage(self, text):
        """Scan transcribed text for dictionary terms and increment their use_count."""
        try:
            terms = storage.get_dictionary()
            text_lower = text.lower()
            for t in terms:
                word = t.get("word", "")
                if word and word.lower() in text_lower:
                    storage.increment_term_usage(t["id"])
        except Exception:
            pass

    def _record_analytics(self, text, bundle_id=""):
        """Record analytics for a transcription."""
        try:
            word_count = len(text.split())
            storage.record_analytics(word_count, bundle_id)
        except Exception:
            pass

    def _process_audio_inner(self):
        audio_buf = self.recorder.stop_recording()
        if not audio_buf:
            self._js("updateStatus('ready', 'No se detecto voz', '');")
            return

        # Check audio has actual speech (not silence/noise)
        has_voice, duration, rms = AudioRecorder.has_speech(audio_buf)
        print(f"[audio] duration={duration:.2f}s, rms={rms:.0f}, has_voice={has_voice}", flush=True)
        if not has_voice:
            self._js("updateStatus('ready', 'No se detecto voz', '');")
            return

        # Check word limit before transcribing
        if not self._can_dictate():
            self._js("showWordLimitModal();")
            return

        self._js("updateStatus('processing', 'Transcribiendo...', '');")
        try:
            form_data = {"temperature": "0"}
            if self.language and self.language != "auto":
                form_data["language"] = self.language
            form_data["prompt"] = self._build_whisper_prompt()
            print(f"[transcribe] language={self.language}, form_data={form_data}", flush=True)

            resp = requests.post(
                f"{API_URL}/transcribe",
                files={"file": ("audio.wav", audio_buf, "audio/wav")},
                data=form_data,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                text = data.get("text", "")
                remaining = data.get("words_remaining", 0)

                if text and not self._is_hallucination(text):
                    lang = self.language or "es"
                    settings = storage.get_settings()

                    # ── NEW PIPELINE ──────────────────────────────
                    # 1. Self-correction (runs first on raw Whisper output)
                    text = detect_self_correction(text, lang)

                    # 2. List formatting
                    text = format_list(text, lang)

                    # 3. Punctuation: dev mode uses code punctuation,
                    #    normal mode uses spoken punctuation dictation
                    dev_mode = self._is_dev_mode_active()
                    if dev_mode:
                        text = apply_code_casing(text)
                        text = apply_code_punctuation(text)
                    elif settings.get("punctuation_dictation", True):
                        text = dictate_punctuation(text, lang)

                    # 4. Filler removal
                    if settings.get("filler_removal", True):
                        text = remove_fillers(text, lang)

                    # 5. Snippet expansion (with fuzzy matching)
                    text = self._apply_snippet_expansion(text)

                    # 6. Style transforms (with per-app override)
                    app_ctx = self._get_style_context_for_app()
                    if app_ctx:
                        original_ctx = storage.get_style().get("active_context", "personal")
                        storage.set_active_style_context(app_ctx)
                        text = self._apply_style_transforms(text)
                        storage.set_active_style_context(original_ctx)
                    else:
                        text = self._apply_style_transforms(text)

                    # 7. Track term usage (frequency boosting)
                    self._track_term_usage(text)

                    # 8. Record analytics
                    bundle_id = self._get_frontmost_bundle_id()
                    self._record_analytics(text, bundle_id)
                    # ── END PIPELINE ──────────────────────────────

                    # Ensure user's app has focus before typing
                    self._restore_focus(self._user_app)
                    time.sleep(0.1)

                    # TYPE FIRST — minimum latency to the user
                    self.keyboard.type_text(text)

                    # Then update UI in background
                    ts = time.strftime("%I:%M %p")
                    entry = {"time": ts, "text": text, "date": time.strftime("%Y-%m-%d")}
                    self.history.insert(0, entry)
                    if len(self.history) > 50:
                        self.history = self.history[:50]
                    # Persist to storage (respects privacy mode)
                    storage.add_history_entry(text)
                    self._push_history()

                    # Track word usage locally
                    word_count = len(text.split())
                    usage = storage.add_words(word_count)
                    wc = usage.get("count", 0)
                    self._js(f"updateWordUsage({wc}, 3000);")

                    if remaining >= 0:
                        sub = f"{remaining} palabras restantes"
                    else:
                        sub = "Pro - uso ilimitado"
                    safe_sub = sub.replace("'", "\\'")
                    self._js(f"updateStatus('done', 'Listo', '{safe_sub}');")
                else:
                    self._js("updateStatus('ready', 'No se detecto voz', '');")

            elif resp.status_code == 403:
                self._js("updateStatus('warning', 'Limite alcanzado', 'Actualiza a Pro en voxeasy.com');")

            elif resp.status_code == 401:
                self._js("updateStatus('error', 'Sesion expirada', '');")
                clear_token()
                self.token = None
                time.sleep(1.5)
                self._js("showLoginRequired();")

            else:
                self._js("updateStatus('error', 'Error del servidor', '');")

        except requests.ConnectionError:
            self._js("updateStatus('error', 'Sin conexion', 'Verifica tu internet');")
        except Exception as e:
            safe_err = str(e)[:40].replace("'", "\\'")
            self._js(f"updateStatus('error', 'Error', '{safe_err}');")


    # ── Dictionary ─────────────────────────────────────────────

    def get_dictionary(self):
        return storage.get_dictionary()

    def add_term(self, word, pronunciation="", context=""):
        if not word:
            return {"ok": False, "error": "Palabra requerida"}
        term = storage.add_term(word, pronunciation, context)
        return {"ok": True, "term": term}

    def update_term(self, term_id, word, pronunciation="", context=""):
        ok = storage.update_term(term_id, word, pronunciation, context)
        return {"ok": ok}

    def delete_term(self, term_id):
        ok = storage.delete_term(term_id)
        return {"ok": ok}

    # ── Snippets ──────────────────────────────────────────────

    def get_snippets(self):
        return storage.get_snippets()

    def add_snippet(self, trigger, content):
        if not trigger or not content:
            return {"ok": False, "error": "Trigger y contenido requeridos"}
        snippet = storage.add_snippet(trigger, content)
        return {"ok": True, "snippet": snippet}

    def update_snippet(self, snippet_id, trigger, content):
        ok = storage.update_snippet(snippet_id, trigger, content)
        return {"ok": ok}

    def delete_snippet(self, snippet_id):
        ok = storage.delete_snippet(snippet_id)
        return {"ok": ok}

    # ── Notes ─────────────────────────────────────────────────

    def get_notes(self):
        return storage.get_notes()

    def add_note(self, text):
        if not text:
            return {"ok": False, "error": "Texto requerido"}
        note = storage.add_note(text)
        return {"ok": True, "note": note}

    def delete_note(self, note_id):
        ok = storage.delete_note(note_id)
        return {"ok": ok}

    def start_note_recording(self):
        if self.is_note_recording or self.is_recording:
            return {"ok": False, "error": "Ya grabando"}
        if not self.token:
            return {"ok": False, "error": "No autenticado"}
        self.is_note_recording = True
        self.note_recorder.start_recording()
        return {"ok": True}

    def stop_note_recording(self):
        if not self.is_note_recording:
            return {"ok": False, "error": "No estaba grabando"}
        self.is_note_recording = False
        threading.Thread(target=self._process_note, daemon=True).start()
        return {"ok": True}

    def _process_note(self):
        try:
            audio_buf = self.note_recorder.stop_recording()
            if not audio_buf:
                self._js("onNoteResult(null, 'No se detecto voz');")
                return

            form_data = {"temperature": "0"}
            if self.language and self.language != "auto":
                form_data["language"] = self.language
            form_data["prompt"] = "Transcripcion de nota de voz."

            resp = requests.post(
                f"{API_URL}/transcribe",
                files={"file": ("audio.wav", audio_buf, "audio/wav")},
                data=form_data,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                text = data.get("text", "")
                if text:
                    note = storage.add_note(text)
                    note_json = json.dumps(note, ensure_ascii=False)
                    self._js(f"onNoteResult({note_json}, null);")
                else:
                    self._js("onNoteResult(null, 'No se detecto voz');")
            else:
                self._js("onNoteResult(null, 'Error del servidor');")
        except Exception as e:
            safe = str(e)[:40].replace("'", "\\'").replace('"', '\\"')
            self._js(f'onNoteResult(null, "{safe}");')

    # ── Style ─────────────────────────────────────────────────

    def get_style(self):
        return storage.get_style()

    def save_style(self, context, formality, punctuation, capitalization):
        storage.save_style(context, formality, punctuation, capitalization)
        return {"ok": True}

    def set_active_style_context(self, context):
        storage.set_active_style_context(context)
        return {"ok": True}

    # ── App Style Map ────────────────────────────────────────

    def get_app_style_map(self):
        return storage.get_app_style_map()

    def set_app_style(self, bundle_id, context):
        if not bundle_id or not context:
            return {"ok": False, "error": "Bundle ID y contexto requeridos"}
        storage.set_app_style(bundle_id, context)
        return {"ok": True}

    def delete_app_style(self, bundle_id):
        ok = storage.delete_app_style(bundle_id)
        return {"ok": ok}

    # ── Analytics ─────────────────────────────────────────────

    def get_analytics(self):
        return storage.get_analytics()

    # ── Dev Mode Apps ─────────────────────────────────────────

    def add_dev_mode_app(self, bundle_id):
        if not bundle_id:
            return {"ok": False, "error": "Bundle ID requerido"}
        settings = storage.get_settings()
        apps = settings.get("dev_mode_apps", [])
        if bundle_id not in apps:
            apps.append(bundle_id)
            storage.set_setting("dev_mode_apps", apps)
        return {"ok": True}

    def remove_dev_mode_app(self, bundle_id):
        settings = storage.get_settings()
        apps = settings.get("dev_mode_apps", [])
        if bundle_id in apps:
            apps.remove(bundle_id)
            storage.set_setting("dev_mode_apps", apps)
        return {"ok": True}

    # ── Settings ──────────────────────────────────────────────

    def get_settings(self):
        return storage.get_settings()

    def set_setting(self, key, value):
        storage.set_setting(key, value)
        if key == "launch_at_login":
            self._set_launch_at_login(value)
        elif key == "show_in_dock":
            self._set_show_in_dock(value)
        return {"ok": True}

    def _get_app_path(self):
        """Get the .app bundle path if running as packaged app, else script path."""
        if getattr(sys, 'frozen', False):
            # PyInstaller: sys.executable = /path/to/Vox Easy.app/Contents/MacOS/Vox Easy
            exe = os.path.realpath(sys.executable)
            # Walk up to find the .app bundle
            parts = exe.split(os.sep)
            for i, part in enumerate(parts):
                if part.endswith('.app'):
                    return os.sep + os.path.join(*parts[1:i+1])
            return exe
        return os.path.abspath(sys.argv[0])

    def _set_launch_at_login(self, enabled):
        try:
            import subprocess
            app_path = self._get_app_path()
            app_name = os.path.splitext(os.path.basename(app_path))[0] if app_path.endswith('.app') else "Vox Easy"
            print(f"[launch_at_login] enabled={enabled}, app_path={app_path}, app_name={app_name}", flush=True)
            if enabled:
                result = subprocess.run([
                    'osascript', '-e',
                    f'tell application "System Events" to make login item at end with properties {{path:"{app_path}", hidden:false}}'
                ], capture_output=True, text=True)
                print(f"[launch_at_login] add result: rc={result.returncode}, out={result.stdout}, err={result.stderr}", flush=True)
            else:
                result = subprocess.run([
                    'osascript', '-e',
                    f'tell application "System Events" to delete login item "{app_name}"'
                ], capture_output=True, text=True)
                print(f"[launch_at_login] remove result: rc={result.returncode}, out={result.stdout}, err={result.stderr}", flush=True)
        except Exception as e:
            print(f"[launch_at_login] error: {e}", flush=True)

    def _set_show_in_dock(self, visible):
        try:
            from AppKit import NSApp, NSApplicationActivationPolicyRegular, NSApplicationActivationPolicyAccessory
            if visible:
                NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            else:
                NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        except Exception as e:
            print(f"Show in dock error: {e}")

    # ── Profile ───────────────────────────────────────────────

    def get_profile(self):
        return storage.get_profile()

    def update_profile(self, first_name=None, last_name=None, avatar_style=None):
        profile = storage.update_profile(first_name, last_name, avatar_style)
        return {"ok": True, "profile": profile}

    # ── Data management ───────────────────────────────────────

    def get_history(self):
        return storage.get_history()

    def clear_history_data(self):
        storage.clear_history()
        self.history = []
        return {"ok": True}

    def delete_all_data(self):
        storage.delete_all_data()
        self.history = []
        return {"ok": True}

    # ── History push ──────────────────────────────────────────

    def _push_history(self):
        entries_json = json.dumps(self.history[:50], ensure_ascii=False)
        self._js(f"updateHistory({entries_json});")


# ── Entry point ───────────────────────────────────────────────────

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_web_dir():
    return os.path.join(get_base_dir(), 'web')

def get_assets_dir():
    return os.path.join(get_base_dir(), 'assets')


INDICATOR_HTML = '''<!DOCTYPE html>
<html><head>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:transparent;font-family:-apple-system,BlinkMacSystemFont,"Inter",sans-serif;
  display:flex;align-items:flex-end;justify-content:center;height:100vh;
  padding-bottom:4px;-webkit-app-region:drag;cursor:default}
.hud{background:rgba(10,10,10,0.88);backdrop-filter:blur(20px) saturate(180%);
  border-radius:980px;padding:10px 20px;display:flex;align-items:center;gap:12px;
  border:1px solid rgba(192,255,62,0.12);
  box-shadow:0 0 20px rgba(192,255,62,0.15),0 8px 32px rgba(0,0,0,0.5)}
.icon{width:28px;height:28px;border-radius:8px;
  background:rgba(192,255,62,0.1);border:1px solid rgba(192,255,62,0.2);
  display:flex;align-items:center;justify-content:center;flex-shrink:0}
.icon img{width:18px;height:18px;object-fit:contain}
.sep{width:1px;height:20px;background:rgba(255,255,255,0.1);flex-shrink:0}
.bars{display:flex;align-items:center;gap:2px;height:24px}
.bar{width:3px;border-radius:99px;background:#C0FF3E;transition:height 0.08s ease,opacity 0.08s ease;
  min-height:3px}
.status{display:flex;align-items:center;gap:6px;padding-left:4px;flex-shrink:0}
.ping{position:relative;display:flex;align-items:center;justify-content:center}
.ping-outer{position:absolute;width:10px;height:10px;border-radius:50%;
  background:#C0FF3E;opacity:0.5;animation:ping 1.2s cubic-bezier(0,0,0.2,1) infinite}
.ping-inner{width:7px;height:7px;border-radius:50%;background:#C0FF3E;position:relative}
.label{font-size:9px;font-weight:700;letter-spacing:0.18em;color:rgba(192,255,62,0.75);
  text-transform:uppercase;white-space:nowrap;font-family:"SF Mono",ui-monospace,monospace}
@keyframes ping{75%,100%{transform:scale(2);opacity:0}}
</style>
</head><body>
<div class="hud">
  <div class="icon"><img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAERlWElmTU0AKgAAAAgAAYdpAAQAAAABAAAAGgAAAAAAA6ABAAMAAAABAAEAAKACAAQAAAABAAAAIKADAAQAAAABAAAAIAAAAACshmLzAAAEBUlEQVRYCeVX2SutURRf5zgZMmceUiJTJ16vFOHBCyVEUWQqb5JHXiRelPgfFCLyYnjxQigkHMODSIZMRTmmDMtaq/vtvnu63zmHcqm7an97Wnut317TPgfgfyeTzgB+NLbq5l85tJFwu6OCX7SA/6ixLiGzNviu/tsBWD56c7PZDFarFTIyMiAqKgpMJhOcnJzAxsYG2Gw2eHt7+6hIxe8yBioqKnBhYQGNaGlpCauqqpBAuoolFQNKOw0MAYSFheHIyIjofXx8xKGhIWxsbMT8/HzMy8vDhoYGHBwcxIeHB+GZmJjAyMhIZyDcB8DK+WZMDCIpKUkJDggIwMDAQDVPSEgQcMy7srKC5CK1RxfUj90D4OHhgWNjYywPe3p6kPyNvr6+2N7ejuRztNvt0tbX12XN399flHR3d8sZtoqDYm3uHgD2ORODYOUsrK6uTtbOz89xZmZGGo+ZNjc3MTU1Vfi6urrETZ8GYLFYcHl5Ge/u7jAxMVFDjqGhoVhcXIxsfk14SEgIdnR0CAjKBAwODlZ7Go9D79oC6enpSCmFw8PDIqywsBCbm5uV4OTkZGRTV1dXq7XOzk4B0dbWJmvx8fHIa+Hh4YrnNxDXAGpqakRYfX29HN7Z2cHLy0v08vLClJQUPDs7k/3Z2VklPCgoCNkdbAV2WW1trfBUVlYqHkcAhpUwLi6OeAEODw+Bggt4vra2Bk9PT0C3hoiICGhpaYGSkhLh48/NzQ1QQALdHChY4fr6WvbIXYrHcWAIYHV1Febm5mB3d1eEeXp6wu3trZynOJCe8l0q3/z8PNBtZe3+/h4ofoD5n5+fZY3nRmQIYHJyErKzs+H4+FgAUEoCFRqRw7cj24qCmJgYyMrKgszMTNkjF4nyl5cX4LLNxLxGZAggOjoaKA2BBbIJueZfXV2JHAoqAUN1QClh1zD19/dDa2urWItdx6TtycThY2ibsrIyEcYPj2byo6MjOe7j4wMUkKKEATJpSqanp4EbE1uN6fT0VPq/fQwBDAwMABUWiYGCggI5u7e3Jz1lBnh7e8Pr6yv4+fEPKVDxwbdnk/f29sL4+Djk5ubC4uKi8Lj6cG46povMR0dHpSZo74D+tSstLZVUa2pqktS7uLjA7e1tVTkNZKo6YBgDGlo2I7uB6gDs7+8DFSCxDFVDYaEHSPqDgwNJTaqCwuss8DTZ3Bu6QGNiM1MhER9zZBcVFUFaWpoEJvNw9DPP1tYWUIGSFGTXfYYMXUDClGumpqaQFGJsbCxSMCIVG+TXkCsfP799fX1/PNn6s7qxcoEeqFsAcnJysLy8XABxLPAvILKCAqhT4mzt8wDcVOBMOe8pAC6DUG+irxh/O4Af9dfsKyz882W+A3IO8+vieiSSAAAAAElFTkSuQmCC" style="width:18px;height:18px" /></div>
  <div class="sep"></div>
  <div class="bars" id="bars"></div>
  <div class="status">
    <div class="ping"><div class="ping-outer"></div><div class="ping-inner"></div></div>
    <span class="label">Grabando</span>
  </div>
</div>
<script>
const N=16,barsEl=document.getElementById("bars"),barEls=[];
const smooth=new Array(N).fill(0);
for(let i=0;i<N;i++){const b=document.createElement("div");
b.className="bar";b.style.height="3px";b.style.opacity="0.25";barsEl.appendChild(b);barEls.push(b)}

function setBars(arr){
  for(let i=0;i<N;i++){
    // Smooth: lerp toward target for fluid motion
    const target=arr[i]||0;
    smooth[i]+=(target-smooth[i])*0.45;
    const v=smooth[i];
    const h=Math.max(3,Math.round(v*28));
    const op=Math.max(0.2,Math.min(1,v*1.3));
    barEls[i].style.height=h+"px";
    barEls[i].style.opacity=op;
    barEls[i].style.boxShadow=v>0.3?"0 0 8px rgba(192,255,62,0.5)":"none";
  }
}
// Fallback for single value
function setLevel(l){const a=new Array(N).fill(l);setBars(a)}
</script>
</body></html>'''


if __name__ == "__main__":
    try:
        api = ApiBridge()
        web_dir = get_web_dir()

        window = webview.create_window(
            'Vox Easy',
            url=os.path.join(web_dir, 'app.html'),
            js_api=api,
            width=960,
            height=640,
            min_size=(800, 500),
            background_color='#0a0a0c',
        )

        # Floating recording indicator (hidden by default, bottom center)
        indicator = webview.create_window(
            '',
            html=INDICATOR_HTML,
            width=340,
            height=64,
            on_top=True,
            frameless=True,
            transparent=True,
            hidden=True,
            resizable=False,
        )
        api.indicator = indicator

        def on_loaded():
            api.set_window(window)
            # Set app icon
            try:
                from AppKit import NSImage, NSApp
                icns_path = os.path.join(get_assets_dir(), 'VoxEasy.icns')
                if os.path.exists(icns_path):
                    icon = NSImage.alloc().initWithContentsOfFile_(icns_path)
                    NSApp.setApplicationIconImage_(icon)
            except Exception as e:
                print(f"App icon error: {e}")

        def on_closing():
            """When user closes main window, hide it instead of quitting.
            But if _quitting is True (from menu bar Salir), allow real quit."""
            if api._quitting:
                print("Quitting for real...", flush=True)
                return True
            print("on_closing fired! Hiding window...", flush=True)
            window.hide()
            return False

        def on_indicator_closing():
            """Prevent indicator from being destroyed unless quitting."""
            if api._quitting:
                return True
            return False

        window.events.loaded += on_loaded
        window.events.closing += on_closing
        indicator.events.closing += on_indicator_closing

        webview.start()
    except Exception as e:
        log_error(f"FATAL: {e}\n{traceback.format_exc()}")
        print(f"Fatal error: {e}", file=sys.stderr)
        raise

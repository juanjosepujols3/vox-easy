"""macOS keyboard controller using CGEventTap for global hotkey detection with fn support."""

import time
import threading
import pyautogui
import Quartz

# ── Modifier flags (same for CGEvent and NSEvent) ──────────────
MOD_FN    = 1 << 23
MOD_CMD   = 1 << 20
MOD_SHIFT = 1 << 17
MOD_CTRL  = 1 << 18
MOD_ALT   = 1 << 19  # Option

# ── Config token -> modifier flag ──────────────────────────────
_CONFIG_TO_FLAG = {
    '<fn>': MOD_FN, '<cmd>': MOD_CMD, '<shift>': MOD_SHIFT,
    '<ctrl>': MOD_CTRL, '<alt>': MOD_ALT,
}

# ── Modifier order for display/config ──────────────────────────
_MOD_ORDER = ['<fn>', '<ctrl>', '<alt>', '<shift>', '<cmd>']
_MOD_DISPLAY = {
    '<fn>': 'fn', '<cmd>': '\u2318', '<shift>': '\u21e7',
    '<ctrl>': '\u2303', '<alt>': '\u2325',
}

# ── macOS virtual keycodes -> character ────────────────────────
_KEYCODE_TO_CHAR = {
    0: 'a', 1: 's', 2: 'd', 3: 'f', 4: 'h', 5: 'g', 6: 'z', 7: 'x',
    8: 'c', 9: 'v', 11: 'b', 12: 'q', 13: 'w', 14: 'e', 15: 'r',
    16: 'y', 17: 't', 18: '1', 19: '2', 20: '3', 21: '4', 22: '6',
    23: '5', 24: '=', 25: '9', 26: '7', 27: '-', 28: '8', 29: '0',
    30: ']', 31: 'o', 32: 'u', 33: '[', 34: 'i', 35: 'p', 37: 'l',
    38: 'j', 39: "'", 40: 'k', 41: ';', 42: '\\', 43: ',', 44: '/',
    45: 'n', 46: 'm', 47: '.', 50: '`',
}

# ── Special keycodes ───────────────────────────────────────────
_KEYCODE_TO_SPECIAL = {
    36: '<enter>', 48: '<tab>', 49: '<space>', 51: '<backspace>', 53: '<esc>',
    122: '<f1>', 120: '<f2>', 99: '<f3>', 118: '<f4>', 96: '<f5>',
    97: '<f6>', 98: '<f7>', 100: '<f8>', 101: '<f9>', 109: '<f10>',
    103: '<f11>', 111: '<f12>', 105: '<f13>', 107: '<f14>', 113: '<f15>',
    106: '<f16>', 64: '<f17>', 79: '<f18>', 80: '<f19>', 90: '<f20>',
}

# ── Modifier keycodes (used in flagsChanged) ───────────────────
_MOD_KEYCODES = {55, 54, 56, 60, 58, 61, 59, 62, 63}

# ── Display map for special keys ───────────────────────────────
_SPECIAL_DISPLAY = {
    '<enter>': 'Enter', '<tab>': 'Tab', '<space>': 'Space',
    '<backspace>': '\u232b', '<esc>': 'Esc',
}
for _i in range(1, 21):
    _SPECIAL_DISPLAY[f'<f{_i}>'] = f'F{_i}'


# ── Helper functions ───────────────────────────────────────────

def _keycode_to_config(keycode):
    if keycode in _KEYCODE_TO_SPECIAL:
        return _KEYCODE_TO_SPECIAL[keycode]
    if keycode in _KEYCODE_TO_CHAR:
        return _KEYCODE_TO_CHAR[keycode]
    return None


def _keycode_to_display(keycode):
    config = _keycode_to_config(keycode)
    if config is None:
        return None
    if config in _SPECIAL_DISPLAY:
        return _SPECIAL_DISPLAY[config]
    return config.upper()


def _flags_to_mods(flags, track_fn=True):
    mods = set()
    if track_fn and (flags & MOD_FN):
        mods.add('<fn>')
    if flags & MOD_CMD:
        mods.add('<cmd>')
    if flags & MOD_SHIFT:
        mods.add('<shift>')
    if flags & MOD_CTRL:
        mods.add('<ctrl>')
    if flags & MOD_ALT:
        mods.add('<alt>')
    return mods


def _parse_hotkey(hotkey_str):
    parts = [p.strip() for p in hotkey_str.split('+')]
    mods = set()
    trigger = None
    for p in parts:
        if p in _CONFIG_TO_FLAG:
            mods.add(p)
        else:
            trigger = p
    return mods, trigger


def hotkey_to_display(hotkey_str):
    display = dict(_MOD_DISPLAY)
    display.update(_SPECIAL_DISPLAY)
    display['<caps_lock>'] = 'CapsLock'
    parts = hotkey_str.split('+')
    result = []
    for p in parts:
        p = p.strip()
        result.append(display.get(p, p.upper()))
    return ' + '.join(result)


# ── KeyboardController (CGEventTap) ───────────────────────────

class KeyboardController:
    def __init__(self, on_activate_callback, on_deactivate_callback=None, hotkey_str='<cmd>+<shift>+v'):
        self.on_activate = on_activate_callback
        self.on_deactivate = on_deactivate_callback
        self.hotkey_str = hotkey_str
        self._required_mods, self._trigger_key = _parse_hotkey(hotkey_str)
        self._track_fn = '<fn>' in self._required_mods
        self._tap = None
        # For modifier-only hotkeys (e.g. just fn)
        self._mod_hotkey_fired = False
        # Capture state (used by settings modal)
        self._capturing = False
        self._capture_on_partial = None
        self._capture_on_complete = None
        self._capture_result = None
        self._capture_last_mods = None
        self._capture_key_pressed = False

    def start_listening(self):
        controller = self

        def _tap_callback(proxy, event_type, event, refcon):
            try:
                # Re-enable if macOS disabled the tap due to timeout
                if event_type in (Quartz.kCGEventTapDisabledByTimeout,
                                  Quartz.kCGEventTapDisabledByUserInput):
                    if controller._tap:
                        Quartz.CGEventTapEnable(controller._tap, True)
                    return event

                keycode = Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventKeycode
                )
                flags = Quartz.CGEventGetFlags(event)

                if controller._capturing:
                    if event_type == Quartz.kCGEventFlagsChanged:
                        controller._capture_flags(flags)
                    elif event_type == Quartz.kCGEventKeyDown:
                        controller._capture_key(keycode, flags)
                    return event

                if event_type == Quartz.kCGEventKeyDown:
                    controller._handle_key_down(keycode, flags)
                elif event_type == Quartz.kCGEventFlagsChanged and controller._trigger_key is None:
                    controller._handle_flags_changed(flags)
            except Exception as e:
                print(f"Tap callback error: {e}", flush=True)

            return event

        def _run_tap():
            mask = (
                (1 << Quartz.kCGEventKeyDown) |
                (1 << Quartz.kCGEventFlagsChanged)
            )

            tap = Quartz.CGEventTapCreate(
                Quartz.kCGSessionEventTap,
                Quartz.kCGHeadInsertEventTap,
                Quartz.kCGEventTapOptionListenOnly,
                mask,
                _tap_callback,
                None,
            )

            if tap is None:
                print("ERROR: No se pudo crear event tap.")
                print("Abre Ajustes > Privacidad > Accesibilidad y agrega la app.")
                return

            controller._tap = tap

            source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
            run_loop = Quartz.CFRunLoopGetCurrent()
            Quartz.CFRunLoopAddSource(run_loop, source, Quartz.kCFRunLoopCommonModes)
            Quartz.CGEventTapEnable(tap, True)

            print(f"Listening for hotkey ({hotkey_to_display(controller.hotkey_str)})...", flush=True)

            # Block this thread processing events
            Quartz.CFRunLoopRun()

        threading.Thread(target=_run_tap, daemon=True).start()

    # ── Hotkey detection ───────────────────────────────────────

    def _handle_key_down(self, keycode, flags):
        key_config = _keycode_to_config(keycode)
        if key_config is None:
            return
        current_mods = _flags_to_mods(flags, track_fn=self._track_fn)
        if key_config == self._trigger_key and current_mods == self._required_mods:
            print("Hotkey triggered!", flush=True)
            self.on_activate()

    def _handle_flags_changed(self, flags):
        """Handle modifier-only hotkeys (e.g. just fn). Supports hold-to-record."""
        current_mods = _flags_to_mods(flags, track_fn=self._track_fn)
        if current_mods == self._required_mods:
            if not self._mod_hotkey_fired:
                self._mod_hotkey_fired = True
                print("Hotkey pressed!", flush=True)
                self.on_activate()
        else:
            if self._mod_hotkey_fired:
                self._mod_hotkey_fired = False
                if self.on_deactivate:
                    print("Hotkey released!", flush=True)
                    self.on_deactivate()

    def update_hotkey(self, new_hotkey_str):
        try:
            self.hotkey_str = new_hotkey_str
            self._required_mods, self._trigger_key = _parse_hotkey(new_hotkey_str)
            self._track_fn = '<fn>' in self._required_mods
            self._mod_hotkey_fired = False
            print(f"Hotkey updated to: {hotkey_to_display(new_hotkey_str)}", flush=True)
        except Exception as e:
            print(f"Error setting hotkey: {e}, reverting to default")
            self.hotkey_str = '<cmd>+<shift>+v'
            self._required_mods, self._trigger_key = _parse_hotkey(self.hotkey_str)
            self._track_fn = '<fn>' in self._required_mods

    # ── Capture mode (for settings modal) ──────────────────────

    def start_capture(self, on_partial, on_complete):
        self._capture_result = None
        self._capture_on_partial = on_partial
        self._capture_on_complete = on_complete
        self._capture_last_mods = None
        self._capture_key_pressed = False
        self._capturing = True

    def stop_capture(self):
        self._capturing = False
        result = self._capture_result
        self._capture_on_partial = None
        self._capture_on_complete = None
        self._capture_result = None
        self._capture_last_mods = None
        self._capture_key_pressed = False
        return result

    def _capture_flags(self, flags):
        mods = _flags_to_mods(flags, track_fn=True)
        if mods:
            if not self._capture_last_mods:
                # New modifier session starting
                self._capture_key_pressed = False
            self._capture_last_mods = frozenset(mods)
            parts = [_MOD_DISPLAY[m] for m in _MOD_ORDER if m in mods]
            if self._capture_on_partial:
                self._capture_on_partial(' + '.join(parts) + ' + ...')
        else:
            # All modifiers released
            if self._capture_last_mods and not self._capture_key_pressed:
                # Modifier-only capture (e.g. just fn)
                mods_set = self._capture_last_mods
                config_parts = [m for m in _MOD_ORDER if m in mods_set]
                display_parts = [_MOD_DISPLAY[m] for m in _MOD_ORDER if m in mods_set]
                self._capture_result = '+'.join(config_parts)
                display_str = ' + '.join(display_parts)
                if self._capture_on_complete:
                    self._capture_on_complete(self._capture_result, display_str)
            elif not self._capture_result and self._capture_on_partial:
                self._capture_on_partial('\u2014')
            self._capture_last_mods = None

    def _capture_key(self, keycode, flags):
        self._capture_key_pressed = True
        if keycode in _MOD_KEYCODES:
            return
        key_config = _keycode_to_config(keycode)
        if key_config is None:
            return
        mods = _flags_to_mods(flags, track_fn=True)
        config_parts = [m for m in _MOD_ORDER if m in mods]
        config_parts.append(key_config)
        display_parts = [_MOD_DISPLAY[m] for m in _MOD_ORDER if m in mods]
        key_display = _keycode_to_display(keycode)
        if key_display:
            display_parts.append(key_display)
        self._capture_result = '+'.join(config_parts)
        display_str = ' + '.join(display_parts)
        if self._capture_on_complete:
            self._capture_on_complete(self._capture_result, display_str)

    # ── Text typing ────────────────────────────────────────────

    def type_text(self, text):
        if not text:
            return
        time.sleep(0.15)
        import subprocess
        # Save user's current clipboard
        old_clip = subprocess.run(['pbpaste'], capture_output=True).stdout
        # Use clipboard + Cmd+V for full Unicode support (accents, ñ, ¿, etc.)
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))
        time.sleep(0.05)
        pyautogui.hotkey('command', 'v')
        # Restore user's original clipboard
        time.sleep(0.15)
        restore = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        restore.communicate(old_clip)
        print(f"Typed: {text}")


if __name__ == "__main__":
    def test_callback():
        print("Action triggered!")

    k = KeyboardController(test_callback, '<fn>')
    k.start_listening()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

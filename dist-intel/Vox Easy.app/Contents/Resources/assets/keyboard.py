from pynput import keyboard
import pyautogui
import threading
import time

class KeyboardController:
    def __init__(self, on_activate_callback):
        self.on_activate = on_activate_callback
        self.hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<cmd>+<shift>+v'),
            on_activate=self._handle_activate
        )
        self.listener = None
        self._is_recording = False

    def _handle_activate(self):
        print("Hotkey triggered!")
        self.on_activate()

    def start_listening(self):
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        print("Listening for hotkey (Cmd+Shift+V)...")

    def _on_press(self, key):
        self.hotkey.press(self.listener.canonical(key))

    def _on_release(self, key):
        self.hotkey.release(self.listener.canonical(key))

    def type_text(self, text):
        if not text:
            return
        
        # Give the user a tiny bit of time to refocus if needed, 
        # though usually it happens in the background.
        time.sleep(0.1)
        pyautogui.write(text)
        print(f"Typed: {text}")

if __name__ == "__main__":
    def test_callback():
        print("Action triggered!")
    
    k = KeyboardController(test_callback)
    k.start_listening()
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

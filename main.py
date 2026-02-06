import customtkinter as ctk
import threading
import time
import os
import json
import requests
from engine.audio import AudioRecorder
from engine.keyboard import KeyboardController

API_URL = os.getenv("VOX_API_URL", "https://voxeasy.com")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".voxeasy", "config.json")


def load_token():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
            return data.get("token")
    return None


def save_token(token):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"token": token}, f)


def clear_token():
    if os.path.exists(CONFIG_PATH):
        os.remove(CONFIG_PATH)


class LoginWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.on_success = on_success

        self.title("Vox - Login")
        self.geometry("350x300")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        ctk.set_appearance_mode("dark")

        frame = ctk.CTkFrame(self, corner_radius=15)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(frame, text="Vox Easy", font=("Inter", 22, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(frame, text="Inicia sesion para continuar", font=("Inter", 12), text_color="gray").pack(pady=(0, 10))

        self.email_entry = ctk.CTkEntry(frame, placeholder_text="Email", width=250)
        self.email_entry.pack(pady=5)

        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Password", show="*", width=250)
        self.password_entry.pack(pady=5)

        self.error_label = ctk.CTkLabel(frame, text="", font=("Inter", 11), text_color="#FF6B6B")
        self.error_label.pack(pady=2)

        self.login_btn = ctk.CTkButton(frame, text="Entrar", command=self.do_login, width=250)
        self.login_btn.pack(pady=5)

        self.register_btn = ctk.CTkButton(frame, text="Crear cuenta", command=self.do_register, width=250, fg_color="transparent", border_width=1)
        self.register_btn.pack(pady=5)

    def do_login(self):
        self._auth_request("/auth/login")

    def do_register(self):
        self._auth_request("/auth/register")

    def _auth_request(self, endpoint):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        if not email or not password:
            self.error_label.configure(text="Completa todos los campos")
            return

        self.login_btn.configure(state="disabled")
        self.register_btn.configure(state="disabled")
        threading.Thread(target=self._send_auth, args=(endpoint, email, password), daemon=True).start()

    def _send_auth(self, endpoint, email, password):
        try:
            resp = requests.post(
                f"{API_URL}{endpoint}",
                json={"email": email, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                save_token(data["token"])
                self.on_success(data["token"])
                self.destroy()
            else:
                detail = resp.json().get("detail", "Error de autenticacion")
                self.error_label.configure(text=detail)
        except requests.ConnectionError:
            self.error_label.configure(text="Sin conexion al servidor")
        except Exception as e:
            self.error_label.configure(text=str(e))
        finally:
            self.login_btn.configure(state="normal")
            self.register_btn.configure(state="normal")


class VoxApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Vox - Invisible Secretary")
        self.geometry("400x150")
        self.attributes("-topmost", True)
        self.overrideredirect(True)

        # Center the window
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - 200
        y = (screen_height // 2) - 300
        self.geometry(f"400x150+{x}+{y}")

        # Appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # UI Elements
        self.frame = ctk.CTkFrame(self, corner_radius=20, border_width=2, border_color="#3B8ED0")
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.label = ctk.CTkLabel(
            self.frame,
            text="Vox is ready",
            font=("Inter", 18, "bold")
        )
        self.label.pack(pady=(20, 5))

        self.status_label = ctk.CTkLabel(
            self.frame,
            text="Press Cmd+Shift+V to start",
            font=("Inter", 12),
            text_color="gray"
        )
        self.status_label.pack(pady=5)

        # Progress bar for "listening" animation
        self.progress = ctk.CTkProgressBar(self.frame, width=300)
        self.progress.pack(pady=10)
        self.progress.set(0)

        # Logic Components
        self.recorder = AudioRecorder()
        self.keyboard = KeyboardController(self.toggle_dictation)
        self.token = load_token()

        self.is_recording = False
        self.is_loading = False

        # Start keyboard listener
        self.keyboard.start_listening()

        # Check auth on startup
        if not self.token:
            self.after(500, self.show_login)
        else:
            self.withdraw()

    def show_login(self):
        self.withdraw()
        LoginWindow(self, self.on_login_success)

    def on_login_success(self, token):
        self.token = token
        self.withdraw()

    def toggle_dictation(self):
        if self.is_loading:
            return

        if not self.token:
            self.deiconify()
            self.label.configure(text="Inicia sesion primero", text_color="#FF6B6B")
            self.after(500, self.show_login)
            return

        if not self.is_recording:
            self.start_dictation()
        else:
            self.stop_dictation()

    def start_dictation(self):
        self.is_recording = True
        self.deiconify()
        self.label.configure(text="Listening...", text_color="#3B8ED0")
        self.status_label.configure(text="Press hotkey again to stop")
        self.progress.start()
        self.recorder.start_recording()

    def stop_dictation(self):
        self.is_recording = False
        self.label.configure(text="Processing...", text_color="#A29BFE")
        self.status_label.configure(text="Enviando audio al servidor...")
        self.progress.stop()
        self.progress.set(1.0)

        threading.Thread(target=self.process_audio, daemon=True).start()

    def process_audio(self):
        audio_path = self.recorder.stop_recording("temp_output.wav")
        if audio_path:
            self.label.configure(text="Transcribiendo...")
            try:
                with open(audio_path, "rb") as f:
                    resp = requests.post(
                        f"{API_URL}/transcribe",
                        files={"file": ("audio.wav", f, "audio/wav")},
                        headers={"Authorization": f"Bearer {self.token}"},
                        timeout=30,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    text = data.get("text", "")
                    remaining = data.get("words_remaining", 0)

                    if text:
                        self.label.configure(text="Typing...", text_color="#55E6C1")
                        if remaining >= 0:
                            self.status_label.configure(text=f"{remaining} palabras restantes esta semana")
                        else:
                            self.status_label.configure(text="Pro - uso ilimitado")
                        self.keyboard.type_text(text)
                    else:
                        self.label.configure(text="No se detecto voz", text_color="gray")

                elif resp.status_code == 403:
                    self.label.configure(text="Limite alcanzado", text_color="#FF6B6B")
                    self.status_label.configure(text="Actualiza a Pro en voxeasy.com")

                elif resp.status_code == 401:
                    self.label.configure(text="Sesion expirada", text_color="#FF6B6B")
                    clear_token()
                    self.token = None
                    self.after(1500, self.show_login)

                else:
                    self.label.configure(text="Error del servidor", text_color="#FF6B6B")

            except requests.ConnectionError:
                self.label.configure(text="Sin conexion", text_color="#FF6B6B")
                self.status_label.configure(text="Verifica tu internet")
            except Exception as e:
                self.label.configure(text="Error", text_color="#FF6B6B")
                self.status_label.configure(text=str(e)[:40])
            finally:
                os.remove(audio_path)

        # Hide after a brief moment
        time.sleep(2)
        self.label.configure(text="Vox is ready", text_color="white")
        self.status_label.configure(text="Press Cmd+Shift+V to start")
        self.progress.set(0)
        self.withdraw()


if __name__ == "__main__":
    app = VoxApp()
    app.mainloop()

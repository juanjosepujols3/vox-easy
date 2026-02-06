import customtkinter as ctk
import threading
import time
import os
from engine.audio import AudioRecorder
from engine.transcriber import Transcriber
from engine.keyboard import KeyboardController

class VoxApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Vox - Invisible Secretary")
        self.geometry("400x150")
        self.attributes("-topmost", True)
        self.overrideredirect(True) # Remove title bar for a floating look
        
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
        self.transcriber = None # Loaded lazily to avoid startup lag
        self.keyboard = KeyboardController(self.toggle_dictation)
        
        self.is_recording = False
        self.is_loading = False

        # Start keyboard listener
        self.keyboard.start_listening()

        # Hide initially, only show when triggered
        self.withdraw()

    def toggle_dictation(self):
        if self.is_loading:
            return

        if not self.is_recording:
            self.start_dictation()
        else:
            self.stop_dictation()

    def start_dictation(self):
        self.is_recording = True
        self.deiconify() # Show window
        self.label.configure(text="Listening...", text_color="#3B8ED0")
        self.status_label.configure(text="Press hotkey again to stop")
        self.progress.start()
        self.recorder.start_recording()

    def stop_dictation(self):
        self.is_recording = False
        self.label.configure(text="Processing...", text_color="#A29BFE")
        self.status_label.configure(text="Converting voice to text")
        self.progress.stop()
        self.progress.set(1.0)
        
        # Process in background thread
        threading.Thread(target=self.process_audio, daemon=True).start()

    def process_audio(self):
        audio_path = self.recorder.stop_recording("temp_output.wav")
        if audio_path:
            # Lazy load transcriber
            if self.transcriber is None:
                self.is_loading = True
                self.label.configure(text="Loading Model...")
                self.transcriber = Transcriber(model_size="tiny")
                self.is_loading = False
            
            self.label.configure(text="Transcribing...")
            text = self.transcriber.transcribe(audio_path)
            
            if text:
                self.label.configure(text="Typing...", text_color="#55E6C1")
                self.keyboard.type_text(text)
                
            os.remove(audio_path)
        
        # Hide after a brief moment
        time.sleep(1)
        self.label.configure(text="Vox is ready", text_color="white")
        self.status_label.configure(text="Press Cmd+Shift+V to start")
        self.progress.set(0)
        self.withdraw()

if __name__ == "__main__":
    app = VoxApp()
    app.mainloop()

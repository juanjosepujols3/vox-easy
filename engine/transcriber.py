from faster_whisper import WhisperModel
import os

class Transcriber:
    def __init__(self, model_size="tiny", device="cpu", compute_type="int8"):
        # We use 'tiny' by default for speed and lower resource usage on laptops
        # Local model storage within the project
        model_path = os.path.join(os.getcwd(), "models")
        if not os.path.exists(model_path):
            os.makedirs(model_path)
            
        print(f"Loading Whisper model: {model_size}...")
        self.model = WhisperModel(
            model_size, 
            device=device, 
            compute_type=compute_type,
            download_root=model_path
        )
        print("Model loaded successfully.")

    def transcribe(self, audio_path):
        if not os.path.exists(audio_path):
            return ""
        
        print(f"Transcribing {audio_path}...")
        segments, info = self.model.transcribe(audio_path, beam_size=5)
        
        text = ""
        for segment in segments:
            text += segment.text + " "
        
        return text.strip()

if __name__ == "__main__":
    # Test script
    import time
    t = Transcriber()
    # Assuming temp_audio.wav exists from audio.py test
    if os.path.exists("temp_audio.wav"):
        start = time.time()
        result = t.transcribe("temp_audio.wav")
        print(f"Result ({time.time()-start:.2f}s): {result}")

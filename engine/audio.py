import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import threading
import queue
import time
import os

class AudioRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self._thread = None

    def _audio_callback(self, indata, frames, time, status):
        if status:
            print(f"Audio status: {status}")
        self.audio_queue.put(indata.copy())

    def start_recording(self):
        if self.recording:
            return
        
        self.recording = True
        self.audio_queue = queue.Queue()
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback
        )
        self.stream.start()
        print("Recording started...")

    def stop_recording(self, output_path="temp_audio.wav"):
        if not self.recording:
            return None
        
        self.recording = False
        self.stream.stop()
        self.stream.close()
        print("Recording stopped.")

        audio_data = []
        while not self.audio_queue.empty():
            audio_data.append(self.audio_queue.get())
        
        if not audio_data:
            return None

        full_audio = np.concatenate(audio_data, axis=0)
        
        # Save to wav file
        wav.write(output_path, self.sample_rate, (full_audio * 32767).astype(np.int16))
        return output_path

if __name__ == "__main__":
    recorder = AudioRecorder()
    recorder.start_recording()
    time.sleep(3)
    path = recorder.stop_recording()
    print(f"Saved to {path}")

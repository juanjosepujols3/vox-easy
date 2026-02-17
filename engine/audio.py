import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import threading
import queue
import time
import os
import io

NUM_BARS = 16


class AudioRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self._thread = None
        self.current_level = 0.0
        # Ring buffer of recent RMS levels for the visualizer
        self.level_buffer = [0.0] * NUM_BARS
        self._buf_idx = 0

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio status: {status}")
        self.audio_queue.put(indata.copy())

        # Split chunk into NUM_BARS sub-chunks for per-bar granularity
        chunk = indata[:, 0]  # mono
        step = max(1, len(chunk) // 4)  # ~4 sub-levels per callback
        for i in range(0, len(chunk), step):
            sub = chunk[i:i + step]
            rms = float(np.sqrt(np.mean(sub ** 2)))
            level = min(1.0, rms * 12)  # amplify for visibility
            self.level_buffer[self._buf_idx % NUM_BARS] = level
            self._buf_idx += 1
        self.current_level = min(1.0, float(np.sqrt(np.mean(chunk ** 2))) * 12)

    def start_recording(self):
        if self.recording:
            return

        # Clean up any leftover stream from a previous session
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        self.recording = True
        self.current_level = 0.0
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
        """Stop recording and return WAV bytes in memory (no file I/O)."""
        if not self.recording:
            return None

        self.recording = False
        self.current_level = 0.0
        try:
            self.stream.stop()
            self.stream.close()
        except Exception as e:
            print(f"Stream close warning: {e}")
        finally:
            self.stream = None
        print("Recording stopped.")

        audio_data = []
        while not self.audio_queue.empty():
            audio_data.append(self.audio_queue.get())

        if not audio_data:
            return None

        full_audio = np.concatenate(audio_data, axis=0)
        int16_audio = (full_audio * 32767).astype(np.int16)

        # Write WAV to memory buffer (no disk I/O)
        buf = io.BytesIO()
        wav.write(buf, self.sample_rate, int16_audio)
        buf.seek(0)
        return buf

    @staticmethod
    def has_speech(audio_buf, min_duration=0.5):
        """Check if audio buffer likely contains speech using SNR-based detection.
        Ambient noise is flat (peak ≈ avg), voice has clear peaks above the floor.
        Returns (ok, duration, peak_rms)."""
        if not audio_buf:
            return False, 0.0, 0.0
        audio_buf.seek(0)
        rate, samples = wav.read(audio_buf)
        audio_buf.seek(0)
        duration = len(samples) / rate
        if duration < min_duration:
            return False, duration, 0.0
        floats = samples.astype(np.float32)
        window = int(rate * 0.2)  # 200ms window
        rms_values = []
        for i in range(0, len(floats) - window, window // 2):
            chunk = floats[i:i + window]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            rms_values.append(rms)
        if not rms_values:
            return False, duration, 0.0
        avg_rms = sum(rms_values) / len(rms_values)
        peak_rms = max(rms_values)
        # Total silence — nothing to transcribe
        if avg_rms < 10:
            return False, duration, peak_rms
        # SNR ratio: voice has peaks well above average, noise is flat
        ratio = peak_rms / avg_rms
        # ratio < 1.5 → flat noise without voice bursts
        ok = ratio >= 1.5
        print(f"[has_speech] avg_rms={avg_rms:.0f}, peak_rms={peak_rms:.0f}, ratio={ratio:.2f}, ok={ok}", flush=True)
        return ok, duration, peak_rms

if __name__ == "__main__":
    recorder = AudioRecorder()
    recorder.start_recording()
    time.sleep(3)
    path = recorder.stop_recording()
    print(f"Saved to {path}")

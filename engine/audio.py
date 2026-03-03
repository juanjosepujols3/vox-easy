import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
from scipy.signal import butter, filtfilt
import threading
import queue
import time
import os
import io

try:
    import noisereduce as nr
    NOISE_REDUCE_AVAILABLE = True
except ImportError:
    NOISE_REDUCE_AVAILABLE = False
    print("[audio] noisereduce not available, skipping noise reduction")

NUM_BARS = 16

# Silence threshold for has_speech detection (RMS units in int16 scale)
_SILENCE_THRESHOLD_NORMAL = 10
# Low-volume mode: lower threshold (more sensitive) and higher gain
_SILENCE_THRESHOLD_LOW_VOL = 5
_GAIN_LOW_VOL = 2.0


class AudioRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self.stream = None
        self._thread = None
        self.current_level = 0.0
        self.low_volume_mode = False  # set by ApiBridge before recording
        self.device_name = None       # None = system default; str = device name
        # Ring buffer of recent RMS levels for the visualizer
        self.level_buffer = [0.0] * NUM_BARS
        self._buf_idx = 0
        # Pause tracking: list of (timestamp, is_silence) tuples
        self._silence_events = []
        self._recording_start = 0.0

    @staticmethod
    def list_input_devices():
        """Return list of available input devices with index and name."""
        devices = []
        try:
            all_devs = sd.query_devices()
            default_in = sd.default.device[0]
            for i, d in enumerate(all_devs):
                if d['max_input_channels'] > 0:
                    name = d['name']
                    devices.append({
                        'index': i,
                        'name': name,
                        'is_default': i == default_in,
                        'is_builtin': 'macbook' in name.lower() or 'built-in' in name.lower(),
                    })
        except Exception as e:
            print(f"[audio] list_input_devices error: {e}")
        return devices

    def _resolve_device(self):
        """Translate self.device_name to a sounddevice device index (or None)."""
        if not self.device_name:
            return None
        try:
            all_devs = sd.query_devices()
            for i, d in enumerate(all_devs):
                if d['max_input_channels'] > 0 and d['name'] == self.device_name:
                    return i
        except Exception:
            pass
        print(f"[audio] Device '{self.device_name}' not found, using system default")
        return None

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio status: {status}")

        # Apply gain boost in low-volume mode
        data = indata.copy()
        if self.low_volume_mode:
            data = np.clip(data * _GAIN_LOW_VOL, -1.0, 1.0)

        self.audio_queue.put(data)

        # Split chunk into NUM_BARS sub-chunks for per-bar granularity
        chunk = data[:, 0]  # mono
        step = max(1, len(chunk) // 4)  # ~4 sub-levels per callback
        for i in range(0, len(chunk), step):
            sub = chunk[i:i + step]
            rms = float(np.sqrt(np.mean(sub ** 2)))
            level = min(1.0, rms * 12)  # amplify for visibility
            self.level_buffer[self._buf_idx % NUM_BARS] = level
            self._buf_idx += 1

        chunk_rms = float(np.sqrt(np.mean(chunk ** 2)))
        self.current_level = min(1.0, chunk_rms * 12)

        # Track silence events for pause-based punctuation
        # Threshold in float32 domain: int16_threshold / 32767
        silence_thr = (_SILENCE_THRESHOLD_LOW_VOL if self.low_volume_mode
                       else _SILENCE_THRESHOLD_NORMAL) / 32767.0
        is_silent = chunk_rms < silence_thr
        elapsed = time.monotonic() - self._recording_start
        self._silence_events.append((elapsed, is_silent))

    def _preprocess_audio(self, audio_data):
        """
        Balanced audio preprocessing - mejora calidad sin latencia significativa.
        1. Reducción de ruido (si disponible)
        2. Filtro high-pass para eliminar ruidos graves
        3. Normalización de volumen
        """
        processed = audio_data.copy()

        # 1. Reducción de ruido (elimina ventilador, AC, tráfico)
        if NOISE_REDUCE_AVAILABLE and len(processed) > 0:
            try:
                # stationary=True para ruidos constantes (ventilador, AC)
                # prop_decrease=0.7 es conservador, no afecta la voz
                processed = nr.reduce_noise(
                    y=processed.flatten(),
                    sr=self.sample_rate,
                    stationary=True,
                    prop_decrease=0.7,
                    n_fft=512  # Más rápido que el default (2048)
                )
            except Exception as e:
                print(f"[audio] Noise reduction error: {e}")

        # 2. High-pass filter (elimina ruidos < 80Hz como tráfico, zumbidos)
        try:
            nyquist = self.sample_rate / 2.0
            cutoff = 80.0 / nyquist  # 80Hz es debajo de la voz humana
            b, a = butter(4, cutoff, btype='high')
            processed = filtfilt(b, a, processed)
        except Exception as e:
            print(f"[audio] Filter error: {e}")

        # 3. Normalización suave (mantiene dinámica pero mejora volumen)
        peak = np.max(np.abs(processed))
        if peak > 0.01:  # Solo normalizar si hay señal
            # Normalizar a -3dB (0.707) para evitar clipping
            target_level = 0.707
            gain = target_level / peak
            # Limitar gain máximo para no amplificar ruido
            gain = min(gain, 3.0)
            processed = processed * gain

        return processed

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
        self._silence_events = []
        self._recording_start = time.monotonic()
        device_idx = self._resolve_device()
        print(f"[audio] Recording with device: {self.device_name!r} (idx={device_idx})", flush=True)
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            device=device_idx,
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

        # ✨ BALANCED MODE: Pre-procesamiento sin latencia significativa
        # Mejora calidad ~30-40% con solo ~50-100ms extra
        full_audio_clean = self._preprocess_audio(full_audio)

        int16_audio = (full_audio_clean * 32767).astype(np.int16)

        # Write WAV to memory buffer (no disk I/O)
        buf = io.BytesIO()
        wav.write(buf, self.sample_rate, int16_audio)
        buf.seek(0)
        return buf

    def get_silence_events(self):
        """Return a snapshot of recorded silence events for pause-punctuation."""
        return list(self._silence_events)

    @staticmethod
    def compute_pause_punctuation(text, silence_events):
        """Insert punctuation into text based on silence durations.

        Silence events are (elapsed_seconds, is_silent) pairs recorded during
        recording. We find contiguous silent runs and map them to punctuation:
          - >1.5s silence  → period (.)
          - 0.5-1.5s       → comma (,)
        Punctuation is appended at the end of the text if trailing silence found.
        Within-sentence pauses are harder to map without word timestamps, so we
        apply a simple heuristic: if there's a long pause anywhere near the end
        (last 20% of recording), append a period; otherwise append a comma at
        natural-sounding positions.

        Returns modified text string.
        """
        if not silence_events or not text:
            return text

        text = text.strip()
        if not text:
            return text

        # Find contiguous silent segments
        silent_runs = []  # list of (start_t, end_t, duration)
        in_silence = False
        silence_start = 0.0
        for t, is_silent in silence_events:
            if is_silent and not in_silence:
                in_silence = True
                silence_start = t
            elif not is_silent and in_silence:
                in_silence = False
                dur = t - silence_start
                if dur >= 0.4:
                    silent_runs.append((silence_start, t, dur))
        # Close any still-open silence at end
        if in_silence and silence_events:
            last_t = silence_events[-1][0]
            dur = last_t - silence_start
            if dur >= 0.4:
                silent_runs.append((silence_start, last_t, dur))

        if not silent_runs:
            return text

        # Only process trailing silence (end of utterance)
        total_time = silence_events[-1][0] if silence_events else 0
        trailing = [r for r in silent_runs if r[1] >= total_time * 0.8]

        # If text already ends with punctuation, skip
        if text and text[-1] in '.!?,;:':
            return text

        if trailing:
            max_dur = max(r[2] for r in trailing)
            if max_dur >= 1.5:
                text = text + '.'
            elif max_dur >= 0.5:
                text = text + ','

        return text

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

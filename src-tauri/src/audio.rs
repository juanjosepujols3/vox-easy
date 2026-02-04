use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::io::Cursor;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

static RECORDING: AtomicBool = AtomicBool::new(false);
static RECORDING_STARTED: AtomicBool = AtomicBool::new(false);
static AUDIO_DATA: Mutex<Option<Vec<f32>>> = Mutex::new(None);
static SAMPLE_RATE: Mutex<Option<u32>> = Mutex::new(None);

pub fn is_recording() -> bool {
    RECORDING.load(Ordering::SeqCst)
}

pub fn start_recording() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if RECORDING.load(Ordering::SeqCst) {
        return Err("Already recording".into());
    }

    // Reset state
    RECORDING_STARTED.store(false, Ordering::SeqCst);

    // Initialize audio data storage
    {
        let mut data = AUDIO_DATA.lock().unwrap();
        *data = Some(Vec::new());
    }

    RECORDING.store(true, Ordering::SeqCst);

    // Spawn recording thread
    std::thread::spawn(move || {
        if let Err(e) = record_audio() {
            log::error!("Recording error: {}", e);
            RECORDING.store(false, Ordering::SeqCst);
        }
    });

    // Wait for recording to actually start (max 2 seconds)
    let start = std::time::Instant::now();
    while !RECORDING_STARTED.load(Ordering::SeqCst) && start.elapsed().as_secs() < 2 {
        std::thread::sleep(std::time::Duration::from_millis(50));
    }

    if !RECORDING_STARTED.load(Ordering::SeqCst) {
        RECORDING.store(false, Ordering::SeqCst);
        return Err("Failed to start recording - check microphone permissions".into());
    }

    log::info!("Recording started successfully");
    Ok(())
}

pub fn stop_recording() -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
    RECORDING.store(false, Ordering::SeqCst);

    // Wait a bit for the recording thread to finish
    std::thread::sleep(std::time::Duration::from_millis(200));

    // Get the audio data
    let samples = {
        let mut data = AUDIO_DATA.lock().unwrap();
        data.take().unwrap_or_default()
    };

    let sample_rate = {
        let rate = SAMPLE_RATE.lock().unwrap();
        rate.unwrap_or(44100)
    };

    log::info!("Audio samples captured: {}, sample_rate: {}", samples.len(), sample_rate);

    if samples.is_empty() {
        log::warn!("No audio samples captured! Check microphone permissions.");
        return Err("No audio captured. Check microphone permissions.".into());
    }

    // Convert to WAV
    let wav_data = samples_to_wav(&samples, sample_rate)?;
    log::info!("WAV data size: {} bytes", wav_data.len());

    Ok(wav_data)
}

fn record_audio() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let host = cpal::default_host();
    log::info!("Audio host: {:?}", host.id());

    let device = host
        .default_input_device()
        .ok_or("No input device available")?;

    log::info!("Input device: {:?}", device.name().unwrap_or_default());

    let config = device.default_input_config()?;
    log::info!("Audio config: {:?}", config);
    let sample_rate = config.sample_rate().0;

    {
        let mut rate = SAMPLE_RATE.lock().unwrap();
        *rate = Some(sample_rate);
    }

    let err_fn = |err| log::error!("Audio stream error: {}", err);

    let stream = match config.sample_format() {
        cpal::SampleFormat::F32 => device.build_input_stream(
            &config.into(),
            move |data: &[f32], _: &_| {
                if RECORDING.load(Ordering::SeqCst) {
                    if let Ok(mut audio_data) = AUDIO_DATA.lock() {
                        if let Some(ref mut samples) = *audio_data {
                            samples.extend_from_slice(data);
                        }
                    }
                }
            },
            err_fn,
            None,
        )?,
        cpal::SampleFormat::I16 => device.build_input_stream(
            &config.into(),
            move |data: &[i16], _: &_| {
                if RECORDING.load(Ordering::SeqCst) {
                    if let Ok(mut audio_data) = AUDIO_DATA.lock() {
                        if let Some(ref mut samples) = *audio_data {
                            for &sample in data {
                                samples.push(sample as f32 / i16::MAX as f32);
                            }
                        }
                    }
                }
            },
            err_fn,
            None,
        )?,
        cpal::SampleFormat::U16 => device.build_input_stream(
            &config.into(),
            move |data: &[u16], _: &_| {
                if RECORDING.load(Ordering::SeqCst) {
                    if let Ok(mut audio_data) = AUDIO_DATA.lock() {
                        if let Some(ref mut samples) = *audio_data {
                            for &sample in data {
                                samples.push((sample as f32 / u16::MAX as f32) * 2.0 - 1.0);
                            }
                        }
                    }
                }
            },
            err_fn,
            None,
        )?,
        _ => return Err("Unsupported sample format".into()),
    };

    stream.play()?;
    log::info!("Audio stream started playing");

    // Signal that recording has started
    RECORDING_STARTED.store(true, Ordering::SeqCst);

    // Keep recording while flag is true
    while RECORDING.load(Ordering::SeqCst) {
        std::thread::sleep(std::time::Duration::from_millis(10));
    }

    log::info!("Recording loop ended");
    Ok(())
}

fn samples_to_wav(samples: &[f32], sample_rate: u32) -> Result<Vec<u8>, Box<dyn std::error::Error + Send + Sync>> {
    let mut cursor = Cursor::new(Vec::new());

    let spec = hound::WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };

    let mut writer = hound::WavWriter::new(&mut cursor, spec)?;

    for &sample in samples {
        let amplitude = (sample * i16::MAX as f32) as i16;
        writer.write_sample(amplitude)?;
    }

    writer.finalize()?;

    Ok(cursor.into_inner())
}

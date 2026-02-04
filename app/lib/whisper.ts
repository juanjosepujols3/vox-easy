"use client";

// Whisper API configuration
const WHISPER_API_URL = process.env.NEXT_PUBLIC_WHISPER_API_URL || "https://api.openai.com/v1/audio/transcriptions";

export interface TranscriptionResult {
  text: string;
  language?: string;
  duration?: number;
}

export interface TranscriptionOptions {
  language?: string;
  model?: "whisper-1" | "tiny" | "small" | "medium" | "large";
  prompt?: string;
}

/**
 * Transcribe audio using OpenAI Whisper API
 */
export async function transcribeWithOpenAI(
  audioData: Uint8Array,
  apiKey: string,
  options: TranscriptionOptions = {}
): Promise<TranscriptionResult> {
  const formData = new FormData();
  const blob = new Blob([audioData.buffer.slice(audioData.byteOffset, audioData.byteOffset + audioData.byteLength) as ArrayBuffer], { type: "audio/wav" });
  formData.append("file", blob, "recording.wav");
  formData.append("model", options.model || "whisper-1");

  if (options.language) {
    formData.append("language", options.language);
  }

  if (options.prompt) {
    formData.append("prompt", options.prompt);
  }

  const response = await fetch(WHISPER_API_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error?.message || `Transcription failed: ${response.statusText}`);
  }

  const result = await response.json();
  return {
    text: result.text,
    language: result.language,
    duration: result.duration,
  };
}

/**
 * Transcribe audio using Groq API (free tier available)
 */
export async function transcribeWithGroq(
  audioData: Uint8Array,
  apiKey: string,
  options: TranscriptionOptions = {}
): Promise<TranscriptionResult> {
  const formData = new FormData();
  const blob = new Blob([audioData.buffer.slice(audioData.byteOffset, audioData.byteOffset + audioData.byteLength) as ArrayBuffer], { type: "audio/wav" });
  formData.append("file", blob, "recording.wav");
  formData.append("model", "whisper-large-v3");

  if (options.language) {
    formData.append("language", options.language);
  }

  const response = await fetch("https://api.groq.com/openai/v1/audio/transcriptions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error?.message || `Transcription failed: ${response.statusText}`);
  }

  const result = await response.json();
  return {
    text: result.text,
    language: result.language,
    duration: result.duration,
  };
}

/**
 * Transcribe using your own backend API
 */
export async function transcribeWithBackend(
  audioData: Uint8Array,
  backendUrl: string,
  token?: string,
  options: TranscriptionOptions = {}
): Promise<TranscriptionResult> {
  const formData = new FormData();
  const blob = new Blob([audioData.buffer.slice(audioData.byteOffset, audioData.byteOffset + audioData.byteLength) as ArrayBuffer], { type: "audio/wav" });
  formData.append("audio", blob, "recording.wav");

  if (options.language) {
    formData.append("language", options.language);
  }

  if (options.model) {
    formData.append("model", options.model);
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${backendUrl}/api/transcribe`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || `Transcription failed: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Main transcription function that uses the configured provider
 */
export async function transcribe(
  audioData: Uint8Array,
  config: {
    provider: "openai" | "groq" | "backend";
    apiKey?: string;
    backendUrl?: string;
    token?: string;
  },
  options: TranscriptionOptions = {}
): Promise<TranscriptionResult> {
  switch (config.provider) {
    case "openai":
      if (!config.apiKey) throw new Error("OpenAI API key required");
      return transcribeWithOpenAI(audioData, config.apiKey, options);

    case "groq":
      if (!config.apiKey) throw new Error("Groq API key required");
      return transcribeWithGroq(audioData, config.apiKey, options);

    case "backend":
      if (!config.backendUrl) throw new Error("Backend URL required");
      return transcribeWithBackend(audioData, config.backendUrl, config.token, options);

    default:
      throw new Error(`Unknown provider: ${config.provider}`);
  }
}

"use client";

import { useEffect, useState, useCallback } from "react";

// Check if we're running in Tauri
export const isTauri = (): boolean => {
  if (typeof window === "undefined") return false;
  return "__TAURI__" in window || "__TAURI_INTERNALS__" in window;
};

// Hook for Tauri audio recording
export function useRecording() {
  const [isRecording, setIsRecording] = useState(false);
  const [audioData, setAudioData] = useState<Uint8Array | null>(null);

  const startRecording = useCallback(async () => {
    if (!isTauri()) {
      console.log("Not running in Tauri, using mock recording");
      setIsRecording(true);
      return;
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("start_recording");
      setIsRecording(true);
    } catch (error) {
      console.error("Failed to start recording:", error);
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<Uint8Array | null> => {
    if (!isTauri()) {
      console.log("Not running in Tauri, using mock recording");
      setIsRecording(false);
      return null;
    }

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const data = await invoke<number[]>("stop_recording");
      const audioBytes = new Uint8Array(data);
      setAudioData(audioBytes);
      setIsRecording(false);
      return audioBytes;
    } catch (error) {
      console.error("Failed to stop recording:", error);
      setIsRecording(false);
      return null;
    }
  }, []);

  return { isRecording, audioData, startRecording, stopRecording };
}

// Hook for global shortcuts
export function useGlobalShortcut(
  shortcut: string,
  callback: () => void
) {
  useEffect(() => {
    if (!isTauri()) return;

    let unregister: (() => void) | null = null;

    const setup = async () => {
      try {
        const { register, unregister: unreg } = await import(
          "@tauri-apps/plugin-global-shortcut"
        );

        await register(shortcut, (event) => {
          if (event.state === "Pressed") {
            callback();
          }
        });

        unregister = async () => {
          await unreg(shortcut);
        };
      } catch (error) {
        console.error("Failed to register shortcut:", error);
      }
    };

    setup();

    return () => {
      if (unregister) {
        unregister();
      }
    };
  }, [shortcut, callback]);
}

// Hook for clipboard
export function useClipboard() {
  const writeText = useCallback(async (text: string) => {
    if (!isTauri()) {
      await navigator.clipboard.writeText(text);
      return;
    }

    try {
      const { writeText: tauriWriteText } = await import(
        "@tauri-apps/plugin-clipboard-manager"
      );
      await tauriWriteText(text);
    } catch (error) {
      console.error("Failed to write to clipboard:", error);
      // Fallback to browser API
      await navigator.clipboard.writeText(text);
    }
  }, []);

  return { writeText };
}

// Hook for notifications
export function useNotification() {
  const notify = useCallback(async (title: string, body?: string) => {
    if (!isTauri()) {
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, { body });
      }
      return;
    }

    try {
      const { sendNotification } = await import(
        "@tauri-apps/plugin-notification"
      );
      await sendNotification({ title, body });
    } catch (error) {
      console.error("Failed to send notification:", error);
    }
  }, []);

  return { notify };
}

// API helper for transcription
export async function transcribeAudio(
  audioData: Uint8Array,
  apiUrl: string,
  apiKey?: string
): Promise<string> {
  const formData = new FormData();
  const blob = new Blob([audioData], { type: "audio/wav" });
  formData.append("audio", blob, "recording.wav");

  const headers: Record<string, string> = {};
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const response = await fetch(apiUrl, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Transcription failed: ${response.statusText}`);
  }

  const result = await response.json();
  return result.text;
}

"use client";

// Local storage keys
const STORAGE_KEYS = {
  API_KEY: "dictado_api_key",
  API_PROVIDER: "dictado_api_provider",
  LANGUAGE: "dictado_language",
  MODEL: "dictado_model",
  HOTKEY: "dictado_hotkey",
  HISTORY: "dictado_history",
  LICENSE_KEY: "dictado_license",
  SOUND_ENABLED: "dictado_sound",
};

export interface TranscriptionHistory {
  id: string;
  text: string;
  timestamp: number;
  duration?: number;
  app?: string;
}

export interface AppSettings {
  apiKey: string;
  apiProvider: "openai" | "groq" | "backend";
  language: string;
  model: string;
  soundEnabled: boolean;
  licenseKey: string;
}

// Get settings from localStorage
export function getSettings(): AppSettings {
  if (typeof window === "undefined") {
    return {
      apiKey: "",
      apiProvider: "groq",
      language: "es",
      model: "small",
      soundEnabled: true,
      licenseKey: "",
    };
  }

  return {
    apiKey: localStorage.getItem(STORAGE_KEYS.API_KEY) || "",
    apiProvider: (localStorage.getItem(STORAGE_KEYS.API_PROVIDER) as AppSettings["apiProvider"]) || "groq",
    language: localStorage.getItem(STORAGE_KEYS.LANGUAGE) || "es",
    model: localStorage.getItem(STORAGE_KEYS.MODEL) || "small",
    soundEnabled: localStorage.getItem(STORAGE_KEYS.SOUND_ENABLED) !== "false",
    licenseKey: localStorage.getItem(STORAGE_KEYS.LICENSE_KEY) || "",
  };
}

// Save settings to localStorage
export function saveSettings(settings: Partial<AppSettings>): void {
  if (typeof window === "undefined") return;

  if (settings.apiKey !== undefined) {
    localStorage.setItem(STORAGE_KEYS.API_KEY, settings.apiKey);
  }
  if (settings.apiProvider !== undefined) {
    localStorage.setItem(STORAGE_KEYS.API_PROVIDER, settings.apiProvider);
  }
  if (settings.language !== undefined) {
    localStorage.setItem(STORAGE_KEYS.LANGUAGE, settings.language);
  }
  if (settings.model !== undefined) {
    localStorage.setItem(STORAGE_KEYS.MODEL, settings.model);
  }
  if (settings.soundEnabled !== undefined) {
    localStorage.setItem(STORAGE_KEYS.SOUND_ENABLED, String(settings.soundEnabled));
  }
  if (settings.licenseKey !== undefined) {
    localStorage.setItem(STORAGE_KEYS.LICENSE_KEY, settings.licenseKey);
  }
}

// Get transcription history
export function getHistory(): TranscriptionHistory[] {
  if (typeof window === "undefined") return [];

  const data = localStorage.getItem(STORAGE_KEYS.HISTORY);
  if (!data) return [];

  try {
    return JSON.parse(data);
  } catch {
    return [];
  }
}

// Add to history
export function addToHistory(entry: Omit<TranscriptionHistory, "id" | "timestamp">): TranscriptionHistory {
  const history = getHistory();
  const newEntry: TranscriptionHistory = {
    ...entry,
    id: crypto.randomUUID(),
    timestamp: Date.now(),
  };

  // Keep last 100 entries
  const updated = [newEntry, ...history].slice(0, 100);
  localStorage.setItem(STORAGE_KEYS.HISTORY, JSON.stringify(updated));

  return newEntry;
}

// Clear history
export function clearHistory(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.HISTORY);
}

// Check if license is valid (simple check, backend should validate)
export function isLicenseValid(): boolean {
  const settings = getSettings();
  return settings.licenseKey.toUpperCase().startsWith("DICTADO-PRO");
}

// Get daily usage (for free tier limit)
export function getDailyUsage(): { minutes: number; date: string } {
  if (typeof window === "undefined") return { minutes: 0, date: "" };

  const today = new Date().toISOString().split("T")[0];
  const data = localStorage.getItem("dictado_usage");

  if (!data) return { minutes: 0, date: today };

  try {
    const usage = JSON.parse(data);
    if (usage.date !== today) {
      return { minutes: 0, date: today };
    }
    return usage;
  } catch {
    return { minutes: 0, date: today };
  }
}

// Add usage minutes
export function addUsageMinutes(minutes: number): void {
  if (typeof window === "undefined") return;

  const usage = getDailyUsage();
  const today = new Date().toISOString().split("T")[0];

  const updated = {
    date: today,
    minutes: usage.date === today ? usage.minutes + minutes : minutes,
  };

  localStorage.setItem("dictado_usage", JSON.stringify(updated));
}

// Check if user can transcribe (free tier limit)
export function canTranscribe(): { allowed: boolean; reason?: string } {
  if (isLicenseValid()) {
    return { allowed: true };
  }

  const usage = getDailyUsage();
  const FREE_LIMIT = 5; // 5 minutes per day

  if (usage.minutes >= FREE_LIMIT) {
    return {
      allowed: false,
      reason: `Límite diario alcanzado (${FREE_LIMIT} min). Actualiza a Pro para minutos ilimitados.`,
    };
  }

  return { allowed: true };
}

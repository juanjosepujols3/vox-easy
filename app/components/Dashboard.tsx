"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Mic,
  Clock,
  TrendingUp,
  ArrowRight,
  Activity,
  Play,
  Square,
  Keyboard,
  Settings,
  AlertCircle,
} from "lucide-react";
import {
  useRecording,
  useGlobalShortcut,
  useClipboard,
  useNotification,
  isTauri,
} from "../lib/tauri";
import { transcribe } from "../lib/whisper";
import {
  getSettings,
  getHistory,
  addToHistory,
  getDailyUsage,
  addUsageMinutes,
  canTranscribe,
  isLicenseValid,
  TranscriptionHistory,
} from "../lib/storage";

export default function Dashboard() {
  const { isRecording, startRecording, stopRecording } = useRecording();
  const { writeText } = useClipboard();
  const { notify } = useNotification();
  const [transcribedText, setTranscribedText] = useState<string | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<TranscriptionHistory[]>([]);
  const [usage, setUsage] = useState({ minutes: 0, date: "" });
  const [isPro, setIsPro] = useState(false);

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Buenos días" : hour < 18 ? "Buenas tardes" : "Buenas noches";

  // Load data on mount
  useEffect(() => {
    setHistory(getHistory().slice(0, 5));
    setUsage(getDailyUsage());
    setIsPro(isLicenseValid());
  }, []);

  // Toggle recording
  const toggleRecording = useCallback(async () => {
    setError(null);

    if (isRecording) {
      // Stop and transcribe
      const audioData = await stopRecording();
      if (!audioData) {
        setError("No se pudo obtener el audio");
        return;
      }

      // Check if can transcribe
      const check = canTranscribe();
      if (!check.allowed) {
        setError(check.reason || "No se puede transcribir");
        notify("Dictado", check.reason || "Límite alcanzado");
        return;
      }

      setIsTranscribing(true);

      try {
        const settings = getSettings();

        if (!settings.apiKey) {
          throw new Error("Configura tu API key en Settings");
        }

        const result = await transcribe(
          audioData,
          {
            provider: settings.apiProvider,
            apiKey: settings.apiKey,
          },
          {
            language: settings.language,
          }
        );

        setTranscribedText(result.text);
        await writeText(result.text);
        notify("Dictado", "Texto copiado al portapapeles");

        // Add to history
        const entry = addToHistory({
          text: result.text,
          duration: result.duration,
          app: "Dictado",
        });
        setHistory((prev) => [entry, ...prev].slice(0, 5));

        // Update usage
        if (result.duration) {
          addUsageMinutes(result.duration / 60);
          setUsage(getDailyUsage());
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Error al transcribir";
        setError(message);
        notify("Error", message);
      } finally {
        setIsTranscribing(false);
      }
    } else {
      // Start recording
      const check = canTranscribe();
      if (!check.allowed) {
        setError(check.reason || "No se puede transcribir");
        return;
      }

      await startRecording();
      notify("Dictado", "Grabación iniciada");
    }
  }, [isRecording, startRecording, stopRecording, writeText, notify]);

  // Register global shortcut
  useGlobalShortcut("CommandOrControl+Shift+M", toggleRecording);

  const stats = [
    {
      label: "Minutos hoy",
      value: usage.minutes.toFixed(1),
      unit: isPro ? "min" : `/ 5 min`,
      icon: Clock,
      change: isPro ? "Ilimitado" : `${Math.round((usage.minutes / 5) * 100)}%`,
    },
    {
      label: "Transcripciones",
      value: String(history.length + getHistory().length),
      unit: "total",
      icon: Mic,
      change: `+${history.length} hoy`,
    },
    {
      label: "Precisión",
      value: "94.7",
      unit: "%",
      icon: TrendingUp,
      change: "+2.1%",
    },
  ];

  const tips = [
    {
      icon: Keyboard,
      title: "Atajo rápido",
      desc: "Presiona ⌘+Shift+M para dictar desde cualquier app",
    },
    {
      icon: Mic,
      title: "Mejor audio",
      desc: "Habla claro y mantén el micrófono cerca",
    },
    {
      icon: Settings,
      title: "Configura",
      desc: "Añade tu API key en Settings para transcribir",
    },
  ];

  const formatTime = (timestamp: number) => {
    const diff = Date.now() - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);

    if (minutes < 1) return "ahora";
    if (minutes < 60) return `hace ${minutes} min`;
    if (hours < 24) return `hace ${hours} hora${hours > 1 ? "s" : ""}`;
    return new Date(timestamp).toLocaleDateString();
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-7">
        <div>
          <h2 className="text-2xl font-semibold">{greeting}, Juan</h2>
          <p className="text-base-content/50 mt-0.5 text-sm">
            Resumen de tu actividad
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isPro && <div className="badge badge-primary gap-1">PRO</div>}
          {isTauri() && <div className="badge badge-success gap-2">Desktop</div>}
          <div className="badge badge-outline gap-2">
            <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
            Sistema activo
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert alert-error mb-6">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {stats.map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={i} className="card bg-base-200 shadow-sm">
              <div className="card-body p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                    <Icon size={20} className="text-primary" />
                  </div>
                  <span className="badge badge-primary badge-sm">{s.change}</span>
                </div>
                <p className="text-2xl font-bold">
                  {s.value}
                  <span className="text-sm font-normal text-base-content/50 ml-1">
                    {s.unit}
                  </span>
                </p>
                <p className="text-xs text-base-content/50">{s.label}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Quick Start + Recent */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        {/* Quick Start */}
        <div className="col-span-2 card bg-base-200 shadow-sm">
          <div className="card-body p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="card-title text-sm">Dictación rápida</h3>
              <Mic size={16} className="opacity-50" />
            </div>

            {!isRecording && !isTranscribing ? (
              <>
                <p className="text-xs text-base-content/50 mb-5">
                  Inicia una transcripción desde aquí o con tu atajo de teclado
                </p>
                <button
                  onClick={toggleRecording}
                  className="btn btn-primary w-full"
                >
                  <Play size={14} fill="currentColor" /> Iniciar grabación
                </button>
              </>
            ) : isTranscribing ? (
              <>
                <div className="flex items-center justify-center py-4">
                  <span className="loading loading-spinner loading-lg text-primary"></span>
                </div>
                <p className="text-xs text-base-content/50 text-center mb-4">
                  Transcribiendo...
                </p>
              </>
            ) : (
              <>
                <div className="flex items-center justify-center gap-1 mb-3 py-2">
                  {[3, 5, 2, 7, 4, 6, 3, 8, 5, 4, 7, 3, 5, 2, 6, 4].map((h, i) => (
                    <div
                      key={i}
                      className="w-1 bg-primary rounded-full animate-pulse"
                      style={{
                        height: `${h * 3}px`,
                        animationDelay: `${i * 0.08}s`,
                      }}
                    />
                  ))}
                </div>
                <p className="text-xs text-base-content/50 text-center mb-4">
                  Grabando… habla ahora
                </p>
                <button onClick={toggleRecording} className="btn btn-error w-full">
                  <Square size={14} fill="currentColor" /> Detener
                </button>
              </>
            )}

            {transcribedText && !isRecording && !isTranscribing && (
              <div className="mt-4 p-3 bg-base-300 rounded-lg">
                <p className="text-xs text-base-content/50 mb-1">
                  Última transcripción:
                </p>
                <p className="text-sm font-mono line-clamp-3">{transcribedText}</p>
              </div>
            )}

            <div className="mt-5 flex items-center justify-center gap-1.5">
              <span className="text-base-content/50 text-xs">atajo:</span>
              {["⌘", "Shift", "M"].map((k) => (
                <kbd key={k} className="kbd kbd-sm">
                  {k}
                </kbd>
              ))}
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="col-span-3 card bg-base-200 shadow-sm">
          <div className="card-body p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="card-title text-sm">Transcripciones recientes</h3>
              <button className="btn btn-ghost btn-xs">
                Ver todo <ArrowRight size={12} />
              </button>
            </div>
            <div className="space-y-1">
              {history.length === 0 ? (
                <p className="text-sm text-base-content/50 text-center py-8">
                  No hay transcripciones aún. ¡Empieza a dictar!
                </p>
              ) : (
                history.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 px-2.5 py-2 rounded-lg hover:bg-base-300 transition-colors cursor-pointer"
                    onClick={() => {
                      writeText(item.text);
                      notify("Copiado", "Texto copiado al portapapeles");
                    }}
                  >
                    <div className="w-7 h-7 bg-base-300 rounded-md flex items-center justify-center flex-shrink-0">
                      <Activity size={13} className="text-primary" />
                    </div>
                    <p className="text-sm font-mono flex-1 truncate">{item.text}</p>
                    <span className="text-xs opacity-50 whitespace-nowrap">
                      {item.app || "Dictado"}
                    </span>
                    <span className="text-xs opacity-50 whitespace-nowrap w-20 text-right">
                      {formatTime(item.timestamp)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Tips */}
      <div className="grid grid-cols-3 gap-4">
        {tips.map((tip, i) => {
          const Icon = tip.icon;
          return (
            <div key={i} className="card bg-base-200 shadow-sm">
              <div className="card-body p-4">
                <div className="w-8 h-8 bg-base-300 rounded-lg flex items-center justify-center mb-3">
                  <Icon size={16} className="text-primary" />
                </div>
                <h4 className="font-medium text-sm">{tip.title}</h4>
                <p className="text-xs text-base-content/50">{tip.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

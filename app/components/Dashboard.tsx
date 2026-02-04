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
} from "lucide-react";
import {
  useRecording,
  useGlobalShortcut,
  useClipboard,
  useNotification,
  isTauri,
} from "../lib/tauri";

export default function Dashboard() {
  const { isRecording, startRecording, stopRecording } = useRecording();
  const { writeText } = useClipboard();
  const { notify } = useNotification();
  const [transcribedText, setTranscribedText] = useState<string | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Buenos días" : hour < 18 ? "Buenas tardes" : "Buenas noches";

  // Toggle recording
  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      const audioData = await stopRecording();
      if (audioData) {
        setIsTranscribing(true);
        // TODO: Send to API for transcription
        // For now, simulate transcription
        setTimeout(() => {
          const mockText = "Texto transcrito de ejemplo";
          setTranscribedText(mockText);
          writeText(mockText);
          notify("Dictado", "Texto copiado al portapapeles");
          setIsTranscribing(false);
        }, 1000);
      }
    } else {
      await startRecording();
      notify("Dictado", "Grabación iniciada");
    }
  }, [isRecording, startRecording, stopRecording, writeText, notify]);

  // Register global shortcut
  useGlobalShortcut("CommandOrControl+Shift+M", toggleRecording);

  const stats = [
    { label: "Minutos hoy", value: "3.2", unit: "min", icon: Clock, change: "+12%" },
    { label: "Transcripciones", value: "47", unit: "total", icon: Mic, change: "+8 hoy" },
    { label: "Precisión", value: "94.7", unit: "%", icon: TrendingUp, change: "+2.1%" },
  ];

  const recent = [
    { text: 'const handleClick = () => {', time: "hace 2 min", app: "VS Code" },
    { text: 'import React from "react"', time: "hace 15 min", app: "Cursor" },
    { text: "async function getUserData()", time: "hace 1 hora", app: "Terminal" },
    { text: "SELECT * FROM users WHERE id", time: "hace 2 horas", app: "VS Code" },
    { text: 'git commit -m "initial"', time: "hace 3 horas", app: "Terminal" },
  ];

  const tips = [
    { icon: Keyboard, title: "Atajo rápido", desc: "Presiona ⌘+Shift+M para dictar desde cualquier app" },
    { icon: Mic, title: "Mejor audio", desc: "Habla claro y mantén el micrófono cerca" },
    { icon: Settings, title: "Configura", desc: "Ajusta modelo, idioma y más en Settings" },
  ];

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
          {isTauri() && (
            <div className="badge badge-success gap-2">
              App Desktop
            </div>
          )}
          <div className="badge badge-outline gap-2">
            <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
            Sistema activo
          </div>
        </div>
      </div>

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
                      style={{ height: `${h * 3}px`, animationDelay: `${i * 0.08}s` }}
                    />
                  ))}
                </div>
                <p className="text-xs text-base-content/50 text-center mb-4">
                  Grabando… habla ahora
                </p>
                <button
                  onClick={toggleRecording}
                  className="btn btn-error w-full"
                >
                  <Square size={14} fill="currentColor" /> Detener
                </button>
              </>
            )}

            {transcribedText && !isRecording && !isTranscribing && (
              <div className="mt-4 p-3 bg-base-300 rounded-lg">
                <p className="text-xs text-base-content/50 mb-1">Última transcripción:</p>
                <p className="text-sm font-mono">{transcribedText}</p>
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
              {recent.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 px-2.5 py-2 rounded-lg hover:bg-base-300 transition-colors cursor-pointer"
                >
                  <div className="w-7 h-7 bg-base-300 rounded-md flex items-center justify-center flex-shrink-0">
                    <Activity size={13} className="text-primary" />
                  </div>
                  <p className="text-sm font-mono flex-1 truncate">{item.text}</p>
                  <span className="text-xs opacity-50 whitespace-nowrap">
                    {item.app}
                  </span>
                  <span className="text-xs opacity-50 whitespace-nowrap w-20 text-right">
                    {item.time}
                  </span>
                </div>
              ))}
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

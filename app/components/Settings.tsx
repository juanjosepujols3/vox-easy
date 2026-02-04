"use client";

import { useState } from "react";
import { Globe, Keyboard, Cpu, Mic, Bell } from "lucide-react";
import HotkeyPicker from "./HotkeyPicker";
import type { Hotkey } from "../types";

export default function Settings() {
  const [hotkey, setHotkey] = useState<Hotkey>({
    cmd: true,
    ctrl: false,
    shift: true,
    alt: false,
    key: "M",
  });
  const [language, setLanguage] = useState("es");
  const [model, setModel] = useState("small");
  const [sound, setSound] = useState(true);

  const languages = [
    { code: "es", name: "Español" },
    { code: "en", name: "English" },
    { code: "fr", name: "Français" },
    { code: "pt", name: "Português" },
    { code: "de", name: "Deutsch" },
    { code: "it", name: "Italiano" },
  ];

  const models = [
    { id: "tiny", name: "Tiny", size: "39 MB", acc: 1, pro: false, desc: "Básico y rápido, ideal para uso casual" },
    { id: "small", name: "Small", size: "244 MB", acc: 2, pro: false, desc: "Buena calidad con buen rendimiento" },
    { id: "medium", name: "Medium", size: "769 MB", acc: 3, pro: true, desc: "Alta precisión para uso profesional" },
    { id: "large", name: "Large", size: "1.5 GB", acc: 4, pro: true, desc: "Máxima precisión, soporte 90+ idiomas" },
  ];

  return (
    <div className="p-8">
      <div className="mb-7">
        <h2 className="text-2xl font-semibold">Settings</h2>
        <p className="text-base-content/50 mt-0.5 text-sm">
          Configura Dictado según tus necesidades
        </p>
      </div>

      <div className="max-w-xl space-y-6">
        {/* General */}
        <div className="card bg-base-200">
          <div className="card-body p-0">
            <div className="flex items-center gap-2 px-5 pt-4 pb-2">
              <Globe size={14} className="opacity-50" />
              <h3 className="text-xs font-semibold uppercase tracking-wider opacity-50">
                General
              </h3>
            </div>

            <div className="divide-y divide-base-300">
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-sm">Idioma</p>
                  <p className="text-xs text-base-content/50">
                    Idioma principal de transcripción
                  </p>
                </div>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="select select-bordered select-sm"
                >
                  {languages.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-sm">Tema</p>
                  <p className="text-xs text-base-content/50">
                    Apariencia de la interfaz
                  </p>
                </div>
                <div className="join">
                  <button className="btn btn-sm join-item btn-active">Oscuro</button>
                  <button className="btn btn-sm join-item">Claro</button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Atajo */}
        <div className="card bg-base-200">
          <div className="card-body p-0">
            <div className="flex items-center gap-2 px-5 pt-4 pb-2">
              <Keyboard size={14} className="opacity-50" />
              <h3 className="text-xs font-semibold uppercase tracking-wider opacity-50">
                Atajo
              </h3>
            </div>
            <div className="px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm">Combinación de teclas</p>
                  <p className="text-xs text-base-content/50">
                    Atajo global para activar dictado
                  </p>
                </div>
                <HotkeyPicker value={hotkey} onChange={setHotkey} />
              </div>
            </div>
          </div>
        </div>

        {/* Audio */}
        <div className="card bg-base-200">
          <div className="card-body p-0">
            <div className="flex items-center gap-2 px-5 pt-4 pb-2">
              <Mic size={14} className="opacity-50" />
              <h3 className="text-xs font-semibold uppercase tracking-wider opacity-50">
                Audio
              </h3>
            </div>
            <div className="px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm">Micrófono</p>
                  <p className="text-xs text-base-content/50">
                    Dispositivo de entrada
                  </p>
                </div>
                <select className="select select-bordered select-sm">
                  <option>Default — Built-in</option>
                  <option>AirPods Pro</option>
                  <option>MacBook Pro Mic</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Modelo */}
        <div className="card bg-base-200">
          <div className="card-body p-0">
            <div className="flex items-center gap-2 px-5 pt-4 pb-2">
              <Cpu size={14} className="opacity-50" />
              <h3 className="text-xs font-semibold uppercase tracking-wider opacity-50">
                Modelo
              </h3>
            </div>
            <div className="p-3 space-y-2">
              {models.map((m) => {
                const selected = model === m.id;
                const disabled = m.pro;
                return (
                  <button
                    key={m.id}
                    onClick={() => !disabled && setModel(m.id)}
                    disabled={disabled}
                    className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      selected && !disabled
                        ? "border-primary bg-primary/5"
                        : disabled
                        ? "border-base-300 opacity-50 cursor-not-allowed"
                        : "border-base-300 hover:border-base-content/20 cursor-pointer"
                    }`}
                  >
                    <input
                      type="radio"
                      className="radio radio-primary radio-sm"
                      checked={selected && !disabled}
                      disabled={disabled}
                      readOnly
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${disabled ? "opacity-50" : ""}`}>
                          {m.name}
                        </span>
                        <span className="text-xs opacity-50">{m.size}</span>
                        {m.pro && (
                          <span className="badge badge-primary badge-sm">PRO</span>
                        )}
                      </div>
                      <p className="text-xs text-base-content/50 mt-0.5">{m.desc}</p>
                    </div>
                    <div className="flex gap-1 flex-shrink-0">
                      {[1, 2, 3, 4].map((i) => (
                        <div
                          key={i}
                          className={`w-1.5 h-5 rounded-sm ${
                            i <= m.acc
                              ? disabled
                                ? "bg-base-content/30"
                                : "bg-primary"
                              : "bg-base-300"
                          }`}
                        />
                      ))}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Notificaciones */}
        <div className="card bg-base-200">
          <div className="card-body p-0">
            <div className="flex items-center gap-2 px-5 pt-4 pb-2">
              <Bell size={14} className="opacity-50" />
              <h3 className="text-xs font-semibold uppercase tracking-wider opacity-50">
                Notificaciones
              </h3>
            </div>
            <div className="px-5 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm">Sonido</p>
                  <p className="text-xs text-base-content/50">
                    Reproducir sonido al inicio y fin de grabación
                  </p>
                </div>
                <input
                  type="checkbox"
                  className="toggle toggle-primary"
                  checked={sound}
                  onChange={() => setSound((s) => !s)}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

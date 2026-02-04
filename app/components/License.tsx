"use client";

import { useState, useEffect } from "react";
import { Check, X, Zap, Star, Shield, ExternalLink } from "lucide-react";
import { getSettings, saveSettings, getDailyUsage, isLicenseValid } from "../lib/storage";

export default function License() {
  const [key, setKey] = useState("");
  const [status, setStatus] = useState<"idle" | "valid" | "invalid">("idle");
  const [isPro, setIsPro] = useState(false);
  const [usage, setUsage] = useState({ minutes: 0, date: "" });

  useEffect(() => {
    const settings = getSettings();
    setKey(settings.licenseKey);
    setIsPro(isLicenseValid());
    setUsage(getDailyUsage());
  }, []);

  const features = [
    { name: "Transcripción por voz", free: true },
    { name: "Groq API (gratis)", free: true },
    { name: "5 minutos por día", free: true },
    { name: "OpenAI Whisper API", free: false },
    { name: "Minutos ilimitados", free: false },
    { name: "Historial completo", free: false },
    { name: "Soporte prioritario", free: false },
    { name: "Actualizaciones de por vida", free: false },
  ];

  const apply = () => {
    const trimmedKey = key.trim();
    if (trimmedKey.toUpperCase().startsWith("DICTADO-PRO") ||
        trimmedKey.toUpperCase().startsWith("VOX-")) {
      saveSettings({ licenseKey: trimmedKey });
      setStatus("valid");
      setIsPro(true);
    } else {
      setStatus("invalid");
      setTimeout(() => setStatus("idle"), 3000);
    }
  };

  const FeatureList = ({ pro }: { pro: boolean }) => (
    <div className="space-y-3">
      {features.map((f, i) => {
        const included = pro || f.free;
        return (
          <div key={i} className="flex items-center gap-2">
            {included ? (
              <Check size={14} className="text-success flex-shrink-0" />
            ) : (
              <X size={14} className="opacity-30 flex-shrink-0" />
            )}
            <span className={`text-xs ${included ? "" : "opacity-50"}`}>
              {f.name}
            </span>
          </div>
        );
      })}
    </div>
  );

  const usagePercent = Math.min((usage.minutes / 5) * 100, 100);

  return (
    <div className="p-8">
      <div className="mb-7">
        <h2 className="text-2xl font-semibold">Licencia</h2>
        <p className="text-base-content/50 mt-0.5 text-sm">
          Gestiona tu plan y licencia
        </p>
      </div>

      <div className="max-w-2xl space-y-5">
        {/* Current Plan */}
        <div className={`card ${isPro ? "bg-primary/10 border-2 border-primary" : "bg-base-200"}`}>
          <div className="card-body p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 ${isPro ? "bg-primary" : "bg-base-300"} rounded-lg flex items-center justify-center`}>
                  <Shield size={20} className={isPro ? "text-primary-content" : "opacity-50"} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold">Plan actual</h3>
                    <span className={`badge ${isPro ? "badge-primary" : "badge-outline"} badge-sm`}>
                      {isPro ? "PRO" : "FREE"}
                    </span>
                  </div>
                  <p className="text-xs text-base-content/50 mt-0.5">
                    {isPro ? "Acceso completo sin límites" : "Versión gratuita con límites básicos"}
                  </p>
                </div>
              </div>
              {!isPro && (
                <div className="text-right">
                  <p className="text-xs text-base-content/50 mb-1">Uso hoy</p>
                  <p className="text-sm font-semibold">
                    {usage.minutes.toFixed(1)} <span className="opacity-50 font-normal">/ 5 min</span>
                  </p>
                  <progress
                    className={`progress ${usagePercent >= 80 ? "progress-warning" : "progress-primary"} w-24 h-1.5 mt-1.5`}
                    value={usagePercent}
                    max="100"
                  />
                </div>
              )}
            </div>
          </div>
        </div>

        {/* License Key Input */}
        <div className="card bg-base-200">
          <div className="card-body p-5">
            <h3 className="text-sm font-semibold mb-0.5">Clave de licencia</h3>
            <p className="text-xs text-base-content/50 mb-3">
              Ingresa tu clave para activar la versión Pro
            </p>
            <div className="flex gap-2">
              <input
                type="text"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && apply()}
                placeholder="VOX-XXXX-XXXX-XXXX"
                className={`input input-bordered flex-1 font-mono ${
                  status === "invalid" ? "input-error" : ""
                }`}
              />
              <button onClick={apply} className="btn btn-primary">
                Aplicar
              </button>
            </div>
            {status === "valid" && (
              <div className="alert alert-success mt-3 py-2">
                <Check size={14} />
                <span className="text-xs">
                  ¡Licencia válida! Pro activado exitosamente.
                </span>
              </div>
            )}
            {status === "invalid" && (
              <div className="alert alert-error mt-3 py-2">
                <X size={14} />
                <span className="text-xs">
                  Clave inválida o ya utilizada. Revisa e intenta de nuevo.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Free vs Pro Cards */}
        <div className="grid grid-cols-2 gap-4">
          {/* Free */}
          <div className={`card bg-base-200 ${!isPro ? "border-2 border-base-content/20" : ""}`}>
            <div className="card-body p-5">
              <div className="flex items-center justify-between mb-0.5">
                <h3 className="text-sm font-semibold">Free</h3>
                {!isPro && <span className="badge badge-outline badge-sm">Actual</span>}
              </div>
              <p className="text-xs text-base-content/50 mb-4">Para probar</p>
              <p className="text-2xl font-bold mb-5">
                $0
                <span className="text-sm font-normal opacity-50 ml-1">
                  / siempre
                </span>
              </p>
              <FeatureList pro={false} />
            </div>
          </div>

          {/* Pro */}
          <div className={`card bg-base-200 ${isPro ? "border-2 border-primary" : "border-2 border-primary/40"} relative overflow-hidden`}>
            <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent" />
            <div className="card-body p-5 relative">
              <div className="flex items-center justify-between mb-0.5">
                <h3 className="text-sm font-semibold">Pro</h3>
                <span className="badge badge-primary badge-sm gap-1">
                  <Star size={10} fill="currentColor" />
                  {isPro ? "Activo" : "Popular"}
                </span>
              </div>
              <p className="text-xs text-base-content/50 mb-4">
                Desbloquea todo
              </p>
              <p className="text-2xl font-bold mb-5">
                $19
                <span className="text-sm font-normal opacity-50 ml-1">
                  / una vez
                </span>
              </p>
              <FeatureList pro={true} />
            </div>
          </div>
        </div>

        {/* CTA */}
        {!isPro && (
          <>
            <a
              href="https://voxeasy.lemonsqueezy.com/checkout/buy/xxxxx"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary btn-block"
            >
              <Zap size={16} /> Upgrade a Pro — $19 una vez
              <ExternalLink size={14} />
            </a>
            <p className="text-center text-xs text-base-content/50">
              Pago único, sin suscripción. Incluye todas las versiones futuras.
            </p>
          </>
        )}

        {isPro && (
          <div className="alert alert-success">
            <Check size={16} />
            <div>
              <p className="font-semibold">¡Gracias por ser Pro!</p>
              <p className="text-xs opacity-80">Tienes acceso completo a todas las funciones.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

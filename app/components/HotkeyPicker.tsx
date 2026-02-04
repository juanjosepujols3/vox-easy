"use client";

import { useState, useEffect, useCallback } from "react";
import type { Hotkey } from "../types";

interface HotkeyPickerProps {
  value: Hotkey;
  onChange: (hotkey: Hotkey) => void;
}

export default function HotkeyPicker({ value, onChange }: HotkeyPickerProps) {
  const [capturing, setCapturing] = useState(false);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      e.preventDefault();
      e.stopPropagation();

      const raw = e.key;
      if (["Shift", "Control", "Alt", "Meta"].includes(raw)) return;

      const key = raw === " " ? "Space" : raw.length === 1 ? raw.toUpperCase() : raw;

      onChange({
        cmd: e.metaKey,
        ctrl: e.ctrlKey,
        shift: e.shiftKey,
        alt: e.altKey,
        key,
      });
      setCapturing(false);
    },
    [onChange]
  );

  useEffect(() => {
    if (!capturing) return;
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [capturing, handleKeyDown]);

  const keys: string[] = [];
  if (value.cmd) keys.push("⌘");
  if (value.ctrl) keys.push("Ctrl");
  if (value.shift) keys.push("Shift");
  if (value.alt) keys.push("Alt");
  keys.push(value.key);

  return (
    <div className="flex items-center gap-3">
      <div
        className={`flex items-center gap-1 px-3 py-2 rounded-lg border transition-all ${
          capturing
            ? "border-primary bg-primary/5"
            : "border-base-300 bg-base-300"
        }`}
      >
        {keys.map((k, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-base-content/50 text-xs">+</span>}
            <kbd className="kbd kbd-sm">{k}</kbd>
          </span>
        ))}
      </div>

      <button
        onClick={() => setCapturing((c) => !c)}
        className={`btn btn-sm ${capturing ? "btn-error animate-pulse" : "btn-ghost"}`}
      >
        {capturing ? "Presiona una tecla..." : "Cambiar"}
      </button>
    </div>
  );
}

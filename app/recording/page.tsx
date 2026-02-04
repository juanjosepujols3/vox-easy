"use client";

import { useEffect, useState } from "react";

export default function RecordingPopup() {
  const [dots, setDots] = useState<number[]>([2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2]);

  useEffect(() => {
    const interval = setInterval(() => {
      setDots(prev =>
        prev.map(() => Math.random() * 6 + 2)
      );
    }, 150);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-screen flex items-center justify-center bg-transparent">
      <div
        className="flex items-center gap-[3px] px-6 py-3 rounded-full shadow-2xl"
        style={{
          backgroundColor: "rgba(30, 32, 36, 0.95)",
          boxShadow: "0 4px 30px rgba(0, 0, 0, 0.5)",
        }}
      >
        {dots.map((height, i) => (
          <div
            key={i}
            className="w-[3px] rounded-full bg-white/80 transition-all duration-150"
            style={{
              height: `${height}px`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

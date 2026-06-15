"use client";

import { useState } from "react";

interface Props {
  b64png: string;
  score?: number;
}

export default function HeatmapViewer({ b64png, score }: Props) {
  const [intensity, setIntensity] = useState(0.85);

  return (
    <div className="space-y-4">
      <div className="relative rounded-xl overflow-hidden bg-black/40">
        <img
          src={`data:image/png;base64,${b64png}`}
          // BUG-09 fix: descriptive alt text. Inferno colormap: purple=clean, yellow=suspicious.
          alt={
            score !== undefined
              ? `Manipulation heatmap — anomaly score: ${Math.round(score * 100)}%`
              : "Manipulation Heatmap"
          }
          className="w-full max-h-96 object-contain"
          style={{
            // BUG-09 fix: opacity only — do NOT use hue-rotate on inferno colormap.
            // hue-rotate shifts yellow (manipulation) → green (misleadingly looks safe)
            // and purple (clean) → cyan (misleadingly looks suspicious).
            opacity: intensity,
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 px-4 py-2 bg-gradient-to-t from-black/80 to-transparent">
          <p className="font-mono text-xs text-white/40">
            Purple = clean · Orange/Yellow = manipulation artifacts
          </p>
        </div>
      </div>

      {/* Intensity slider — controls opacity, NOT color rotation */}
      <div className="flex items-center gap-4">
        <span className="font-mono text-xs text-white/30 w-16">Intensity</span>
        <input
          type="range"
          min={0.3}
          max={1}
          step={0.01}
          value={intensity}
          onChange={(e) => setIntensity(parseFloat(e.target.value))}
          className="flex-1 accent-cyan h-1"
        />
        <span className="font-mono text-xs text-cyan w-10 text-right">{Math.round(intensity * 100)}%</span>
      </div>
    </div>
  );
}

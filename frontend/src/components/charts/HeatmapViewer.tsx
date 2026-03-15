"use client";

import { useState } from "react";

interface Props {
  b64png: string;
}

export default function HeatmapViewer({ b64png }: Props) {
  const [blend, setBlend] = useState(0.6);

  return (
    <div className="space-y-4">
      <div className="relative rounded-xl overflow-hidden bg-black/40">
        <img
          src={`data:image/png;base64,${b64png}`}
          alt="Manipulation Heatmap"
          className="w-full max-h-96 object-contain"
          style={{
            filter: `hue-rotate(${blend * 60}deg) saturate(${1 + blend}) brightness(${0.8 + blend * 0.4})`,
          }}
        />
        <div className="absolute bottom-0 left-0 right-0 px-4 py-2 bg-gradient-to-t from-black/80 to-transparent">
          <p className="font-mono text-xs text-white/40">
            Hot zones indicate manipulation or generation artifacts
          </p>
        </div>
      </div>

      {/* Blend slider */}
      <div className="flex items-center gap-4">
        <span className="font-mono text-xs text-white/30 w-16">Enhance</span>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={blend}
          onChange={(e) => setBlend(parseFloat(e.target.value))}
          className="flex-1 accent-cyan h-1"
        />
        <span className="font-mono text-xs text-cyan w-10 text-right">{Math.round(blend * 100)}%</span>
      </div>
    </div>
  );
}

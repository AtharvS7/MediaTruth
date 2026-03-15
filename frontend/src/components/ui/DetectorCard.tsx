"use client";

import { motion } from "framer-motion";

interface Props {
  label: string;
  score?: number;
}

const THRESHOLDS = [
  { max: 0.3,  color: "#00f5ff", label: "Clean" },
  { max: 0.6,  color: "#b8ff57", label: "Suspicious" },
  { max: 1.01, color: "#ff4d6d", label: "Flagged" },
];

export default function DetectorCard({ label, score = 0 }: Props) {
  const pct = Math.round(score * 100);
  const tier = THRESHOLDS.find((t) => score < t.max) || THRESHOLDS[2];

  return (
    <div className="glass rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-white/40 uppercase tracking-widest">{label}</span>
        <span className="font-mono text-xs px-2 py-0.5 rounded-full" style={{ color: tier.color, background: tier.color + "18" }}>
          {tier.label}
        </span>
      </div>

      {/* Arc-style gauge */}
      <div className="flex items-center justify-center py-2">
        <div className="relative w-20 h-20">
          <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
            <circle cx="40" cy="40" r="30" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
            <motion.circle
              cx="40" cy="40" r="30"
              fill="none"
              stroke={tier.color}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={`${2 * Math.PI * 30}`}
              initial={{ strokeDashoffset: 2 * Math.PI * 30 }}
              animate={{ strokeDashoffset: 2 * Math.PI * 30 * (1 - score) }}
              transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
              style={{ filter: `drop-shadow(0 0 6px ${tier.color}80)` }}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-display font-bold text-lg" style={{ color: tier.color }}>{pct}%</span>
          </div>
        </div>
      </div>

      <div className="font-mono text-xs text-white/25 text-center">
        Anomaly score
      </div>
    </div>
  );
}

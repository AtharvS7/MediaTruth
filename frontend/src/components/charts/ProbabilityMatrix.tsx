"use client";

import { motion } from "framer-motion";

interface Props {
  aiGenerated: number;
  aiEdited: number;
  traditionalEdit: number;
  authentic: number;
}

const BARS = [
  { key: "aiGenerated",    label: "AI Generated",          color: "#ff4d6d" },
  { key: "aiEdited",       label: "AI Edited",             color: "#8b5cf6" },
  { key: "traditionalEdit",label: "Traditionally Edited",  color: "#b8ff57" },
  { key: "authentic",      label: "Authentic / Original",  color: "#00f5ff" },
];

export default function ProbabilityMatrix(props: Props) {
  const values: Record<string, number> = {
    aiGenerated:     props.aiGenerated,
    aiEdited:        props.aiEdited,
    traditionalEdit: props.traditionalEdit,
    authentic:       props.authentic,
  };

  return (
    <div className="space-y-5">
      {BARS.map((bar) => {
        const pct = Math.round(values[bar.key] * 100);
        return (
          <div key={bar.key}>
            <div className="flex justify-between items-center mb-2">
              <span className="font-mono text-xs text-white/50">{bar.label}</span>
              <span className="font-display font-bold text-lg" style={{ color: bar.color }}>
                {pct}%
              </span>
            </div>
            <div className="prob-bar">
              <motion.div
                className="prob-bar-fill"
                style={{ backgroundColor: bar.color, boxShadow: `0 0 12px ${bar.color}50` }}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

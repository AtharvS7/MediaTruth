"use client";

/**
 * VideoFrameTimeline — Per-frame forensic verdict visualisation.
 *
 * Renders a horizontal timeline bar where each analysed frame is
 * plotted at its timestamp position, colour-coded by verdict.
 * Hovering over a frame marker shows that frame's full probability breakdown.
 *
 * This is the key differentiator for video forensic analysis — showing
 * exactly WHICH point in the video triggered each detection.
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Film } from "lucide-react";

interface FrameResult {
  timestamp: number;
  frame_index: number;
  final_verdict: string;
  confidence: number;
  ai_generated_probability: number;
  ai_edited_probability: number;
  traditional_edit_probability: number;
  authentic_probability: number;
}

interface Props {
  frames: FrameResult[];
  durationSeconds: number;
}

const VERDICT_COLORS: Record<string, string> = {
  "Inconclusive":         "#f59e0b",
  "AI Generated":         "#ff4d6d",
  "AI Edited":            "#8b5cf6",
  "Traditionally Edited": "#b8ff57",
  "Authentic / Original": "#00f5ff",
};

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function VideoFrameTimeline({ frames, durationSeconds }: Props) {
  const [hoveredFrame, setHoveredFrame] = useState<FrameResult | null>(null);

  if (!frames || frames.length === 0) return null;

  // Sort frames by timestamp for correct display order
  const sorted = [...frames].sort((a, b) => a.timestamp - b.timestamp);

  // Count frames per verdict for the summary row
  const verdictCounts = Object.keys(VERDICT_COLORS).reduce<Record<string, number>>(
    (acc, key) => {
      acc[key] = sorted.filter((f) => f.final_verdict === key).length;
      return acc;
    },
    {}
  );

  return (
    <div className="space-y-6">
      {/* Timeline ruler */}
      <div className="relative">
        {/* Time labels */}
        <div className="flex justify-between mb-2">
          <span className="font-mono text-[10px] text-white/25">0:00</span>
          <span className="font-mono text-[10px] text-white/25">
            {formatTime(durationSeconds / 2)}
          </span>
          <span className="font-mono text-[10px] text-white/25">
            {formatTime(durationSeconds)}
          </span>
        </div>

        {/* Track */}
        <div className="relative h-10 bg-white/[0.03] rounded-full border border-white/5 overflow-visible">
          {/* Quarter markers */}
          {[0.25, 0.5, 0.75].map((q) => (
            <div
              key={q}
              className="absolute top-0 bottom-0 w-px bg-white/5"
              style={{ left: `${q * 100}%` }}
            />
          ))}

          {/* Frame markers */}
          {sorted.map((frame) => {
            const pct =
              durationSeconds > 0
                ? Math.min((frame.timestamp / durationSeconds) * 100, 99)
                : 0;
            const color =
              VERDICT_COLORS[frame.final_verdict] || "#00f5ff";
            const isHovered = hoveredFrame?.frame_index === frame.frame_index;

            return (
              <motion.button
                key={frame.frame_index}
                className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-10 focus:outline-none"
                style={{ left: `${pct}%` }}
                onMouseEnter={() => setHoveredFrame(frame)}
                onMouseLeave={() => setHoveredFrame(null)}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: frame.frame_index * 0.015, duration: 0.3 }}
                aria-label={`Frame ${frame.frame_index + 1} at ${formatTime(frame.timestamp)}: ${frame.final_verdict}`}
              >
                <motion.div
                  className="rounded-full border-2 border-obsidian-800"
                  animate={{
                    width: isHovered ? 14 : 8,
                    height: isHovered ? 14 : 8,
                  }}
                  transition={{ duration: 0.15 }}
                  style={{
                    backgroundColor: color,
                    boxShadow: isHovered
                      ? `0 0 12px ${color}, 0 0 24px ${color}60`
                      : `0 0 4px ${color}80`,
                  }}
                />
              </motion.button>
            );
          })}
        </div>

        {/* Hover detail card */}
        <AnimatePresence>
          {hoveredFrame && (
            <motion.div
              className="mt-3 glass-cyan rounded-xl p-4"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.15 }}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Film size={12} className="text-white/30" />
                  <span className="font-mono text-xs text-white/40">
                    Frame {hoveredFrame.frame_index + 1} · {formatTime(hoveredFrame.timestamp)}
                  </span>
                </div>
                <span
                  className="font-display font-semibold text-sm"
                  style={{
                    color:
                      VERDICT_COLORS[hoveredFrame.final_verdict] || "#00f5ff",
                  }}
                >
                  {hoveredFrame.final_verdict}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
                {[
                  { label: "AI Generated",    val: hoveredFrame.ai_generated_probability,    color: "#ff4d6d" },
                  { label: "AI Edited",       val: hoveredFrame.ai_edited_probability,       color: "#8b5cf6" },
                  { label: "Trad. Edit",      val: hoveredFrame.traditional_edit_probability, color: "#b8ff57" },
                  { label: "Authentic",       val: hoveredFrame.authentic_probability,        color: "#00f5ff" },
                ].map(({ label, val, color }) => (
                  <div key={label} className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-white/30">{label}</span>
                    <span className="font-mono text-[10px] font-medium" style={{ color }}>
                      {Math.round((val || 0) * 100)}%
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-3 prob-bar">
                <div
                  className="prob-bar-fill"
                  style={{
                    width: `${Math.round((hoveredFrame.confidence || 0) * 100)}%`,
                    backgroundColor:
                      VERDICT_COLORS[hoveredFrame.final_verdict] || "#00f5ff",
                  }}
                />
              </div>
              <p className="font-mono text-[10px] text-white/25 mt-1">
                {Math.round((hoveredFrame.confidence || 0) * 100)}% confidence
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {Object.entries(VERDICT_COLORS).map(([label, color]) => (
          <div
            key={label}
            className="flex items-center gap-1.5 bg-white/[0.03] border border-white/5 rounded-full px-3 py-1"
          >
            <div
              className="w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: color }}
            />
            <span className="font-mono text-[10px] text-white/40">{label}</span>
          </div>
        ))}
      </div>

      {/* Verdict breakdown summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {Object.entries(verdictCounts).map(([verdict, count]) => {
          if (count === 0) return null;
          const color = VERDICT_COLORS[verdict];
          const pct = Math.round((count / sorted.length) * 100);
          return (
            <motion.div
              key={verdict}
              className="glass rounded-xl p-3 text-center"
              style={{ borderColor: `${color}20` }}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
            >
              <p
                className="font-display font-bold text-2xl"
                style={{ color }}
              >
                {count}
              </p>
              <p className="font-mono text-[10px] text-white/30 mt-0.5 leading-tight">
                {verdict}
              </p>
              <p className="font-mono text-[10px] text-white/20 mt-1">
                {pct}% of frames
              </p>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

"use client";

/**
 * Results page — full forensic analysis dashboard.
 *
 * Fixes applied:
 *  - sessionStorage keyed by scan_id (no timer-based removal race condition)
 *  - sessionStorage cleared immediately AFTER confirmed read, not on a 3-second timer
 *  - Video per-frame timeline rendered when result.file_type === "video"
 *  - Share / copy link button
 *  - Video metadata section (duration, frames analysed)
 *  - Cleaner error states with sign-in prompt
 *  - Limited Mode banner shown when running without fine-tuned ML weights
 */

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Link2,
  Film,
  Clock,
  FlaskConical,
} from "lucide-react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import Link from "next/link";
import toast from "react-hot-toast";
import Nav from "@/components/layout/Nav";
import ProbabilityMatrix from "@/components/charts/ProbabilityMatrix";
import HeatmapViewer from "@/components/charts/HeatmapViewer";
import DetectorCard from "@/components/ui/DetectorCard";
import VideoFrameTimeline from "@/components/charts/VideoFrameTimeline";
import { getScanById } from "@/lib/api";
import { supabase } from "@/lib/supabase";

const VERDICT_CONFIG: Record<
  string,
  { color: string; icon: any; label: string }
> = {
  "AI Generated":         { color: "coral",  icon: XCircle,       label: "AI Generated" },
  "AI Edited":            { color: "violet", icon: AlertTriangle,  label: "AI Edited" },
  "Traditionally Edited": { color: "acid",   icon: AlertTriangle,  label: "Traditionally Edited" },
  "Authentic / Original": { color: "cyan",   icon: CheckCircle,   label: "Authentic" },
  "Inconclusive":         { color: "amber",  icon: HelpCircle,    label: "Inconclusive" },
};

const COLOR_MAP: Record<string, string> = {
  coral:  "#ff4d6d",
  violet: "#8b5cf6",
  acid:   "#b8ff57",
  cyan:   "#00f5ff",
  amber:  "#f59e0b",
};

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMeta, setShowMeta] = useState(false);

  // Auth guard — redirect to /auth if not signed in
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace(`/auth?redirect=/results/${id}`);
      }
    });
  }, [router, id]);

  useEffect(() => {
    if (!id) return;

    const controller = new AbortController();

    // Try sessionStorage first (immediate result after upload)
    // Key is per-scan-id to avoid stale data from previous uploads
    const cacheKey = `mt_result_${id}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        setResult(parsed);
        setLoading(false);
        // Remove immediately after confirmed read — no timer race
        sessionStorage.removeItem(cacheKey);
        return;
      } catch {
        sessionStorage.removeItem(cacheKey);
      }
    }

    // Fall back to API fetch (e.g. sharing a link, hard refresh)
    getScanById(id)
      .then((data) => {
        if (controller.signal.aborted) return;
        setResult(data?.full_result || data);
        setLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          // Not authenticated — redirect to auth with return path
          router.replace(`/auth?redirect=/results/${id}`);
          return;
        } else if (status === 404) {
          setError("Scan not found. It may have been deleted.");
        } else {
          setError("Failed to load analysis results. Please try again later.");
        }
        setLoading(false);
      });

    return () => controller.abort();
  }, [id]);

  function handleCopyLink() {
    navigator.clipboard
      .writeText(window.location.href)
      .then(() => toast.success("Link copied to clipboard!"))
      .catch(() => toast.error("Could not copy link."));
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 rounded-full border-2 border-cyan/30 border-t-cyan animate-spin" />
          <p className="font-mono text-sm text-white/40">Loading analysis…</p>
        </div>
      </div>
    );
  }

  if (error || !result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-center max-w-md px-6">
          <AlertTriangle size={32} className="text-coral" />
          <p className="font-mono text-white/60">{error || "Scan not found."}</p>
          {error?.includes("Sign in") && (
            <Link href="/auth" className="btn-primary px-6 py-2 text-sm mt-2">
              Sign In
            </Link>
          )}
          <Link href="/upload" className="text-cyan text-sm hover:underline mt-2">
            ← Back to Upload
          </Link>
        </div>
      </div>
    );
  }

  const verdict = result.final_verdict || "Authentic / Original";
  const cfg = VERDICT_CONFIG[verdict] || VERDICT_CONFIG["Authentic / Original"];
  const Icon = cfg.icon;
  const accentColor = COLOR_MAP[cfg.color];
  const isVideo = result.file_type === "video";

  // Limited mode: backend is running without fine-tuned ML weights
  // deepfake + GAN scores are 0.0 (not meaningful noise)
  const limitedMode: boolean = result.limited_mode === true;

  // Strip the [Limited Mode: ...] technical suffix from user-facing explanation
  const cleanExplanation: string = (result.explanation || "").replace(
    /\s*\[Limited Mode:.*?\]\s*$/,
    ""
  );

  const radarData = [
    { subject: "Deepfake",     score: Math.round((result.detector_scores?.deepfake_score || 0) * 100) },
    { subject: "GAN",          score: Math.round((result.detector_scores?.gan_score || 0) * 100) },
    { subject: "Manipulation", score: Math.round((result.detector_scores?.manipulation_score || 0) * 100) },
    { subject: "Metadata",     score: Math.round((result.detector_scores?.metadata_anomaly_score || 0) * 100) },
  ];

  return (
    <div className="min-h-screen relative">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-28 pb-20">

        {/* Header */}
        <motion.div
          className="flex items-start justify-between flex-wrap gap-6 mb-10"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <p className="font-mono text-xs tracking-[0.3em] text-white/30 uppercase mb-2">
              Scan ID: {id?.slice(0, 8)}…
            </p>
            <h1 className="font-display font-extrabold text-4xl md:text-5xl">
              Analysis Report
            </h1>
          </div>

          <div className="flex items-start gap-3">
            {/* Share button */}
            <button
              onClick={handleCopyLink}
              title="Copy link to this report"
              className="btn-ghost flex items-center gap-2 text-sm px-4 py-2"
            >
              <Link2 size={14} /> Copy Link
            </button>

            {/* Verdict badge */}
            <motion.div
              className="glass rounded-2xl px-8 py-6 flex items-center gap-4"
              style={{
                borderColor: accentColor + "40",
                boxShadow: `0 0 40px ${accentColor}15`,
              }}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.2 }}
            >
              <Icon size={32} style={{ color: accentColor }} />
              <div>
                <p className="font-mono text-xs text-white/30 uppercase tracking-widest mb-1">
                  Final Verdict
                </p>
                <p
                  className="font-display font-bold text-2xl"
                  style={{ color: accentColor }}
                >
                  {verdict}
                </p>
                <p className="font-mono text-xs text-white/40 mt-1">
                  {Math.round((result.confidence || 0) * 100)}% confidence
                </p>
              </div>
            </motion.div>
          </div>
        </motion.div>

        {/* Video metadata bar */}
        {isVideo && (
          <motion.div
            className="flex items-center gap-6 glass rounded-xl px-6 py-4 mb-8 flex-wrap"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
          >
            <div className="flex items-center gap-2">
              <Film size={14} className="text-cyan" />
              <span className="font-mono text-xs text-white/40">Video</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock size={14} className="text-white/30" />
              <span className="font-mono text-xs text-white/60">
                {formatDuration(result.duration_seconds || 0)} duration
              </span>
            </div>
            <div className="font-mono text-xs text-white/40">
              {result.frames_analyzed} frames analysed
            </div>
          </motion.div>
        )}

        {/* Limited Mode warning banner */}
        {limitedMode && (
          <motion.div
            className="rounded-xl px-6 py-4 mb-6 flex items-start gap-3 border"
            style={{
              background: "rgba(184,255,87,0.04)",
              borderColor: "rgba(184,255,87,0.25)",
            }}
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <FlaskConical size={16} className="text-acid mt-0.5 shrink-0" />
            <div>
              <p className="font-display font-semibold text-sm text-acid mb-1">
                Limited Analysis Mode
              </p>
              <p className="font-body text-xs text-white/50 leading-relaxed">
                Deepfake and GAN ML detectors require fine-tuned model weights to produce
                meaningful results. They are currently{" "}
                <strong className="text-white/70">disabled</strong>. This analysis
                is based on{" "}
                <strong className="text-white/70">Error Level Analysis (ELA)</strong>{" "}
                and{" "}
                <strong className="text-white/70">EXIF metadata forensics</strong>{" "}
                only — both of which are fully functional.
              </p>
            </div>
          </motion.div>
        )}

        {/* Explanation */}
        {cleanExplanation && (
          <motion.div
            className="glass rounded-xl px-6 py-4 mb-8 flex items-start gap-3"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.25 }}
          >
            <Info size={16} className="text-cyan mt-0.5 shrink-0" />
            <p className="font-body text-sm text-white/60 leading-relaxed">
              {cleanExplanation}
            </p>
          </motion.div>
        )}

        {/* Main grid — probability matrix + radar */}
        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          <motion.div
            className="glass-cyan rounded-2xl p-6"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
          >
            <h2 className="font-display font-semibold text-lg mb-6">
              Probability Matrix
            </h2>
            <ProbabilityMatrix
              aiGenerated={result.ai_generated_probability || 0}
              aiEdited={result.ai_edited_probability || 0}
              traditionalEdit={result.traditional_edit_probability || 0}
              authentic={result.authentic_probability || 0}
            />
          </motion.div>

          <motion.div
            className="glass-cyan rounded-2xl p-6"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.35 }}
          >
            <h2 className="font-display font-semibold text-lg mb-4">
              Detector Signals
            </h2>
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.07)" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{
                    fill: "rgba(255,255,255,0.4)",
                    fontSize: 12,
                    fontFamily: "var(--font-mono)",
                  }}
                />
                <Radar
                  name="Score"
                  dataKey="score"
                  stroke={accentColor}
                  fill={accentColor}
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0d0d1a",
                    border: "1px solid rgba(0,245,255,0.2)",
                    borderRadius: 8,
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [`${v}%`, "Anomaly Score"]}
                />
              </RadarChart>
            </ResponsiveContainer>
          </motion.div>
        </div>

        {/* Manipulation heatmap — image only */}
        {!isVideo && result.manipulation_heatmap && (
          <motion.div
            className="glass-cyan rounded-2xl p-6 mb-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <h2 className="font-display font-semibold text-lg mb-4">
              Manipulation Heatmap
              <span className="ml-2 font-mono text-xs text-white/30 font-normal">
                inferno colormap · purple=clean · yellow=suspicious
              </span>
            </h2>
            <HeatmapViewer b64png={result.manipulation_heatmap} />
          </motion.div>
        )}

        {/* Video frame timeline — video only */}
        {isVideo && result.per_frame_results?.length > 0 && (
          <motion.div
            className="glass-cyan rounded-2xl p-6 mb-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <h2 className="font-display font-semibold text-lg mb-6">
              Per-Frame Forensic Timeline
              <span className="ml-2 font-mono text-xs text-white/30 font-normal">
                hover a frame marker to inspect
              </span>
            </h2>
            <VideoFrameTimeline
              frames={result.per_frame_results}
              durationSeconds={result.duration_seconds || 0}
            />
          </motion.div>
        )}

        {/* Detector cards */}
        <motion.div
          className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.45 }}
        >
          <DetectorCard
            label="Deepfake"
            score={limitedMode ? undefined : result.detector_scores?.deepfake_score}
            disabled={limitedMode}
            disabledLabel="No weights"
          />
          <DetectorCard
            label="GAN Detect"
            score={limitedMode ? undefined : result.detector_scores?.gan_score}
            disabled={limitedMode}
            disabledLabel="No weights"
          />
          <DetectorCard label="Manipulation" score={result.detector_scores?.manipulation_score} />
          <DetectorCard label="Metadata" score={result.detector_scores?.metadata_anomaly_score} />
        </motion.div>

        {/* Metadata / findings */}
        {result.metadata_findings?.length > 0 && (
          <motion.div
            className="glass rounded-2xl overflow-hidden mb-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
          >
            <button
              onClick={() => setShowMeta(!showMeta)}
              className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/5 transition-colors"
            >
              <span className="font-display font-semibold">
                Forensic Findings ({result.metadata_findings.length})
              </span>
              {showMeta ? (
                <ChevronUp size={18} className="text-white/40" />
              ) : (
                <ChevronDown size={18} className="text-white/40" />
              )}
            </button>
            {showMeta && (
              <div className="px-6 pb-6 space-y-2">
                {result.metadata_findings.map((f: string, i: number) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-sm font-mono text-white/60"
                  >
                    <span className="mt-0.5 shrink-0 text-cyan/40">›</span>
                    <span>{f}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Footer actions */}
        <motion.div
          className="flex gap-3"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.55 }}
        >
          <Link href="/upload" className="btn-ghost text-sm px-6 py-2">
            ← Analyse Another File
          </Link>
          <Link href="/history" className="btn-ghost text-sm px-6 py-2">
            View History
          </Link>
        </motion.div>
      </div>
    </div>
  );
}

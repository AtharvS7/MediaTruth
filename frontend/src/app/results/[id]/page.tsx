"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { Shield, AlertTriangle, CheckCircle, XCircle, Info, ChevronDown, ChevronUp } from "lucide-react";
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from "recharts";
import Link from "next/link";
import Nav from "@/components/layout/Nav";
import ProbabilityMatrix from "@/components/charts/ProbabilityMatrix";
import HeatmapViewer from "@/components/charts/HeatmapViewer";
import DetectorCard from "@/components/ui/DetectorCard";
import { getScanById } from "@/lib/api";

const VERDICT_CONFIG: Record<string, { color: string; icon: any; label: string }> = {
  "AI Generated":          { color: "coral",  icon: XCircle,       label: "AI Generated" },
  "AI Edited":             { color: "violet", icon: AlertTriangle,  label: "AI Edited" },
  "Traditionally Edited":  { color: "acid",   icon: AlertTriangle,  label: "Traditionally Edited" },
  "Authentic / Original":  { color: "cyan",   icon: CheckCircle,   label: "Authentic" },
};

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showMeta, setShowMeta] = useState(false);

  useEffect(() => {
    // Try sessionStorage first (immediate after upload)
    const cached = sessionStorage.getItem("mt_result");
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        if (parsed.scan_id === id) {
          setResult(parsed);
          setLoading(false);
          return;
        }
      } catch {}
    }
    // Fetch from API — BUG-013 fix: added .catch() handler
    getScanById(id)
      .then((data) => {
        setResult(data?.full_result || data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load scan:", err);
        // BUG-017: Show meaningful message for auth errors
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          setError("Sign in to view this scan. This scan belongs to an authenticated user.");
        } else if (status === 404) {
          setError("Scan not found. It may have been deleted.");
        } else {
          setError("Failed to load analysis results. Please try again later.");
        }
        setResult(null);
        setLoading(false);
      });
  }, [id]);

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
          {(error?.includes("Sign in")) && (
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
  const colorMap: Record<string, string> = {
    coral: "#ff4d6d", violet: "#8b5cf6", acid: "#b8ff57", cyan: "#00f5ff",
  };
  const accentColor = colorMap[cfg.color];

  const radarData = [
    { subject: "Deepfake",    score: Math.round((result.detector_scores?.deepfake_score || 0) * 100) },
    { subject: "GAN",         score: Math.round((result.detector_scores?.gan_score || 0) * 100) },
    { subject: "Manipulation",score: Math.round((result.detector_scores?.manipulation_score || 0) * 100) },
    { subject: "Metadata",    score: Math.round((result.detector_scores?.metadata_anomaly_score || 0) * 100) },
  ];

  return (
    <div className="min-h-screen relative">
      <Nav />
      <div className="max-w-6xl mx-auto px-6 pt-28 pb-20">

        {/* Header */}
        <motion.div
          className="flex items-start justify-between flex-wrap gap-6 mb-12"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        >
          <div>
            <p className="font-mono text-xs tracking-[0.3em] text-white/30 uppercase mb-2">Scan ID: {id?.slice(0,8)}…</p>
            <h1 className="font-display font-extrabold text-4xl md:text-5xl">Analysis Report</h1>
          </div>

          {/* Verdict badge */}
          <motion.div
            className="glass rounded-2xl px-8 py-6 flex items-center gap-4"
            style={{ borderColor: accentColor + "40", boxShadow: `0 0 40px ${accentColor}15` }}
            initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2 }}
          >
            <Icon size={32} style={{ color: accentColor }} />
            <div>
              <p className="font-mono text-xs text-white/30 uppercase tracking-widest mb-1">Final Verdict</p>
              <p className="font-display font-bold text-2xl" style={{ color: accentColor }}>{verdict}</p>
              <p className="font-mono text-xs text-white/40 mt-1">
                {Math.round((result.confidence || 0) * 100)}% confidence
              </p>
            </div>
          </motion.div>
        </motion.div>

        {/* Explanation */}
        {result.explanation && (
          <motion.div
            className="glass rounded-xl px-6 py-4 mb-8 flex items-start gap-3"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }}
          >
            <Info size={16} className="text-cyan mt-0.5 shrink-0" />
            <p className="font-body text-sm text-white/60 leading-relaxed">{result.explanation}</p>
          </motion.div>
        )}

        {/* Main grid */}
        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* Probability Matrix */}
          <motion.div
            className="glass-cyan rounded-2xl p-6"
            initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}
          >
            <h2 className="font-display font-semibold text-lg mb-6">Probability Matrix</h2>
            <ProbabilityMatrix
              aiGenerated={result.ai_generated_probability || 0}
              aiEdited={result.ai_edited_probability || 0}
              traditionalEdit={result.traditional_edit_probability || 0}
              authentic={result.authentic_probability || 0}
            />
          </motion.div>

          {/* Radar chart */}
          <motion.div
            className="glass-cyan rounded-2xl p-6"
            initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.35 }}
          >
            <h2 className="font-display font-semibold text-lg mb-4">Detector Signals</h2>
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(255,255,255,0.07)" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 12, fontFamily: "var(--font-mono)" }}
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
                  contentStyle={{ background: "#0d0d1a", border: "1px solid rgba(0,245,255,0.2)", borderRadius: 8, fontFamily: "var(--font-mono)", fontSize: 12 }}
                  formatter={(v: number) => [`${v}%`, "Anomaly Score"]}
                />
              </RadarChart>
            </ResponsiveContainer>
          </motion.div>
        </div>

        {/* Heatmap */}
        {result.manipulation_heatmap && (
          <motion.div
            className="glass-cyan rounded-2xl p-6 mb-6"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
          >
            <h2 className="font-display font-semibold text-lg mb-4">Manipulation Heatmap</h2>
            <HeatmapViewer b64png={result.manipulation_heatmap} />
          </motion.div>
        )}

        {/* Detector cards */}
        <motion.div
          className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}
        >
          <DetectorCard label="Deepfake"     score={result.detector_scores?.deepfake_score} />
          <DetectorCard label="GAN"          score={result.detector_scores?.gan_score} />
          <DetectorCard label="Manipulation" score={result.detector_scores?.manipulation_score} />
          <DetectorCard label="Metadata"     score={result.detector_scores?.metadata_anomaly_score} />
        </motion.div>

        {/* Metadata findings */}
        {result.metadata_findings?.length > 0 && (
          <motion.div
            className="glass rounded-2xl overflow-hidden mb-6"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
          >
            <button
              onClick={() => setShowMeta(!showMeta)}
              className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/5 transition-colors"
            >
              <span className="font-display font-semibold">Metadata Findings ({result.metadata_findings.length})</span>
              {showMeta ? <ChevronUp size={18} className="text-white/40" /> : <ChevronDown size={18} className="text-white/40" />}
            </button>
            {showMeta && (
              <div className="px-6 pb-6 space-y-2">
                {result.metadata_findings.map((f: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-sm font-mono text-white/60">
                    <span className="mt-0.5 shrink-0">›</span>
                    <span>{f}</span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

      </div>
    </div>
  );
}

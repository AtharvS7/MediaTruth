"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { format } from "date-fns";
import Link from "next/link";
import { Film, Image as ImageIcon, ArrowRight, Clock, AlertTriangle } from "lucide-react";
import Nav from "@/components/layout/Nav";
import { getScanHistory } from "@/lib/api";

const VERDICT_COLORS: Record<string, string> = {
  "AI Generated":         "#ff4d6d",
  "AI Edited":            "#8b5cf6",
  "Traditionally Edited": "#b8ff57",
  "Authentic / Original": "#00f5ff",
};

export default function HistoryPage() {
  const [scans, setScans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    setError(null);
    // BUG-014 fix: added .catch() handler
    getScanHistory(page)
      .then((d) => {
        setScans(d.scans || []);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load history:", err);
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          setError("Please sign in to view your scan history.");
        } else {
          setError("Failed to load scan history. Please try again.");
        }
        setScans([]);
        setLoading(false);
      });
  }, [page]);

  return (
    <div className="min-h-screen relative">
      <Nav />
      <div className="max-w-4xl mx-auto px-6 pt-28 pb-20">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <p className="font-mono text-xs tracking-[0.3em] text-cyan/50 uppercase mb-2">Audit Trail</p>
          <h1 className="font-display font-bold text-4xl md:text-5xl mb-10">Scan History</h1>
        </motion.div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 rounded-full border-2 border-cyan/30 border-t-cyan animate-spin" />
          </div>
        ) : error ? (
          <div className="glass rounded-2xl p-12 text-center">
            <AlertTriangle size={32} className="text-coral mx-auto mb-4" />
            <p className="font-mono text-white/50 mb-4">{error}</p>
            {error.includes("sign in") && (
              <Link href="/auth" className="btn-primary inline-flex gap-2">
                Sign In
              </Link>
            )}
          </div>
        ) : scans.length === 0 ? (
          <div className="glass rounded-2xl p-12 text-center">
            <p className="font-mono text-white/30">No scans found. Upload media to get started.</p>
            <Link href="/upload" className="btn-primary inline-flex mt-6 gap-2">
              Upload Media <ArrowRight size={16} />
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {scans.map((scan, i) => {
              const color = VERDICT_COLORS[scan.verdict] || "#00f5ff";
              return (
                <motion.div
                  key={scan.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                >
                  <Link href={`/results/${scan.id}`}>
                    <div className="glass rounded-xl px-6 py-5 flex items-center gap-4 hover:border-white/10 hover:bg-white/[0.03] transition-all group">
                      {/* Type icon */}
                      <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center shrink-0">
                        {scan.file_type === "video"
                          ? <Film size={18} className="text-white/40" />
                          : <ImageIcon size={18} className="text-white/40" />}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="font-display font-medium text-sm truncate">{scan.filename || scan.id}</p>
                        <p className="flex items-center gap-1.5 font-mono text-xs text-white/30 mt-0.5">
                          <Clock size={10} />
                          {scan.created_at ? format(new Date(scan.created_at), "MMM d, yyyy · HH:mm") : "—"}
                        </p>
                      </div>

                      {/* Verdict */}
                      <div className="text-right shrink-0">
                        <span className="font-mono text-xs font-medium" style={{ color }}>
                          {scan.verdict || "—"}
                        </span>
                        {scan.confidence != null && (
                          <p className="font-mono text-xs text-white/25 mt-0.5">
                            {Math.round(scan.confidence * 100)}% conf.
                          </p>
                        )}
                      </div>

                      <ArrowRight size={16} className="text-white/20 group-hover:text-cyan transition-colors shrink-0" />
                    </div>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {scans.length >= 20 && (
          <div className="flex justify-center gap-3 mt-8">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-ghost text-sm px-4 py-2 disabled:opacity-30">
              Previous
            </button>
            <span className="font-mono text-sm text-white/30 flex items-center">Page {page}</span>
            <button onClick={() => setPage(p => p + 1)} className="btn-ghost text-sm px-4 py-2">
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

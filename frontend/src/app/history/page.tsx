"use client";

/**
 * History page — paginated scan history with delete support.
 *
 * Fixes applied:
 *  - Pagination: "Next" disabled when result count < page_size (was infinite)
 *  - Delete: per-scan delete button with inline confirm, IDOR-protected via backend
 *  - Skeleton loading: animated placeholder cards instead of a bare spinner
 *  - Sign-in prompt when unauthenticated
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { format } from "date-fns";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Film,
  Image as ImageIcon,
  ArrowRight,
  Clock,
  AlertTriangle,
  Trash2,
  Check,
  X,
} from "lucide-react";
import Nav from "@/components/layout/Nav";
import { getScanHistory, deleteScan } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import toast from "react-hot-toast";

const VERDICT_COLORS: Record<string, string> = {
  "Inconclusive":         "#f59e0b",
  "AI Generated":         "#ff4d6d",
  "AI Edited":            "#8b5cf6",
  "Traditionally Edited": "#b8ff57",
  "Authentic / Original": "#00f5ff",
};

const PAGE_SIZE = 20;

/** Animated skeleton placeholder for a scan row */
function SkeletonRow() {
  return (
    <div className="glass rounded-xl px-6 py-5 flex items-center gap-4 animate-pulse">
      <div className="w-10 h-10 rounded-xl bg-white/5 shrink-0" />
      <div className="flex-1 space-y-2 min-w-0">
        <div className="h-3 bg-white/5 rounded-full w-2/5" />
        <div className="h-2 bg-white/5 rounded-full w-1/4" />
      </div>
      <div className="h-3 bg-white/5 rounded-full w-24 shrink-0" />
    </div>
  );
}

interface Scan {
  id: string;
  file_type: "image" | "video";
  filename?: string;
  verdict?: string;
  confidence?: number;
  created_at?: string;
}

export default function HistoryPage() {
  const router = useRouter();
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  // Track which scan is in "confirm delete" state
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Auth guard — redirect to /auth if not signed in
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/auth?redirect=/history");
      }
    });
  }, [router]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    getScanHistory(page, PAGE_SIZE)
      .then((d) => {
        if (controller.signal.aborted) return;
        const rows: Scan[] = d.scans || [];
        setScans(rows);
        // If we got a full page, there may be more
        setHasMore(rows.length >= PAGE_SIZE);
        setLoading(false);
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          setError("Please sign in to view your scan history.");
        } else {
          setError("Failed to load scan history. Please try again.");
        }
        setScans([]);
        setHasMore(false);
        setLoading(false);
      });
    // Cleanup: abort in-flight request on unmount or page change.
    // This prevents the React StrictMode double-mount from firing two API calls.
    return () => controller.abort();
  }, [page]);


  async function handleDelete(scanId: string) {
    setDeletingId(scanId);
    try {
      await deleteScan(scanId);
      setScans((prev) => prev.filter((s) => s.id !== scanId));
      toast.success("Scan deleted.");
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 401) {
        toast.error("Sign in to delete scans.");
      } else if (status === 403) {
        toast.error("You can only delete your own scans.");
      } else {
        toast.error("Failed to delete scan.");
      }
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  }

  return (
    <div className="min-h-screen relative">
      <Nav />
      <div className="max-w-4xl mx-auto px-6 pt-28 pb-20">

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <p className="font-mono text-xs tracking-[0.3em] text-cyan/50 uppercase mb-2">
            Audit Trail
          </p>
          <h1 className="font-display font-bold text-4xl md:text-5xl mb-10">
            Scan History
          </h1>
        </motion.div>

        {/* Skeleton loading */}
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : error ? (
          <div className="glass rounded-2xl p-12 text-center">
            <AlertTriangle size={32} className="text-coral mx-auto mb-4" />
            <p className="font-mono text-white/50 mb-4">{error}</p>
            {error.toLowerCase().includes("sign in") && (
              <Link href="/auth" className="btn-primary inline-flex gap-2">
                Sign In
              </Link>
            )}
          </div>
        ) : scans.length === 0 ? (
          <div className="glass rounded-2xl p-12 text-center">
            <p className="font-mono text-white/30">
              No scans found. Upload media to get started.
            </p>
            <Link href="/upload" className="btn-primary inline-flex mt-6 gap-2">
              Upload Media <ArrowRight size={16} />
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {scans.map((scan, i) => {
              const color = VERDICT_COLORS[scan.verdict || ""] || "#00f5ff";
              const isConfirming = confirmDeleteId === scan.id;
              const isDeleting = deletingId === scan.id;

              return (
                <motion.div
                  key={scan.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  transition={{ delay: i * 0.04 }}
                  layout
                >
                  <div className="glass rounded-xl px-5 py-4 flex items-center gap-3 hover:border-white/10 hover:bg-white/[0.02] transition-all group">
                    {/* Type icon */}
                    <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center shrink-0">
                      {scan.file_type === "video" ? (
                        <Film size={17} className="text-white/40" />
                      ) : (
                        <ImageIcon size={17} className="text-white/40" />
                      )}
                    </div>

                    {/* File info — clicking navigates to result */}
                    <Link
                      href={`/results/${scan.id}`}
                      className="flex-1 min-w-0 group/link"
                    >
                      <p className="font-display font-medium text-sm truncate group-hover/link:text-cyan transition-colors">
                        {scan.filename || scan.id}
                      </p>
                      <p className="flex items-center gap-1.5 font-mono text-xs text-white/30 mt-0.5">
                        <Clock size={10} />
                        {scan.created_at
                          ? format(new Date(scan.created_at), "MMM d, yyyy · HH:mm")
                          : "—"}
                      </p>
                    </Link>

                    {/* Verdict */}
                    <div className="text-right shrink-0 mr-2">
                      <span
                        className="font-mono text-xs font-medium"
                        style={{ color }}
                      >
                        {scan.verdict || "—"}
                      </span>
                      {scan.confidence != null && (
                        <p className="font-mono text-xs text-white/25 mt-0.5">
                          {Math.round(scan.confidence * 100)}% conf.
                        </p>
                      )}
                    </div>

                    {/* Delete button / confirm */}
                    {isConfirming ? (
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => handleDelete(scan.id)}
                          disabled={isDeleting}
                          className="flex items-center gap-1 text-xs font-mono text-coral border border-coral/40 rounded-lg px-2.5 py-1.5 hover:bg-coral/10 transition-colors disabled:opacity-50"
                        >
                          {isDeleting ? (
                            <span className="w-3 h-3 rounded-full border border-coral/60 border-t-transparent animate-spin" />
                          ) : (
                            <Check size={12} />
                          )}
                          Delete
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="p-1.5 text-white/30 hover:text-white/60 transition-colors"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmDeleteId(scan.id)}
                        title="Delete this scan"
                        className="shrink-0 p-2 text-white/10 hover:text-coral/70 opacity-0 group-hover:opacity-100 transition-all"
                      >
                        <Trash2 size={15} />
                      </button>
                    )}

                    {!isConfirming && (
                      <Link
                        href={`/results/${scan.id}`}
                        className="shrink-0 text-white/20 group-hover:text-cyan transition-colors"
                      >
                        <ArrowRight size={16} />
                      </Link>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {!loading && !error && (page > 1 || hasMore) && (
          <div className="flex justify-center items-center gap-3 mt-8">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-ghost text-sm px-5 py-2 disabled:opacity-30"
            >
              ← Previous
            </button>
            <span className="font-mono text-sm text-white/30">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore}
              className="btn-ghost text-sm px-5 py-2 disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

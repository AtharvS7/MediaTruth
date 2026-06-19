"use client";

/**
 * Upload page — drag-and-drop media upload with real forensic analysis pipeline.
 *
 * Fixes applied:
 *  - Progress simulation now completes only after the API resolves (not on a timer alone)
 *  - AbortController wired up for video cancellation (X button)
 *  - Retry resets ALL state (stepIdx, progress, stage)
 *  - Video-specific UX: warning message + cancel button + extended timeout
 *  - File type-specific step labels
 *  - sessionStorage keyed by scan_id to prevent race condition on results page
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload,
  Image as ImageIcon,
  Film,
  AlertCircle,
  Loader2,
  X,
  Clock,
} from "lucide-react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { analyzeMedia } from "@/lib/api";
import Nav from "@/components/layout/Nav";
import { supabase } from "@/lib/supabase";

type Stage = "idle" | "uploading" | "analyzing" | "done" | "error";

const IMAGE_STEPS = [
  "Extracting image features…",
  "Running EfficientNet-B5 deepfake classifier…",
  "CNNDetect GAN fingerprint detection…",
  "Localizing manipulation regions (ELA + DCT)…",
  "Parsing EXIF metadata…",
  "Aggregating confidence matrix…",
  "Generating forensic verdict…",
];

const VIDEO_STEPS = [
  "Extracting video frames (OpenCV)…",
  "Running deepfake classifier on frames…",
  "GAN fingerprint detection per frame…",
  "ELA + DCT manipulation localization…",
  "Parsing video metadata…",
  "Aggregating per-frame temporal signals…",
  "Generating forensic verdict…",
];

export default function UploadPage() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [progress, setProgress] = useState(0);

  const previewUrlRef = useRef<string | null>(null);
  const stepIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const isVideo = file?.type.startsWith("video/") ?? false;
  const ANALYSIS_STEPS = isVideo ? VIDEO_STEPS : IMAGE_STEPS;

  // ── Auth guard (defence-in-depth: middleware is primary, this is backup) ────
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) {
        router.replace("/auth?redirect=/upload");
      }
    });
  }, [router]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      if (stepIntervalRef.current) clearInterval(stepIntervalRef.current);
    };
  }, []);

  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    setStage("idle");
    setStepIdx(0);
    setProgress(0);
    if (f.type.startsWith("image/")) {
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      const url = URL.createObjectURL(f);
      previewUrlRef.current = url;
      setPreview(url);
    } else {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = null;
      }
      setPreview(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "image/*": [".jpg", ".jpeg", ".png", ".webp", ".bmp"],
      "video/*": [".mp4", ".mov", ".avi", ".webm", ".mkv"],
    },
    maxSize: 500 * 1024 * 1024,
    multiple: false,
    disabled: stage !== "idle",
  });

  function clearStepInterval() {
    if (stepIntervalRef.current) {
      clearInterval(stepIntervalRef.current);
      stepIntervalRef.current = null;
    }
  }

  /** Full state reset — used by retry and cancel. */
  function resetToIdle() {
    clearStepInterval();
    setStage("idle");
    setStepIdx(0);
    setProgress(0);
  }

  function handleCancel() {
    abortControllerRef.current?.abort();
    resetToIdle();
  }

  function handleClear() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setFile(null);
    setPreview(null);
    resetToIdle();
  }

  async function handleAnalyze() {
    if (!file) return;

    // Reset all state before starting
    setStage("uploading");
    setStepIdx(0);
    setProgress(0);

    abortControllerRef.current = new AbortController();

    // Advance steps every ~900ms up to 90% — final 100% fires only on success
    const totalSteps = ANALYSIS_STEPS.length;
    let currentStep = 0;
    stepIntervalRef.current = setInterval(() => {
      if (currentStep < totalSteps - 2) {
        currentStep++;
        setStepIdx(currentStep);
        // Map steps to 0–90% range, keeping the last 10% for the API response
        setProgress(Math.round((currentStep / (totalSteps - 1)) * 90));
      }
    }, 900);

    try {
      setStage("analyzing");
      const rawResult = await analyzeMedia(file, abortControllerRef.current.signal);

      // BUG-11 fix: merge parent scan metadata with full_result analysis data.
      const result = rawResult?.full_result
        ? { ...rawResult, ...rawResult.full_result }
        : rawResult;

      // API resolved — complete the progress animation
      clearStepInterval();
      setStepIdx(totalSteps - 1);
      setProgress(100);
      setStage("done");

      // Key sessionStorage by scan_id to prevent race condition
      // BUG-12 fix: catch QuotaExceededError (sessionStorage ~5MB limit)
      // Video results with 60 frames can exceed this limit silently.
      const cacheKey = `mt_result_${result.scan_id}`;
      try {
        sessionStorage.setItem(cacheKey, JSON.stringify(result));
      } catch (storageErr) {
        console.warn("[MediaTruth] sessionStorage quota exceeded, skipping cache:", storageErr);
        // Navigation still works — results page will fall back to API fetch
      }
      setTimeout(() => router.push(`/results/${result.scan_id}`), 500);
    } catch (err: any) {
      clearStepInterval();

      // Silently reset on deliberate user cancellation
      if (err?.name === "AbortError" || err?.code === "ERR_CANCELED") {
        resetToIdle();
        return;
      }

      setStage("error");
      const status = err?.response?.status;
      if (status === 422) {
        toast.error("Unsupported file type or file too large.");
      } else if (status === 429) {
        toast.error("Rate limit reached. Please wait a moment.");
      } else if (status === 401 || status === 403) {
        toast.error("Please sign in to analyze media.");
      } else {
        toast.error("Analysis failed. Please try again.");
      }
    }
  }

  return (
    <div className="min-h-screen relative">
      <Nav />
      <div className="max-w-3xl mx-auto px-6 pt-28 pb-16">

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <p className="font-mono text-xs tracking-[0.3em] text-cyan/50 uppercase mb-2">
            Forensic Analysis
          </p>
          <h1 className="font-display font-bold text-4xl md:text-5xl mb-8">
            Upload Media
          </h1>
        </motion.div>

        {/* Drop zone */}
        <div {...getRootProps()}>
          <motion.div
            className={`
              relative rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer overflow-hidden
              ${isDragActive
                ? "border-cyan bg-cyan/5 shadow-glow-cyan"
                : "border-white/10 hover:border-cyan/40 hover:bg-white/[0.02]"}
              ${stage !== "idle" ? "pointer-events-none opacity-60" : ""}
            `}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            style={{ minHeight: 280 }}
          >
            <input {...getInputProps()} />

            {/* Scan line on drag */}
            {isDragActive && (
              <motion.div
                className="absolute left-0 right-0 h-px bg-cyan/60 pointer-events-none"
                animate={{ top: ["0%", "100%"] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
              />
            )}

            <div className="flex flex-col items-center justify-center gap-4 py-16 px-8 text-center">
              {preview ? (
                <img
                  src={preview}
                  alt="File preview"
                  className="max-h-48 rounded-xl object-contain"
                />
              ) : (
                <div
                  className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${
                    isDragActive ? "bg-cyan/20" : "bg-white/5"
                  }`}
                >
                  <Upload
                    size={28}
                    className={isDragActive ? "text-cyan" : "text-white/30"}
                  />
                </div>
              )}

              {file ? (
                <div className="text-center">
                  <p className="font-display font-semibold text-lg">{file.name}</p>
                  <p className="font-mono text-xs text-white/30 mt-1">
                    {file.type} · {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                  {isVideo && (
                    <div className="flex items-center justify-center gap-1.5 mt-3 font-mono text-xs text-amber-400/70">
                      <Clock size={11} />
                      <span>Video analysis may take 1–3 minutes on CPU</span>
                    </div>
                  )}
                </div>
              ) : (
                <>
                  <p className="font-display text-xl font-semibold text-white/70">
                    {isDragActive ? "Drop to analyze" : "Drop your file here"}
                  </p>
                  <p className="font-mono text-xs text-white/30">
                    Images up to 20 MB · Videos (MP4, MOV, MKV) up to 500 MB
                  </p>
                  <div className="flex items-center gap-3 mt-2">
                    <span className="flex items-center gap-1.5 text-xs font-mono text-white/20 bg-white/5 px-3 py-1.5 rounded-full">
                      <ImageIcon size={12} /> Images
                    </span>
                    <span className="flex items-center gap-1.5 text-xs font-mono text-white/20 bg-white/5 px-3 py-1.5 rounded-full">
                      <Film size={12} /> Videos
                    </span>
                  </div>
                </>
              )}
            </div>
          </motion.div>
        </div>

        {/* Action area */}
        <AnimatePresence mode="wait">
          {file && stage === "idle" && (
            <motion.div
              key="btn"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mt-6 flex gap-3"
            >
              <button
                id="analyze-btn"
                onClick={handleAnalyze}
                className="btn-primary flex-1 flex items-center justify-center gap-2 py-4 text-base"
              >
                Run Forensic Analysis
              </button>
              <button onClick={handleClear} className="btn-ghost px-4">
                Clear
              </button>
            </motion.div>
          )}

          {(stage === "uploading" || stage === "analyzing") && (
            <motion.div
              key="progress"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-6 glass-cyan rounded-2xl p-6"
            >
              {/* Step label + cancel */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3 min-w-0">
                  <Loader2 size={16} className="text-cyan animate-spin shrink-0" />
                  <span className="font-mono text-sm text-cyan truncate">
                    {ANALYSIS_STEPS[stepIdx]}
                  </span>
                </div>
                <button
                  onClick={handleCancel}
                  title="Cancel analysis"
                  className="ml-3 shrink-0 text-white/30 hover:text-white/70 transition-colors"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Progress bar */}
              <div className="prob-bar">
                <motion.div
                  className="prob-bar-fill"
                  style={{
                    background: "linear-gradient(90deg, #00f5ff, #b8ff57)",
                    boxShadow: "0 0 8px rgba(0,245,255,0.4)",
                  }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                />
              </div>

              <div className="flex justify-between mt-2">
                <span className="font-mono text-xs text-white/30">
                  Step {Math.min(stepIdx + 1, ANALYSIS_STEPS.length)} /{" "}
                  {ANALYSIS_STEPS.length}
                </span>
                <span className="font-mono text-xs text-cyan">{progress}%</span>
              </div>

              {/* Video-specific patience message */}
              {isVideo && (
                <motion.p
                  className="font-mono text-xs text-amber-400/60 mt-3 flex items-center gap-1.5"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 5 }}
                >
                  <Clock size={11} />
                  Video analysis is CPU-intensive — analysing each frame individually.
                  Please wait…
                </motion.p>
              )}
            </motion.div>
          )}

          {stage === "error" && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-6 flex items-center gap-3 px-5 py-4 rounded-xl bg-coral/10 border border-coral/30 text-coral"
            >
              <AlertCircle size={18} className="shrink-0" />
              <span className="font-mono text-sm">
                Analysis failed. Please try a different file.
              </span>
              <button
                onClick={resetToIdle}
                className="ml-auto text-xs underline hover:no-underline"
              >
                Retry
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

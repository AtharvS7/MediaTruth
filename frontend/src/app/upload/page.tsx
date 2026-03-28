"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Image as ImageIcon, Film, AlertCircle, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { analyzeMedia } from "@/lib/api";
import Nav from "@/components/layout/Nav";

type Stage = "idle" | "uploading" | "analyzing" | "done" | "error";

const ANALYSIS_STEPS = [
  "Extracting image features…",
  "Running deepfake classifier…",
  "GAN fingerprint detection…",
  "Locating manipulation regions…",
  "Parsing EXIF metadata…",
  "Aggregating confidence matrix…",
  "Generating verdict…",
];

export default function UploadPage() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [progress, setProgress] = useState(0);

  // BUG-015: Track object URL for cleanup
  const previewUrlRef = useRef<string | null>(null);

  // BUG-015: Cleanup object URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  const onDrop = useCallback((accepted: File[]) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    if (f.type.startsWith("image/")) {
      // BUG-015: Revoke old URL before creating new one
      if (previewUrlRef.current) {
        URL.revokeObjectURL(previewUrlRef.current);
      }
      const url = URL.createObjectURL(f);
      previewUrlRef.current = url;
      setPreview(url);
    } else {
      // Revoke if switching from image to non-image
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

  async function handleAnalyze() {
    if (!file) return;
    setStage("uploading");
    setProgress(0);

    // Simulate step-through animation
    const stepInterval = setInterval(() => {
      setStepIdx((prev) => {
        if (prev < ANALYSIS_STEPS.length - 1) return prev + 1;
        clearInterval(stepInterval);
        return prev;
      });
      setProgress((prev) => Math.min(prev + 100 / ANALYSIS_STEPS.length, 95));
    }, 700);

    try {
      setStage("analyzing");
      const result = await analyzeMedia(file);
      clearInterval(stepInterval);
      setProgress(100);
      setStage("done");
      // Store result in sessionStorage and navigate to results page
      sessionStorage.setItem("mt_result", JSON.stringify(result));
      setTimeout(() => router.push(`/results/${result.scan_id}`), 500);
      // IMPROVE-007: Clear stale cache after navigation completes
      setTimeout(() => sessionStorage.removeItem("mt_result"), 3000);
    } catch (err: any) {
      clearInterval(stepInterval);
      setStage("error");
      // BUG-016: Improved error messages based on status code
      const status = err?.response?.status;
      if (status === 401 || status === 403) {
        toast.error("Please sign in to analyze media.");
      } else if (status === 422) {
        toast.error("Unsupported file type or file too large.");
      } else {
        toast.error("Analysis failed. Please try again.");
      }
    }
  }

  function handleClear() {
    // Clean up preview URL on clear
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
    setFile(null);
    setPreview(null);
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
          <p className="font-mono text-xs tracking-[0.3em] text-cyan/50 uppercase mb-2">Forensic Analysis</p>
          <h1 className="font-display font-bold text-4xl md:text-5xl mb-8">
            Upload Media
          </h1>
        </motion.div>

        {/* Drop zone */}
        <div {...getRootProps()}>
          <motion.div
            className={`
              relative rounded-2xl border-2 border-dashed transition-all duration-300 cursor-pointer overflow-hidden
              ${isDragActive ? "border-cyan bg-cyan/5 shadow-glow-cyan" : "border-white/10 hover:border-cyan/40 hover:bg-white/[0.02]"}
              ${stage !== "idle" ? "pointer-events-none" : ""}
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
                className="absolute left-0 right-0 h-px bg-cyan/60"
                animate={{ top: ["0%", "100%"] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
              />
            )}

            <div className="flex flex-col items-center justify-center gap-4 py-16 px-8 text-center">
              {preview ? (
                <img src={preview} alt="preview" className="max-h-48 rounded-xl object-contain" />
              ) : (
                <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-colors ${isDragActive ? "bg-cyan/20" : "bg-white/5"}`}>
                  <Upload size={28} className={isDragActive ? "text-cyan" : "text-white/30"} />
                </div>
              )}

              {file ? (
                <div className="text-center">
                  <p className="font-display font-semibold text-lg">{file.name}</p>
                  <p className="font-mono text-xs text-white/30 mt-1">
                    {file.type} · {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              ) : (
                <>
                  <p className="font-display text-xl font-semibold text-white/70">
                    {isDragActive ? "Drop to analyze" : "Drop your file here"}
                  </p>
                  <p className="font-mono text-xs text-white/30">
                    Images (JPG, PNG, WebP) · Videos (MP4, MOV) up to 500 MB
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

        {/* Analyze button */}
        <AnimatePresence mode="wait">
          {file && stage === "idle" && (
            <motion.div
              key="btn"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mt-6 flex gap-3"
            >
              <button onClick={handleAnalyze} className="btn-primary flex-1 flex items-center justify-center gap-2 py-4 text-base">
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
              <div className="flex items-center gap-3 mb-4">
                <Loader2 size={18} className="text-cyan animate-spin" />
                <span className="font-mono text-sm text-cyan">{ANALYSIS_STEPS[stepIdx]}</span>
              </div>

              {/* Progress bar */}
              <div className="prob-bar">
                <motion.div
                  className="prob-bar-fill"
                  style={{ background: "linear-gradient(90deg, #00f5ff, #b8ff57)" }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>

              <div className="flex justify-between mt-2">
                <span className="font-mono text-xs text-white/30">Step {stepIdx + 1} / {ANALYSIS_STEPS.length}</span>
                <span className="font-mono text-xs text-cyan">{Math.round(progress)}%</span>
              </div>
            </motion.div>
          )}

          {stage === "error" && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="mt-6 flex items-center gap-3 px-5 py-4 rounded-xl bg-coral/10 border border-coral/30 text-coral"
            >
              <AlertCircle size={18} />
              <span className="font-mono text-sm">Analysis failed. Please try a different file.</span>
              <button onClick={() => setStage("idle")} className="ml-auto text-xs underline">Retry</button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

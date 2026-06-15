"use client";

/**
 * Supabase Auth Callback Page
 *
 * Handles the redirect after a user clicks the email verification link.
 * Supabase appends ?code=… to the URL. We exchange that code for a session
 * and redirect the user to /upload on success, or back to /auth on failure.
 *
 * To enable this flow, set the Supabase Redirect URL in your project to:
 *   http://localhost:3000/auth/callback  (development)
 *   https://your-domain.com/auth/callback  (production)
 */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
import { supabase } from "@/lib/supabase";

type Status = "verifying" | "success" | "error";

export default function AuthCallbackPage() {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("verifying");
  const [message, setMessage] = useState("Verifying your account…");

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // exchangeCodeForSession reads the ?code= param from the full URL
        const { error } = await supabase.auth.exchangeCodeForSession(
          window.location.href
        );

        if (error) {
          console.error("Auth callback error:", error.message);
          setStatus("error");
          setMessage(
            error.message || "Verification failed. Please try signing in again."
          );
          setTimeout(() => router.replace("/auth"), 3000);
        } else {
          setStatus("success");
          setMessage("Account verified! Redirecting you…");
          setTimeout(() => router.replace("/upload"), 1500);
        }
      } catch (err) {
        setStatus("error");
        setMessage("Something went wrong. Please try again.");
        setTimeout(() => router.replace("/auth"), 3000);
      }
    };

    handleCallback();
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6 relative">
      {/* Logo */}
      <div className="absolute top-6 left-6">
        <span className="font-display font-bold text-xl tracking-tight text-glow-cyan">
          MEDIA<span className="text-white">TRUTH</span>
        </span>
      </div>

      <motion.div
        className="glass-cyan rounded-2xl p-10 w-full max-w-sm text-center"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <motion.div
          key={status}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center gap-4"
        >
          {status === "verifying" && (
            <Loader2 size={40} className="text-cyan animate-spin" />
          )}
          {status === "success" && (
            <CheckCircle size={40} className="text-cyan" />
          )}
          {status === "error" && (
            <XCircle size={40} className="text-coral" />
          )}

          <div>
            <p
              className="font-display font-semibold text-lg"
              style={{
                color:
                  status === "error"
                    ? "#ff4d6d"
                    : status === "success"
                    ? "#00f5ff"
                    : "white",
              }}
            >
              {status === "verifying"
                ? "Verifying"
                : status === "success"
                ? "Verified!"
                : "Error"}
            </p>
            <p className="font-mono text-sm text-white/40 mt-2">{message}</p>
          </div>

          {status === "error" && (
            <button
              onClick={() => router.replace("/auth")}
              className="btn-primary text-sm px-6 py-2 mt-2"
            >
              Back to Sign In
            </button>
          )}
        </motion.div>
      </motion.div>
    </div>
  );
}

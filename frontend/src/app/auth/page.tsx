"use client";

import { useState, Suspense } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter, useSearchParams } from "next/navigation";
import toast from "react-hot-toast";
import { Loader2, Lock, Mail, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";

type Mode = "signin" | "signup" | "reset";

/** Inner component that reads search params — must be inside Suspense */
function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Read the ?redirect= param — fall back to /upload.
  // SEC (S1): only allow same-origin relative paths to prevent open-redirect phishing.
  // Reject absolute URLs (https://evil.com) and protocol-relative URLs (//evil.com).
  const rawRedirect = searchParams.get("redirect");
  const redirectTo =
    rawRedirect && rawRedirect.startsWith("/") && !rawRedirect.startsWith("//")
      && !/[\\\x00-\x20]/.test(rawRedirect)
      ? rawRedirect
      : "/upload";

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);

    try {
      // ── Password Reset ──────────────────────────────────────────────────────
      if (mode === "reset") {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/auth`,
        });
        if (error) throw error;
        toast.success("Password reset email sent! Check your inbox.", { duration: 6000 });
        setMode("signin");
        setLoading(false);
        return;
      }

      // ── Sign Up ─────────────────────────────────────────────────────────────
      if (mode === "signup") {
        if (password.length < 6) {
          toast.error("Password must be at least 6 characters.");
          setLoading(false);
          return;
        }
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;

        // Detect already-registered email — Supabase returns success but identities=[]
        if (data.user?.identities?.length === 0) {
          toast.error("This email is already registered. Try signing in instead.", {
            duration: 5000,
          });
          setMode("signin");
          setLoading(false);
          return;
        }
        toast.success("Account created! Check your email to verify.", { duration: 6000 });
        setLoading(false);
        return;
      }

      // ── Sign In ─────────────────────────────────────────────────────────────
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      toast.success("Signed in successfully.");
      // Redirect to the page the user originally tried to visit
      router.push(redirectTo);

    } catch (err: any) {
      const msg: string = err?.message || "";
      if (msg.includes("Invalid login credentials")) {
        toast.error("Incorrect email or password.");
      } else if (msg.includes("Email not confirmed")) {
        toast.error("Please verify your email before signing in.");
      } else if (msg.includes("rate limit") || msg.includes("too many")) {
        toast.error("Too many attempts. Please wait a moment.");
      } else {
        toast.error(msg || "Authentication failed. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  const titles: Record<Mode, string> = {
    signin: "Welcome Back",
    signup: "Create Account",
    reset: "Reset Password",
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-6 relative">
      <div className="absolute top-6 left-6">
        <Link href="/" className="font-display font-bold text-xl tracking-tight text-glow-cyan">
          MEDIA<span className="text-white">TRUTH</span>
        </Link>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={mode}
          className="glass-cyan rounded-2xl p-8 w-full max-w-sm"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.35 }}
        >
          {/* Back button for reset mode */}
          {mode === "reset" && (
            <button
              onClick={() => setMode("signin")}
              className="flex items-center gap-1.5 text-xs font-mono text-white/40 hover:text-white transition-colors mb-6"
            >
              <ArrowLeft size={13} /> Back to sign in
            </button>
          )}

          <h1 className="font-display font-bold text-2xl mb-2">{titles[mode]}</h1>
          {mode === "reset" && (
            <p className="font-mono text-xs text-white/40 mb-6">
              Enter your email and we&apos;ll send a password reset link.
            </p>
          )}

          {/* Tabs: only shown in signin / signup mode */}
          {mode !== "reset" && (
            <div className="flex gap-2 mb-8 p-1 bg-white/5 rounded-xl mt-4">
              {(["signin", "signup"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`flex-1 py-2 rounded-lg font-display text-sm font-semibold transition-all ${
                    mode === m
                      ? "bg-cyan text-obsidian-950 shadow-glow-cyan"
                      : "text-white/40 hover:text-white"
                  }`}
                >
                  {m === "signin" ? "Sign In" : "Sign Up"}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <Mail size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
              <input
                id="auth-email"
                type="email"
                placeholder="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 font-mono text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-cyan/50 transition-colors"
              />
            </div>

            {mode !== "reset" && (
              <div className="relative">
                <Lock size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/30" />
                <input
                  id="auth-password"
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 font-mono text-sm text-white placeholder:text-white/25 focus:outline-none focus:border-cyan/50 transition-colors"
                />
              </div>
            )}

            {mode === "signin" && (
              <div className="text-right -mt-1">
                <button
                  type="button"
                  onClick={() => { setMode("reset"); setPassword(""); }}
                  className="font-mono text-xs text-white/30 hover:text-cyan transition-colors"
                >
                  Forgot password?
                </button>
              </div>
            )}

            <button
              id="auth-submit"
              type="submit"
              disabled={loading}
              className="btn-primary w-full flex items-center justify-center gap-2 py-3 mt-2 disabled:opacity-60"
            >
              {loading && <Loader2 size={16} className="animate-spin" />}
              {mode === "signin"
                ? "Sign In"
                : mode === "signup"
                ? "Create Account"
                : "Send Reset Link"}
            </button>
          </form>

          {mode !== "reset" && (
            <p className="text-center font-mono text-xs text-white/30 mt-6">
              {mode === "signin" ? "No account? " : "Have an account? "}
              <button
                onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
                className="text-cyan hover:underline"
              >
                {mode === "signin" ? "Sign up" : "Sign in"}
              </button>
            </p>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

/**
 * AuthPage — wraps AuthForm in Suspense.
 * Next.js 14 requires this whenever a client component uses useSearchParams().
 */
export default function AuthPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-cyan/30 border-t-cyan animate-spin" />
      </div>
    }>
      <AuthForm />
    </Suspense>
  );
}

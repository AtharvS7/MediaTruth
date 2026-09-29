"use client";
import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
export default function UpdatePassword() {
  const recoveryExchange = useRef<ReturnType<typeof supabase.auth.exchangeCodeForSession> | undefined>(undefined);
  const [ready, setReady] = useState(false);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Checking your recovery link?");
  useEffect(() => {
    const code = new URL(window.location.href).searchParams.get("code");
    if (code && !recoveryExchange.current) {
      recoveryExchange.current = supabase.auth.exchangeCodeForSession(code);
      window.history.replaceState(null, "", window.location.pathname);
    }
    if (!recoveryExchange.current) { setMessage("Request a new recovery link and open it in the same browser."); return; }
    recoveryExchange.current.then(({ error }) => {
      setReady(!error);
      setMessage(error ? "Recovery link expired. Request a new one." : "Choose a new password.");
    }).catch(() => setMessage("Recovery failed. Request a new link."));
  }, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (password !== confirm) { setMessage("Passwords must match."); return; }
    setBusy(true);
    try {
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      await supabase.auth.signOut();
      setReady(false);
      setPassword(""); setConfirm("");
      setMessage("Password updated. Sign in with your new password.");
    } catch { setMessage("Could not update the password. Try a new recovery link."); }
    finally { setBusy(false); }
  }
  return <main className="max-w-md mx-auto px-6 py-24">
    <h1 className="text-2xl mb-4">Update password</h1>
    <p role="status" className="mb-6">{message}</p>
    {ready && <form onSubmit={submit} className="flex flex-col gap-4">
      <label>New password<input className="w-full bg-white/10 p-3" type="password" autoComplete="new-password" minLength={12} required value={password} onChange={e => setPassword(e.target.value)} /></label>
      <label>Confirm password<input className="w-full bg-white/10 p-3" type="password" autoComplete="new-password" minLength={12} required value={confirm} onChange={e => setConfirm(e.target.value)} /></label>
      <button className="btn-primary" disabled={busy}>{busy ? "Saving?" : "Save password"}</button>
    </form>}
    <Link href="/auth" className="block mt-6 underline">Back to sign in</Link>
  </main>;
}

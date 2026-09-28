"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Nav from "@/components/layout/Nav";
import { cleanImageMetadata } from "@/lib/api";
import { supabase } from "@/lib/supabase";

export default function MetadataPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [download, setDownload] = useState<string | null>(null);
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) router.replace("/auth?redirect=/metadata");
    });
  }, [router]);
  useEffect(() => () => { if (download) URL.revokeObjectURL(download); }, [download]);

  async function exportCopy() {
    if (!file) return;
    setError("");
    setDownload(null);
    if (file.size > 50 * 1024 * 1024) {
      setError("Choose an image smaller than 50 MB.");
      return;
    }
    setBusy(true);
    try {
      const blob = await cleanImageMetadata(file);
      setDownload(URL.createObjectURL(blob));
    } catch (failure: unknown) {
      const response = (failure as { response?: { status?: number; data?: Blob } }).response;
      let message = "Export failed. Please try again.";
      if (response?.status === 401 || response?.status === 403) message = "Please sign in to export an image.";
      else if (response?.status === 429) message = "Too many exports. Please wait a minute.";
      else if (response?.status === 422 && response.data instanceof Blob) {
        try { message = JSON.parse(await response.data.text()).detail || message; } catch { /* use fallback */ }
      }
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <Nav />
      <main className="max-w-2xl mx-auto px-6 pt-28 pb-16">
        <h1 className="font-display text-3xl font-bold mb-6">Remove image metadata</h1>
        <p className="text-white/70 mb-4">
          Export a new PNG without source metadata such as EXIF, location, software
          tags, comments, and embedded provenance information. Your original stays unchanged.
        </p>
        <p className="text-white/70 mb-6">
          Invisible watermarks and other AI signals in the pixels may remain. This
          export does not prove an image is authentic or make AI content undetectable.
          Color appearance may change when color profiles are removed.
        </p>
        <div className="glass rounded-xl p-6 space-y-4">
          <label htmlFor="metadata-file" className="block font-semibold">Choose an image</label>
          <input id="metadata-file" type="file" accept="image/jpeg,image/png,image/webp,image/bmp"
            disabled={busy} className="block w-full"
            onChange={(event) => { setFile(event.target.files?.[0] || null); setError(""); setDownload(null); }} />
          <p className="text-sm text-white/60">JPEG, PNG, WebP or BMP. Up to 50 MB and 16 megapixels. Still images only.</p>
          <button type="button" onClick={exportCopy} disabled={!file || busy}
            className="btn-primary px-5 py-3 disabled:opacity-50">
            {busy ? "Exporting…" : "Create metadata-free copy"}
          </button>
          {error && <p role="alert" className="text-coral">{error}</p>}
          {download && <p role="status"><a href={download} download="metadata-removed.png"
            className="text-cyan underline">Download PNG copy</a></p>}
        </div>
      </main>
    </div>
  );
}

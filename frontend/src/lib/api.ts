/**
 * MediaTruth API client.
 * Talks to FastAPI backend via environment variable NEXT_PUBLIC_API_URL.
 *
 * Features:
 *  - Auto-injects Supabase Bearer token when user is signed in
 *  - AbortSignal support for cancellable requests (video analysis)
 *  - Centralised error logging
 */

import axios from "axios";
import { supabase } from "./supabase";

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 180_000, // 3 min — long enough for heavy video analysis
});

// Inject auth token if a session exists
API.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  }
  return config;
});

// Centralised response error logging
API.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url;
    // Don't log aborted requests as errors
    if (error?.name !== "AbortError" && error?.code !== "ERR_CANCELED") {
      console.error(`[MediaTruth API] ${status || "network"} error on ${url}`);
    }
    return Promise.reject(error);
  }
);

/**
 * Analyze an image or video file for forensic authenticity.
 *
 * @param file     - The File to upload and analyze
 * @param signal   - Optional AbortSignal for cancellation (especially for videos)
 */
export async function analyzeMedia(
  file: File,
  signal?: AbortSignal,
  onStage?: (stage: string) => void
): Promise<any> {
  onStage?.("uploading");
  const capabilities = await getCapabilities();
  const limit = file.type.startsWith("video/") ? capabilities.max_video_bytes : capabilities.max_image_bytes;
  if (file.size > limit) throw new Error(`File exceeds the ${limit / 1_000_000} MB limit.`);
  let job;
  if (capabilities.durable_jobs) {
    job = await uploadDurable(file, file.type.startsWith("video/") ? "video" : "image", signal);
  } else {
    const form = new FormData();
    form.append("file", file);
    job = (await API.post("/jobs", form, { signal })).data;
  }
  try {
    for (;;) {
      if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
      const { data } = await API.get(`/jobs/${job.id}`, { signal });
      onStage?.(data.stage);
      if (data.status === "completed") return data.result;
      if (data.status === "failed") throw new Error(data.error || "Analysis failed");
      if (data.status === "cancelled") throw new DOMException("Cancelled", "AbortError");
      await new Promise(resolve => setTimeout(resolve, 2500));
    }
  } catch (error) {
    if (signal?.aborted) {
      // Wait for the server to terminate the worker before declaring cancellation.
      try {
        const { data: cancellation } = await API.delete(`/jobs/${job.id}`);
        if (cancellation.status !== "cancelled") {
          throw new Error("Cancellation requested; worker acknowledgement is pending.");
        }
      }
      catch { throw new Error("Could not confirm cancellation. Check your saved history before retrying."); }
      throw new DOMException("Cancelled", "AbortError");
    }
    throw error;
  }
}

/** Fetch a single scan result by ID. */
export async function getScanById(id: string): Promise<any> {
  const { data } = await API.get(`/scan/${id}`);
  return data;
}

/** Fetch paginated scan history. */
export async function getScanHistory(
  page = 1,
  pageSize = 20
): Promise<any> {
  const { data } = await API.get("/scan/history", {
    params: { page, page_size: pageSize },
  });
  return data;
}

/** Delete a scan by ID. Requires authentication; only the owner can delete. */
export async function deleteScan(id: string): Promise<void> {
  await API.delete(`/scan/${id}`);
}

/** Download a newly encoded PNG without source metadata. */
export async function cleanImageMetadata(file: File): Promise<Blob> {
  if ((await getCapabilities()).durable_jobs) {
    if (file.size > 50_000_000) throw new Error("Cloud uploads must be under 50 MB.");
    const job = await uploadDurable(file, "clean");
    for (;;) {
      const { data } = await API.get(`/jobs/${job.id}`);
      if (data.status === "completed") {
        const { data: download } = await API.get(`/jobs/${job.id}/download`);
        const response = await fetch(download.url);
        if (!response.ok) throw new Error("Export download failed");
        return response.blob();
      }
      if (["failed", "cancelled"].includes(data.status)) throw new Error(data.error || "Export stopped");
      await new Promise(resolve => setTimeout(resolve, 2500));
    }
  }
  const form = new FormData();
  form.append("file", file);
  const { data } = await API.post("/image/clean-metadata", form, { responseType: "blob" });
  return data;
}

export async function getCapabilities() {
  return (await API.get("/capabilities")).data;
}

async function uploadDurable(file: File, kind: string, signal?: AbortSignal) {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const input_sha256 = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
  const idempotency_key = crypto.randomUUID();
  const { data } = await API.post("/uploads", {kind, filename: file.name,
    byte_size: file.size, input_sha256, idempotency_key}, { signal });
  try {
    if (data.upload) {
      const response = await fetch(data.upload.signed_url, {
        method: "PUT", body: file, signal, headers: {"Content-Type": file.type || "application/octet-stream"}
      });
      if (!response.ok) throw new Error("Private upload failed");
    }
    return (await API.post(`/uploads/${data.job.id}/finalize`, {}, { signal })).data;
  } catch (error) {
    try { await API.delete(`/jobs/${data.job.id}`); } catch { /* reservation expires */ }
    throw error;
  }
}

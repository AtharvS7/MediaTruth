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
  signal?: AbortSignal
): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const endpoint = file.type.startsWith("video/")
    ? "/video/analyze"
    : "/image/analyze";
  // CODE-13 fix: Do NOT set Content-Type manually for FormData.
  // Axios sets it automatically WITH the required multipart boundary parameter.
  // Manual override removes the boundary, breaking multipart parsing on FastAPI.
  const { data } = await API.post(endpoint, form, { signal });

  return data;
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

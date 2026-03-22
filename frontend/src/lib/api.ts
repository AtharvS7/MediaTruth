/**
 * MediaTruth API client.
 * Talks to FastAPI backend via environment variable NEXT_PUBLIC_API_URL.
 */

import axios from "axios";
import { supabase } from "./supabase";

const API = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  timeout: 120_000, // 2 min for large video analysis
});

// Inject auth token if present
API.interceptors.request.use(async (config) => {
  if (typeof window !== "undefined") {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  }
  return config;
});

export async function analyzeMedia(file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const endpoint = file.type.startsWith("video/") ? "/video/analyze" : "/image/analyze";
  const { data } = await API.post(endpoint, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function getScanById(id: string): Promise<any> {
  const { data } = await API.get(`/scan/${id}`);
  return data;
}

export async function getScanHistory(page = 1, pageSize = 20): Promise<any> {
  const { data } = await API.get("/scan/history", { params: { page, page_size: pageSize } });
  return data;
}

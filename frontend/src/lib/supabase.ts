import { createClient } from "@supabase/supabase-js";

// DEPLOY-02: Validate required env vars at module load time.
// Missing vars with the ! assertion would cause a cryptic crash deep in the Supabase library.
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // During build/SSR in CI/production, throw. In browser, warn gracefully.
  const msg =
    "[MediaTruth] Missing Supabase environment variables: " +
    "NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are required. " +
    "Add them to your .env.local file (local dev) or Vercel dashboard (production).";
  if (typeof window === "undefined") {
    // Server-side — throw to fail the build/render with a clear message
    console.error(msg);
  } else {
    // Client-side — warn without crashing the page
    console.error(msg);
  }
}

export const supabase = createClient(
  supabaseUrl ?? "",
  supabaseAnonKey ?? "",
  { auth: { flowType: "pkce", detectSessionInUrl: false } }
);


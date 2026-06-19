/**
 * Next.js Edge Middleware — Route Protection
 *
 * Protects /upload, /history and /results/* from unauthenticated access.
 * Uses @supabase/auth-helpers-nextjs to read the session from cookies.
 * Unauthenticated users are redirected to /auth with the original path stored
 * in the `redirect` query param so the auth page can send them back after login.
 */

import { createMiddlewareClient } from "@supabase/auth-helpers-nextjs";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Routes that require an authenticated session */
const PROTECTED_PATHS = ["/upload", "/history", "/results"];

export async function middleware(req: NextRequest) {
  const res = NextResponse.next();

  try {
    // createMiddlewareClient reads/refreshes the Supabase session cookie
    const supabase = createMiddlewareClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    const { pathname } = req.nextUrl;
    const isProtected = PROTECTED_PATHS.some((p) => pathname.startsWith(p));

    if (isProtected && !session) {
      const authUrl = req.nextUrl.clone();
      authUrl.pathname = "/auth";
      authUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(authUrl);
    }
  } catch {
    // If Supabase is unreachable at the edge, fall through and let the
    // page-level auth check handle it gracefully.
  }

  return res;
}

export const config = {
  // Only run middleware on the routes that need protection.
  // Excludes static files, images, API routes, and _next internals.
  matcher: ["/upload/:path*", "/history/:path*", "/results/:path*"],
};

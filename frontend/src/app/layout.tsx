import type { Metadata, Viewport } from "next";
import "@fontsource-variable/syne";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/dm-sans";
import { Toaster } from "react-hot-toast";
import Background3D from "@/components/ui/Background3D";
import "./globals.css";

// Next.js 14: themeColor and viewport MUST be in generateViewport(), not metadata.
// Putting them in metadata causes "Unsupported metadata" warnings and they are ignored.
export const viewport: Viewport = {
  themeColor: "#0d0d1a",
  width: "device-width",
  initialScale: 1,
  // viewport-fit=cover makes content reach iPhone X+ notch area
  viewportFit: "cover",
};

export const metadata: Metadata = {
  title: "MediaTruth — AI Media Forensics",
  description:
    "Detect AI-generated, AI-edited, and manipulated images and videos with state-of-the-art forensic analysis.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"
  ),
  openGraph: {
    title: "MediaTruth — AI Media Forensics",
    description:
      "Detect AI-generated, AI-edited, and manipulated images and videos.",
    images: ["/og-image.png"],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "MediaTruth — AI Media Forensics",
    description:
      "Detect AI-generated, AI-edited, and manipulated images and videos.",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
    >
      <body className="bg-obsidian-950 text-white font-body antialiased">
        <Background3D />
        <div className="fixed inset-0 bg-grid-fine pointer-events-none opacity-100" />
        <div className="fixed inset-0 bg-radial-glow pointer-events-none" />
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0d0d1a",
              color: "#e2e8f0",
              border: "1px solid rgba(0,245,255,0.2)",
              fontFamily: "var(--font-mono)",
              fontSize: "13px",
            },
          }}
        />
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Syne, JetBrains_Mono, DM_Sans } from "next/font/google";
import { Toaster } from "react-hot-toast";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700", "800"],
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["300", "400", "500"],
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["300", "400", "500", "600"],
});

export const metadata: Metadata = {
  title: "MediaTruth — AI Media Forensics",
  description: "Detect AI-generated, AI-edited, and manipulated images and videos with state-of-the-art forensic analysis.",
  openGraph: {
    title: "MediaTruth",
    description: "AI Media Forensics Platform",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${syne.variable} ${jetbrains.variable} ${dmSans.variable}`}>
      <body className="bg-obsidian-950 text-white font-body antialiased">
        <div className="fixed inset-0 bg-grid-fine bg-grid-fine pointer-events-none opacity-100" />
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

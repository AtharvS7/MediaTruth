"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Nav() {
  const path = usePathname();
  const links = [
    { href: "/upload",  label: "Analyze" },
    { href: "/history", label: "History" },
  ];

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-5 border-b border-white/5 glass">
      <Link href="/" className="font-display font-bold text-lg tracking-tight text-glow-cyan">
        MEDIA<span className="text-white">TRUTH</span>
      </Link>
      <div className="flex items-center gap-6 text-sm font-mono text-white/50">
        {links.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`transition-colors hover:text-cyan ${path.startsWith(l.href) ? "text-cyan" : ""}`}
          >
            {l.label}
          </Link>
        ))}
        <Link href="/auth" className="btn-primary text-xs py-2 px-4">
          Account
        </Link>
      </div>
    </nav>
  );
}

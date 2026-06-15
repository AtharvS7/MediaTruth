"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useRef } from "react";
import { supabase } from "@/lib/supabase";

export default function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Initial fetch
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUserEmail(session?.user?.email || null);
    });

    // Listen for auth events (login/logout)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserEmail(session?.user?.email || null);
    });

    // Handle click outside to close dropdown
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    
    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      subscription.unsubscribe();
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
    setDropdownOpen(false);
    router.push("/");
  }

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
        
        {userEmail ? (
          <div className="relative" ref={dropdownRef}>
            <button 
              onClick={() => setDropdownOpen(!dropdownOpen)} 
              className="btn-ghost text-xs py-2 px-4 hover:text-white transition-colors flex items-center gap-2"
            >
              Account <span className="text-[10px]">▼</span>
            </button>
            {dropdownOpen && (
              <div className="absolute right-0 mt-2 w-52 bg-[#12121a] border border-white/10 rounded-xl shadow-2xl overflow-hidden py-1">
                <div className="px-4 py-3 border-b border-white/10">
                  <p className="text-white/30 text-[10px] uppercase tracking-wider mb-1">Signed in as</p>
                  <p className="text-white text-xs truncate max-w-full block" title={userEmail}>{userEmail}</p>
                </div>
                <button 
                  onClick={handleSignOut}
                  className="w-full text-left px-4 py-3 text-coral hover:bg-white/5 transition-colors text-xs font-semibold"
                >
                  Log Out
                </button>
              </div>
            )}
          </div>
        ) : (
          <Link href="/auth" className="btn-primary text-xs py-2 px-4">
            Sign In
          </Link>
        )}
      </div>
    </nav>
  );
}

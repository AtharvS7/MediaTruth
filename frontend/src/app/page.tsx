"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Shield, Zap, Eye, Film, ArrowRight, GitBranch } from "lucide-react";

const FEATURES = [
  { icon: Eye,      label: "Deepfake Detection",        desc: "EfficientNet-B5 deepfake classifier with frame-level analysis" },
  { icon: Zap,      label: "GAN Fingerprinting",         desc: "CNNDetect identifies GAN-generated images (StyleGAN, BigGAN)" },
  { icon: Shield,   label: "Manipulation Localization",  desc: "ELA + DCT artifact maps pinpoint edited regions" },
  { icon: Film,     label: "Video Forensics",            desc: "Frame-by-frame analysis for videos up to 180 seconds" },
  { icon: GitBranch,"label": "Metadata Analysis",       desc: "EXIF anomaly detection flags AI generator software signatures" },
];

const STATS = [
  { value: "4+",    label: "Detection Models" },
  { value: "180s",  label: "Max Video Length" },
  { value: "<3s",   label: "Avg Analysis Time" },
  { value: "99.1%", label: "GAN Detection Accuracy" },
];

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-x-hidden">
      {/* Ambient orbs */}
      <div className="fixed top-[-20%] left-[10%] w-[600px] h-[600px] rounded-full bg-cyan/5 blur-[120px] pointer-events-none" />
      <div className="fixed bottom-[-10%] right-[5%] w-[400px] h-[400px] rounded-full bg-violet/5 blur-[100px] pointer-events-none" />

      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-5 border-b border-white/5 glass">
        <span className="font-display font-bold text-xl tracking-tight text-glow-cyan">
          MEDIA<span className="text-white">TRUTH</span>
        </span>
        <div className="flex items-center gap-6 text-sm font-mono text-white/50">
          <Link href="/upload" className="hover:text-cyan transition-colors">Analyze</Link>
          <Link href="/history" className="hover:text-cyan transition-colors">History</Link>
          <Link href="/auth" className="btn-primary text-sm py-2 px-4">
            Sign In
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative flex flex-col items-center justify-center min-h-screen pt-24 pb-16 px-6 text-center">
        {/* Scanning animation */}
        <motion.div
          className="absolute inset-0 pointer-events-none overflow-hidden"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          {[...Array(3)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-cyan/20 to-transparent"
              animate={{ top: ["0%", "100%"] }}
              transition={{
                duration: 4 + i * 1.5,
                repeat: Infinity,
                delay: i * 1.2,
                ease: "linear",
              }}
            />
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        >
          <p className="font-mono text-xs tracking-[0.3em] text-cyan/60 uppercase mb-6">
            AI Media Forensics Platform
          </p>

          <h1 className="font-display font-extrabold text-5xl md:text-7xl lg:text-8xl leading-[0.92] tracking-tight mb-6">
            <span className="text-white">IS YOUR MEDIA</span>
            <br />
            <span className="text-glow-cyan">TELLING THE TRUTH?</span>
          </h1>

          <p className="max-w-xl mx-auto text-white/50 font-body text-lg leading-relaxed mb-10">
            Upload any image or video. Our multi-model forensics engine detects
            deepfakes, GAN generation, and manipulation down to the pixel.
          </p>

          <div className="flex items-center justify-center gap-4">
            <Link href="/upload" className="btn-primary flex items-center gap-2 text-base py-3 px-8">
              Start Analysis <ArrowRight size={18} />
            </Link>
            <Link href="#how-it-works" className="btn-ghost text-base">
              How it works
            </Link>
          </div>
        </motion.div>

        {/* Stats bar */}
        <motion.div
          className="relative mt-24 grid grid-cols-2 md:grid-cols-4 gap-px bg-white/5 rounded-2xl overflow-hidden max-w-3xl w-full"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.6 }}
        >
          {STATS.map((s) => (
            <div key={s.label} className="bg-obsidian-800/80 px-6 py-5 text-center">
              <p className="font-display font-bold text-3xl text-glow-cyan">{s.value}</p>
              <p className="font-mono text-xs text-white/40 mt-1 uppercase tracking-widest">{s.label}</p>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Features grid */}
      <section id="how-it-works" className="relative px-6 pb-32 max-w-6xl mx-auto">
        <motion.p
          className="font-mono text-xs tracking-[0.3em] text-cyan/50 uppercase text-center mb-3"
          initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
        >
          Detection Pipeline
        </motion.p>
        <motion.h2
          className="font-display font-bold text-4xl md:text-5xl text-center mb-16"
          initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }}
        >
          Five layers of forensic analysis
        </motion.h2>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.label}
              className="glass-cyan rounded-2xl p-6 group hover:border-cyan/40 transition-all duration-300"
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
            >
              <div className="w-10 h-10 rounded-xl bg-cyan/10 flex items-center justify-center mb-4 group-hover:bg-cyan/20 transition-colors">
                <f.icon size={20} className="text-cyan" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">{f.label}</h3>
              <p className="font-body text-sm text-white/40 leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative px-6 pb-32 text-center">
        <div className="glass-cyan rounded-3xl max-w-2xl mx-auto p-12">
          <h2 className="font-display font-bold text-4xl mb-4">
            Don't trust. Verify.
          </h2>
          <p className="text-white/40 mb-8 font-body">
            In an era of generative AI, ground truth matters more than ever.
          </p>
          <Link href="/upload" className="btn-primary inline-flex items-center gap-2 text-base py-3 px-10">
            Analyze Media Now <ArrowRight size={18} />
          </Link>
        </div>
      </section>
    </main>
  );
}

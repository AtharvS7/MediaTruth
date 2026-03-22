"use client";

import { motion } from "framer-motion";

export default function Background3D() {
  return (
    <div className="fixed inset-0 z-[-1] pointer-events-none overflow-hidden mix-blend-screen opacity-70">
      {/* Ambient Orb 1 */}
      <motion.div
        className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full blur-[120px]"
        style={{ background: "radial-gradient(circle, rgba(0,245,255,0.15) 0%, rgba(0,0,0,0) 70%)" }}
        animate={{
          x: [0, 100, -50, 0],
          y: [0, 50, 100, 0],
          scale: [1, 1.1, 0.9, 1]
        }}
        transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
      />
      {/* Ambient Orb 2 */}
      <motion.div
        className="absolute bottom-[-20%] right-[-10%] w-[60vw] h-[60vw] rounded-full blur-[150px]"
        style={{ background: "radial-gradient(circle, rgba(139,92,246,0.15) 0%, rgba(0,0,0,0) 70%)" }}
        animate={{
          x: [0, -100, 50, 0],
          y: [0, -100, 50, 0],
          scale: [1, 1.2, 0.8, 1]
        }}
        transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
      />
    </div>
  );
}

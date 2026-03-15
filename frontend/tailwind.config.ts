import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        mono: ["var(--font-mono)", "monospace"],
        body: ["var(--font-body)", "sans-serif"],
      },
      colors: {
        obsidian: {
          950: "#030308",
          900: "#07070f",
          800: "#0d0d1a",
          700: "#131326",
        },
        cyan: {
          DEFAULT: "#00f5ff",
          dim: "#00c8d4",
          glow: "rgba(0,245,255,0.15)",
        },
        acid: {
          DEFAULT: "#b8ff57",
          dim: "#8ecc3a",
        },
        coral: {
          DEFAULT: "#ff4d6d",
          dim: "#cc3d57",
        },
        violet: {
          DEFAULT: "#8b5cf6",
          dim: "#6d44c4",
        },
      },
      backgroundImage: {
        "grid-fine": "linear-gradient(rgba(0,245,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,245,255,0.03) 1px, transparent 1px)",
        "radial-glow": "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,245,255,0.12), transparent)",
      },
      backgroundSize: {
        "grid-fine": "32px 32px",
      },
      boxShadow: {
        "glow-cyan": "0 0 20px rgba(0,245,255,0.3), 0 0 60px rgba(0,245,255,0.1)",
        "glow-acid": "0 0 20px rgba(184,255,87,0.3), 0 0 60px rgba(184,255,87,0.1)",
        "glow-coral": "0 0 20px rgba(255,77,109,0.3), 0 0 60px rgba(255,77,109,0.1)",
        "glass": "inset 0 1px 0 rgba(255,255,255,0.06), 0 1px 3px rgba(0,0,0,0.5)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "scan-line": "scanLine 2s linear infinite",
        "float": "float 6s ease-in-out infinite",
        "shimmer": "shimmer 2s linear infinite",
      },
      keyframes: {
        scanLine: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;

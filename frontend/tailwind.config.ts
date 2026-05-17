import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          950: "#03020a",
          900: "#0a0814",
          800: "#130f24",
          700: "#1e1535",
          600: "#2d2151",
          500: "#4c1d95",
          400: "#6d28d9",
          300: "#7c3aed",
          200: "#a855f7",
          100: "#d8b4fe",
          50: "#f5f3ff",
        },
      },
      backgroundImage: {
        "hero-glow":
          "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(124,58,237,0.18) 0%, transparent 70%)",
        "card-shine":
          "linear-gradient(135deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0) 60%)",
      },
      boxShadow: {
        "glow-purple": "0 0 40px rgba(124,58,237,0.25)",
        "glow-purple-sm": "0 0 20px rgba(124,58,237,0.15)",
        "glow-purple-lg": "0 0 80px rgba(124,58,237,0.3)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.4s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;

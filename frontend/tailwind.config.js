/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0a0f1c",
        panel: "#111a2e",
        panel2: "#16213a",
        line: "#1f2c47",
        pitch: { DEFAULT: "#10b981", dark: "#059669", glow: "#34d399" },
        accent: "#38bdf8",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

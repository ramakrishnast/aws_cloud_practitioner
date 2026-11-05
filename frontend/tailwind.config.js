/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: { 50: "#eef5fd", 100: "#cde2fb", 500: "#2a78d6", 600: "#256abf", 700: "#1c5cab", 900: "#0d366b" },
        ink: { 900: "#0b0b0b", 600: "#52514e" },
        good: "#0ca30c",
        critical: "#d03b3b",
        warn: "#fab219",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

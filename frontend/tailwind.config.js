/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#0B1220",
          900: "#0F1830",
          800: "#121A2B",
          700: "#1B2740",
          600: "#28375A",
        },
        accent: {
          teal: "#2DD4BF",
          amber: "#F59E0B",
          red: "#EF4444",
          blue: "#60A5FA",
        },
        ink: {
          100: "#E7ECF5",
          300: "#AEB9CF",
          500: "#7C88A3",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
}

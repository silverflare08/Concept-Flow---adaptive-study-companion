/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "rgb(var(--ink) / <alpha-value>)",
        lilac: "rgb(var(--lilac) / <alpha-value>)",
        lavender: "rgb(var(--lavender) / <alpha-value>)",
        mint: "rgb(var(--mint) / <alpha-value>)",
        peach: "rgb(var(--peach) / <alpha-value>)",
        sky: "rgb(var(--sky) / <alpha-value>)",
        plum: "rgb(var(--accent) / <alpha-value>)"
      },
      boxShadow: { soft: "0 12px 35px rgba(82, 69, 122, .10)" },
      fontFamily: {
        sans: ["Inter Variable", "ui-sans-serif", "system-ui", "sans-serif"],
        heading: ["Sora Variable", "Inter Variable", "ui-sans-serif", "system-ui", "sans-serif"],
        brand: ["Caveat Variable", "Segoe Print", "cursive"]
      }
    }
  },
  plugins: []
};

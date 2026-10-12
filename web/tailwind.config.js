/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#263746",
        lilac: "#EEE9FF",
        lavender: "#DCD4FF",
        mint: "#E2F4EC",
        peach: "#FFF0E7",
        sky: "#E6F2FF",
        plum: "#67578F"
      },
      boxShadow: { soft: "0 12px 35px rgba(82, 69, 122, .10)" },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] }
    }
  },
  plugins: []
};

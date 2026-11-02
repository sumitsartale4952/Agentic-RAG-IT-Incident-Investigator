/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--page)",
        surface: "var(--surface)",
        accent: "var(--accent)",
      },
    },
  },
  plugins: [],
};

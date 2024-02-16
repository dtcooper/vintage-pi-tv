/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: "Space Mono Local"
      },
    },
  },
  daisyui: {
    themes: ["cyberpunk"],
  },
  plugins: [require("daisyui")],
}

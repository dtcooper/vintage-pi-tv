import { addDynamicIconSelectors } from "@iconify/tailwind"
import daisyui from "daisyui"
import { cyberpunk } from "daisyui/src/theming/themes"

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{svelte,js}"],
  daisyui: {
    logs: false,
    themes: [
      {
        light: {
          ...cyberpunk,
          fontFamily: `Space Mono,Space Mono Local,${cyberpunk.fontFamily}`
        }
      }
    ]
  },
  plugins: [addDynamicIconSelectors(), daisyui]
}

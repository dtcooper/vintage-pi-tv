import { addDynamicIconSelectors } from "@iconify/tailwind"
import daisyui from "daisyui"
import { synthwave } from "daisyui/src/theming/themes"

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{svelte,js}"],
  daisyui: {
    logs: false,
    themes: [
      {
        light: {
          ...synthwave,
          fontFamily: `Space Mono,Space Mono Local,${synthwave.fontFamily}`
        }
      }
    ]
  },
  plugins: [addDynamicIconSelectors(), daisyui]
}

import { cyberpunk } from "daisyui/src/theming/themes";
import daisyui from "daisyui"


/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{svelte,js}",
  ],
  daisyui: {
    logs: false,
    themes: [
      {
        light: {
          ...cyberpunk,
          fontFamily: `Space Mono,Space Mono Local,${cyberpunk.fontFamily}`
        },
      },
    ],
  },
  plugins: [daisyui],
}

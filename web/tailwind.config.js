import { addDynamicIconSelectors } from "@iconify/tailwind"
import daisyui from "daisyui"
import { emerald as emeraldTheme, night as nightTheme } from "daisyui/src/theming/themes"

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{svelte,js}"],
  extend: {
    keyframes: {
      blink: {
        "0%, 100%": { visibility: "none" },
        "50%": { visibility: "#hidden" }
      }
    },
    animation: {
      blink: "blink 2s ease-in-out infinite"
    }
  },
  daisyui: {
    logs: false,
    darkTheme: "night",
    themes: [
      {
        emerald: {
          ...emeraldTheme,
          fontFamily: `Space Mono,Space Mono Local,${emeraldTheme.fontFamily}`
        },
        night: {
          ...nightTheme,
          fontFamily: `Space Mono,Space Mono Local,${nightTheme.fontFamily}`
        }
      }
    ]
  },
  plugins: [addDynamicIconSelectors(), daisyui]
}

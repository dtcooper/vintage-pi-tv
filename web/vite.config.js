import { svelte } from "@sveltejs/vite-plugin-svelte"
import { execSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { defineConfig } from "vite"

let version = "unknown"
const codeDir = path.resolve(path.join(__dirname, ".."))
const versionFile = path.join(codeDir, "version.txt")
const gitDir = path.join(codeDir, ".git")
if (fs.existsSync(versionFile)) {
  version = fs.readFileSync(versionFile, "utf-8").trim()
} else if (fs.existsSync(gitDir)) {
  try {
    version = execSync(`git --git-dir=${gitDir} rev-parse HEAD`, { encoding: "utf-8" }).trim().substring(0, 8)
  } catch {}
}

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    fs: {
      allow: [".."]
    }
  },
  define: {
    __VERSION__: JSON.stringify(version)
  },
  plugins: [svelte()]
})

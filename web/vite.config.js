import { svelte } from "@sveltejs/vite-plugin-svelte"
import { execSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"
import { env } from "node:process"
import { defineConfig } from "vite"

let version = "unknown"

if (env.VINTAGE_PI_TV_VERSION) {
  version = env.VINTAGE_PI_TV_VERSION.trim()
} else {
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
}

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

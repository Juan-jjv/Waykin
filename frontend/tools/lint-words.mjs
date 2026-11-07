#!/usr/bin/env node
// Banned-word lint (spec A1.8). Only READS files. Exit 1 if any banned word appears.
// Usage: node tools/lint-words.mjs [extra paths...]   (defaults to frontend/src and backend/waykin)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const BANNED = /\b(safe|safer|safest|safety|unsafe|danger|dangerous)\b/i; // lint-words: ignore
const EXT = new Set([".ts", ".tsx", ".css", ".html", ".py"]);
const SKIP_DIRS = new Set(["node_modules", "__pycache__", "dist", ".pytest_cache"]);

function* walk(p) {
  const st = statSync(p, { throwIfNoEntry: false });
  if (!st) return;
  if (st.isFile()) {
    if (EXT.has(extname(p)) && !p.endsWith("types.gen.ts")) yield p;
    return;
  }
  for (const name of readdirSync(p)) if (!SKIP_DIRS.has(name)) yield* walk(join(p, name));
}

const roots = process.argv.length > 2 ? process.argv.slice(2) : [join(repo, "frontend", "src"), join(repo, "backend", "waykin")];
let hits = 0;
for (const root of roots) {
  for (const file of walk(resolve(root))) {
    readFileSync(file, "utf8").split("\n").forEach((line, i) => {
      if (line.includes("lint-words: ignore")) return;
      const m = line.match(BANNED);
      if (m) {
        hits++;
        console.log(`${file}:${i + 1}: ${m[0]}`);
      }
    });
  }
}
if (hits) {
  console.log(`\n${hits} banned word(s). Use "lower-exposure", "fewer reported incidents" or "closure".`);
  process.exit(1);
}
console.log("lint:words ok");

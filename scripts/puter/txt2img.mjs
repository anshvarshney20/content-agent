/**
 * Puter.txt2img bridge for the Python agent.
 *
 * Usage:
 *   PUTER_AUTH_TOKEN=... node txt2img.mjs --prompt "..." --model openai/gpt-image-2 --out out.png
 *
 * Prints JSON: {"ok":true,"path":"..."} or {"ok":false,"error":"..."}
 */
import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const out = { prompt: "", model: "openai/gpt-image-2", quality: "low", out: "" };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--prompt") out.prompt = argv[++i] || "";
    else if (a === "--model") out.model = argv[++i] || out.model;
    else if (a === "--quality") out.quality = argv[++i] || out.quality;
    else if (a === "--out") out.out = argv[++i] || "";
  }
  return out;
}

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function polyfillImage() {
  if (typeof globalThis.Image === "undefined") {
    globalThis.Image = class Image {
      constructor() {
        this.src = "";
        this.onload = null;
        this.onerror = null;
      }
      setAttribute() {}
    };
  }
}

async function decodeToBuffer(result) {
  const src =
    (result && typeof result === "object" && (result.src || result.href)) ||
    (typeof result === "string" ? result : null);

  if (!src) {
    throw new Error(`Unexpected Puter txt2img result: ${typeof result}`);
  }

  if (typeof src === "string" && src.startsWith("data:")) {
    const comma = src.indexOf(",");
    const b64 = comma >= 0 ? src.slice(comma + 1) : src;
    return Buffer.from(b64, "base64");
  }

  if (typeof src === "string" && (src.startsWith("http://") || src.startsWith("https://"))) {
    const res = await fetch(src);
    if (!res.ok) throw new Error(`Failed to download Puter image (${res.status})`);
    return Buffer.from(await res.arrayBuffer());
  }

  throw new Error(`Unsupported image src scheme: ${String(src).slice(0, 80)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.prompt || !args.out) {
    emit({ ok: false, error: "Required: --prompt and --out" });
    process.exit(2);
  }

  const token = (process.env.PUTER_AUTH_TOKEN || "").trim();
  if (!token) {
    emit({
      ok: false,
      error:
        "PUTER_AUTH_TOKEN is missing. In Node, run getAuthToken once or paste a Puter auth token into IMAGE__API_KEY.",
    });
    process.exit(2);
  }

  polyfillImage();

  let init;
  try {
    ({ init } = require("@heyputer/puter.js/src/init.cjs"));
  } catch (err) {
    emit({
      ok: false,
      error:
        "Puter.js not installed. Run: npm install --prefix scripts/puter",
    });
    process.exit(2);
  }

  try {
    const puter = init(token);
    const options = { model: args.model };
    if (args.quality) options.quality = args.quality;

    const result = await puter.ai.txt2img(args.prompt, options);
    const buf = await decodeToBuffer(result);
    writeFileSync(args.out, buf);
    emit({ ok: true, path: args.out, bytes: buf.length, model: args.model });
  } catch (err) {
    emit({ ok: false, error: err?.message || String(err) });
    process.exit(1);
  }
}

main();

import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile, writeFile, mkdir, copyFile, readdir } from "node:fs/promises";

const root = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(root, "../../frontend/pdfme-bundle");
const clawpdfDist = resolve(root, "node_modules/clawpdf/dist");
const clawpdfBrowser = resolve(clawpdfDist, "browser.js");

await mkdir(resolve(outDir, "vendor"), { recursive: true });

await build({
  entryPoints: ["entry.js"],
  outfile: resolve(outDir, "designer.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2022"],
  minify: true,
  sourcemap: false,
  legalComments: "none",
  external: ["node:zlib", "node:url", "node:module"],
  plugins: [{
    name: "clawpdf-browser",
    setup(build) {
      build.onResolve({ filter: /^clawpdf$/ }, () => ({ path: clawpdfBrowser }));
    },
  }],
  loader: {
    ".wasm": "file",
  },
});

const bundlePath = resolve(outDir, "designer.js");
let bundle = await readFile(bundlePath, "utf8");
bundle = bundle
  .replaceAll('"node:zlib"', '"./node-zlib.js"')
  .replaceAll('"node:url"', '"./node-url.js"')
  .replaceAll('"node:module"', '"./node-module.js"');
await writeFile(bundlePath, bundle);

await copyFile(resolve(root, "shims/node-zlib.js"), resolve(outDir, "node-zlib.js"));
await copyFile(resolve(root, "shims/node-url.js"), resolve(outDir, "node-url.js"));
await copyFile(resolve(root, "shims/node-module.js"), resolve(outDir, "node-module.js"));

await copyFile(
  resolve(clawpdfDist, "vendor/pdfium.esm.wasm"),
  resolve(outDir, "vendor/pdfium.esm.wasm"),
);

// PDFMe/clawpdf uses a hashed worker JavaScript asset at runtime.
// Package layouts can differ between clawpdf releases, so locate the worker
// recursively instead of assuming one fixed dist/assets directory.
async function findWorker(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = resolve(dir, entry.name);
    if (entry.isFile() && /^clawpdf-worker-.*\\.js$/.test(entry.name)) return fullPath;
    if (entry.isDirectory()) {
      const found = await findWorker(fullPath);
      if (found) return found;
    }
  }
  return null;
}

const workerPath = await findWorker(clawpdfDist);
if (!workerPath) {
  throw new Error("clawpdf render worker asset was not found anywhere in node_modules/clawpdf");
}
const workerName = workerPath.split("/").pop();
await mkdir(resolve(outDir, "assets"), { recursive: true });
await copyFile(workerPath, resolve(outDir, "assets", workerName));

console.log("PDFMe production bundle created with render worker:", workerName);

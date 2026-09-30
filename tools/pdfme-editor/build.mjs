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
// Keep that asset beside the generated bundle so import.meta.url resolves locally.
const assetDir = resolve(clawpdfDist, "assets");
const assetNames = await readdir(assetDir);
const workerName = assetNames.find((name) => /^clawpdf-worker-.*\.js$/.test(name));
if (!workerName) {
  throw new Error("clawpdf render worker asset was not found in dist/assets");
}
await mkdir(resolve(outDir, "assets"), { recursive: true });
await copyFile(resolve(assetDir, workerName), resolve(outDir, "assets", workerName));

console.log("PDFMe production bundle created with render worker:", workerName);

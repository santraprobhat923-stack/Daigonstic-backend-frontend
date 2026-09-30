import { build } from "esbuild";

await build({
  entryPoints: ["entry.js"],
  outfile: "../../frontend/pdfme-bundle/designer.js",
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2022"],
  minify: true,
  sourcemap: false,
  legalComments: "none",
  alias: {
    clawpdf: "clawpdf/browser",
  },
  loader: {
    ".wasm": "file",
  },
});

console.log("PDFMe production bundle created.");

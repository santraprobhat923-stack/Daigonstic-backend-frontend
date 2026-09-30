import { build } from "esbuild";

await build({
  entryPoints: ["entry.js"],
  outfile: "../../frontend/pdfme-bundle/designer.js",
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2020"],
  minify: true,
  sourcemap: false,
  legalComments: "none",
});

console.log("PDFMe production bundle created.");

import { build } from "esbuild";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const clawpdfBrowser = resolve(root, "node_modules/clawpdf/dist/browser.js");
const shims = {
  "node:zlib": resolve(root, "shims/node-zlib.js"),
  "node:url": resolve(root, "shims/node-url.js"),
  "node:module": resolve(root, "shims/node-module.js"),
};

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
  plugins: [{
    name: "browser-node-shims",
    setup(build) {
      build.onResolve({ filter: /^clawpdf$/ }, () => ({ path: clawpdfBrowser }));
      build.onResolve({ filter: /^node:(zlib|url|module)$/ }, ({ path }) => ({ path: shims[path] }));
    },
  }],
  loader: {
    ".wasm": "file",
  },
});

console.log("PDFMe production bundle created.");

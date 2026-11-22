// Decode PNG QR codes with jsQR (the pure-JS decoder used in the browser) under Node.
// Run:  NODE_PATH=<dir with jsqr+pngjs node_modules> node tools_tests/jsqr_decode.js <png files...>
const fs = require("fs");
const jsQR = require("jsqr");
const { PNG } = require("pngjs");

for (const f of process.argv.slice(2)) {
  const png = PNG.sync.read(fs.readFileSync(f));
  const t0 = process.hrtime.bigint();
  const code = jsQR(new Uint8ClampedArray(png.data), png.width, png.height);
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  console.log(`${f.split("/").pop()}: ${png.width}x${png.height}, decoded=${!!code}, ` +
              `chars=${code ? code.data.length : 0}, ${ms.toFixed(1)} ms`);
}

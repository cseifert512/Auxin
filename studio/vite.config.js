// The studio draws with the plant viewer's own code and its copy of three.js,
// read in place from the Horti-code-ture checkout beside this repository (or at
// HORTI_DIR). One copy of three.js for both: the plants' shaders are spliced
// into that release's materials, and two copies would not share a renderer.
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '..');
const slashed = (p) => p.replaceAll('\\', '/');
const horti = slashed(resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture')));
const three = `${horti}/node_modules/three`;

export default {
  root: here,
  // a film is made from a second server, which keeps its own cache
  cacheDir: resolve(here, process.env.STUDIO_CACHE ?? '.vite'),
  resolve: {
    alias: [
      { find: /^three\/addons\/(.*)$/, replacement: `${three}/examples/jsm/$1` },
      { find: /^three$/, replacement: `${three}/build/three.module.js` },
      { find: /^@horti\/viewer\/(.*)$/, replacement: `${horti}/packages/viewer/src/$1` },
      { find: /^@horti\/core$/, replacement: `${horti}/packages/core/src/index.ts` },
    ],
  },
  // the folder that holds this repository and the checkouts it reads
  server: { port: 5310, strictPort: true, fs: { allow: [resolve(root, '..')] } },
  build: { target: 'es2023', outDir: resolve(root, 'dist'), emptyOutDir: true, chunkSizeWarningLimit: 4000 },
};

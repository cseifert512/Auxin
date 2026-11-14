// The studio draws with the plant viewer's own code and its copy of three.js,
// read in place from the Horti-code-ture folder beside this one (or at
// HORTI_DIR). One copy of three.js for both: the plants' shaders are spliced
// into that release's materials, and two copies would not share a renderer.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const root = resolve(here, '..');
const slashed = (p) => p.replaceAll('\\', '/');
const horti = slashed(resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture')));
const three = `${horti}/node_modules/three`;
// which building is drawn: the snapshot named in snapshot.json (or BOWER_SNAPSHOT), read from ../releases
const snapshot = process.env.BOWER_SNAPSHOT ?? JSON.parse(readFileSync(resolve(root, 'snapshot.json'), 'utf8')).snapshot;

export default {
  root: here,
  // a film is made from a second server, which keeps its own cache
  cacheDir: resolve(here, process.env.STUDIO_CACHE ?? '.vite'),
  resolve: {
    alias: [
      { find: /^three\/addons\/(.*)$/, replacement: `${three}/examples/jsm/$1` },
      { find: /^three$/, replacement: `${three}/build/three.module.js` },
      { find: /^@snapshot\/(.*)$/, replacement: `${slashed(resolve(root, '..'))}/releases/${snapshot}/$1` },
      { find: /^@scene\/(.*)$/, replacement: `${slashed(root)}/scenes/${snapshot}/$1` },
      { find: /^@horti\/viewer\/(.*)$/, replacement: `${horti}/packages/viewer/src/$1` },
      { find: /^@horti\/core$/, replacement: `${horti}/packages/core/src/index.ts` },
    ],
  },
  // the repository (snapshots, plant simulator) and the website's fonts, which are beside the repository
  server: { port: 5310, strictPort: true, fs: { allow: [resolve(root, '..'), resolve(root, '../../Bower_Web')] } },
  build: { target: 'es2023', outDir: resolve(root, 'dist'), emptyOutDir: true, chunkSizeWarningLimit: 4000 },
};

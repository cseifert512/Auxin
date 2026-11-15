// Bundles only this experiment. Source scene modules remain unchanged.
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const here = dirname(fileURLToPath(import.meta.url)), repo = resolve(here, '../../../../..');
const require = createRequire(import.meta.url);
const { build } = require(process.env.ESBUILD_MODULE || 'C:/BOWER/Bower_Web/node_modules/esbuild');
const three = resolve(repo, 'Horti-code-ture/node_modules/three');
const result = await build({
  entryPoints: [resolve(here, 'renderer.js')], outfile: resolve(here, 'renderer.bundle.js'),
  bundle: true, format: 'esm', platform: 'browser', target: 'es2022', minify: true,
  legalComments: 'inline', metafile: true,
  plugins: [{ name: 'one-scene-three', setup(builder) {
    builder.onResolve({ filter: /^three$/ }, () => ({ path: resolve(three, 'build/three.module.js') }));
    builder.onResolve({ filter: /^three\/addons\/controls\/OrbitControls\.js$/ }, () => ({ path: resolve(here, 'fixed-controls.js') }));
    builder.onResolve({ filter: /^three\/addons\// }, args => ({ path: resolve(three, 'examples/jsm', args.path.slice('three/addons/'.length)) }));
  } }],
});
const output = Object.values(result.metafile.outputs).find(file => file.entryPoint);
console.log(`Isolated renderer: ${output.bytes.toLocaleString('en-GB')} bytes. Source scene modules unchanged.`);

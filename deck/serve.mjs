// Serves this folder so the deck opens at the same addresses it has on the website.
//   node deck/serve.mjs [port]        then http://localhost:5312/designx/v8
//
// Nothing is built and nothing is installed: the deck is plain files. A server is used instead of opening the
// file because the customer film is sought through, which needs byte ranges, and because each edition expects
// to live at /designx/<edition> with no file name.
//   /                         goes to the newest edition
//   /designx/<edition>        that edition's index.html
//   /designx/<edition>/pdf    the PDF in that edition's downloads folder, shown in the browser
//   /designx/pieces/<name>/   the dynamic drawings, straight from ../drawings-in-code/exports/deck/ where they are
//                             made, so the deck always shows the latest (a copy in designx/pieces/ is used if there)
// Nothing is cached, so an edit shows on the next reload.
import { createReadStream, existsSync, readdirSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.argv[2] ?? process.env.PORT ?? 5312);
const newest = '/designx';
const made = resolve(root, '../drawings-in-code/exports/deck');

const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.woff2': 'font/woff2',
  '.pdf': 'application/pdf',
  '.md': 'text/plain; charset=utf-8',
};

// the file an address stands for, or null
function find(path) {
  const file = resolve(root, normalize(`.${path}`));
  if (file !== resolve(root) && !file.startsWith(resolve(root) + sep)) return null;
  if (!existsSync(file) && path.startsWith('/designx/pieces/')) {
    const piece = resolve(made, normalize(`./${path.slice('/designx/pieces/'.length)}`));
    if (!piece.startsWith(made + sep) || !existsSync(piece)) return null;
    if (statSync(piece).isFile()) return piece;
    return existsSync(join(piece, 'index.html')) ? join(piece, 'index.html') : null;
  }
  if (existsSync(file)) {
    if (statSync(file).isFile()) return file;
    const index = join(file, 'index.html');
    return existsSync(index) ? index : null;
  }
  if (path.endsWith('/pdf')) {
    const downloads = resolve(file, '..', 'downloads');
    const pdf = existsSync(downloads) && readdirSync(downloads).find((f) => f.endsWith('.pdf'));
    return pdf ? join(downloads, pdf) : null;
  }
  return null;
}

createServer((request, response) => {
  const path = decodeURIComponent(new URL(request.url, 'http://deck').pathname).replace(/\/+$/, '') || '/';
  if (path === '/') {
    response.writeHead(302, { Location: newest }).end();
    return;
  }
  const file = find(path);
  if (!file) {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end(`Nothing at ${path}`);
    console.log(`404 ${path}`);
    return;
  }
  const size = statSync(file).size;
  const head = {
    'Content-Type': types[extname(file).toLowerCase()] ?? 'application/octet-stream',
    'Cache-Control': 'no-store',
    'Accept-Ranges': 'bytes',
  };
  const range = /^bytes=(\d*)-(\d*)$/.exec(request.headers.range ?? '');
  if (range && (range[1] || range[2])) {
    const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]));
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1;
    if (start > end || start >= size) {
      response.writeHead(416, { 'Content-Range': `bytes */${size}` }).end();
      return;
    }
    response.writeHead(206, { ...head, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
    if (request.method === 'HEAD') response.end();
    else createReadStream(file, { start, end }).pipe(response);
    return;
  }
  response.writeHead(200, { ...head, 'Content-Length': size });
  if (request.method === 'HEAD') response.end();
  else createReadStream(file).pipe(response);
}).listen(port, () => console.log(`The deck is at http://localhost:${port}${newest}`));

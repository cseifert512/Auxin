// The studio in a browser nobody is looking at: started, opened, asked for pictures, and shut again.
// No dependencies: Node's own fetch and WebSocket, talking to Chrome or Edge over the DevTools protocol.
import { spawn } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const BROWSERS = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
];

/** Start the studio on a port of its own and a browser to look at it with. Returns how to open pages, and how to stop. */
export async function startStudio(port = 5318) {
  const exe = process.env.BROWSER_EXE ?? BROWSERS.find((p) => existsSync(p));
  if (!exe) throw new Error('no Chrome or Edge found: set BROWSER_EXE to a Chromium browser');
  const horti = resolve(process.env.HORTI_DIR ?? resolve(root, '../Horti-code-ture'));
  const server = spawn(process.execPath, [resolve(horti, 'node_modules/vite/bin/vite.js'), '--config', resolve(root, 'studio/vite.config.js'), '--port', String(port), '--strictPort'], {
    cwd: root,
    stdio: 'ignore',
    env: { ...process.env, STUDIO_CACHE: '.vite-film' },
  });
  const profile = mkdtempSync(join(tmpdir(), 'bower-studio-'));
  const debugPort = 9400 + Math.floor(Math.random() * 300);
  let browser = null;
  const stop = () => {
    browser?.kill();
    server.kill();
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      // the browser may still hold its profile for a moment: it is in the temporary folder either way
    }
  };
  process.on('exit', stop);
  process.on('SIGINT', () => process.exit(130));

  for (let i = 0; ; i++) {
    try {
      if ((await fetch(`http://localhost:${port}/`)).ok) break;
    } catch {
      if (i > 120) throw new Error('the studio did not start');
    }
    await sleep(250);
  }
  browser = spawn(
    exe,
    ['--headless=new', `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--hide-scrollbars', '--ignore-gpu-blocklist', '--enable-gpu', '--use-angle=d3d11', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows', 'about:blank'],
    { stdio: 'ignore' },
  );

  /** A page of the studio with the query given, sized as asked, and waited for until it has read its planting. */
  async function open(query, { width, height, scale = 2 }) {
    let target;
    for (let i = 0; i < 80 && !target; i++) {
      try {
        target = await (await fetch(`http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent('about:blank')}`, { method: 'PUT' })).json();
      } catch {
        await sleep(250);
      }
    }
    if (!target) throw new Error('the browser did not start');
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((r) => (ws.onopen = r));
    const pending = new Map();
    const problems = [];
    let nextId = 1;
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id && pending.has(m.id)) {
        const { ok, fail } = pending.get(m.id);
        pending.delete(m.id);
        if (m.error) fail(new Error(JSON.stringify(m.error)));
        else ok(m.result);
      } else if (m.method === 'Runtime.exceptionThrown') problems.push(m.params.exceptionDetails.exception?.description ?? m.params.exceptionDetails.text);
    };
    const send = (method, params = {}) =>
      new Promise((ok, fail) => {
        const id = nextId++;
        pending.set(id, { ok, fail });
        ws.send(JSON.stringify({ id, method, params }));
      });
    const js = async (expression) => {
      const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
      if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
      return r.result.value;
    };
    const size = (w, h, s = scale) => send('Emulation.setDeviceMetricsOverride', { width: Math.round(w), height: Math.round(h), deviceScaleFactor: s, mobile: false });
    await send('Runtime.enable');
    await send('Page.enable');
    await size(width, height);
    await send('Page.navigate', { url: `http://localhost:${port}/?${new URLSearchParams(query)}` });
    let ready = false;
    for (let i = 0; i < 1200 && !ready; i++) {
      await sleep(500);
      ready = await js('typeof window.studio === "object"').catch(() => false);
      if (problems.length) throw new Error(`the studio failed to open:\n  ${problems.join('\n  ')}`);
    }
    if (!ready) throw new Error('the studio did not open in ten minutes');
    return {
      js,
      size,
      problems,
      /** The page as it now is, as PNG bytes. */
      async shot(format = 'png') {
        const r = await send('Page.captureScreenshot', format === 'png' ? { format } : { format, quality: 95 });
        return Buffer.from(r.data, 'base64');
      },
      close: () => ws.close(),
    };
  }
  return { open, stop };
}

/* Edition 08: one selected view of the existing raster growth study.
   The architecture and plants are pre-rendered, never live browser geometry.
   Occupation is a separate, authored diagram. It is not a behaviour simulation. */
(() => {
  'use strict';
  const SOURCE = 'pieces/04-plants-make-space-timber/';
  const HOLD = .08;
  const CACHE_LIMIT = 6;
  const TIME_VIEWS = ['Above', 'Approach', 'Inside'];
  const LIGHT_VIEWS = ['Installation', 'Establishing', 'Established'];
  const CHAPTERS = {
    time: [['Design', 0], ['Installation', 16], ['Summer', 26], ['Winter', 30]],
    space: [['Installation', 0], ['Established', 7]],
    light: [['Morning', 9], ['Noon', 18], ['Afternoon', 27]]
  };
  const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
  const fraction = value => ((value % 1) + 1) % 1;

  function mount(host) {
    const root = document.createElement('div');
    root.className = 'v8-study v8-study-growth v8-growth-player';
    root.innerHTML = `<div class="v8-growth-topline">
      <nav class="v8-growth-views" aria-label="Choose a view of the room"></nav>
      <button type="button" class="v8-growth-occupation" data-v8-occupation aria-pressed="true">Inhabitants <span>on</span></button>
    </div>
    <div class="v8-study-screen v8-growth-screen">
      <canvas class="v8-growth-canvas" role="img" aria-label="Growth drawing" tabindex="0"></canvas>
      <div class="v8-growth-message" role="status"><span>Open this slide to explore the drawing.</span><button type="button" data-v8-retry hidden>Retry drawing</button></div>
      <span class="v8-growth-view-label"></span>
    </div>
    <nav class="v8-study-chapters" aria-label="Choose a moment in the drawing"></nav>
    <div class="v8-study-timeline">
      <button type="button" data-v8-study-play disabled>Play</button>
      <button type="button" data-v8-study-reset disabled>Reset</button>
      <input type="range" min="0" max="1000" step="1" value="0" aria-label="Position in growth scenario" disabled>
      <output class="v8-study-caption" aria-live="off"></output>
    </div>
    <div class="v8-growth-evidence"><span data-v8-growth-disclosure>Pre-rendered growth scenario · authored occupation</span>
      <details><summary>About this drawing</summary><div class="v8-growth-details">
        <strong>Scenario and drawing</strong><p>Existing six-bay timber and planting study. The browser selects and blends pre-rendered images. Growth and light depend on provisional assumptions; they are not measured performance or a forecast.</p>
        <strong>Authored occupation</strong><p>Faint people and birds suggest movement and scale. Their paths are diagrammatic, without collision, behaviour or habitat modelling. They pause and scrub with the drawing. No furniture is proposed.</p>
        <strong>Views</strong><p>Time offers Above, Approach and Inside views of one moment. Light shows a midsummer day in plan, with a choice of growth stage. Space is a pre-rendered panorama that can be dragged to turn.</p>
      </div></details>
    </div>`;
    host.append(root);
    const $ = selector => root.querySelector(selector);
    const canvas = $('canvas'), ctx = canvas.getContext('2d');
    const mixCanvas = document.createElement('canvas'), mix = mixCanvas.getContext('2d');
    const screen = $('.v8-growth-screen'), message = $('.v8-growth-message');
    const messageText = message.querySelector('span'), retryButton = $('[data-v8-retry]');
    const playButton = $('[data-v8-study-play]'), resetButton = $('[data-v8-study-reset]');
    const range = $('input'), output = $('output'), views = $('.v8-growth-views');
    const chapterHost = $('.v8-study-chapters'), viewLabel = $('.v8-growth-view-label');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    const state = { kind: 'growth', active: false, ready: false, mode: 'time', view: 2,
      time: 16 / 33 * (1 - HOLD) * 40, duration: 40, playing: false,
      occupation: true, pan: 0, caption: '', requestedCaption: '', error: null, fallback: false };
    const savedModes = new Map(), cache = new Map(), pending = new Map();
    let manifest = null, manifestRequest = null, destroyed = false, raf = 0, last = 0;
    let renderRequest = '', displayed = null, fallback = null, held = null, serial = 0;
    const sourceURL = file => new URL(SOURCE + file, document.baseURI).href;
    const usable = () => state.active && !document.hidden && !destroyed;
    const currentMode = () => manifest?.modes.find(mode => mode.id === state.mode);
    const viewName = () => state.mode === 'space' ? 'Inside panorama' : (state.mode === 'time' ? TIME_VIEWS : LIGHT_VIEWS)[state.view];

    function controls() {
      root.dataset.mode = state.mode;
      root.dataset.ready = String(state.ready);
      root.dataset.view = String(state.view);
      root.dataset.playing = String(state.playing);
      playButton.textContent = state.playing ? 'Pause' : 'Play';
      playButton.setAttribute('aria-label', state.playing ? 'Pause drawing' : 'Play drawing');
      // Reduced motion starts and stays paused automatically, but explicit Play is allowed.
      playButton.disabled = !manifest || !!state.error;
      resetButton.disabled = range.disabled = !manifest;
      range.value = String(Math.round(1000 * state.time / state.duration));
      range.setAttribute('aria-valuetext', state.ready ? state.caption : `Requested ${state.requestedCaption || 'moment'}. ${state.caption ? `Shown: ${state.caption}.` : 'Loading drawing.'}`);
      output.textContent = state.caption || (state.error ? 'Drawing unavailable' : 'Loading drawing');
      output.title = output.textContent;
      views.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.v8View) === state.view)));
      const mode = currentMode();
      chapterHost.querySelectorAll('button').forEach(button => {
        button.disabled = !mode;
        button.setAttribute('aria-pressed', String(Math.abs(state.time - Number(button.dataset.time)) < .025));
      });
      $('[data-v8-occupation]').setAttribute('aria-pressed', String(state.occupation));
      $('[data-v8-occupation] span').textContent = state.occupation ? 'on' : 'off';
      $('[data-v8-growth-disclosure]').textContent = state.occupation
        ? 'Pre-rendered growth scenario · authored occupation' : 'Pre-rendered growth scenario · occupation hidden';
      canvas.style.cursor = state.mode === 'space' ? (held ? 'grabbing' : 'grab') : 'default';
    }

    function showMessage(text, error = false) {
      message.hidden = !text;
      messageText.textContent = text;
      retryButton.hidden = !error;
      message.classList.toggle('is-error', error);
    }

    function makeSelectors() {
      const labels = state.mode === 'time' ? TIME_VIEWS : state.mode === 'light' ? LIGHT_VIEWS : [];
      views.setAttribute('aria-label', state.mode === 'light' ? 'Choose the planting stage in the light study' : 'Choose a view of the room');
      views.replaceChildren();
      const label = document.createElement('span');
      label.className = 'v8-growth-selector-label';
      label.textContent = state.mode === 'light' ? 'Growth stage' : state.mode === 'space' ? 'Panorama · drag to turn' : 'View';
      views.append(label);
      labels.forEach((text, index) => {
        const button = document.createElement('button'); button.type = 'button';
        button.textContent = text; button.dataset.v8View = String(index);
        button.addEventListener('click', () => setView(index)); views.append(button);
      });
      const mode = currentMode();
      chapterHost.replaceChildren(...CHAPTERS[state.mode].map(([text, index]) => {
        const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
        const time = mode ? index / (mode.frames.length - 1) * (1 - HOLD) * mode.seconds : 0;
        button.dataset.time = String(time); button.dataset.v8StudyChapter = String(index);
        button.addEventListener('click', () => seek(time)); return button;
      }));
      controls();
    }

    async function fetchTimed(url, controller) {
      let timedOut = false;
      const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 12000);
      try {
        const response = await fetch(url, { signal: controller.signal });
        if (!response.ok) throw new Error(`Drawing asset returned ${response.status}`);
        const blob = await response.blob();
        if (timedOut) throw new Error('Drawing load timed out');
        return blob;
      } catch (error) {
        if (timedOut) throw new Error('Drawing load timed out');
        throw error;
      } finally { clearTimeout(timer); }
    }

    function touchCache(key) {
      const item = cache.get(key);
      if (item) { cache.delete(key); cache.set(key, item); }
      return item;
    }

    function trimCache() {
      for (const [key, bitmap] of cache) {
        if (cache.size <= CACHE_LIMIT) break;
        if (displayed?.keys.includes(key) || bitmap === fallback) continue;
        cache.delete(key); bitmap.close?.();
      }
    }

    function imageFor(key) {
      if (cache.has(key)) return Promise.resolve(touchCache(key));
      if (pending.has(key)) return pending.get(key).promise;
      const controller = new AbortController();
      const request = { controller, promise: null };
      request.promise = fetchTimed(sourceURL(key), controller)
        .then(blob => createImageBitmap(blob))
        .then(bitmap => {
          if (controller.signal.aborted || !usable()) { bitmap.close(); throw new DOMException('Inactive drawing', 'AbortError'); }
          cache.set(key, bitmap); return bitmap;
        })
        .finally(() => { if (pending.get(key) === request) pending.delete(key); });
      pending.set(key, request);
      return request.promise;
    }

    function selection() {
      const mode = currentMode();
      if (!mode) return null;
      const along = Math.min(1, state.time / mode.seconds / (1 - HOLD)) * (mode.frames.length - 1);
      const first = Math.min(mode.frames.length - 1, Math.floor(along + 1e-9));
      const second = Math.min(mode.frames.length - 1, first + 1);
      const amount = along - first, eased = amount * amount * (3 - 2 * amount);
      return { mode, first, second, amount: eased,
        keys: [mode.frames[first].src, mode.frames[second].src],
        caption: mode.frames[amount > .5 ? second : first].stage };
    }

    // Human figures are deliberately spare silhouettes, in image coordinates.
    // They are placed behind the timber/plant layer so the actual drawing occludes them.
    function person(context, x, y, height, phase, opacity = .38, plan = false) {
      context.save(); context.translate(x, y); context.scale(height, height);
      context.fillStyle = '#536f65'; context.strokeStyle = '#536f65'; context.globalAlpha = opacity;
      context.lineCap = 'round'; context.lineJoin = 'round';
      if (plan) {
        context.rotate(phase);
        context.beginPath(); context.ellipse(0, 0, .17, .26, 0, 0, Math.PI * 2); context.fill();
        context.beginPath(); context.arc(0, -.12, .12, 0, Math.PI * 2); context.fill();
      } else {
        const gait = Math.sin(phase) * .09;
        context.beginPath(); context.arc(0, -.88, .085, 0, Math.PI * 2); context.fill();
        context.beginPath(); context.moveTo(-.1, -.76); context.quadraticCurveTo(0, -.82, .1, -.76);
        context.lineTo(.075, -.39); context.lineTo(-.075, -.39); context.closePath(); context.fill();
        context.lineWidth = .062;
        context.beginPath(); context.moveTo(-.08, -.72); context.lineTo(-.15 - gait, -.43);
        context.moveTo(.08, -.72); context.lineTo(.15 + gait, -.43);
        context.moveTo(-.04, -.4); context.lineTo(-.07 - gait, 0);
        context.moveTo(.04, -.4); context.lineTo(.07 + gait, 0); context.stroke();
      }
      context.restore();
    }

    function bird(context, x, y, size, phase) {
      context.save(); context.translate(x, y); context.strokeStyle = '#536f65';
      context.globalAlpha = .34; context.lineWidth = Math.max(1, size * .12); context.lineCap = 'round';
      const wing = Math.sin(phase) * size * .35;
      context.beginPath(); context.moveTo(-size, wing); context.quadraticCurveTo(-size * .45, -size * .45, 0, 0);
      context.quadraticCurveTo(size * .45, -size * .45, size, wing); context.stroke(); context.restore();
    }

    function inhabitants(rect, frame) {
      if (!state.occupation || (state.mode === 'time' && frame.first < 16)) return;
      const { x, y, w, h } = rect, t = state.time;
      ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
      if (state.mode === 'light') {
        // Overhead movement stays within the open central area of the shadow plan.
        const angle = t * .18;
        person(ctx, x + w * (.5 + Math.cos(angle) * .14), y + h * (.47 + Math.sin(angle) * .16), h * .065, angle, .43, true);
        person(ctx, x + w * (.47 + Math.sin(angle + 2) * .12), y + h * (.49 + Math.cos(angle + 2) * .12), h * .055, angle + 2, .34, true);
      } else if (state.mode === 'space') {
        [.1, .43, .79].forEach((start, i) => {
          const px = fraction(start + t * .003 - state.pan);
          person(ctx, x + px * w, y + h * (.89 + i * .015), h * (.2 - i * .025), t * 2.3 + i, .36);
        });
        bird(ctx, x + fraction(.35 + t * .004 - state.pan) * w, y + h * .4, h * .018, t * 5);
      } else if (state.view === 2) {
        // The inspected Inside image has the ground in its lower fifth.
        person(ctx, x + w * (.18 + .13 * Math.sin(t * .12)), y + h * .92, h * .19, t * 2.3, .39);
        person(ctx, x + w * (.57 + .12 * Math.sin(t * .1 + 2)), y + h * .87, h * .14, t * 2.2 + 2, .31);
        bird(ctx, x + w * (.56 + Math.sin(t * .15) * .12), y + h * (.63 + Math.cos(t * .15) * .04), h * .018, t * 5);
      } else if (state.view === 1) {
        person(ctx, x + w * (.38 + .12 * Math.sin(t * .12)), y + h * .71, h * .15, t * 2.3, .4);
        person(ctx, x + w * (.68 + .09 * Math.sin(t * .1 + 2)), y + h * .76, h * .17, t * 2.2 + 2, .32);
        bird(ctx, x + w * (.5 + Math.sin(t * .15) * .24), y + h * (.26 + Math.cos(t * .15) * .025), h * .015, t * 5);
      } else {
        person(ctx, x + w * (.27 + .08 * Math.sin(t * .12)), y + h * .79, h * .11, t * 2.3, .37);
        person(ctx, x + w * (.7 + .08 * Math.sin(t * .1 + 2)), y + h * .83, h * .13, t * 2.2 + 2, .34);
        bird(ctx, x + w * (.45 + Math.sin(t * .15) * .25), y + h * .14, h * .014, t * 5);
      }
      ctx.restore();
    }

    function dimensions(bitmap, mode, view) {
      const cw = canvas.width, ch = canvas.height;
      const width = bitmap.width, height = bitmap.height;
      const gap = (mode.gutter || 0) * width;
      const sw = mode.turns ? width : (width - gap * 2) / 3;
      const sx = mode.turns ? 0 : view * (sw + gap);
      const scale = Math.min(cw / sw, ch / height);
      const w = sw * scale, h = height * scale;
      return { sx, sw, sh: height, x: (cw - w) / 2, y: (ch - h) / 2, w, h };
    }

    function paint(frame) {
      if (!usable()) return;
      const ratio = Math.min(devicePixelRatio || 1, 2);
      const box = screen.getBoundingClientRect();
      const width = Math.max(1, Math.round(box.width * ratio)), height = Math.max(1, Math.round(box.height * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = mixCanvas.width = width; canvas.height = mixCanvas.height = height;
      }
      ctx.clearRect(0, 0, width, height);
      if (!frame) return;
      const first = cache.get(frame.keys[0]);
      const second = cache.get(frame.keys[1]);
      if (!first || !second) return;
      const rect = dimensions(first, frame.mode, state.view);
      const lay = (bitmap, alpha) => {
        if (alpha <= 0) return;
        mix.globalAlpha = alpha;
        if (frame.mode.turns) {
          mix.save(); mix.beginPath(); mix.rect(rect.x, rect.y, rect.w, rect.h); mix.clip();
          const shift = fraction(state.pan) * rect.w;
          mix.drawImage(bitmap, rect.x - shift, rect.y, rect.w, rect.h);
          mix.drawImage(bitmap, rect.x - shift + rect.w, rect.y, rect.w, rect.h); mix.restore();
        } else mix.drawImage(bitmap, rect.sx, 0, rect.sw, rect.sh, rect.x, rect.y, rect.w, rect.h);
      };
      mix.globalCompositeOperation = 'source-over'; mix.clearRect(0, 0, width, height);
      lay(first, 1 - frame.amount); mix.globalCompositeOperation = 'lighter'; lay(second, frame.amount);
      inhabitants(rect, frame);
      ctx.globalAlpha = 1; ctx.drawImage(mixCanvas, 0, 0);
      canvas.setAttribute('aria-label', `${viewName()}. ${frame.caption}. Pre-rendered growth scenario${state.occupation ? ' with authored diagrammatic people and birds' : ''}.`);
      viewLabel.textContent = state.mode === 'light' ? `Plan · ${viewName()}` : viewName();
    }

    async function showFallback() {
      if (!usable()) return;
      const requested = ++serial;
      try {
        fallback ||= await createImageBitmap(await fetchTimed(new URL('v8/assets/studies/seasonal-summer.webp', document.baseURI).href, new AbortController()));
        if (!usable() || requested !== serial || !state.error) return;
        const key = '__fallback'; cache.set(key, fallback);
        const frame = { keys: [key, key], amount: 0, mode: { gutter: .012533572068039392 }, first: 26, caption: 'Static fallback · established summer' };
        state.fallback = true; state.caption = frame.caption;
        const previousMode = state.mode, previousView = state.view;
        state.mode = 'time'; state.view = previousMode === 'time' ? previousView : 2;
        paint(frame); viewLabel.textContent = `${viewName()} · static fallback`;
        state.mode = previousMode; state.view = previousView; controls();
      } catch { /* The retry message remains if the local fallback is unavailable too. */ }
    }

    function fail(error) {
      if (!usable() || error?.name === 'AbortError') return;
      state.ready = false; state.playing = false; state.error = error.message || 'Drawing unavailable';
      cancelAnimationFrame(raf); raf = 0;
      showMessage(`This moment could not load: ${state.error}. Retry to load the selected moment.`, true);
      controls(); showFallback();
    }

    function draw() {
      if (!usable() || !manifest || state.error) return;
      const frame = selection();
      state.requestedCaption = frame.caption;
      const needed = [...new Set(frame.keys)];
      // Scrubbing must not queue the whole film on a slow connection.
      const ahead = frame.mode.frames[Math.min(frame.second + 1, frame.mode.frames.length - 1)].src;
      for (const [key, request] of pending) {
        if (!needed.includes(key) && key !== ahead) { request.controller.abort(); pending.delete(key); }
      }
      if (needed.every(key => cache.has(key))) {
        displayed = frame; state.ready = true; state.fallback = false; state.caption = frame.caption;
        renderRequest = ''; showMessage(''); needed.forEach(touchCache); paint(frame); controls(); trimCache();
        // At most one look-ahead image, never a complete mode download.
        const next = frame.mode.frames[Math.min(frame.second + 1, frame.mode.frames.length - 1)].src;
        if (!cache.has(next) && !pending.has(next)) imageFor(next).then(trimCache).catch(() => {});
        return;
      }
      state.ready = false;
      showMessage(`Loading ${frame.caption.toLowerCase()}…${state.caption ? ` Showing ${state.caption.toLowerCase()} meanwhile.` : ''}`);
      controls();
      const key = needed.join('|');
      if (renderRequest === key) return;
      renderRequest = key;
      Promise.all(needed.map(imageFor)).then(() => {
        if (renderRequest !== key || !usable()) return;
        renderRequest = ''; draw(); startClock();
      }).catch(error => { if (renderRequest === key) { renderRequest = ''; fail(error); } });
    }

    async function loadManifest() {
      if (!usable()) return;
      if (manifest) { draw(); startClock(); return; }
      if (manifestRequest) return;
      const controller = new AbortController(); manifestRequest = controller;
      showMessage('Loading the growth drawing…');
      try {
        const blob = await fetchTimed(sourceURL('manifest.json'), controller);
        const data = JSON.parse(await blob.text());
        if (!Array.isArray(data.modes) || !['time', 'space', 'light'].every(id => data.modes.some(mode => mode.id === id && mode.frames?.length))) throw new Error('Growth manifest is incomplete');
        if (!usable() || controller.signal.aborted) return;
        manifest = data; state.duration = currentMode().seconds; makeSelectors(); draw();
      } catch (error) { fail(error); }
      finally { if (manifestRequest === controller) manifestRequest = null; }
    }

    function tick(now) {
      raf = 0;
      if (!usable() || !state.playing || !state.ready) return;
      const dt = Math.min(.1, Math.max(0, (now - last) / 1000)); last = now;
      state.time = Math.min(state.duration, state.time + dt);
      if (state.time >= state.duration) state.playing = false;
      draw();
      if (state.playing && state.ready) raf = requestAnimationFrame(tick);
    }

    function startClock() {
      cancelAnimationFrame(raf); raf = 0;
      if (usable() && state.ready && state.playing) { last = performance.now(); raf = requestAnimationFrame(tick); }
    }

    function seek(value) {
      if (destroyed || !Number.isFinite(Number(value))) return;
      state.time = clamp(Number(value), 0, state.duration); state.playing = false;
      cancelAnimationFrame(raf); raf = 0; draw(); controls();
    }

    function setView(value) {
      if (destroyed || state.mode === 'space' || !Number.isInteger(Number(value)) || Number(value) < 0 || Number(value) > 2) return false;
      state.view = Number(value); state.playing = false; cancelAnimationFrame(raf); raf = 0;
      draw(); controls(); return true;
    }

    function setMode(mode) {
      if (destroyed || !Object.hasOwn(CHAPTERS, mode)) return false;
      if (mode === state.mode) return true;
      savedModes.set(state.mode, { time: state.time, view: state.view, pan: state.pan });
      const saved = savedModes.get(mode);
      state.mode = mode; state.duration = manifest?.modes.find(item => item.id === mode)?.seconds || { time: 40, space: 30, light: 22 }[mode];
      state.time = saved?.time ?? (mode === 'time' ? 16 / 33 * (1 - HOLD) * 40 : mode === 'light' ? 18 / 36 * (1 - HOLD) * 22 : 0);
      state.view = saved?.view ?? 2; state.pan = saved?.pan ?? 0; state.playing = false; state.ready = false;
      state.caption = ''; state.error = null; state.fallback = false; displayed = null; renderRequest = ''; serial++;
      cancelAnimationFrame(raf); raf = 0; ctx.clearRect(0, 0, canvas.width, canvas.height);
      makeSelectors(); draw(); controls(); return true;
    }

    function suspend() {
      serial++; renderRequest = ''; cancelAnimationFrame(raf); raf = 0;
      manifestRequest?.abort(); manifestRequest = null;
      for (const request of pending.values()) request.controller.abort();
      pending.clear();
    }

    function sync() {
      if (!usable()) suspend();
      else { if (state.error) showFallback(); else loadManifest(); }
    }

    function retry() {
      state.error = null; state.ready = false; state.fallback = false; state.caption = ''; displayed = null; serial++;
      showMessage('Loading the requested moment…'); loadManifest(); controls();
    }

    playButton.addEventListener('click', () => {
      if (!manifest || state.error) return;
      if (!state.playing && state.time >= state.duration) state.time = 0;
      state.playing = !state.playing; draw(); startClock(); controls();
    });
    resetButton.addEventListener('click', () => seek(0));
    range.addEventListener('input', () => seek(Number(range.value) / 1000 * state.duration));
    retryButton.addEventListener('click', retry);
    $('[data-v8-occupation]').addEventListener('click', () => { state.occupation = !state.occupation; draw(); controls(); });
    canvas.addEventListener('pointerdown', event => {
      if (state.mode !== 'space' || !state.ready) return;
      seek(state.time); held = { x: event.clientX, pan: state.pan }; canvas.setPointerCapture(event.pointerId); controls();
    });
    canvas.addEventListener('pointermove', event => {
      if (!held) return;
      state.pan = fraction(held.pan - (event.clientX - held.x) / Math.max(1, canvas.getBoundingClientRect().width)); draw();
    });
    const release = () => { held = null; controls(); };
    canvas.addEventListener('pointerup', release); canvas.addEventListener('pointercancel', release);
    root.addEventListener('keydown', event => {
      if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown', ' '].includes(event.key)) event.stopPropagation();
      if (event.target !== canvas) return;
      if (event.key === ' ') { event.preventDefault(); playButton.click(); }
      else if (['ArrowLeft', 'ArrowRight'].includes(event.key)) {
        event.preventDefault(); const direction = event.key === 'ArrowRight' ? 1 : -1;
        if (event.shiftKey && state.mode === 'space') { seek(state.time); state.pan = fraction(state.pan + direction / 12); draw(); }
        else seek(state.time + direction * state.duration / Math.max(8, (currentMode()?.frames.length || 15) * 2));
      } else if (event.key === 'Home' || event.key === 'End') { event.preventDefault(); seek(event.key === 'Home' ? 0 : state.duration); }
    });
    root.addEventListener('wheel', event => event.stopPropagation(), { passive: true });
    const onMotion = () => { if (motion.matches) seek(state.time); };
    document.addEventListener('visibilitychange', sync); motion.addEventListener('change', onMotion);
    const resize = new ResizeObserver(() => { if (usable() && displayed && !state.error) paint(displayed); });
    resize.observe(screen); makeSelectors(); controls();

    return {
      setActive(value) { if (destroyed) return; state.active = !!value; sync(); },
      setMode, setView, seek,
      getState: () => ({ ...state, loaded: !!manifest, running: !!raf, destroyed, cachedFrames: cache.size, pendingFrames: pending.size, renderedFrame: displayed?.first ?? null }),
      destroy() {
        if (destroyed) return;
        state.active = false; suspend(); destroyed = true; resize.disconnect();
        document.removeEventListener('visibilitychange', sync); motion.removeEventListener('change', onMotion);
        for (const bitmap of new Set([...cache.values(), fallback].filter(Boolean))) bitmap.close?.();
        cache.clear(); root.remove();
      }
    };
  }
  window.DESIGNX_V8_GROWTH = Object.freeze({ mount });
})();

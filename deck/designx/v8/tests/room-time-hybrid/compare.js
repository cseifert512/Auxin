// Isolated experiment: nothing here mounts into or changes the presentation.
const $ = selector => document.querySelector(selector);
const surface = $('#drawing-surface'), viewer = $('.viewer');
const names = { original: 'Original film', hybrid: 'Hybrid', compressed: 'Compressed film' };
const descriptions = { original: 'The existing camera-study film.', hybrid: 'Live timber, with a baked plant layer.', compressed: 'The complete scene, encoded for smaller delivery.' };
const records = new Map();
let manifest, active = null, generation = 0, currentTime = 0, playing = false, ready = false, raf = 0;
const formatBytes = n => Number.isFinite(n) ? `${(n / 1e6).toFixed(n < 1e6 ? 2 : 1)} MB` : '—';
const formatMs = n => Number.isFinite(n) ? n >= 1000 ? `${(n / 1000).toFixed(2)} s` : `${Math.round(n)} ms` : '—';
const clampTime = t => Math.max(0, Math.min(Number(manifest?.duration) || 51, Number(t) || 0));
const reportError = error => { $('#error-note').hidden = false; $('#error-note').textContent = error?.message || String(error); };
function payloadFor(id) {
  const data = manifest?.[id];
  if (Number.isFinite(data?.totalBytes)) return data.totalBytes;
  if (Number.isFinite(data?.payloadBytes)) return data.payloadBytes;
  if (Array.isArray(data?.assets)) return data.assets.reduce((sum, asset) => sum + (asset.bytes || 0), 0);
  if (Number.isFinite(data?.bytes)) return data.bytes;
  return id === 'original' ? 39599179 : null;
}
function renderTime(t) {
  currentTime = clampTime(t);
  $('#scrub').value = String(currentTime);
  $('#time-readout').value = `${currentTime.toFixed(1)} s`;
  $('#phase-readout').textContent = currentTime < 12 ? 'Assembly' : currentTime < 13 ? 'Planting' : `Year ${Math.min(9, Math.floor((currentTime - 13) / 36 * 9.2758))} · Scenario`;
  $('#scrub').setAttribute('aria-valuetext', `${currentTime.toFixed(1)} seconds, ${$('#phase-readout').textContent}`);
}
function setPlaying(value) {
  playing = Boolean(value && ready);
  $('#play').textContent = playing ? 'Pause' : 'Play';
  $('#play').setAttribute('aria-label', `${playing ? 'Pause' : 'Play'} drawing`);
}
function resourceMeasurements(record) {
  const resources = performance.getEntriesByType('resource').filter(entry => entry.startTime >= record.started && entry.name !== new URL('manifest.json', location.href).href);
  return { requestedResources: resources.length, transferBytes: resources.reduce((sum, entry) => sum + entry.transferSize, 0), encodedBodyBytes: resources.reduce((sum, entry) => sum + entry.encodedBodySize, 0), note: 'Resource Timing entries observed since activation; zero transfer can mean a cached response. In-flight media requests may not yet be included.' };
}
function syncRecord() {
  if (!active?.record) return;
  const record = active.record;
  try { record.renderer = active.controller?.getMetrics?.() || {}; } catch { /* Timing stays available if a renderer is being disposed. */ }
  const video = active.video || active.controller?.video;
  if (video?.getVideoPlaybackQuality) {
    const quality = video.getVideoPlaybackQuality();
    record.droppedFrames = quality.droppedVideoFrames;
    record.decodedFrames = quality.totalVideoFrames;
  } else {
    record.droppedFrames = record.renderer.droppedVideoFrames ?? record.renderer.droppedFrames ?? null;
    record.decodedFrames = record.renderer.totalVideoFrames ?? record.renderer.decodedFrames ?? null;
  }
  record.resources = resourceMeasurements(record);
  record.meanCallbackRate = record.playbackMs > 0 ? record.callbacks * 1000 / record.playbackMs : null;
}
function renderMetrics() {
  syncRecord();
  const record = active?.record;
  $('#metric-startup').textContent = formatMs(record?.firstFrameMs);
  $('#metric-payload').textContent = formatBytes(record?.declaredBytes);
  $('#metric-cadence').textContent = record?.meanCallbackRate ? `${record.meanCallbackRate.toFixed(1)} / s` : '—';
  $('#metric-dropped').textContent = Number.isFinite(record?.droppedFrames) ? String(record.droppedFrames) : '—';
  $('#metric-payload-note').textContent = active?.id === 'original' ? 'Existing film file; player excluded' : 'Declared test assets; see saved report';
  const rows = [];
  for (const id of ['original', 'hybrid', 'compressed'].filter(id => id !== 'compressed' || manifest?.compressed)) {
    const r = records.get(id), row = document.createElement('tr');
    row.classList.toggle('is-current', active?.id === id);
    const values = [names[id], formatMs(r?.firstFrameMs), formatBytes(r?.declaredBytes ?? payloadFor(id)), r?.meanCallbackRate ? `${r.meanCallbackRate.toFixed(1)} / s` : '—', r ? String(r.stalls) : '—', Number.isFinite(r?.decodedFrames) ? `${r.droppedFrames ?? '—'} / ${r.decodedFrames}` : '—'];
    values.forEach(value => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); });
    rows.push(row);
  }
  $('#comparison-rows').replaceChildren(...rows);
}
function stopSampling() { cancelAnimationFrame(raf); raf = 0; }
function sample() {
  stopSampling();
  let previous = performance.now(), refreshed = previous;
  const frame = now => {
    if (!active) return;
    if (playing && !document.hidden) {
      const delta = now - previous;
      if (delta > 0 && delta < 1000) { active.record.callbacks++; active.record.playbackMs += delta; active.record.maxCallbackGapMs = Math.max(active.record.maxCallbackGapMs, delta); }
      if (active.video) renderTime(active.video.currentTime);
    }
    previous = now;
    if (now - refreshed > 500) { renderMetrics(); refreshed = now; }
    raf = requestAnimationFrame(frame);
  };
  raf = requestAnimationFrame(frame);
}
function waitForVideo(video, event, test, signal) {
  if (test()) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const events = Array.isArray(event) ? event : [event];
    const done = () => { if (test()) { cleanup(); resolve(); } };
    const fail = () => { cleanup(); reject(new Error('The film could not load. The still remains visible.')); };
    const abort = () => { cleanup(); reject(new DOMException('Player replaced', 'AbortError')); };
    const timeout = setTimeout(() => { cleanup(); reject(new Error('The film is taking too long to load. Select the version again to retry.')); }, 45000);
    const cleanup = () => { clearTimeout(timeout); events.forEach(name => video.removeEventListener(name, done)); video.removeEventListener('error', fail); signal.removeEventListener('abort', abort); };
    events.forEach(name => video.addEventListener(name, done)); video.addEventListener('error', fail, { once: true }); signal.addEventListener('abort', abort, { once: true });
  });
}
async function createFilm(id, token, abort) {
  const video = document.createElement('video');
  video.muted = true; video.playsInline = true; video.preload = 'auto'; video.loop = false;
  video.setAttribute('aria-label', names[id]);
  surface.replaceChildren(video); active.video = video;
  video.addEventListener('waiting', () => { if (active?.video === video && playing) active.record.stalls++; });
  video.addEventListener('ended', () => { if (active?.video === video) { renderTime(video.currentTime); setPlaying(false); renderMetrics(); } });
  video.src = new URL(manifest[id]?.src || '../../assets/time-experiment/orbit.mp4', location.href).href;
  video.load();
  await waitForVideo(video, 'loadedmetadata', () => video.readyState >= 1, abort.signal);
  if (token !== generation) return;
  if (currentTime > 0) video.currentTime = currentTime;
  await waitForVideo(video, ['loadeddata', 'seeked'], () => video.readyState >= 2 && !video.seeking, abort.signal);
  return {
    async setTime(t) { video.currentTime = clampTime(t); await waitForVideo(video, 'seeked', () => video.readyState >= 2 && !video.seeking, abort.signal); },
    play: () => video.play(), pause: () => video.pause(),
    dispose() { video.pause(); video.removeAttribute('src'); video.load(); video.remove(); },
    getMetrics: () => ({ videoWidth: video.videoWidth, videoHeight: video.videoHeight, bufferedSeconds: [...Array(video.buffered.length)].reduce((sum, _, i) => sum + video.buffered.end(i) - video.buffered.start(i), 0) }),
  };
}
async function select(id) {
  if (!manifest || !(id in names) || (id === 'compressed' && !manifest.compressed)) return;
  const resume = playing, requestedTime = currentTime, token = ++generation;
  syncRecord(); stopSampling();
  active?.abort.abort(); active?.controller?.pause?.(); active?.controller?.dispose?.();
  if (active?.video) { active.video.pause(); active.video.removeAttribute('src'); active.video.load(); }
  surface.replaceChildren();
  ready = false; setPlaying(false); viewer.classList.remove('is-ready');
  $('#play').disabled = $('#scrub').disabled = $('#restart').disabled = true;
  $('#error-note').hidden = true;
  $('#status-text').textContent = `Preparing ${names[id].toLowerCase()}…`;
  $('#viewer-label').textContent = names[id]; $('#variant-description').textContent = descriptions[id];
  document.querySelectorAll('[data-variant]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.variant === id)));
  const record = { id, label: names[id], started: performance.now(), startedAt: new Date().toISOString(), firstFrameMs: null, declaredBytes: payloadFor(id), callbacks: 0, playbackMs: 0, maxCallbackGapMs: 0, stalls: 0, droppedFrames: null, decodedFrames: null };
  records.set(id, record);
  active = { id, record, abort: new AbortController(), controller: null, video: null };
  renderMetrics();
  try {
    let controller;
    if (id === 'hybrid') {
      const canvas = document.createElement('canvas'); canvas.width = manifest.width || 1600; canvas.height = manifest.height || 900;
      canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', 'Live timber with the baked planting layer'); surface.append(canvas);
      const { createHybrid } = await import('./renderer.bundle.js');
      if (token !== generation) return;
      controller = await createHybrid({ canvas, manifest, signal: active.abort.signal, onReady() {}, onError(error) { if (token === generation) reportError(error); }, onFrame(frame) { if (token === generation && ready) renderTime(frame.time ?? frame.mediaTime); }, onTime(t) { if (token === generation && ready) renderTime(t); } });
      if (token !== generation) { controller?.dispose?.(); return; }
      await controller.setTime(requestedTime);
      renderTime(requestedTime);
    } else controller = await createFilm(id, token, active.abort);
    if (token !== generation) { controller?.dispose?.(); return; }
    active.controller = controller;
    if (id === 'hybrid' && controller.video) {
      controller.video.addEventListener('waiting', () => { if (token === generation && playing) record.stalls++; });
      controller.video.addEventListener('ended', () => { if (token === generation) { setPlaying(false); renderMetrics(); } });
    }
    await new Promise(resolve => requestAnimationFrame(resolve));
    if (token !== generation) return;
    record.firstFrameMs = performance.now() - record.started;
    ready = true; viewer.classList.add('is-ready');
    $('#play').disabled = $('#scrub').disabled = $('#restart').disabled = false;
    $('#download-results').disabled = false;
    renderMetrics(); sample();
    if (resume) await play();
  } catch (error) {
    if (token !== generation || error.name === 'AbortError') return;
    record.error = error.message; $('#status-text').textContent = 'Drawing unavailable · still retained'; reportError(error); renderMetrics();
  }
}
async function play() {
  if (!ready) return;
  if (currentTime >= (manifest.duration || 51) - .02) await seek(0);
  try { await active.controller.play(); setPlaying(true); } catch (error) { setPlaying(false); reportError(error); }
}
function pause() { active?.controller?.pause?.(); setPlaying(false); renderMetrics(); }
async function seek(t) { pause(); renderTime(t); if (ready) await active.controller.setTime(currentTime); }
function snapshot() {
  syncRecord();
  return { schema: 'bower.room-time-rendering-comparison/1', savedAt: new Date().toISOString(), page: location.href, userAgent: navigator.userAgent, viewport: { width: innerWidth, height: innerHeight, devicePixelRatio }, currentVersion: active?.id, currentTime, playing, ready, manifest, measurements: [...records.values()], limitation: 'Device-local readings. A reload does not clear the browser cache. Display callbacks are not GPU timings; unfinished media transfers may be absent from Resource Timing.' };
}
document.querySelectorAll('[data-variant]').forEach(button => button.addEventListener('click', () => select(button.dataset.variant)));
$('#play').addEventListener('click', () => playing ? pause() : play());
$('#scrub').addEventListener('input', event => { seek(Number(event.target.value)).catch(reportError); });
$('#restart').addEventListener('click', () => seek(0).catch(reportError));
$('#download-results').addEventListener('click', () => {
  const href = URL.createObjectURL(new Blob([JSON.stringify(snapshot(), null, 2) + '\n'], { type: 'application/json' }));
  const link = document.createElement('a'); link.href = href; link.download = 'bower-room-through-time-comparison.json'; link.click(); setTimeout(() => URL.revokeObjectURL(href), 1000);
});
document.addEventListener('visibilitychange', () => { if (document.hidden) pause(); });
window.addEventListener('pagehide', () => { active?.abort.abort(); active?.controller?.dispose?.(); stopSampling(); });
window.__roomTimeTest = { select, seek, play, pause, snapshot, setLayerEnabled(value) { return active?.controller?.setLayerEnabled?.(value); }, get ready() { return ready; } };
try {
  const response = await fetch('./manifest.json'); if (!response.ok) throw new Error('The comparison manifest is not available yet.');
  manifest = await response.json();
  $('#scrub').max = String(manifest.duration || 51);
  document.querySelector('[data-variant="compressed"]').hidden = !manifest.compressed;
  const poster = manifest.poster || manifest.original?.poster;
  if (poster) $('#poster').src = new URL(poster, location.href).href;
  if (manifest.note) $('#evidence-note').textContent = manifest.note;
  const parameters = new URL(location.href).searchParams;
  renderTime(clampTime(parameters.get('time')));
  const requested = parameters.get('variant');
  await select(requested && requested in names && (requested !== 'compressed' || manifest.compressed) ? requested : 'original');
} catch (error) { $('#status-text').textContent = 'Comparison unavailable · still retained'; reportError(error); }

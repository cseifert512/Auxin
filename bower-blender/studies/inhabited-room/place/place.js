/* "The place": the whole place first, then into it. Everything shown was made beforehand (manifest.js);
   this page only chooses which picture, marks and words to show. Each view is a sequence of frames of any
   length, on one line of days; the named moments are ticks on that line. */
(() => {
  'use strict';
  const P = window.BOWER_THE_PLACE;
  const $ = (id) => document.getElementById(id);
  const NS = 'http://www.w3.org/2000/svg';
  const query = new URLSearchParams(location.search);
  const stations = new Map(P.stations.map((s) => [s.id, s]));
  const still = query.has('still') || matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (query.has('embed')) document.body.classList.add('embed');
  if (still) document.body.classList.add('still');

  const state = { station: P.start, day: P.moments[0].day, life: false, playing: false };
  let shot = null, timer = null;
  const cache = new Map();   // pictures asked for ahead of being shown, kept so the browser holds them
  const allDays = Object.values(P.views).flatMap((v) => v.frames.map((f) => f.day));
  const span = [Math.min(...allDays), Math.max(...allDays)];

  // the stage is drawn at 1600 x 900 and scaled to the window
  const fitStage = () => document.documentElement.style.setProperty('--k', Math.min(innerWidth / 1600, innerHeight / 900));
  addEventListener('resize', fitStage); fitStage();

  const svg = (tag, attrs = {}, text) => {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  const view = () => P.views[stations.get(state.station).view];
  /** The frame the picture shows: the last one this view has on or before the chosen day. */
  const frame = (v = view()) => [...v.frames].reverse().find((f) => f.day <= state.day) ?? v.frames[0];
  /** The named moment a day falls in, for the words and figures. */
  const moment = (day) => [...P.moments].reverse().find((m) => m.day <= day) ?? P.moments[0];
  /** A figure for the frame on show: the frame's own, else the moment's, else the one value the manifest has. */
  const figure = (key, f, m) => f.fig?.[key] ?? P.figures[key]?.values?.[m.id] ?? P.figures[key]?.value ?? null;
  const say = (words, id) => (typeof words === 'string' ? words : words[id] ?? words.default ?? '');
  const preload = (v) => { for (const f of v.frames) if (!cache.has(f.file)) { const img = new Image(); img.src = f.file; cache.set(f.file, img); } };

  /** One picture fitted into the picture area, with its click targets. */
  function build(station, f) {
    const v = P.views[station.view], box = $('pic');
    const k = Math.min(box.clientWidth / v.size[0], box.clientHeight / v.size[1]);
    const w = v.size[0] * k, h = v.size[1] * k, x0 = (box.clientWidth - w) / 2, y0 = (box.clientHeight - h) / 2;
    const node = document.createElement('div');
    node.className = 'shot';
    Object.assign(node.style, { width: `${w}px`, height: `${h}px`, left: `${x0}px`, top: `${y0}px` });
    node.dataset.station = station.id; node.dataset.file = f.file;
    const img = new Image(); img.alt = v.note; img.src = f.file;
    const marks = svg('svg', { class: `marks${shot?.dataset.station === station.id ? ' again' : ''}`, viewBox: `0 0 ${w} ${h}` });
    station.targets.forEach((target, i) => {
      const name = target.at.find((n) => v.places[n]);
      if (!name) return;
      const [x, y] = [v.places[name][0] * w, v.places[name][1] * h];
      const left = x > w - 260;   // the label goes to whichever side has room
      const g = svg('g', { class: 'hot', tabindex: 0, role: 'button', 'aria-label': target.label });
      const inner = svg('g', { class: 'in', style: `animation-delay:${i * 120}ms` });   // they arrive one after another
      const tx = x + (left ? -26 : 26), anchor = left ? 'end' : 'start';
      const fig = svg('text', { class: 'fig', x: tx, y: y + 26, 'text-anchor': anchor });
      fig.dataset.key = target.figure ?? ''; fig.dataset.suffix = target.suffix ?? '';
      inner.append(svg('circle', { class: 'pulse', cx: x, cy: y, r: 8, style: `animation-delay:${(i * 0.6) % 2.4}s` }),
        svg('circle', { class: 'ring', cx: x, cy: y, r: 17 }), svg('circle', { class: 'core', cx: x, cy: y, r: 6 }),
        svg('text', { x: tx, y: y + 4, 'text-anchor': anchor }, target.label), fig);
      g.append(inner);
      const go = () => goTo(target.to);
      g.addEventListener('click', go);
      g.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
      marks.append(g);
    });
    node.box = { x: x0, y: y0, w, h, places: v.places };
    node.append(img, marks);
    return node;
  }

  /** Put the right picture on top. A view with few frames dissolves from one to the next; a dense one just steps. */
  function show() {
    const station = stations.get(state.station), f = frame();
    if (shot?.dataset.station === station.id) {
      if (shot.dataset.file === f.file) return;
      if (view().frames.length >= 8) { shot.dataset.file = f.file; shot.querySelector('img').src = f.file; return; }
    }
    const before = shot, next = build(station, f);
    $('pic').insertBefore(next, $('life'));
    shot = next;
    const reveal = () => { next.classList.add('on'); if (before) setTimeout(() => before.remove(), still ? 0 : 520); };
    const img = next.querySelector('img');
    if (still || !before) reveal();
    else if (img.complete) requestAnimationFrame(() => requestAnimationFrame(reveal));
    else { img.onload = reveal; img.onerror = reveal; }
  }

  function chrome() {
    const station = stations.get(state.station), f = frame(), m = moment(f.day), days = new Set(view().frames.map((x) => x.day));
    $('title').textContent = station.title;
    $('back').disabled = state.station === P.start;
    $('caption').textContent = say(station.caption, m.id);
    $('figures').replaceChildren(...station.figures.filter((key) => figure(key, f, m) !== null).map((key) => {
      const fig = P.figures[key], li = document.createElement('li');
      li.innerHTML = '<b></b><span></span><small></small>';
      li.children[0].textContent = figure(key, f, m);
      li.children[1].textContent = fig.label;
      li.children[2].textContent = f.fig?.[key] ? `${fig.kind}, this frame` : fig.kind; li.title = fig.source;
      return li;
    }));
    // each bubble's live figure, from the frame on show; it ticks when it changes
    for (const t of shot?.querySelectorAll('text.fig') ?? []) {
      const value = t.dataset.key ? figure(t.dataset.key, f, m) : null, text = value === null ? '' : value + t.dataset.suffix;
      if (text === t.textContent) continue;
      if (t.textContent) t.classList.toggle('tick-a', !t.classList.toggle('tick-b'));   // swap animations: no layout read
      t.textContent = text;
    }
    $('date').textContent = f.month;
    $('scrub').value = f.day;
    // a tick's label shows when it is the moment on show, or when it has room beside those already shown
    const shownAt = [];
    const ticks = [...$('ticks').children].sort((a, b) => (b.dataset.moment === f.moment) - (a.dataset.moment === f.moment));
    for (const li of ticks) {
      const x = Number(li.dataset.x), room = shownAt.every((s) => Math.abs(s - x) > 130);
      li.classList.toggle('missing', !days.has(Number(li.dataset.day)));   // no picture of that day here: the view keeps the one before
      li.classList.toggle('quiet', !room);
      if (room) shownAt.push(x);
      li.firstChild.setAttribute('aria-current', String(li.dataset.moment === f.moment));
    }
    document.body.classList.toggle('playing', state.playing);
    $('play').textContent = state.playing ? '❚❚ Pause' : '▶ Play';
    $('lifebtn').setAttribute('aria-pressed', String(state.life));
    $('life').style.display = state.life && P.life.views.includes(station.view) ? '' : 'none';
  }

  const current = () => ({ station: state.station, view: stations.get(state.station).view, day: state.day, frame: frame().file, moment: moment(frame().day).id, life: state.life, playing: state.playing, stations: [...stations.keys()], moments: P.moments.map((m) => m.id) });
  function changed() {
    chrome();
    if (parent !== window) parent.postMessage({ type: 'bower-place:state', state: current() }, '*');
    return current();
  }

  function goTo(id) {
    if (!stations.has(id)) throw new Error(`No such place in the drawing: ${id}`);
    state.station = id; preload(view()); show(); return changed();
  }
  /** A named moment ('year-3'), a day ('day:837') or a number of days after the start of the run. */
  function setMoment(at) {
    const named = P.moments.find((m) => m.id === at);
    const day = named ? named.day : Number(String(at).replace('day:', ''));
    if (!Number.isFinite(day)) throw new Error(`No such moment: ${at}`);
    state.day = Math.max(span[0], Math.min(span[1], day)); show(); return changed();
  }
  function setLife(on) { state.life = !!on; return changed(); }
  /** Milliseconds a frame: brisk when a view has many, slow when few. */
  const rate = (n = view().frames.length) => (n >= 24 ? 1000 / 12 : n >= 8 ? 1000 / 6 : 1200);
  /** Once through every frame of this view at that steady rate, from `from` (a frame index). */
  function play(on = !state.playing, from = 0) {
    clearTimeout(timer);
    state.playing = on;
    if (on) {
      const frames = view().frames, ms = rate();
      let i = from;
      const step = () => { setMoment(frames[i].day); i += 1; if (i < frames.length) timer = setTimeout(step, ms); else { state.playing = false; changed(); } };
      step();
    }
    return changed();
  }
  /** For the deck: seconds a full play of this view takes, and a seek within it that pauses. */
  const duration = () => (view().frames.length * rate()) / 1000;
  function setT(seconds) {
    const frames = view().frames, i = Math.max(0, Math.min(frames.length - 1, Math.floor((seconds * 1000) / rate())));
    play(false);
    return setMoment(frames[i].day);
  }
  const nudge = (by) => { const frames = view().frames, i = frames.indexOf(frame()) + by; if (frames[i]) { play(false); setMoment(frames[i].day); } };

  // ---- the page's controls ----
  Object.assign($('scrub'), { min: span[0], max: span[1] });
  $('scrub').addEventListener('input', (e) => { play(false); setMoment(Number(e.target.value)); });
  for (const m of P.moments) {
    const li = document.createElement('li'), button = document.createElement('button');
    const share = (m.day - span[0]) / (span[1] - span[0] || 1);
    li.dataset.moment = m.id; li.dataset.day = m.day; li.dataset.x = share * $('ticks').clientWidth; li.style.left = `${share * 100}%`;
    button.type = 'button'; button.title = m.says; button.textContent = m.month;
    button.addEventListener('click', () => { play(false); setMoment(m.id); });
    li.append(button); $('ticks').append(li);
  }
  $('back').addEventListener('click', () => goTo(P.start));
  $('play').addEventListener('click', () => play());
  $('lifebtn').addEventListener('click', () => setLife(!state.life));
  $('reallines').replaceChildren(...P.real.lines.map((t) => Object.assign(document.createElement('li'), { textContent: t })));
  $('realfrom').textContent = `From ${P.real.from}`;
  $('realbtn').addEventListener('click', () => { const open = $('real').hidden; $('real').hidden = !open; $('realbtn').setAttribute('aria-expanded', String(open)); });
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape') goTo(P.start);
    if (e.target === $('scrub')) return;   // the slider steps itself
    if (e.key === 'ArrowRight') nudge(1);
    if (e.key === 'ArrowLeft') nudge(-1);
  });

  // ---- life: an illustration, not a finding. A few birds cross the picture now and then and sometimes settle. ----
  const birds = [];
  const rnd = (a, b) => a + Math.random() * (b - a);
  function fly(b, now) {
    const box = shot?.box, perch = box?.places[P.life.perch];
    if (!box) return;
    const at = (x, y) => [box.x + x * box.w, box.y + y * box.h];
    const fromLeft = Math.random() < 0.5, settle = !!perch && !b.perched && Math.random() < 0.35;
    b.p0 = b.perched ? b.p2 : at(fromLeft ? -0.08 : 1.08, rnd(0.05, 0.35));
    b.p2 = settle ? at(perch[0] + rnd(-0.03, 0.03), perch[1]) : at(fromLeft ? 1.1 : -0.1, rnd(0.05, 0.4));
    b.p1 = [(b.p0[0] + b.p2[0]) / 2 + rnd(-80, 80), Math.min(b.p0[1], b.p2[1]) - rnd(40, 160)];
    b.t0 = now + (b.perched ? 0 : rnd(1500, 9000)); b.dur = rnd(5000, 9000); b.perched = false; b.settle = settle;
  }
  for (let i = 0; i < 4; i += 1) {
    const el = svg('path', { class: 'bird', d: 'M-7,0 Q-3.5,-5 0,0 Q3.5,-5 7,0' });
    $('life').append(el); birds.push({ el, t0: 0, dur: 0 });
  }
  function tick(now) {
    requestAnimationFrame(tick);
    if (!state.life || $('life').style.display === 'none') return;
    $('life').setAttribute('viewBox', `0 0 ${$('pic').clientWidth} ${$('pic').clientHeight}`);
    for (const b of birds) {
      if (!b.p0) fly(b, now);
      else if (!b.perched && now > b.t0 + b.dur) { if (b.settle) { b.perched = true; b.t0 = now; b.dur = rnd(3000, 7000); } else fly(b, now); }
      else if (b.perched && now > b.t0 + b.dur) fly(b, now);
      if (!b.p0) continue;
      const t = b.perched ? 1 : (now - b.t0) / b.dur;
      if (t < 0) { b.el.style.opacity = 0; continue; }
      const u = 1 - t, x = u * u * b.p0[0] + 2 * u * t * b.p1[0] + t * t * b.p2[0], y = u * u * b.p0[1] + 2 * u * t * b.p1[1] + t * t * b.p2[1];
      const flap = b.perched ? 0.25 : 0.35 + 0.65 * Math.abs(Math.sin(now / 95 + b.dur));
      b.el.style.opacity = 1;
      b.el.setAttribute('transform', `translate(${x.toFixed(1)},${y.toFixed(1)}) scale(1.4,${(1.4 * flap).toFixed(2)})`);
    }
  }
  if (!still) requestAnimationFrame(tick);

  // ---- for a slide that drives it ----
  const actions = { goTo, setMoment, setLife, play, setT, state: current };
  Object.assign(window, { __goTo: goTo, __setMoment: setMoment, __setLife: setLife, __play: play, __setT: setT, __state: current });
  Object.defineProperty(window, '__duration', { get: duration });
  addEventListener('message', (event) => {
    const data = event.data;
    if (parent === window || event.source !== parent || data?.type !== 'bower-place:command') return;
    try {
      if (!actions[data.action]) throw new Error(`No such action: ${data.action}`);
      parent.postMessage({ type: 'bower-place:reply', requestId: data.requestId, result: actions[data.action](...(data.args ?? [])) }, '*');
    } catch (error) {
      parent.postMessage({ type: 'bower-place:reply', requestId: data.requestId, error: String(error?.message ?? error) }, '*');
    }
  });

  state.life = query.get('life') === '1';
  goTo(stations.has(query.get('station')) ? query.get('station') : P.start);
  if (query.get('moment')) { try { setMoment(query.get('moment')); } catch { /* an unknown moment leaves the first */ } }
  window.__ready = true;
  if (parent !== window) parent.postMessage({ type: 'bower-place:ready', state: current() }, '*');
})();

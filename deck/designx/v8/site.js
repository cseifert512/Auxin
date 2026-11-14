// Scroll is the only control on this page, and it is time: years in the room, hours on its floor, seconds at the mill.
//
// A scene is a tall stretch of page with a stage pinned in it. How far the stretch has been scrolled is a number
// from 0 to 1, and each kind of scene turns that number into a moment:
//   frames    a drawing made beforehand as pictures (drawings-in-code, `npm run plate`), blended from one to the next
//   factory   Daniel's factory drawings, which draw themselves at a time they are told (bower-factory:command, seek)
// Nothing is worked out here but which picture to show. The clock in the mast says what the scroll is moving.
(() => {
  'use strict';
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const two = (n) => String(n).padStart(2, '0');

  // a scene rests a little at each end of its stretch, so the first and last moments are seen arriving and leaving
  const LEAD = 0.04;
  const TAIL = 0.07;
  // the gap between the views in a frame, as a share of its width (the same in every piece made by plate.mjs)
  const GAP = 0.012533572;
  const narrow = matchMedia('(max-width: 760px)');

  // ---- what each frame is called, and where a scene's rail names a new part (by frame) -------------------------
  const runs = (list) => list.flatMap(([name, n]) => Array(n).fill(name));
  const hour = (i) => {
    const minutes = 360 + i * 20;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    if (h === 12 && m === 0) return 'noon';
    return `${h > 12 ? h - 12 : h}${m ? `:${two(m)}` : ''} ${h < 12 ? 'am' : 'pm'}`;
  };
  const called = {
    room: runs([['The design', 2], ['Assembly', 14], ['At installation', 1], ['Planting', 1], ['Establishing', 7], ['Established', 1],
      ['Established · summer', 1], ['Established · early autumn', 1], ['Established · autumn', 1], ['Established · leaf fall', 1],
      ['Established · winter', 1], ['Established · early spring', 1], ['Established · spring', 1], ['Established · summer', 1]]),
    light: Array.from({ length: 37 }, (_, i) => `Midsummer · ${hour(i)}`),
  };
  const marks = {
    room: [['The design', 0], ['Assembly', 2], ['Planting', 16], ['Establishing', 18], ['Established', 25]],
    light: [['6 am', 0], ['9 am', 9], ['Noon', 18], ['3 pm', 27]],
  };

  // ---- a drawing made beforehand as pictures -------------------------------------------------------------------
  function frames(el) {
    const canvas = $('canvas', el);
    const ctx = canvas.getContext('2d');
    const figure = canvas.closest('.drawing');
    const count = Number(el.dataset.count);
    const panels = Number(el.dataset.panels ?? 1);
    const images = new Array(count).fill(null);
    let asked = false;
    let source = null; // the part of a frame that is drawn: all of it, or its first view on a narrow screen
    let at = 0;

    const fit = () => {
      const first = images.find(Boolean);
      if (!first) return;
      const one = narrow.matches && panels > 1;
      const gap = first.naturalWidth * GAP;
      const w = one ? (first.naturalWidth - gap * (panels - 1)) / panels : first.naturalWidth;
      source = { w, h: first.naturalHeight };
      canvas.width = Math.round(w);
      canvas.height = first.naturalHeight;
      figure.style.setProperty('--ratio', (w / first.naturalHeight).toFixed(4));
      figure.classList.toggle('one', one);
    };
    // the nearest frame that has come, looking back first: a drawing still arriving shows what it has
    const nearest = (i) => {
      for (let d = 0; d < count; d++) {
        if (images[i - d]) return images[i - d];
        if (images[i + d]) return images[i + d];
      }
      return null;
    };
    const put = (image, alpha) => {
      ctx.globalAlpha = alpha;
      ctx.drawImage(image, 0, 0, source.w, source.h, 0, 0, canvas.width, canvas.height);
    };
    const render = (pp) => {
      at = pp;
      if (!source) return;
      const x = pp * (count - 1);
      const i = Math.min(count - 1, Math.floor(x));
      const f = x - i;
      const a = nearest(i);
      const b = images[i + 1];
      ctx.globalCompositeOperation = 'source-over';
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!a) return;
      if (!b || b === a || f < 0.004) return put(a, 1);
      // a true blend of two pictures on a clear ground: each by its share, added, so that timber which is in both
      // stays solid and what is in only one fades
      put(a, 1 - f);
      ctx.globalCompositeOperation = 'lighter';
      put(b, f);
    };
    const load = () => {
      if (asked) return;
      asked = true;
      for (let i = 0; i < count; i++) {
        const image = new Image();
        image.decoding = 'async';
        image.onload = () => {
          images[i] = image;
          if (!source) fit();
          render(at);
        };
        image.src = `${el.dataset.src}${two(i)}.webp`;
      }
    };
    const names = called[el.id] ?? [];
    return {
      load,
      render,
      refit: () => { fit(); render(at); },
      when: (pp) => names[Math.round(pp * (count - 1))] ?? '',
      marks: (marks[el.id] ?? []).map(([name, i]) => [name, i / (count - 1)]),
      state: () => ({ frames: count, come: images.filter(Boolean).length }),
    };
  }

  // ---- Daniel's factory drawings: each is a page of its own that draws itself at the time it is told ------------
  let serial = 0;
  const tell = (frame, action, ...args) => frame.contentWindow?.postMessage({ type: 'bower-factory:command', requestId: ++serial, action, args }, '*');

  function factory(el) {
    const sheets = $$('iframe', el);
    const ready = new Set();
    let asked = false;
    let at = 0;
    const where = (pp) => {
      const x = pp * sheets.length;
      const k = Math.min(sheets.length - 1, Math.floor(x));
      return { k, sheet: sheets[k], seconds: clamp(x - k) * Number(sheets[k].dataset.seconds) };
    };
    const render = (pp) => {
      at = pp;
      const { k, sheet, seconds } = where(pp);
      sheets.forEach((s, i) => s.classList.toggle('on', i === k));
      if (ready.has(sheet)) tell(sheet, 'seek', seconds);
    };
    const load = () => {
      if (asked) return;
      asked = true;
      for (const sheet of sheets) {
        sheet.addEventListener('load', () => {
          ready.add(sheet);
          tell(sheet, 'seek', 0);
          render(at);
        });
        sheet.src = sheet.dataset.src;
      }
    };
    return {
      load,
      render,
      refit: () => {},
      when: (pp) => {
        const { sheet, seconds } = where(pp);
        return `${sheet.dataset.station} · ${Math.round(seconds)} s`;
      },
      marks: sheets.map((s, i) => [s.dataset.station, i / sheets.length]),
      state: () => ({ sheets: sheets.length, come: ready.size }),
    };
  }

  // ---- the scenes, and the one thing that moves them -----------------------------------------------------------
  const kinds = { frames, factory };
  const scenes = $$('.scene').map((el) => {
    const scene = { el, pp: -1, ...kinds[el.dataset.scene](el) };
    scene.notes = $$('[data-from]', el).map((p) => [p, Number(p.dataset.from), Number(p.dataset.to)]);
    scene.rail = $('.rail', el);
    scene.ticks = scene.marks.map(([name, x]) => {
      const li = document.createElement('li');
      li.textContent = name;
      li.style.left = `${(x * 100).toFixed(2)}%`;
      li.classList.toggle('late', x > 0.7); // named to the left of its tick, so the name stays on the rail
      $('ol', scene.rail).append(li);
      return [li, x];
    });
    return scene;
  });

  const clock = $('#clock');
  const what = $('#clock-what');
  const when = $('#clock-when');

  let waiting = false;
  const ask = () => {
    if (waiting) return;
    waiting = true;
    requestAnimationFrame(move);
  };
  function move() {
    waiting = false;
    const vh = innerHeight;
    let pinned = null;
    for (const scene of scenes) {
      const r = scene.el.getBoundingClientRect();
      if (r.top < vh * 2.5 && r.bottom > -vh) scene.load();
      if (r.top >= vh || r.bottom <= 0) continue;
      const p = clamp(-r.top / (r.height - vh));
      const pp = clamp((p - LEAD) / (1 - LEAD - TAIL));
      if (r.top <= 1 && r.bottom >= vh - 1) pinned = scene;
      if (pp === scene.pp) continue;
      scene.pp = pp;
      scene.render(pp);
      for (const [note, from, to] of scene.notes) note.classList.toggle('on', pp >= from && pp < to);
      scene.rail.style.setProperty('--p', pp.toFixed(4));
      const now = scene.ticks.filter(([, x]) => x <= pp + 0.0005).at(-1);
      for (const tick of scene.ticks) tick[0].classList.toggle('on', tick === now);
    }
    clock.hidden = !pinned;
    if (pinned) {
      what.textContent = pinned.el.dataset.what;
      when.textContent = pinned.when(pinned.pp);
    }
  }
  addEventListener('scroll', ask, { passive: true });
  addEventListener('resize', () => { for (const scene of scenes) scene.refit(); ask(); });
  narrow.addEventListener('change', () => { for (const scene of scenes) scene.refit(); });

  // ---- the rest of the page: pictures are asked for as they come near, and words rise as they are reached ---------
  const near = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.src = entry.target.dataset.src;
      near.unobserve(entry.target);
    }
  }, { rootMargin: '900px 0px' });
  for (const picture of $$('img[data-src]')) near.observe(picture);

  const reached = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('in');
      reached.unobserve(entry.target);
    }
  }, { threshold: 0.18 });
  for (const words of $$('.reveal')) reached.observe(words);

  // the line plays by itself while it is in sight, and rests when it is not
  for (const sheet of $$('iframe[data-factory]')) {
    let come = false;
    let seen = false;
    const play = () => { if (come) { tell(sheet, 'setActive', seen); tell(sheet, seen ? 'play' : 'pause'); } };
    sheet.addEventListener('load', () => { come = true; play(); });
    new IntersectionObserver(([entry]) => {
      seen = entry.isIntersecting;
      if (seen && !sheet.src) sheet.src = sheet.dataset.src;
      play();
    }, { rootMargin: '300px 0px' }).observe(sheet);
  }

  window.BOWER_SITE = { state: () => scenes.map((s) => ({ id: s.el.id, at: s.pp, ...s.state() })) };
  move();
})();

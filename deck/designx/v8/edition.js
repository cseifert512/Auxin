/* Edition 08: edition 07 with the drawings in.
   Nothing of 07 is taken out. Where 07 keeps a note for a drawing, the drawing made for that place is set in;
   a drawing that has no place in 07 has a slide of its own, straight after the slide it answers.

   The drawings are the pieces made in drawings-in-code (exports/deck/<name>/): each is a page of its own that
   plays by itself and shows only pictures made beforehand. They are read from pieces/<name>/, which the deck's
   server takes from where they are made. This file sets them into slides and tells each one when its slide
   comes and goes. It draws nothing itself. */
(() => {
  'use strict';
  const slides = window.DESIGNX_SLIDES;
  const at = (theme) => slides.findIndex((slide) => slide.theme.split(' ')[0] === theme);
  const piece = (name, kind, title, query = '') => `<iframe class="v8-piece" data-v8-piece="${kind}" data-src="pieces/${name}/index.html?embed${query}" title="${title}" tabindex="-1"></iframe>`;
  const edit = (slide, change) => {
    const template = document.createElement('template');
    template.innerHTML = slide.html;
    change(template.content);
    return { ...slide, html: template.innerHTML };
  };
  const scenario = 'A growth scenario on stated assumptions, not a forecast.';
  const concept = 'Concept geometry; trial planting.';
  const source = 'Growth studies of one six-bay room, November 2026: pictures made beforehand from a planting grown in simulation. Most of the simulator’s plant numbers are labelled assumptions; nothing here is a structural, fabrication or horticultural check.';

  // ---- the room through time: the only thing on its slide, from one view, straight after the cover ---------------
  // It is the one piece that is drawn live (drawings-in-code, npm run live): turned by hand, played and scrubbed.
  const cover = at('cover');
  slides.splice(cover + 1, 0, {
    ...slides[at('v7-growth-slide')],
    title: 'A room through time',
    theme: 'v8-room-slide',
    html: `<section class="v7-scene v8-sheet v8-room">${piece('a-room-through-time', 'live', 'A room through time: one room on the approach, from its design to an established planting', '&paper=EEF3EA&ink=102820&view=approach&play')}<img class="v8-poster" data-src="pieces/a-room-through-time/poster.webp" alt="The room on the approach, established, in summer."><p class="v7-status">${scenario} ${concept}</p></section>`,
    notes: 'One Bower, from one place, along one line of time: the design, assembly member by member, planting, establishment season by season, and a year of seasons. It is drawn as it is shown, so it can be turned by hand, played and scrubbed. The planting is divided by pier and tended; the plants go in as grown specimens. This is a growth scenario on stated assumptions, not a forecast. Do not assign a fixed year or guaranteed coverage. The engineered timber frame carries the structural loads; planting colonises it.',
    source,
  });

  // ---- Plants make space: the piece made for that space, with a mode for each of the slide's tabs -------
  const modes = ['space', 'light', 'time'];
  const growth = at('v7-growth-slide');
  slides[growth] = edit(slides[growth], (content) => {
    const space = content.querySelector('.v7-drawing-space');
    space.classList.add('v8-placed');
    space.insertAdjacentHTML('afterbegin', `${piece('04-plants-make-space-timber', 'player', 'One room: unrolled, the light on its floor, and through time', '&mode=space')}<img class="v8-poster" data-src="pieces/04-plants-make-space-timber/poster-space.png" alt="The room unrolled, established and in leaf.">`);
    content.querySelector('.v7-status').textContent = `Architectural intentions. ${scenario} ${concept}`;
  });

  // ---- slide 5, Growth changes the geometry: the plate made for its first tab ------------------------------------
  const anatomy = at('v7-anatomy-slide');
  slides[anatomy] = edit(slides[anatomy], (content) => {
    const space = content.querySelector('.v7-anatomy-drawing');
    space.classList.add('v8-placed');
    space.insertAdjacentHTML('afterbegin', '<img class="v8-plate" src="pieces/05-shaded-room-timber.webp" alt="The shade wanted on the floor of the room, the ways up from the soil at each pier, and one pier with its training lines." loading="lazy">');
  });

  // ---- drawings with no place in 07: a slide each ----------------------------------------------------------------
  const sheet = (name, kind, title, statement) => `<section class="v7-scene v8-sheet v8-${kind}">${piece(name, kind, title)}<p class="v7-status">${statement}</p></section>`;

  // two findings from growing a planting on the room, each in the steps slide 5 sets out, after slide 5
  slides.splice(anatomy + 1, 0, {
    ...slides[anatomy],
    title: 'The plants were shading each other',
    theme: 'v8-vignette-slide',
    html: sheet('shaded-at-the-pier', 'vignette', 'The plants were shading each other: the room and one pier of it', `${scenario} The light model is provisional. ${concept}`),
    notes: 'The first of two worked examples of the relationship on the slide before, in the same steps: we want, we ask, we reconsider, we ask again. The room and one pier of it. The planting grows for five tended years on the room as it was drawn; the piers are marked, where each plant stands in the shade of its neighbours and of the timber; the piers open, and the way through each bay narrows; and the same planting grows for the same five years on the opened room. It plays by itself; the steps under it can be chosen. This is a growth scenario on stated assumptions, not a forecast, and the light model is provisional.',
    source,
  }, {
    ...slides[anatomy],
    title: 'The clinging plants found the joints',
    theme: 'v8-vignette-slide',
    html: sheet('found-the-joints', 'vignette', 'The clinging plants found the joints: the room and one patch of its roof', `${scenario} The cut is set out, not proved. ${concept}`),
    notes: 'The second worked example, addressed to single joints. The room and one patch of its roof, looked at squarely from outside. The planting grows for ten tended years; the joints the clinging plants reach are marked as they are reached; the lap is shown cut through, with a stem going into the gap beside the crossing member and thickening; then the same patch of roof as it is now cut, bare and with the ivy on it; and last which joints are reached in every run and which only in some. That a stem in a gap wedges it is taken from what clinging plants are known to do to fences and cladding; the simulator does not show it. The splayed lap is set out and cut in the model, not proved: its sizes are provisional and nobody has checked what it does to the strength of the lap.',
    source,
  });

  // the same pier grown three times, after the slide that sets making beside growing
  const computation = at('v7-computation-slide');
  slides.splice(computation + 1, 0, {
    ...slides[computation],
    title: 'Grown again',
    theme: 'v8-again-slide',
    html: sheet('06-grown-again', 'again', 'The same pier grown three times: what is the same every time, and what is not', `${scenario} ${concept}`),
    notes: 'One pier of the room on one summer day, from three grown runs of the same planting on the same building with the same care, differing only in the simulator’s chance. Shown one after another, then together: what is the same in all three in ink, what is not in red. Beneath, the scale from decided by us to decided by the plant, with a bar wherever this picture can measure it: of what is drawn in each marked place, the share that differs between the three. The measure is of these pictures, not of plants: it says how far three runs of one scenario agree, on the simulator’s assumptions. This drawing was made for the slide before it, in place of the two checks side by side; here it follows that slide and replaces nothing.',
    source,
  });

  window.DESIGNX_META = Object.freeze({ ...window.DESIGNX_META, edition: 8, targetSlideCount: slides.length });

  (window.DESIGNX_MOUNTS ||= []).push((root) => {
    const printing = document.body.classList.contains('print-mode');
    const frames = [...root.querySelectorAll('iframe[data-v8-piece]')];
    const kind = (frame) => frame.dataset.v8Piece;
    const say = (frame, type, value) => frame.contentWindow?.postMessage({ type, value }, '*');
    const inside = (frame) => { try { return frame.contentWindow; } catch { return null; } };

    // what each kind of piece is told when its slide comes, when it goes, and when the deck is laid out for paper.
    // Like the factory drawings, a piece starts again from its beginning each time its slide is shown.
    const begin = {
      player: (frame) => { if (frame.dataset.v8Mode) say(frame, 'bower:mode', frame.dataset.v8Mode); say(frame, 'bower:play', true); },
      vignette: (frame) => { inside(frame)?.__setT?.(0); inside(frame)?.__play?.(); },
      again: (frame) => { say(frame, 'bower:step', 0); say(frame, 'bower:play', true); },
      live: () => {},
    };
    const rest = {
      player: (frame) => say(frame, 'bower:play', false),
      vignette: (frame) => inside(frame)?.__setT?.(0),
      again: (frame) => say(frame, 'bower:play', false),
      live: (frame) => { frame.removeAttribute('src'); delete frame.dataset.v8Asked; come.delete(frame); },
    };
    const still = {
      player: () => {},
      live: () => {},
      again: () => {}, // asked for with ?print, which shows its last step
      vignette: (frame) => {
        // its last moment, once its pictures have come
        const tries = setInterval(() => {
          const w = inside(frame);
          if (!w?.__ready) return;
          clearInterval(tries);
          w.__setT(w.__duration - 0.05);
        }, 200);
        setTimeout(() => clearInterval(tries), 20000);
      },
    };

    const shown = new Set();
    const come = new Set();
    const ask = (frame) => {
      if (frame.dataset.v8Asked || (printing && (kind(frame) === 'player' || kind(frame) === 'live'))) return;
      frame.dataset.v8Asked = 'yes';
      frame.src = frame.dataset.src + (printing ? '&print' : '');
    };
    // a piece is a page of its own, so keys and the wheel over it would stop there: pass on the ones the deck uses,
    // unless the piece has used them itself
    const pass = new Set(['ArrowRight', 'ArrowLeft', 'PageDown', 'PageUp', 'Home', 'End', 'g', 'G', 'n', 'N', 'f', 'F']);
    for (const frame of frames) {
      frame.addEventListener('load', () => {
        if (!frame.dataset.v8Asked) return;
        come.add(frame);
        const w = inside(frame);
        if (w) {
          w.addEventListener('keydown', (event) => {
            if (event.defaultPrevented || !pass.has(event.key)) return;
            document.dispatchEvent(new KeyboardEvent('keydown', { key: event.key, code: event.code, bubbles: true, cancelable: true }));
          });
          if (kind(frame) !== 'live') w.addEventListener('wheel', (event) => {
            root.dispatchEvent(new WheelEvent('wheel', { deltaX: event.deltaX, deltaY: event.deltaY, deltaMode: event.deltaMode, bubbles: true, cancelable: true }));
          }, { passive: true });
        }
        if (printing) still[kind(frame)](frame);
        else (shown.has(frame) ? begin : rest)[kind(frame)](frame);
      });
    }
    document.addEventListener('designx:slidechange', (event) => {
      for (const frame of frames) {
        const here = printing || event.detail.element.contains(frame);
        if (here === shown.has(frame) && frame.dataset.v8Asked) continue;
        if (here) { shown.add(frame); ask(frame); } else shown.delete(frame);
        if (!printing && (come.has(frame) || kind(frame) === 'live')) (here ? begin : rest)[kind(frame)](frame);
      }
    });

    // Plants make space: each tab is a mode of the piece. It opens on Space, as 07 does; Time has the slide before it.
    const growthScene = root.querySelector('[data-v7-scene="growth"]');
    const player = growthScene.querySelector('iframe[data-v8-piece="player"]');
    const poster = growthScene.querySelector('.v8-poster');
    growthScene.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-v7-growth]');
      if (!button) return;
      const mode = modes[Number(button.dataset.v7Growth)];
      player.dataset.v8Mode = mode;
      if (come.has(player)) say(player, 'bower:mode', mode);
      if (printing) poster.src = poster.dataset.src.replace('poster-space', `poster-${mode}`);
    });
    if (printing) for (const still of root.querySelectorAll('.v8-poster')) still.src = still.dataset.src;

    // slide 5: the plate is the drawing for Shaded room; the other two tabs keep 07's note until theirs are made
    const anatomyScene = root.querySelector('[data-v7-scene="anatomy"]');
    const slot = anatomyScene.querySelector('.v7-anatomy-drawing');
    anatomyScene.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-v7-intent]');
      if (button) slot.classList.toggle('v8-placed', button.dataset.v7Intent === '0');
    });

    const seventh = document.querySelector('[data-edition-seven]');
    document.addEventListener('designx:slidechange', (event) => {
      seventh.hash = `slide-${String(window.DESIGNX_SLIDES[event.detail.index].comparisonIndex + 1).padStart(2, '0')}`;
    });
  });
})();

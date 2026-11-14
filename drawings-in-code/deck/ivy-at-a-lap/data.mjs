// What the drawing of one lap is drawn from: the two members as Blender mills them, as every lap is cut and as
// this one is now cut; the run of each member's centre line by the joint; the room's centre lines, for coming
// in from the whole building and going back out to it; and the laps that are cut this way.
// Reads three files made beside the sketches (see README, sketches): joint-detail.js
// (bower-blender/scripts/joint_detail.py), reached-joints.js (joints.mjs) and states.js
// (bower-blender/scripts/sweep_states.py). Nothing here is typed in by hand.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const made = (file, start) => {
  if (!existsSync(file)) throw new Error(`${file} is not there: make it first (drawings-in-code/README.md, under sketches)`);
  return JSON.parse(readFileSync(file, 'utf8').replace(start, '').replace(/;\s*$/, ''));
};

export default function gather(root) {
  const J = made(resolve(root, 'sketches/design-space/joint-detail.js'), /^window\.JOINT_DETAIL = /);
  const R = made(resolve(root, 'sketches/design-space/reached-joints.js'), /^window\.REACHED = /);
  const S = made(resolve(root, 'sketches/design-space/states.js'), /^window\.DESIGN_SPACE = /);
  if (J.joint !== R.close.joint.id) throw new Error(`joint-detail.js is of ${J.joint}, and the joint drawn close to is ${R.close.joint.id}`);
  const m = (p) => p.map((v) => v / 1000);
  const was = J.variants.as_drawn, now = J.variants.now;
  // the member notched on its outer face takes the other one in: that other one is the one a stem runs along into the gap
  const under = was.cuts.find((c) => c.face === 'outer').member, over = was.cuts.find((c) => c.member !== under).member;
  const run = (id) => { const piece = R.close.a.id === id ? R.close.a : R.close.b; return { id, family: piece.family, widthM: piece.widthM, depthM: piece.depthM, frames: piece.frames.map((f) => ({ p: m(f.p), d: f.d })) }; };
  const mesh = (variant) => Object.fromEntries([under, over].map((id) => [id === under ? 'under' : 'over', { verts: variant.pieces[id].verts_m, faces: variant.pieces[id].faces }]));
  const base = S.sweeps[0], N = S.points;
  const lines = base.states[0].has.map((mi, j) => ({ closed: base.members[mi].closed, wide: base.members[mi].width_m, mm: base.states[0].mm.slice(j * N * 3, (j + 1) * N * 3) }));
  // the laps that are cut splayed: every cross lap a clinging plant reached in any run
  const cut = new Map();
  for (const place of Object.values(R.places)) for (const j of place.milled) if (j.kind === 'cross_lap') cut.set(j.id, m(place.at));
  return {
    at: was.at_m,
    under: run(under),
    over: run(over),
    was: mesh(was),
    now: mesh(now),
    gapM: was.clearance_m,
    closeM: now.clearance_m,
    landM: now.detail.land_m,
    mouthM: now.detail.mouth_m,
    lapDepthM: was.cuts[0].depth_m,
    room: { points: N, lines },
    cut: [...cut.values()],
    laps: R.kinds.cross_lap,
    joints: R.joints,
  };
}

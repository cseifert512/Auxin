// What the joints drawing says in numbers and places, worked out from the grown runs.
// Reads two files made beside the sketches (see README, sketches): reached-joints.js (joints.mjs) and
// joint-detail.js (bower-blender/scripts/joint_detail.py). Nothing here is typed in by hand.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const made = (file, global) => {
  if (!existsSync(file)) throw new Error(`${file} is not there: make it first (drawings-in-code/README.md, under sketches)`);
  return JSON.parse(readFileSync(file, 'utf8').replace(new RegExp(`^window\\.${global} = `), '').replace(/;\s*$/, ''));
};

export default function gather(root) {
  const R = made(resolve(root, 'sketches/design-space/reached-joints.js'), 'REACHED');
  const J = made(resolve(root, 'sketches/design-space/joint-detail.js'), 'JOINT_DETAIL');
  const run = R.runs[0], m = (p) => p.map((v) => v / 1000);
  const milled = (nodes) => new Set(nodes.flatMap((node) => R.places[node].milled.map((j) => j.id))).size;
  const joints = Object.entries(R.places).filter(([, p]) => p.milled.length).map(([node, p]) => ({
    at: m(p.at),
    day: run.reached.find((x) => x.node === node)?.day ?? null,
    inRun: run.reached.some((x) => x.node === node),
    always: R.always.includes(node),
  }));
  // how many milled joints have been reached by each day of the run that is drawn
  const order = run.reached.filter((x) => x.day != null && R.places[x.node].milled.length).sort((a, b) => a.day - b.day);
  const count = order.map((x, i) => ({ day: x.day, n: milled(order.slice(0, i + 1).map((y) => y.node)) }));
  const ever = new Map(Object.values(R.places).flatMap((p) => p.milled.map((j) => [j.id, j.kind])));
  const laps = [...ever.values()].filter((kind) => kind === 'cross_lap').length;
  const was = J.variants.as_drawn, now = J.variants.now;
  const notched = was.cuts.find((c) => c.face === 'outer').member;
  const wide = (id) => (R.close.a.id === id ? R.close.a.widthM : R.close.b.widthM);
  return {
    points: { joints: joints.map((j) => j.at), joint: m(R.close.at) },
    total: R.joints,
    lastDay: run.lastDay,
    joints: joints.map(({ day, inRun, always }) => ({ day, inRun, always })),
    count,
    inRun: milled(run.reached.map((x) => x.node)),
    always: R.milledAlways,
    sometimes: R.milledEver - R.milledAlways,
    laps,
    others: ever.size - laps,
    leftOut: run.reached.filter((x) => !R.places[x.node].milled.length).length,
    close: { day: R.close.day, who: R.close.plants.map((id) => run.labels[id]).join(' and '), kind: R.close.joint.kind },
    section: { wA: wide(notched), wB: wide(was.cuts.find((c) => c.member !== notched).member), phi: R.close.angleDeg * Math.PI / 180, c0: was.clearance_m, c1: now.clearance_m, land: now.detail.land_m, mouth: now.detail.mouth_m, depth: was.cuts[0].depth_m },
    runs: R.runs.map((r) => ({ seed: r.seed, simulator: r.simulator, care: r.care, years: r.years, specimenM: r.specimenM })),
    clingers: [...new Set(run.reached.flatMap((x) => x.plants).map((id) => run.labels[id]))],
    statement: run.statement,
  };
}

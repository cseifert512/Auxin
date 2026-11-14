// The timber as solids, for asking where a point stands in relation to it.
//
// Each member is taken as its section swept along its centre line, turned as the snapshot says it is turned. The
// laps and housings milled into it are not taken out, so a point in a notch counts as inside the timber: a small
// over-count, on the safe side for keeping plants out of the wood.

export const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
export const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
export const mul = (a, k) => [a[0] * k, a[1] * k, a[2] * k];
export const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
export const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
export const len = (a) => Math.hypot(a[0], a[1], a[2]);
export const unit = (a) => {
  const l = len(a);
  return l > 1e-12 ? mul(a, 1 / l) : [0, 0, 0];
};
export const reject = (v, t) => sub(v, mul(t, dot(v, t)));
export const lerp = (a, b, u) => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];

const CELL = 0.5;

/** Every stretch of every member between two samples of its centre line, with the frame of its section there. */
export function segmentsOf(centrelines) {
  const segments = [];
  centrelines.members.forEach((m, member) => {
    for (let i = 0; i + 1 < m.points_m.length; i++) {
      const a = m.points_m[i];
      const ab = sub(m.points_m[i + 1], a);
      const l = len(ab);
      if (l < 1e-9) continue;
      const t = mul(ab, 1 / l);
      const deep = unit(reject(lerp(m.depth_axes[i], m.depth_axes[i + 1], 0.5), t));
      segments.push({ member, id: m.id, family: m.family, a, ab, l, t, deep, wide: cross(deep, t), axis0: m.depth_axes[i], axis1: m.depth_axes[i + 1], halfW: m.width_m / 2, halfD: m.depth_m / 2 });
    }
  });
  return segments;
}

/** A way to get the segments near a point without looking at all of them. */
export function gridOf(segments, reachM = 0.05) {
  const grid = new Map();
  const key = (x, y, z) => `${x},${y},${z}`;
  segments.forEach((s, index) => {
    const b = add(s.a, s.ab);
    const reach = Math.hypot(s.halfW, s.halfD) + reachM;
    const lo = [0, 1, 2].map((k) => Math.floor((Math.min(s.a[k], b[k]) - reach) / CELL));
    const hi = [0, 1, 2].map((k) => Math.floor((Math.max(s.a[k], b[k]) + reach) / CELL));
    for (let x = lo[0]; x <= hi[0]; x++) for (let y = lo[1]; y <= hi[1]; y++) for (let z = lo[2]; z <= hi[2]; z++) {
      const k = key(x, y, z);
      if (!grid.has(k)) grid.set(k, []);
      grid.get(k).push(index);
    }
  });
  return (p) => grid.get(key(Math.floor(p[0] / CELL), Math.floor(p[1] / CELL), Math.floor(p[2] / CELL))) ?? [];
}

/**
 * Where a point stands against one stretch of timber. `inside` is how far in it is from the nearest face
 * (negative: outside, by about that much); `out` is the way straight out through that face, and `on` the point
 * on it. Null if the point is beyond either end of the stretch.
 */
export function against(p, s, endSlack = 0.005) {
  const r = sub(p, s.a);
  const along = dot(r, s.t);
  if (along < -endSlack || along > s.l + endSlack) return null;
  const x = dot(r, s.wide);
  const y = dot(r, s.deep);
  const dx = s.halfW - Math.abs(x);
  const dy = s.halfD - Math.abs(y);
  const byWidth = dx < dy;
  const out = byWidth ? mul(s.wide, x < 0 ? -1 : 1) : mul(s.deep, y < 0 ? -1 : 1);
  const inside = Math.min(dx, dy);
  return { inside, out, on: add(p, mul(out, inside)) };
}

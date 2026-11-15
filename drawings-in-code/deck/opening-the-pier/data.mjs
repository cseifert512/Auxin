// What "Opening the pier" is drawn from.
//   bower-blender/studies/inhabited-room/ground/openings.json (study_openings.py; its header says where each field
//     comes from): for every opening of the pier, the room's members (the same ids and the same 16 places along
//     each, so the page can interpolate point for point), where each climber is planted, the way in, the
//     simulator's hours of June sun at each planting place, the sole under the pier in focus, and the footing
//     draft's review of the piles.
//   scenes/<snapshot>/bower-place.json for each opening: the members, cables, planting stations and site exactly as
//     the growth simulator was handed them. From these, at gather time, this works out for each climber and each
//     20 minute step of the sun on 15 June (the day the simulator reads June on) how much of the beam reaches the
//     place the simulator reads light at, the way the simulator's light model does it
//     (Horti-code-ture/packages/core/src/light/exposure.ts: the sky in 72 x 24 equal patches, each member a strip
//     of the round bar of equal girth, walls solid, deciduous crowns in leaf passing 3.3%). It leaves out one thing
//     the simulator counts: the leaf the other climbers carried the season before. So these rays show more sun than
//     the simulator's hours; the hours shown as numbers are the simulator's own.
// Rounded to millimetres. Nothing here is typed in by hand.
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const mm = (v) => Math.round(v * 1000);
const r3 = (v) => Math.round(v * 1000) / 1000;
const RAD = Math.PI / 180;

/** z = a + b x + c y through points [x, y, z], by least squares. */
function plane(points) {
  const n = points.length;
  let sx = 0, sy = 0, sz = 0, sxx = 0, syy = 0, sxy = 0, sxz = 0, syz = 0;
  for (const [x, y, z] of points) { sx += x; sy += y; sz += z; sxx += x * x; syy += y * y; sxy += x * y; sxz += x * z; syz += y * z; }
  const m = [[n, sx, sy], [sx, sxx, sxy], [sy, sxy, syy]], v = [sz, sxz, syz];
  const det = (a) => a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1]) - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0]) + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]);
  const d = det(m);
  return [0, 1, 2].map((k) => Math.round(det(m.map((row, i) => row.map((x, j) => (j === k ? v[i] : x)))) / d * 1e6) / 1e6);
}

// ---- the simulator's sky map, ported (exposure.ts, sun.ts): only what June's direct sun needs ----
const SKY_AZ = 72, SKY_EL = 24, CELLS = SKY_AZ * SKY_EL, CELL_SR = (2 * Math.PI) / CELLS, CELL_ANGLE = 0.05, TWO_PI = 2 * Math.PI;
const IN_LEAF = 0.033, MAP_DOY = 172, STEP_MIN = 20, CELL_M = 0.2, MAP_Z = 0.05;   // 21 June; a grass-high point every 20 cm   // light/model.ts, light/site.ts, light/sun.ts
const cellOf = (dx, dy, dz) => { const a = Math.floor(((Math.atan2(dx, dy) + Math.PI) / TWO_PI) * SKY_AZ), e = Math.floor(dz * SKY_EL); return (e >= SKY_EL ? SKY_EL - 1 : e) * SKY_AZ + (a >= SKY_AZ ? SKY_AZ - 1 : a); };
const cellDir = (c) => { const e = Math.floor(c / SKY_AZ), a = c % SKY_AZ, z = (e + 0.5) / SKY_EL, f = Math.sqrt(1 - z * z), az = ((a + 0.5) / SKY_AZ) * TWO_PI - Math.PI; return [f * Math.sin(az), f * Math.cos(az), z]; };
function stripInto(into, p, a, b, width) {
  const [px, py, pz] = p, sx = b[0] - a[0], sy = b[1] - a[1], sz = b[2] - a[2], len = Math.hypot(sx, sy, sz);
  if (len < 1e-6) return;
  const ux = sx / len, uy = sy / len, uz = sz / len;
  const along = Math.min(len, Math.max(0, (px - a[0]) * ux + (py - a[1]) * uy + (pz - a[2]) * uz));
  const near = Math.hypot(a[0] + ux * along - px, a[1] + uy * along - py, a[2] + uz * along - pz);
  if (Math.max(a[2], b[2]) < pz - width && near > 2 * width) return;
  const pieces = Math.min(96, Math.max(1, Math.ceil(len / (CELL_ANGLE * Math.max(near, 0.05))))), piece = len / pieces;
  for (let i = 0; i < pieces; i++) {
    const t = (i + 0.5) * piece, qx = a[0] + ux * t - px, qy = a[1] + uy * t - py, qz = a[2] + uz * t - pz, d = Math.hypot(qx, qy, qz);
    if (d < 0.02) continue;
    const dx = qx / d, dy = qy / d, dz = qz / d, cos = dx * ux + dy * uy + dz * uz, sin = Math.sqrt(Math.max(0, 1 - cos * cos));
    const omega = (width * piece * sin) / (d * d) / CELL_SR, across = Math.min(24, Math.max(1, Math.ceil(width / d / CELL_ANGLE)));
    if (across === 1) { if (dz > 0) into[cellOf(dx, dy, dz)] += omega; continue; }
    let wx = uy * dz - uz * dy, wy = uz * dx - ux * dz, wz = ux * dy - uy * dx; const wl = Math.hypot(wx, wy, wz);
    if (wl < 1e-9) continue;
    wx /= wl; wy /= wl; wz /= wl;
    for (let k = 0; k < across; k++) {
      const off = ((k + 0.5) / across - 0.5) * width, rx = qx + wx * off, ry = qy + wy * off, rz = qz + wz * off;
      if (rz <= 0) continue;
      const rd = Math.hypot(rx, ry, rz); into[cellOf(rx / rd, ry / rd, rz / rd)] += omega / across;
    }
  }
}
function resample(pts, step = 0.6) {   // Polyline.pointAt at equal lengths: strips no longer than 0.6 m
  const L = [0]; for (let i = 1; i < pts.length; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1], pts[i][2] - pts[i - 1][2]));
  const len = L.at(-1), n = Math.max(1, Math.ceil(len / step)), out = [];
  for (let k = 0; k <= n; k++) { const s = len * k / n; let i = 1; while (i < pts.length - 1 && L[i] < s) i++; const f = (s - L[i - 1]) / ((L[i] - L[i - 1]) || 1); out.push([0, 1, 2].map((c) => pts[i - 1][c] + (pts[i][c] - pts[i - 1][c]) * f)); }
  return out;
}
function hitsWall(q, p, d) { const ex = q.to[0] - q.from[0], ey = q.to[1] - q.from[1], den = -ey * d[0] + ex * d[1]; if (Math.abs(den) < 1e-12) return false; const t = (-ey * (q.from[0] - p[0]) + ex * (q.from[1] - p[1])) / den; if (t <= 1e-6) return false; const z = p[2] + d[2] * t; if (z < 0 || z > q.heightM) return false; const al = ((p[0] + d[0] * t - q.from[0]) * ex + (p[1] + d[1] * t - q.from[1]) * ey) / (ex * ex + ey * ey); return al >= 0 && al <= 1; }
function hitsCrown(o, p, d) { const stem = o.clearStemM ?? o.heightM / 3, cz = (stem + o.heightM) / 2, rz = (o.heightM - stem) / 2, k = o.crownRadiusM / rz; const ox = p[0] - o.at[0], oy = p[1] - o.at[1], oz = (p[2] - cz) * k, ez = d[2] * k; const a = d[0] ** 2 + d[1] ** 2 + ez * ez, b = ox * d[0] + oy * d[1] + oz * ez, cc = ox * ox + oy * oy + oz * oz - o.crownRadiusM ** 2; if (cc <= 0) return true; const disc = b * b - a * cc; return disc > 0 && -b - Math.sqrt(disc) > 0; }
/** The sun's path on a day, in equal steps from sunrise to sunset, turned into the drawing's frame (sun.ts sunPath). */
function sunPath(lat, bearing, doy) {
  const dec = 23.44 * RAD * Math.sin(2 * Math.PI * (284 + doy) / 365), half = Math.acos(-Math.tan(lat * RAD) * Math.tan(dec)) / (15 * RAD), rise = 12 - half;
  const n = Math.round(2 * half * 60 / STEP_MIN), step = 2 * half / n, out = [];
  for (let i = 0; i < n; i++) {
    const hour = rise + (i + 0.5) * step, h = (hour - 12) * 15 * RAD, la = lat * RAD;
    const east = -Math.cos(dec) * Math.sin(h), north = Math.cos(la) * Math.sin(dec) - Math.sin(la) * Math.cos(dec) * Math.cos(h), up = Math.sin(la) * Math.sin(dec) + Math.cos(la) * Math.cos(dec) * Math.cos(h);
    if (up <= 0) continue;
    const turned = Math.atan2(east, north) - bearing * RAD, flat = Math.hypot(east, north);
    out.push({ hour, step, dir: [flat * Math.sin(turned), flat * Math.cos(turned), up] });
  }
  return out;
}
/** The strips the simulator makes of a scene's members and cables, and its walls and crowns. */
function occluders(place) {
  const strips = [];
  for (const m of place.members) { const w = (m.section.shape === 'round' ? m.section.diameterMm : 2 * (m.section.widthMm + m.section.depthMm) / Math.PI) / 1000, r = resample(m.points); for (let i = 1; i < r.length; i++) strips.push([r[i - 1], r[i], w]); }
  for (const c of place.cables ?? []) { const r = resample(c.points); for (let i = 1; i < r.length; i++) strips.push([r[i - 1], r[i], c.diameterMm / 1000]); }
  return { strips, obs: place.site?.obstructions ?? [] };
}
/** Hours of direct sun at a point on a day: the share of the beam that gets through at each step, by the step's length. */
function hoursAt(occ, p, path) {
  const s = new Float32Array(CELLS);
  for (const [a, b, w] of occ.strips) stripInto(s, p, a, b, w);
  let h = 0;
  for (const sun of path) {
    const c = cellOf(...sun.dir), d = cellDir(c);
    let hidden = Math.min(1, s[c]), tree = false;
    for (const o of occ.obs) if (o.kind === 'wall' && hitsWall(o, p, d)) hidden = 1;
    if (hidden < 1) for (const o of occ.obs) if (o.kind === 'tree' && hitsCrown(o, p, d)) { if (o.leafHabit === 'deciduous') tree = true; else hidden = 1 - (1 - hidden) * (1 - IN_LEAF); }
    h += (1 - Math.round(255 * hidden) / 255) * (tree ? IN_LEAF : 1) * sun.step;
  }
  return h;
}

export default function gather(root) {
  const file = resolve(root, '../bower-blender/studies/inhabited-room/ground/openings.json');
  if (!existsSync(file)) throw new Error(`${file} is not there: make it with python study_openings.py (bower-blender/studies/inhabited-room)`);
  const O = JSON.parse(readFileSync(file, 'utf8'));
  const list = [...O.openings].sort((a, b) => a.ring_radius_m - b.ring_radius_m);
  if (list.length < 2) throw new Error(`openings.json has ${list.length} opening: the drawing needs at least two`);
  const first = list[0];
  const members = first.members.map((m) => ({ id: m.id, family: m.family, w: mm(m.w) }));
  const plants = first.plants.map((p) => ({ id: p.id, pier: p.pier, taxon: p.taxon }));
  const centre = (feet) => { const c = feet.flatMap((f) => f.corners); return [c.reduce((s, p) => s + p[0], 0) / c.length, c.reduce((s, p) => s + p[1], 0) / c.length]; };
  const piers = Object.fromEntries(Object.entries(first.feet).map(([id, feet]) => [id, centre(feet).map(r3)]));
  for (const o of list) {
    const ids = new Set(o.members.map((m) => m.id));
    for (const m of members) if (!ids.has(m.id)) throw new Error(`member ${m.id} is missing at ring ${o.ring_radius_m} m`);
  }
  const sunOf = (o, id) => o.sun.stations[id] ?? o.sun.stations[id.replace('climber.', 'bed.')];
  const chosen = list.reduce((best, o, i) => (Math.abs(o.ring_radius_m - O.chosen_ring_radius_m) < Math.abs(list[best].ring_radius_m - O.chosen_ring_radius_m) ? i : best), 0);
  // the bay in view: the one whose two piers' climbers gain most sun between the tightest opening and the chosen one
  const gain = {};
  for (const p of plants) gain[p.pier] = (gain[p.pier] ?? 0) + sunOf(list[chosen], p.id).june_h - sunOf(first, p.id).june_h;
  const bays = [...new Set(first.members.map((m) => m.id.match(/^R1\.(B\d)\./)?.[1]).filter(Boolean))];
  const pierIds = Object.keys(piers).sort(), bayPiers = (b) => { const n = Number(b.slice(1)); return [pierIds[(n - 1) % pierIds.length], pierIds[n % pierIds.length]]; };
  const bay = bays.sort((a, b) => bayPiers(b).reduce((s, p) => s + gain[p], 0) - bayPiers(a).reduce((s, p) => s + gain[p], 0))[0];
  const [pierA, pierB] = bayPiers(bay);
  // the gap between the two piers in view. The way in is measured in the entry bay; here the bay's innermost hoop
  // stands on feet exactly as far apart as the entry bay's (checked, to a centimetre), so the gap is the same figure,
  // drawn between the hoop's feet drawn in by the same margin as openings.json's way-in points sit inside the entry's.
  const entry = O.site.entry_bay?.split('.')[1] ?? 'B3';
  const gapOf = (o) => {
    const feet = (b) => { const h = o.members.find((m) => m.id === `R1.${b}.hoop0`).pts; return [h[0], h.at(-1)]; };
    const span = ([a, b]) => Math.hypot(a[0] - b[0], a[1] - b[1]), e = feet(entry), f = feet(bay);
    if (Math.abs(span(e) - span(f)) > 0.01) throw new Error(`bay ${bay}'s legs stand ${span(f).toFixed(2)} m apart and the entry bay's ${span(e).toFixed(2)} m at ring ${o.ring_radius_m} m: its gap would need measuring`);
    const inset = (span(f) - o.way_in_m) / 2, dx = (f[1][0] - f[0][0]) / span(f), dy = (f[1][1] - f[0][1]) / span(f);
    return [[f[0][0] + dx * inset, f[0][1] + dy * inset], [f[1][0] - dx * inset, f[1][1] - dy * inset]];
  };

  // the ground in view, in the bay's own axes: across from pier A to pier B, and out from the room
  const A = piers[pierA], B = piers[pierB], mid = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2], half = Math.hypot(B[0] - A[0], B[1] - A[1]) / 2;
  const ax = [(B[0] - A[0]) / (2 * half), (B[1] - A[1]) / (2 * half)], out = [mid[0], mid[1]].map((v) => v / Math.hypot(...mid));
  const GRID = { origin: [mid[0] - ax[0] * (half + 1.8) - out[0] * 2.4, mid[1] - ax[1] * (half + 1.8) - out[1] * 2.4], across: ax, out, nx: Math.round((2 * half + 3.6) / CELL_M) + 1, ny: Math.round(5.4 / CELL_M) + 1, cell: CELL_M };

  const scene = (o) => { const f = resolve(root, 'scenes', o.snapshot, 'bower-place.json'); if (!existsSync(f)) throw new Error(`${f} is not there: the simulator's input for ${o.snapshot}`); return JSON.parse(readFileSync(f, 'utf8')); };
  const place0 = scene(first), path = sunPath(place0.site.latitudeDeg, place0.site.bearingDeg ?? 0, MAP_DOY);
  const possible = path.reduce((s, x) => s + x.step, 0);
  const openings = list.map((o) => {
    const occ = occluders(scene(o)), ground = plane(Object.entries(o.levels_m).map(([id, z]) => [...piers[id], z]));
    const map = [];
    for (let j = 0; j < GRID.ny; j++) for (let i = 0; i < GRID.nx; i++) {
      const x = GRID.origin[0] + ax[0] * i * CELL_M + out[0] * j * CELL_M, y = GRID.origin[1] + ax[1] * i * CELL_M + out[1] * j * CELL_M;
      map.push(Math.round(hoursAt(occ, [x, y, ground[0] + ground[1] * x + ground[2] * y + MAP_Z], path) * 10));   // tenths of an hour
    }
    const gap = gapOf(o), fails = o.footing_review ?? [];
    return {
      ring: o.ring_radius_m,
      across: Math.round(o.ring_radius_m * 20) / 10,   // the ring of legs, measured across
      snapshot: o.snapshot,
      gap: o.way_in_m,
      gapPts: gap.map((p) => p.map(r3)),
      wayIn: o.way_in_m,
      ground,
      sun: { mean: o.sun.mean_june_h, full: o.sun.full_sun, june: plants.map((p) => sunOf(o, p.id).june_h) },
      pts: members.flatMap((m) => o.members.find((x) => x.id === m.id).pts.flat().map(mm)),
      roots: plants.map((p) => { const q = o.plants.find((x) => x.id === p.id); return [mm(q.root[0]), mm(q.root[1]), mm(q.soil_z)]; }),
      footing: fails.length ? (fails.some((x) => /a foot stands/.test(x)) ? 'reach' : 'gap') : null,   // the footing draft's review of the piles
      map,
    };
  });
  return {
    note: O.note,
    run: O.run,
    site: { latitude: O.site.latitude_deg, floorR: O.site.floor_radius_m },
    chosen,
    bay, piersInView: [pierA, pierB],
    piers,
    members,
    plants,
    grid: GRID,
    mapDay: '21 June',
    mapPossible: Math.round(possible * 10) / 10,
    openings,
  };
}

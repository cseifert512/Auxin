// Leaves seen across a room, drawn as what can be seen of them.
//
// The plant models come in three finenesses, and the coarsest is still a portrait: a leaf of five leaflets is 92
// triangles, each leaflet shaped, on its stalk. From the far side of a room that leaf is a few pixels, and there
// are thirty thousand of them. Here the coarsest model is redrawn from its own corners: each blade (a leaf, or
// one leaflet of a leaf made of several) becomes the outline round it, a few corners of the model's own joined
// into a fan, and the stalks, which are thinner than a pixel, are left out. The finer models, for the few hundred
// leaves of each kind nearest the eye, are not touched: close to, a leaf keeps its shape.
//
// Every corner kept is one the model already had, with everything it carries (its colour, its place on the leaf
// picture, which blade it belongs to), so the leaf unfolds, turns and colours as it did.
import * as THREE from 'three';

/** The outline of points in a plane (indices into `xy`), anticlockwise. */
function outline(ids: number[], x: (i: number) => number, y: (i: number) => number): number[] {
  const sorted = [...ids].sort((a, b) => x(a) - x(b) || y(a) - y(b));
  const cross = (o: number, a: number, b: number) => (x(a) - x(o)) * (y(b) - y(o)) - (y(a) - y(o)) * (x(b) - x(o));
  const half = (list: number[]) => {
    const h: number[] = [];
    for (const p of list) {
      while (h.length >= 2 && cross(h[h.length - 2]!, h[h.length - 1]!, p) <= 0) h.pop();
      h.push(p);
    }
    h.pop();
    return h;
  };
  return [...half(sorted), ...half(sorted.reverse())];
}

/**
 * A model redrawn as the outlines of its blades: at most `corners` to a blade.
 * Returns null where the model is not made that way (no `aPart`) or would gain nothing.
 */
export function outlined(src: THREE.BufferGeometry, corners: number): { geometry: THREE.BufferGeometry; triangles: number } | null {
  const position = src.getAttribute('position');
  const part = src.getAttribute('aPart');
  const index = src.index;
  if (!position || !part || !index) return null;
  // the corners of each blade: those that share the place where it joins its stalk (aPart.xyz), stalks (w < 0) apart
  const blades = new Map<string, number[]>();
  for (let i = 0; i < position.count; i++) {
    if (part.getW(i) < 0) continue;
    const key = `${part.getX(i).toFixed(4)},${part.getY(i).toFixed(4)},${part.getZ(i).toFixed(4)}`;
    let list = blades.get(key);
    if (!list) blades.set(key, (list = []));
    list.push(i);
  }
  const p = (i: number) => new THREE.Vector3().fromBufferAttribute(position, i);
  const normal = src.getAttribute('normal');
  const tris: number[] = [];
  for (const ids of blades.values()) {
    if (ids.length < 3) continue;
    // the blade's own plane: along it from where it joins its stalk to its far end, and across
    const base = new THREE.Vector3(part.getX(ids[0]!), part.getY(ids[0]!), part.getZ(ids[0]!));
    let tip = ids[0]!;
    for (const i of ids) if (p(i).distanceToSquared(base) > p(tip).distanceToSquared(base)) tip = i;
    const along = p(tip).sub(base).normalize();
    let side = ids[0]!;
    let widest = -1;
    for (const i of ids) {
      const v = p(i).sub(base);
      const w = v.addScaledVector(along, -v.dot(along)).lengthSq();
      if (w > widest) {
        widest = w;
        side = i;
      }
    }
    const sideways = p(side).sub(base);
    const across = sideways.addScaledVector(along, -sideways.dot(along)).normalize();
    if (!(across.lengthSq() > 0.5)) continue;
    const x = (i: number) => p(i).sub(base).dot(along);
    const y = (i: number) => p(i).sub(base).dot(across);
    let hull = outline(ids, x, y);
    // fewer corners: the one whose loss takes least from the outline goes first
    const area = (a: number, b: number, c: number) => Math.abs((x(b) - x(a)) * (y(c) - y(a)) - (y(b) - y(a)) * (x(c) - x(a)));
    while (hull.length > corners) {
      let least = Infinity;
      let at = 0;
      for (let k = 0; k < hull.length; k++) {
        const lost = area(hull[(k + hull.length - 1) % hull.length]!, hull[k]!, hull[(k + 1) % hull.length]!);
        if (lost < least) {
          least = lost;
          at = k;
        }
      }
      hull = hull.filter((_, k) => k !== at);
    }
    // The outline runs anticlockwise seen from along x across. It is turned over if the model says the blade's upper
    // side is the other one (its normals), so that the outline is lit from the side the leaf was.
    if (normal) {
      const up = new THREE.Vector3();
      for (const i of ids) up.add(new THREE.Vector3().fromBufferAttribute(normal, i));
      if (new THREE.Vector3().crossVectors(along, across).dot(up) < 0) hull.reverse();
    }
    // The fan is drawn from a corner in the middle of the blade, where the model has one. A leaf's picture is laid
    // on it from the midrib out to the margin: an outline alone carries only the margin, and the leaf comes out
    // the colour of its edge.
    const cx = hull.reduce((sum, i) => sum + x(i), 0) / hull.length;
    const cy = hull.reduce((sum, i) => sum + y(i), 0) / hull.length;
    let hub = ids[0]!;
    for (const i of ids) if ((x(i) - cx) ** 2 + (y(i) - cy) ** 2 < (x(hub) - cx) ** 2 + (y(hub) - cy) ** 2) hub = i;
    if (hull.includes(hub)) for (let k = 1; k + 1 < hull.length; k++) tris.push(hull[0]!, hull[k]!, hull[k + 1]!);
    else for (let k = 0; k < hull.length; k++) tris.push(hub, hull[k]!, hull[(k + 1) % hull.length]!);
  }
  if (!tris.length || tris.length >= index.count) return null;
  // only the corners used, with all they carry
  const used = [...new Set(tris)];
  const place = new Map(used.map((v, k) => [v, k]));
  const geometry = new THREE.BufferGeometry();
  for (const name of Object.keys(src.attributes)) {
    const from = src.getAttribute(name) as THREE.BufferAttribute;
    if ((from as unknown as { isInstancedBufferAttribute?: boolean }).isInstancedBufferAttribute) continue;
    const to = new Float32Array(used.length * from.itemSize);
    used.forEach((v, k) => {
      for (let c = 0; c < from.itemSize; c++) to[k * from.itemSize + c] = from.getComponent(v, c);
    });
    geometry.setAttribute(name, new THREE.BufferAttribute(to, from.itemSize, from.normalized));
  }
  geometry.setIndex(tris.map((v) => place.get(v)!));
  // The normals the corners carried were for the leaf's own folds and curl. Over an outline they can lie in the
  // plane of a triangle, which the lighting cannot take (the leaf comes out black): they are worked out again
  // from the outline itself.
  geometry.computeVertexNormals();
  geometry.boundingSphere = src.boundingSphere;
  geometry.boundingBox = src.boundingBox;
  return { geometry, triangles: tris.length / 3 };
}

interface Slot {
  mesh: THREE.InstancedMesh;
  tris: number;
}

/**
 * Redraw the coarsest model of every kind of leaf, with `far` corners to a blade.
 * Returns how many triangles one of each takes, before and after, for the record.
 */
export function coarsenLeaves(leafPools: readonly { asset: { key: string }; pool: unknown }[], far = 6): string[] {
  const done: string[] = [];
  for (const { asset, pool } of leafPools) {
    const slots = (pool as { slots: Slot[][] }).slots;
    for (const lods of slots) {
      lods.forEach((slot, level) => {
        const fromFar = lods.length - 1 - level;
        if (fromFar > 0 || lods.length < 2) return;
        // a leaf of many leaflets gets fewer corners to each: there are more of them to draw
        const blades = new Set<string>();
        const part = slot.mesh.geometry.getAttribute('aPart');
        if (part) for (let i = 0; i < part.count; i++) if (part.getW(i) >= 0) blades.add(`${part.getX(i).toFixed(4)},${part.getY(i).toFixed(4)},${part.getZ(i).toFixed(4)}`);
        const corners = Math.max(4, Math.round(far / (blades.size > 3 ? 1.5 : 1)));
        const made = outlined(slot.mesh.geometry, corners);
        if (!made) return;
        // what is set for each leaf drawn (where it stands, how far it has unfolded) is the pool's, and stays
        for (const [name, attribute] of Object.entries(slot.mesh.geometry.attributes)) {
          if ((attribute as unknown as { isInstancedBufferAttribute?: boolean }).isInstancedBufferAttribute) made.geometry.setAttribute(name, attribute);
        }
        if (level === lods.length - 1) done.push(`${asset.key} ${slot.tris} -> ${made.triangles}`);
        slot.mesh.geometry = made.geometry;
        slot.tris = made.triangles;
      });
    }
  }
  return done;
}

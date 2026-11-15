import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {cameraAt,film} from './canopy-camera.mjs';
for(const projection of ['perspective','axonometric']){
  const start=cameraAt(0,projection),end=cameraAt(49,projection);
  assert.equal(start.eye[2],1.7);assert.equal(end.eye[2],36);
  assert.ok(cameraAt(12,projection).eye[2]>cameraAt(24,projection).eye[2],'The eye level should vary before the final ascent');
  assert.ok(Math.abs(end.azimuth-start.azimuth-Math.PI*2)<1e-10,'The route should make a full orbit');
  assert.equal(Math.hypot(...end.eye.slice(0,2)),0,'The end must be directly overhead, not merely elevated');
  assert.deepEqual(cameraAt(54,projection).eye,end.eye);assert.equal(film.duration-film.motionEnd,6);
  for(let t=0;t<49;t+=.05){const a=cameraAt(t,projection),b=cameraAt(t+.05,projection);assert.ok([...a.eye,...a.up,a.zoom,a.fieldHeight].every(Number.isFinite));assert.ok(Math.hypot(...a.eye.map((v,i)=>v-b.eye[i]))<.3,'Camera travel must remain continuous');}
  const data=JSON.parse(await readFile(new URL(`../assets/canopy-orbit/${projection}-camera.json`,import.meta.url),'utf8'));
  assert.equal(data.samples.at(-1).time,49);
  for(const frame of data.samples){
    const p=frame.projectionMatrix;assert.equal(p[11],projection==='perspective'?-1:0);assert.equal(p[15],projection==='perspective'?0:1);
    assert.ok([...p,...frame.matrix,...frame.eye].every(Number.isFinite));
  }
}
// The insert must keep all prior slide objects and authored content untouched.
const environment={window:{}};vm.runInNewContext(await readFile(new URL('../story.js',import.meta.url),'utf8'),environment);
const originalStory=environment.window.DESIGNX_V8_STORY,originalSlides=originalStory.map(s=>({theme:s.theme,title:s.title,html:`original-${s.number}`,notes:s.purpose}));
const snapshot=JSON.stringify(originalSlides);environment.window.DESIGNX_SLIDES=originalSlides.slice();environment.window.DESIGNX_META={targetSlideCount:18};
vm.runInNewContext(await readFile(new URL('../canopy-orbit.js',import.meta.url),'utf8'),environment);
assert.equal(environment.window.DESIGNX_SLIDES.length,19);assert.equal(environment.window.DESIGNX_SLIDES[3].theme,'v8-canopy-orbit-slide');
assert.equal(JSON.stringify(environment.window.DESIGNX_SLIDES.filter(s=>s.theme!=='v8-canopy-orbit-slide')),snapshot);
assert.deepEqual(environment.window.DESIGNX_SLIDES.filter(s=>s.theme!=='v8-canopy-orbit-slide'),originalSlides);
assert.equal(environment.window.DESIGNX_V8_STORY.length,19);
console.log('PASS: full orbit, varying eye height, true overhead hold, genuine projection matrices and unchanged existing slides.');

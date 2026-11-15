// Test-owned renderer. It reuses the scene owner's timber, assembly and lighting
// code, and reads only exported building data. No growth record or plant meshes
// are downloaded. The packed film is a view-specific vegetation/shadow residual.
import * as THREE from 'three';
import { makePaper } from '../../../../../drawings-in-code/studio/src/paper.ts';
import { loadTimber, drawBeds, drawCables } from '../../../../../drawings-in-code/studio/src/timber.ts';
import { makeAssembly } from '../../../../../drawings-in-code/studio/src/assembly.ts';

const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const smooth = x => { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); };
const vertexShader = 'varying vec2 vUv; void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}';
const percentile = (values, p) => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))];
};

export async function createHybrid({ canvas, manifest, signal, onReady, onError, onTime, onFrame }) {
  const began = performance.now(), config = manifest.hybrid, source = manifest.source || {};
  const duration = Number(manifest.duration || source.duration || 51), fps = Number(config.fps || 12);
  const width = Number(manifest.width || 1600), height = Number(manifest.height || 900);
  const asset = path => new URL(path, document.baseURI).href;
  const abort = new AbortController();
  const json = async path => {
    const response = await fetch(asset(path), { signal: abort.signal });
    if (!response.ok) throw new Error(`Cannot load ${path}: HTTP ${response.status}`);
    return response.json();
  };
  let disposed = false, paper, timber, assembly, cables, overlayMaterial, blendMaterial;
  let videoTexture, inkTexture, frameHandle = 0, raf = 0, lastMediaTime = 0, lastRenderedTime = -1;
  let firstFrameMs = null, renderedFrames = 0, lastDrawCalls = 0, lastTriangles = 0;
  let error = null, pendingSeek = null;
  let layerEnabled = true;
  let cancelVideoReady = () => {};
  const renderTimes = [], frameGaps = [];
  let lastPresentation = 0;
  const video = document.createElement('video');
  video.muted = true; video.playsInline = true; video.preload = 'auto'; video.loop = false;
  video.hidden = true; video.setAttribute('aria-hidden', 'true');
  canvas.parentElement?.append(video);
  canvas.style.pointerEvents = 'none'; // This experiment deliberately has a prescribed camera.

  const fail = problem => {
    if (disposed) return;
    error = problem instanceof Error ? problem : new Error(String(problem));
    video.pause(); onError?.(error);
  };
  const videoReady = new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('The foliage film did not provide its first frame within 60 seconds.')), 60000);
    const clear = () => { clearTimeout(timeout); video.removeEventListener('loadeddata', ready); video.removeEventListener('error', bad); };
    const ready = () => { clear(); cancelVideoReady = () => {}; resolve(); };
    const bad = () => { clear(); cancelVideoReady = () => {}; reject(new Error(`Foliage film unavailable (${video.error?.code || 'media error'}).`)); };
    cancelVideoReady = () => { clear(); reject(new DOMException('Hybrid loading cancelled.', 'AbortError')); };
    video.addEventListener('loadeddata', ready, { once: true });
    video.addEventListener('error', bad, { once: true });
    video.src = asset(config.src); video.load();
  });
  // Geometry preparation and video download overlap. Keep an early media error
  // handled until the awaited readiness check propagates it to the caller.
  videoReady.catch(() => {});

  const overlayScene = new THREE.Scene(), overlayCamera = new THREE.Camera();
  const quadGeometry = new THREE.PlaneGeometry(2, 2);
  const packedQuad = new THREE.Mesh(quadGeometry);
  const blendQuad = new THREE.Mesh(quadGeometry);
  packedQuad.frustumCulled = blendQuad.frustumCulled = false;
  const assertActive = () => { if (disposed || signal?.aborted) throw new DOMException('Hybrid loading cancelled.', 'AbortError'); };
  const externalAbort = () => dispose();

  function cameraAt(time) {
    const frames = source.cameraFrames;
    if (frames?.length) {
      // Samples and the overlay are both baked at 12 fps. Never advance the
      // geometry to an interpolated viewpoint while an older video frame shows.
      let index = clamp(Math.round(time * fps), 0, frames.length - 1);
      while (index > 0 && frames[index].time > time + 0.0001) index--;
      while (index + 1 < frames.length && frames[index + 1].time <= time + 0.0001) index++;
      return frames[index];
    }
    const p = smooth(Math.min(1, time / 49));
    const angle = Math.atan2(-21, 1.2) + Math.PI * p, radius = Math.hypot(1.2, 21);
    return { eye: [radius * Math.cos(angle), radius * Math.sin(angle), 1.7 + 0.9 * p], target: [0, 0, 3], zoom: 1.23 };
  }
  function dayAt(time) {
    const line = source.line || { start: -598, planted: 11, lastSummer: 3399 };
    return time < 12 ? line.start + time / 12 * (line.planted - line.start)
      : time < 13 ? line.planted
      : line.planted + Math.min(1, (time - 13) / 36) * (line.lastSummer - line.planted);
  }
  function render(time, presentationTime = performance.now()) {
    if (disposed || !paper || video.readyState < 2) return;
    const renderBegan = performance.now();
    const at = clamp(Math.floor((time + 0.0001) * fps) / fps, 0, duration - 1 / fps);
    const cameraData = cameraAt(at), camera = paper.camera();
    const eye = cameraData.eye, target = cameraData.target || [0, 0, 3];
    camera.position.set(eye[0], eye[2], -eye[1]);
    camera.fov = Number(source.fov || 33.39848846798724);
    camera.aspect = width / height; camera.zoom = cameraData.zoom || 1.23;
    camera.lookAt(target[0], target[2], -target[1]);
    camera.updateProjectionMatrix(); camera.updateMatrixWorld(true);
    if (cameraData.matrix) {
      // Preserve the original published projection, including any framing crop.
      camera.projectionMatrix.fromArray(cameraData.matrix).multiply(camera.matrixWorld);
      camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    }
    const planted = (source.line || {}).planted ?? 11, day = dayAt(at);
    assembly.set(Math.min(1, at / 12));
    cables.visible = day >= planted && cables.userData.hasCables;
    timber.setAge((day - planted) / 365.25);
    const renderer = paper.renderer;
    renderer.info.reset(); renderer.info.autoReset = false;
    // Timber's shadow changes during assembly. Camera movement and timber ageing
    // do not require rendering the same stationary shadow map again.
    if (lastRenderedTime < 0 || at < 12 || lastRenderedTime < 12) paper.shadeChanged();
    const blend = smooth((at - 12) / 2);
    renderer.autoClear = true;
    if (blend > 0 && blend < 1) {
      timber.setLook('ink'); paper.render();
      renderer.copyFramebufferToTexture(inkTexture);
      timber.setLook('wood'); paper.render();
      blendMaterial.uniforms.opacity.value = 1 - blend;
      overlayScene.clear(); overlayScene.add(blendQuad);
      renderer.autoClear = false; renderer.render(overlayScene, overlayCamera);
    } else {
      timber.setLook(blend === 0 ? 'ink' : 'wood'); paper.render();
    }
    if (layerEnabled) {
      // A paused first frame or seek can arrive before VideoTexture's own rVFC.
      // Upload exactly the frame whose media timestamp drives this render.
      videoTexture.needsUpdate = true;
      overlayScene.clear(); overlayScene.add(packedQuad);
      renderer.autoClear = false; renderer.render(overlayScene, overlayCamera); renderer.autoClear = true;
    }
    lastDrawCalls = renderer.info.render.calls; lastTriangles = renderer.info.render.triangles;
    lastMediaTime = time; lastRenderedTime = at; renderedFrames++;
    const renderMs = performance.now() - renderBegan;
    renderTimes.push(renderMs); if (renderTimes.length > 2000) renderTimes.shift();
    if (!video.paused && lastPresentation) frameGaps.push(presentationTime - lastPresentation);
    lastPresentation = presentationTime;
    if (firstFrameMs === null) firstFrameMs = performance.now() - began;
    const detail = { time: Math.min(time, duration), mediaTime: time, cameraTime: at, renderMs };
    onTime?.(detail.time); onFrame?.(detail);
  }
  function frame(now, metadata) {
    frameHandle = 0;
    if (disposed) return;
    if (metadata) render(metadata.mediaTime, now);
    else if (video.currentTime !== lastMediaTime || lastRenderedTime < 0) render(video.currentTime, now);
    if (!video.paused) schedule();
  }
  function schedule() {
    if (disposed || frameHandle || raf || video.paused) return;
    if ('requestVideoFrameCallback' in video) frameHandle = video.requestVideoFrameCallback(frame);
    else raf = requestAnimationFrame(now => { raf = 0; frame(now); });
  }
  const cancelFrames = () => {
    if (frameHandle && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(frameHandle);
    frameHandle = 0; cancelAnimationFrame(raf); raf = 0; lastPresentation = 0;
  };
  async function setTime(value) {
    if (disposed) return;
    const time = clamp(Number(value) || 0, 0, duration - 0.0001);
    video.pause(); cancelFrames();
    pendingSeek?.cancel();
    if (!video.seeking && Math.abs(video.currentTime - time) < 0.00001) { render(video.currentTime); return; }
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => finish(new Error('Timed out seeking the foliage film.')), 30000);
      const finish = failure => {
        clearTimeout(timer); video.removeEventListener('seeked', done);
        if (pendingSeek?.done === done) pendingSeek = null;
        if (failure) reject(failure); else resolve();
      };
      const done = () => { render(video.currentTime); finish(); };
      pendingSeek = { done, cancel: () => finish() };
      video.addEventListener('seeked', done, { once: true });
      video.currentTime = time;
    });
  }
  function dispose() {
    if (disposed) return;
    disposed = true; abort.abort(); signal?.removeEventListener('abort', externalAbort); cancelVideoReady(); pendingSeek?.cancel(); cancelFrames(); video.pause();
    video.removeAttribute('src'); video.load(); video.remove();
    videoTexture?.dispose(); inkTexture?.dispose(); quadGeometry.dispose(); overlayMaterial?.dispose(); blendMaterial?.dispose();
    if (paper) {
      const geometries = new Set(), materials = new Set();
      paper.scene.traverse(object => {
        if (object.geometry) geometries.add(object.geometry);
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) if (material) materials.add(material);
      });
      geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose());
      paper.scene.environment?.dispose(); paper.sun.shadow.map?.dispose(); paper.renderer.dispose(); paper.renderer.forceContextLoss();
    }
  }
  try {
    signal?.addEventListener('abort', externalAbort, { once: true }); assertActive();
    const [design, centrelines, plan, bower] = await Promise.all([
      json(config.design), json(config.centrelines), json(config.assembly), json(config.bower),
    ]);
    assertActive();
    const stand = id => {
      const found = design.views.find(view => view.id === id);
      return { eye: found.location_m, target: found.target_m, lensMm: found.lens_mm };
    };
    const approach = stand('exterior'), inside = stand('interior');
    paper = makePaper(canvas, { approach, inside, approachTall: { ...approach, acrossDeg: 44 }, middle: design.rooms[0].crown.centre_m });
    paper.setSun(new THREE.Vector3(-0.609, 0.669, 0.426));
    paper.renderer.setPixelRatio(1); paper.renderer.setSize(width, height, false);
    paper.sun.shadow.mapSize.set(config.shadowSize || 4096, config.shadowSize || 4096);
    timber = await loadTimber(asset(config.timber), centrelines.members || centrelines);
    assertActive();
    paper.scene.add(timber.group); paper.frame(timber.bounds); paper.setView('approach');
    // paper.step is intentionally never called: no OrbitControls movement.
    assembly = makeAssembly(timber, plan); paper.scene.add(assembly.group);
    const stations = config.bedsUsed ? bower.stations.filter(station => config.bedsUsed.includes(station.id)) : bower.stations;
    paper.scene.add(drawBeds(stations));
    cables = drawCables(bower.cables || []); cables.userData.hasCables = Boolean(bower.cables?.length); paper.scene.add(cables);
    videoTexture = new THREE.VideoTexture(video); videoTexture.colorSpace = THREE.NoColorSpace;
    videoTexture.minFilter = videoTexture.magFilter = THREE.LinearFilter;
    inkTexture = new THREE.FramebufferTexture(width, height); inkTexture.colorSpace = THREE.NoColorSpace;
    blendMaterial = new THREE.ShaderMaterial({
      uniforms: { image: { value: inkTexture }, opacity: { value: 1 } }, vertexShader,
      fragmentShader: 'uniform sampler2D image;uniform float opacity;varying vec2 vUv;void main(){gl_FragColor=vec4(texture2D(image,vUv).rgb,opacity);}',
      transparent: true, depthTest: false, depthWrite: false, toneMapped: false,
    });
    overlayMaterial = new THREE.ShaderMaterial({
      uniforms: { packed: { value: videoTexture }, padding: { value: new THREE.Vector2(0.25 / (config.width || 1280), 0.5 / (config.height || 720)) } }, vertexShader,
      // Pixels are already display-encoded by the offline renderer. Applying
      // scene tone mapping or another sRGB conversion here would change them.
      fragmentShader: 'uniform sampler2D packed;uniform vec2 padding;varying vec2 vUv;void main(){vec2 c=clamp(vec2(vUv.x*.5,vUv.y),padding,vec2(.5-padding.x,1.-padding.y));vec2 m=clamp(vec2(.5+vUv.x*.5,vUv.y),vec2(.5+padding.x,padding.y),vec2(1.)-padding);vec3 rgb=texture2D(packed,c).rgb;float a=texture2D(packed,m).r;a=clamp((a-.015)/.97,0.,1.);gl_FragColor=vec4(rgb,a);}',
      transparent: true, depthTest: false, depthWrite: false, toneMapped: false,
    });
    blendQuad.material = blendMaterial; packedQuad.material = overlayMaterial;
    await videoReady;
    assertActive();
    render(video.currentTime);
    video.addEventListener('play', schedule);
    video.addEventListener('pause', cancelFrames);
    video.addEventListener('ended', () => { cancelFrames(); onTime?.(duration); onFrame?.({ time: duration, mediaTime: duration, ended: true }); });
    video.addEventListener('error', () => fail(new Error(`Foliage playback failed (${video.error?.code || 'unknown'}).`)));
    const result = {
      video, setTime,
      setLayerEnabled(enabled) { layerEnabled = Boolean(enabled); render(lastMediaTime); },
      async play() { if (disposed) return; error = null; await video.play(); schedule(); },
      pause() { video.pause(); cancelFrames(); }, dispose,
      getMetrics() {
        const quality = video.getVideoPlaybackQuality?.();
        const gl = paper.renderer.getContext(), debug = gl.getExtension('WEBGL_debug_renderer_info');
        return {
          firstFrameMs, renderedFrames, drawCalls: lastDrawCalls, triangles: lastTriangles,
          renderMs: renderTimes.at(-1) || 0, renderP50Ms: percentile(renderTimes, 0.5), renderP95Ms: percentile(renderTimes, 0.95),
          renderMeanMs: renderTimes.length ? renderTimes.reduce((sum, v) => sum + v, 0) / renderTimes.length : 0,
          frameGapP95Ms: percentile(frameGaps, 0.95), renderTiming: 'CPU submission; excludes unsynchronised GPU completion',
          mediaTime: video.currentTime, cameraTime: lastRenderedTime, duration,
          droppedVideoFrames: quality?.droppedVideoFrames || 0, totalVideoFrames: quality?.totalVideoFrames || 0,
          decodedWidth: video.videoWidth, decodedHeight: video.videoHeight,
          drawingWidth: width, drawingHeight: height, foliageWidth: config.width, foliageHeight: config.height,
          graphicsVendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
          graphicsRenderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
          playing: !video.paused, error: error?.message || null,
          layerEnabled,
        };
      },
    };
    onReady?.(result.getMetrics()); return result;
  } catch (problem) { dispose(); if (problem.name !== 'AbortError') onError?.(problem); throw problem; }
}

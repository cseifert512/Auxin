// Reproduce the film's geometry/cameras as compact, lossless linear-depth tiles.
// The full plant model is used only here, never loaded by the presentation.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {startStudio} from '../../../../drawings-in-code/pipeline/headless.mjs';
const require=createRequire(import.meta.url);
const sharp=require('C:/BOWER/Bower_Web/node_modules/sharp');
const base=new URL('../assets/time-experiment/',import.meta.url);
const manifest=JSON.parse(await readFile(new URL('manifest.json',base),'utf8'));
const args=Object.fromEntries(process.argv.slice(2).map(s=>s.replace(/^--/,'').split('=')));
const variants=(args.variant||'orbit,fixed,rise').split(',').map(id=>{
  const variant=manifest.variants.find(v=>v.id===id);if(!variant)throw Error('Unknown camera');return variant;
});
const width=768,height=432,fps=12,start=13,end=51,perChunk=12,columns=3,range=64;
const out=new URL('depth/',base);await mkdir(out,{recursive:true});
const studio=await startStudio(Number(args.port||5342),'six-bay-radial-v1');let page;
try{
  page=await studio.open({film:'',tour:'',view:'approach',timber:'wood',build:'0',run:'trained-10y'},{width:1600,height:900,scale:1});
  await page.js(`(async()=>{
    const T=await import('/@fs/C:/BOWER/Auxin/Horti-code-ture/node_modules/three/build/three.module.js');
    const {shared}=await import('/@fs/C:/BOWER/Auxin/Horti-code-ture/packages/viewer/src/plant/shaders.ts');
    const s=window.studio,r=s.paper.renderer;s.paper.step=()=>false;
    r.shadowMap.enabled=false;
    const scene=new T.Scene();scene.add(s.timber.group,s.plants.group);
    s.paper.render=()=>{};
    const target=new T.WebGLRenderTarget(${width},${height},{minFilter:T.NearestFilter,magFilter:T.NearestFilter,depthBuffer:true});
    const camera=new T.Camera(),bytes=new Uint8Array(${width*height*4});
    const patched=new WeakSet(),generic=new T.MeshDepthMaterial({side:T.DoubleSide,depthPacking:T.RGBADepthPacking});
    const patch=m=>{if(patched.has(m))return m;patched.add(m);const original=m.onBeforeCompile.bind(m);m.onBeforeCompile=(shader,renderer)=>{
      original(shader,renderer);
      shader.fragmentShader=shader.fragmentShader.replace(/}\\s*$/, 'float q = floor(clamp(vHighPrecisionZW.y / ${range}.0, 0.0, 1.0) * 65534.0); gl_FragColor = vec4(floor(q/256.0)/255.0, mod(q,256.0)/255.0, 0.0, 1.0); }');
    };m.customProgramCacheKey=()=> 'time-linear-depth-'+m.uuid;m.side=T.DoubleSide;m.toneMapped=false;m.needsUpdate=true;return m;};
    window.timeDepth=async(frame,time,fixed)=>{
      const c=s.paper.camera();c.position.set(frame.eye[0],frame.eye[2],-frame.eye[1]);c.zoom=1.23;c.lookAt(0,3,0);c.updateProjectionMatrix();c.updateMatrixWorld();
      await s.film(11+Math.min(1,(time-13)/36)*(3399-11),1/12);
      shared.uTime.value=fixed?Math.max(0,time-12)+1/30:Math.max(0,time-12)+Math.min(23/12,Math.max(0,time-12-1/12))+1/12;
      scene.traverse(o=>{if(o.isLine||o.isLineSegments2||o.isLine2){o.visible=false;return;}if(o.isMesh)o.material=patch(o.customDepthMaterial||generic);});
      camera.projectionMatrix.fromArray(frame.matrix);camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
      r.setRenderTarget(target);r.setClearColor(0xffffff,1);r.clear();r.render(scene,camera);r.readRenderTargetPixels(target,0,0,${width},${height},bytes);r.setRenderTarget(null);
      let binary='';for(let i=0;i<bytes.length;i+=16384)binary+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(binary);
    };
    return true;
  })()`);
  for(const variant of variants){
  const camera=t=>variant.cameraFrames.reduce((a,b)=>b.time<=t+1e-6?b:a,variant.cameraFrames[0]);
  const count=(end-start)*fps,probe=Object.hasOwn(args,'probe'),began=performance.now();
  // Optional targeted regeneration, e.g. --frames=orbit:98,101. Unchanged
  // cells in the affected chunks are retained losslessly.
  const requested=args.frames?.split(':');
  const selected=requested?.[0]===variant.id?new Set(requested[1].split(',').map(Number)):null;
  const first=Number(args.from||0),last=probe?3:count;
  let tiles=[];
  for(let i=first;i<last;i++){
    if(selected&&i%perChunk===0){
      if(!Array.from({length:perChunk},(_,n)=>i+n).some(n=>selected.has(n))){i+=perChunk-1;continue;}
      const chunk=Math.floor(i/perChunk);
      tiles=[{input:await readFile(new URL(`${variant.id}-${String(chunk).padStart(2,'0')}.webp`,out)),left:0,top:0}];
    }
    if(!selected||selected.has(i)){
    const time=probe?[18,32,49][i]:start+i/fps;
    const raw=Buffer.from(await page.js(`timeDepth(${JSON.stringify(camera(time))},${time},${variant.id==='fixed'})`),'base64');
    const input=await sharp(raw,{raw:{width,height,channels:4}}).flip().removeAlpha().png().toBuffer();
    if(probe){await writeFile(new URL(`../.qa/depth-${variant.id}-${time}.png`,new URL('../',base)),input);console.log(`${time}: ${((performance.now()-began)/1000).toFixed(1)}s elapsed`);continue;}
    tiles.push({input,left:(i%perChunk)%columns*width,top:Math.floor((i%perChunk)/columns)*height});
    }
    if(i%perChunk===perChunk-1){
      const chunk=Math.floor(i/perChunk),file=`${variant.id}-${String(chunk).padStart(2,'0')}.webp`;
      await sharp({create:{width:width*columns,height:height*Math.ceil(perChunk/columns),channels:3,background:'#ffffff'}}).composite(tiles).webp({lossless:true,effort:4}).toFile(fileURLToPath(new URL(file,out)));
      tiles=[];console.log(`${variant.id}: ${i+1}/${count}, ${((performance.now()-began)/1000/(i-first+1)).toFixed(2)}s/frame`);
    }
  }
  if(!probe)await writeFile(new URL('manifest.json',out),JSON.stringify({schema:'bower.time-depth/1',width,height,fps,start,end,perChunk,columns,range,encoding:'R*256+G; 0..65534 = 0..64 metres along camera axis; 65535 = clear',variants:manifest.variants.map(v=>v.id),source:'six-bay-radial-v1 / trained-10y; original organ deformation shaders and film camera matrices',evidence:'Generated depth of the illustrative growth scenario; not measured geometry.'},null,2)+'\n');
  }
}finally{page?.close();studio.stop();}
process.exit(0);

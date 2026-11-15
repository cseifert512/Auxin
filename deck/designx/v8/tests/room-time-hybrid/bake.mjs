// Isolated delivery experiment. Reads the existing model/run; writes only here.
// node bake.mjs --probe | --render | --encode
import { createRequire } from 'node:module';
import { mkdir, readFile, writeFile, copyFile, stat } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { startStudio } from '../../../../../drawings-in-code/pipeline/headless.mjs';

const here=dirname(fileURLToPath(import.meta.url)), repo=resolve(here,'../../../../..');
const assets=resolve(here,'assets'), work=resolve(here,'.qa'), frames=resolve(work,'packed'), fullFrames=resolve(work,'full');
const require=createRequire(import.meta.url);
const sharp=require('C:/BOWER/Bower_Web/node_modules/sharp');
const ffmpeg=require(resolve(repo,'drawings-in-code/node_modules/ffmpeg-static'));
const opts=Object.fromEntries(process.argv.slice(2).map(x=>x.replace(/^--/,'').split('=')));
const W=1600,H=900, OW=1280,OH=720,FPS=12,DURATION=51;
const sourceFolder=resolve(here,'../../assets/time-experiment');
const sourceManifest=JSON.parse(await readFile(resolve(sourceFolder,'manifest.json'),'utf8'));
const orbit=sourceManifest.variants.find(v=>v.id==='orbit');
const sourceLine=JSON.parse(await readFile(resolve(sourceFolder,'timeline-source.json'),'utf8'));
const smooth=p=>{p=Math.max(0,Math.min(1,p));return p*p*(3-2*p);};
const cameraAt=t=>{const p=Math.min(1,t/49),a=Math.atan2(-21,1.2)+Math.PI*smooth(p),r=Math.hypot(1.2,21);return {eye:[r*Math.cos(a),r*Math.sin(a),1.7+.9*smooth(p)],target:[0,0,3],zoom:1.23};};
const at=t=>t<12?sourceLine.line.start+t/12*(sourceLine.line.planted-sourceLine.line.start):t<13?sourceLine.line.planted:sourceLine.line.planted+Math.min(1,(t-13)/36)*(sourceLine.line.lastSummer-sourceLine.line.planted);
const hash=b=>createHash('sha256').update(b).digest('hex');
for(const p of [assets,work,frames,fullFrames])await mkdir(p,{recursive:true});
const exec=(cmd,args)=>new Promise((yes,no)=>{const p=spawn(cmd,args,{stdio:['ignore','ignore','pipe']});let err='';p.stderr.on('data',b=>err+=b);p.on('error',no);p.on('exit',code=>code===0?yes():no(Error(err.slice(-5000))));});

async function copyInputs(){
  for(const [from,to] of [
    ['releases/six-bay-radial-v1/bower.glb','timber.glb'],
    ['releases/six-bay-radial-v1/centrelines.json','centrelines.json'],
    ['releases/six-bay-radial-v1/design.json','design.json'],
    ['drawings-in-code/scenes/six-bay-radial-v1/assembly.json','assembly.json'],
    ['drawings-in-code/scenes/six-bay-radial-v1/bower.json','bower.json'],
  ])await copyFile(resolve(repo,from),resolve(assets,to));
  await copyFile(resolve(sourceFolder,'orbit-poster.jpg'),resolve(assets,'poster.jpg'));
}
await copyInputs();

let studio,page;
async function open(){
  studio=await startStudio(5338,'six-bay-radial-v1');
  page=await studio.open({film:'',tour:'',view:'approach',timber:'ink',build:'0',run:'trained-10y'}, {width:W,height:H,scale:1});
  await page.js(`(()=>{const s=window.studio;s.paper.step=()=>false;s.paper.resize();return true;})()`);
}
async function pair(t){
  const c=cameraAt(t),blend=smooth((t-12)/2);
  return page.js(`(async()=>{
    const s=window.studio,p=s.paper,c=p.camera();
    c.position.set(${c.eye[0]},${c.eye[2]},${-c.eye[1]});c.zoom=1.23;c.lookAt(0,3,0);c.updateProjectionMatrix();c.updateMatrixWorld();
    s.look(${JSON.stringify(blend===0?'ink':'wood')});await s.film(${at(t)},${1/FPS});
    const capture=()=>p.renderer.domElement.toDataURL('image/png').split(',')[1];
    const result={full:capture(),matrix:c.projectionMatrix.clone().multiply(c.matrixWorldInverse).toArray()};
    const visible=s.plants.group.visible;s.plants.group.visible=false;p.shadeChanged();p.render();result.base=capture();
    if(${blend}>0&&${blend}<1){
      s.look('ink');p.shadeChanged();p.render();result.inkBase=capture();
      s.plants.group.visible=visible;p.shadeChanged();p.render();result.inkFull=capture();
    }
    s.plants.group.visible=visible;
    return result;
  })()`);
}
async function processPair(t,data,index,probe=false){
  const decode=async b=>sharp(Buffer.from(b,'base64')).removeAlpha().raw().toBuffer();
  let full=await decode(data.full),base=await decode(data.base);
  const blend=smooth((t-12)/2);
  if(data.inkFull){const f=await decode(data.inkFull),b=await decode(data.inkBase);for(let k=0;k<full.length;k++){full[k]=Math.round(f[k]*(1-blend)+full[k]*blend);base[k]=Math.round(b[k]*(1-blend)+base[k]*blend);}}
  // Difference includes occluded vegetation and its shadows, preserving the source's relationships.
  // The 3/255 threshold rejects insignificant precision noise; one-pixel dilation protects fine edges.
  const mask=Buffer.alloc(W*H);let marked=0;
  for(let i=0;i<mask.length;i++){const k=i*3;if(Math.max(Math.abs(full[k]-base[k]),Math.abs(full[k+1]-base[k+1]),Math.abs(full[k+2]-base[k+2]))>3){mask[i]=255;marked++;}}
  const dilated=Buffer.from(mask);
  for(let y=1;y<H-1;y++)for(let x=1;x<W-1;x++){const i=y*W+x;if(mask[i]){dilated[i-1]=dilated[i+1]=dilated[i-W]=dilated[i+W]=255;}}
  // sharp's morphology grows dark pixels for dilate; erode expands this white coverage mask.
  const support=await sharp(dilated,{raw:{width:W,height:H,channels:1}}).erode(5).greyscale().raw().toBuffer();
  if(support.length!==W*H)throw Error('Colour support must have exactly one channel');
  const isolated=Buffer.from(full);
  for(let i=0;i<support.length;i++){if(dilated[i]&&!support[i])throw Error('Colour support must contain the entire coverage mask');if(!support[i]){isolated[i*3]=253;isolated[i*3+1]=252;isolated[i*3+2]=249;}}
  const colour=await sharp(isolated,{raw:{width:W,height:H,channels:3}}).resize(OW,OH).png().toBuffer();
  const alpha=await sharp(dilated,{raw:{width:W,height:H,channels:1}}).resize(OW,OH).png().toBuffer();
  const packed=await sharp({create:{width:OW*2,height:OH,channels:3,background:'#000'}}).composite([{input:colour,left:0,top:0},{input:alpha,left:OW,top:0}]).png().toBuffer();
  const stem=String(index).padStart(5,'0');
  await writeFile(resolve(frames,`${stem}.png`),packed);
  await sharp(full,{raw:{width:W,height:H,channels:3}}).jpeg({quality:94}).toFile(resolve(fullFrames,`${stem}.jpg`));
  if(probe){
    await sharp(full,{raw:{width:W,height:H,channels:3}}).png().toFile(resolve(work,`probe-${t}-full.png`));
    await sharp(base,{raw:{width:W,height:H,channels:3}}).png().toFile(resolve(work,`probe-${t}-base.png`));
    await sharp(dilated,{raw:{width:W,height:H,channels:1}}).png().toFile(resolve(work,`probe-${t}-mask.png`));
    // Exact-resolution residual should reconstruct the source apart from sub-threshold differences.
    const restored=Buffer.from(base);let absolute=0,maxError=0;
    for(let i=0;i<mask.length;i++)for(let ch=0;ch<3;ch++){const k=i*3+ch;if(dilated[i])restored[k]=full[k];const d=Math.abs(restored[k]-full[k]);absolute+=d;maxError=Math.max(maxError,d);}
    await sharp(restored,{raw:{width:W,height:H,channels:3}}).png().toFile(resolve(work,`probe-${t}-reconstructed.png`));
    console.log(JSON.stringify({probe:t,maskPercent:100*marked/mask.length,meanResidualError:absolute/full.length,maxResidualError:maxError}));
  }
  return {time:t,...cameraAt(t),matrix:data.matrix,maskFraction:marked/mask.length};
}

async function encode(){
  await exec(ffmpeg,['-y','-loglevel','error','-framerate',String(FPS),'-i',resolve(frames,'%05d.png'),'-c:v','libx264','-preset','slow','-crf','25','-pix_fmt','yuv420p','-movflags','+faststart','-an',resolve(assets,'foliage-packed.mp4')]);
  // A third control separates encoder savings from hybrid-rendering savings.
  let reusable=false;
  try{const prior=JSON.parse(await readFile(resolve(here,'manifest.json'),'utf8'));const bytes=await readFile(resolve(assets,'compressed-film.mp4'));
    reusable=prior.original.sha256===orbit.sha256&&prior.assets['compressed-film.mp4'].sha256===hash(bytes)&&!('reencode-control'in opts);
  }catch{}
  if(!reusable)await exec(ffmpeg,['-y','-loglevel','error','-i',resolve(sourceFolder,'orbit.mp4'),'-vf',`scale=${OW}:${OH},fps=${FPS}`,'-c:v','libx264','-preset','slow','-crf','25','-pix_fmt','yuv420p','-movflags','+faststart','-an',resolve(assets,'compressed-film.mp4')]);
}
async function repack(only=null){
  // Upgrade already baked frames without repeating the expensive plant render.
  for(let i=0;i<DURATION*FPS;i++){
    if(only!==null&&i!==only)continue;
    const file=resolve(frames,`${String(i).padStart(5,'0')}.png`),packed=await readFile(file);
    const colour=await sharp(resolve(fullFrames,`${String(i).padStart(5,'0')}.jpg`)).resize(OW,OH).removeAlpha().raw().toBuffer();
    const alpha=await sharp(packed).extract({left:OW,top:0,width:OW,height:OH}).greyscale().raw().toBuffer();
    const support=await sharp(alpha,{raw:{width:OW,height:OH,channels:1}}).threshold(1).erode(5).greyscale().raw().toBuffer();
    if(support.length!==OW*OH)throw Error('Colour support must have exactly one channel');
    for(let p=0;p<support.length;p++){if(alpha[p]&&!support[p])throw Error('Colour support must contain the entire coverage mask');if(!support[p]){colour[p*3]=253;colour[p*3+1]=252;colour[p*3+2]=249;}}
    const rgb=await sharp(colour,{raw:{width:OW,height:OH,channels:3}}).png().toBuffer();
    const mask=await sharp(alpha,{raw:{width:OW,height:OH,channels:1}}).png().toBuffer();
    const next=await sharp({create:{width:OW*2,height:OH,channels:3,background:'#000'}}).composite([{input:rgb,left:0,top:0},{input:mask,left:OW,top:0}]).png().toBuffer();
    await writeFile(file,next);
    if(i%120===119)console.log(`Isolated foliage colour ${i+1}/${DURATION*FPS}`);
  }
}
async function manifest(){
  const payload={};for(const name of ['timber.glb','centrelines.json','design.json','assembly.json','bower.json','poster.jpg','foliage-packed.mp4','compressed-film.mp4']){try{const b=await readFile(resolve(assets,name));payload[name]={bytes:b.length,sha256:hash(b)};}catch{}}
  const cameraFrames=JSON.parse(await readFile(resolve(work,'camera.json'),'utf8'));
  const bundle=await readFile(resolve(here,'renderer.bundle.js'));
  const hybridTotal=bundle.length+['timber.glb','centrelines.json','design.json','assembly.json','bower.json','foliage-packed.mp4'].reduce((n,f)=>n+(payload[f]?.bytes||0),0);
  const m={schema:'bower.room-time-hybrid-test/1',title:'Room through time — delivery comparison',duration:DURATION,width:W,height:H,poster:'assets/poster.jpg',
    original:{src:'../../assets/time-experiment/orbit.mp4',bytes:orbit.bytes,sha256:orbit.sha256,label:'Original film'},
    compressed:{src:'assets/compressed-film.mp4',bytes:payload['compressed-film.mp4']?.bytes,label:'Compressed film'},
    hybrid:{src:'assets/foliage-packed.mp4',bytes:payload['foliage-packed.mp4']?.bytes,totalBytes:hybridTotal,bundleBytes:bundle.length,width:OW,height:OH,fps:FPS,packing:'rgb-left-alpha-right',shadowSize:4096,
      timber:'assets/timber.glb',centrelines:'assets/centrelines.json',design:'assets/design.json',assembly:'assets/assembly.json',bower:'assets/bower.json'},
    source:{snapshot:'six-bay-radial-v1',run:'trained-10y',...sourceLine,cameraFrames,transition:[12,14],plantedTime:13,lastSummerTime:49},assets:payload,
    evidence:'Delivery experiment only. The existing growth scenario, camera path, model and slide remain unchanged. Hybrid bakes a view-specific vegetation-and-shadow residual; its 3/255 mask threshold, dilation and downsampling are display approximations, not new biological or lighting evidence.'};
  await writeFile(resolve(here,'manifest.json'),JSON.stringify(m)+'\n');
  console.log(JSON.stringify({assets:payload}));
}
try{
  if('probe' in opts){await open();for(const t of [6,13,28,42,49]){const began=performance.now();await processPair(t,await pair(t),Math.round(t*FPS),true);console.log(`Probe ${t}: ${((performance.now()-began)/1000).toFixed(1)} s`);}}
  else if('render' in opts){
    await open();const samples=[],began=performance.now(),start=Number(opts.start||0),end=Number(opts.end||DURATION*FPS);
    for(let i=start;i<end;i++){
      const t=i/FPS;const data=await pair(t);samples.push(await processPair(t,data,i));
      if(i%12===11)console.log(`Baked ${i+1}/${DURATION*FPS}: ${((performance.now()-began)/1000).toFixed(0)} s elapsed`);
    }
    await writeFile(resolve(work,'camera.json'),JSON.stringify(samples)+'\n');
    page.close();studio.stop();page=studio=null;
    if(start===0&&end===DURATION*FPS&&!('no-encode'in opts)){await encode();await manifest();}
  }else if('check-mask' in opts){await repack(49*FPS);console.log('Mature mask covers all visible foliage; colour proof updated.');}
  else if('repack' in opts){await repack();await encode();await manifest();}
  else if('manifest' in opts){await manifest();}
  else if('encode' in opts){await encode();await manifest();}
  else throw Error('Choose --probe, --render or --encode');
}finally{page?.close();studio?.stop();}

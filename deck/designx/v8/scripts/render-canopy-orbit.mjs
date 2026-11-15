// New v8 camera comparison. Read the frozen room and full growth run in place.
// Only this new asset folder is written; existing films/players are untouched.
import {createRequire} from 'node:module';
import {readFile,writeFile,mkdir,copyFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve,dirname} from 'node:path';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import {startStudio} from '../../../../drawings-in-code/pipeline/headless.mjs';
import {cameraAt,film,dayAt} from './canopy-camera.mjs';
const here=dirname(fileURLToPath(import.meta.url)),repo=resolve(here,'../../../..');
const out=resolve(here,'../assets/canopy-orbit'),proofs=resolve(here,'../.qa/canopy-orbit');
const require=createRequire(import.meta.url),sharp=require('C:/BOWER/Bower_Web/node_modules/sharp'),ffmpeg=require(resolve(repo,'drawings-in-code/node_modules/ffmpeg-static'));
const args=Object.fromEntries(process.argv.slice(2).map(s=>s.replace(/^--/,'').split('=')));
const variants=(args.variant||'perspective,axonometric').split(',');
const width=Number(args.width||film.width),height=Math.round(width*9/16),fps=Number(args.fps||film.fps);
await mkdir(out,{recursive:true});await mkdir(proofs,{recursive:true});
const run=(cmd,argv)=>new Promise((yes,no)=>{const p=spawn(cmd,argv,{stdio:['ignore','ignore','pipe']});let errors='';p.stderr.on('data',c=>errors+=c);p.on('exit',code=>code===0?yes():no(Error(errors)));});
const studio=await startStudio(Number(args.port||5346),'six-bay-radial-v1');let page;
try{
  page=await studio.open({film:'',tour:'',view:'approach',timber:'ink',build:'0',run:'trained-10y'},{width,height,scale:1});
  console.log('Studio loaded');
  const line=await page.js(`(()=>{const s=window.studio;s.paper.step=()=>false;s.paper.resize();return s.line();})()`);
  await page.js(await readFile(resolve(here,'../time-experiment.js'),'utf8')+'\ntrue;');
  await page.js(`(async()=>{
    const T=await import('/@fs/${repo.replaceAll('\\','/')}/Horti-code-ture/node_modules/three/build/three.module.js');
    const s=window.studio,p=s.paper;
    const perspective=new T.PerspectiveCamera(${cameraAt(0).fov},16/9,.05,600),parallel=new T.OrthographicCamera(-1,1,1,-1,.05,600);
    let active=perspective;const detail=new T.PerspectiveCamera(40,16/9,.05,600),aim=new T.Vector3(0,2.8,0);
    p.camera=()=>active;p.detailFrom=()=>{
      if(active===perspective)return active;
      detail.position.copy(aim).add(active.position.clone().sub(aim).normalize().multiplyScalar((parallel.top-parallel.bottom)/(2*Math.tan(Math.PI/9))));
      return detail;
    };p.render=()=>p.renderer.render(p.scene,active);
    const life=await import('/@fs/${repo.replaceAll('\\','/')}/deck/designx/v8/scripts/canopy-inhabitants.mjs');
    const inhabitants=await life.makeInhabitants(p.scene,'/@fs/${repo.replaceAll('\\','/')}/deck/designx/v8/assets/inhabitants/');
    window.canopyFrame=async(c,day,look,t)=>{
      active=c.projection==='perspective'?perspective:parallel;
      active.position.set(c.eye[0],c.eye[2],-c.eye[1]);active.up.set(c.up[0],c.up[2],-c.up[1]);
      active.lookAt(c.target[0],c.target[2],-c.target[1]);
      if(c.projection==='perspective')active.zoom=c.zoom;
      else{parallel.left=-c.fieldHeight*16/9/2;parallel.right=-parallel.left;parallel.top=c.fieldHeight/2;parallel.bottom=-parallel.top;parallel.zoom=1;}
      active.updateProjectionMatrix();active.updateMatrixWorld();
      inhabitants.update(t,window.DESIGNX_V8_TIME_EXPERIMENT);
      s.look(look);await s.film(day,1/${fps});
      return {matrix:active.projectionMatrix.clone().multiply(active.matrixWorldInverse).toArray(),view:active.matrixWorldInverse.toArray(),projectionMatrix:active.projectionMatrix.toArray()};
    };return true;
  })()`);
  console.log('Cameras and 3D inhabitants ready');
  const draw=async(t,variant,look)=>{
    const c=cameraAt(t,variant),projection=await page.js(`canopyFrame(${JSON.stringify(c)},${dayAt(t,line)},${JSON.stringify(look)},${t})`);
    return {bytes:await page.shot('jpeg'),camera:{...c,...projection}};
  };
  for(const variant of variants){
    if(!['perspective','axonometric'].includes(variant))throw Error('Unknown projection');
    if(Object.hasOwn(args,'probe')){
      for(const t of [6,12,24,36,43,49]){
        const began=performance.now(),frame=await draw(t,variant,t<12?'ink':'wood');
        await writeFile(resolve(proofs,`${variant}-${t}.jpg`),frame.bytes);
        console.log(`${variant} ${t}: ${((performance.now()-began)/1000).toFixed(2)}s`);
      }
      continue;
    }
    const frames=resolve(proofs,variant);await mkdir(frames,{recursive:true});
    const samples=[],began=performance.now(),last=Math.round(film.motionEnd*fps);
    for(let i=0;i<=last;i++){
      const t=i/fps,blend=Math.max(0,Math.min(1,(t-12)/2));
      const frame=await draw(t,variant,blend===0?'ink':'wood');let bytes=frame.bytes;
      if(blend>0&&blend<1){const ink=await draw(t,variant,'ink'),a=await sharp(ink.bytes).raw().toBuffer(),b=await sharp(bytes).raw().toBuffer(),mix=blend*blend*(3-2*blend);for(let k=0;k<a.length;k++)a[k]=Math.round(a[k]*(1-mix)+b[k]*mix);bytes=await sharp(a,{raw:{width,height,channels:3}}).jpeg({quality:94}).toBuffer();}
      await writeFile(resolve(frames,`${String(i).padStart(5,'0')}.jpg`),bytes);samples.push(frame.camera);
      if(i%48===47)console.log(`${variant} ${i+1}/${last+1}, ${((performance.now()-began)/1000/(i+1)).toFixed(2)}s/frame`);
    }
    await run(ffmpeg,['-y','-framerate',String(fps),'-i',resolve(frames,'%05d.jpg'),'-vf',`tpad=stop_mode=clone:stop_duration=6,fps=24`,'-t',String(film.duration),'-c:v','libx264','-crf','20','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart','-an',resolve(out,`${variant}.mp4`)]);
    await copyFile(resolve(frames,`${String(last).padStart(5,'0')}.jpg`),resolve(out,`${variant}-poster.jpg`));
    await writeFile(resolve(out,`${variant}-camera.json`),JSON.stringify({fps,samples})+'\n');
    console.log(`Finished ${variant}`);
  }
  if(!Object.hasOwn(args,'probe')){
    const variants=[];
    for(const [id,label] of [['perspective','Perspective'],['axonometric','Axonometric']]){
      try{const bytes=await readFile(resolve(out,`${id}.mp4`));variants.push({id,label,src:`${id}.mp4`,poster:`${id}-poster.jpg`,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),projection:id==='perspective'?'perspective':'orthographic'});}catch{}
    }
    await writeFile(resolve(out,'manifest.json'),JSON.stringify({schema:'bower.canopy-orbit/1',...film,width,height,fps,variants,startDate:'2027-03-12',endDate:'2036-06-20',sources:{snapshot:'six-bay-radial-v1',run:'trained-10y'},evidence:'Pre-rendered camera comparison of the existing generated room and provisional growth scenario, with authored 3D inhabitants. Neither projection is measured evidence.'},null,2)+'\n');
  }
}finally{page?.close();studio.stop();}
process.exit(0);

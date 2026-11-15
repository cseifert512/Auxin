// Source coordinates: east, north, up. A shared orbit, with two projections.
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const smooth=x=>{x=clamp(x);return x*x*(3-2*x);};
const radius=Math.hypot(1.2,21),startAngle=Math.atan2(-21,1.2);
const heights=[[0,1.7],[12,3],[24,1.9],[32,4.8],[40,16],[49,36]];
export function cameraAt(time,projection='perspective'){
  const t=Math.min(time,49),p=clamp(t/49),azimuth=startAngle+Math.PI*2*smooth(p);
  const lift=smooth((t-34)/15),r=radius*(1-lift);
  const next=heights.findIndex(([at])=>at>=t),a=heights[Math.max(0,next-1)],b=heights[Math.max(0,next)];
  const height=a[1]+(b[1]-a[1])*smooth((t-a[0])/(b[0]-a[0]||1));
  // Camera-up follows the limiting radial direction: the final vertical view
  // remains continuous instead of flipping at the lookAt singularity.
  const elevation=Math.atan2(height-2.8,r),zoom=1.16-.22*smooth((t-26)/9)+.30*smooth((t-43)/6);
  const fieldHeight=Math.max(9.6,(8.4*Math.cos(elevation)+12.8*Math.abs(Math.sin(elevation)))*1.08+.8*lift);
  return {time,projection,eye:[r*Math.cos(azimuth),r*Math.sin(azimuth),height],target:[0,0,2.8],up:[-Math.cos(azimuth)*lift,-Math.sin(azimuth)*lift,1-lift],fov:33.39848846798724,zoom,fieldHeight,azimuth,overhead:t===49};
}
export const film={width:1600,height:900,fps:12,duration:55,motionEnd:49,assemblyEnd:12,transition:[12,14],plantedDay:11,lastSummerDay:3399};
export const dayAt=(t,line)=>t<12?line.start+t/12*(line.planted-line.start):t<13?line.planted:line.planted+clamp((t-13)/36)*(line.lastSummer-line.planted);

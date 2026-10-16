export const SETTLE_MS=50;
export const DUST_LIFETIME_MS=280;
export function landingInfo(poses,level,action){
 const active=poses.find(pose=>pose.box.active);if(!active)return null;
 const min=[0,1,2].map(axis=>Math.min(...active.points.map(point=>point[axis])));
 const max=[0,1,2].map(axis=>Math.max(...active.points.map(point=>point[axis])));
 const cells=[];
 for(let r=Math.floor(min[1]+1e-6);r<Math.ceil(max[1]-1e-6);r++)for(let c=Math.floor(min[0]+1e-6);c<Math.ceil(max[0]-1e-6);c++)cells.push([r,c]);
 const symbols=cells.map(([r,c])=>level.grid[r]?.[c]||'.');
 if(symbols.some(symbol=>symbol==='.'||symbol==='G'))return null;
 const surfaceType=symbols.includes('O')?'fragile':symbols.includes('B')?'bridge':symbols.includes('T')?'split':symbols.some(symbol=>'SX'.includes(symbol))?'switch':level.biomeId==='forest'?'grass':'stone';
 return {action,cells,surfaceType,position:{x:(min[0]+max[0])/2,y:0,z:(min[1]+max[1])/2},
  upright:max[2]-min[2]>1.5,width:max[0]-min[0],depth:max[1]-min[1]};
}
export function settledPose(poses,progress,impact){
 const pulse=Math.sin(Math.PI*Math.max(0,Math.min(1,progress)));
 return poses.map(({box,points})=>{
  if(!box.active)return {box,points:points.map(point=>[...point])};
  const center=[0,1].map(axis=>(Math.min(...points.map(p=>p[axis]))+Math.max(...points.map(p=>p[axis])))/2);
  const squash=1-(impact.upright?.04:.025)*pulse,stretch=1/Math.sqrt(squash),sink=impact.upright?-.05*pulse:0;
  return {box,points:points.map(([x,y,z])=>[center[0]+(x-center[0])*stretch,center[1]+(y-center[1])*stretch,z*squash+sink])};
 });
}
/** Eight reusable fragments per contact, emitted along the footprint edges. */
export function dustBurst(impact){
 return Array.from({length:8},(_,index)=>{
  const angle=index*Math.PI/4,edge=index%4;
  const x=impact.position.x+(edge===0?-.47:edge===2?.47:Math.cos(angle)*.4)*impact.width;
  const z=impact.position.z+(edge===1?-.47:edge===3?.47:Math.sin(angle)*.4)*impact.depth;
  return {x,y:.02,z,vx:Math.cos(angle)*1.3,vy:.55+(index%3)*.15,vz:Math.sin(angle)*1.3,size:.045+(index%3)*.012};
 });
}

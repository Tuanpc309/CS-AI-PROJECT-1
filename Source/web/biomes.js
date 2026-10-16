import * as THREE from './vendor/three.module.js';
import { createWindMesh } from './wind.js';
export const BIOMES = {
 forest:{name:'Floating Pixel Forest',label:'Rừng trên mây',sky:'#142f32',horizon:'#40594b',fog:'#294345',accent:'#b6e4aa',grass:'#668f72',stone:'#526863',dark:'#314743',light:'#ffe2ad',particle:'#d2d895'},
 dusk:{name:'Dusk Sanctuary',label:'Thánh địa hoàng hôn',sky:'#30213f',horizon:'#865764',fog:'#594253',accent:'#f2c59c',grass:'#aa8178',stone:'#776779',dark:'#494255',light:'#ffd0a0',particle:'#f6c2a0'},
 neon:{name:'Misty Neon',label:'Mưa qua phố tím',sky:'#15172f',horizon:'#293452',fog:'#24283f',accent:'#96e5e9',grass:'#52627e',stone:'#3d4763',dark:'#292c48',light:'#d1b1ff',particle:'#80bbdf'},
 cavern:{name:'Crystal Cavern',label:'Hồ pha lê',sky:'#101f30',horizon:'#294956',fog:'#213848',accent:'#9be8e4',grass:'#557f8b',stone:'#45566f',dark:'#2c3d55',light:'#b5c8ff',particle:'#9bddf3'},
 celestial:{name:'Starlit Void',label:'Miền sao tĩnh lặng',sky:'#131329',horizon:'#363553',fog:'#26243f',accent:'#d4c6ff',grass:'#77728e',stone:'#514e6c',dark:'#34324e',light:'#f5debc',particle:'#e8dfff'},
};
export function seededRandom(seed) {
 let n=2166136261;for(const c of String(seed))n=Math.imul(n^c.charCodeAt(0),16777619);
 return ()=>{n=(Math.imul(n,1664525)+1013904223)>>>0;return n/4294967296;};
}
/** Procedural decorations outside the playable rectangle. One instanced draw
 * for the solid voxels, shared 8x8 pixel texture for camera-facing particles. */
export class VoxelEnvironment {
 constructor(level,theme) {
  this.group=new THREE.Group();this.theme=theme;this.resources=[];
  const rand=seededRandom(level.id),voxels=[],plants=[];
  const voxel=(x,y,z,w,h,d,color)=>voxels.push({x,y,z,w,h,d,color});
  const plant=(x,y,z,w,h,d,color,root,height,phase,strength=.12)=>plants.push({x,y,z,w,h,d,color,root,height,phase,strength});
  const cx=level.width/2,cz=level.height/2;
  for(let side=0;side<6;side++) {
   const a=side*Math.PI/3+.2,radius=Math.hypot(level.width,level.height)*.5+3+rand()*2;
   const x=cx+Math.cos(a)*radius,z=cz+Math.sin(a)*radius,y=-2.5-rand()*1.3,size=2+rand()*1.3;
   voxel(x,y,z,size,.6,size,theme.grass);voxel(x+.2,y-.65,z,size*.78,.8,size*.8,theme.stone);
   voxel(x-.15,y-1.25,z+.2,size*.45,.6,size*.47,theme.dark);
   if(level.biomeId==='forest') {
    const phase=rand()*6.28;
    plant(x,y+1,z,.35,2,.35,'#6b5a4b',y,3.6,phase,.14);
    for(let i=0;i<4;i++)plant(x+(rand()-.5)*1.1,y+2+i*.3,z+(rand()-.5)*.8,1.4-i*.18,.8,1.4-i*.13,['#81a77a','#638e70','#a7c58c','#82a77c'][i],y,3.6,phase,.14);
    for(let i=0;i<3;i++)voxel(x+(rand()-.5)*size,y+.4,z+(rand()-.5)*size,.22,.3,.22,'#e1cda1');
   } else if(level.biomeId==='dusk') {
    voxel(x,y+.5,z,1.6,.3,1.4,theme.light);
    for(const dx of [-.55,.55])voxel(x+dx,y+1.2,z,.3,1.2,.4,'#b7a6a1');
    voxel(x,y+1.9,z,1.8,.32,.8,'#cbb7ab');
   } else if(level.biomeId==='neon') {
    for(let i=0;i<3;i++){const h=1+rand()*2;voxel(x+(i-1)*.6,y+h/2,z,.5,h,.7,theme.dark);voxel(x+(i-1)*.6,y+h*.7,z+.37,.32,.09,.04,i%2?'#b8a0ef':'#87ccd4');}
   } else if(level.biomeId==='cavern') {
    for(let i=0;i<4;i++){const h=.8+rand()*1.5;voxel(x+(rand()-.5)*1.5,y+h/2,z+(rand()-.5),.35,h,.35,i%2?'#9ec5d6':'#83aaa9');}
   } else {
    voxel(x,y+1,z,1.2,.25,.35,theme.light);voxel(x,y+1,z,.35,.25,1.2,theme.light);voxel(x,y+.6,z,.25,.6,.25,theme.accent);
   }
   if(['forest','dusk'].includes(level.biomeId))for(let tuft=0;tuft<24;tuft++){
    const gx=x+(rand()-.5)*size*.85,gz=z+(rand()-.5)*size*.85;
    for(let blade=0;blade<3;blade++){
     const height=.15+rand()*.23,root=y+.3;
     plant(gx+(blade-1)*.07,root+height/2,gz,.045,height,.055,level.biomeId==='forest'?['#91b57d','#77a080','#acc68b'][blade]:['#b9a188','#c5aa8f','#9b8f87'][blade],root,height,rand()*6.28,.065);
    }
   }
  }
  for(let i=0;i<25;i++) {
   const a=rand()*Math.PI*2,r=Math.hypot(level.width,level.height)*.65+2+rand()*9;
   const cloud=['forest','dusk'].includes(level.biomeId);
   voxel(cx+Math.cos(a)*r,-3-rand()*4,cz+Math.sin(a)*r,cloud?2+rand()*3:.3+rand(),cloud?.3+rand()*.3:.5,cloud?1+rand():.5,cloud?'#8c9c9c':theme.stone);
  }
  const geometry=new THREE.BoxGeometry(1,1,1),material=new THREE.MeshLambertMaterial({flatShading:true});
  const instances=new THREE.InstancedMesh(geometry,material,voxels.length),dummy=new THREE.Object3D();
  voxels.forEach((v,i)=>{dummy.position.set(v.x,v.y,v.z);dummy.scale.set(v.w,v.h,v.d);dummy.updateMatrix();instances.setMatrixAt(i,dummy.matrix);instances.setColorAt(i,new THREE.Color(v.color));});
  this.group.add(instances);this.resources.push(geometry,material);
  if(plants.length){this.wind=createWindMesh(plants);this.group.add(this.wind.mesh);this.resources.push(this.wind.geometry,this.wind.material);}
  const pixels=document.createElement('canvas');pixels.width=pixels.height=8;
  const ctx=pixels.getContext('2d');ctx.fillStyle=theme.particle;
  if(level.biomeId==='forest'){ctx.fillRect(2,1,4,5);ctx.fillRect(1,2,6,2);}else{ctx.fillRect(3,0,2,8);ctx.fillRect(0,3,8,2);}
  const texture=new THREE.CanvasTexture(pixels);texture.magFilter=THREE.NearestFilter;texture.minFilter=THREE.NearestFilter;
  const spriteMaterial=new THREE.SpriteMaterial({map:texture,transparent:true,opacity:.5,depthWrite:false,fog:true});
  this.resources.push(texture,spriteMaterial);this.particles=[];
  for(let i=0;i<36;i++) {
   const sprite=new THREE.Sprite(spriteMaterial),a=rand()*Math.PI*2,r=Math.max(level.width,level.height)*.65+rand()*7;
   sprite.position.set(cx+Math.cos(a)*r,rand()*8-2,cz+Math.sin(a)*r);
   const s=level.biomeId==='neon'?.04:.08+rand()*.08;sprite.scale.set(s,level.biomeId==='neon'?.65:s,1);
   this.particles.push({sprite,origin:sprite.position.clone(),phase:rand()*6.28});this.group.add(sprite);
  }
  this.drifters=[];
  if(level.biomeId==='forest')for(let i=0;i<4;i++){
   const leaf=new THREE.Sprite(spriteMaterial);leaf.scale.set(.12,.17,1);this.group.add(leaf);
   this.drifters.push({sprite:leaf,phase:i*.25,cx,cz,width:level.width,height:level.height});
  }
  if(level.biomeId==='cavern') {
   const geo=new THREE.PlaneGeometry(100,100),mat=new THREE.MeshBasicMaterial({color:'#34526b',transparent:true,opacity:.22,depthWrite:false});
   const lake=new THREE.Mesh(geo,mat);lake.rotation.x=-Math.PI/2;lake.position.set(cx,-7,cz);this.group.add(lake);this.resources.push(geo,mat);
  }
  if(level.biomeId==='celestial') {
   const points=[];
   for(let i=0;i<140;i++){const a=rand()*6.28,r=18+rand()*25;points.push(cx+Math.cos(a)*r,rand()*22-2,cz+Math.sin(a)*r);}
   const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
   const mat=new THREE.PointsMaterial({color:theme.particle,size:2,sizeAttenuation:false,transparent:true,opacity:.65,fog:false});
   this.group.add(new THREE.Points(geo,mat));this.resources.push(geo,mat);
   this.meteor=new THREE.Sprite(spriteMaterial);this.meteor.scale.set(1.4,.035,1);this.meteor.visible=false;
   this.meteorOrigin=new THREE.Vector3(cx-12,6,cz-10);this.group.add(this.meteor);
  }
 }
 update(time,reducedMotion) {
  if(this.wind){this.wind.uniforms.uWindTime.value=time;this.wind.uniforms.uWindEnabled.value=reducedMotion?0:1;}
  this.drifters.forEach(({sprite,phase,cx,cz,width,height})=>{const t=(time*.035+phase)%1;sprite.visible=!reducedMotion&&t>.18&&t<.82;sprite.position.set(cx-width*.65+t*width*1.3,1.4-t*.7+Math.sin(time*.8+phase)*.15,cz+(phase-.5)*height*.6);sprite.material.rotation=0;});
  if(reducedMotion)return;
  this.particles.forEach(({sprite,origin,phase})=>{const rain=this.theme===BIOMES.neon;
   sprite.position.y=rain?origin.y-((time*.8+phase)%7):origin.y-Math.sin(time*.18+phase)*.6;
   sprite.position.x=origin.x+Math.sin(time*.12+phase)*.3;
  });
  if(this.meteor){const t=time%28;this.meteor.visible=t<1.4;this.meteor.position.copy(this.meteorOrigin).add(new THREE.Vector3(t*7,-t*.8,0));}
 }
 dispose(){this.resources.forEach(resource=>resource.dispose());this.group.clear();}
}

import * as THREE from './vendor/three.module.js';
import { BoardMotion } from './motion.js';
import { boxesForState, cuboidVertices } from './rolling.js';
import { OrbitCamera } from './camera.js';
import { BIOMES, VoxelEnvironment, seededRandom } from './biomes.js';
import { LandingDust } from './landing-dust.js';
const FACES=[[0,3,2,1],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]];

export class Board extends BoardMotion {
 constructor(canvas) {
  super();this.canvas=canvas;this.data=null;this.frame=null;this.animation=null;this._moving=false;
  this.reduceMotion=matchMedia('(prefers-reduced-motion: reduce)');this.orbit=new OrbitCamera();
  this.scene=new THREE.Scene();this.camera=new THREE.OrthographicCamera(-10,10,10,-10,.1,250);
  this.renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:false,powerPreference:'low-power'});
  this.renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5));this.renderer.setClearColor(0x000000,0);
  this.renderer.outputColorSpace=THREE.SRGBColorSpace;this.scene.add(new THREE.HemisphereLight(0xe5f0ff,0x252e3d,2));
  this.sun=new THREE.DirectionalLight(0xffedc5,2.1);this.sun.position.set(-9,18,7);this.scene.add(this.sun);
  this.boardGroup=new THREE.Group();this.scene.add(this.boardGroup);this.blockGroup=new THREE.Group();this.scene.add(this.blockGroup);
  this.dust=new LandingDust(this.scene);this.effectHooks={};
  this.boxGeometry=new THREE.BoxGeometry(1,1,1);this.materials=new Map();this.tiles=[];this.blocks=[];
  this.levelId=null;this.alive=true;this.lastFrame=performance.now();
  this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(canvas);
  this.reduceMotion.addEventListener('change',()=>{this.environment?.update(performance.now()/1000,this.reduceMotion.matches);if(this.reduceMotion.matches)this.dust.clear();this.draw();});
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();this.contextLost=true;});
  canvas.addEventListener('webglcontextrestored',()=>{this.contextLost=false;this.draw();});
  this.resize();this.loop();
 }
 material(color,emissive=false) {
  const key=color+emissive;
  if(!this.materials.has(key))this.materials.set(key,new THREE.MeshLambertMaterial({color,emissive:emissive?color:0,emissiveIntensity:emissive?.28:0,flatShading:true}));
  return this.materials.get(key);
 }
 box(group,x,y,z,w,h,d,color,emissive=false) {
  const mesh=new THREE.Mesh(this.boxGeometry,this.material(color,emissive));mesh.position.set(x,y,z);mesh.scale.set(w,h,d);group.add(mesh);return mesh;
 }
 ensureLevel() {
  if(!this.data||this.levelId===this.data.level.id)return;
  this.levelId=this.data.level.id;this.boardGroup.clear();this.tiles=[];
  this.environment?.dispose();if(this.environment)this.scene.remove(this.environment.group);
  this.theme=BIOMES[this.data.level.biomeId]||BIOMES.forest;
  const theme=this.theme,level=this.data.level,rand=seededRandom(level.id);
  document.documentElement.style.setProperty('--biome-sky',theme.sky);document.documentElement.style.setProperty('--biome-horizon',theme.horizon);
  document.documentElement.style.setProperty('--mint',theme.accent);this.scene.fog=new THREE.Fog(theme.fog,32,85);this.sun.color.set(theme.light);
  this.environment=new VoxelEnvironment(level,theme);this.scene.add(this.environment.group);
  this.environment.update(performance.now()/1000,this.reduceMotion.matches);this.dust.clear();
  level.grid.forEach((row,r)=>[...row].forEach((tile,c)=>{
   if(tile==='.')return;
   const group=new THREE.Group();this.boardGroup.add(group);group.position.set(c+.5,0,r+.5);
   const bridge=tile==='B'?level.bridges.findIndex(b=>b.cells.some(([br,bc])=>br===r&&bc===c)):-1;
   if(tile==='G') {
    for(const side of [-1,1]){this.box(group,side*.45,-.14,0,.1,.28,1,theme.accent,true);this.box(group,0,-.14,side*.45,.8,.28,.1,theme.accent,true);}
    this.box(group,0,-1.3,0,.77,.04,.77,'#080d1c');
   } else {
    const color=tile==='O'?'#d69b60':tile==='B'?theme.accent:theme.grass;this.box(group,0,-.15,0,.96,.3,.96,color);
    if(tile!=='B'){const depth=.35+rand()*.5;this.box(group,0,-.3-depth/2,0,.86,depth,.86,theme.stone);if(rand()>.5)this.box(group,.1,-.35-depth,0,.55,.2,.6,theme.dark);}
    if(tile==='O')for(let i=0;i<3;i++){const line=this.box(group,(i-1)*.15,.013,(i-1)*.2,.025,.014,.35,'#ffe2ae');line.rotation.y=i%2?.65:-.65;}
    if('SXT'.includes(tile)) {
     this.box(group,0,.025,0,.56,.05,.56,tile==='T'?'#c2a2ed':tile==='X'?'#e7b7a0':'#9adcd8',true);
     if(tile==='X')for(const angle of [-Math.PI/4,Math.PI/4]){const bar=this.box(group,0,.058,0,.4,.018,.055,'#3c364a');bar.rotation.y=angle;}
     else if(tile==='S')this.box(group,0,.06,0,.18,.02,.18,'#385a60');else for(const side of [-1,1])this.box(group,side*.1,.06,0,.07,.02,.3,'#4d426d');
    }
   }
   this.tiles.push({group,tile,r,c,bridge});
  }));this.fit();
 }
 resize() {
  const rect=this.canvas.getBoundingClientRect();this.width=rect.width;this.height=rect.height;
  this.renderer.setSize(this.width,this.height,false);this.fit();this.draw();
 }
 fit() {
  if(!this.data)return;const level=this.data.level;this.center=new THREE.Vector3(level.width/2,0,level.height/2);
  const mobile=innerWidth<=700&&innerHeight>innerWidth,short=innerHeight<=550;
  const top=mobile?(innerHeight<=700?160:200):short?86:112,bottom=mobile?(innerHeight<=700?132:180):short?83:155;
  const available=Math.max(85,this.height-top-bottom),diameter=Math.hypot(level.width,level.height)+2.2;
  const unitsPerPixel=Math.max(diameter/(this.width*.94),(diameter*Math.max(.68,Math.cos(this.orbit.polar))+2)/available);
  const halfH=this.height*unitsPerPixel/2,halfW=this.width*unitsPerPixel/2,offset=(this.height/2-(top+available/2))*unitsPerPixel;
  this.camera.left=-halfW;this.camera.right=halfW;this.camera.top=halfH+offset;this.camera.bottom=-halfH+offset;
  this.camera.updateProjectionMatrix();this.updateCamera();
 }
 updateCamera() {
  if(!this.center)return;const a=this.orbit.azimuth,p=this.orbit.polar,d=38;
  this.camera.position.set(this.center.x+Math.sin(a)*Math.sin(p)*d,Math.cos(p)*d,this.center.z+Math.cos(a)*Math.sin(p)*d);
  this.camera.lookAt(this.center);this.camera.updateMatrixWorld();
  this.canvas.dataset.azimuth=String(Math.round(a*180/Math.PI));this.canvas.dataset.polar=String(Math.round(p*180/Math.PI));
 }
 loop() {
  if(!this.alive)return;const now=performance.now(),dt=(now-this.lastFrame)/1000;this.lastFrame=now;
  if(!document.hidden&&!this.suspended){const moved=this.orbit.step(dt,this.reduceMotion.matches);if(moved)this.fit();else this.updateCamera();
   if(moved)this.canvas.dispatchEvent(new CustomEvent('camera-change'));
   this.environment?.update(now/1000,this.reduceMotion.matches);const dustActive=this.dust.update(now);
   const interval=this.environment?.wind?15:33;
   if(!this.contextLost&&(moved||dustActive||(!this.animating&&!this.reduceMotion.matches&&now-(this.lastAmbient||0)>interval))){this.renderer.render(this.scene,this.camera);this.lastAmbient=now;}
  }this.renderFrame=requestAnimationFrame(()=>this.loop());
 }
 set(data){this.data=data;this.animation=null;this.ensureLevel();this.fit();this.draw();}
 direction(action){return this.orbit.direction(action);}
 swipe(dx,dy){return this.orbit.direction(Math.abs(dx)>=Math.abs(dy)?(dx>0?'RIGHT':'LEFT'):(dy>0?'DOWN':'UP'));}
 orbitDrag(dx,dy){this.orbit.drag(dx,dy);}
 resetCamera(){this.orbit.reset();}
 setEffectHooks(hooks){this.effectHooks={...hooks};}
 resetEffects(){this.dust?.clear();}
 emitImpact(impact){if(!this.reduceMotion.matches)this.dust?.emit(impact,performance.now());this.notify('onImpact',impact.surfaceType,impact);}
 syncBlocks(poses,alpha,drop) {
  while(this.blocks.length<poses.length){const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(new Float32Array(108),3));
   const material=new THREE.MeshLambertMaterial({color:'#ddf0c3',flatShading:true,transparent:true});const mesh=new THREE.Mesh(geometry,material);mesh.frustumCulled=false;this.blocks.push(mesh);this.blockGroup.add(mesh);
  }
  this.blocks.forEach((mesh,i)=>{mesh.visible=i<poses.length&&alpha>.001;if(!mesh.visible)return;
   const {points,box}=poses[i],positions=mesh.geometry.attributes.position.array;let cursor=0;
   // The Y/Z swap reverses handedness: reverse the triangle winding as well.
   for(const [a,b,c,d] of FACES)for(const index of [a,c,b,a,d,c]){const p=points[index];positions[cursor++]=p[0];positions[cursor++]=p[2]-drop;positions[cursor++]=p[1];}
   mesh.geometry.attributes.position.needsUpdate=true;mesh.geometry.computeVertexNormals();mesh.material.color.set(i===1?'#b5cbf0':'#e0efc3');mesh.material.opacity=alpha*(box.active?1:.7);
  });
 }
 draw() {
  if(!this.data)return;this.ensureLevel();const {state,phase,fallenState}=this.data,anim=this.animation;
  this.tiles.forEach(({group,tile,r,c,bridge},i)=>{group.visible=tile!=='B'||!!state.bridges[bridge];group.position.y=0;group.scale.set(1,1,1);
   if(anim?.type==='settle'&&anim.impact.upright&&anim.impact.cells.some(([row,column])=>row===r&&column===c))group.position.y=-.05*Math.sin(Math.PI*anim.progress);
   if(tile==='O'&&((anim?.fragile?.[0]===r&&anim.fragile[1]===c)||(!anim&&phase==='LOST'&&fallenState?.orientation==='U'&&fallenState.anchor[0]===r&&fallenState.anchor[1]===c))){const t=anim?.progress??1;group.position.y=-t*t*5;group.scale.setScalar(1-t*.5);group.visible=t<1;}
   if(anim?.type==='reveal')group.position.y=-((1-Math.min(1,Math.max(0,anim.progress*1.8-i/this.tiles.length*.7)))**2)*2;
  });
  const displayState=anim?.state||state,poses=anim?.pose||boxesForState(displayState).map(box=>({box,points:cuboidVertices(box.x,box.y,box.w,box.d,box.h)}));
  let alpha=phase==='WON'||phase==='LOST'?0:1,drop=0;
  if(anim)alpha=anim.type==='split'?Math.abs(anim.progress*2-1):anim.type==='reveal'?Math.max(0,(anim.progress-.3)/.7):1;
  if(anim?.type==='fall'){drop=anim.progress**2*5;alpha=1-anim.progress;}
  this.syncBlocks(poses,alpha,drop);this.updateCamera();if(!this.contextLost)this.renderer.render(this.scene,this.camera);
 }
 dispose(){this.alive=false;cancelAnimationFrame(this.renderFrame);this.observer.disconnect();this.environment?.dispose();this.dust.dispose();this.blocks.forEach(mesh=>{mesh.geometry.dispose();mesh.material.dispose();});this.boxGeometry.dispose();this.materials.forEach(material=>material.dispose());this.renderer.dispose();}
}

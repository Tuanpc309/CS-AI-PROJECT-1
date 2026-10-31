import * as THREE from './vendor/three.module.js';
import {dustBurst,DUST_LIFETIME_MS} from './impact.js';
export class LandingDust {
 constructor(scene){
  this.geometry=new THREE.BoxGeometry(1,1,1);this.material=new THREE.MeshBasicMaterial({color:'#c1c8b8',transparent:true,opacity:.62,depthWrite:false});
  this.mesh=new THREE.InstancedMesh(this.geometry,this.material,32);this.mesh.frustumCulled=false;
  this.particles=Array(32).fill(null);this.cursor=0;this.dummy=new THREE.Object3D();scene.add(this.mesh);this.clear();
 }
 clear(){this.particles.fill(null);this.dummy.scale.setScalar(0);this.dummy.updateMatrix();for(let i=0;i<32;i++)this.mesh.setMatrixAt(i,this.dummy.matrix);this.mesh.instanceMatrix.needsUpdate=true;}
 emit(impact,now){for(const particle of dustBurst(impact)){this.particles[this.cursor]={...particle,birth:now};this.cursor=(this.cursor+1)%32;}this.update(now);}
 update(now){
  let active=false,dirty=false;
  this.particles.forEach((particle,index)=>{
   if(!particle)return;dirty=true;
   const t=Math.max(0,(now-particle.birth)/DUST_LIFETIME_MS),age=(now-particle.birth)/1000;
   if(t>=1){this.particles[index]=null;this.dummy.scale.setScalar(0);}
   else{active=true;this.dummy.position.set(particle.x+particle.vx*age,particle.y+particle.vy*age-.8*age*age,particle.z+particle.vz*age);this.dummy.scale.setScalar(particle.size*(1-t)**.7);this.dummy.rotation.set(age*2,age*3,age);}
   this.dummy.updateMatrix();this.mesh.setMatrixAt(index,this.dummy.matrix);
  });
  if(dirty)this.mesh.instanceMatrix.needsUpdate=true;return active||dirty;
 }
 dispose(){this.geometry.dispose();this.material.dispose();}
}

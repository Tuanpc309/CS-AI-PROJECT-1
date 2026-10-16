import * as THREE from './vendor/three.module.js';
export function windWeight(y,root,height){return Math.max(0,Math.min(1,(y-root)/height))**2;}
export function windOffset({y,root,height,x,z,time,phase=0,strength=.12,speed=.8}){
 const weight=windWeight(y,root,height);return weight===0?0:Math.sin(time*speed+x*.5+z*.5+phase)*strength*weight;
}
/** Per-instance root and height are in world space. Offset is converted back
 * into local coordinates before Three.js applies instanceMatrix. */
export function createWindMesh(plants){
 const geometry=new THREE.BoxGeometry(1,1,1);
 geometry.setAttribute('windData',new THREE.InstancedBufferAttribute(new Float32Array(plants.flatMap(p=>[p.root,p.height,p.phase,p.strength])),4));
 const uniforms={uWindTime:{value:0},uWindEnabled:{value:1}};
 const material=new THREE.MeshLambertMaterial({flatShading:true});
 material.onBeforeCompile=shader=>{
  Object.assign(shader.uniforms,uniforms);
  shader.vertexShader='attribute vec4 windData;\nuniform float uWindTime;\nuniform float uWindEnabled;\n'+shader.vertexShader;
  shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>',`#include <begin_vertex>
   vec3 windWorld=(instanceMatrix*vec4(transformed,1.0)).xyz;
   float windHeight=clamp((windWorld.y-windData.x)/max(windData.y,0.01),0.0,1.0);
   float windWave=sin(uWindTime*0.8+windWorld.x*0.5+windWorld.z*0.5+windData.z);
   float windAmount=windHeight*windHeight*windData.w*uWindEnabled;
   transformed.x+=windWave*windAmount/max(length(instanceMatrix[0].xyz),0.01);
   transformed.z+=cos(uWindTime*0.65+windData.z)*windAmount*0.35/max(length(instanceMatrix[2].xyz),0.01);
  `);
 };
 material.customProgramCacheKey=()=> 'bloxorz-anchored-wind-v1';
 const mesh=new THREE.InstancedMesh(geometry,material,plants.length),dummy=new THREE.Object3D();mesh.frustumCulled=false;
 plants.forEach((plant,index)=>{dummy.position.set(plant.x,plant.y,plant.z);dummy.scale.set(plant.w,plant.h,plant.d);dummy.updateMatrix();mesh.setMatrixAt(index,dummy.matrix);mesh.setColorAt(index,new THREE.Color(plant.color));});
 return {mesh,geometry,material,uniforms};
}

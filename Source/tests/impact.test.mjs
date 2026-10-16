import test from 'node:test';import assert from 'node:assert/strict';
import {cuboidVertices} from '../web/rolling.js';
import {landingInfo,settledPose,dustBurst,SETTLE_MS} from '../web/impact.js';
import {windWeight,windOffset,createWindMesh} from '../web/wind.js';
const pose=[{box:{active:true},points:cuboidVertices(1,1,1,1,2)}];
const level={grid:['FFFF','FFFF','FFFF'],biomeId:'forest'};
test('upright contact has one tile, the correct surface and eight bounded fragments',()=>{
 const impact=landingInfo(pose,level,'RIGHT');assert.equal(impact.upright,true);assert.deepEqual(impact.cells,[[1,1]]);assert.equal(impact.surfaceType,'grass');
 const dust=dustBurst(impact);assert.equal(dust.length,8);assert.ok(dust.every(p=>p.size<.1&&Math.abs(p.x-impact.position.x)<=.5&&p.vy>0));
 assert.equal(landingInfo(pose,{...level,grid:['FFFF','FGFF','FFFF']},'RIGHT'),null);
});
test('settle restores exactly, compresses at midpoint and follows a 0.05 tile sink',()=>{
 const original=structuredClone(pose),impact=landingInfo(pose,level,'RIGHT');assert.equal(SETTLE_MS,50);
 for(const t of [0,1])settledPose(pose,t,impact)[0].points.forEach((p,i)=>p.forEach((n,j)=>assert.ok(Math.abs(n-pose[0].points[i][j])<1e-10)));
 const middle=settledPose(pose,.5,impact)[0].points;assert.equal(Math.min(...middle.map(p=>p[2])),-.05);
 assert.ok(Math.max(...middle.map(p=>p[2]))<2);assert.deepEqual(pose,original);
});
test('wind anchors roots, bends tips and is spatially coherent',()=>{
 for(const time of [0,.5,4,100])assert.equal(windOffset({y:2,root:2,height:3,x:1,z:1,time}),0);
 assert.equal(windWeight(5,2,3),1);assert.equal(windWeight(1,2,3),0);
 assert.notEqual(windOffset({y:5,root:2,height:3,x:1,z:1,time:1}),0);
 const a=windOffset({y:5,root:2,height:3,x:1,z:1,time:1}),b=windOffset({y:5,root:2,height:3,x:1.001,z:1,time:1});assert.ok(Math.abs(a-b)<.001);
});
test('instanced vegetation shares one shader and updates time by uniform',()=>{
 const plants=[{x:1,y:1,z:1,w:.1,h:2,d:.1,color:'#99bb88',root:0,height:2,phase:0,strength:.1}];
 const wind=createWindMesh(plants);assert.equal(wind.mesh.count,1);assert.equal(wind.geometry.attributes.windData.count,1);
 const shader={uniforms:{},vertexShader:'#include <begin_vertex>'};wind.material.onBeforeCompile(shader);
 assert.ok(shader.vertexShader.includes('windHeight*windHeight'));assert.ok(shader.vertexShader.includes('instanceMatrix'));
 wind.uniforms.uWindTime.value=12;assert.equal(shader.uniforms.uWindTime.value,12);
 wind.uniforms.uWindEnabled.value=0;assert.equal(shader.uniforms.uWindEnabled.value,0);wind.geometry.dispose();wind.material.dispose();
});

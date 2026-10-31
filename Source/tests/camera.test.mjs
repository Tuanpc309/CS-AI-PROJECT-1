import test from 'node:test';
import assert from 'node:assert/strict';
import { OrbitCamera, MIN_POLAR, MAX_POLAR, screenDirection } from '../web/camera.js';

test('orbit accepts arbitrary full turns but clamps elevation above the floor',()=>{
 const orbit=new OrbitCamera();orbit.drag(10000,10000);assert.equal(orbit.targetPolar,MIN_POLAR);
 orbit.drag(-20000,-20000);assert.equal(orbit.targetPolar,MAX_POLAR);assert.ok(orbit.targetAzimuth>Math.PI*2);
});
test('damping is independent of frame rate and converges without overshoot',()=>{
 const a=new OrbitCamera(),b=new OrbitCamera();a.drag(100,30);b.drag(100,30);
 for(let i=0;i<60;i++)a.step(1/60);for(let i=0;i<30;i++)b.step(1/30);
 assert.ok(Math.abs(a.azimuth-b.azimuth)<1e-5);assert.ok(a.azimuth>=a.targetAzimuth);
 for(let i=0;i<100;i++)a.step(1/60);assert.equal(a.azimuth,a.targetAzimuth);
});
test('reduced motion still requests a render on the frame that snaps to target',()=>{
 const orbit=new OrbitCamera();orbit.drag(200,0);assert.equal(orbit.step(.016,true),true);
 assert.equal(orbit.azimuth,orbit.targetAzimuth);assert.equal(orbit.step(.016,true),false);
});
test('four camera quadrants map all four inputs bijectively',()=>{
 const orbit=new OrbitCamera(),actions=['UP','RIGHT','DOWN','LEFT'];
 const up=['UP','LEFT','DOWN','RIGHT'];
 for(let q=0;q<4;q++){
  orbit.azimuth=q*Math.PI/2;assert.equal(orbit.direction('UP'),up[q]);
  assert.equal(new Set(actions.map(action=>orbit.direction(action))).size,4);
  assert.equal(orbit.direction('SWITCH'),'SWITCH');
 }
});
test('mapping is periodic for negative angles and stable at diagonal boundaries',()=>{
 const orbit=new OrbitCamera(),actions=['UP','RIGHT','DOWN','LEFT'];
 for(const angle of [-9,-4,-1,0,.785,2,5,15]){
  orbit.azimuth=angle;const mapped=actions.map(a=>orbit.direction(a));
  orbit.azimuth=angle+Math.PI*8;assert.deepEqual(actions.map(a=>orbit.direction(a)),mapped);
 }
 orbit.azimuth=Math.PI/4;assert.deepEqual(actions.map(a=>orbit.direction(a)),actions);
});
test('reset follows the shortest arc after multiple turns',()=>{
 const orbit=new OrbitCamera();orbit.azimuth=10*Math.PI+.1;orbit.reset();
 assert.ok(Math.abs(orbit.targetAzimuth-orbit.azimuth)<Math.PI);
 orbit.step(.016,true);assert.equal(orbit.direction('RIGHT'),'RIGHT');
});
test('screen vectors project onto the world ground plane',()=>{
 assert.equal(screenDirection(0,-1,0),'UP');assert.equal(screenDirection(1,0,0),'RIGHT');
 assert.equal(screenDirection(0,-1,Math.PI/2),'LEFT');assert.equal(screenDirection(1,0,Math.PI/2),'UP');
});

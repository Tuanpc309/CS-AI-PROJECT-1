import test from 'node:test';
import assert from 'node:assert/strict';
import { BoardGestures } from '../web/gestures.js';
function setup(){const orbit=[],swipes=[];return {orbit,swipes,input:new BoardGestures((...v)=>orbit.push(v),(...v)=>swipes.push(v))};}
test('a one-finger swipe rolls once, a tap or jitter never rolls',()=>{
 const {input,orbit,swipes}=setup();input.down(1,0,0);input.move(1,40,30);input.up(1,40,30);
 input.down(1,0,0);input.up(1,5,3);assert.deepEqual(swipes,[[40,30]]);assert.deepEqual(orbit,[]);
});
test('right mouse drag orbits and never issues a move on release',()=>{
 const {input,orbit,swipes}=setup();input.down(1,100,100,2);input.move(1,160,120);input.up(1,160,120);
 assert.deepEqual(orbit,[[60,20]]);assert.deepEqual(swipes,[]);
});
test('two touches orbit by centroid delta; lifting either finger cannot roll',()=>{
 const {input,orbit,swipes}=setup();input.down(1,0,0);input.down(2,100,0);
 input.move(1,20,10);input.move(2,120,10);input.up(1,20,10);input.move(2,130,20);input.up(2,130,20);
 assert.deepEqual(orbit,[[10,5],[10,5],[10,10]]);assert.deepEqual(swipes,[]);
 input.down(3,0,0);input.up(3,30,0);assert.deepEqual(swipes,[[30,0]]);
});
test('pointer cancellation and lost capture clear pending swipes',()=>{
 const {input,swipes}=setup();input.down(1,0,0);input.cancel(1);input.up(1,100,0);
 assert.deepEqual(swipes,[]);assert.equal(input.down(2,0,0,1),false);
});

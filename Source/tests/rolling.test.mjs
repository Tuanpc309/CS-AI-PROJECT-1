import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ROLL_DURATION_MS, easeInOutQuad, cuboidVertices,
  boxesForState, pivotForMove, rollVertices,
} from '../web/rolling.js';

const EPSILON = 1e-10;
const EDGES = [[0,1], [1,2], [2,3], [3,0], [4,5], [5,6], [6,7], [7,4], [0,4], [1,5], [2,6], [3,7]];
const ACTIONS = ['UP', 'DOWN', 'LEFT', 'RIGHT'];
const close = (actual, expected, message) => assert.ok(Math.abs(actual - expected) < EPSILON,
  `${message}: expected ${expected}, got ${actual}`);
const distance = (a, b) => Math.hypot(...a.map((value, index) => value - b[index]));
const boxPoints = box => cuboidVertices(box.x, box.y, box.w, box.d, box.h);
const merged = (r, c, orientation) => ({mode: 'MERGED', anchor: [r, c], orientation});

function sameVertices(actual, expected) {
  assert.equal(actual.length, expected.length);
  const remaining = [...expected];
  for (const point of actual) {
    const index = remaining.findIndex(other => distance(point, other) < EPSILON);
    assert.ok(index >= 0, `Unexpected corner ${JSON.stringify(point)}`);
    remaining.splice(index, 1);
  }
}

function volume(points) {
  const edge = index => points[index].map((value, axis) => value - points[0][axis]);
  const [a, b, c] = [edge(1), edge(3), edge(4)];
  return Math.abs(a[0] * (b[1] * c[2] - b[2] * c[1])
    - a[1] * (b[0] * c[2] - b[2] * c[0])
    + a[2] * (b[0] * c[1] - b[1] * c[0]));
}

// Independent fixtures from Source/geometry.py's 12 authoritative transitions.
// Starting row/column is deliberately nonzero so origin-only errors cannot pass.
const TRANSITIONS = [
  ['U', 'UP',    5, 11, 'V'], ['U', 'DOWN',  8, 11, 'V'],
  ['U', 'LEFT',  7,  9, 'H'], ['U', 'RIGHT', 7, 12, 'H'],
  ['H', 'UP',    6, 11, 'H'], ['H', 'DOWN',  8, 11, 'H'],
  ['H', 'LEFT',  7, 10, 'U'], ['H', 'RIGHT', 7, 13, 'U'],
  ['V', 'UP',    6, 11, 'U'], ['V', 'DOWN',  9, 11, 'U'],
  ['V', 'LEFT',  7, 10, 'V'], ['V', 'RIGHT', 7, 12, 'V'],
];

for (const [orientation, action, row, col, nextOrientation] of TRANSITIONS) {
  test(`${orientation} + ${action}: 90 degree corners match engine state`, () => {
    const box = boxesForState(merged(7, 11, orientation))[0];
    const next = boxesForState(merged(row, col, nextOrientation))[0];
    sameVertices(rollVertices(boxPoints(box), box, action, Math.PI / 2), boxPoints(next));
  });

  test(`${orientation} + ${action}: rigid geometry, fixed edge and no floor penetration`, () => {
    const box = boxesForState(merged(7, 11, orientation))[0];
    const points = boxPoints(box);
    const {axis, pivot} = pivotForMove(box, action);
    const edgeIndices = points.flatMap((point, index) =>
      point[axis] === pivot && point[2] === 0 ? [index] : []);
    assert.equal(edgeIndices.length, 2, 'the pivot is exactly one bottom edge');
    for (const progress of [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]) {
      const rotated = rollVertices(points, box, action, easeInOutQuad(progress) * Math.PI / 2);
      close(volume(rotated), 2, 'cuboid volume is preserved');
      for (const [a, b] of EDGES) {
        close(distance(rotated[a], rotated[b]), distance(points[a], points[b]), 'edge length is preserved');
      }
      for (const index of edgeIndices) close(distance(rotated[index], points[index]), 0, 'pivot edge stays fixed');
      for (const point of rotated) assert.ok(point[2] >= -EPSILON, 'the rotating block stays above the floor');
    }
  });
}

test('merged state dimensions and anchor use [column, row, height]', () => {
  for (const [orientation, w, d, h] of [['U',1,1,2], ['H',2,1,1], ['V',1,2,1]]) {
    assert.deepEqual(boxesForState(merged(3, 5, orientation)),
      [{x:5, y:3, w, d, h, index:0, active:true}]);
  }
});

test('split cubes preserve identity and only the selected cube moves', () => {
  for (const active_cube of [0, 1]) {
    const state = {mode:'SPLIT', cubes:[[2,3], [8,10]], active_cube};
    const snapshot = structuredClone(state);
    const boxes = boxesForState(state);
    assert.deepEqual(boxes, [
      {x:3,y:2,w:1,d:1,h:1,index:0,active:active_cube===0},
      {x:10,y:8,w:1,d:1,h:1,index:1,active:active_cube===1},
    ]);
    for (const action of ACTIONS) {
      const [dr, dc] = {UP:[-1,0], DOWN:[1,0], LEFT:[0,-1], RIGHT:[0,1]}[action];
      for (const box of boxes) {
        const points = boxPoints(box);
        const rotated = box.active ? rollVertices(points, box, action, Math.PI/2) : points;
        const expected = cuboidVertices(box.x + (box.active ? dc : 0),
          box.y + (box.active ? dr : 0), 1, 1, 1);
        sameVertices(rotated, expected);
        close(volume(rotated), 1, 'split cube volume is preserved');
      }
    }
    assert.deepEqual(state, snapshot, 'state is unchanged');
  }
});

test('roll does not mutate points or box and returns independent vertices', () => {
  const box = Object.freeze({x:-3,y:-5,w:2,d:1,h:1});
  const points = Object.freeze(boxPoints(box).map(Object.freeze));
  const snapshot = structuredClone(points);
  for (const action of ACTIONS) {
    const rotated = rollVertices(points, box, action, Math.PI/4);
    assert.notEqual(rotated, points);
    rotated.forEach((point, index) => assert.notEqual(point, points[index]));
    assert.deepEqual(points, snapshot);
    sameVertices(rollVertices(points, box, action, 0), points);
  }
});

test('vertices support an explicit base elevation', () => {
  assert.deepEqual(cuboidVertices(2,3,1,2,4,-2), [
    [2,3,-2], [3,3,-2], [3,5,-2], [2,5,-2],
    [2,3,2], [3,3,2], [3,5,2], [2,5,2],
  ]);
});

test('pivot rejects non-movement actions instead of silently rolling down', () => {
  assert.throws(() => pivotForMove({x:0,y:0,w:1,d:1}, 'SWITCH'), RangeError);
});

test('easing has exact endpoints, symmetry, monotonicity and 220 ms duration', () => {
  assert.equal(ROLL_DURATION_MS, 220);
  assert.ok(ROLL_DURATION_MS >= 150 && ROLL_DURATION_MS <= 250);
  assert.equal(easeInOutQuad(0), 0);
  assert.equal(easeInOutQuad(0.5), 0.5);
  assert.equal(easeInOutQuad(1), 1);
  assert.equal(easeInOutQuad(-0.1), 0);
  assert.equal(easeInOutQuad(1.1), 1);
  assert.equal(easeInOutQuad(0.25), 0.125);
  assert.equal(easeInOutQuad(0.75), 0.875);
  for (let index=1; index<=100; index++) {
    const t=index/100;
    assert.ok(easeInOutQuad(t) >= easeInOutQuad(t-0.01));
    close(easeInOutQuad(t) + easeInOutQuad(1-t), 1, 'easing symmetry');
  }
});

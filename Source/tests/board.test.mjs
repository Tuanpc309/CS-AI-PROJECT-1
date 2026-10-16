import test from 'node:test';
import assert from 'node:assert/strict';
import { Board } from '../web/board.js';

const SAMPLE_TIMES = [0, .25, .5, .75, 1];

function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}

function merged(orientation = 'U', anchor = [2, 2], bridges = [false]) {
  return { mode: 'MERGED', orientation, anchor, cubes: [], active_cube: null, bridges };
}

function split(active = 0, bridges = [true]) {
  return { mode: 'SPLIT', orientation: null, anchor: null,
    cubes: [[1, 1], [4, 4]], active_cube: active, bridges };
}

function snapshot(state, phase = 'PLAYING', extra = {}) {
  return freeze({
    state, phase, fallenState: null,
    level: { grid: ['######', '######', '####O#', '######', '######'], goal: [2, 4] },
    ...extra,
  });
}

// Exercise the real animation lifecycle without needing Canvas or a browser.
function harness({ reducedMotion = false } = {}) {
  const board = Object.create(Board.prototype);
  const frames = [], durations = [];
  Object.assign(board, {
    canvas: { dataset: { motion: 'idle' } },
    reduceMotion: { matches: reducedMotion },
    data: null, animation: null, frame: null, _moving: false,
    draw() {
      frames.push({ data: this.data, motion: this.canvas.dataset.motion,
        animation: this.animation ? structuredClone(this.animation) : null });
    },
    async tween(duration, update) {
      durations.push(duration);
      SAMPLE_TIMES.forEach(update);
    },
  });
  return { board, frames, durations };
}

function bounds(pose) {
  const points = pose.flatMap(item => item.points);
  return [0, 1, 2].map(axis => [
    Math.min(...points.map(point => point[axis])),
    Math.max(...points.map(point => point[axis])),
  ]);
}

function near(actual, expected, message = 'coordinates differ') {
  const a = actual.flat(Infinity), b = expected.flat(Infinity);
  assert.equal(a.length, b.length, message);
  a.forEach((value, index) => assert.ok(Math.abs(value - b[index]) < 1e-10,
    `${message}: coordinate ${index}, expected ${b[index]}, received ${value}`));
}

function assertIdle(board) {
  assert.equal(board.animating, false);
  assert.equal(board.animation, null);
  assert.equal(board.canvas.dataset.motion, 'idle');
}

test('a move rolls for 220 ms, commits after landing, then settles for 50 ms', async () => {
  const { board, frames, durations } = harness();
  const previous = snapshot(merged());
  const next = snapshot(merged('H', [2, 3], [true]));

  assert.equal(await board.animate(previous, next, 'RIGHT'), true);

  assert.deepEqual(durations, [220, 50]);
  const roll = frames.filter(frame => frame.animation?.type === 'roll');
  assert.equal(roll.length, SAMPLE_TIMES.length);
  for (const frame of roll) {
    assert.equal(frame.data, previous, 'logical state must remain the previous snapshot during roll');
    assert.deepEqual(frame.data.state.bridges, [false], 'bridge must not toggle before landing');
    assert.equal(frame.motion, 'rolling');
  }
  near(bounds(roll[0].animation.pose), [[2, 3], [2, 3], [0, 2]]);
  near(bounds(roll.at(-1).animation.pose), [[3, 5], [2, 3], [0, 1]], '90-degree landing');
  assert.equal(frames.at(-1).data, next);
  assert.deepEqual(board.data.state.bridges, [true]);
  assertIdle(board);
});

test('impact hooks fire once after landing and input stays locked through settle',async()=>{
 const {board,frames}=harness(),events=[];
 board.effectHooks={onRollStart:()=>events.push(['roll',board.data]),onImpact:surface=>events.push(['impact',surface,board.data])};
 const previous=snapshot(merged('H')),next=snapshot(merged('U',[2,4]));
 board.tween=async(duration,update)=>{if(duration===50)assert.equal(board.animating,true);SAMPLE_TIMES.forEach(update);};
 await board.animate(previous,next,'RIGHT');assert.deepEqual(events.map(event=>event[0]),['roll','impact']);
 assert.equal(events[1][1],'fragile');assert.equal(events[1][2],next);
 assert.ok(frames.some(frame=>frame.animation?.type==='settle'&&frame.animation.impact.upright));assertIdle(board);
});

test('falling into void/hole and SWITCH never emit a landing impact',async()=>{
 for(const [phase,action] of [['WON','RIGHT'],['LOST','RIGHT'],['PLAYING','SWITCH']]){
  const {board}=harness(),events=[];board.effectHooks={onImpact:()=>events.push('impact')};
  await board.animate(snapshot(merged('H')),snapshot(merged('U',[2,4]),phase),action);assert.deepEqual(events,[]);
 }
});

for (const [phase, fallDuration] of [['WON', 380], ['LOST', 420]]) {
  test(`${phase}: complete the 220 ms roll before the ${fallDuration} ms fall`, async () => {
    const { board, frames, durations } = harness();
    const previous = snapshot(merged('H'));
    const landed = merged('U', [2, 4], [true]);
    const next = snapshot(phase === 'WON' ? landed : previous.state, phase,
      { fallenState: phase === 'LOST' ? landed : null });

    assert.equal(await board.animate(previous, next, 'RIGHT'), true);

    assert.deepEqual(durations, [220, fallDuration]);
    assert.equal(durations.reduce((sum, duration) => sum + duration, 0), 220 + fallDuration);
    const roll = frames.filter(frame => frame.animation?.type === 'roll');
    const falling = frames.filter(frame => frame.animation?.type === 'fall');
    assert.equal(roll.length, SAMPLE_TIMES.length);
    assert.equal(falling.length, SAMPLE_TIMES.length);
    assert.ok(roll.every(frame => frame.data === previous));
    assert.ok(falling.every(frame => frame.data === next && frame.motion === 'falling'));
    assert.equal(frames.indexOf(falling[0]), frames.indexOf(roll.at(-1)) + 1,
      'the fall must start after the final roll sample');
    near(bounds(roll.at(-1).animation.pose), [[4, 5], [2, 3], [0, 2]], 'upright landing');
    for (const frame of falling) {
      near(frame.animation.pose.flatMap(item => item.points),
        roll.at(-1).animation.pose.flatMap(item => item.points), 'fall keeps the fully rolled pose');
      assert.equal(frame.animation.progress, SAMPLE_TIMES[falling.indexOf(frame)]);
    }
    assert.deepEqual(falling[0].animation.fragile, phase === 'LOST' ? [2, 4] : null);
    assert.equal(board.data, next);
    assertIdle(board);
  });
}

test('split starts only after a full roll, then reveals the two cubes over 150 ms', async () => {
  const { board, frames, durations } = harness();
  const previous = snapshot(merged('H'));
  const next = snapshot(split());

  assert.equal(await board.animate(previous, next, 'RIGHT'), true);

  assert.deepEqual(durations, [220, 50, 150]);
  const roll = frames.filter(frame => frame.animation?.type === 'roll');
  const splitting = frames.filter(frame => frame.animation?.type === 'split');
  assert.ok(roll.every(frame => frame.data === previous));
  assert.ok(frames.indexOf(splitting[0]) > frames.indexOf(roll.at(-1)));
  assert.ok(frames.some(frame=>frame.animation?.type==='settle'));
  near(bounds(roll.at(-1).animation.pose), [[4, 5], [2, 3], [0, 2]]);
  for (const frame of splitting) {
    assert.equal(frame.data, next);
    assert.equal(frame.motion, 'splitting');
    if (frame.animation.progress < .5) {
      assert.equal(frame.animation.state.mode, 'MERGED');
      near(frame.animation.pose.flatMap(item => item.points),
        roll.at(-1).animation.pose.flatMap(item => item.points));
    } else {
      assert.equal(frame.animation.state.mode, 'SPLIT');
      assert.equal(frame.animation.pose.length, 2);
      near(bounds([frame.animation.pose[0]]), [[1, 2], [1, 2], [0, 1]]);
      near(bounds([frame.animation.pose[1]]), [[4, 5], [4, 5], [0, 1]]);
    }
  }
  assert.equal(board.data, next);
  assertIdle(board);
});

test('SWITCH changes the active cube immediately without rolling or tweening', async () => {
  const { board, frames, durations } = harness();
  const previous = snapshot(split(0));
  const next = snapshot(split(1));

  assert.equal(await board.animate(previous, next, 'SWITCH'), true);

  assert.deepEqual(durations, []);
  assert.equal(board.data, next);
  assert.equal(board.data.state.active_cube, 1);
  assert.ok(frames.every(frame => frame.animation === null));
  assertIdle(board);
});

for (const outcome of ['move', 'win', 'loss', 'split']) {
  test(`reduced motion commits ${outcome} immediately without roll, fall, or split tween`, async () => {
    const { board, frames, durations } = harness({ reducedMotion: true });
    const previous = snapshot(merged('H'));
    const next = outcome === 'split' ? snapshot(split()) : snapshot(merged('U', [2, 4]),
      outcome === 'win' ? 'WON' : outcome === 'loss' ? 'LOST' : 'PLAYING');

    assert.equal(await board.animate(previous, next, 'RIGHT'), true);

    assert.deepEqual(durations, []);
    assert.equal(board.data, next);
    assert.ok(frames.every(frame => frame.data === next && frame.animation === null));
    assertIdle(board);
  });
}

test('a concurrent animate call is rejected without replacing the active move', async () => {
  const { board, frames, durations } = harness();
  const previous = snapshot(merged());
  const next = snapshot(merged('H', [2, 3]));
  let finish;
  board.tween = (duration, update) => {
    durations.push(duration);
    if(duration!==220){SAMPLE_TIMES.forEach(update);return Promise.resolve();}
    update(0);
    return new Promise(resolve => { finish = () => { update(1); resolve(); }; });
  };
  const activeMove = board.animate(previous, next, 'RIGHT');
  try {
    assert.equal(board.animating, true);
    assert.equal(board.data, previous);
    const frameCount = frames.length;
    assert.equal(await board.animate(next, snapshot(merged('U', [2, 5])), 'RIGHT'), false);
    assert.deepEqual(durations, [220]);
    assert.equal(frames.length, frameCount);
    assert.equal(board.data, previous);
    assert.equal(board.canvas.dataset.motion, 'rolling');
  } finally {
    finish();
    await activeMove;
  }
  assert.equal(board.data, next);
  assertIdle(board);
});

test('an existing scheduled animation frame also blocks animate', async () => {
  const { board, frames, durations } = harness();
  const previous = snapshot(merged());
  board.data = previous;
  board.frame = 123;

  assert.equal(await board.animate(previous, snapshot(merged('H', [2, 3])), 'RIGHT'), false);

  assert.equal(board.data, previous);
  assert.equal(board.frame, 123);
  assert.deepEqual(durations, []);
  assert.deepEqual(frames, []);
});

for (const rejectionStage of ['roll', 'fall']) {
  test(`a rejected ${rejectionStage} tween propagates the error and unlocks the renderer`, async () => {
    const { board } = harness();
    const previous = snapshot(merged('H'));
    const next = snapshot(merged('U', [2, 4]), 'WON');
    const failure = new Error(`failed ${rejectionStage} frame`);
    let calls = 0;
    board.tween = async (duration, update) => {
      calls++;
      update(0);
      if (calls === (rejectionStage === 'roll' ? 1 : 2)) throw failure;
      update(1);
    };

    await assert.rejects(board.animate(previous, next, 'RIGHT'), error => error === failure);

    assertIdle(board);
    board.tween = async (duration, update) => update(1);
    const recovery = snapshot(merged('U', [2, 4]));
    assert.equal(await board.animate(previous, recovery, 'RIGHT'), true,
      'a later move must be accepted after the rejected tween');
    assert.equal(board.data, recovery);
    assertIdle(board);
  });
}

import test from 'node:test';
import assert from 'node:assert/strict';
import {ALGORITHMS, renderSolutions, solutionKey} from '../web/solutions.js';

function result(overrides = {}) {
  return {algorithm:'BFS', cost_policy:'UNIT', status:'FOUND', actions:['RIGHT','RIGHT'],
    solution_length:2, solution_cost:2, movement_count:2, selection_count:0,
    preprocessing_time_seconds:0, search_time_seconds:.0006, total_time_seconds:.0006,
    peak_memory_bytes:4096, expanded_nodes:2, metadata:{metrics_available:true}, ...overrides};
}
function panel(value, options = {}) {
  return renderSolutions({solver:{results:{'BFS:UNIT':value}, origin_moves:3}, ...options});
}

test('all four algorithms and both cost policies are offered without mixing result keys', () => {
  const html = renderSolutions();
  for (const algorithm of ALGORITHMS) assert.match(html, new RegExp(`data-action="solve" data-algorithm="${algorithm}"`));
  assert.match(html, /value="UNIT" selected/);
  assert.match(html, /value="FRAGILE_PENALTY"/);
  assert.equal(solutionKey('ASTAR','FRAGILE_PENALTY'), 'ASTAR:FRAGILE_PENALTY');
  const weighted = renderSolutions({policy:'FRAGILE_PENALTY', solver:{results:{'BFS:UNIT':result()}}});
  assert.doesNotMatch(weighted, /Có lời giải/);
});

test('found path preserves action order including cube selection and exposes measured counts', () => {
  const html = panel(result({actions:['UP','SWITCH','LEFT'],solution_length:3,solution_cost:5,movement_count:2,selection_count:1}));
  assert.match(html, /Vị trí xuất phát: sau 3 thao tác/);
  assert.ok(html.indexOf('title="UP"') < html.indexOf('title="SWITCH"'));
  assert.ok(html.indexOf('title="SWITCH"') < html.indexOf('title="LEFT"'));
  assert.match(html, /⇄/);
  assert.match(html, /Đổi khối: 1/);
  assert.match(html, /data-action="replay" data-algorithm="BFS">/);
});

test('a zero-action goal is a valid playable result, not an absent solution', () => {
  const html = panel(result({actions:[],solution_length:0,solution_cost:0,movement_count:0}));
  assert.match(html, /Đã ở ô đích/);
  assert.match(html, /<b>0<\/b> thao tác/);
  assert.match(html, /data-action="replay" data-algorithm="BFS">/);
});

test('NO_SOLUTION has no invented zero length or cost and cannot replay', () => {
  const html = panel(result({status:'NO_SOLUTION',actions:[],solution_length:0,solution_cost:0}));
  assert.match(html, /Đã duyệt hết: không có lời giải/);
  assert.match(html, /data-status="NO_SOLUTION">Vô nghiệm/);
  assert.match(html, /Vô nghiệm<\/span><\/td><td>—<\/td><td>—<\/td>/);
  assert.match(html, /data-action="replay" data-algorithm="BFS" disabled data-locked="true" data-unavailable="true"/);
});

test('timeout remains undecided and worker errors do not display default zero measurements', () => {
  const timeout = panel(result({status:'TIMEOUT',actions:[],solution_length:null,solution_cost:null}));
  assert.match(timeout, /Chưa thể kết luận màn vô nghiệm/);
  const error = panel(result({status:'ERROR',actions:[],metadata:{metrics_available:false,message:'Worker failed'},total_time_seconds:0,peak_memory_bytes:0,expanded_nodes:0}));
  assert.match(error, /Lỗi<\/span><\/td><td>—<\/td><td>—<\/td><td>—<\/td><td>—<\/td><td>—<\/td>/);
  assert.match(error, /Tìm kiếm: — s/);
});

test('unsupported memory measurement is a dash even when the serialized default is zero', () => {
  const html = panel(result({peak_memory_bytes:0,metadata:{memory_available:false}}));
  assert.match(html, /Lượt này chưa có số liệu peak Python memory/);
  assert.doesNotMatch(html, /<td>0\.000<\/td>/);
});

test('untrusted errors and unknown action labels are escaped', () => {
  const payload = '<img src=x onerror="alert(1)">';
  const error = panel(result({status:'ERROR',metadata:{message:payload}}));
  assert.doesNotMatch(error, /<img/);
  assert.match(error, /&lt;img src=x onerror=&quot;alert\(1\)&quot;&gt;/);
  const unknown = panel(result({actions:[payload]}));
  assert.doesNotMatch(unknown, /<img/);
  assert.doesNotThrow(() => panel(result({actions:['__proto__', 'constructor', null]})));
});

test('busy state blocks restarting/replaying stale results while leaving cancel available', () => {
  const html = renderSolutions({solver:{results:{'BFS:UNIT':result()}, busy:true, active:{algorithm:'BFS',cost_policy:'UNIT'}}});
  assert.match(html, /Đang tìm lời giải/);
  assert.match(html, /data-action="solve" data-algorithm="BFS" disabled/);
  assert.match(html, /data-action="solve-cancel" data-allow-busy="true">Dừng tìm kiếm/);
  assert.doesNotMatch(html, /data-action="replay"/);
  const queued = panel(result(), {runAll:true});
  assert.match(queued, /data-action="replay" data-algorithm="BFS" disabled/);
});

test('browser runtime does not offer an unsupported cancellation action', () => {
  const html = renderSolutions({solver:{busy:true,can_cancel:false,active:{algorithm:'BFS',cost_policy:'UNIT'}}});
  assert.doesNotMatch(html, /data-action="solve-cancel"/);
  assert.match(html, /data-action="solve-all" disabled data-locked="true"/);
  assert.match(html, /id="solution-policy" disabled data-locked="true"/);
});

test('the selected algorithm has a collapsible explanation with its actual search strategy', () => {
  const strategies = {BFS:'hàng đợi', DFS:'ngăn xếp', UCS:'chi phí g nhỏ nhất', ASTAR:'f = g + h'};
  for (const algorithm of ALGORITHMS) {
    const html = renderSolutions({selectedAlgorithm:algorithm});
    assert.match(html, /<details class="solution-explanation"><summary>/);
    assert.ok(html.includes(strategies[algorithm]));
    assert.match(html, /không phải thứ tự tất cả trạng thái đã duyệt/);
  }
  const weighted = renderSolutions({selectedAlgorithm:'UCS',policy:'FRAGILE_PENALTY'});
  assert.match(weighted, /bước mới đi vào gạch cam có cost 3/);
  assert.match(weighted, /Đổi cube luôn có cost 1/);
  assert.match(weighted, /không phải RAM của cả trình duyệt/);
});

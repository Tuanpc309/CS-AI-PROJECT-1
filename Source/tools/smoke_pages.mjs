/** Exercise the deployed Python engine under real WebAssembly, without a server. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';

try{
  const root=resolve(process.argv[2]||'dist');
  const html=await readFile(join(root,'index.html'),'utf8');
  assert.match(html,/<meta name="bloxorz-runtime" content="browser">/);
  assert.doesNotMatch(html,/(?:href|src)="\//);
  const runtime=join(root,'runtime','pyodide');
  const {loadPyodide}=await import(pathToFileURL(join(runtime,'pyodide.mjs')));
  const python=await loadPyodide({indexURL:runtime});
  python.unpackArchive(new Uint8Array(await readFile(join(root,'engine.zip'))),'zip',{extractDir:'/app'});
  const proofs=JSON.parse(await readFile(new URL('../web/levels/solutions.json',import.meta.url),'utf8'));
  python.globals.set('_proofs',JSON.stringify(proofs));
  await python.runPythonAsync(`
import json, sys
sys.path.insert(0, '/app/Source')
from browser_api import browser_dispatch

def call(path, body, token=''):
    return json.loads(browser_dispatch(json.dumps(dict(path=path, body=body, token=token))))

def command(token, name, **data):
    response = call('/api/command', dict(command=name, **data), token)
    assert response['status'] == 200, response
    return response['body']

for key, proof in json.loads(_proofs).items():
    response = call('/api/session', dict(level=key))
    assert response['status'] == 200, response
    session = response['body']
    assert len(session['catalog']) == 43
    assert session['level']['optimal'] == proof['optimal'], key
    for action in proof['solution']:
        state = command(session['session'], 'move', action=action)
    assert state['phase'] == 'WON', key
    assert state['moves'] == proof['optimal'], key
    assert state['stars'] == 3, key

first = call('/api/session', dict(level='basic_01'))['body']
second = call('/api/session', dict(level='basic_01'))['body']
assert first['solver']['can_cancel'] is False
token = first['session']
assert token != second['session']
assert command(token, 'move', action='RIGHT')['moves'] == 1
assert command(second['session'], 'state')['moves'] == 0
assert command(token, 'pause')['phase'] == 'PAUSED'
assert command(token, 'move', action='RIGHT')['moves'] == 1
command(token, 'resume')
assert command(token, 'move', action='RIGHT')['phase'] == 'WON'
state = command(token, 'undo')
assert (state['phase'], state['moves'], state['undos']) == ('PLAYING', 1, 4)
assert command(token, 'restart')['undos'] == 5
assert call('/api/command', dict(command='state'), 'bad')['status'] == 410
assert call('/api/session', dict(level=[]))['status'] == 400
assert call('/api/command', dict(command='load', level=[]), token)['status'] == 400
assert call('/api/session', [])['status'] == 400
assert call('/api/missing', {})['status'] == 404

# The same protocol now exposes each real Python solver, not prebuilt witnesses.
command(token, 'move', action='RIGHT')
memory_modes = {}
for algorithm in ('BFS', 'DFS', 'UCS', 'ASTAR'):
    state = command(token, 'solve', algorithm=algorithm, cost_policy='UNIT')
    result = state['solver']['results'][algorithm + ':UNIT']
    assert not state['solver']['busy'], state
    assert state['solver']['can_cancel'] is False, state
    assert result['status'] == 'FOUND', result
    assert result['actions'] == ['RIGHT'], result
    assert result['solution_length'] == result['solution_cost'] == 1
    assert state['solver']['origin_moves'] == 1
    assert result['metadata']['replay_verified'] is True
    memory_modes[algorithm] = result['metadata']['memory_available']
    if not result['metadata']['memory_available']:
        assert result['peak_memory_bytes'] is None
    state = command(token, 'replay_start', algorithm=algorithm, cost_policy='UNIT')
    assert state['moves'] == 1
    while state['replay']['active']:
        state = command(token, 'replay_step')
    assert state['phase'] == 'WON' and state['moves'] == 2
assert len(state['solver']['results']) == 4

weighted = call('/api/session', dict(level='fragile_02'))['body']['session']
for algorithm in ('UCS', 'ASTAR'):
    state = command(weighted, 'solve', algorithm=algorithm, cost_policy='FRAGILE_PENALTY')
    result = state['solver']['results'][algorithm + ':FRAGILE_PENALTY']
    assert result['status'] == 'FOUND', result
    assert result['solution_cost'] == result['solution_length'] == 11, result
    state = command(weighted, 'replay_start', algorithm=algorithm, cost_policy='FRAGILE_PENALTY')
    while state['replay']['active']:
        state = command(weighted, 'replay_step')
    assert state['phase'] == 'WON'

split = call('/api/session', dict(level='split_02'))['body']['session']
state = command(split, 'solve', algorithm='ASTAR')
assert state['solver']['results']['ASTAR:UNIT']['selection_count'] >= 2
state = command(split, 'replay_start', algorithm='ASTAR')
while state['replay']['active']:
    state = command(split, 'replay_step')
assert state['phase'] == 'WON'

unsolvable = call('/api/session', dict(level='no_solution_02'))['body']['session']
state = command(unsolvable, 'solve', algorithm='BFS')
assert state['solver']['results']['BFS:UNIT']['status'] == 'NO_SOLUTION'
assert state['solver']['results']['BFS:UNIT']['solution_length'] is None
limited = call('/api/session', dict(level='basic_01'))['body']['session']
state = command(limited, 'solve', algorithm='BFS', time_limit_seconds=0)
assert state['solver']['results']['BFS:UNIT']['status'] == 'TIMEOUT'
state = command(limited, 'solve', algorithm='BFS', memory_limit_bytes=0)
assert state['solver']['results']['BFS:UNIT']['status'] == 'MEMORY_LIMIT'
print('WASM solver memory availability:', json.dumps(memory_modes, sort_keys=True))
`);
  console.log('Pages WASM smoke: 30 optimal wins, rules/session/undo checks, all four solvers from current state, retained results, replay, weighted cost, no-solution and budget statuses passed.');
}catch(error){console.error(error.message);process.exitCode=1;}

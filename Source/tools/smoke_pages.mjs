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
`);
  console.log('Pages WASM smoke: 30 optimal wins, split/switch/fragile/bridge rules, session isolation, pause, undo, restart and invalid requests passed.');
}catch(error){console.error(error.message);process.exitCode=1;}

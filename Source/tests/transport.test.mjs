import test from 'node:test';
import assert from 'node:assert/strict';
let version=0;
class FakeWorker extends EventTarget{
  static instances=[];
  constructor(){super();this.messages=[];FakeWorker.instances.push(this);}
  postMessage(data){this.messages.push(data);}
  terminate(){this.terminated=true;}
  reply(data){this.dispatchEvent(new MessageEvent('message',{data}));}
}
async function setup(t,mode='browser'){
  const original={Worker:globalThis.Worker,document:globalThis.document,fetch:globalThis.fetch};
  globalThis.Worker=FakeWorker;FakeWorker.instances=[];
  globalThis.document={querySelector:()=>mode==='browser'?{content:'browser'}:null};
  t.after(()=>{for(const worker of FakeWorker.instances)worker.dispatchEvent(new Event('error'));Object.assign(globalThis,original);});
  return import(`../web/transport.js?case=${++version}`);
}
test('static requests use one worker and keep concurrent responses isolated',async t=>{
  const {requestGame}=await setup(t);
  const first=requestGame('/api/session',{},''),second=requestGame('/api/command',{command:'state'},'two');
  const worker=FakeWorker.instances[0];assert.equal(FakeWorker.instances.length,1);
  const [a,b]=worker.messages;assert.equal(b.token,'two');
  worker.reply({id:b.id,status:200,body:{moves:9}});worker.reply({id:a.id,status:200,body:{moves:0}});
  assert.deepEqual(await first,{moves:0});assert.deepEqual(await second,{moves:9});
});
test('bootstrap progress reaches the loading UI',async t=>{
  const {requestGame}=await setup(t),progress=[];
  const pending=requestGame('/api/session',{},'',value=>progress.push(value)),worker=FakeWorker.instances[0];
  worker.reply({progress:'Đang tải…'});worker.reply({id:worker.messages[0].id,status:200,body:{}});
  await pending;assert.deepEqual(progress,['Đang tải…']);
});
test('an expired or failed engine is discarded and a retry creates a clean worker',async t=>{
  const {requestGame}=await setup(t);
  const pending=requestGame('/api/command',{},'expired'),worker=FakeWorker.instances[0];
  const rejected=assert.rejects(pending,error=>error.status===410);
  worker.reply({id:worker.messages[0].id,status:410,body:{error:'expired'}});
  await rejected;assert.equal(worker.terminated,true);
  const retry=requestGame('/api/session',{},''),fresh=FakeWorker.instances[1];
  fresh.reply({id:fresh.messages[0].id,status:200,body:{session:'new'}});
  assert.equal((await retry).session,'new');
});
test('worker load errors reject pending commands instead of leaving the UI locked',async t=>{
  const {requestGame}=await setup(t),pending=requestGame('/api/session',{},'');
  const rejected=assert.rejects(pending,error=>error.status===410);
  FakeWorker.instances[0].dispatchEvent(new Event('error'));await rejected;
});
test('local mode keeps the server protocol and propagates HTTP status',async t=>{
  const {requestGame}=await setup(t,'server');let sent;
  globalThis.fetch=async(path,options)=>{sent={path,options};return {ok:false,status:400,json:async()=>({error:'bad move'})};};
  await assert.rejects(requestGame('/api/command',{command:'move'},'token'),error=>error.status===400&&error.message==='bad move');
  assert.equal(sent.path,'/api/command');assert.equal(sent.options.headers['X-Session'],'token');
  assert.equal(sent.options.body,'{"command":"move"}');assert.equal(FakeWorker.instances.length,0);
});

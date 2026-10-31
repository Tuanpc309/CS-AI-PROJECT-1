import test from 'node:test';
import assert from 'node:assert/strict';
import { ProfileStore, PROFILE_PREFIX,canPlay,unlockedFor } from '../web/profiles.js';
import {RunClock,formatTime} from '../web/run-clock.js';
class Storage{
 constructor(){this.values=new Map();}
 get length(){return this.values.size;}key(i){return [...this.values.keys()][i]??null;}
 getItem(key){return this.values.get(key)??null;}setItem(key,value){this.values.set(key,value);}
}
const catalog=Array.from({length:30},(_,i)=>({id:`campaign_${String(i+1).padStart(2,'0')}`,number:i+1,collection:'campaign'}));
function setup(storage=new Storage()){let id=0;return {storage,store:new ProfileStore(storage,{id:()=>`user-${++id}`,now:()=> '2026-10-16T12:00:00.000Z'})};}
function win(level=1,moves=8,stars=3,timeMs=10000){return {level:catalog[level-1],moves,stars,timeMs,catalog};}
test('creating two slots and switching never shares progress',async()=>{
 const {store}=setup();const a=await store.create('An','fox'),b=await store.create('Bình','moon');
 await store.select(a.id,catalog);await store.recordWin(a.id,win());
 assert.equal(store.currentUser.unlockedLevel,2);await store.select(b.id,catalog);
 assert.deepEqual(store.currentUser.levelStats,{});assert.equal(store.currentUser.unlockedLevel,1);
 await store.select(a.id,catalog);assert.equal(store.currentUser.levelStats.campaign_01.bestMoves,8);
 assert.ok(a.createdAt&&a.lastPlayed);assert.equal(store.list().length,2);
});
test('best moves, stars and best time improve independently and survive reload',async()=>{
 const {store,storage}=setup(),a=await store.create('An','sprout');
 await store.recordWin(a.id,win(1,8,2,10000));await store.recordWin(a.id,win(1,6,3,14000));await store.recordWin(a.id,win(1,10,1,7000));
 const reload=setup(storage).store,stat=reload.read(a.id).levelStats.campaign_01;
 assert.equal(stat.bestMoves,6);assert.equal(stat.stars,3);assert.equal(stat.bestTimeMs,7000);
 assert.equal(stat.lastMoves,10);assert.equal(stat.lastTimeMs,7000);assert.equal(stat.plays,3);
 assert.ok(stat.completedAt&&stat.lastCompletedAt);assert.equal(reload.currentUser,null);
});
test('writes merge the newest saved result rather than a stale selected snapshot',async()=>{
 const {store,storage}=setup(),a=await store.create('An','star');const other=setup(storage).store;
 await store.select(a.id,catalog);await other.select(a.id,catalog);
 await store.recordWin(a.id,win(1,5,3,1000));await other.recordWin(a.id,win(1,20,1,2000));
 assert.equal(store.currentUser.levelStats.campaign_01.bestMoves,5);assert.equal(store.currentUser.levelStats.campaign_01.stars,3);
});
test('per-slot writes use Web Locks when available',async()=>{
 const calls=[],storage=new Storage();const store=new ProfileStore(storage,{id:()=> 'a',locks:{request:async(name,fn)=>{calls.push(name);return fn();}}});
 await store.create('An','fox');await store.recordWin('a',win());assert.deepEqual(calls,['bloxorz-profile-create','bloxorz-profile-a']);
});
test('old single-player records migrate once into one independent profile',async()=>{
 const {store,storage}=setup();storage.setItem('bloxorz.worlds.best.v1',JSON.stringify({campaign_01:{moves:5,stars:3},campaign_19:{moves:11,stars:3},invalid:{moves:0,stars:4}}));
 await store.migrateLegacy(catalog);await store.migrateLegacy(catalog);
 const old=store.list()[0];assert.equal(store.list().length,1);assert.equal(old.username,'Hành trình cũ');assert.equal(old.unlockedLevel,20);
 assert.equal(old.levelStats.campaign_01.bestTimeMs,null);assert.ok(storage.getItem('bloxorz.worlds.best.v1'));
 const newcomer=await store.create('Mới','cloud');assert.deepEqual(newcomer.levelStats,{});
});
test('gating applies to passcodes too and extends beyond 30 with a new catalog',async()=>{
 const {store}=setup(),a=await store.create('An','crystal');assert.equal(canPlay(a,catalog[1],catalog),false);
 assert.equal(canPlay(a,{collection:'extra'},catalog),true);await store.recordWin(a.id,win(30));
 assert.equal(store.read(a.id).unlockedLevel,30);
 const expanded=[...catalog,{id:'campaign_31',number:31,collection:'campaign'}];assert.equal(unlockedFor(store.read(a.id),expanded),31);
});
test('bad names, duplicate names, bad avatars and damaged records cannot replace saves',async()=>{
 const {store,storage}=setup();await assert.rejects(store.create('   ','fox'));await assert.rejects(store.create('An','bad'));
 const a=await store.create('An','fox');await assert.rejects(store.create(' an ','cloud'));
 storage.setItem(PROFILE_PREFIX+'broken','{bad-json');assert.equal(store.list().length,1);
 await assert.rejects(store.recordWin(a.id,win(1,8,5)));assert.deepEqual(store.read(a.id).levelStats,{});
});
test('failed persistence reports an error without changing another profile',async()=>{
 const {store,storage}=setup(),a=await store.create('An','fox');const old=storage.getItem(PROFILE_PREFIX+a.id);
 storage.setItem=()=>{throw new Error('quota');};await assert.rejects(store.recordWin(a.id,win()),/Chưa lưu/);assert.equal(storage.getItem(PROFILE_PREFIX+a.id),old);
});
test('active clock excludes pauses and hidden/profile time, resets only for new runs',()=>{
 let time=0;const clock=new RunClock(()=>time);clock.resume();time=1200;clock.pause();time=9000;
 assert.equal(clock.milliseconds,1200);clock.resume();clock.resume();time=10000;clock.pause();assert.equal(clock.milliseconds,2200);
 clock.reset();assert.equal(clock.milliseconds,0);assert.equal(formatTime(125000),'2:05');assert.equal(formatTime(null),'—');
});

/** Local multi-slot profiles. Each slot has its own key; Web Locks serialize
 * updates to the same slot across tabs. No credentials or cloud auth implied. */
export const PROFILE_PREFIX='bloxorz.profiles.v1.slot.';
export const AVATARS=['sprout','fox','moon','crystal','star','cloud'];
const LEGACY_KEY='bloxorz.worlds.best.v1';
const clone=value=>structuredClone(value);
export function newProfileId(){return `player-${Array.from(crypto.getRandomValues(new Uint8Array(16)),value=>value.toString(16).padStart(2,'0')).join('')}`;}
const validId=id=>typeof id==='string'&&/^[\w-]{1,80}$/.test(id)&&id!=='__proto__';
const integer=(n,min=0)=>Number.isSafeInteger(n)&&n>=min;
export function displayName(value){
 const name=String(value??'').trim().replace(/\s+/g,' ');
 if(!name||Array.from(name).length>20||/[\u0000-\u001f\u007f]/.test(name))throw new Error('Tên cần có từ 1 đến 20 ký tự.');
 return name;
}
function normalize(raw){
 if(!raw||!validId(raw.id)||!AVATARS.includes(raw.avatar)||!integer(raw.unlockedLevel,1))return null;
 let username;try{username=displayName(raw.username);}catch{return null;}
 const levelStats={};
 for(const [id,stat] of Object.entries(raw.levelStats||{})){
  if(!validId(id)||!stat||!integer(stat.stars,1)||stat.stars>3||!integer(stat.bestMoves))continue;
  levelStats[id]={...stat,bestTimeMs:Number.isFinite(stat.bestTimeMs)&&stat.bestTimeMs>=0?Math.round(stat.bestTimeMs):null};
 }
 return {...raw,username,levelStats};
}
export function unlockedFor(profile,catalog){
 const main=catalog.filter(level=>level.collection==='campaign');
 const maximum=Math.max(1,...main.map(level=>level.number));
 const completed=Math.max(0,...main.filter(level=>profile?.levelStats[level.id]).map(level=>level.number));
 return Math.min(maximum,Math.max(1,profile?.unlockedLevel||1,completed+1));
}
export function canPlay(profile,level,catalog){
 return !!profile&&!!level&&(level.collection!=='campaign'||level.number<=unlockedFor(profile,catalog));
}
export class ProfileStore {
 constructor(storage,{locks=null,now=()=>new Date().toISOString(),id=newProfileId}={}){
  this.storage=storage;this.locks=locks;this.now=now;this.id=id;this.activeId=null;this.listeners=new Set();this.queue=Promise.resolve();
 }
 read(id){
  if(!validId(id))return null;
  try{const value=normalize(JSON.parse(this.storage.getItem(PROFILE_PREFIX+id)||'null'));return value?.id===id?value:null;}catch{return null;}
 }
 list(){
  const profiles=[];
  try{for(let i=0;i<this.storage.length;i++){const key=this.storage.key(i);if(key?.startsWith(PROFILE_PREFIX)){const profile=this.read(key.slice(PROFILE_PREFIX.length));if(profile)profiles.push(profile);}}}catch{throw new Error('Trình duyệt chưa cho phép đọc hồ sơ local.');}
  return profiles.sort((a,b)=>String(b.lastPlayed).localeCompare(String(a.lastPlayed)));
 }
 get currentUser(){return this.activeId?this.read(this.activeId):null;}
 subscribe(listener){this.listeners.add(listener);return ()=>this.listeners.delete(listener);}
 refresh(){for(const listener of this.listeners)listener(this.currentUser);}
 write(profile){
  try{this.storage.setItem(PROFILE_PREFIX+profile.id,JSON.stringify(profile));}catch{throw new Error('Chưa lưu được hồ sơ. Kiểm tra dung lượng hoặc quyền lưu dữ liệu của trình duyệt.');}
  this.refresh();return clone(profile);
 }
 async locked(id,operation){
  if(this.locks)return this.locks.request('bloxorz-profile-'+id,operation);
  const pending=this.queue.then(operation);this.queue=pending.catch(()=>{});return pending;
 }
 async create(username,avatar){
  const name=displayName(username);if(!AVATARS.includes(avatar))throw new Error('Hãy chọn một avatar.');
  return this.locked('create',()=>{
   if(this.list().some(profile=>profile.username.toLocaleLowerCase('vi')===name.toLocaleLowerCase('vi')))throw new Error('Tên này đã có hồ sơ. Hãy chọn tên khác.');
   const timestamp=this.now();return this.write({id:this.id(),username:name,avatar,unlockedLevel:1,levelStats:{},createdAt:timestamp,lastPlayed:timestamp});
  });
 }
 async select(id,catalog){
  const selected=await this.locked(id,()=>{
   const profile=this.read(id);if(!profile)throw new Error('Hồ sơ này không còn tồn tại.');
   return this.write({...profile,unlockedLevel:unlockedFor(profile,catalog),lastPlayed:this.now()});
  });
  this.activeId=selected.id;this.refresh();return selected;
 }
 async recordWin(id,{level,moves,stars,timeMs,catalog}){
  if(!validId(level?.id)||!integer(moves)||!integer(stars,1)||stars>3||!Number.isFinite(timeMs)||timeMs<0)throw new Error('Kết quả màn chơi không hợp lệ.');
  return this.locked(id,()=>{
   const profile=this.read(id);if(!profile)throw new Error('Không tìm thấy hồ sơ để lưu kết quả.');
   const previous=profile.levelStats[level.id],timestamp=this.now(),duration=Math.round(timeMs);
   profile.levelStats[level.id]={stars:Math.max(previous?.stars||0,stars),bestMoves:Math.min(previous?.bestMoves??Infinity,moves),
    bestTimeMs:Math.min(previous?.bestTimeMs??Infinity,duration),lastMoves:moves,lastTimeMs:duration,
    completedAt:previous?.completedAt||timestamp,lastCompletedAt:timestamp,plays:(previous?.plays||0)+1};
   profile.unlockedLevel=unlockedFor(profile,catalog);profile.lastPlayed=timestamp;
   return this.write(profile);
  });
 }
 async migrateLegacy(catalog){
  return this.locked('migration',()=>{
   const id='legacy-worlds';if(this.read(id))return;
   let old;try{old=JSON.parse(this.storage.getItem(LEGACY_KEY)||'null');}catch{return;}
   if(!old||typeof old!=='object')return;
   const levelStats={};for(const level of catalog){const stat=old[level.id];if(stat&&integer(stat.moves)&&integer(stat.stars,1)&&stat.stars<=3)levelStats[level.id]={bestMoves:stat.moves,stars:stat.stars,bestTimeMs:null,plays:1};}
   if(!Object.keys(levelStats).length)return;
   const timestamp=this.now(),profile={id,username:'Hành trình cũ',avatar:'moon',unlockedLevel:1,levelStats,createdAt:timestamp,lastPlayed:timestamp};
   profile.unlockedLevel=unlockedFor(profile,catalog);this.write(profile);
  });
 }
}

import { AVATARS,unlockedFor } from './profiles.js';
const escape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ART={
 sprout:['...22...','..2222..','3..22..3','33.22.33','.332233.','...44...','...44...','..4444..'],
 fox:['2.....2.','22...22.','2332332.','2333332.','.31413..','.33333..','..353...','...3....'],
 moon:['..2222..','.222....','222.....','222.....','2222....','.22222..','..22222.','....22..'],
 crystal:['...2....','..232...','.23332..','2333332.','2333332.','.23332..','..232...','...2....'],
 star:['...22...','...22...','22222222','.233332.','..2332..','.232232.','22....22','........'],
 cloud:['........','..222...','.22332..','2223332.','23333332','23333332','.222222.','........']
};
const COLORS={sprout:['#acd7a1','#d8e6ac','#66957c','#7c695c','#f0dfb3'],fox:['#e4ad87','#f5d0a6','#d39071','#263d47','#f3e9ce'],moon:['#d7cbf3','#c7b6e6','#b7abd5','#8e86ae','#f7eac9'],crystal:['#a3e0df','#d1eddf','#95c8dc','#617eac','#e7f6f1'],star:['#efd193','#ffe7b3','#d7b87c','#a6c3bf','#fff3ce'],cloud:['#c7d7e8','#e2e9ec','#b5c8d5','#8ea5bc','#f6e8d2']};
export function avatarIcon(id){
 const pixels=ART[id]||ART.sprout,palette=COLORS[id]||COLORS.sprout;
 return `<svg viewBox="0 0 8 8" class="pixel-avatar" aria-hidden="true" shape-rendering="crispEdges">${pixels.flatMap((row,y)=>[...row].map((value,x)=>value==='.'?'':`<rect x="${x}" y="${y}" width="1" height="1" fill="${palette[Number(value)-1]}"/>`)).join('')}</svg>`;
}
export class ProfileUI {
 constructor(store,{catalog,onSelect,onReturn}){
  this.store=store;this.catalog=catalog;this.onSelect=onSelect;this.onReturn=onReturn;
  this.screen=document.querySelector('#profile-screen');this.editor=document.querySelector('#profile-editor');this.form=document.querySelector('#profile-form');
  document.querySelector('#add-profile').addEventListener('click',()=>this.create());
  document.querySelector('#profile-back').addEventListener('click',()=>onReturn());
  document.querySelector('#profile-list').addEventListener('click',event=>{const card=event.target.closest('[data-profile]');if(card)this.select(card.dataset.profile);});
  document.querySelector('#profile-create-cancel').addEventListener('click',()=>this.editor.close());
  this.form.addEventListener('submit',async event=>{
   event.preventDefault();const data=new FormData(this.form);this.setPending(true);this.error('','create');
   let created=false;
   try{const profile=await store.create(data.get('username'),data.get('avatar'));created=true;this.editor.close();await onSelect(profile.id);}
   catch(error){this.error(error.message,created?'select':'create');}finally{this.setPending(false);}
  });
 }
 get visible(){return !this.screen.hidden;}
 setPending(value){this.pending=value;this.screen.querySelectorAll('button').forEach(button=>button.disabled=value);this.form.querySelectorAll('button,input').forEach(input=>input.disabled=value);}
 error(message,target='select'){document.querySelector(target==='create'?'#profile-create-error':'#profile-error').textContent=message;}
 render(){
  let profiles;try{profiles=this.store.list();}catch(error){this.error(error.message);profiles=[];}
  const maximum=this.catalog().filter(level=>level.collection==='campaign').length;
  document.querySelector('#profile-list').innerHTML=profiles.map(profile=>{
   const completed=Object.keys(profile.levelStats).filter(id=>this.catalog().some(level=>level.id===id&&level.collection==='campaign')).length;
   const stars=Object.values(profile.levelStats).reduce((sum,stat)=>sum+stat.stars,0);
   return `<button class="profile-card" data-profile="${escape(profile.id)}"><span class="profile-avatar">${avatarIcon(profile.avatar)}</span><span class="profile-card-info"><strong>${escape(profile.username)}</strong><small>${completed}/${maximum} màn · ${stars} ★</small><span class="profile-track"><i style="width:${maximum?Math.round(completed/maximum*100):0}%"></i></span></span><span class="profile-continue">Màn ${unlockedFor(profile,this.catalog())}<span>↗</span></span></button>`;
  }).join('');
  document.querySelector('#profile-empty').hidden=profiles.length>0;
  document.querySelector('#profile-back').hidden=!this.store.currentUser;
 }
 show(){this.render();this.screen.hidden=false;document.querySelector('#game-shell').inert=true;(this.screen.querySelector('[data-profile]')||document.querySelector('#add-profile')).focus();}
 hide(){this.screen.hidden=true;document.querySelector('#game-shell').inert=false;}
 create(){
  this.form.reset();document.querySelector('#avatar-choices').innerHTML=AVATARS.map((avatar,index)=>`<label class="avatar-option"><input type="radio" name="avatar" value="${avatar}" ${index===0?'checked':''} aria-label="Avatar ${avatar}"><span>${avatarIcon(avatar)}</span></label>`).join('');
  this.error('','create');this.editor.showModal();document.querySelector('#profile-username').focus();
 }
 async select(id){if(this.pending)return;this.setPending(true);this.error('');try{await this.onSelect(id);}catch(error){this.error(error.message);}finally{this.setPending(false);}}
}

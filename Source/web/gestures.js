/** Pointer-state controller shared by mouse and touch. Multi-touch never rolls. */
export class BoardGestures {
 constructor(onOrbit,onSwipe){this.onOrbit=onOrbit;this.onSwipe=onSwipe;this.pointers=new Map();this.start=null;this.orbit=false;}
 down(id,x,y,button=0) {
  if(![0,2].includes(button))return false;
  this.pointers.set(id,{x,y});if(this.pointers.size===1)this.start={id,x,y};
  if(button===2||this.pointers.size>=2){this.orbit=true;this.start=null;}return true;
 }
 move(id,x,y) {
  const previous=this.pointers.get(id);if(!previous)return;
  this.pointers.set(id,{x,y});
  if(this.orbit)this.onOrbit((x-previous.x)/(this.pointers.size>=2?2:1),(y-previous.y)/(this.pointers.size>=2?2:1));
 }
 up(id,x,y) {
  if(!this.pointers.has(id))return;this.pointers.delete(id);
  if(this.orbit){if(!this.pointers.size)this.orbit=false;this.start=null;return;}
  if(this.start?.id!==id)return;
  const dx=x-this.start.x,dy=y-this.start.y;this.start=null;
  if(Math.hypot(dx,dy)>=24)this.onSwipe(dx,dy);
 }
 cancel(id){this.pointers.delete(id);this.start=null;if(!this.pointers.size)this.orbit=false;}
}

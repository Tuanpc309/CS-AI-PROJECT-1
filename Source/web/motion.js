/** Isometric presentation only. Python remains the authority for every rule. */
import { ROLL_DURATION_MS, easeInOutQuad, cuboidVertices as vertices,
  boxesForState as boxes, rollVertices as roll } from './rolling.js';
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
import { SETTLE_MS,landingInfo,settledPose } from './impact.js';
// A render pose is independent of the committed logical state.
function poseFor(state, action, angle = 0) {
  return boxes(state).map(box => {
    let points = vertices(box.x,box.y,box.w,box.d,box.h);
    if (action && action !== 'SWITCH' && box.active) points = roll(points,box,action,angle);
    return {box,points};
  });
}


export class BoardMotion {
  notify(name,...args){
    try{this.effectHooks?.[name]?.(...args);this.canvas?.dispatchEvent?.(new CustomEvent(name==='onImpact'?'bloxorz-impact':'bloxorz-roll-start',{detail:name==='onImpact'?{surfaceType:args[0],...args[1]}:args[0],bubbles:true}));}
    catch(error){console.warn('Bloxorz effect hook failed:',error);}
  }
  get animating() { return this._moving || this.frame !== null; }

  async reveal(data) {
    this.resetEffects?.();
    this.data=data; this.fit();
    if(this.reduceMotion.matches) { this.animation=null; this.draw(); return; }
    await this.tween(620, t=>{ this.animation={type:'reveal',progress:t}; this.draw(); });
    this.animation=null; this.draw();
  }

  async animate(previous, next, action) {
    if (this.animating) return false;
    this._moving=true;
    try {
      const landed=poseFor(previous.state,action,action==='SWITCH'?0:Math.PI/2);
      const impact=action!=='SWITCH'&&next.phase==='PLAYING'?landingInfo(landed,next.level,action):null;
      if(action!=='SWITCH')this.notify('onRollStart',{action,orientation:previous.state.orientation,mode:previous.state.mode});
      if(this.reduceMotion.matches) { this.data=next;if(impact)this.emitImpact?.(impact);return true; }
      this.data=previous;
      if(action!=='SWITCH') {
        this.canvas.dataset.motion='rolling';
        // Nothing commits visually until the complete 90-degree roll has landed.
        await this.tween(ROLL_DURATION_MS, t=>{
          this.animation={type:'roll',progress:t,
            pose:poseFor(previous.state,action,easeInOutQuad(t)*Math.PI/2),state:previous.state};
          this.draw();
        });
      }
      this.data=next;
      if(impact){
        this.emitImpact?.(impact);this.canvas.dataset.motion='settling';
        await this.tween(SETTLE_MS,t=>{this.animation={type:'settle',progress:t,impact,pose:settledPose(landed,t,impact),state:previous.state};this.draw();});
      }
      if(next.phase==='WON'||next.phase==='LOST') {
        this.canvas.dataset.motion='falling';
        const candidate=next.fallenState;
        const fragile=next.phase==='LOST'&&candidate?.orientation==='U'&&
          next.level.grid[candidate.anchor[0]]?.[candidate.anchor[1]]==='O' ? candidate.anchor : null;
        await this.tween(next.phase==='WON'?380:420,t=>{
          this.animation={type:'fall',progress:t,pose:landed,state:previous.state,fragile};this.draw();
        });
      } else if(previous.state.mode==='MERGED'&&next.state.mode==='SPLIT') {
        this.canvas.dataset.motion='splitting';
        await this.tween(150,t=>{
          this.animation={type:'split',progress:t,pose:t<.5?landed:poseFor(next.state),
            state:t<.5?previous.state:next.state};this.draw();
        });
      }
      return true;
    } finally {
      this._moving=false;
      this.animation=null;
      this.canvas.dataset.motion='idle';
      this.draw();
    }
  }

  tween(duration, update) {
    return new Promise((resolve,reject)=>{
      const start=performance.now();
      const tick=now=>{
        const t=clamp((now-start)/duration,0,1);
        try { update(t); } catch(error) { this.frame=null;reject(error);return; }
        if(t<1) this.frame=requestAnimationFrame(tick);
        else { this.frame=null; resolve(); }
      };
      this.frame=requestAnimationFrame(tick);
    });
  }

}

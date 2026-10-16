/** Counts active play only; pause, profile screens, hidden tabs and win VFX stop it. */
export class RunClock {
 constructor(now=()=>performance.now()){this.now=now;this.reset();}
 reset(){this.elapsed=0;this.started=null;}
 resume(){if(this.started===null)this.started=this.now();}
 pause(){if(this.started!==null){this.elapsed+=Math.max(0,this.now()-this.started);this.started=null;}}
 get milliseconds(){return Math.round(this.elapsed+(this.started===null?0:Math.max(0,this.now()-this.started)));}
}
export function formatTime(ms){if(ms===null||!Number.isFinite(ms))return '—';const seconds=Math.floor(ms/1000);return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;}

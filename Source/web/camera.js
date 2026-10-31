/** Ground axes are column=x, row=z. Angles are deliberately unbounded. */
export const DEFAULT_AZIMUTH = Math.PI / 4;
export const MIN_POLAR = Math.PI / 6;
export const MAX_POLAR = Math.PI * .395;
export const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

export function screenDirection(dx, dy, azimuth) {
  // Project the screen vector onto the horizontal camera right/forward basis.
  const x = dx * Math.cos(azimuth) + dy * Math.sin(azimuth);
  const z = -dx * Math.sin(azimuth) + dy * Math.cos(azimuth);
  return Math.abs(x) >= Math.abs(z) ? (x >= 0 ? 'RIGHT' : 'LEFT') : (z >= 0 ? 'DOWN' : 'UP');
}

export class OrbitCamera {
  constructor() { this.reset(true); }
  reset(immediate = false) {
    this.targetAzimuth = DEFAULT_AZIMUTH;
    // Reset via the shortest arc even after many complete turns.
    if (!immediate) this.targetAzimuth = this.azimuth + Math.atan2(
      Math.sin(DEFAULT_AZIMUTH-this.azimuth), Math.cos(DEFAULT_AZIMUTH-this.azimuth));
    this.targetPolar = Math.PI * .29;
    if (immediate) { this.azimuth=this.targetAzimuth; this.polar=this.targetPolar; }
  }
  drag(dx, dy) {
    this.targetAzimuth -= dx * .008;
    this.targetPolar = clamp(this.targetPolar - dy * .005, MIN_POLAR, MAX_POLAR);
  }
  step(seconds, reducedMotion = false) {
    const changing=Math.abs(this.targetAzimuth-this.azimuth)+Math.abs(this.targetPolar-this.polar)>1e-8;
    const weight = reducedMotion ? 1 : 1-Math.exp(-14*Math.min(seconds,.1));
    this.azimuth += (this.targetAzimuth-this.azimuth)*weight;
    this.polar += (this.targetPolar-this.polar)*weight;
    if(Math.abs(this.targetAzimuth-this.azimuth)+Math.abs(this.targetPolar-this.polar)<1e-5){this.azimuth=this.targetAzimuth;this.polar=this.targetPolar;}
    return changing;
  }
  direction(action) {
    if(action==='SWITCH') return action;
    // One quantized camera basis keeps all four controls distinct at diagonals.
    const order=['UP','LEFT','DOWN','RIGHT'];
    const quarter=Math.floor((this.azimuth+Math.PI/4-1e-4)/(Math.PI/2));
    return order[((order.indexOf(action)+quarter)%4+4)%4];
  }
}

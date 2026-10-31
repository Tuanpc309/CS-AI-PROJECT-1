/** Pure world-space geometry shared by the Canvas renderer and its tests.
 * Coordinates are [column, row, height]; the board surface is z = 0.
 */
export const ROLL_DURATION_MS = 220;

export function easeInOutQuad(progress) {
  const t = Math.max(0, Math.min(1, progress));
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

export function cuboidVertices(x, y, width, depth, height, z = 0) {
  return [
    [x, y, z], [x + width, y, z],
    [x + width, y + depth, z], [x, y + depth, z],
    [x, y, z + height], [x + width, y, z + height],
    [x + width, y + depth, z + height], [x, y + depth, z + height],
  ];
}

export function boxesForState(state) {
  if (state.mode === 'SPLIT') {
    return state.cubes.map(([r, c], index) => ({
      x: c, y: r, w: 1, d: 1, h: 1,
      index, active: index === state.active_cube,
    }));
  }
  return [{
    x: state.anchor[1], y: state.anchor[0],
    w: state.orientation === 'H' ? 2 : 1,
    d: state.orientation === 'V' ? 2 : 1,
    h: state.orientation === 'U' ? 2 : 1,
    index: 0, active: true,
  }];
}

/** axis selects the changing ground coordinate, not the rotation-axis vector.
 * The other ground coordinate stays fixed along the bottom pivot edge.
 */
export function pivotForMove(box, action) {
  switch (action) {
    case 'RIGHT': return { axis: 0, pivot: box.x + box.w, sign: 1 };
    case 'LEFT': return { axis: 0, pivot: box.x, sign: -1 };
    case 'DOWN': return { axis: 1, pivot: box.y + box.d, sign: 1 };
    case 'UP': return { axis: 1, pivot: box.y, sign: -1 };
    default: throw new RangeError(`Cannot roll in direction: ${action}`);
  }
}

/** Rotate a rigid cuboid about its leading bottom edge, without translation
 * or interpolation of its dimensions. angle is an unsigned angle in radians;
 * the direction determines the sign, and PI / 2 reaches the next footprint.
 */
export function rollVertices(points, box, action, angle) {
  const { axis, pivot, sign } = pivotForMove(box, action);
  const cosine = Math.cos(angle * sign), sine = Math.sin(angle * sign);
  return points.map(point => {
    const result = [...point], distance = point[axis] - pivot;
    result[axis] = pivot + distance * cosine + point[2] * sine;
    result[2] = -distance * sine + point[2] * cosine;
    return result;
  });
}

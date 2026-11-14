// Which plantings there are to draw.
//   whole   every run as the simulator recorded it (scenes/<snapshot>/runs/<name>/growth.json): what pictures are made
//           from beforehand
//   light   its lighter copy (scenes/<snapshot>/light/<name>.growth, from pipeline/lighten.mjs): what is drawn live
export const whole = import.meta.glob('@scene/runs/*/growth.json', { query: '?url', import: 'default', eager: true }) as Record<string, string>;
export const light = import.meta.glob('@scene/light/*.growth', { query: '?url', import: 'default', eager: true }) as Record<string, string>;

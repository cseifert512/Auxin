// The same as data.ts for the drawing that goes to the presentation: the light copies only, so that the whole
// records, a hundred megabytes each, are not carried along with it.
export const whole: Record<string, string> = {};
export const light = import.meta.glob('@scene/light/*.growth', { query: '?url', import: 'default', eager: true }) as Record<string, string>;

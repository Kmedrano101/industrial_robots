/** The backend keeps SI (m, rad, m/s); operators read mm, degrees, mm/s.
 *  All conversions for the settings forms live here so the two never mix. */

export const M_TO_MM = 1000;
export const RAD_TO_DEG = 180 / Math.PI;

/** Round to `digits` decimals, avoiding 0.1 + 0.2 artefacts in inputs. */
export function round(v: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(v * f) / f;
}

export const mToMm = (m: number) => round(m * M_TO_MM, 2);
export const mmToM = (mm: number) => mm / M_TO_MM;
export const radToDeg = (r: number) => round(r * RAD_TO_DEG, 2);
export const degToRad = (d: number) => d / RAD_TO_DEG;

/** Parse an input's text; null for anything that is not a finite number
 *  (so a half-typed "-" or "1e" does not overwrite the draft). */
export function parseNumber(text: string): number | null {
  if (text.trim() === '') return null;
  const v = Number(text);
  return Number.isFinite(v) ? v : null;
}

/** Shallow-ish equality for the plain values a settings group holds. */
export function sameValue(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** Replace index `i` of a numeric vector, returning a new array. */
export function withIndex(vec: number[], i: number, value: number): number[] {
  const out = vec.slice();
  out[i] = value;
  return out;
}

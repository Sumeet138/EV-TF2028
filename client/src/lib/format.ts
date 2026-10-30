import type { GapBand } from '../types';

const grouped = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 });
const DASH = '–'; // shown for missing values

export function formatIN(n: number | null | undefined, digits = 0): string {
  if (n == null || !Number.isFinite(n)) return DASH;
  return digits === 0
    ? grouped.format(n)
    : new Intl.NumberFormat('en-IN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

/** 1.08 crore, 12.4 lakh; below one lakh falls back to grouped digits. */
export function formatCompactIN(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return DASH;
  const a = Math.abs(n);
  const one = (v: number) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: v < 10 ? 2 : 1 }).format(v);
  if (a >= 1e7) return `${one(n / 1e7)} crore`;
  if (a >= 1e5) return `${one(n / 1e5)} lakh`;
  return formatIN(n);
}

/** Input is a 0-1 share. */
export function formatPct(share: number | null | undefined, digits = 0): string {
  if (share == null || !Number.isFinite(share)) return DASH;
  return `${(share * 100).toFixed(digits)}%`;
}

export function formatKm(km: number | null | undefined, digits = 1): string {
  if (km == null || !Number.isFinite(km)) return DASH;
  return `${formatIN(km, km >= 100 ? 0 : digits)} km`;
}

const BANDS: Record<GapBand, string> = {
  1: 'Well served',
  2: 'Adequate',
  3: 'Stretched',
  4: 'Severe',
  5: 'Critical',
};
export function gapBandLabel(band: GapBand): string {
  return BANDS[band];
}

/** Export writes no-census districts as score 0, band 1; never present those as well served. */
export function isUnscored(d: { gapScore: number; confidence: string }): boolean {
  return d.gapScore === 0 && d.confidence === 'low';
}

// Same formula as scripts/pipeline/03_forecast.py `estimate`. Keep constants in sync; estimator.check.ts proves parity.
import type { District, Forecast, ScenarioKey, Scenarios } from '../types';

export const HOURS = 16;
export const POWER = { ac: 7.4, dc30: 30, dc60: 60, dc120: 120 };
export const RURAL_MIX = { ac: 0.45, dc30: 0.4, dc60: 0.12, dc120: 0.03 };
export const URBAN_DENSITY = 5000;
export const CPS = 2.1; // connectors per existing station
export const SPACING_KM = 3;
/** Share of the 2035 utilisation reached in `year` (0.30 in 2025, linear to 1.0). Same as ramp() in 03_forecast.py. */
export const ramp = (year: number) => 0.3 + 0.07 * (year - 2025);

export type Overrides = Partial<Scenarios['defaults']>;
type Year = '2027' | '2030' | '2035';

const round = (x: number) => Math.floor(x + 0.5);

/** Base-scenario EVs come from district.forecast[year]; other scenarios scale by the national series ratio. */
export function estimate(
  district: District,
  year: Year,
  scenario: ScenarioKey,
  overrides: Overrides,
  scenarios: Scenarios,
): Forecast {
  const d = { ...scenarios.defaults, ...overrides };
  const y = Number(year);
  const nat = (k: ScenarioKey) => scenarios.series[k].find((p) => p.year === y)!.evs;
  const evs = district.forecast[year].evs * (nat(scenario) / nat('base'));
  const types = ['2W', '3W', '4W'] as const;
  const kwhPerEv = types.reduce((a, t) => a + (d.fleetMix[t] * d.kmPerDay[t] * d.kwhPer100km[t]) / 100, 0);
  const energy = evs * kwhPerEv * d.publicShare;
  const u = district.urbanShare;
  const keys = ['ac', 'dc30', 'dc60', 'dc120'] as const;
  const cnt = { ac: 0, dc30: 0, dc60: 0, dc120: 0 };
  for (const k of keys) {
    cnt[k] = (energy * (u * d.typeMix[k] + (1 - u) * RURAL_MIX[k])) / (POWER[k] * HOURS * d.utilisation * ramp(y));
  }
  const urbanArea = Math.min(district.areaKm2, (district.population * u) / URBAN_DENSITY);
  const floor = urbanArea / (2.6 * SPACING_KM ** 2);
  const gap = floor - (cnt.ac + cnt.dc30 + cnt.dc60 + cnt.dc120);
  if (gap > 0) {
    cnt.ac += gap / 2;
    cnt.dc30 += gap / 2;
  }
  const byType = { ac: round(cnt.ac), dc30: round(cnt.dc30), dc60: round(cnt.dc60), dc120: round(cnt.dc120) };
  const req = byType.ac + byType.dc30 + byType.dc60 + byType.dc120;
  return {
    evs: round(evs),
    chargersRequired: req,
    chargersToAdd: Math.max(0, round(req - district.chargersAdjusted * CPS)),
    byType,
    demandMWhPerDay: round(energy) / 1000,
  };
}

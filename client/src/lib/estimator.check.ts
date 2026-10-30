// Run: npx tsx client/src/lib/estimator.check.ts  (after the pipeline has produced data/processed)
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import type { District, Scenarios } from '../types';
import { estimate } from './estimator';

const dir = new URL('../../../data/processed/', import.meta.url);
const csv = (f: string) => {
  const [h, ...rows] = readFileSync(new URL(f, dir), 'utf8').trim().split('\n');
  const head = h.split(',');
  return rows.map((r) => {
    const cells = (r.match(/("([^"]|"")*"|[^,]*)(,|$)/g) ?? []).slice(0, head.length);
    return Object.fromEntries(head.map((k, i) => [k, (cells[i] ?? '').replace(/,$/, '').replace(/^"|"$/g, '').replace(/""/g, '"')]));
  });
};
const scenarios: Scenarios = JSON.parse(readFileSync(new URL('scenarios.json', dir), 'utf8'));
const base = new Map(csv('districts_base.csv').map((r) => [r.id, r]));
const gap = new Map(csv('districts_gap.csv').map((r) => [r.id, r]));
let n = 0;
for (const row of csv('districts_forecast.csv').slice(0, 50)) {
  const forecast = JSON.parse(row.forecast);
  const b = base.get(row.id)!, g = gap.get(row.id)!;
  const d = {
    id: row.id, forecast, urbanShare: +b.urbanShare, areaKm2: +b.areaKm2,
    population: +b.population, chargersAdjusted: +g.chargersAdjusted,
  } as unknown as District;
  for (const y of ['2027', '2030', '2035'] as const) {
    assert.deepEqual(estimate(d, y, 'base', {}, scenarios), forecast[y], `${row.id} ${y}`);
  }
  assert.ok(estimate(d, '2030', 'high', {}, scenarios).evs >= estimate(d, '2030', 'low', {}, scenarios).evs);
  n++;
}
console.log(`estimator parity OK on ${n} districts`);

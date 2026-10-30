import { useMemo, useState } from 'react';
import { Download, RotateCcw } from 'lucide-react';
import { useData } from '../lib/data';
import { useRoute, setParams } from '../lib/route';
import { formatIN, formatPct, formatKm, isUnscored } from '../lib/format';
import { estimate } from '../lib/estimator';
import { Button, Milestone, ModelledTag, Panel, Select, Slider, Stat, Table, Tabs, type Column } from '../ui';
import type { Forecast, ScenarioKey, Site } from '../types';
import './PlannerView.css';

type Year = '2027' | '2030' | '2035';
const YEARS: Year[] = ['2027', '2030', '2035'];
const SCEN = [{ id: 'low' as const, label: 'Low' }, { id: 'base' as const, label: 'Base' }, { id: 'high' as const, label: 'High' }];
const TYPES = [['ac', 'AC'], ['dc30', 'DC 30 kW'], ['dc60', 'DC 60 kW'], ['dc120', 'DC 120 kW']] as const;
const ALL = '__all';

const sumF = (fs: Forecast[]): Forecast =>
  fs.reduce<Forecast>((a, f) => ({
    evs: a.evs + f.evs, chargersRequired: a.chargersRequired + f.chargersRequired, chargersToAdd: a.chargersToAdd + f.chargersToAdd,
    byType: { ac: a.byType.ac + f.byType.ac, dc30: a.byType.dc30 + f.byType.dc30, dc60: a.byType.dc60 + f.byType.dc60, dc120: a.byType.dc120 + f.byType.dc120 },
    demandMWhPerDay: a.demandMWhPerDay + f.demandMWhPerDay,
  }), { evs: 0, chargersRequired: 0, chargersToAdd: 0, byType: { ac: 0, dc30: 0, dc60: 0, dc120: 0 }, demandMWhPerDay: 0 });

const csvCell = (v: string | number | null) => `"${String(v ?? '').replace(/"/g, '""')}"`;

export default function PlannerView() {
  const { districts, states, sites, scenarios, districtById } = useData();
  const route = useRoute();
  const def = scenarios.defaults;

  const initD = route.d ? districtById.get(route.d) : undefined;
  const [state, setState] = useState(initD?.state ?? route.s ?? [...states].filter((s) => districts.some((d) => d.state === s.name && !isUnscored(d))).sort((a, b) => b.chargersToAdd2030 - a.chargersToAdd2030)[0]?.name ?? '');
  const [dist, setDist] = useState(initD?.id ?? ALL);
  const [year, setYear] = useState<Year>('2030');
  const [scen, setScen] = useState<ScenarioKey>('base');
  const [share, setShare] = useState(def.publicShare);
  const [util, setUtil] = useState(def.utilisation);
  const [m2, setM2] = useState(def.fleetMix['2W']);
  const [m3, setM3] = useState(def.fleetMix['3W']);
  const m4 = Math.max(0, 1 - m2 - m3);

  const overrides = useMemo(
    () => ({ publicShare: share, utilisation: util, fleetMix: { '2W': m2, '3W': m3, '4W': m4 } }),
    [share, util, m2, m3, m4],
  );
  const inState = useMemo(() => districts.filter((d) => d.state === state && !isUnscored(d)), [districts, state]);
  const unscored = districts.filter((d) => d.state === state && isUnscored(d)).length;
  const scope = useMemo(() => (dist === ALL ? inState : inState.filter((d) => d.id === dist)), [inState, dist]);
  const per = useMemo(
    () => inState.map((d) => ({ d, f: estimate(d, year, scen, overrides, scenarios) })),
    [inState, year, scen, overrides, scenarios],
  );
  const total = useMemo(() => sumF(per.filter((p) => scope.includes(p.d)).map((p) => p.f)), [per, scope]);
  const next = useMemo(() => [...per].sort((a, b) => b.f.chargersToAdd - a.f.chargersToAdd).slice(0, 4), [per]);
  const scopeIds = useMemo(() => new Set(scope.map((d) => d.id)), [scope]);
  const picks = useMemo(
    () => sites.filter((s) => scopeIds.has(s.districtId)).sort((a, b) => a.rank - b.rank || b.evsCovered - a.evsCovered).slice(0, 12),
    [sites, scopeIds],
  );

  const changed = [
    share !== def.publicShare && `Public charging share ${formatPct(def.publicShare)} to ${formatPct(share)}`,
    util !== def.utilisation && `Utilisation ${formatPct(def.utilisation)} to ${formatPct(util)}`,
    (m2 !== def.fleetMix['2W'] || m3 !== def.fleetMix['3W']) &&
      `Fleet mix 2W ${formatPct(def.fleetMix['2W'])}, 3W ${formatPct(def.fleetMix['3W'])}, 4W ${formatPct(def.fleetMix['4W'])} to ${formatPct(m2)}, ${formatPct(m3)}, ${formatPct(m4)}`,
  ].filter(Boolean) as string[];

  const reset = () => { setShare(def.publicShare); setUtil(def.utilisation); setM2(def.fleetMix['2W']); setM3(def.fleetMix['3W']); };
  const pickState = (s: string) => { setState(s); setDist(ALL); setParams({ s, d: null }); };
  const pickDist = (id: string) => { setDist(id); setParams({ d: id === ALL ? null : id }); };

  const exportCsv = () => {
    const head = ['district', 'state', 'year', 'scenario', 'site_rank', 'charger_type', 'connectors', 'evs_covered_modelled', 'nearest_substation_km', 'corridor', 'reason'];
    const rows = picks.map((s) => {
      const d = districtById.get(s.districtId);
      return [d?.name ?? s.districtId, d?.state ?? state, year, scen, s.rank, s.chargerType, s.connectors, s.evsCovered, s.nearestSubstationKm, s.corridor, s.reason];
    });
    const note = [`# Modelled plan. Overrides: ${changed.length ? changed.join('; ') : 'none (defaults)'}. Charger inventory is partial.`];
    const csv = [note.join('\n'), head.join(','), ...rows.map((r) => r.map(csvCell).join(','))].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = `ev-plan-${state.toLowerCase().replace(/\s+/g, '-')}-${year}-${scen}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const siteCols: Column<Site>[] = [
    { key: 'd', header: 'District', render: (s) => districtById.get(s.districtId)?.name ?? s.districtId },
    { key: 't', header: 'Type', render: (s) => TYPES.find((t) => t[0] === s.chargerType)?.[1] ?? s.chargerType },
    { key: 'c', header: 'Connectors', align: 'right', render: (s) => formatIN(s.connectors) },
    { key: 'e', header: 'EVs covered', align: 'right', render: (s) => <>{formatIN(s.evsCovered)} <ModelledTag /></> },
    { key: 's', header: 'Nearest substation', align: 'right', render: (s) => formatKm(s.nearestSubstationKm) },
    { key: 'r', header: 'Why here', render: (s) => s.reason },
  ];

  return (
    <div className="plan">
      <header className="plan-head">
        <h1>Planner</h1>
        <p>Estimate the chargers a state or district needs, then see where to build first.</p>
      </header>

      <div className="plan-grid">
        <Panel title="Inputs" className="plan-in" actions={<Button variant="ghost" onClick={reset} disabled={!changed.length}><RotateCcw aria-hidden="true" /> Reset to defaults</Button>}>
          <div className="plan-fields">
            <Select label="State" value={state} options={states.map((s) => ({ value: s.name, label: s.name }))} onChange={pickState} />
            <Select label="District (optional)" value={dist}
              options={[{ value: ALL, label: 'All districts' }, ...inState.map((d) => ({ value: d.id, label: d.name }))]} onChange={pickDist} />
            <Select label="Year" value={year} options={YEARS.map((y) => ({ value: y, label: y }))} onChange={setYear} />
          </div>
          <Tabs label="Scenario" value={scen} items={SCEN} onChange={setScen} />
          <details className="plan-adjust">
            <summary>Adjust assumptions{changed.length ? ` (${changed.length} changed)` : ''}</summary>
          <div className="plan-sliders">
            <Slider label="Public charging share" value={share} min={0.05} max={0.8} step={0.01} onChange={setShare} format={(v) => formatPct(v)} />
            <Slider label="Charger utilisation, 2035 target" value={util} min={0.03} max={0.5} step={0.01} onChange={setUtil} format={(v) => formatPct(v)} />
            <Slider label="Two-wheelers in fleet" value={m2} min={0} max={1 - m3} step={0.01} onChange={setM2} format={(v) => formatPct(v)} />
            <Slider label="Three-wheelers in fleet" value={m3} min={0} max={1 - m2} step={0.01} onChange={setM3} format={(v) => formatPct(v)} />
            <p className="plan-sub">Four-wheelers take the rest: {formatPct(m4)}.</p>
          </div>
          </details>
          <div className="plan-changed" aria-live="polite">
            <h3>Assumptions changed</h3>
            {changed.length ? <ul>{changed.map((c) => <li key={c}>{c}</li>)}</ul> : <p>None. Using the defaults.</p>}
          </div>
        </Panel>

        <div className="plan-out">
          <Panel title={`${dist === ALL ? state : districtById.get(dist)?.name ?? state} in ${year}, ${scen} scenario`}>
            <dl className="plan-stats">
              <Stat label="Chargers to add" value={formatIN(total.chargersToAdd)} modelled />
              <Stat label="Chargers required" value={formatIN(total.chargersRequired)} modelled />
              <Stat label="EVs" value={formatIN(total.evs)} modelled />
              <Stat label="Energy demand" value={formatIN(total.demandMWhPerDay, 1)} unit="MWh per day" modelled />
            </dl>
            <h3 className="plan-h3">Type split <ModelledTag /></h3>
            <ul className="plan-split">
              {TYPES.map(([k, label]) => {
                const v = total.byType[k];
                const max = Math.max(...TYPES.map(([kk]) => total.byType[kk]), 1);
                return (
                  <li key={k}><span>{label}</span><span className="plan-bar"><i style={{ width: `${(v / max) * 100}%` }} /></span><b>{formatIN(v)}</b></li>
                );
              })}
            </ul>
          </Panel>

          <Panel title={`Next stops in ${state}`}>
            {unscored > 0 && <p className="plan-sub">{unscored} {unscored === 1 ? 'district has' : 'districts have'} no census data and {unscored === 1 ? 'is' : 'are'} left out.</p>}
            <p className="plan-sub">Districts needing the most new chargers. <ModelledTag /></p>
            <div className="plan-stops">
              {next.map(({ d, f }) => (
                <Milestone key={`${d.id}-${year}-${scen}`} cap={d.code} reading={formatIN(f.chargersToAdd)} unit="chargers to add" sub={d.name} animate={false} />
              ))}
            </div>
          </Panel>
        </div>
      </div>

      <Panel title="Site recommendations" actions={<Button variant="primary" onClick={exportCsv} disabled={!picks.length}><Download aria-hidden="true" /> Export plan CSV</Button>}>
        {picks.length ? (
          <Table caption="Recommended sites" columns={siteCols} rows={picks} rowKey={(s) => s.id} />
        ) : <p className="plan-sub">No candidate sites for this selection.</p>}
        <p className="plan-sub">Candidates for survey. Land and grid capacity are not checked.</p>
      </Panel>
    </div>
  );
}

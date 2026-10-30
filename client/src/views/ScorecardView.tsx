import { useMemo } from 'react';
import { useData } from '../lib/data';
import { hrefFor, navigate, setParams, useRoute } from '../lib/route';
import { formatCompactIN, formatIN, formatPct, gapBandLabel, isUnscored } from '../lib/format';
import { BarList, Button, EmptyState, ModelledTag, Panel, Stat, Table, type Column } from '../ui';
import type { State } from '../types';
import './ScorecardView.css';

type Pt = { x: number; y: number };

/** One-series line chart, plain SVG. Own y-axis: never combined with another scale. */
function LineChart({ pts, title, desc, fmtY, fmtX, note }: {
  pts: Pt[]; title: string; desc: string; fmtY: (n: number) => string; fmtX: (n: number) => string; note?: string;
}) {
  const W = 360, H = 190, L = 52, R = 14, T = 12, B = 26;
  if (pts.length < 2) return <p className="sc-muted">Not enough points to draw {title}.</p>;
  const x0 = pts[0].x, x1 = pts[pts.length - 1].x;
  const yMax = Math.max(...pts.map((p) => p.y)) * 1.08 || 1;
  const sx = (x: number) => L + ((x - x0) / (x1 - x0 || 1)) * (W - L - R);
  const sy = (y: number) => T + (1 - y / yMax) * (H - T - B);
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join('');
  const last = pts[pts.length - 1];
  const ticks = [0, 0.5, 1].map((f) => f * yMax);
  return (
    <figure className="sc-fig">
      <figcaption>{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={desc}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={W - R} y1={sy(t)} y2={sy(t)} stroke="var(--line)" strokeWidth="1" />
            <text x={L - 6} y={sy(t) + 4} textAnchor="end" className="sc-tick">{fmtY(t)}</text>
          </g>
        ))}
        <text x={L} y={H - 6} className="sc-tick">{fmtX(x0)}</text>
        <text x={W - R} y={H - 6} textAnchor="end" className="sc-tick">{fmtX(x1)}</text>
        <path d={d} fill="none" stroke="var(--peacock-700)" strokeWidth="2" strokeLinejoin="round" />
        <circle cx={sx(last.x)} cy={sy(last.y)} r="4" fill="var(--peacock-700)" stroke="var(--white)" strokeWidth="2" />
        <text x={sx(last.x) - 8} y={sy(last.y) - 8} textAnchor="end" className="sc-label">{fmtY(last.y)}</text>
      </svg>
      {note && <p className="sc-note">{note}</p>}
      <table className="sr-only"><caption>{title}</caption><tbody>
        {pts.map((p) => <tr key={p.x}><th>{fmtX(p.x)}</th><td>{fmtY(p.y)}</td></tr>)}
      </tbody></table>
    </figure>
  );
}

const unscored = isUnscored;

const cmpN = (f: (s: State) => number | null) => (a: State, b: State) => (f(a) ?? -1) - (f(b) ?? -1);

function csvCell(v: string | number | null) {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export default function ScorecardView() {
  const { states, districts, national: nat } = useData();
  const route = useRoute();
  const sel = route.s && states.some((s) => s.name === route.s) ? route.s : null;
  const selState = states.find((s) => s.name === sel) ?? null;

  const finding = useMemo(() => {
    const ranked = states.filter((s) => s.evsPerCharger != null);
    const worst = [...ranked].sort((a, b) => b.evsPerCharger! - a.evsPerCharger!)[0];
    const crit = districts.filter((d) => !unscored(d) && d.gapBand >= 4).length;
    const per = nat.chargersOfficial ? nat.evsCumulative / nat.chargersOfficial : null;
    const r = nat.chargersToAddRange;
    const need = r ? ` By 2030 India needs about ${formatCompactIN(r.base['2030'])} more chargers, with a plausible range of ${formatCompactIN(r.low['2030'])} to ${formatCompactIN(r.high['2030'])}.` : '';
    return `India has ${formatCompactIN(nat.evsCumulative)} registered EVs and ${formatIN(nat.chargersOfficial)} official public stations${per ? `, about ${formatIN(per)} EVs per station` : ''}; ${formatIN(crit)} of ${formatIN(districts.length)} districts rate Severe or Critical${worst ? `, and ${worst.name} is most stretched at ${formatIN(worst.evsPerCharger)} EVs per found charger` : ''}.${need}`;
  }, [states, districts, nat]);

  const columns: Column<State>[] = [
    { key: 'name', header: 'State', render: (s) => s.name, compare: (a, b) => b.name.localeCompare(a.name) },
    { key: 'evs', header: 'EVs', align: 'right', render: (s) => formatIN(s.evs), compare: cmpN((s) => s.evs) },
    { key: 'ch', header: 'Chargers found', align: 'right', render: (s) => formatIN(s.chargers), compare: cmpN((s) => s.chargers) },
    { key: 'adj', header: 'Adjusted', align: 'right', render: (s) => formatIN(s.chargersAdjusted), compare: cmpN((s) => s.chargersAdjusted) },
    { key: 'epc', header: 'EVs per charger', align: 'right', render: (s) => formatIN(s.evsPerCharger), compare: cmpN((s) => s.evsPerCharger) },
    {
      key: 'band', header: 'Gap band', render: (s) => (
        <span className="sc-band" data-b={s.gapBand}><i />{gapBandLabel(s.gapBand)}</span>
      ), compare: (a, b) => a.gapScore - b.gapScore,
    },
    { key: 'add', header: 'Add by 2030', align: 'right', render: (s) => formatIN(s.chargersToAdd2030), compare: cmpN((s) => s.chargersToAdd2030) },
  ];

  const exportCsv = () => {
    const head = ['State', 'EVs', 'Chargers found', 'Chargers adjusted', 'EVs per charger', 'Gap band', 'Chargers to add 2030'];
    const lines = [head, ...states.map((s) => [s.name, s.evs, s.chargers, Math.round(s.chargersAdjusted), s.evsPerCharger == null ? null : Math.round(s.evsPerCharger), gapBandLabel(s.gapBand), s.chargersToAdd2030])]
      .map((r) => r.map(csvCell).join(','));
    const url = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: 'ev-infra-states.csv' });
    a.click();
    URL.revokeObjectURL(url);
  };

  const scope = useMemo(() => districts.filter((d) => !sel || d.state === sel), [districts, sel]);
  const worst = useMemo(() => scope.filter((d) => !unscored(d)).sort((a, b) => b.gapScore - a.gapScore).slice(0, 15), [scope]);
  const stationPts = nat.officialSeries.map((p) => ({ x: Date.parse(p.date), y: p.stations })).filter((p) => Number.isFinite(p.x));
  const evPts = nat.evSeries.map((p) => ({ x: p.year, y: p.evs }));
  const fmtDate = (t: number) => new Date(t).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' });

  if (!states.length) return <div className="sc"><EmptyState title="No state data">The states file loaded but is empty.</EmptyState></div>;

  return (
    <div className="sc">
      <header className="sc-head">
        <h1>Scorecard</h1>
        <p className="sc-finding">{finding}</p>
        <dl className="sc-metrics">
          <Stat label="Registered EVs" value={formatCompactIN(nat.evsCumulative)} />
          <Stat label="Official stations found" value={formatPct(nat.coverageShare)} unit={`of ${formatIN(nat.chargersOfficial)}`} />
          <Stat label="Districts Severe or Critical" value={formatIN(districts.filter((d) => !unscored(d) && d.gapBand >= 4).length)} unit={`of ${formatIN(districts.length)}`} modelled />
        </dl>
      </header>

      <Panel title="EV registrations against official stations" className="sc-span">
        <div className="sc-pair">
          <LineChart pts={evPts} title="New EV registrations per year (2026 partial)" fmtY={formatCompactIN} fmtX={String}
            desc={`Registered EVs rose from ${formatCompactIN(evPts[0]?.y)} in ${evPts[0]?.x} to ${formatCompactIN(evPts.at(-1)?.y)} in ${evPts.at(-1)?.x}.`} />
          <LineChart pts={stationPts} title="Official public stations" fmtY={formatIN} fmtX={fmtDate}
            desc={`Official public stations rose from ${formatIN(stationPts[0]?.y)} to ${formatIN(stationPts.at(-1)?.y)}.`}
            note={`Partial coverage: our inventory found ${formatIN(nat.chargersFound)} chargers, ${formatPct(nat.coverageShare)} of the official ${formatIN(nat.chargersOfficial)} (as of ${nat.chargersOfficialAsOf}). The last point comes from a different portal, so part of the jump is a change of source. The two series use separate scales.`} />
        </div>
      </Panel>

      <Panel title="States" className="sc-span" actions={<Button variant="primary" onClick={exportCsv}>Export CSV</Button>}>
        <p className="sc-hint">
          {selState ? <>Showing districts in <strong>{selState.name}</strong>. <a href={hrefFor('planner', { s: selState.name })}>Open in planner</a> · <button className="sc-link" onClick={() => setParams({ s: null })}>Clear filter</button></> : 'Select a state to filter the panels below.'}
        </p>
        <Table className="sc-table" columns={columns} rows={states} rowKey={(s) => s.name} caption="States ranked by EV charging gap"
          defaultSort={{ key: 'epc', dir: 'desc' }} selectedKey={sel}
          onRowSelect={(s) => setParams({ s: s.name === sel ? null : s.name })} />
      </Panel>

      <Panel title={`Worst 15 districts, ${sel ?? 'India'}`} className="sc-span" actions={<ModelledTag />}>
        {worst.length ? (
          <>
            <div onClick={(e) => {
              const i = [...(e.currentTarget.querySelectorAll('li'))].indexOf((e.target as HTMLElement).closest('li') as HTMLLIElement);
              if (i >= 0) navigate('map', { d: worst[i].id });
            }} className="sc-clickable">
              <BarList label="Gap score by district, higher is worse" max={100}
                items={worst.map((d) => ({ label: sel ? d.name : `${d.name}, ${d.state}`, value: d.gapScore, color: `var(--gap-${d.gapBand})`, valueLabel: `${Math.round(d.gapScore)}` }))} />
            </div>
            <details className="sc-links"><summary>Open a district on the map</summary>
              <ul>{worst.map((d) => <li key={d.id}><a href={hrefFor('map', { d: d.id })}>{d.name}</a></li>)}</ul>
            </details>
          </>
        ) : <EmptyState title="No districts">No district data for this selection.</EmptyState>}
      </Panel>

    </div>
  );
}

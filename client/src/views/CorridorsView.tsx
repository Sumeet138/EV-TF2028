import { useMemo, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { useData } from '../lib/data';
import { hrefFor } from '../lib/route';
import { formatIN, formatKm } from '../lib/format';
import { Panel, Table, type Column } from '../ui';
import type { Corridor } from '../types';
import './CorridorsView.css';

const R = 6371;
const hav = (a: [number, number], b: [number, number]) => {
  const rad = Math.PI / 180;
  const dLat = (b[1] - a[1]) * rad, dLon = (b[0] - a[0]) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};

/** Km along the path of each vertex, scaled so the last vertex equals lengthKm. */
function chainage(c: Corridor): number[] {
  const out = [0];
  for (let i = 1; i < c.path.length; i++) out.push(out[i - 1] + hav(c.path[i - 1], c.path[i]));
  const k = out[out.length - 1] > 0 ? c.lengthKm / out[out.length - 1] : 1;
  return out.map((v) => v * k);
}
function at(c: Corridor, ch: number[], p: [number, number]): number {
  let best = 0, bd = Infinity;
  c.path.forEach((v, i) => {
    const d = (v[0] - p[0]) ** 2 + (v[1] - p[1]) ** 2;
    if (d < bd) { bd = d; best = i; }
  });
  return ch[best] ?? 0;
}

function Strip({ c, norm }: { c: Corridor; norm: number }) {
  const W = 1000, PAD = 24, H = 120, Y = 56;
  const { gaps, stations } = useMemo(() => {
    const ch = chainage(c);
    const gaps = c.gapSegments.map((g) => {
      const a = at(c, ch, g.from), b = at(c, ch, g.to);
      return { a: Math.min(a, b), b: Math.max(a, b), km: g.km };
    });
    // Gap ends that are not the corridor ends are where a charger sits.
    const stations = gaps.flatMap((g) => [g.a, g.b]).filter((v) => v > 1 && v < c.lengthKm - 1);
    return { gaps, stations: [...new Set(stations.map((v) => Math.round(v)))] };
  }, [c]);
  const x = (km: number) => PAD + (km / Math.max(c.lengthKm, 1)) * (W - 2 * PAD);
  const ticks: number[] = [];
  const step = norm * Math.max(1, Math.ceil(c.lengthKm / norm / 12));
  for (let k = 0; k <= c.lengthKm; k += step) ticks.push(k);
  return (
    <figure className="strip">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${c.name}: ${formatKm(c.lengthKm)} long, ${gaps.length} gap stretches, longest ${formatKm(c.maxGapKm)}`}>
        <line x1={x(0)} x2={x(c.lengthKm)} y1={Y} y2={Y} className="strip-road" />
        {gaps.map((g, i) => (
          <rect key={i} x={x(g.a)} y={Y - 7} width={Math.max(x(g.b) - x(g.a), 2)} height={14} rx={2}
            className={g.km > norm ? 'strip-gap over' : 'strip-gap'}>
            <title>{`Gap of ${formatKm(g.km)}`}</title>
          </rect>
        ))}
        {stations.map((s) => <circle key={s} cx={x(s)} cy={Y} r={4.5} className="strip-stn" />)}
        {ticks.map((k) => (
          <g key={k}>
            <line x1={x(k)} x2={x(k)} y1={Y + 14} y2={Y + 24} className="strip-tick" />
            <text x={x(k)} y={Y + 40} textAnchor="middle" className="strip-lab">{k}</text>
          </g>
        ))}
        <text x={x(0)} y={16} className="strip-lab">Start</text>
        <text x={x(c.lengthKm)} y={16} textAnchor="end" className="strip-lab">{formatKm(c.lengthKm)}</text>
        <text x={W / 2} y={H - 4} textAnchor="middle" className="strip-lab">Ticks every {step} km (highway spacing norm is {norm} km)</text>
      </svg>
      <figcaption>
        <span><i className="sw gap over" /> gap longer than the norm</span>
        <span><i className="sw gap" /> gap within the norm</span>
        <span><i className="sw stn" /> charger at a gap end</span>
      </figcaption>
    </figure>
  );
}

export default function CorridorsView() {
  const { corridors, meta } = useData();
  const [sel, setSel] = useState<string>(corridors[0]?.id ?? '');
  const c = corridors.find((x) => x.id === sel) ?? corridors[0];
  const norm = meta.norms.highwaySpacingKm;

  const cols: Column<Corridor>[] = [
    { key: 'name', header: 'Corridor', render: (r) => <strong>{r.name}</strong>, compare: (a, b) => b.name.localeCompare(a.name, 'en', { numeric: true }) },
    { key: 'len', header: 'Length', align: 'right', render: (r) => formatKm(r.lengthKm), compare: (a, b) => a.lengthKm - b.lengthKm },
    { key: 'near', header: 'Chargers near', align: 'right', render: (r) => formatIN(r.chargersNear), compare: (a, b) => a.chargersNear - b.chargersNear },
    { key: 'gap', header: 'Max gap', align: 'right', render: (r) => formatKm(r.maxGapKm), compare: (a, b) => a.maxGapKm - b.maxGapKm },
    { key: 'add', header: 'Stations to add', align: 'right', render: (r) => formatIN(r.stationsToAdd), compare: (a, b) => a.stationsToAdd - b.stationsToAdd },
  ];

  return (
    <div className="corr">
      <header className="corr-head">
        <h1>Corridors</h1>
        <p>Highway stretches checked against the {norm} km spacing norm. <a href={hrefFor('map')}>See them on the map <ArrowRight aria-hidden="true" size={14} /></a></p>
      </header>
      <p className="corr-note">Corridor paths come from the MoRTH GatiShakti highway layer (June 2022). Holes in that layer are bridged, so lengths run slightly short. Chargers counted are the ones in our partial inventory.</p>

      <div className="corr-grid">
        <Panel title="All corridors" className="corr-table">
          <Table caption="Corridors with length, chargers nearby, longest gap and stations to add" columns={cols} rows={corridors}
            rowKey={(r) => r.id} defaultSort={{ key: 'add', dir: 'desc' }} selectedKey={c?.id} onRowSelect={(r) => setSel(r.id)} />
        </Panel>
        {c && (
          <Panel title={c.name} className="corr-detail">
            <dl className="corr-facts">
              <div><dt>Length</dt><dd>{formatKm(c.lengthKm)}</dd></div>
              <div><dt>Mean spacing</dt><dd>{formatKm(c.meanSpacingKm)}</dd></div>
              <div><dt>Longest gap</dt><dd>{formatKm(c.maxGapKm)}</dd></div>
              <div><dt>Stations needed</dt><dd>{formatIN(c.stationsRequired)}</dd></div>
              <div><dt>To add</dt><dd>{formatIN(c.stationsToAdd)}</dd></div>
              <div><dt>States</dt><dd>{c.states.join(', ')}</dd></div>
            </dl>
            <Strip c={c} norm={norm} />
          </Panel>
        )}
      </div>
    </div>
  );
}

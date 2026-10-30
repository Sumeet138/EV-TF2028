import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import type { GeoJSONSource, Map as MLMap, ExpressionSpecification, MapLayerMouseEvent } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { X } from 'lucide-react';
import { useData, useChargers, useSubstations } from '../lib/data';
import { setParams, useRoute, hrefFor } from '../lib/route';
import { formatIN, formatPct, gapBandLabel, isUnscored } from '../lib/format';
import { Select, Milestone, ModelledTag } from '../ui';
import type { District, GapBand } from '../types';
import './MapView.css';

type Mode = 'gap' | 'evpc';
type Overlay = 'chargers' | 'substations' | 'corridors' | 'sites' | 'streets';
const OVERLAYS: [Overlay, string][] = [
  ['chargers', 'Chargers'], ['substations', 'Substations'], ['corridors', 'Corridors'],
  ['sites', 'Candidate sites'], ['streets', 'Streets'],
];
const EVPC_STEPS = [50, 100, 200, 400]; // EVs per charger break points for the alternate layer
const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const SRC_COLORS = ['--indigo-dye', '--parrot', '--peacock-700', '--sindoor', '--marigold', '--rani'];

function bounds(geom: unknown): [number, number, number, number] {
  const b: [number, number, number, number] = [180, 90, -180, -90];
  const walk = (c: unknown) => {
    const a = c as number[] | unknown[];
    if (typeof a[0] === 'number') {
      const [x, y] = a as number[];
      b[0] = Math.min(b[0], x); b[1] = Math.min(b[1], y); b[2] = Math.max(b[2], x); b[3] = Math.max(b[3], y);
    } else a.forEach(walk);
  };
  walk((geom as { coordinates: unknown }).coordinates);
  return b;
}

function hatch(): ImageData {
  const c = document.createElement('canvas'); c.width = c.height = 8;
  const g = c.getContext('2d')!;
  g.fillStyle = css('--gap-none'); g.fillRect(0, 0, 8, 8);
  g.strokeStyle = css('--ink-soft'); g.lineWidth = 1;
  g.beginPath(); g.moveTo(0, 8); g.lineTo(8, 0); g.stroke();
  return g.getImageData(0, 0, 8, 8);
}


export default function MapView() {
  const data = useData();
  const route = useRoute();
  const { districts, districtById, geo, national, states } = data;
  const el = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const [mode, setMode] = useState<Mode>('gap');
  const [on, setOn] = useState<Record<Overlay, boolean>>({ chargers: false, substations: false, corridors: false, sites: false, streets: false });
  const [stateF, setStateF] = useState('');
  const [query, setQuery] = useState('');
  const [painted, setPainted] = useState(false);
  const [tip, setTip] = useState<{ x: number; y: number; d: District } | null>(null);
  const selected = route.d ? districtById.get(route.d) ?? null : null;
  const autoPicked = useRef<string | null>(null); // the seeded worst district keeps the national view
  const selRef = useRef(route.d);
  selRef.current = route.d;

  const fc = useMemo(() => ({
    ...geo,
    features: geo.features.map((f) => {
      const d = districtById.get(f.properties.id);
      return { ...f, properties: { id: f.properties.id, state: d?.state ?? '', band: !d || isUnscored(d) ? 0 : d.gapBand, evpc: d?.evsPerCharger ?? -1 } };
    }),
  }), [geo, districtById]);
  const geomById = useMemo(() => new Map(geo.features.map((f) => [f.properties.id, f.geometry])), [geo]);

  const unscored = selected ? isUnscored(selected) : false;
  useEffect(() => {
    if (route.d) return;
    const worst = districts.filter((d) => !isUnscored(d)).sort((a, b) => b.gapScore - a.gapScore)[0];
    if (worst) { autoPicked.current = worst.id; setParams({ d: worst.id }); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (id: string | null) => setParams({ d: id });

  // init map once
  useEffect(() => {
    const m = new maplibregl.Map({
      container: el.current!,
      style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': css('--chalk') } }] },
      bounds: [68, 6, 98, 36.5], fitBoundsOptions: { padding: 20 }, attributionControl: { compact: true },
      minZoom: 2.5, maxZoom: 14,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.on('load', () => {
      m.addImage('hatch', hatch());
      m.addSource('districts', { type: 'geojson', data: fc as never, promoteId: 'id' });
      m.addLayer({ id: 'district-fill', type: 'fill', source: 'districts', paint: { 'fill-color': css('--gap-none'), 'fill-opacity': 1 } });
      m.addLayer({ id: 'district-hatch', type: 'fill', source: 'districts', filter: ['==', ['get', 'band'], 0], paint: { 'fill-pattern': 'hatch' } });
      m.addLayer({ id: 'district-line', type: 'line', source: 'districts', paint: { 'line-color': css('--white'), 'line-width': 0.4 } });
      m.addLayer({ id: 'district-sel', type: 'line', source: 'districts', filter: ['==', ['get', 'id'], ''], paint: { 'line-color': css('--ink'), 'line-width': 2.5 } });
      m.on('click', 'district-fill', (e: MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id as string | undefined;
        if (id) setParams({ d: id });
      });
      m.on('mousemove', 'district-fill', (e: MapLayerMouseEvent) => {
        m.getCanvas().style.cursor = 'pointer';
        const id = e.features?.[0]?.properties?.id as string | undefined;
        const d = id ? districtById.get(id) : undefined;
        setTip(d ? { x: e.point.x, y: e.point.y, d } : null);
      });
      m.on('mouseleave', 'district-fill', () => { m.getCanvas().style.cursor = ''; setTip(null); });
      setMap(m);
      m.once('idle', () => setPainted(true));
    });
    return () => { m.remove(); setMap(null); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // base layer mode + state dim + streets opacity
  useEffect(() => {
    if (!map) return;
    const g = [1, 2, 3, 4, 5].flatMap((b) => [b, css(`--gap-${b}`)]);
    const color: ExpressionSpecification = mode === 'gap'
      ? ['match', ['get', 'band'], ...g, css('--gap-none')] as never
      : ['step', ['get', 'evpc'], css('--gap-none'), 0, css('--gap-1'), EVPC_STEPS[0], css('--gap-2'), EVPC_STEPS[1], css('--gap-3'), EVPC_STEPS[2], css('--gap-4'), EVPC_STEPS[3], css('--gap-5')] as never;
    map.setPaintProperty('district-fill', 'fill-color', color);
    map.setFilter('district-hatch', mode === 'gap' ? ['==', ['get', 'band'], 0] : ['<', ['get', 'evpc'], 0]);
    const base = on.streets ? 0.55 : 1;
    map.setPaintProperty('district-fill', 'fill-opacity', stateF ? ['case', ['==', ['get', 'state'], stateF], base, 0.2] : base);
  }, [map, mode, stateF, on.streets]);

  // selection highlight, fit, restore from URL
  useEffect(() => {
    if (!map) return;
    map.setFilter('district-sel', ['==', ['get', 'id'], selected?.id ?? '']);
    const g = selected && geomById.get(selected.id);
    if (g && autoPicked.current !== selected?.id) {
      const b = bounds(g);
      const narrow = window.innerWidth < 800;
      map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: narrow ? { top: 60, bottom: 280, left: 20, right: 20 } : { top: 40, bottom: 260, left: 40, right: 40 }, maxZoom: 9, duration: 600 });
    }
  }, [map, selected?.id, geomById]); // eslint-disable-line react-hooks/exhaustive-deps

  // state filter fit
  const chooseState = (s: string) => {
    setStateF(s);
    if (!map) return;
    if (!s) { map.fitBounds([68, 6, 98, 36.5] as never, { padding: 20 }); return; }
    const ids = new Set(districts.filter((d) => d.state === s).map((d) => d.id));
    const b: [number, number, number, number] = [180, 90, -180, -90];
    for (const f of geo.features) if (ids.has(f.properties.id)) {
      const x = bounds(f.geometry);
      b[0] = Math.min(b[0], x[0]); b[1] = Math.min(b[1], x[1]); b[2] = Math.max(b[2], x[2]); b[3] = Math.max(b[3], x[3]);
    }
    map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, duration: 600 });
  };

  const inState = useMemo(() => districts.filter((d) => !stateF || d.state === stateF), [districts, stateF]);
  const label = (d: District) => `${d.name}, ${d.state}`;
  const onSearch = (v: string) => {
    setQuery(v);
    const d = districts.find((x) => label(x).toLowerCase() === v.trim().toLowerCase());
    if (d) { pick(d.id); setQuery(''); }
  };
  const stateOpts = [{ value: '', label: 'All states' }, ...states.map((s) => ({ value: s.name, label: s.name }))];
  const distOpts = [{ value: '', label: 'Choose a district' }, ...inState.map((d) => ({ value: d.id, label: stateF ? d.name : label(d) }))];

  return (
    <div className="mapview">
      <div ref={el} className="map-canvas" aria-label="Map of India by district charging gap" />
      {!painted && <p className="map-loading" role="status">Drawing 735 districts</p>}
      {map && <Overlays map={map} on={on} />}

      <div className="map-controls">
        <Select label="State" value={stateF} options={stateOpts} onChange={chooseState} />
        <Select label="District" value={selected?.id ?? ''} options={distOpts} onChange={(v) => pick(v || null)} />
        <div className="field">
          <label htmlFor="map-search">Search district</label>
          <input id="map-search" className="select" list="map-districts" value={query} placeholder="Type a district"
            onChange={(e) => onSearch(e.target.value)} autoComplete="off" />
          <datalist id="map-districts">{inState.map((d) => <option key={d.id} value={label(d)} />)}</datalist>
        </div>
        <fieldset className="map-layers">
          <legend>Layers</legend>
          {([['gap', 'Gap score'], ['evpc', 'EVs per charger']] as [Mode, string][]).map(([k, l]) => (
            <label key={k}><input type="radio" name="mode" checked={mode === k} onChange={() => setMode(k)} />{l}</label>
          ))}
          {OVERLAYS.map(([k, l]) => (
            <label key={k}><input type="checkbox" checked={on[k]} onChange={(e) => setOn({ ...on, [k]: e.target.checked })} />{l}</label>
          ))}
        </fieldset>
      </div>

      <div className="map-legend">
        <strong>{mode === 'gap' ? 'Charging gap' : 'EVs per charger'} {mode === 'evpc' && <ModelledTag />}</strong>
        <ul>
          {([1, 2, 3, 4, 5] as GapBand[]).map((b) => (
            <li key={b}><i className={`sw-${b}`} />
              {mode === 'gap' ? gapBandLabel(b)
                : b === 1 ? `Under ${EVPC_STEPS[0]}` : b === 5 ? `${EVPC_STEPS[3]}+` : `${EVPC_STEPS[b - 2]} to ${EVPC_STEPS[b - 1]}`}
            </li>
          ))}
          <li><i className="hatch" />No data</li>
        </ul>
        <p className="map-coverage">
          Inventory covers {formatPct(national.coverageShare)} of {formatIN(national.chargersOfficial)} official stations
          (as of {national.chargersOfficialAsOf}). A gap is not proof there are no chargers.
        </p>
        {on.streets && <p className="map-coverage">Streets: OpenFreeMap, OpenStreetMap contributors.</p>}
      </div>

      {tip && (
        <div className="map-tip" style={{ left: tip.x + 12, top: tip.y + 12 }} role="presentation">
          <b>{tip.d.name}</b>, {tip.d.state}<br />
          {isUnscored(tip.d) ? 'No data' : `${gapBandLabel(tip.d.gapBand)}, score ${formatIN(tip.d.gapScore)}`}
        </div>
      )}

      {selected && (
        <aside className="map-sheet" aria-label={`${selected.name} detail`}>
          <button className="map-sheet-x" onClick={() => pick(null)} aria-label="Close district panel"><X size={18} /></button>
          <Milestone key={selected.id} cap={selected.code}
            reading={selected.evsPerCharger == null ? 'No chargers found' : formatIN(selected.evsPerCharger)}
            unit={selected.evsPerCharger == null ? 'in our inventory' : 'EVs per charger'}
            sub={`${selected.name}, ${selected.state}`} animate={false} />
          <div className="map-sheet-body">
            <h2>{selected.name} <ModelledTag note={selected.evsSource === 'rto' ? 'Modelled. State VAHAN total split using registrations at the RTOs matched to this district.' : 'Modelled. No RTO matched this district, so the state VAHAN total is split using district indicators.'} /></h2>
            <p className="map-band"><i className={`sw-${unscored ? 0 : selected.gapBand}`} />
              {unscored ? 'No data, not scored' : `${gapBandLabel(selected.gapBand)}, gap score ${formatIN(selected.gapScore)} of 100`}</p>
            {selected.gapDrivers.length > 0 && <ul className="map-drivers">{selected.gapDrivers.map((x) => <li key={x}>{x}</li>)}</ul>}
            <dl>
              <div><dt>Chargers found</dt><dd>{formatIN(selected.chargers)}</dd></div>
              <div><dt>Adjusted for coverage</dt><dd>{formatIN(selected.chargersAdjusted, 1)}</dd></div>
              <div><dt>To add by 2030</dt><dd>{formatIN(selected.forecast['2030'].chargersToAdd)} <ModelledTag /></dd></div>
              <div><dt>Confidence</dt><dd>{selected.confidence}</dd></div>
            </dl>
            {selected.evsPerCharger == null && <p className="map-note">We found no chargers here. The inventory is partial, so this may be a data gap, not an absence.</p>}
            <a className="btn btn-primary" href={hrefFor('planner', { d: selected.id })}>Plan this district</a>
          </div>
        </aside>
      )}
    </div>
  );
}

/** Overlay layers; each child mounts only when toggled so lazy files load on demand. */
function Overlays({ map, on }: { map: MLMap; on: Record<Overlay, boolean> }) {
  return (
    <>
      {on.chargers && <ChargerLayer map={map} />}
      {on.substations && <SubstationLayer map={map} />}
      {on.corridors && <CorridorLayer map={map} />}
      {on.sites && <SiteLayer map={map} />}
      {on.streets && <StreetLayer map={map} />}
    </>
  );
}

function useLayers(map: MLMap, add: () => void, ids: string[], sources: string[], deps: unknown[]) {
  useEffect(() => {
    add();
    return () => {
      if (!map.getStyle()) return;
      ids.forEach((i) => map.getLayer(i) && map.removeLayer(i));
      sources.forEach((s) => map.getSource(s) && map.removeSource(s));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

function ChargerLayer({ map }: { map: MLMap }) {
  const r = useChargers();
  const ready = r.status === 'ready' ? r.data : null;
  useLayers(map, () => {
    if (!ready) return;
    const colors = SRC_COLORS.map(css);
    map.addSource('chargers', {
      type: 'geojson', cluster: true, clusterRadius: 40, clusterMaxZoom: 9,
      data: { type: 'FeatureCollection', features: ready.rows.map((c) => ({ type: 'Feature', properties: { s: c[2], n: c[3] }, geometry: { type: 'Point', coordinates: [c[1], c[0]] } })) } as never,
    });
    map.addLayer({ id: 'ch-cluster', type: 'circle', source: 'chargers', filter: ['has', 'point_count'], paint: { 'circle-color': css('--peacock-700'), 'circle-opacity': 0.85, 'circle-radius': ['step', ['get', 'point_count'], 10, 50, 14, 500, 19], 'circle-stroke-color': css('--white'), 'circle-stroke-width': 1 } });
    map.addLayer({ id: 'ch-pt', type: 'circle', source: 'chargers', filter: ['!', ['has', 'point_count']], paint: { 'circle-color': ['match', ['get', 's'], ...ready.sources.flatMap((_, i) => [i, colors[i % colors.length]]), colors[0]] as never, 'circle-radius': 3.5, 'circle-stroke-color': css('--white'), 'circle-stroke-width': 0.8 } });
    map.on('click', 'ch-cluster', (e: MapLayerMouseEvent) => {
      const f = e.features?.[0]; if (!f) return;
      (map.getSource('chargers') as GeoJSONSource).getClusterExpansionZoom(f.properties.cluster_id).then((z) => map.easeTo({ center: (f.geometry as unknown as { coordinates: number[] }).coordinates as [number, number], zoom: z }));
    });
  }, ['ch-cluster', 'ch-pt'], ['chargers'], [ready]);
  return null;
}

function SubstationLayer({ map }: { map: MLMap }) {
  const r = useSubstations();
  const ready = r.status === 'ready' ? r.data : null;
  useLayers(map, () => {
    if (!ready) return;
    map.addSource('subs', { type: 'geojson', data: { type: 'FeatureCollection', features: ready.map((s) => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [s[1], s[0]] } })) } as never });
    map.addLayer({ id: 'subs', type: 'circle', source: 'subs', paint: { 'circle-color': css('--indigo-dye'), 'circle-radius': 2.5, 'circle-opacity': 0.7 } });
  }, ['subs'], ['subs'], [ready]);
  return null;
}

function CorridorLayer({ map }: { map: MLMap }) {
  const { corridors } = useData();
  useLayers(map, () => {
    const line = (f: (c: (typeof corridors)[number]) => [number, number][][]) => ({ type: 'FeatureCollection', features: corridors.flatMap((c) => f(c).map((p) => ({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: p } }))) });
    map.addSource('cor', { type: 'geojson', data: line((c) => [c.path]) as never });
    map.addSource('cor-gap', { type: 'geojson', data: line((c) => c.gapSegments.map((g) => [g.from, g.to])) as never });
    map.addLayer({ id: 'cor', type: 'line', source: 'cor', paint: { 'line-color': css('--peacock-900'), 'line-width': 2 } });
    map.addLayer({ id: 'cor-gap', type: 'line', source: 'cor-gap', paint: { 'line-color': css('--rani'), 'line-width': 4 } });
  }, ['cor', 'cor-gap'], ['cor', 'cor-gap'], [corridors]);
  return null;
}

function SiteLayer({ map }: { map: MLMap }) {
  const { sites } = useData();
  useLayers(map, () => {
    map.addSource('sites', { type: 'geojson', data: { type: 'FeatureCollection', features: sites.map((s) => ({ type: 'Feature', properties: {}, geometry: { type: 'Point', coordinates: [s.lon, s.lat] } })) } as never });
    map.addLayer({ id: 'sites', type: 'circle', source: 'sites', paint: { 'circle-color': css('--marigold'), 'circle-radius': 5, 'circle-stroke-color': css('--ink'), 'circle-stroke-width': 1.5 } });
  }, ['sites'], ['sites'], [sites]);
  return null;
}

/** OpenFreeMap positron, vector layers without labels (no glyph/sprite dependency). Fails silently. */
function StreetLayer({ map }: { map: MLMap }) {
  useEffect(() => {
    let added: { layers: string[]; sources: string[] } = { layers: [], sources: [] };
    let live = true;
    fetch('https://tiles.openfreemap.org/styles/positron').then((r) => r.json()).then((st) => {
      if (!live || !map.getStyle()) return;
      for (const [k, s] of Object.entries(st.sources)) { map.addSource('ofm-' + k, s as never); added.sources.push('ofm-' + k); }
      for (const l of st.layers) {
        if (l.type === 'symbol' || l.type === 'background') continue;
        map.addLayer({ ...l, id: 'ofm-' + l.id, source: 'ofm-' + l.source }, 'district-line');
        added.layers.push('ofm-' + l.id);
      }
    }).catch(() => undefined);
    return () => {
      live = false;
      if (!map.getStyle()) return;
      added.layers.forEach((i) => map.getLayer(i) && map.removeLayer(i));
      added.sources.forEach((s) => map.getSource(s) && map.removeSource(s));
      added = { layers: [], sources: [] };
    };
  }, [map]);
  return null;
}


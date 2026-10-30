import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type {
  Chargers, Corridor, District, DistrictId, Meta, National, Scenarios, Site, State, SubstationRow,
} from '../types';

/** FeatureCollection with properties.id = DistrictId. */
export interface DistrictGeoJSON {
  type: 'FeatureCollection';
  features: { type: 'Feature'; properties: { id: DistrictId } & Record<string, unknown>; geometry: unknown }[];
}

export interface DataShape {
  geo: DistrictGeoJSON;
  districts: District[];
  states: State[];
  national: National;
  corridors: Corridor[];
  sites: Site[];
  scenarios: Scenarios;
  meta: Meta;
  districtById: Map<DistrictId, District>;
  stateByName: Map<string, State>;
}

const base = () => `${import.meta.env.BASE_URL}data/`;

async function getJSON<T>(file: string): Promise<T> {
  const res = await fetch(base() + file);
  if (!res.ok) throw new Error(`${file}: HTTP ${res.status}`);
  try {
    return (await res.json()) as T;
  } catch {
    throw new Error(`${file}: not valid JSON`);
  }
}

async function loadAll(): Promise<DataShape> {
  const [geo, districts, states, national, corridors, sites, scenarios, meta] = await Promise.all([
    getJSON<DistrictGeoJSON>('districts.geojson'),
    getJSON<District[]>('districts.json'),
    getJSON<State[]>('states.json'),
    getJSON<National>('national.json'),
    getJSON<Corridor[]>('corridors.json'),
    getJSON<Site[]>('sites.json'),
    getJSON<Scenarios>('scenarios.json'),
    getJSON<Meta>('meta.json'),
  ]);
  return {
    geo, districts, states, national, corridors, sites, scenarios, meta,
    districtById: new Map(districts.map((d) => [d.id, d])),
    stateByName: new Map(states.map((s) => [s.name, s])),
  };
}

const Ctx = createContext<DataShape | null>(null);

/** Everything except chargers and substations. Only call under <DataProvider>. */
export function useData(): DataShape {
  const v = useContext(Ctx);
  if (!v) throw new Error('useData must be used inside <DataProvider>');
  return v;
}

// Lazy files: fetched once on first use, cached for the session.
const lazy = new Map<string, Promise<unknown>>();
export type Lazy<T> = { status: 'loading' } | { status: 'error'; error: Error } | { status: 'ready'; data: T };

function useLazy<T>(file: string): Lazy<T> {
  const [state, setState] = useState<Lazy<T>>({ status: 'loading' });
  useEffect(() => {
    let live = true;
    let p = lazy.get(file) as Promise<T> | undefined;
    if (!p) {
      p = getJSON<T>(file);
      lazy.set(file, p);
      p.catch(() => lazy.delete(file)); // allow retry on next mount
    }
    p.then((data) => live && setState({ status: 'ready', data }))
      .catch((e: Error) => live && setState({ status: 'error', error: e }));
    return () => { live = false; };
  }, [file]);
  return state;
}
export const useChargers = () => useLazy<Chargers>('chargers.json');
export const useSubstations = () => useLazy<SubstationRow[]>('substations.json');

export function DataProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Lazy<DataShape>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => { setState({ status: 'loading' }); setAttempt((n) => n + 1); }, []);

  useEffect(() => {
    let live = true;
    loadAll()
      .then((data) => live && setState({ status: 'ready', data }))
      .catch((e: Error) => live && setState({ status: 'error', error: e }));
    return () => { live = false; };
  }, [attempt]);

  const value = useMemo(() => (state.status === 'ready' ? state.data : null), [state]);

  if (state.status === 'loading') {
    return <div className="boot" role="status" aria-live="polite"><span className="boot-dot" />Loading district data</div>;
  }
  if (state.status === 'error') {
    return (
      <div className="boot" role="alert">
        <h1>Data did not load</h1>
        <p>{state.error.message}. Check that the data files are in place, then try again.</p>
        <button className="btn btn-primary" onClick={retry}>Retry</button>
      </div>
    );
  }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

// Shape of every file in client/public/data/. Python writes them, the client reads them.
// Change this file and docs/CONTRACT.md together.

/** Stable id: slug of "<state>-<district>", e.g. "maharashtra-pune". */
export type DistrictId = string;

export type GapBand = 1 | 2 | 3 | 4 | 5; // 1 well served, 5 critical
export type Confidence = 'high' | 'medium' | 'low';

export interface District {
  id: DistrictId;
  name: string;
  state: string; // Title Case, canonical (matches State.name)
  code: string; // Milestone cap, e.g. "MH 12"
  lat: number;
  lon: number;
  areaKm2: number;
  population: number; // Census 2011, split districts apportioned by area
  urbanShare: number; // 0-1
  nightlights: number; // VIIRS 2024 sum
  evs: number; // MODELLED: state VAHAN cumulative allocated to district
  evsSource: 'rto' | 'proxy'; // Allocation weight: matched RTO registrations, or the demographic proxy
  evsByYear: Record<string, number>; // MODELLED: year -> annual registrations
  chargers: number; // Deduplicated stations found in the district
  chargersAdjusted: number; // chargers / state coverage factor, see Meta
  connectors: number | null;
  evsPerCharger: number | null; // evs / chargersAdjusted, null when no chargers
  coverageKm: number; // Share-free metric: mean km from a populated grid cell to the nearest charger
  within3kmShare: number; // 0-1, area share within the MoP urban spacing norm
  substations: number;
  tollPlazas: number;
  gapScore: number; // 0-100, higher is worse
  gapBand: GapBand;
  gapDrivers: string[]; // Up to 3 plain-language reasons
  confidence: Confidence;
  forecast: Record<'2027' | '2030' | '2035', Forecast>;
}

export interface Forecast {
  evs: number;
  chargersRequired: number;
  chargersToAdd: number;
  byType: { ac: number; dc30: number; dc60: number; dc120: number };
  demandMWhPerDay: number;
}

export interface State {
  name: string;
  evs: number; // Measured, VAHAN cumulative
  evsByYear: Record<string, number>; // Measured
  evShare2025: number; // 0-1, EV share of 2025 registrations
  chargers: number;
  chargersAdjusted: number;
  evsPerCharger: number | null;
  coverageFactor: number; // 0-1, share of the state's likely chargers we can see
  gapScore: number;
  gapBand: GapBand;
  districts: number;
  chargersToAdd2030: number;
}

export interface National {
  evsCumulative: number;
  evs2025: number;
  vehicles2025: number;
  chargersFound: number;
  chargersOfficial: number; // Latest official public charging station total
  chargersOfficialAsOf: string;
  coverageShare: number; // chargersFound / chargersOfficial
  officialSeries: { date: string; stations: number }[];
  evSeries: { year: number; evs: number }[];
  chargersToAdd: Record<'2027' | '2030' | '2035', number>;
  chargersToAddRange?: Record<'low' | 'base' | 'high', Record<'2027' | '2030' | '2035', number>> | null;
}

/** Compact: [lat, lon, sourceIndex, name, districtIndex]. districtIndex is into districts.json. */
export type ChargerRow = [number, number, number, string, number];
export interface Chargers {
  sources: string[];
  rows: ChargerRow[];
}

/** [lat, lon, voltageKv | null]. */
export type SubstationRow = [number, number, number | null];

export interface Corridor {
  id: string; // e.g. "nh-48"
  name: string; // e.g. "NH 48"
  path: [number, number][]; // [lon, lat], ordered
  lengthKm: number;
  states: string[];
  chargersNear: number; // Stations within the corridor buffer
  maxGapKm: number; // Longest stretch with no charger in the buffer
  meanSpacingKm: number;
  stationsRequired: number; // To meet the highway spacing norm
  stationsToAdd: number;
  gapSegments: { from: [number, number]; to: [number, number]; km: number }[];
}

export interface Site {
  id: string;
  districtId: DistrictId;
  lat: number;
  lon: number;
  rank: number; // Within district
  chargerType: 'ac' | 'dc30' | 'dc60' | 'dc120';
  connectors: number;
  evsCovered: number;
  nearestSubstationKm: number;
  corridor: string | null;
  reason: string;
}

export interface Assumption {
  id: string;
  label: string;
  value: string;
  source: string;
  kind: 'measured' | 'norm' | 'modelled' | 'assumed';
}

export interface Meta {
  generatedAt: string;
  sources: { name: string; layer: string; rows: number; licence: string; url: string }[];
  assumptions: Assumption[];
  norms: { urbanSpacingKm: number; highwaySpacingKm: number; source: string };
  validation: { check: string; result: string; pass: boolean }[];
}

export type ScenarioKey = 'low' | 'base' | 'high';
export interface Scenarios {
  /** National EV stock by year per scenario. The Planner scales district forecasts with this. */
  series: Record<ScenarioKey, { year: number; evs: number }[]>;
  defaults: {
    kwhPer100km: Record<'2W' | '3W' | '4W', number>;
    fleetMix: Record<'2W' | '3W' | '4W', number>;
    kmPerDay: Record<'2W' | '3W' | '4W', number>;
    publicShare: number;
    utilisation: number;
    typeMix: Forecast['byType'];
  };
  /** National chargers to add, base EVs, by demand-input sensitivity. */
  sensitivity?: Record<ScenarioKey, Record<'2027' | '2030' | '2035', number>>;
}

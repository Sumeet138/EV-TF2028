import { Check, X } from 'lucide-react';
import { useData } from '../lib/data';
import { formatIN, formatPct } from '../lib/format';
import { ModelledTag } from '../ui';
import './MethodView.css';

const STEPS = [
  ['Collect', 'Charger locations from open operator and government sources, VAHAN registrations by state and RTO, Census 2011 population, night lights, substations, toll plazas and district boundaries.'],
  ['Integrate', 'Remove duplicate stations, assign every charger to a district, and attach population, area and grid points to each district.'],
  ['Find gaps', 'Score each district from 0 to 100 on EVs per charger, distance to the nearest charger and share of area inside the urban spacing norm. Divide charger counts by the state coverage factor, because our inventory is partial.'],
  ['Forecast', 'Allocate state EV registrations to districts, project 2027, 2030 and 2035 under low, base and high scenarios, then convert to chargers and energy demand.'],
  ['Corridors and sites', 'Trace each highway from MoRTH geometry, find stretches longer than the spacing norm, and rank candidate sites near demand and substations.'],
] as const;

const KIND_LABEL = { measured: 'Measured', norm: 'Norm', modelled: 'Modelled', assumed: 'Assumed' } as const;

export default function MethodView() {
  const { meta, national, districts, states } = useData();
  const covered = states.filter((s) => s.coverageFactor >= 0.5).length;
  return (
    <article className="method">
      <header>
        <h1>Method</h1>
        <p>How the numbers are made, what each one rests on, and where it can mislead. Generated {meta.generatedAt.slice(0, 10)}.</p>
      </header>

      <section aria-labelledby="m-pipe">
        <h2 id="m-pipe">How it works</h2>
        <ol className="steps">
          {STEPS.map(([t, d]) => <li key={t}><strong>{t}.</strong> {d}</li>)}
        </ol>
      </section>

      <section aria-labelledby="m-src">
        <h2 id="m-src">Data sources</h2>
        <div className="table-wrap"><table className="table">
          <caption className="sr-only">Data sources with layer, rows and licence</caption>
          <thead><tr><th>Source</th><th>Layer</th><th className="num">Rows</th><th>Licence</th></tr></thead>
          <tbody>{meta.sources.map((s) => (
            <tr key={s.name}>
              <td>{s.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> : s.name}</td>
              <td>{s.layer}</td><td className="num">{formatIN(s.rows)}</td><td>{s.licence}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </section>

      <section aria-labelledby="m-ass">
        <h2 id="m-ass">Assumptions</h2>
        <p>Every figure that is not a direct measurement is listed here with its kind.</p>
        <div className="table-wrap"><table className="table">
          <caption className="sr-only">Assumptions with value, source and kind</caption>
          <thead><tr><th>Assumption</th><th>Value</th><th>Source</th><th>Kind</th></tr></thead>
          <tbody>{meta.assumptions.map((a) => (
            <tr key={a.id}>
              <td>{a.label}</td><td>{a.value}</td><td>{a.source}</td>
              <td><span className={`kind kind-${a.kind}`}>{KIND_LABEL[a.kind]}</span></td>
            </tr>
          ))}</tbody>
        </table></div>
        <p>Norms: urban spacing {meta.norms.urbanSpacingKm} km, highway spacing {meta.norms.highwaySpacingKm} km. {meta.norms.source}</p>
      </section>

      <section aria-labelledby="m-val">
        <h2 id="m-val">Validation checks</h2>
        <ul className="checks">
          {meta.validation.map((v) => (
            <li key={v.check}>
              {v.pass ? <Check aria-hidden="true" size={16} className="ok" /> : <X aria-hidden="true" size={16} className="bad" />}
              <span><strong>{v.pass ? 'Pass' : 'Fail'}.</strong> {v.check}. {v.result}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="m-lim">
        <h2 id="m-lim">Known limits</h2>
        <ul className="limits">
          <li>
            <strong>Coverage is partial.</strong> We found {formatIN(national.chargersFound)} stations against {formatIN(national.chargersOfficial)} officially reported
            as of {national.chargersOfficialAsOf}, a coverage of {formatPct(national.coverageShare)}. A district with no chargers here may have some we cannot see. Treat a gap as a place to check, not proof of absence.
          </li>
          <li>
            <strong>District EV counts are modelled.</strong> <ModelledTag /> State VAHAN totals are measured. We allocate them to {formatIN(districts.length)} districts using matched RTO registrations, or household and night-light indicators where no RTO matched, so district figures carry error even where state totals are exact.
          </li>
          <li>Coverage factors differ by state; {covered} of {states.length} states have a factor of 0.5 or more, so adjusted counts are least reliable elsewhere.</li>
          <li>Corridor paths use MoRTH highway geometry from June 2022. Holes in that layer are bridged with straight lines.</li>
          <li>District EVs use RTO registrations where an RTO matched. RTO areas are not district boundaries, and a vehicle may charge away from where it is registered.</li>
          <li>Census 2011 population is old. Split districts are apportioned by area.</li>
          <li>Site recommendations are candidates for survey, not approved locations. Land, ownership and grid capacity are not checked.</li>
        </ul>
      </section>
    </article>
  );
}

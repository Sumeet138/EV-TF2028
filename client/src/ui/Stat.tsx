import type { ReactNode } from 'react';
import { ModelledTag } from './ModelledTag';

export interface StatProps {
  label: string;
  value: ReactNode;
  /** Small unit or qualifier after the value, e.g. "per charger" */
  unit?: string;
  modelled?: boolean;
  className?: string;
}
/** A plain label/value pair for use inside panels. Not a KPI card. */
export function Stat({ label, value, unit, modelled, className = '' }: StatProps) {
  return (
    <div className={`stat ${className}`}>
      <dt>{label}{modelled && <ModelledTag />}</dt>
      <dd>{value}{unit && <span className="stat-unit"> {unit}</span>}</dd>
    </div>
  );
}

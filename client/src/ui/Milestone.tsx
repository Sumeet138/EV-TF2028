import type { ReactNode } from 'react';

export interface MilestoneProps {
  /** Marigold cap text, e.g. "MH 12" */
  cap: string;
  /** The big reading, already formatted, e.g. "1,240" */
  reading: ReactNode;
  /** Unit line under the reading, e.g. "EVs per charger" */
  unit: string;
  /** Small line at the foot, e.g. "Pune, Maharashtra" */
  sub?: string;
  /** Slide up on mount (240ms). Give the element key={id} to replay on selection change. */
  animate?: boolean;
  className?: string;
}
/** NH milestone: white stone, marigold rounded cap. Signature component, use only for the selected district and planner next stops. */
export function Milestone({ cap, reading, unit, sub, animate = true, className = '' }: MilestoneProps) {
  return (
    <figure className={`milestone ${animate ? 'milestone-in' : ''} ${className}`}>
      <div className="milestone-cap">{cap}</div>
      <div className="milestone-body">
        <div className="milestone-reading">{reading}</div>
        <div className="milestone-unit">{unit}</div>
        {sub && <figcaption className="milestone-sub">{sub}</figcaption>}
      </div>
    </figure>
  );
}

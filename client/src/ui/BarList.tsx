export interface BarItem {
  label: string;
  value: number;
  /** CSS colour, use a token: 'var(--rani)' */
  color?: string;
  /** Overrides the formatted value text */
  valueLabel?: string;
}
export interface BarListProps {
  items: BarItem[];
  /** Scale max; defaults to the largest value */
  max?: number;
  format?: (v: number) => string;
  label: string;
  className?: string;
}
export function BarList({ items, max, format = String, label, className = '' }: BarListProps) {
  const top = max ?? Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className={`barlist ${className}`} aria-label={label}>
      {items.map((i) => (
        <li key={i.label}>
          <span className="barlist-label" title={i.label}>{i.label}</span>
          <svg className="barlist-bar" viewBox="0 0 100 10" preserveAspectRatio="none" aria-hidden="true">
            <rect x="0" y="0" width="100" height="10" fill="var(--line)" opacity="0.5" />
            <rect x="0" y="0" width={Math.max(0, Math.min(100, (i.value / top) * 100))} height="10" fill={i.color ?? 'var(--peacock-700)'} />
          </svg>
          <span className="barlist-value">{i.valueLabel ?? format(i.value)}</span>
        </li>
      ))}
    </ul>
  );
}

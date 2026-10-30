import { useId } from 'react';

export interface SelectProps<V extends string> {
  label: string;
  value: V;
  options: { value: V; label: string }[];
  onChange: (v: V) => void;
  className?: string;
}
export function Select<V extends string>({ label, value, options, onChange, className = '' }: SelectProps<V>) {
  const id = useId();
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id}>{label}</label>
      <select id={id} className="select" value={value} onChange={(e) => onChange(e.target.value as V)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

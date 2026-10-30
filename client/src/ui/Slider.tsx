import { useId } from 'react';

export interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  /** Text for the current value, e.g. v => `${v}%` */
  format?: (v: number) => string;
  className?: string;
}
export function Slider({ label, value, min, max, step = 1, onChange, format, className = '' }: SliderProps) {
  const id = useId();
  return (
    <div className={`field slider ${className}`}>
      <div className="slider-head">
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id}>{format ? format(value) : value}</output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </div>
  );
}

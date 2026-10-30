import type { KeyboardEvent } from 'react';

export interface TabsProps<V extends string> {
  label: string;
  value: V;
  items: { id: V; label: string }[];
  onChange: (v: V) => void;
  className?: string;
}
/** Tab buttons only; the view renders the matching panel and may give it role="tabpanel". */
export function Tabs<V extends string>({ label, value, items, onChange, className = '' }: TabsProps<V>) {
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const i = items.findIndex((t) => t.id === value);
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = items[(i + step + items.length) % items.length];
    onChange(next.id);
    (e.currentTarget.querySelector(`[data-tab="${next.id}"]`) as HTMLElement | null)?.focus();
  };
  return (
    <div role="tablist" aria-label={label} className={`tabs ${className}`} onKeyDown={onKey}>
      {items.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          data-tab={t.id}
          aria-selected={t.id === value}
          tabIndex={t.id === value ? 0 : -1}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

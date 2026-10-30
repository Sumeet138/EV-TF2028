import { useMemo, useState, type ReactNode } from 'react';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Present = sortable. Return negative/zero/positive like Array.sort. */
  compare?: (a: T, b: T) => number;
  align?: 'left' | 'right';
}
export interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  caption: string;
  /** { key, dir } of the initial sort; a column key with compare. */
  defaultSort?: { key: string; dir: 'asc' | 'desc' };
  selectedKey?: string | null;
  /** Makes rows keyboard-activatable (Enter or Space on the row). */
  onRowSelect?: (row: T) => void;
  className?: string;
}

export function Table<T>({ columns, rows, rowKey, caption, defaultSort, selectedKey, onRowSelect, className = '' }: TableProps<T>) {
  const [sort, setSort] = useState(defaultSort ?? null);
  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sort?.key);
    if (!col?.compare || !sort) return rows;
    const s = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => s * col.compare!(a, b));
  }, [rows, columns, sort]);

  const toggle = (key: string) =>
    setSort((p) => (p?.key === key ? { key, dir: p.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }));

  return (
    <div className={`table-wrap ${className}`}>
      <table className="table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => {
              const active = sort?.key === c.key;
              return (
                <th
                  key={c.key}
                  scope="col"
                  className={c.align === 'right' ? 'num' : ''}
                  aria-sort={c.compare ? (active ? (sort!.dir === 'asc' ? 'ascending' : 'descending') : 'none') : undefined}
                >
                  {c.compare ? (
                    <button type="button" onClick={() => toggle(c.key)}>
                      {c.header}
                      <span className="sort-mark" aria-hidden="true">{active ? (sort!.dir === 'asc' ? '▲' : '▼') : ''}</span>
                    </button>
                  ) : c.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const k = rowKey(r);
            return (
              <tr
                key={k}
                aria-selected={onRowSelect ? k === selectedKey : undefined}
                data-selected={k === selectedKey || undefined}
                tabIndex={onRowSelect ? 0 : undefined}
                onClick={onRowSelect && (() => onRowSelect(r))}
                onKeyDown={onRowSelect && ((e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowSelect(r); }
                })}
              >
                {columns.map((c) => <td key={c.key} className={c.align === 'right' ? 'num' : ''}>{c.render(r)}</td>)}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

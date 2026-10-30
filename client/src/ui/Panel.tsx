import type { ElementType, ReactNode } from 'react';

export interface PanelProps {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
  as?: ElementType;
  className?: string;
}
export function Panel({ title, actions, children, as: Tag = 'section', className = '' }: PanelProps) {
  return (
    <Tag className={`panel ${className}`}>
      {(title || actions) && (
        <header className="panel-head">
          {title && <h2>{title}</h2>}
          {actions && <div className="panel-actions">{actions}</div>}
        </header>
      )}
      {children}
    </Tag>
  );
}

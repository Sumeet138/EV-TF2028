import { useSyncExternalStore } from 'react';

export type View = 'map' | 'scorecard' | 'planner' | 'corridors' | 'method';
export const VIEWS: View[] = ['map', 'scorecard', 'planner', 'corridors', 'method'];

export interface Route {
  view: View;
  /** Selected district id (?d=) */
  d: string | null;
  /** Selected state name (?s=) */
  s: string | null;
  params: URLSearchParams;
}

function subscribe(cb: () => void) {
  window.addEventListener('hashchange', cb);
  return () => window.removeEventListener('hashchange', cb);
}
const snapshot = () => window.location.hash;

function parse(hash: string): Route {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const params = new URLSearchParams(query);
  const view = (VIEWS as string[]).includes(path) ? (path as View) : 'map';
  return { view, d: params.get('d'), s: params.get('s'), params };
}

/** Build an href for a view. Pass params: { d: 'maharashtra-pune' } to carry a selection. */
export function hrefFor(view: View, params: Record<string, string | null | undefined> = {}): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, v);
  const qs = q.toString();
  return `#/${view}${qs ? `?${qs}` : ''}`;
}

export function navigate(view: View, params: Record<string, string | null | undefined> = {}) {
  window.location.hash = hrefFor(view, params);
}

/** Update params on the current view without adding a history entry. */
export function setParams(params: Record<string, string | null | undefined>) {
  const r = parse(window.location.hash);
  const merged: Record<string, string | null | undefined> = { d: r.d, s: r.s, ...params };
  history.replaceState(null, '', hrefFor(r.view, merged));
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, snapshot);
  return parse(hash); // cheap; views should depend on route.d / route.s / route.view strings
}

import { lazy, Suspense } from 'react';
import { BarChart3, BookOpen, Map as MapIcon, Route as RouteIcon, SlidersHorizontal, Zap, type LucideIcon } from 'lucide-react';
import { DataProvider, useData } from './lib/data';
import { formatPct } from './lib/format';
import { hrefFor, useRoute, type View } from './lib/route';
import './ui';

const views: Record<View, ReturnType<typeof lazy>> = {
  map: lazy(() => import('./views/MapView')),
  scorecard: lazy(() => import('./views/ScorecardView')),
  planner: lazy(() => import('./views/PlannerView')),
  corridors: lazy(() => import('./views/CorridorsView')),
  method: lazy(() => import('./views/MethodView')),
};

const NAV: { view: View; label: string; Icon: LucideIcon }[] = [
  { view: 'map', label: 'Map', Icon: MapIcon },
  { view: 'scorecard', label: 'Scorecard', Icon: BarChart3 },
  { view: 'planner', label: 'Planner', Icon: SlidersHorizontal },
  { view: 'corridors', label: 'Corridors', Icon: RouteIcon },
  { view: 'method', label: 'Method', Icon: BookOpen },
];

function Shell() {
  const route = useRoute();
  const { national } = useData();
  const View = views[route.view];
  return (
    <div className="shell">
      <aside className="rail on-dark">
        <a className="brand" href={hrefFor('map')}>
          <Zap aria-hidden="true" />
          <span>EV Infra Map India</span>
        </a>
        <nav aria-label="Views">
          {NAV.map(({ view, label, Icon }) => (
            <a
              key={view}
              href={hrefFor(view, { d: route.d, s: route.s })}
              aria-current={route.view === view ? 'page' : undefined}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <p className="coverage">
          Inventory covers <strong>{formatPct(national.coverageShare)}</strong> of official stations. A gap may be missing data, not a missing charger.
        </p>
      </aside>
      <main id="main">
        <Suspense fallback={<div className="boot" role="status">Loading view</div>}>
          <View />
        </Suspense>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <DataProvider>
      <Shell />
    </DataProvider>
  );
}

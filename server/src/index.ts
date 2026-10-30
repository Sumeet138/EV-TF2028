// One server: built client + a small read-only API over the same JSON the client loads (no database).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import express from 'express';
import helmet from 'helmet';

const here = path.dirname(fileURLToPath(import.meta.url));
const DATA = path.resolve(here, '../../client/public/data');
const DIST = path.resolve(here, '../../client/dist');
const PORT = Number(process.env.PORT) || 5000;
const TILES = 'https://tiles.openfreemap.org';

// Loaded once at startup; a missing file stops the server with the file name.
const load = <T,>(f: string): T => JSON.parse(fs.readFileSync(path.join(DATA, f), 'utf8')) as T;
/* eslint-disable @typescript-eslint/no-explicit-any */
const districts = load<any[]>('districts.json');
const states = load<any[]>('states.json');
const national = load<any>('national.json');
const corridors = load<any[]>('corridors.json');
const sites = load<any[]>('sites.json');
const meta = load<any>('meta.json');
const districtById = new Map(districts.map((d) => [d.id, d]));

const app = express();
app.disable('x-powered-by');
app.use(
  helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'"],
        styleSrc: ["'self'", "'unsafe-inline'"], // MapLibre sets inline styles
        imgSrc: ["'self'", 'data:', 'blob:', TILES],
        fontSrc: ["'self'", 'data:'],
        connectSrc: ["'self'", TILES],
        workerSrc: ["'self'", 'blob:'], // MapLibre workers
        childSrc: ["'self'", 'blob:'],
        objectSrc: ["'none'"],
        upgradeInsecureRequests: null, // plain http on localhost
      },
    },
  }),
);

const api = express.Router();
const notFound = (res: express.Response, what: string) => res.status(404).json({ error: `${what} not found` });

api.get('/health', (_req, res) => res.json({ status: 'ok', districts: districts.length, generatedAt: meta.generatedAt }));
api.get('/national', (_req, res) => res.json(national));
api.get('/states', (_req, res) => res.json(states));
api.get('/states/:name', (req, res) => {
  const q = req.params.name.toLowerCase();
  const s = states.find((x) => x.name.toLowerCase() === q);
  if (!s) return notFound(res, `State "${req.params.name}"`);
  res.json({ ...s, districtList: districts.filter((d) => d.state === s.name).map((d) => d.id) });
});
api.get('/districts', (req, res) => {
  const { state, band } = req.query;
  let out = districts;
  if (typeof state === 'string') out = out.filter((d) => d.state.toLowerCase() === state.toLowerCase());
  if (typeof band === 'string') out = out.filter((d) => String(d.gapBand) === band);
  res.json(out);
});
api.get('/districts/:id', (req, res) => {
  const d = districtById.get(req.params.id);
  if (!d) return notFound(res, `District "${req.params.id}"`);
  res.json({ ...d, sites: sites.filter((s) => s.districtId === d.id) });
});
api.get('/corridors', (_req, res) => res.json(corridors));
api.get('/sites', (req, res) => {
  const id = req.query.districtId;
  res.json(typeof id === 'string' ? sites.filter((s) => s.districtId === id) : sites);
});
api.get('/meta', (_req, res) => res.json(meta));
api.use((req, res) => notFound(res, `Route ${req.originalUrl}`));
app.use('/api', api);

// Built client (present after `npm run build`). SPA is hash-routed, so index.html covers every other path.
if (fs.existsSync(DIST)) {
  app.use(express.static(DIST));
  app.get('/{*splat}', (_req, res) => res.sendFile(path.join(DIST, 'index.html')));
}

app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));

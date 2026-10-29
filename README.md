# EV TF2028

React 19 + Vite 8 (client) and Express 5 (server), TypeScript, npm workspaces.

## Setup
```sh
npm install
cp .env.example .env
npm run dev   # client :5173, server :5000 (Vite proxies /api)
```

## Scripts
- `npm run dev` – run both with hot reload
- `npm run build` – build client then server
- `npm start` – run built server (`NODE_ENV=production` serves `client/dist`)
- `npm run typecheck`

## Layout
```
client/   React + Vite
server/   Express API (src/index.ts)
```

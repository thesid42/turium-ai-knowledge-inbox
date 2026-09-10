# Turium frontend

Vite + React 19 + TypeScript + Tailwind CSS v4 client for the Turium API.

Setup, run, and configuration instructions live in the [root README](../README.md).
API contract: [`docs/API.md`](../docs/API.md). Design notes: [`docs/DESIGN.md`](../docs/DESIGN.md).

```powershell
npm install
npm run dev     # http://localhost:5173, proxies /api/* to http://localhost:8000
npm run build   # type check + production build
npm run lint    # oxlint
```

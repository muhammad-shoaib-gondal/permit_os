# EstatePermit landing page (moved)

The marketing landing page now lives inside the unified frontend at [`../web/`](../web/):

| Path | Purpose |
|------|---------|
| `web/index.html` | Marketing landing (served at `/`) |
| `web/public/css/`, `web/public/js/` | Landing styles and scripts |
| `web/app/index.html` | React product app (served at `/app`) |

## Local development (single command)

```bash
cd ../web
npm install
npm run dev
```

- **Marketing:** http://localhost:5173/
- **Product app:** http://localhost:5173/app (linked from “Launch app” on the landing page)

Start the API separately:

```bash
cd ..
uvicorn api.main:app --reload --port 8000
```

## Production

`npm run build` in `web/` produces:

- `dist/index.html` — landing at `/`
- `dist/app/index.html` — React app at `/app`
- `dist/css/`, `dist/js/` — landing assets

FastAPI serves both when `web/dist` exists.

This folder is kept for reference; edit the files under `web/` instead.

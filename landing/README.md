# EstatePermit landing page

Static marketing site (vanilla HTML/CSS/JS). The product app lives in `web/` (React + Vite).

## Preview locally

From repo root:

```bash
# Python
python -m http.server 8080 --directory landing

# Or npx
npx serve landing -p 8080
```

Open http://localhost:8080

## Deploy notes

- **Landing:** serve `landing/` at `/` (or `www.estatepermit.com`)
- **App:** build `web/` with `npm run build` and serve `web/dist` at `/app`
- Update `href="/app"` in `index.html` if your app URL differs

## Files

```
landing/
  index.html      # Full page
  css/styles.css
  js/main.js      # Nav, FAQ accordion, waitlist mailto
```

Built on branch `feature/estatepermit-landing-page`.

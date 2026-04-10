# TN Elections 2026 Dashboard

Interactive, bilingual dashboard for the 2026 Tamil Nadu Legislative Assembly election. The app is a static single-page site built with vanilla HTML, CSS, and JavaScript, with D3 for the constituency map and Chart.js for charts.

## What It Includes

- Interactive map for all 234 assembly constituencies with view modes for constituency map, 2021 winners, and 2016 winners.
- Constituency detail drawer with voter demographics, prior winners, and deferred candidate enrichment when candidate JSON is available.
- Candidate modal with photo, party, financial disclosures, criminal-case summary, and validated ECI affidavit links.
- Searchable constituency table and enriched candidates table with sorting and pagination.
- State overview charts, party/alliance views, and historical results summaries.
- Manifesto comparison plus a previous-term manifesto audit section for 2021 and 2016 with source-backed fulfillment notes.
- Full English and Tamil UI support.
- Light and dark themes with responsive mobile behavior.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript (ES2020-style browser code) |
| Map | D3.js v7 |
| Charts | Chart.js |
| Fonts | Fontshare: General Sans, Cabinet Grotesk |
| Hosting | Static deployment on Vercel |
| Local preview | Python `http.server` or any static file server |

## Project Structure

```
.
├── public/
│   ├── app.js
│   ├── data.js
│   ├── dataLoader.js
│   ├── favicon.svg
│   ├── index.html
│   ├── styles.css
│   ├── tn_constituencies.geojson
│   └── data/
│       ├── tn2026_all_candidates.json
│       ├── tn2026_by_constituency.json
│       └── tn2026_summary.json
├── research/
│   ├── manifesto_audit_summary.json
│   ├── manifesto_audit_tracker.csv
│   └── manifesto_official_evidence.json
├── archive/
├── vercel.json
└── README.md
```

## Data Model

- `public/data.js` contains the static constituency, party, alliance, and localization data needed for baseline rendering.
- `public/dataLoader.js` loads optional enriched candidate JSON from `public/data/`.
- The app still works in fallback mode if the enriched candidate files are missing or fail to load.
- `research/` contains the source pack used for the manifesto audit section and supporting evidence notes.

## Key Runtime Behavior

- The initial load renders the core shell, map, and static dataset first.
- Candidate-heavy JSON is now lazy-loaded only when the user enters candidate-heavy experiences such as the Constituency Table, State Overview candidate charts, or a constituency detail panel that needs enriched candidate records.
- D3 and Chart.js are loaded with `defer`, and external font/CDN hosts are preconnected.
- Candidate images and affidavit links are validated before use.

## Security And Hardening

- Dynamic user-visible content rendered from external data is escaped before insertion into the DOM.
- Candidate photo and symbol URLs are restricted to allowed HTTPS hosts.
- ECI affidavit links are validated before being opened.
- Search input is normalized before filtering operations.
- Vercel response headers include:
  - Content Security Policy
  - Referrer Policy
  - `X-Content-Type-Options: nosniff`
  - Permissions Policy

Note: the current CSP still permits `'unsafe-inline'` scripts because `index.html` still uses inline event handlers. That is an intentional compatibility compromise in the current version, not an unnoticed gap.

## Performance Notes

- Initial page load no longer fetches enriched candidate JSON by default.
- Third-party libraries are deferred.
- The candidate table and candidate charts are built only when needed.
- The dashboard keeps a static fallback path so the first paint does not depend on large candidate data responses.

## Responsive Behavior

- Header and language toggle are stabilized across English and Tamil.
- Mobile tabs are easier to tap and remain usable on narrow screens.
- Hidden off-canvas panels are non-interactive while closed, preventing accidental click interception.
- Search inputs and selectors use mobile-friendly sizing.

## Running Locally

Because this is a static site, no Node or build pipeline is required.

From the repository root:

```powershell
Set-Location "d:\TN Elections 2026 Dashboard\public"
& "d:/TN Elections 2026 Dashboard/.venv/Scripts/python.exe" -m http.server 8000
```

Then open `http://127.0.0.1:8000/index.html`.

Any static file server is fine as long as it serves the `public/` directory and allows the JSON and GeoJSON files to be fetched over HTTP.

## Deployment

Vercel is configured to serve the `public/` directory as the static output.

Current deployment config:

```json
{
  "outputDirectory": "public",
  "framework": null,
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://api.fontshare.com; font-src 'self' data: https:; img-src 'self' data: https:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests"
        },
        {
          "key": "Referrer-Policy",
          "value": "strict-origin-when-cross-origin"
        },
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "Permissions-Policy",
          "value": "camera=(), microphone=(), geolocation=()"
        }
      ]
    }
  ]
}
```

## End-To-End Validation Completed

The current version was manually and ad hoc verified for these flows:

- Initial dashboard load and map rendering.
- Language toggle and Tamil rendering in the manifesto audit section.
- Mobile header stability across language changes.
- Constituency table loading and enriched candidate-table lazy load.
- Candidate charts loading when entering the overview tab.
- Detail panel opening and candidate modal opening.
- Validated affidavit button wiring.
- No initial candidate JSON fetch until candidate-heavy UI is opened.
- No favicon 404 after adding `public/favicon.svg`.

## Known Remaining Tradeoff

- Inline event handlers in `public/index.html` are still present. Functionally this is fine, but if you want a stricter CSP without `'unsafe-inline'`, those handlers should be converted to event listeners in JavaScript.

## Primary Data Sources

- Election Commission of India
- Tamil Nadu Chief Electoral Officer resources
- Official Tamil Nadu government portals referenced in the manifesto audit evidence pack
- Historical election result references already embedded in the project dataset

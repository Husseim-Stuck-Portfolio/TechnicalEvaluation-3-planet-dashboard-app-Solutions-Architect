# ForestGuard EUDR

Satellite-powered forest carbon & supply-chain compliance screening for the
EU Deforestation Regulation (Regulation (EU) 2023/1115, cutoff 2020-12-31).

**Analytical decision support only - not legal advice, not a regulatory
declaration.** Detected changes are alerts for human review.

## Objective

Help EUDR compliance teams screen supplier production plots for potential
deforestation and degradation after the regulatory cutoff, quantify
carbon impacts, prioritise field verification, and export auditable
screening evidence.

## Core components

| Component | What it does |
|---|---|
| Business logic | Explainable screening rules + transparent 0-100 risk score (weights in `src/config.py`) |
| Map interface | Folium map, plots coloured by risk, popups with full screening story |
| Analytical view | Plotly charts: risk distribution, per-plot canopy/carbon trajectory with EUDR cutoff marker, risk-score derivation |
| Information dashboard | KPIs + sortable plot table; everything filterable and CSV-exportable |
| Interactivity | Sidebar thresholds/filters, map clicks and table selection drive all tabs; downloads in every tab |
| Evidence | Per-plot evidence records + generated, timestamped markdown report with limitations |

## Data & assumptions

- **Demo AOI:** Pará, Brazil (-6.77, -52.37) - the only sandbox region present
  in *both* Forest Carbon Diligence (2015-2017) and Forest Carbon Monitoring
  (2020-12-21 - 2023-09-21) collections, enabling the full
  baseline -> cutoff -> quarterly-monitoring narrative.
- **Bundled dataset is 100% SYNTHETIC** (`scripts/generate_sample_data.py`,
  seed 42): 24 plots / 5 suppliers / annual measurements 2015-2023 across six
  scenarios (stable forest, post-cutoff clearing, gradual degradation,
  selective logging, secondary growth, long-converted agriculture). It
  demonstrates every dashboard state including all four risk categories.
- **Planet mode (optional):** `src/planet_client.py` is an isolated adapter
  for the Subscriptions API (FCM layers, quarterly cadence). Any failure -
  no key, 401/403/429/5xx, delivery timeout - falls back to sample mode.
- **Known limitation:** the FCD archive ends 2017 while FCM starts at the
  cutoff; the gap is disclosed in the app and the report.

## Local deployment

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/generate_sample_data.py              # regenerates demo data (deterministic)
streamlit run app.py
```

Optional: `pip install pytest && pytest -q` (26 tests covering metrics,
risk scoring, validation, geodesy and the end-to-end pipeline).

Optional Planet mode: copy `.env.example` to `.env`, add `PLANET_API_KEY` and
the three FCM BYOC collection ids from Planet Docs > Sandbox Data, then select
"Planet API" in the sidebar.

## Architecture

```
app.py                    thin UI layer (6 tabs)
src/config.py             single source of truth for thresholds/weights
src/validation.py         loud failures, actionable messages
src/geospatial.py         UTM-projected area maths (never degrees)
src/metrics.py            summarise -> detect_change (pure functions)
src/risk_scoring.py       normalised, weighted, fully explained score
src/data_loader.py        access layer; builds the flat risk table
src/reporting.py          CSV + markdown evidence report
src/planet_client.py      Subscriptions API adapter (offline-safe)
src/ui_components.py      map + Plotly widgets
scripts/generate_sample_data.py   deterministic synthetic Pará dataset
tests/                    26 unit + pipeline tests
```

Engineering rules: hectare maths only in projected CRS; API key never
hard-coded/logged; expensive loads cached (`st.cache_data`); every threshold
user-adjustable; every score decomposable to its components.

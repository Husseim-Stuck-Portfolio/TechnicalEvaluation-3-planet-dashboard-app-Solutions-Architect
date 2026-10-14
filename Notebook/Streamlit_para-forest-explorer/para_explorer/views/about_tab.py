"""Tab: narrative for the technical panel - user story, requirement mapping, caveats."""
from __future__ import annotations

import streamlit as st

TEXT = """
### User story
*As a regional forest-monitoring analyst in Pará I need to know **where vegetation vigour dropped between 2021 and 2023, how big and how
persistent those areas are, and how much I can trust the evidence** - before I send a field team or open a PRODES/DETER cross-check.*

Planet's daily 3 m imagery makes the temporal resolution possible; this app turns annual composites into a **change budget, candidate
patches and a robustness score**, shows how many images stand behind every composite, and lets the analyst browse the underlying Planet
scenes (cloud/date filters) without downloading anything.

### Brief → feature map
| Requirement | Where in the app |
|---|---|
| Business logic / insights | Change budget (ha, %), trajectory classes, connected decline patches with robustness score |
| Map interface | 3-D globe: composites (true colour, NDVI, change, trajectory), patches, Planet scene footprints, CDSE basemap |
| Analytical view | Histogram, budget bars, sensitivity curves, patch NDVI history, monthly/yearly scene statistics |
| Information dashboard | KPI strip, composite table (images used), ranked patch table, scene table |
| Interactivity | Sidebar thresholds → map + KPIs + charts; table row → globe fly-to + inspector; bar click → previews + footprints |
| Stretch | Planet Data API (Stats + quick-search + thumbnails), CDSE STAC, Sentinel Hub Catalog counts, threshold-sensitivity analysis |

### Architecture
`precompute` (once, in Jupyter/CLI) → analysis-ready NDVI GeoTIFFs + previews + counts → Streamlit loads, filters and displays.
Large arrays are cached as resources, small results by parameters; maps receive ≤1200 px overlays; Planet counts come from the
server-side Stats API (no paging through tens of thousands of scenes); thumbnails are fetched per page, in parallel, and kept in memory only.

### Known limitations (read before quoting a number)
* **NDVI change ≠ deforestation.** A decrease marks a *candidate* disturbance; cause is not identified.
* Composites are built from different acquisition sets; part of any difference can be atmospheric, phenological or radiometric.
* Three annual points give a trajectory *classification*, not a trend. Seasonality needs more dates.
* Image counts are catalog items (tiles/scenes); a day can contain several. Count is not a measure of *clear* observations.
* The sandbox data are CC-BY-NC and limited to 2021-01-01 → 2023-12-29; the Data API search covers the account's entitlement (2016-2026).
* Pixel areas use WGS-84 degree lengths per row (error « 1 %).
"""


def render(ctx) -> None:
    st.markdown(TEXT)

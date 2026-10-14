"""Tab: method, the three notebooks, limitations and next steps."""
from __future__ import annotations

import streamlit as st

from .. import texts as X

BRIEF = """
### Brief → feature map
| Requirement | Where in the app |
|---|---|
| Business logic / insights | Change budget (ha, %), trajectory classes, connected decline patches with robustness score |
| Map interface | 3-D globe: composites (true colour, NDVI, change, trajectory), patches, Planet scene footprints, CDSE basemap |
| Analytical view | Histogram, budget bars, sensitivity curves, patch NDVI history, monthly/yearly scene statistics |
| Information dashboard | KPI strip, composite table (images used), ranked patch table, scene table |
| Interactivity | Sidebar thresholds → map + KPIs + charts; table row → globe fly-to + inspector; bar click → previews + footprints |
| Stretch | Planet Data API (Stats + quick-search + thumbnails), CDSE STAC and Sentinel-2 image, Sentinel Hub Catalog counts, sensitivity analysis, PDF report |

### Architecture
`precompute` (once) → analysis-ready NDVI GeoTIFFs + previews + counts → Streamlit loads, filters and displays.
Large arrays are cached as resources, small results by parameters; maps receive ≤1200 px overlays; Planet counts come from the
server-side Stats API; thumbnails are fetched per page and kept in memory only; credentials come from the environment, Streamlit
secrets or a password field and are never displayed or logged.
"""


def render(ctx) -> None:
    st.markdown("### User story")
    st.markdown("*A forest-monitoring analyst wants to identify areas in Pará that may have experienced vegetation loss between 2021 and 2023. "
                "The app compares satellite imagery, calculates NDVI change, highlights possible change patches, and provides statistics that "
                "help prioritise areas for further investigation.*")
    st.markdown("**Why it matters.** Forest loss can affect biodiversity, carbon storage, water cycles, local communities and climate goals. "
                "Frequent satellite observations help organisations detect and investigate changes earlier. Satellite analysis does not replace "
                "field verification or official deforestation assessments - this is a decision-support tool for prioritising locations and communicating evidence.")
    st.markdown("### How NDVI works")
    st.markdown(X.NDVI_EXPLANATION)
    st.code(X.NDVI_FORMULA)

    st.markdown("### The three notebooks")
    cols = st.columns(3, gap="medium")
    for col, (title, fname, bullets, blurb) in zip(cols, X.NOTEBOOKS):
        with col:
            st.markdown(f"**{title}**  \n`{fname}`")
            st.markdown("\n".join(f"- {b}" for b in bullets))
            st.caption(blurb)

    st.markdown(BRIEF)
    st.markdown("### Known limitations (read before quoting a number)")
    st.warning(X.SEASONAL_LIMITATION)
    st.markdown("\n".join(f"* {t}" for t in X.LIMITATIONS if t != X.SEASONAL_LIMITATION))
    st.markdown("### Future scope / next steps")
    st.markdown("\n".join(f"* {t}" for t in X.FUTURE_SCOPE))
    st.caption(X.FUTURE_NOTE)

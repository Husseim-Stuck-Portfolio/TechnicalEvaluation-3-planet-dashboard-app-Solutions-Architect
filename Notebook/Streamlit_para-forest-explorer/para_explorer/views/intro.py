"""Beginner-friendly introduction shown at the top of the page: purpose, vocabulary and how to read the results."""
from __future__ import annotations

import streamlit as st

GLOSSARY = [
    ("Satellite imagery", "Pictures and measurements of Earth collected from space."),
    ("PlanetScope", "Frequent, high-resolution satellite imagery produced by Planet (the 2021-2023 composites in this app come from it)."),
    ("Copernicus Sentinel-2", "An openly available European Earth-observation mission for land monitoring. It measures many spectral bands, "
                              "including the red and near-infrared bands that are useful for vegetation (10 m, 20 m and 60 m bands)."),
    ("NDVI", "An index that estimates the presence and condition of green vegetation. Dense healthy forest is close to 0.8-0.9; bare soil is low."),
    ("NDVI value", "A number from −1 to +1 calculated from red and near-infrared reflectance: (NIR − Red) ÷ (NIR + Red)."),
    ("NDVI change", "The difference between the NDVI of two dates or periods (later − earlier). Negative = less vegetation later."),
    ("Composite", "A representative image built by combining many observations, usually to reduce clouds and atmospheric effects."),
    ("Pixel", "One small cell of a satellite image (here about 10 m × 10 m on the ground)."),
    ("Patch", "A connected group of pixels that show a similar type of change."),
    ("AOI", "Area of interest - the region selected for analysis (here 568 km² in Pará, Brazil)."),
    ("Moderate change", "A noticeable but not necessarily severe change (|ΔNDVI| above the moderate threshold)."),
    ("Strong change", "A larger change that may require further investigation (|ΔNDVI| above the strong threshold)."),
]

LEARN = [
    "Where did vegetation decrease?",
    "How large are the affected areas?",
    "Was the change concentrated in a few patches?",
    "Did the change occur consistently across different datasets (Planet vs Copernicus)?",
    "Could the change be caused by seasonality, clouds, fire or land-use change?",
    "Which areas require further investigation?",
]

CAUTION = ("**NDVI is not a direct measurement of deforestation.** It is an indicator of vegetation condition. A strong decrease may "
           "suggest forest clearing, fire damage, flooding, drought, harvest activity, seasonal effects, cloud contamination, or other "
           "land-surface changes.")

USES = ["Possible deforestation", "Forest degradation", "Vegetation loss", "Fire damage", "Agricultural expansion",
        "Seasonal vegetation differences", "Reforestation or vegetation recovery", "Areas that need field validation or additional data"]


def user_story() -> None:
    st.markdown(
        '<div class="pe-card"><h4>Why this app exists</h4>'
        '<div class="pe-note" style="font-size:.92rem;line-height:1.5">A <b>forest-monitoring analyst</b> wants to identify areas in Pará that may have '
        'experienced vegetation loss between 2021 and 2023. The app compares satellite imagery, calculates NDVI change, highlights possible '
        'change patches, and provides statistics that help <b>prioritise areas for further investigation</b>. It is a decision-support tool: '
        'it does not replace field verification or official deforestation assessments.</div></div>', unsafe_allow_html=True)


def basics() -> None:
    with st.expander("📘 New to satellite data? Start here - what NDVI is and what you can learn", expanded=True):
        c1, c2 = st.columns([1.35, 1], gap="large")
        with c1:
            st.markdown("##### Key terms in plain language")
            half = (len(GLOSSARY) + 1) // 2
            g1, g2 = st.columns(2)
            for col, items in ((g1, GLOSSARY[:half]), (g2, GLOSSARY[half:])):
                col.markdown("\n\n".join(f"**{t}**: {d}" for t, d in items))
        with c2:
            st.markdown("##### How NDVI change is calculated")
            st.markdown("1. NDVI per composite = (NIR − Red) ÷ (NIR + Red) (bands B, G, R, NIR → red = band 3, NIR = band 4).\n"
                        "2. Change = NDVI of the later year − NDVI of the earlier year, pixel by pixel.\n"
                        "3. Pixels are sorted into *strong / moderate decrease*, *little change*, *moderate / strong increase* with the thresholds in the sidebar.\n"
                        "4. Connected strong-decrease pixels form **patches**, ranked by area.")
            st.info(CAUTION)
            st.markdown("##### What can I learn from this?")
            st.markdown("\n".join(f"- {q}" for q in LEARN))
        st.markdown("##### It helps to investigate")
        st.markdown(" · ".join(USES))
        st.caption("Planet describes its Earth-observation products as supporting forest monitoring, land-use-change detection, "
                   "biodiversity monitoring, climate-risk analysis and forest-carbon applications "
                   "([planet.com](https://www.planet.com/)). Sentinel-2 band information: "
                   "[Copernicus Data Space documentation](https://documentation.dataspace.copernicus.eu/Data/Sentinel2.html).")

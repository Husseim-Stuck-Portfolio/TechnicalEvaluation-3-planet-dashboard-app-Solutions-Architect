"""Shared wording for the app (Method & limits tab) and the PDF report, so both always say the same thing."""
from __future__ import annotations

NDVI_FORMULA = "NDVI = (NIR − Red) / (NIR + Red)"
NDVI_EXPLANATION = (
    "NDVI (Normalized Difference Vegetation Index) estimates the presence and condition of green vegetation from red and "
    "near-infrared reflectance. Healthy leaves absorb red light and reflect near-infrared light, so dense forest has high NDVI "
    "(about 0.8-0.9 here) while bare soil, burnt areas and water have low values. In the composites the band order is Blue, "
    "Green, Red, NIR, so red is band 3 and NIR is band 4. NDVI change is the NDVI of the later period minus the earlier one.")

SEASONAL_LIMITATION = (
    "The compared scenes or annual composites may represent different seasons. A difference in NDVI may therefore reflect rainfall "
    "and seasonal vegetation dynamics rather than permanent land-cover change. For stronger conclusions, compare images from "
    "similar months, use multiple observations per year, and apply cloud and quality masks consistently.")

INTERPRETATION = (
    "The NDVI change map identifies locations where vegetation conditions differed between the selected periods. Areas with negative "
    "change may indicate vegetation loss, but they may also result from seasonality, cloud contamination, fire, drought, flooding, "
    "harvest, or different acquisition dates. Results should therefore be interpreted as areas for investigation rather than "
    "confirmed deforestation.")

LIMITATIONS = [
    "NDVI change is an indicator for investigation, not definitive proof of deforestation; the cause of a change is not identified.",
    SEASONAL_LIMITATION,
    "Each annual composite is built from a different set of acquisitions, so atmospheric, phenological and radiometric differences can leak into the change.",
    "Three annual points give a trajectory classification, not a statistically established trend.",
    "Image counts are scenes/tiles, not a measure of clear observations; a day can contain several scenes.",
    "Planet and Copernicus differ in sensor response, resolution, dates and processing; their NDVI values are comparable but not identical.",
    "Thresholds are analyst choices (limited here to 0.10-0.20); the reported area moves with them, see the sensitivity chart.",
    "Pixel areas use WGS-84 degree lengths per raster row (error well below 1 %).",
    "The sandbox data are licensed CC-BY-NC and cover 2021-01-01 to 2023-12-29.",
]

FUTURE_SCOPE = [
    "Compare images from the same months or seasons.",
    "Use monthly or quarterly time series instead of only annual composites.",
    "Add rainfall data.",
    "Add soil-moisture or soil-condition indicators.",
    "Add temperature and drought indicators.",
    "Add fire and burn-scar data.",
    "Add true-colour and false-colour composites.",
    "Add indices related to water, burn severity or vegetation stress.",
    "Add land-cover and protected-area layers.",
    "Compare results with official deforestation datasets (PRODES, DETER, MapBiomas).",
    "Add automated alerts for new change patches.",
    "Add confidence scores.",
    "Add field observations or validation points.",
    "Add cloud-probability and image-quality reporting.",
    "Add user-uploaded areas of interest.",
    "Add authenticated Planet API processing.",
    "Add scheduled data updates.",
    "Add historical time-series charts.",
    "Add automated PDF report generation on a schedule.",
    "Add a model to distinguish likely deforestation from seasonal or atmospheric effects.",
]
FUTURE_NOTE = "Each of these would require additional data, validation and processing time; none is implied by the current results."

NOTEBOOKS = [
    ("1 · Imagery discovery", "1_Planet_API_imagery_discovery.ipynb",
     ["Authenticate with the Planet API", "Define the area of interest", "Search for available imagery",
      "Inspect metadata, dates, cloud cover, assets and image availability", "Identify suitable scenes or collections"],
     "This notebook is responsible for discovering and inspecting available Planet imagery. Separating discovery from processing makes it "
     "easier to verify that suitable data exist before downloading or analyzing them."),
    ("2 · Data preparation", "2_planet_sandbox_Para_BRA_sentinelhub.ipynb",
     ["Request or load imagery", "Retrieve the relevant bands", "Apply preprocessing", "Create annual composites",
      "Save the analysis-ready raster outputs"],
     "This notebook prepares consistent annual imagery for the Pará AOI. Keeping data retrieval and preprocessing separate ensures that "
     "the analysis notebook receives standardized inputs."),
    ("3 · NDVI analysis", "3_planet_sandbox_Para_BRA_sentinelhub_Analysis_NDVI.ipynb",
     ["Calculate NDVI and NDVI change", "Classify moderate and strong decreases or increases", "Calculate area and percentage statistics",
      "Identify connected change patches", "Create graphs, maps and exports"],
     "This notebook performs the analytical and interpretive work. Separating it from data discovery and preprocessing makes the workflow "
     "easier to test, explain, reproduce and reuse."),
]

DATA_SOURCES = [
    "Planet sandbox collection PS_ARD_SR_DAILY (PlanetScope surface reflectance), accessed through Sentinel Hub: annual composites 2021-2023.",
    "Planet Data API: scene metadata and previews (cloud cover, acquisition dates) - discovery only, imagery is not redistributed.",
    "Copernicus Data Space Ecosystem: area of interest, Sentinel-2 L2A availability (STAC) and a cloud-masked Sentinel-2 image for comparison.",
]

STUDY_AREA = ("Study area: a 568 km² rectangle in Pará, North Region, Brazil (centre ≈ 52.37° W, 6.77° S), mostly tropical forest. "
              "The polygon was exported from the Copernicus Data Space Ecosystem browser.")

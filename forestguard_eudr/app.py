"""ForestGuard EUDR - Streamlit entry point.

Run:  streamlit run app.py
Works fully offline in sample-data mode (default). Planet API mode is
optional and degrades gracefully to sample mode on any failure.
"""
from __future__ import annotations

import ast
import json

import pandas as pd
import streamlit as st

from src.config import (APP_NAME, APP_VERSION, DATA_DIR, DEFAULT_THRESHOLDS,
                        EUDR_CUTOFF_DATE, RISK_WEIGHTS, Thresholds)
from src.data_loader import (build_risk_table, load_evidence, load_measurements,
                             load_plots, load_suppliers)
from src.metrics import portfolio_kpis
from src.reporting import build_evidence_report, to_csv_bytes
from src.ui_components import (plot_trend_chart, render_map, risk_breakdown_chart,
                               risk_distribution_chart, risk_map,
                               supplier_carbon_chart)

st.set_page_config(page_title=APP_NAME, layout="wide")
st.title(f"{APP_NAME} v{APP_VERSION}")
st.caption("Satellite-powered forest carbon & supply-chain compliance "
           "screening - analytical decision support, not legal advice.")

# ------------------------------------------------------------ sidebar controls
with st.sidebar:
    st.header("Analysis setup")
    mode = st.radio("Data mode", ["Sample data (offline demo)",
                                  "Planet API (optional)"],
                    help="Planet mode requires a Planet account with Monitoring "
                         "Credits and the env vars from .env.example.")
    baseline_year = st.slider("Baseline year", 2015, 2022, 2015)
    comparison_year = st.slider("Comparison year", baseline_year + 1, 2023, 2023)
    st.divider()
    st.header("Screening thresholds (adjustable)")
    th = Thresholds(
        min_baseline_canopy_cover_percent=st.number_input(
            "Min baseline canopy cover (%)", 0.0, 100.0,
            DEFAULT_THRESHOLDS.min_baseline_canopy_cover_percent),
        canopy_cover_loss_threshold_percent=st.number_input(
            "Canopy loss threshold (%)", 0.0, 100.0,
            DEFAULT_THRESHOLDS.canopy_cover_loss_threshold_percent),
        minimum_affected_area_percent=st.number_input(
            "Min affected area (%)", 0.0, 100.0,
            DEFAULT_THRESHOLDS.minimum_affected_area_percent),
        carbon_loss_threshold_mg_per_ha=st.number_input(
            "Carbon loss threshold (Mg/ha)", 0.0, 400.0,
            DEFAULT_THRESHOLDS.carbon_loss_threshold_mg_per_ha),
        height_loss_threshold_m=st.number_input(
            "Height loss threshold (m)", 0.0, 80.0,
            DEFAULT_THRESHOLDS.height_loss_threshold_m),
        risk_score_alert_threshold=st.number_input(
            "Alert score threshold", 0.0, 100.0,
            DEFAULT_THRESHOLDS.risk_score_alert_threshold),
        reference_canopy_loss_percent=DEFAULT_THRESHOLDS.reference_canopy_loss_percent,
        reference_carbon_loss_mg_ha=DEFAULT_THRESHOLDS.reference_carbon_loss_mg_ha,
        reference_height_loss_m=DEFAULT_THRESHOLDS.reference_height_loss_m,
    )

if mode.startswith("Planet"):
    st.info("Planet API mode: this prototype ships with the adapter "
            "(src/planet_client.py). With no valid key configured it falls "
            "back to sample data - which is what you are seeing now.")

# ------------------------------------------------------------ data + analytics
@st.cache_data
def get_data():
    return (load_suppliers(DATA_DIR), load_plots(DATA_DIR),
            load_measurements(DATA_DIR), load_evidence(DATA_DIR))

@st.cache_data
def get_risk(base_y: int, comp_y: int, th_json: str):
    _, plots, meas, _ = get_data()
    return build_risk_table(plots, meas, base_y, comp_y, Thresholds(**json.loads(th_json)))

suppliers, plots, measurements, evidence = get_data()
risk = get_risk(baseline_year, comparison_year, json.dumps(th.__dict__))

# filters
with st.sidebar:
    st.divider()
    st.header("Filters")
    f_sup = st.multiselect("Supplier", sorted(risk["supplier_name"].unique()))
    f_com = st.multiselect("Commodity", sorted(risk["commodity"].unique()))
    f_cat = st.multiselect("Risk category", ["Low", "Moderate", "High", "Critical"])
flt = risk.copy()
if f_sup: flt = flt[flt["supplier_name"].isin(f_sup)]
if f_com: flt = flt[flt["commodity"].isin(f_com)]
if f_cat: flt = flt[flt["risk_category"].isin(f_cat)]

selected_plot = st.session_state.get("selected_plot")
if selected_plot not in set(flt["plot_id"]):
    selected_plot = None

tabs = st.tabs(["Executive Overview", "Supply Chain Explorer", "Plot Risk Map",
                "Forest & Carbon Trends", "Evidence & Due Diligence",
                "Methodology & Limitations"])

# ---------------------------------------------------------- 1 executive overview
with tabs[0]:
    k = portfolio_kpis(flt)
    c = st.columns(5)
    c[0].metric("Plots monitored", f"{k['total_plots']}  ({k['total_area_ha']:,.0f} ha)")
    c[1].metric("Low risk", k["low_risk"])
    c[2].metric("High / Critical", f"{k['high_risk']} / {k['critical_risk']}")
    c[3].metric("Post-cutoff alerts", k["post_cutoff_alerts"])
    c[4].metric("Est. carbon loss (Mg/ha sum)", f"{k['estimated_carbon_loss_mg']:,.0f}")
    st.write(f"Plots missing legality evidence: **{k['missing_evidence']}**  |  "
             f"Mean data completeness: **{k['mean_data_completeness_percent']}%**")
    a, b = st.columns(2)
    a.plotly_chart(risk_distribution_chart(flt), use_container_width=True)
    b.plotly_chart(supplier_carbon_chart(flt), use_container_width=True)
    st.download_button("Download filtered results (CSV)",
                       to_csv_bytes(flt), "forestguard_results.csv", "text/csv")

# ---------------------------------------------------------- 2 supply chain explorer
with tabs[1]:
    st.subheader("Plot-level screening table")
    show_cols = ["plot_id", "supplier_name", "commodity", "area_ha",
                 "baseline_canopy_cover_percent", "latest_canopy_cover_percent",
                 "canopy_cover_change_percent", "carbon_loss_mg_ha",
                 "detected_change_year", "post_cutoff_change",
                 "legality_document_available", "alert_types",
                 "risk_score", "risk_category", "confidence",
                 "recommended_action"]
    styled = flt[show_cols].sort_values("risk_score", ascending=False)
    st.dataframe(styled, use_container_width=True, hide_index=True,
                 column_config={"post_cutoff_change": st.column_config.CheckboxColumn(
                     "Post-cutoff change")})
    st.caption("Selecting a plot here drives the Map and Trends tabs.")
    pick = st.selectbox("Focus plot", ["(none)"] + sorted(flt["plot_id"].tolist()))
    if pick != "(none)":
        st.session_state["selected_plot"] = pick
        selected_plot = pick

# ---------------------------------------------------------- 3 plot risk map
with tabs[2]:
    if selected_plot:
        st.success(f"Selected plot: **{selected_plot}** "
                   f"(click polygons or pick in Supply Chain Explorer)")
    render_map(risk_map(flt, selected_plot))

# ---------------------------------------------------------- 4 trends
with tabs[3]:
    if selected_plot:
        st.plotly_chart(plot_trend_chart(measurements, selected_plot),
                        use_container_width=True)
        row = flt[flt["plot_id"] == selected_plot].iloc[0]
        st.write(f"**{selected_plot}** ({row['supplier_name']}): risk "
                 f"**{row['risk_score']}** ({row['risk_category']}) - "
                 f"{row['alert_types']}, confidence: {row['confidence']}")
        try:
            breakdown = ast.literal_eval(row["risk_breakdown"])
        except (ValueError, SyntaxError):
            breakdown = {}
        if breakdown:
            st.plotly_chart(risk_breakdown_chart(breakdown), use_container_width=True)
    else:
        st.info("Select a plot (map click or Supply Chain Explorer) to see its "
                "forest & carbon trajectory and risk derivation.")

# ---------------------------------------------------------- 5 evidence
with tabs[4]:
    if selected_plot:
        ev = evidence[evidence["plot_id"] == selected_plot]
        st.subheader(f"Evidence records - {selected_plot}")
        st.dataframe(ev, use_container_width=True, hide_index=True)
        row = flt[flt["plot_id"] == selected_plot].iloc[0]
        try:
            breakdown = ast.literal_eval(row["risk_breakdown"])
        except (ValueError, SyntaxError):
            breakdown = {}
        report = build_evidence_report(row, th, breakdown)
        st.download_button("Download evidence report (.md)", report.encode("utf-8"),
                           f"evidence_{selected_plot}.md", "text/markdown")
    else:
        st.info("Select a plot to review its due-diligence evidence.")
    miss = flt[~flt["legality_document_available"]][
        ["plot_id", "supplier_name", "risk_category"]]
    st.subheader("Plots missing legality documents")
    st.dataframe(miss if len(miss) else pd.DataFrame({"note": ["none"]}),
                 use_container_width=True, hide_index=True)

# ---------------------------------------------------------- 6 methodology
with tabs[5]:
    st.subheader("Risk model")
    st.table(pd.DataFrame(
        [{"component": n, "weight_percent": w} for n, w in RISK_WEIGHTS.items()]))
    st.write(f"Categories: Low 0-24 | Moderate 25-49 | High 50-74 | Critical 75-100. "
             f"Alert threshold: {th.risk_score_alert_threshold}. "
             f"EUDR cutoff: {EUDR_CUTOFF_DATE}.")
    st.subheader("Limitations (read before relying on any number)")
    for item in [
        "Forest Carbon Diligence is annual at ~30 m; Forest Carbon Monitoring is "
        "quarterly at 3 m. The demo uses SYNTHETIC annual data - never present "
        "it as real operational evidence.",
        "Detected changes are alerts for human investigation, not proof of "
        "illegal deforestation or legal non-compliance.",
        "Carbon density is a modelled estimate, not a certified carbon-credit inventory.",
        "EUDR compliance also requires legality and supply-chain evidence that "
        "satellite data alone cannot provide.",
        "The 2017-2020 gap between the FCD and FCM archives limits direct "
        "cutoff-date comparison; production deployments should fuse both products.",
        "Country context risk is a configurable business heuristic, not a Planet product.",
    ]:
        st.write("- " + item)

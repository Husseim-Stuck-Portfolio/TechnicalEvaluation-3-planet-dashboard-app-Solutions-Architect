"""Reusable Streamlit/Plotly/Folium components. Kept out of app.py so the
UI layer stays thin and every widget is testable in isolation."""
from __future__ import annotations

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .config import RISK_COLORS, RISK_WEIGHTS

CENTER = [-6.77, -52.37]  # Pará demo AOI


def risk_map(risk: pd.DataFrame, selected_plot: str | None = None) -> folium.Map:
    """Supplier plots coloured by risk category, popup with the full story."""
    fmap = folium.Map(location=CENTER, zoom_start=11, tiles="CartoDB positron")
    for _, row in risk.iterrows():
        color = RISK_COLORS.get(row["risk_category"], "#888888")
        weight = 4 if row["plot_id"] == selected_plot else 1.5
        popup = folium.Popup(
            f"<b>{row['plot_id']}</b> - {row['supplier_name']}<br>"
            f"Commodity: {row['commodity']} | Area: {row['area_ha']} ha<br>"
            f"Risk: <b>{row['risk_score']}</b> ({row['risk_category']})<br>"
            f"Canopy change: {row['canopy_cover_change_percent']:+.1f}%<br>"
            f"Carbon loss: {row['carbon_loss_mg_ha']} Mg/ha<br>"
            f"Alerts: {row['alert_types']}<br>"
            f"Action: {row['recommended_action']}", max_width=320)
        folium.GeoJson(
            row["geometry"].__geo_interface__ if hasattr(row["geometry"], "__geo_interface__")
            else row["geometry"],
            style_function=lambda c, col=color, w=weight: {
                "fillColor": col, "color": "#222222", "weight": w,
                "fillOpacity": 0.55 if w > 2 else 0.35},
            popup=popup, tooltip=f"{row['plot_id']} - {row['risk_category']}",
        ).add_to(fmap)
    legend_html = "<div style='position:fixed;bottom:20px;left:20px;z-index:1000;" \
        "background:white;padding:8px 12px;border-radius:6px;box-shadow:0 0 6px #999;'>" \
        "<b>Risk category</b><br>" + "<br>".join(
        f"<span style='color:{c};font-weight:bold;'>&#9632;</span> {n}"
        for n, c in RISK_COLORS.items()) + "</div>"
    fmap.get_root().html.add_child(folium.Element(legend_html))
    return fmap


def render_map(fmap: folium.Map) -> None:
    """Render folium map in Streamlit without requiring streamlit-folium."""
    import streamlit as st
    try:
        from streamlit_folium import st_folium
        result = st_folium(fmap, use_container_width=True, height=520)
        if result and result.get("last_object_clicked_tooltip"):
            clicked = result["last_object_clicked_tooltip"].split(" - ")[0]
            st.session_state["selected_plot"] = clicked
    except ImportError:
        st.components.v1.html(fmap._repr_html_(), height=540)


def risk_distribution_chart(risk: pd.DataFrame) -> go.Figure:
    order = ["Low", "Moderate", "High", "Critical"]
    counts = risk["risk_category"].value_counts().reindex(order, fill_value=0)
    fig = px.bar(x=counts.index, y=counts.values, color=counts.index,
                 color_discrete_map=RISK_COLORS,
                 labels={"x": "Risk category", "y": "Plots"},
                 title="Risk category distribution")
    fig.update_layout(showlegend=False, yaxis_title="Number of plots")
    return fig


def plot_trend_chart(measurements: pd.DataFrame, plot_id: str) -> go.Figure:
    sub = measurements[measurements["plot_id"] == plot_id].sort_values("year")
    fig = go.Figure()
    fig.add_scatter(x=sub["year"], y=sub["canopy_cover_percent"],
                    name="Canopy cover (%)", yaxis="y1")
    fig.add_scatter(x=sub["year"], y=sub["carbon_density_mg_ha"],
                    name="Carbon density (Mg/ha)", yaxis="y2")
    fig.update_layout(
        title=f"Forest & carbon trajectory - {plot_id}",
        yaxis=dict(title="Canopy cover (%)", range=[0, 100]),
        yaxis2=dict(title="Carbon density (Mg/ha)", overlaying="y",
                    side="right", range=[0, 400]),
        hovermode="x unified",
        shapes=[dict(type="line", x0=2020.99, x1=2020.99, y0=0, y1=1,
                     yref="paper", line=dict(dash="dash", color="red"))],
        annotations=[dict(x=2020.99, y=1.02, yref="paper", showarrow=False,
                          text="EUDR cutoff (2020-12-31)", font=dict(color="red"))],
    )
    return fig


def supplier_carbon_chart(risk: pd.DataFrame) -> go.Figure:
    grp = (risk.groupby("supplier_name", as_index=False)["carbon_loss_mg_ha"]
           .sum().sort_values("carbon_loss_mg_ha", ascending=False))
    fig = px.bar(grp, x="carbon_loss_mg_ha", y="supplier_name", orientation="h",
                 labels={"carbon_loss_mg_ha": "Sum of plot carbon loss (Mg/ha)",
                         "supplier_name": "Supplier"},
                 title="Estimated carbon loss by supplier (demo units)")
    return fig


def risk_breakdown_chart(breakdown: dict) -> go.Figure:
    names = list(breakdown.keys())
    weights = [RISK_WEIGHTS[n] for n in names]
    contrib = [breakdown[n] for n in names]
    fig = go.Figure(go.Bar(
        x=contrib, y=names, orientation="h",
        text=[f"w={w}%, contributes {c}" for w, c in zip(weights, contrib)],
        textposition="auto"))
    fig.update_layout(title="How this score was built (contribution points)",
                      xaxis_title="Points contributed to total score")
    return fig

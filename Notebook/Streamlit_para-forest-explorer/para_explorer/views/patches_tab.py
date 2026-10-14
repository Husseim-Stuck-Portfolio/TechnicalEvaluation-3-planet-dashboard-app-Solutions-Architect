"""Tab: ranked disturbance patches linked to the map (idea 3)."""
from __future__ import annotations

import json

import plotly.graph_objects as go
import streamlit as st

from para_explorer import compat

from .. import config as C
from .. import theme as T

TABLE_KEY = "patch_table"


def selected_row(df):
    """Row picked in the table on the *previous* run (selection lives in session_state)."""
    try:
        rows = st.session_state[TABLE_KEY]["selection"]["rows"]
        return df.iloc[rows[0]] if rows and rows[0] < len(df) else None
    except (KeyError, TypeError, IndexError):
        return None


def render(ctx) -> None:
    df, s = ctx.patch_df, ctx.patch_summary
    st.markdown(f"#### Decline patches {ctx.a} → {ctx.b}")
    st.caption(f"ΔNDVI ≤ −{ctx.t_strong:.2f}, cleaned with a 3×3 opening/closing, connected with 8-neighbourhood. "
               f"{s.get('total_candidates', 0):,} candidates → {s.get('kept', 0):,} ≥ {ctx.min_ha} ha → {len(df):,} after the sidebar filters. "
               "Select a row: the globe flies to the patch and the inspector shows its history.")
    if df.empty:
        if s.get("total_candidates", 0) == 0:
            st.info("No pixels exceed the selected NDVI-decrease threshold for these years. Try a lower threshold.")
        elif s.get("kept", 0) == 0:
            st.info("No vegetation-change patches meet the selected minimum size.\n\nTry a smaller patch-size threshold.")
        else:
            st.info("No patches pass the robustness / recovery filters in the sidebar. Relax them to see the candidates.")
        return
    cols = ["patch_id", "area_ha", "mean_change", "max_decline", f"ndvi_{ctx.a}", f"ndvi_{ctx.b}",
            "declining_21_22_pct", "recovering_22_23_pct", "compactness", "robustness", "lat", "lon"]
    cols = [c for c in cols if c in df.columns]
    compat.dataframe(
        df[cols], hide_index=True, height=330, on_select="rerun", selection_mode="single-row", key=TABLE_KEY,
        column_config={
            "patch_id": st.column_config.NumberColumn("#", width="small"),
            "area_ha": st.column_config.NumberColumn("Area (ha)", format="%.1f"),
            "mean_change": st.column_config.NumberColumn("Mean ΔNDVI", format="%+.2f"),
            "max_decline": st.column_config.NumberColumn("Worst Δ", format="%+.2f"),
            f"ndvi_{ctx.a}": st.column_config.NumberColumn(f"NDVI {ctx.a}", format="%.2f"),
            f"ndvi_{ctx.b}": st.column_config.NumberColumn(f"NDVI {ctx.b}", format="%.2f"),
            "declining_21_22_pct": st.column_config.NumberColumn("Already ↓ 21→22 (%)", format="%.0f"),
            "recovering_22_23_pct": st.column_config.NumberColumn("Recovering 22→23 (%)", format="%.0f"),
            "compactness": st.column_config.NumberColumn("Compactness", format="%.2f"),
            "robustness": st.column_config.ProgressColumn("Robustness", min_value=0.0, max_value=1.0, format="%.0f%%"),
            "lat": st.column_config.NumberColumn(format="%.4f"), "lon": st.column_config.NumberColumn(format="%.4f"),
        })
    sel = ctx.sel_patch
    c1, c2 = st.columns([1.3, 1], gap="large")
    with c1:
        if sel is not None:
            years = [y for y in C.YEARS if f"ndvi_{y}" in sel.index]
            fig = go.Figure(go.Scatter(x=years, y=[sel[f"ndvi_{y}"] for y in years], mode="lines+markers", line=dict(color=T.ACCENT, width=3),
                                       marker=dict(size=9), hovertemplate="%{x}: NDVI %{y:.2f}<extra></extra>"))
            fig.update_layout(**T.plotly_layout(280, title=dict(text=f"Patch #{int(sel.patch_id)}: mean NDVI per composite", font=dict(size=14, color=T.TEXT)),
                                                yaxis=dict(title="NDVI", range=[0, 1], gridcolor=T.GRID), showlegend=False))
            compat.plotly_chart(fig)
        else:
            st.info("Select a patch to see its NDVI history.")
    with c2:
        st.markdown("**How to read this**")
        st.markdown("- *Robustness*: share of tested thresholds (0.10-0.30) at which the patch’s median change still qualifies.\n"
                    "- *Recovering 22→23*: a high value hints at a temporary dip (cloud shadow, haze, phenology) rather than a lasting change.\n"
                    "- Geometry describes **candidate** disturbances; it cannot identify the cause. Verify against high-resolution imagery, "
                    "PRODES/DETER or MapBiomas before reporting deforestation.")
        st.download_button("Download patches (GeoJSON)", json.dumps(ctx.patch_gj), "decline_patches.geojson", "application/geo+json")
        st.download_button("Download table (CSV)", df.drop(columns=["bbox"], errors="ignore").to_csv(index=False), "decline_patches.csv", "text/csv")

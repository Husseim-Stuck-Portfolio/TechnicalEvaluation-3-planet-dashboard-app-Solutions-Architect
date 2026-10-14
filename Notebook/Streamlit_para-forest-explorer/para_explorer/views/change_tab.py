"""Tab: NDVI change budget, histogram, trajectories and threshold sensitivity (ideas 1, 2, 10)."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from para_explorer import compat

from .. import config as C
from .. import services as S
from .. import texts as X
from .. import theme as T

CLASS_COLORS = {"Strong decrease": "#e66767", "Moderate decrease": "#9a4b4b", "Little change": "#5d6b7e",
                "Moderate increase": "#35629c", "Strong increase": "#3987e5"}


ORDER = ["Strong decrease", "Moderate decrease", "Little change", "Moderate increase", "Strong increase"]

INTERPRETATION = (
    "**How to read the change graphs.** Negative ΔNDVI means vegetation was lower in the later period; positive means higher; "
    "values near zero mean little detected change. *Moderate* and *strong* depend on the thresholds chosen in the sidebar. "
    "Percentages use valid pixels only. The NDVI change map identifies locations where vegetation conditions differed between the "
    "selected periods. Areas with negative change may indicate vegetation loss, but they may also result from seasonality, cloud "
    "contamination, fire, drought, flooding, harvest, or different acquisition dates. Results should therefore be interpreted as "
    "**areas for investigation rather than confirmed deforestation**.")


def _budget(ctx) -> None:
    b = ctx.budget[ctx.budget["class"] != "No data"].set_index("class").reindex(ORDER).reset_index()
    nod = ctx.budget[ctx.budget["class"] == "No data"].iloc[0]
    cols = [CLASS_COLORS[c] for c in b["class"]]
    c1, c2 = st.columns(2, gap="large")
    with c1:
        fig = go.Figure(go.Bar(
            y=b["class"], x=b["area_ha"], orientation="h", marker_color=cols,
            text=[f"{h:,.0f} ha · {int(px):,} px" for h, px in zip(b["area_ha"], b["pixels"])], textposition="outside", cliponaxis=False,
            textfont=dict(color=T.TEXT), hovertemplate="%{y}<br>%{x:,.1f} ha<extra></extra>"))
        fig.update_layout(**T.plotly_layout(310, title=dict(text=f"Area per class {ctx.a} → {ctx.b} (hectares)", font=dict(size=14, color=T.TEXT)),
                                            xaxis=dict(gridcolor=T.GRID, title="hectares", range=[0, b["area_ha"].max() * 1.95]),
                                            yaxis=dict(autorange="reversed", showgrid=False), showlegend=False))
        compat.plotly_chart(fig)
    with c2:
        fig = go.Figure(go.Bar(
            y=b["class"], x=b["pct_valid"], orientation="h", marker_color=cols,
            text=[f"{p:.2f} %" for p in b["pct_valid"]], textposition="outside", cliponaxis=False, textfont=dict(color=T.TEXT),
            hovertemplate="%{y}<br>%{x:.2f} % of valid pixels<extra></extra>"))
        fig.update_layout(**T.plotly_layout(310, title=dict(text="Share of valid pixels (%)", font=dict(size=14, color=T.TEXT)),
                                            xaxis=dict(gridcolor=T.GRID, title="% of valid pixels", range=[0, max(b["pct_valid"].max() * 1.25, 1)]),
                                            yaxis=dict(autorange="reversed", showgrid=False, showticklabels=False), showlegend=False))
        compat.plotly_chart(fig)
    st.caption(f"Moderate: |ΔNDVI| ≥ {ctx.t_moderate:.2f} · strong: ≥ {ctx.t_strong:.2f}. Denominator = valid pixels in both years; "
               f"unobserved pixels ({nod.area_ha:,.1f} ha) are excluded, not counted as “no change”. Classes always appear in the same order, "
               "and the two panels show absolute area and percentage so small classes are not exaggerated.")


def _hist(ctx) -> None:
    counts, edges = S.histogram(ctx.folder, ctx.mtime, ctx.a, ctx.b)
    x = (edges[1:] + edges[:-1]) / 2
    fig = go.Figure(go.Bar(x=x, y=counts, marker_color="#8aa0bd", hovertemplate="ΔNDVI %{x:.2f}: %{y:,} px<extra></extra>"))
    for v, name in [(-ctx.t_strong, "strong"), (-ctx.t_moderate, "moderate"), (ctx.t_moderate, "moderate"), (ctx.t_strong, "strong")]:
        fig.add_vline(x=v, line=dict(color=T.ACCENT if name == "moderate" else T.DANGER, width=1.2, dash="dot"))
    fig.update_layout(**T.plotly_layout(310, title=dict(text=f"ΔNDVI distribution {ctx.a} → {ctx.b}", font=dict(size=14, color=T.TEXT)),
                                        yaxis=dict(type="log", gridcolor=T.GRID, title="pixels (log)"), xaxis=dict(title="ΔNDVI", gridcolor=T.GRID),
                                        showlegend=False, bargap=0))
    compat.plotly_chart(fig)


def _maps(ctx) -> None:
    c1, c2 = st.columns(2, gap="large")
    with c1:
        d = S.small_change(ctx.folder, ctx.mtime, ctx.a, ctx.b)
        fig = go.Figure(go.Heatmap(z=d, zmin=-0.5, zmax=0.5, zmid=0, colorscale=[[k / 4, c] for k, c in enumerate(T.CHANGE_RAMP)],
                                   colorbar=dict(title="ΔNDVI", thickness=10), hovertemplate="ΔNDVI %{z:+.2f}<extra></extra>"))
        fig.update_xaxes(visible=False); fig.update_yaxes(visible=False, autorange="reversed", scaleanchor="x")
        fig.update_layout(**T.plotly_layout(470, title=dict(text=f"NDVI change {ctx.a} → {ctx.b} (red = decrease)", font=dict(size=14, color=T.TEXT))))
        compat.plotly_chart(fig)
    with c2:
        if not all(y in ctx.ndvis for y in C.YEARS):
            st.info("Trajectory classes need the 2021, 2022 and 2023 composites.")
            return
        tab, tmap = S.trajectory(ctx.folder, ctx.mtime, ctx.t_moderate)
        stepped = [[x, T.TRAJECTORY[k][1]] for k in range(6) for x in (k / 6, (k + 1) / 6)]
        fig = go.Figure(go.Heatmap(z=tmap, zmin=0, zmax=5, colorscale=stepped, showscale=False,
                                   customdata=np.vectorize(lambda k: T.TRAJECTORY[int(k)][0])(tmap),
                                   hovertemplate="%{customdata}<extra></extra>"))
        fig.update_xaxes(visible=False); fig.update_yaxes(visible=False, autorange="reversed", scaleanchor="x")
        fig.update_layout(**T.plotly_layout(470, title=dict(text="Vegetation trajectory 2021 → 2022 → 2023", font=dict(size=14, color=T.TEXT))))
        compat.plotly_chart(fig)
    t = tab[tab["class"] != "No data"].copy()
    compat.dataframe(t[["class", "area_ha", "pct_valid"]].rename(columns={"area_ha": "area (ha)", "pct_valid": "% of valid"}),
                 hide_index=True,
                 column_config={"area (ha)": st.column_config.NumberColumn(format="%.0f"),
                                "% of valid": st.column_config.NumberColumn(format="%.2f")})
    st.caption(f"Classes use a minimum |ΔNDVI| of {ctx.t_moderate:.2f} per interval. With only three annual points this is a "
               "trajectory *classification*, not a statistically established trend.")


def _sensitivity(ctx) -> None:
    sens = S.sensitivity(ctx.folder, ctx.mtime, ctx.a, ctx.b)
    fig = go.Figure()
    for (mh, g), col in zip(sens.groupby("min_patch_ha"), ["#3987e5", "#d95926", "#199e70", "#c3c2b7"]):
        fig.add_scatter(x=g["threshold"], y=g["area_ha"], mode="lines+markers", name=f"min patch {mh} ha", line=dict(color=col, width=2),
                        marker=dict(size=7), hovertemplate=f"min {mh} ha · threshold %{{x:.2f}}: %{{y:,.0f}} ha<extra></extra>")
    fig.add_vline(x=ctx.t_strong, line=dict(color=T.ACCENT, dash="dot"), annotation_text="current", annotation_font_color=T.ACCENT)
    fig.update_layout(**T.plotly_layout(340, title=dict(text=f"Sensitivity: reported decline area vs. analyst settings ({ctx.a} → {ctx.b})", font=dict(size=14, color=T.TEXT)),
                                        yaxis=dict(type="log", gridcolor=T.GRID, title="declined area (ha)"), xaxis=dict(title="NDVI-decrease threshold", gridcolor=T.GRID)))
    compat.plotly_chart(fig)
    st.caption("The headline number moves a lot with the threshold, so it is reported with its settings. A patch’s "
               "*robustness* score (Decline patches tab) is the share of a wider test range (0.10-0.30) at which it stays flagged - "
               "robustness to our choices, not a probability of deforestation.")


def render(ctx) -> None:
    st.info(INTERPRETATION)
    st.warning("**Seasonal limitation.** " + X.SEASONAL_LIMITATION)
    _budget(ctx)
    _hist(ctx)
    _maps(ctx)
    _sensitivity(ctx)

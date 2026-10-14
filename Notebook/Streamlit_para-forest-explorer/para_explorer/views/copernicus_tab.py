"""Tab: Sentinel-2 L2A availability from the Copernicus Data Space Ecosystem (context for the Planet data)."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from para_explorer import compat

from .. import cdse
from .. import config as C
from .. import services as S
from .. import theme as T


def render(ctx) -> None:
    st.markdown("#### Copernicus Data Space Ecosystem · Sentinel-2 L2A context")
    st.caption("The area of interest comes from the CDSE browser. Here the public CDSE STAC API (no credentials) tells us how "
               "many free 10 m Sentinel-2 scenes cover the same place - a cross-check of how often the forest can be observed "
               "when clouds are limited, and an independent sensor for validating Planet-derived change.")
    c1, c2, c3 = st.columns([1, 1, 1])
    start = c1.date_input("From", value=ctx.p_start_date, key="cdse_from")
    end = c2.date_input("To", value=ctx.p_end_date, key="cdse_to")
    cloud = c3.slider("Max cloud cover (%)", 0, 100, int(ctx.cloud[1]), key="cdse_cloud")
    if not st.button("Query Copernicus STAC", type="primary"):
        st.info("Press the button to search (read-only metadata request).")
        return
    try:
        df, trunc = S.cdse_items(str(start), str(end), float(cloud))
    except cdse.CdseError as e:
        st.error(str(e))
        return
    if df.empty:
        st.warning("No Sentinel-2 scenes found for these filters.")
        return
    m = cdse.monthly(df)
    k = st.columns(3)
    k[0].markdown(T.kpi("Sentinel-2 L2A scenes", f"{len(df):,}", f"cloud ≤ {cloud} %"), unsafe_allow_html=True)
    k[1].markdown(T.kpi("Median cloud cover", f"{df['cloud'].median():.0f} %", "eo:cloud_cover"), unsafe_allow_html=True)
    k[2].markdown(T.kpi("Observed months", f"{(m['count'] > 0).sum()}", f"of {len(m)} in range"), unsafe_allow_html=True)
    fig = go.Figure(go.Bar(x=m["start"].dt.strftime("%Y-%m-01"), y=m["count"], marker_color="#199e70",
                           hovertemplate="%{x|%b %Y}: %{y} scenes<extra></extra>"))
    fig.update_layout(**T.plotly_layout(320, title=dict(text="Sentinel-2 L2A scenes per month (AOI)", font=dict(size=14, color=T.TEXT)),
                                        showlegend=False, yaxis=dict(gridcolor=T.GRID, title="scenes")))
    compat.plotly_chart(fig)
    if trunc:
        st.caption("Result list was capped; counts are a lower bound.")

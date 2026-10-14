"""Header, KPI strip and the globe + side panel (the 'map-first' part of the UI)."""
from __future__ import annotations

import numpy as np
import streamlit as st

from para_explorer import compat

from .. import config as C
from .. import globe
from .. import services as S
from .. import theme as T


def header(ctx) -> None:
    st.markdown(
        f'<div class="pe-topbar"><div class="pe-logo"></div><div>'
        f'<div class="pe-title">Pará Forest Change Explorer</div>'
        f'<div class="pe-sub">{C.AOI_NAME} · {C.AOI_AREA_KM2:.0f} km² · annual PlanetScope composites 2021-2023 · '
        f'area of interest from the Copernicus Data Space Ecosystem</div></div>'
        f'<div class="pe-pill">data: <b>Planet sandbox</b></div></div>', unsafe_allow_html=True)


def kpis(ctx) -> None:
    n = ctx.counts.get(ctx.period, {}) if ctx.counts else {}
    imgs = f"{n['items']:,}" if n.get("items") is not None else "n/a"
    bits = []
    if n.get("usable") is not None:
        bits.append(f"{n['usable']:,} with ≥50 % valid pixels")
    if n.get("available") is not None:
        bits.append(f"{n['available']:,} in catalog")
    dates = " · ".join(bits) or (f"{n['dates']:,} acquisition dates" if n.get("dates") else "enter counts in the Composites tab")
    ps = ctx.period_stats.set_index("period").loc[ctx.period]
    strong = ctx.budget.set_index("class").loc["Strong decrease"]
    kept = ctx.patch_df
    cols = st.columns(5)
    items = [
        (f"Images in “{ctx.period}”", imgs, dates),
        ("Mean NDVI", f"{ps.mean_ndvi:.3f}", f"median {ps.median_ndvi:.3f} · p5 {ps.p05:.2f}"),
        ("Valid area", f"{ps.valid_km2:,.0f} km²", f"of {C.AOI_AREA_KM2:.0f} km² AOI"),
        ("Strong NDVI decrease", f"{strong.area_ha:,.0f} ha", f"{ctx.a}→{ctx.b} · {strong.pct_valid:.2f} % of valid area"),
        ("Candidate patches", f"{len(kept):,}", (f"largest {kept.area_ha.max():,.0f} ha" if len(kept) else "none at these settings")),
    ]
    for c, (l, v, s) in zip(cols, items):
        c.markdown(T.kpi(l, v, s), unsafe_allow_html=True)


def _legend(ctx, layer: str, show_patches: bool, scenes: bool) -> str:
    sw = lambda col, txt: f'<div><i style="background:{col}"></i>{txt}</div>'  # noqa: E731
    out = []
    if layer == "NDVI":
        out.append(f'<div style="height:8px;border-radius:4px;background:linear-gradient(90deg,{",".join(T.NDVI_RAMP)})"></div>'
                   f'<div style="display:flex;justify-content:space-between;color:#9fb0c6"><span>{T.NDVI_RANGE[0]}</span><span>NDVI</span><span>{T.NDVI_RANGE[1]}</span></div>')
    elif layer == "NDVI change":
        out.append(f'<div style="height:8px;border-radius:4px;background:linear-gradient(90deg,{",".join(T.CHANGE_RAMP)})"></div>'
                   f'<div style="display:flex;justify-content:space-between;color:#9fb0c6"><span>−0.5</span><span>ΔNDVI {ctx.a}→{ctx.b}</span><span>+0.5</span></div>')
    elif layer == "Trajectory":
        out += [sw(T.TRAJECTORY[k][1], T.TRAJECTORY[k][0]) for k in (3, 4, 2, 5)]
    if show_patches:
        out.append(sw("#E66767", "Decline patch (click for stats)"))
    if scenes:
        out.append(sw("#3987e5", "Planet scene footprint (bolder = clearer)"))
    return "".join(out)


LAYER_KIND = {"True colour": "rgb", "NDVI": "ndvi", "NDVI change": "change", "Trajectory": "trajectory"}


def globe_and_panel(ctx, pl) -> None:
    left, right = st.columns([3.1, 1.15], gap="medium")
    with left:
        overlay, kind = None, LAYER_KIND.get(ctx.layer)
        if kind:
            url = S.overlay_url(ctx.folder, ctx.mtime, kind, ctx.period, ctx.a, ctx.b, ctx.t_moderate)
            overlay = {"url": url, "coordinates": globe.overlay_coords(ctx.bounds)}
        title = {"True colour": f"True colour · {ctx.period}", "NDVI": f"NDVI · {ctx.period}",
                 "NDVI change": f"NDVI change {ctx.a} → {ctx.b}", "Trajectory": "Vegetation trajectory 2021→2022→2023"}.get(ctx.layer, "Area of interest")
        n = ctx.counts.get(ctx.period, {}).get("items") if ctx.counts else None
        sub = f"{n} images in composite" if (n is not None and ctx.layer in ("True colour", "NDVI")) else C.AOI_NAME
        sel = ctx.sel_patch
        focus = {"center": [float(sel.lon), float(sel.lat)], "zoom": 13.4} if sel is not None else None
        intro = ctx.intro
        html = globe.build_html(
            C.AOI_FEATURE, basemap=ctx.basemap, overlay=overlay, info=f"<b>{title}</b><div class=m>{sub}</div>",
            legend=_legend(ctx, ctx.layer, ctx.show_patches and len(ctx.patch_df) > 0, pl.fc is not None),
            patches=ctx.patch_gj if ctx.show_patches else None, scenes=pl.fc,
            highlight_patch=int(sel.patch_id) if sel is not None else None,
            highlight_scene=pl.highlight, focus=focus, autorotate=intro, restore=not intro, opacity=ctx.opacity)
        compat.html_frame(html, height=640)
    with right:
        composite_panel(ctx)
        patch_card(ctx)


def composite_panel(ctx) -> None:
    ps = ctx.period_stats.set_index("period")
    rows = ""
    for p in C.COMPOSITES:
        if p not in ps.index:
            continue
        n = ctx.counts.get(p, {}).get("items") if ctx.counts else None
        sel = " style='color:#19D3C5;font-weight:650'" if p == ctx.period else ""
        rows += (f"<tr{sel}><td>{p}</td><td style='text-align:right'>{'n/a' if n is None else f'{n:,}'}</td>"
                 f"<td style='text-align:right'>{ps.loc[p, 'mean_ndvi']:.3f}</td></tr>")
    st.markdown(
        f'<div class="pe-card"><h4>Images used per composite</h4>'
        f'<table style="width:100%;font-size:.82rem;color:{T.TEXT_2}"><tr style="color:{T.MUTED}"><td>composite</td>'
        f'<td style="text-align:right">images</td><td style="text-align:right">mean NDVI</td></tr>{rows}</table>'
        f'<div class="pe-note" style="margin-top:6px">source: {ctx.counts_source}</div></div>', unsafe_allow_html=True)


def patch_card(ctx) -> None:
    sel = ctx.sel_patch
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    if sel is None:
        st.markdown('<div class="pe-card"><h4>Patch inspector</h4><div class="pe-note">Select a row in the '
                    '“Decline patches” tab (or click a red patch on the map) to see its NDVI history here and '
                    'fly the globe to it.</div></div>', unsafe_allow_html=True)
        return
    rec = sel.get("recovering_22_23_pct", np.nan)
    st.markdown(
        f'<div class="pe-card"><h4>Patch #{int(sel.patch_id)}</h4>'
        f'<div style="font-size:1.4rem;font-weight:650">{sel.area_ha:,.1f} ha</div>'
        f'<div class="pe-note">ΔNDVI mean {sel.mean_change:+.2f} · worst {sel.max_decline:+.2f}<br>'
        f'robustness {sel.robustness:.0%} of thresholds · compactness {sel.compactness:.2f}<br>'
        f'{rec:.0f} % of pixels recovering in 2022→23<br>{sel.lat:.4f}, {sel.lon:.4f}</div></div>', unsafe_allow_html=True)

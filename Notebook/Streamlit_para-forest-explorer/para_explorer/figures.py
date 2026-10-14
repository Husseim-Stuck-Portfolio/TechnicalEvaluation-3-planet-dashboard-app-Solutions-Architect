"""Static (matplotlib) figures used for the square composite images, the downloads and the PDF report.

Every function returns a ``matplotlib.figure.Figure`` built without pyplot (no global state, safe in Streamlit);
``to_png`` turns it into bytes. ``style`` is "dark" (matches the app) or "light" (print / PDF).
"""
from __future__ import annotations

import io

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
from matplotlib.figure import Figure

from . import theme as T

SQUARE = (6.0, 6.0)          # inches - every composite image uses exactly this canvas
NDVI_CMAP = LinearSegmentedColormap.from_list("ndvi", T.NDVI_RAMP)
CHANGE_CMAP = LinearSegmentedColormap.from_list("change", T.CHANGE_RAMP)
CLASS_COLORS = {"Strong decrease": "#e66767", "Moderate decrease": "#c98a8a", "Little change": "#8a96a8",
                "Moderate increase": "#6fa3de", "Strong increase": "#3987e5"}

_STYLES = {
    "dark": dict(bg=T.BG, fg=T.TEXT, sub=T.TEXT_2, grid=T.GRID),
    "light": dict(bg="#ffffff", fg="#14202e", sub="#4a5a6e", grid="#dfe5ec"),
}


def _st(style: str) -> dict:
    return _STYLES.get(style, _STYLES["light"])


def to_png(fig: Figure, dpi: int = 130) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor=fig.get_facecolor())
    return buf.getvalue()


def _fig(size=SQUARE, style="light") -> Figure:
    return Figure(figsize=size, facecolor=_st(style)["bg"])


def _square_axes(fig: Figure, style: str, bottom: float = 0.12):
    top = 0.88                                   # leaves room for title + subtitle
    ax = fig.add_axes([0.03, bottom, 0.94, top - bottom])
    ax.set_facecolor(_st(style)["bg"])
    ax.set_aspect("equal")          # never stretch
    ax.axis("off")
    return ax


def _caption(fig: Figure, title: str, subtitle: str, style: str) -> None:
    c = _st(style)
    fig.text(0.04, 0.965, title, ha="left", va="top", color=c["fg"], fontsize=13, fontweight="bold")
    if subtitle:
        fig.text(0.04, 0.925, subtitle, ha="left", va="top", color=c["sub"], fontsize=9)


def _colorbar(fig: Figure, mappable, label: str, style: str, ticks=None) -> None:
    c = _st(style)
    cax = fig.add_axes([0.2, 0.075, 0.6, 0.02])
    cb = fig.colorbar(mappable, cax=cax, orientation="horizontal", ticks=ticks)
    cb.outline.set_edgecolor(c["grid"])
    cb.ax.tick_params(colors=c["sub"], labelsize=8)
    cb.set_label(label, color=c["sub"], fontsize=8)


def composite_figure(kind: str, data: np.ndarray, title: str, subtitle: str = "", style: str = "dark") -> Figure:
    """Square canvas, equal aspect, identical size for every year. kind: 'rgb' | 'ndvi' | 'change'."""
    fig = _fig(style=style)
    ax = _square_axes(fig, style, bottom=0.03 if kind == "rgb" else 0.14)
    if kind == "rgb":
        ax.imshow(data[..., :3], interpolation="nearest")
    elif kind == "ndvi":
        im = ax.imshow(data, cmap=NDVI_CMAP, vmin=T.NDVI_RANGE[0], vmax=T.NDVI_RANGE[1], interpolation="nearest")
        _colorbar(fig, im, "NDVI", style)
    elif kind == "change":
        im = ax.imshow(data, cmap=CHANGE_CMAP, norm=TwoSlopeNorm(0, -0.5, 0.5), interpolation="nearest")
        _colorbar(fig, im, "ΔNDVI (negative = lower vegetation in the later period)", style, ticks=[-0.5, -0.25, 0, 0.25, 0.5])
    else:
        raise ValueError(kind)
    _caption(fig, title, subtitle, style)
    return fig


def budget_figure(budget, a: str, b: str, t_mod: float, t_strong: float, style: str = "light") -> Figure:
    """Change budget as absolute area and as % of valid pixels, in a fixed class order."""
    c = _st(style)
    df = budget[budget["class"] != "No data"]
    fig = Figure(figsize=(10, 3.6), facecolor=c["bg"])
    names = list(df["class"])
    cols = [CLASS_COLORS[n] for n in names]
    for i, (col, lab, fmt) in enumerate([("area_ha", "Area (hectares)", "{:,.0f} ha"), ("pct_valid", "% of valid pixels", "{:.2f} %")]):
        ax = fig.add_subplot(1, 2, i + 1, facecolor=c["bg"])
        vals = df[col].to_numpy(float)
        bars = ax.barh(names, vals, color=cols)
        ax.invert_yaxis()
        ax.set_xlim(0, max(vals.max() * (2.1 if i == 0 else 1.5), 1e-9))
        for bar, v, px in zip(bars, vals, df["pixels"]):
            extra = f"\n({int(px):,} px)" if i == 0 else ""
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, " " + fmt.format(v) + extra, va="center", ha="left",
                    color=c["fg"], fontsize=7.5, linespacing=0.95)
        ax.set_title(lab, color=c["fg"], fontsize=10, loc="left")
        ax.tick_params(colors=c["sub"], labelsize=8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(c["grid"])
        ax.grid(axis="x", color=c["grid"], lw=0.6)
        ax.set_axisbelow(True)
        if i == 1:
            ax.set_yticklabels([])
    fig.suptitle(f"NDVI change budget {a} → {b}  (moderate ≥ {t_mod:.2f}, strong ≥ {t_strong:.2f})", color=c["fg"], fontsize=11,
                 x=0.01, ha="left")
    fig.text(0.01, 0.01, "Percentages use valid pixels only as denominator; unobserved pixels are excluded, not counted as ‘no change’.",
             color=c["sub"], fontsize=7.5)
    fig.subplots_adjust(left=0.13, right=0.97, top=0.82, bottom=0.14, wspace=0.12)
    return fig


def ndvi_distribution_figure(ndvis: dict, style: str = "light", max_px: int = 600) -> Figure:
    """Per-year NDVI histograms (same bins) with mean lines - the 'yearly NDVI graph'."""
    c = _st(style)
    fig = Figure(figsize=(8, 3.6), facecolor=c["bg"])
    ax = fig.add_subplot(111, facecolor=c["bg"])
    bins = np.linspace(0, 1, 101)
    for name, arr in ndvis.items():
        step = max(1, int(np.ceil(max(arr.shape) / max_px)))
        v = arr[::step, ::step]
        v = v[np.isfinite(v)]
        if v.size == 0:
            continue
        col = T.PERIOD_COLORS.get(name, "#888888")
        h, e = np.histogram(v, bins=bins, density=True)
        ax.plot((e[1:] + e[:-1]) / 2, h, color=col, lw=1.8, label=f"{name} (mean {v.mean():.3f})")
        ax.axvline(v.mean(), color=col, lw=0.9, ls=":")
    ax.set_xlabel("NDVI", color=c["sub"], fontsize=9)
    ax.set_ylabel("share of pixels (density)", color=c["sub"], fontsize=9)
    ax.set_title("NDVI distribution per composite (dotted = mean)", color=c["fg"], fontsize=10, loc="left")
    ax.tick_params(colors=c["sub"], labelsize=8)
    ax.grid(color=c["grid"], lw=0.6)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(c["grid"])
    leg = ax.legend(frameon=False, fontsize=8, loc="upper left")
    for t in leg.get_texts():
        t.set_color(c["fg"])
    fig.subplots_adjust(left=0.09, right=0.98, top=0.88, bottom=0.16)
    return fig


def change_histogram_figure(counts, edges, a: str, b: str, t_mod: float, t_strong: float, style: str = "light") -> Figure:
    c = _st(style)
    fig = Figure(figsize=(8, 3.4), facecolor=c["bg"])
    ax = fig.add_subplot(111, facecolor=c["bg"])
    x = (edges[1:] + edges[:-1]) / 2
    ax.bar(x, counts, width=np.diff(edges), color="#8aa0bd")
    ax.set_yscale("log")
    for v, col in [(-t_strong, "#e66767"), (-t_mod, "#c98a8a"), (t_mod, "#6fa3de"), (t_strong, "#3987e5")]:
        ax.axvline(v, color=col, lw=1.2, ls=":")
    ax.set_xlabel("ΔNDVI (later − earlier)", color=c["sub"], fontsize=9)
    ax.set_ylabel("pixels (log)", color=c["sub"], fontsize=9)
    ax.set_title(f"Distribution of NDVI change {a} → {b}; dotted lines = thresholds", color=c["fg"], fontsize=10, loc="left")
    ax.tick_params(colors=c["sub"], labelsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(c["grid"])
    fig.subplots_adjust(left=0.09, right=0.98, top=0.88, bottom=0.16)
    return fig


def aoi_map_figure(rgb: np.ndarray, bounds: tuple, aoi_ring: list, patches: list | None = None, style: str = "light") -> Figure:
    """True-colour composite in lon/lat axes with the AOI outline (and decline patches if given)."""
    c = _st(style)
    fig = Figure(figsize=(5.6, 5.6), facecolor=c["bg"])
    ax = fig.add_subplot(111, facecolor=c["bg"])
    w, s, e, n = bounds
    ax.imshow(rgb[..., :3], extent=(w, e, s, n), interpolation="nearest")
    xs, ys = zip(*aoi_ring)
    ax.plot(xs, ys, color="#19D3C5", lw=2)
    for ring in patches or []:
        px, py = zip(*ring)
        ax.fill(px, py, facecolor="#e66767", edgecolor="#e66767", alpha=0.55, lw=0.5)
    ax.set_aspect(1 / np.cos(np.radians((s + n) / 2)))
    ax.set_xlabel("longitude", color=c["sub"], fontsize=8)
    ax.set_ylabel("latitude", color=c["sub"], fontsize=8)
    ax.tick_params(colors=c["sub"], labelsize=7)
    for sp in ax.spines.values():
        sp.set_color(c["grid"])
    ax.set_title("Area of interest (teal outline), Pará, Brazil", color=c["fg"], fontsize=10, loc="left")
    fig.subplots_adjust(left=0.14, right=0.97, top=0.92, bottom=0.1)
    return fig


def comparison_figure(planet_rgb, cop_rgb, planet_ndvi, cop_ndvi, titles: tuple, style: str = "light") -> Figure:
    """2x2: true colour and NDVI for Planet (left) and Copernicus (right), all square and on the same grid."""
    c = _st(style)
    fig = Figure(figsize=(8.4, 8.8), facecolor=c["bg"])
    panels = [(planet_rgb, "rgb", titles[0] + " · true colour"), (cop_rgb, "rgb", titles[1] + " · true colour"),
              (planet_ndvi, "ndvi", titles[0] + " · NDVI"), (cop_ndvi, "ndvi", titles[1] + " · NDVI")]
    for i, (arr, kind, ttl) in enumerate(panels):
        ax = fig.add_subplot(2, 2, i + 1, facecolor=c["bg"])
        ax.set_aspect("equal")
        ax.axis("off")
        if arr is None:
            ax.text(0.5, 0.5, "not loaded", ha="center", va="center", color=c["sub"], transform=ax.transAxes)
        elif kind == "rgb":
            ax.imshow(arr[..., :3])
        else:
            im = ax.imshow(arr, cmap=NDVI_CMAP, vmin=T.NDVI_RANGE[0], vmax=T.NDVI_RANGE[1])
        ax.set_title(ttl, color=c["fg"], fontsize=10)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.04, wspace=0.04, hspace=0.12)
    return fig

"""PDF report (matplotlib PdfPages - no extra dependency). Pure function of a ``content`` dict, so it is easy to test.

The report never prints file-system paths.
"""
from __future__ import annotations

import io
import textwrap
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from PIL import Image

from . import config as C
from . import texts as X

A4 = (8.27, 11.69)
INK, SUB, ACCENT, RULE = "#14202e", "#4a5a6e", "#0e8f86", "#d5dde6"


def _page(title: str | None = None, number: int | None = None) -> Figure:
    fig = Figure(figsize=A4, facecolor="white")
    if title:
        fig.text(0.07, 0.955, title, fontsize=16, fontweight="bold", color=INK, va="top")
        fig.add_artist(__import__("matplotlib.lines", fromlist=["Line2D"]).Line2D([0.07, 0.93], [0.93, 0.93], color=ACCENT, lw=1.5))
    if number:
        fig.text(0.93, 0.025, f"{number}", fontsize=8, color=SUB, ha="right")
    fig.text(0.07, 0.025, f"Pará Forest Change Explorer · v{C.APP_VERSION}", fontsize=7.5, color=SUB)
    return fig


def _text(fig: Figure, x: float, y: float, text: str, width: int = 95, size: float = 9, color: str = INK, bold: bool = False,
          gap: float = 0.0165) -> float:
    """Wrapped paragraph; returns the y below it."""
    for para in text.split("\n"):
        lines = textwrap.wrap(para, width) or [""]
        for ln in lines:
            fig.text(x, y, ln, fontsize=size, color=color, va="top", fontweight="bold" if bold else "normal")
            y -= gap * size / 9
        y -= gap * 0.35
    return y


def _bullets(fig: Figure, x: float, y: float, items: list[str], width: int = 92, size: float = 8.6) -> float:
    for it in items:
        lines = textwrap.wrap(it, width)
        for i, ln in enumerate(lines):
            fig.text(x, y, ("•  " if i == 0 else "    ") + ln, fontsize=size, color=INK, va="top")
            y -= 0.0155
        y -= 0.004
    return y


def _image(fig: Figure, png: bytes | None, rect: tuple, caption: str = "") -> None:
    ax = fig.add_axes(rect)
    ax.axis("off")
    if png:
        ax.imshow(np.array(Image.open(io.BytesIO(png)).convert("RGB")))
        ax.set_aspect("equal")
    else:
        ax.text(0.5, 0.5, "not available", ha="center", va="center", color=SUB, transform=ax.transAxes)
    if caption:
        ax.set_title(caption, fontsize=8, color=SUB, loc="left")


def _table(fig: Figure, df: pd.DataFrame, rect: tuple, font: float = 7.5, col_widths=None) -> None:
    ax = fig.add_axes(rect)
    ax.axis("off")
    t = ax.table(cellText=df.astype(str).values, colLabels=list(df.columns), loc="upper left", cellLoc="left",
                 colWidths=col_widths)
    t.auto_set_font_size(False)
    t.set_fontsize(font)
    t.scale(1, 1.35)
    for (r, _), cell in t.get_celld().items():
        cell.set_edgecolor(RULE)
        if r == 0:
            cell.set_facecolor("#eaf4f3")
            cell.set_text_props(fontweight="bold", color=INK)
        else:
            cell.set_text_props(color=INK)


def build(c: dict) -> bytes:
    """``c`` keys: aoi_png, composites{period:{'rgb','ndvi'}}, counts_df, dist_png, change_png, budget_png, hist_png,
    period_stats_df, budget_df, thresholds{moderate,strong,from,to,min_ha}, patch_summary, comparison|None, generated (datetime|None)."""
    now = c.get("generated") or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    th = c["thresholds"]
    buf = io.BytesIO()
    with PdfPages(buf, metadata={"Title": "Pará Forest Change Explorer - report", "Author": "Pará Forest Change Explorer",
                                 "CreationDate": now}) as pdf:
        # 1 ------------------------------------------------------------------ title, area, sources
        f = _page(None, 1)
        f.text(0.07, 0.93, "Pará Forest Change Explorer", fontsize=24, fontweight="bold", color=INK, va="top")
        f.text(0.07, 0.895, "Vegetation change 2021-2023 from annual PlanetScope composites,\nwith a Copernicus Sentinel-2 cross-check",
               fontsize=10.5, color=SUB, va="top")
        f.text(0.07, 0.858, f"Generated {stamp} · application version {C.APP_VERSION}", fontsize=8.5, color=SUB, va="top")
        y = _text(f, 0.07, 0.825, "Purpose", size=11, bold=True)
        y = _text(f, 0.07, y, "A forest-monitoring analyst wants to identify areas in Pará that may have experienced vegetation loss between "
                  "2021 and 2023. The report compares satellite imagery, calculates NDVI change, highlights possible change patches and gives "
                  "statistics that help prioritise areas for further investigation. It supports decisions; it does not replace field "
                  "verification or official deforestation assessments.")
        y = _text(f, 0.07, y - 0.01, "Study area", size=11, bold=True)
        y = _text(f, 0.07, y, X.STUDY_AREA)
        _image(f, c.get("aoi_png"), (0.07, 0.30, 0.50, 0.31))
        f.text(0.60, 0.585, "Data sources", fontsize=10, fontweight="bold", color=INK, va="top")
        _bullets(f, 0.60, 0.56, X.DATA_SOURCES, width=38, size=7.8)
        f.text(0.07, 0.275, "Image dates and periods", fontsize=10, fontweight="bold", color=INK, va="top")
        if c.get("counts_df") is not None and len(c["counts_df"]):
            _table(f, c["counts_df"], (0.07, 0.08, 0.86, 0.18), font=7.5, col_widths=[0.14, 0.34, 0.18, 0.18, 0.16])
        pdf.savefig(f)

        # 2 ------------------------------------------------------------------ NDVI explained, settings
        f = _page("What NDVI is and how change is calculated", 2)
        y = _text(f, 0.07, 0.90, X.NDVI_EXPLANATION)
        f.text(0.07, y - 0.012, X.NDVI_FORMULA, fontsize=14, fontweight="bold", color=ACCENT, va="top")
        y -= 0.05
        y = _text(f, 0.07, y, "Steps", size=11, bold=True)
        y = _bullets(f, 0.07, y, [
            "NDVI is calculated for each annual composite (and for all years together).",
            f"Change = NDVI {th['to']} − NDVI {th['from']}, pixel by pixel; negative values mean less vegetation in the later period.",
            f"Pixels are classified with the thresholds below. Percentages use valid pixels only.",
            "Connected pixels with a strong decrease form patches, ranked by area; very small patches are ignored.",
        ])
        y = _text(f, 0.07, y - 0.01, "Settings used for this report", size=11, bold=True)
        settings = pd.DataFrame([
            ("Years compared", f"{th['from']} → {th['to']}"),
            ("Moderate change threshold (|ΔNDVI|)", f"{th['moderate']:.2f}"),
            ("Strong change threshold (|ΔNDVI|)", f"{th['strong']:.2f}"),
            ("Allowed threshold range", f"{C.NDVI_T_MIN:.2f} - {C.NDVI_T_MAX:.2f}"),
            ("Minimum patch size", f"{th['min_ha']:g} ha"),
        ], columns=["Setting", "Value"])
        _table(f, settings, (0.07, y - 0.17, 0.6, 0.15), font=8)
        y = y - 0.21
        y = _text(f, 0.07, y, "Classes", size=11, bold=True)
        _bullets(f, 0.07, y, [
            "Strong decrease: ΔNDVI ≤ −strong threshold · Moderate decrease: between −strong and −moderate.",
            "Little change: |ΔNDVI| below the moderate threshold.",
            "Moderate increase: between +moderate and +strong · Strong increase: ΔNDVI ≥ +strong threshold.",
        ])
        pdf.savefig(f)

        # 3 ------------------------------------------------------------------ yearly composites
        f = _page("Yearly composites (true colour)", 3)
        periods = [p for p in C.COMPOSITES if p in c["composites"]]
        for i, p in enumerate(periods[:4]):
            r, col = divmod(i, 2)
            _image(f, c["composites"][p].get("rgb"), (0.07 + col * 0.44, 0.50 - r * 0.42, 0.42, 0.40))
        _text(f, 0.07, 0.09, "Every composite is shown on the same square canvas without stretching. Colours use a common contrast stretch "
              "so years are comparable. The number of images behind each composite is listed on page 1.", size=8, color=SUB)
        pdf.savefig(f)

        # 4 ------------------------------------------------------------------ yearly NDVI
        f = _page("Yearly NDVI", 4)
        _image(f, c.get("dist_png"), (0.07, 0.58, 0.86, 0.32))
        for i, p in enumerate(periods[:4]):
            _image(f, c["composites"][p].get("ndvi"), (0.07 + i * 0.22, 0.34, 0.20, 0.20))
        if c.get("period_stats_df") is not None:
            _table(f, c["period_stats_df"], (0.07, 0.22, 0.86, 0.10), font=7.5)
        pdf.savefig(f)

        # 5 ------------------------------------------------------------------ change
        f = _page(f"NDVI change {th['from']} → {th['to']}", 5)
        _image(f, c.get("change_png"), (0.07, 0.50, 0.44, 0.40))
        _image(f, c.get("hist_png"), (0.52, 0.55, 0.42, 0.30))
        _image(f, c.get("budget_png"), (0.07, 0.29, 0.86, 0.21))
        if c.get("budget_df") is not None:
            _table(f, c["budget_df"], (0.07, 0.14, 0.86, 0.14), font=7.5)
        ps = c.get("patch_summary") or {}
        _text(f, 0.07, 0.09, f"Decline patches: {ps.get('kept', 0)} of {ps.get('total_candidates', 0)} connected candidates are at least "
              f"{th['min_ha']:g} ha ({ps.get('kept_ha', 0):,.0f} ha in total). " + ("No vegetation-change patches meet the selected minimum size."
              if not ps.get("kept") else ""), size=8.5)
        pdf.savefig(f)

        # 6 ------------------------------------------------------------------ comparison
        f = _page("Planet vs Copernicus: same area comparison", 6)
        cmp_ = c.get("comparison")
        if cmp_:
            _image(f, cmp_["png"], (0.07, 0.47, 0.86, 0.44))
            _table(f, cmp_["table"], (0.07, 0.17, 0.86, 0.28), font=6.8, col_widths=[0.16, 0.42, 0.42])
            _text(f, 0.07, 0.15, cmp_["text"], width=105, size=8)
            if not cmp_.get("loaded"):
                f.text(0.07, 0.10, "The Copernicus image had not been loaded when this report was created.", fontsize=8, color="#b25b00")
        else:
            _text(f, 0.07, 0.90, "The comparison was not prepared when this report was created. Open the section ‘Planet vs Copernicus’ in the app "
                  "and load the Copernicus image first.", size=10)
        _text(f, 0.07, 0.08, "The comparison is only valid when location, date/season, cloud conditions, resolution, projection, band definitions "
              "and preprocessing are sufficiently aligned.", size=7.5, color=SUB)
        pdf.savefig(f)

        # 7 ------------------------------------------------------------------ interpretation etc.
        f = _page("Interpretation, limitations and next steps", 7)
        y = _text(f, 0.07, 0.90, "Interpretation", size=11, bold=True)
        y = _text(f, 0.07, y, X.INTERPRETATION)
        y = _text(f, 0.07, y - 0.008, "Limitations", size=11, bold=True)
        y = _bullets(f, 0.07, y, X.LIMITATIONS)
        y = _text(f, 0.07, y - 0.008, "Future work", size=11, bold=True)
        y = _bullets(f, 0.07, y, X.FUTURE_SCOPE[:10] , size=8)
        pdf.savefig(f)
        f = _page("Future work (continued)", 8)
        y = _bullets(f, 0.07, 0.90, X.FUTURE_SCOPE[10:], size=8.6)
        y = _text(f, 0.07, y - 0.01, X.FUTURE_NOTE, size=8.6, color=SUB)
        _text(f, 0.07, y - 0.03, f"Report generated {stamp} · Pará Forest Change Explorer v{C.APP_VERSION}", size=8, color=SUB)
        pdf.savefig(f)
    return buf.getvalue()

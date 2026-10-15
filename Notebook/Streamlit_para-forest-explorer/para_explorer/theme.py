"""Visual identity: dark, map-first, teal accent (inspired by Planet Explorer / CDSE Browser).

Chart colours come from the validated dark categorical palette of the dataviz skill
(slots 1-3 validate all-pairs): blue / orange / aqua for 2021 / 2022 / 2023, neutral for the
all-years composite. Colour follows the *entity* (the year), never the rank.
"""
from __future__ import annotations

BG = "#070D17"
SURFACE = "#0F1826"
SURFACE_2 = "#152238"
BORDER = "rgba(255,255,255,0.09)"
TEXT = "#E8EEF6"
TEXT_2 = "#B4C0D0"
MUTED = "#7F8DA3"
GRID = "#1E2B40"
ACCENT = "#19D3C5"
DANGER = "#E66767"

PERIOD_COLORS = {"2021": "#3987e5", "2022": "#d95926", "2023": "#199e70", "All years": "#c3c2b7"}

#: single-hue (green) sequential ramp for NDVI, light -> dark
NDVI_RAMP = ["#e9f3dc", "#b6d99b", "#72b35a", "#2f8a3e", "#0b4d24"]
NDVI_RANGE = (0.3, 0.95)
#: diverging, red (decrease) <-> neutral <-> blue (increase)
CHANGE_RAMP = ["#e66767", "#9a4b4b", "#383835", "#35629c", "#3987e5"]

#: trajectory classes (id -> (label, colour)); id 0 = insufficient data
TRAJECTORY = {
    0: ("No data", "#2c2c2a"),
    1: ("Stable", "#5d6b7e"),
    2: ("Increase (persistent)", "#3987e5"),
    3: ("Decrease (persistent)", "#e66767"),
    4: ("Decrease then recovery", "#eda100"),
    5: ("Increase then decrease", "#9085e9"),
}


def plotly_layout(height: int = 320, **kw) -> dict:
    base = dict(
        height=height, margin=dict(l=8, r=8, t=36, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_2, family="system-ui, -apple-system, Segoe UI, sans-serif", size=12),
        title=dict(font=dict(size=14, color=TEXT), x=0.0, xanchor="left"),
        xaxis=dict(gridcolor=GRID, zerolinecolor="#383835", linecolor="#383835"),
        yaxis=dict(gridcolor=GRID, zerolinecolor="#383835", linecolor="#383835"),
        legend=dict(orientation="h", y=-0.2, yanchor="top", x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=SURFACE_2, font_color=TEXT, bordercolor=GRID),
    )
    base.update(kw)
    return base


CSS = f"""
<style>
  .stApp {{ background: radial-gradient(1200px 500px at 70% -10%, #10213a 0%, {BG} 60%); }}
  header[data-testid="stHeader"] {{ background: transparent; }}
  .block-container {{ padding-top: 1.0rem; padding-bottom: 3rem; max-width: 1500px; }}
  section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
  h1,h2,h3,h4 {{ letter-spacing: -0.01em; }}
  .pe-topbar {{ display:flex; align-items:center; gap:14px; padding: 6px 2px 14px 2px; }}
  .pe-logo {{ width:34px; height:34px; border-radius:50%;
             background: conic-gradient(from 210deg, {ACCENT}, #3987e5, #0b4d24, {ACCENT});
             box-shadow: 0 0 22px rgba(25,211,197,.45); }}
  .pe-title {{ font-size: 1.35rem; font-weight: 650; color:{TEXT}; line-height:1.1; }}
  .pe-sub {{ color:{MUTED}; font-size:.82rem; }}
  .pe-pill {{ margin-left:auto; border:1px solid {BORDER}; background:{SURFACE}; color:{TEXT_2};
             padding:4px 10px; border-radius:999px; font-size:.75rem; }}
  .pe-pill b {{ color:{ACCENT}; }}
  .pe-side-brand {{ display:flex; align-items:center; gap:12px; padding:2px 0 4px 0; }}
  .pe-side-brand .pe-logo {{ flex:none; }}
  .pe-side-title {{ font-size:1.55rem; font-weight:700; color:{TEXT}; line-height:1.12; letter-spacing:-0.02em; }}
  .pe-side-tag {{ color:{MUTED}; font-size:.8rem; margin:4px 0 6px 0; }}
  .pe-side-sec {{ font-size:1.2rem; font-weight:650; color:{TEXT}; margin:22px 0 2px 0; padding-top:14px;
                 border-top:1px solid {BORDER}; letter-spacing:-0.01em; }}
  .pe-side-desc {{ color:{TEXT_2}; font-size:.82rem; line-height:1.35; margin:0 0 10px 0; }}
  .pe-side-desc b {{ color:{ACCENT}; font-weight:600; }}
  .pe-kpi {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px; padding:12px 14px; height:100%; }}
  .pe-kpi .l {{ color:{MUTED}; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; }}
  .pe-kpi .v {{ color:{TEXT}; font-size:1.55rem; font-weight:650; margin-top:2px; }}
  .pe-kpi .s {{ color:{TEXT_2}; font-size:.74rem; }}
  .pe-card {{ background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px; padding:14px 16px; }}
  .pe-card h4 {{ margin:0 0 6px 0; font-size:.95rem; color:{TEXT}; }}
  .pe-note {{ color:{MUTED}; font-size:.78rem; }}
  .pe-banner {{ background:rgba(237,161,0,.10); border:1px solid rgba(237,161,0,.45); color:#f3d28a;
               border-radius:10px; padding:8px 12px; font-size:.82rem; margin-bottom:10px; }}
  .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom:1px solid {BORDER}; }}
  .stTabs [data-baseweb="tab"] {{ background: transparent; border-radius:8px 8px 0 0; padding:8px 14px; color:{TEXT_2}; }}
  .stTabs [aria-selected="true"] {{ color:{ACCENT}; }}
  div[data-testid="stImage"] img {{ border-radius:8px; border:1px solid {BORDER}; }}
  .pe-scene-cap {{ font-size:.72rem; color:{TEXT_2}; line-height:1.25; margin:2px 0 10px 0; }}
  .pe-scene-cap b {{ color:{TEXT}; }}
</style>
"""


def kpi(label: str, value: str, sub: str = "") -> str:
    return (f'<div class="pe-kpi"><div class="l">{label}</div><div class="v">{value}</div>'
            f'<div class="s">{sub}</div></div>')

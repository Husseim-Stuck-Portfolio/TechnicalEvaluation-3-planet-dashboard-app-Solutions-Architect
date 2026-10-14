"""Visualise the yearly composites (2021, 2022, 2023, All years) - companion of notebook 3.

Implements the analysis ideas of the ideas-PDF as static figures:
  1 change budget · 2 trajectories · 3 disturbance patches · 10 threshold sensitivity
and shows, in every title, how many images were used to build each composite.

Run as a script:
    python scripts/visualize_composites.py --composites /path/to/composites \
        [--downloads /path/to/planet_downloads] [--counts composite_counts.json] [--out figures]
or paste it cell by cell (``# %%``) into Jupyter - the cells are independent after the first two.

Fixes vs. the notebook cell that raised ``NameError: labels / large_patch_ids``: the patch figure
here recomputes labels itself, defines ``large_patch_ids`` and imports ``Rectangle``.
"""
# %% 0. Imports and configuration -----------------------------------------------------------
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from para_explorer import analysis as A  # noqa: E402
from para_explorer import composites as K  # noqa: E402
from para_explorer import config as C  # noqa: E402
from para_explorer import counts as N  # noqa: E402
from para_explorer import theme as T  # noqa: E402

DISPLAY_PX = 1200          # maps are block-averaged to this size for display only
T_MODERATE, T_STRONG = C.DEFAULT_T_MODERATE, C.DEFAULT_T_STRONG
MIN_PATCH_HA = C.DEFAULT_MIN_PATCH_HA


def style(plt):
    plt.rcParams.update({
        "figure.facecolor": T.BG, "axes.facecolor": T.SURFACE, "savefig.facecolor": T.BG,
        "axes.edgecolor": "#383835", "axes.labelcolor": T.TEXT_2, "text.color": T.TEXT,
        "xtick.color": T.MUTED, "ytick.color": T.MUTED, "axes.grid": True, "grid.color": T.GRID,
        "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    })


# %% 1. Load composites + image counts ------------------------------------------------------
def load_everything(composites_dir: Path, downloads: Path | None, counts_json: Path | None):
    paths = {n: K.raw_composite_path(composites_dir, n) for n in C.COMPOSITES}
    paths = {n: p for n, p in paths.items() if p.exists()}
    if not paths:
        sys.exit(f"No composite_*.tif found in {composites_dir}")
    ndvis = {n: K.read_ndvi(p) for n, p in paths.items()}
    ref = paths.get("All years", next(iter(paths.values())))
    lims = K.rgb_limits(K.read_bands(ref, [1, 2, 3], DISPLAY_PX))
    rgba = {n: K.to_rgba_uint8(K.read_bands(p, [1, 2, 3], DISPLAY_PX), lims) for n, p in paths.items()}
    info = K.raster_info(ref)
    area_row = K.pixel_area_ha_by_row(info["height"], info["bounds"], info["width"])
    rec = N.load(counts_json) if counts_json else None
    if rec is None and downloads:
        rec = N.from_download_folder(downloads)
    counts = (rec or {}).get("counts", {})
    return ndvis, rgba, info, area_row, counts, (rec or {}).get("source", "n/a")


def label(name: str, counts: dict) -> str:
    n = counts.get(name, {}).get("items")
    return f"{name} - {n} images" if n is not None else f"{name} - image count n/a"


# %% 2. Figures -----------------------------------------------------------------------------
def fig_true_color(plt, rgba, counts):
    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    for ax, name in zip(axes.ravel(), C.COMPOSITES):
        if name in rgba:
            ax.imshow(rgba[name])
        ax.set_title("True colour: " + label(name, counts)); ax.axis("off")
    fig.tight_layout()
    return fig


def fig_ndvi(plt, ndvis, counts):
    fig, axes = plt.subplots(2, 2, figsize=(12, 11))
    im = None
    for ax, name in zip(axes.ravel(), C.COMPOSITES):
        if name not in ndvis:
            continue
        st = K.ndvi_stats(ndvis[name])
        im = ax.imshow(K.downsample(ndvis[name], DISPLAY_PX), cmap=K.NDVI_CMAP, vmin=T.NDVI_RANGE[0], vmax=T.NDVI_RANGE[1])
        ax.set_title(f"NDVI {label(name, counts)}\nmean {st['mean']:.3f} · median {st['median']:.3f} · p5 {st['p05']:.3f}")
        ax.axis("off")
    fig.colorbar(im, ax=axes, fraction=0.025, label="NDVI")
    return fig


def fig_counts(plt, counts):
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1, 1.6]})
    names = [n for n in C.COMPOSITES if n in counts]
    vals = [counts[n]["items"] for n in names]
    bars = a.bar(names, vals, color=[T.PERIOD_COLORS[n] for n in names], width=0.6)
    a.bar_label(bars, padding=3, color=T.TEXT)
    a.set_title("Images used per composite"); a.set_ylabel("images (catalog items)"); a.grid(axis="x", visible=False)
    months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]
    x = np.arange(12)
    for i, y in enumerate(C.YEARS):
        m = counts.get(y, {}).get("monthly")
        if m:
            b.bar(x + (i - 1) * 0.27, [m[f"{k:02d}"] for k in range(1, 13)], width=0.27, color=T.PERIOD_COLORS[y], label=y)
    top = max([max(counts.get(y, {}).get("monthly", {}).values(), default=0) for y in C.YEARS] + [1])
    b.set_ylim(0, top * 1.3)
    b.set_xticks(x, months); b.set_title("Images per month"); b.legend(frameon=False, ncol=3, loc="upper left")
    b.grid(axis="x", visible=False)
    fig.tight_layout()
    return fig


def fig_change_maps(plt, ndvis):
    pairs = [("2021", "2022"), ("2022", "2023"), ("2021", "2023")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.6))
    for ax, (a, b) in zip(axes, pairs):
        d = K.downsample(ndvis[b] - ndvis[a], DISPLAY_PX)
        im = ax.imshow(d, cmap=K.CHANGE_CMAP, vmin=-0.5, vmax=0.5)
        ax.set_title(f"NDVI change {a} → {b}\n(red = decrease, blue = increase)"); ax.axis("off")
    fig.colorbar(im, ax=axes, fraction=0.02, label="ΔNDVI")
    return fig


def fig_budget(plt, ndvis, area_row):
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.4), sharey=True)
    colors = ["#e66767", "#9a4b4b", "#5d6b7e", "#35629c", "#3987e5"]
    for ax, (a, b) in zip(axes, [("2021", "2022"), ("2022", "2023"), ("2021", "2023")]):
        tab = A.change_budget(ndvis[a], ndvis[b], area_row, T_MODERATE, T_STRONG)
        tab = tab[tab["class"] != "No data"]
        bars = ax.barh(tab["class"], tab["area_ha"], color=colors)
        ax.bar_label(bars, labels=[f"{p:.1f} %" for p in tab["pct_valid"]], padding=3, color=T.TEXT_2)
        ax.set_title(f"Change budget {a} → {b}"); ax.set_xlabel("hectares"); ax.invert_yaxis(); ax.grid(axis="y", visible=False)
        ax.set_xscale("log")
    fig.suptitle(f"Moderate |ΔNDVI| ≥ {T_MODERATE}, strong ≥ {T_STRONG} · log scale · % of valid area", color=T.MUTED, fontsize=9)
    fig.tight_layout()
    return fig


def fig_trajectory(plt, ndvis, area_row):
    traj = A.trajectory(ndvis["2021"], ndvis["2022"], ndvis["2023"], T_MODERATE)
    tab = A.trajectory_table(traj, area_row)
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([T.TRAJECTORY[k][1] for k in sorted(T.TRAJECTORY)])
    fig, (a, b) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1.6, 1]})
    a.imshow(K.downsample(traj.astype("float32"), DISPLAY_PX).round(), cmap=cmap, vmin=0, vmax=5, interpolation="nearest")
    a.set_title("Vegetation trajectory 2021 → 2022 → 2023 (3 annual points = classification, not a trend)"); a.axis("off")
    t = tab[tab["class"] != "No data"]
    b.barh(t["class"], t["area_ha"], color=t["color"]); b.invert_yaxis(); b.set_xscale("log")
    b.set_title("Area per class (ha)"); b.grid(axis="y", visible=False)
    fig.tight_layout()
    return fig


def fig_patches(plt, ndvis, area_row, info, top_n=15):
    from matplotlib.patches import Rectangle
    df, _, summary = A.detect_patches(ndvis, "2021", "2023", T_STRONG, MIN_PATCH_HA, area_row, info["bounds"])
    mask = K.downsample(A.decline_mask(ndvis["2023"] - ndvis["2021"], T_STRONG).astype("float32"), DISPLAY_PX)
    f = info["width"] / mask.shape[1]
    w, s, e, n = info["bounds"]
    fig, ax = plt.subplots(figsize=(10, 9))
    from matplotlib.colors import ListedColormap
    ax.imshow(mask > 0.5, cmap=ListedColormap([T.SURFACE, "#e66767"]), interpolation="nearest")
    large_patch_ids = df.nlargest(top_n, "area_ha")["patch_id"].tolist() if len(df) else []
    for _, r in df[df["patch_id"].isin(large_patch_ids)].iterrows():
        x0, y0 = (r.bbox[0] - w) / (e - w) * mask.shape[1], (n - r.bbox[3]) / (n - s) * mask.shape[0]
        x1, y1 = (r.bbox[2] - w) / (e - w) * mask.shape[1], (n - r.bbox[1]) / (n - s) * mask.shape[0]
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor="#eda100", lw=1.3))
        ax.text(x0, y0, f"#{int(r.patch_id)} · {r.area_ha:.0f} ha", color="white", fontsize=7, backgroundcolor="#000000aa")
    ax.set_title(f"NDVI decline ≥ {T_STRONG} (2021 → 2023): {summary.get('kept', 0)} patches ≥ {MIN_PATCH_HA} ha "
                 f"of {summary['total_candidates']} candidates"); ax.axis("off")
    return fig, df


def fig_sensitivity(plt, ndvis, area_row):
    sens = A.sensitivity(ndvis["2021"], ndvis["2023"], area_row, np.arange(0.05, 0.41, 0.05).round(2), C.SENS_MIN_HA)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    for (mh, g), col in zip(sens.groupby("min_patch_ha"), ["#3987e5", "#d95926", "#199e70", "#c3c2b7"]):
        ax.plot(g["threshold"], g["area_ha"], marker="o", ms=4, lw=2, color=col, label=f"min patch {mh} ha")
    ax.set_yscale("log"); ax.set_xlabel("NDVI-decrease threshold"); ax.set_ylabel("declined area (ha)")
    ax.set_title("How much 'loss' we report depends on our settings (2021 → 2023)"); ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def fig_hist(plt, ndvis, counts):
    fig, (a, b) = plt.subplots(1, 2, figsize=(13, 4.2))
    for n, nd in ndvis.items():
        v = nd[np.isfinite(nd)][::7]
        h, e = np.histogram(v, bins=100, range=(0, 1), density=True)
        a.plot((e[1:] + e[:-1]) / 2, h, color=T.PERIOD_COLORS[n], lw=2, label=label(n, counts))
    a.set_title("NDVI distribution per composite"); a.set_xlabel("NDVI"); a.legend(frameon=False, fontsize=8)
    for pair, col in zip([("2021", "2022"), ("2022", "2023"), ("2021", "2023")], ["#3987e5", "#d95926", "#199e70"]):
        h, e = A.change_histogram(ndvis[pair[0]], ndvis[pair[1]])
        b.plot((e[1:] + e[:-1]) / 2, h, color=col, lw=2, label=f"{pair[0]}→{pair[1]}")
    b.set_yscale("log"); b.set_title("ΔNDVI distribution"); b.set_xlabel("ΔNDVI"); b.legend(frameon=False)
    fig.tight_layout()
    return fig


# %% 3. Run everything ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--composites", type=Path, default=C.RAW_COMPOSITES_DIR, help="folder with composite_*.tif")
    ap.add_argument("--downloads", type=Path, help="folder with the per-date GeoTIFFs (for image counts)")
    ap.add_argument("--counts", type=Path, help="composite_counts.json (overrides --downloads)")
    ap.add_argument("--out", type=Path, default=ROOT / "figures")
    ap.add_argument("--show", action="store_true", help="open the figures instead of only saving them")
    a = ap.parse_args()
    if not a.show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    style(plt)
    a.out.mkdir(parents=True, exist_ok=True)

    counts_json = a.counts or (a.composites.parent / "composite_counts.json")
    ndvis, rgba, info, area_row, counts, src = load_everything(a.composites, a.downloads, counts_json)
    print(f"image counts source: {src}")
    for k, v in counts.items():
        print(f"  {k:<10} {v['items']} images" + (f", {v['dates']} acquisition dates" if v.get("dates") else ""))

    figs = {"01_true_color": fig_true_color(plt, rgba, counts), "02_ndvi": fig_ndvi(plt, ndvis, counts),
            "04_change_maps": fig_change_maps(plt, ndvis), "05_change_budget": fig_budget(plt, ndvis, area_row),
            "06_trajectory": fig_trajectory(plt, ndvis, area_row), "08_sensitivity": fig_sensitivity(plt, ndvis, area_row),
            "09_histograms": fig_hist(plt, ndvis, counts)}
    if counts:
        figs["03_image_counts"] = fig_counts(plt, counts)
    fig7, patches = fig_patches(plt, ndvis, area_row, info)
    figs["07_patches"] = fig7
    for name, fig in sorted(figs.items()):
        fig.savefig(a.out / f"{name}.png", dpi=130)
    patches.drop(columns=["bbox"]).to_csv(a.out / "patches.csv", index=False)
    print(f"saved {len(figs)} figures + patches.csv to {a.out}")
    if a.show:
        plt.show()


if __name__ == "__main__":
    main()

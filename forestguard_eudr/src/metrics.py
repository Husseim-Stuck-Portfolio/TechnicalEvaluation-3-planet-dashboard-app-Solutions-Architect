"""Plot-level forest and carbon metrics.

Pure functions over pandas rows: given a measurement table and a pair of
years, derive every indicator the risk engine and the UI need.
"""
from __future__ import annotations

import pandas as pd

from .config import Thresholds, EUDR_CUTOFF_YEAR
from .validation import check_measurements_exist, check_year_order


def pct_change(baseline: float, latest: float) -> float:
    """Percentage change from baseline to latest. 0 if baseline is 0."""
    if baseline == 0:
        return 0.0
    return (latest - baseline) / baseline * 100.0


def summarize_plot(measurements: pd.DataFrame, plot_id: str,
                   baseline_year: int, comparison_year: int) -> dict:
    """Extract baseline/latest indicators for one plot and year pair."""
    check_year_order(baseline_year, comparison_year)
    check_measurements_exist(measurements, plot_id, baseline_year, comparison_year)

    sub = measurements[measurements["plot_id"] == plot_id].set_index("year").sort_index()
    base = sub.loc[baseline_year]
    comp = sub.loc[comparison_year]

    summary = {
        "plot_id": plot_id,
        "baseline_year": baseline_year,
        "comparison_year": comparison_year,
        "baseline_canopy_cover_percent": float(base["canopy_cover_percent"]),
        "latest_canopy_cover_percent": float(comp["canopy_cover_percent"]),
        "canopy_cover_change_percent": pct_change(
            float(base["canopy_cover_percent"]), float(comp["canopy_cover_percent"])),
        "baseline_canopy_height_m": float(base["canopy_height_m"]),
        "latest_canopy_height_m": float(comp["canopy_height_m"]),
        "canopy_height_change_m": float(comp["canopy_height_m"] - base["canopy_height_m"]),
        "baseline_carbon_density_mg_ha": float(base["carbon_density_mg_ha"]),
        "latest_carbon_density_mg_ha": float(comp["carbon_density_mg_ha"]),
        "carbon_loss_mg_ha": max(
            0.0, float(base["carbon_density_mg_ha"] - comp["carbon_density_mg_ha"])),
        # First year after the baseline in which canopy cover dropped below
        # (baseline - 20%); None if no such year.
        "detected_change_year": _detect_change_year(sub, float(base["canopy_cover_percent"]),
                                                    baseline_year, comparison_year),
        # Share of years with data inside the window -> data completeness.
        "data_completeness_percent": round(
            len(sub.loc[baseline_year:comparison_year]) /
            (comparison_year - baseline_year + 1) * 100.0, 1),
    }
    summary["post_cutoff_change"] = (
        summary["detected_change_year"] is not None
        and summary["detected_change_year"] > EUDR_CUTOFF_YEAR
    )
    return summary


def _detect_change_year(sub: pd.DataFrame, baseline_canopy: float,
                        baseline_year: int, comparison_year: int,
                        drop_fraction: float = 0.2) -> int | None:
    window = sub.loc[baseline_year + 1: comparison_year, "canopy_cover_percent"]
    hits = window[window < baseline_canopy * (1.0 - drop_fraction)]
    return int(hits.index[0]) if len(hits) else None


def detect_change(summary: dict, thresholds: Thresholds) -> dict:
    """Explainable screening rules. Outputs are ALERTS for human review,
    never legal determinations."""
    base_cov = summary["baseline_canopy_cover_percent"]
    latest_cov = summary["latest_canopy_cover_percent"]
    loss_pct = base_cov - latest_cov
    canopy_decline_pct = -summary["canopy_cover_change_percent"]

    was_forest = base_cov >= thresholds.min_baseline_canopy_cover_percent
    lost_forest = latest_cov < thresholds.min_baseline_canopy_cover_percent
    significant_loss = (
        canopy_decline_pct >= thresholds.canopy_cover_loss_threshold_percent
        and loss_pct >= thresholds.minimum_affected_area_percent
    )

    potential_deforestation = bool(
        was_forest and significant_loss and lost_forest)
    # Degradation: material decline but canopy stays above the forest threshold.
    carbon_hit = summary["carbon_loss_mg_ha"] >= thresholds.carbon_loss_threshold_mg_per_ha
    height_hit = summary["canopy_height_change_m"] <= -thresholds.height_loss_threshold_m
    potential_degradation = bool(
        was_forest and not lost_forest
        and (significant_loss or carbon_hit) and (carbon_hit or height_hit))

    alerts = []
    if potential_deforestation:
        alerts.append("potential_deforestation")
    if potential_degradation:
        alerts.append("potential_degradation")
    if not alerts:
        alerts.append("no_alert")

    if potential_deforestation:
        action = "Priority field verification + supplier engagement; request legality evidence."
    elif potential_degradation:
        action = "Remote review of high-resolution imagery; add plot to enhanced monitoring."
    else:
        action = "Routine monitoring cadence."

    return {
        "potential_deforestation": potential_deforestation,
        "potential_degradation": potential_degradation,
        "alert_types": alerts,
        "affected_area_percent": round(max(0.0, loss_pct), 1),
        "confidence": _confidence(canopy=significant_loss, carbon=carbon_hit, height=height_hit),
        "recommended_action": action,
    }


def _confidence(**indicators: bool) -> str:
    n = sum(indicators.values())
    return {3: "high", 2: "medium"}.get(n, "low")


def portfolio_kpis(plots_with_risk: pd.DataFrame) -> dict:
    """High-level KPIs for the executive dashboard."""
    n = len(plots_with_risk)
    return {
        "total_plots": n,
        "total_area_ha": round(float(plots_with_risk["area_ha"].sum()), 1),
        "low_risk": int((plots_with_risk["risk_category"] == "Low").sum()),
        "high_risk": int((plots_with_risk["risk_category"] == "High").sum()),
        "critical_risk": int((plots_with_risk["risk_category"] == "Critical").sum()),
        "post_cutoff_alerts": int(plots_with_risk["post_cutoff_change"].sum()),
        "estimated_carbon_loss_mg": round(
            float(plots_with_risk["carbon_loss_mg_ha"].clip(lower=0).sum()), 1),
        "missing_evidence": int((~plots_with_risk["legality_document_available"]).sum()),
        "mean_data_completeness_percent": round(
            float(plots_with_risk["data_completeness_percent"].mean()), 1) if n else 0.0,
    }

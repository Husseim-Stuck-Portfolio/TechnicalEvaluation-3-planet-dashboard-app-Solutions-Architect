"""Evidence export. Everything needed to audit a screening decision."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .config import APP_NAME, APP_VERSION, EUDR_CUTOFF_DATE


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def build_evidence_report(plot_row: pd.Series, thresholds,
                          risk_breakdown: dict) -> str:
    """Human-readable, timestamped screening report for ONE plot.

    Explicitly labelled as analytical screening evidence - not a regulatory
    declaration and not legal advice.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {APP_NAME} - Plot Screening Evidence Report",
        "",
        "_Analytical screening evidence for internal due-diligence review. "
        "This report is NOT a regulatory declaration, NOT a legal determination, "
        "and does NOT replace human compliance review._",
        "",
        f"- Generated: {now}",
        f"- Application version: {APP_VERSION}",
        f"- EUDR reference cutoff: {EUDR_CUTOFF_DATE}",
        f"- Data source: {plot_row.get('data_source', 'n/a')} "
        f"(product {plot_row.get('product_version', 'n/a')})",
        "",
        "## Plot identification",
        f"- Plot: {plot_row['plot_id']}  |  Supplier: {plot_row['supplier_name']} "
        f"({plot_row['supplier_id']})",
        f"- Commodity: {plot_row['commodity']}  |  Country: {plot_row['country']}",
        f"- Area: {plot_row['area_ha']} ha",
        f"- Legality document on file: {bool(plot_row['legality_document_available'])}",
        "",
        "## Analysis window",
        f"- Baseline year: {plot_row['baseline_year']}   "
        f"Comparison year: {plot_row['comparison_year']}",
        "",
        "## Observed indicators",
        f"- Canopy cover: {plot_row['baseline_canopy_cover_percent']}% -> "
        f"{plot_row['latest_canopy_cover_percent']}% "
        f"({plot_row['canopy_cover_change_percent']:+.1f}%)",
        f"- Canopy height: {plot_row['baseline_canopy_height_m']} m -> "
        f"{plot_row['latest_canopy_height_m']} m",
        f"- Carbon density: {plot_row['baseline_carbon_density_mg_ha']} -> "
        f"{plot_row['latest_carbon_density_mg_ha']} Mg/ha "
        f"(loss {plot_row['carbon_loss_mg_ha']} Mg/ha)",
        f"- Detected change year: {plot_row.get('detected_change_year')}",
        f"- Post-cutoff change: {bool(plot_row.get('post_cutoff_change'))}",
        "",
        "## Screening result",
        f"- Alert type(s): {plot_row.get('alert_types', 'n/a')}",
        f"- Risk score: {plot_row['risk_score']} / 100 ({plot_row['risk_category']})",
        f"- Confidence: {plot_row.get('confidence', 'n/a')}",
        f"- Recommended action: {plot_row.get('recommended_action', 'n/a')}",
        "",
        "## Risk score derivation",
        "| Component | Weight | Raw value | Contribution |",
        "|---|---|---|---|",
    ]
    for name, contrib in risk_breakdown.items():
        lines.append(f"| {name} | - | - | {contrib} |")
    lines += [
        "",
        "## Thresholds applied",
        f"- Min baseline canopy cover: {thresholds.min_baseline_canopy_cover_percent}%",
        f"- Canopy loss threshold: {thresholds.canopy_cover_loss_threshold_percent}%",
        f"- Min affected area: {thresholds.minimum_affected_area_percent}%",
        f"- Carbon loss threshold: {thresholds.carbon_loss_threshold_mg_per_ha} Mg/ha",
        "",
        "## Limitations",
        "- Forest Carbon Diligence is annual at ~30 m; Forest Carbon Monitoring "
        "is quarterly at 3 m. Synthetic demo data was used for this report.",
        "- Detected changes are alerts for investigation, not proof of "
        "illegal deforestation.",
    ]
    return "\n".join(lines)

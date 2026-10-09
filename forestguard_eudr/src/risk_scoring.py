"""Transparent, explainable risk scoring (0-100).

Design rules:
- every component is normalised to 0-100 before weighting;
- every contribution is recorded so the UI can show its derivation;
- regional context and evidence gaps come from supplier data, not imagery;
- the formula is deterministic and unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import RISK_CATEGORIES, RISK_WEIGHTS, COUNTRY_CONTEXT_RISK, Thresholds


@dataclass
class RiskComponent:
    name: str
    weight: float          # percent, from RISK_WEIGHTS
    raw_value: float       # unnormalised input
    normalised: float      # 0-100
    contribution: float    # weight * normalised / 100


@dataclass
class RiskScore:
    total: float
    category: str
    is_alert: bool
    components: list[RiskComponent] = field(default_factory=list)

    def breakdown(self) -> dict[str, float]:
        return {c.name: round(c.contribution, 2) for c in self.components}


def _scale(decline: float, reference: float) -> float:
    """Map a decline onto 0-100 with a configurable full-risk reference."""
    if reference <= 0:
        raise ValueError("reference decline must be positive")
    return max(0.0, min(100.0, decline / reference * 100.0))


def categorize(score: float) -> str:
    lo = int(score)
    for lower, upper, label in RISK_CATEGORIES:
        if lower <= lo <= upper:
            return label
    return "Critical" if score >= 75 else "Low"


def compute_risk_score(summary: dict, change: dict, plot_row: dict,
                       thresholds: Thresholds | None = None) -> RiskScore:
    """Combine plot metrics, change detection and supplier evidence into a
    single, fully explained risk score."""
    th = thresholds or Thresholds()
    canopy_decline_pct = max(0.0, -summary["canopy_cover_change_percent"])

    # Post-cutoff gate: declines detected entirely before the EUDR cutoff do
    # not count fully toward the imagery-driven components (context only).
    post_cutoff = bool(summary.get("post_cutoff_change", False))
    gate = 1.0 if post_cutoff else 0.25

    country = str(plot_row.get("country", "default")).strip()
    context = COUNTRY_CONTEXT_RISK.get(country, COUNTRY_CONTEXT_RISK["default"])
    has_docs = bool(plot_row.get("legality_document_available"))

    raw = {
        "post_cutoff_canopy_loss": canopy_decline_pct,
        "carbon_decline": summary["carbon_loss_mg_ha"],
        "height_decline": max(0.0, -summary["canopy_height_change_m"]),
        "affected_area": change["affected_area_percent"],
        "regional_context": context,
        "missing_evidence": 0.0 if has_docs else 1.0,
    }
    refs = {
        "post_cutoff_canopy_loss": th.reference_canopy_loss_percent,
        "carbon_decline": th.reference_carbon_loss_mg_ha,
        "height_decline": th.reference_height_loss_m,
        "affected_area": 50.0,
        "regional_context": 100.0,   # already on a 0-100 context scale
        "missing_evidence": 1.0,     # binary
    }
    comps = []
    for name, weight in RISK_WEIGHTS.items():
        is_imagery = name in {"post_cutoff_canopy_loss", "carbon_decline",
                              "height_decline", "affected_area"}
        norm = _scale(raw[name], refs[name]) * (gate if is_imagery else 1.0)
        comps.append(RiskComponent(name, weight, round(raw[name], 2),
                                   round(norm, 2), round(weight * norm / 100.0, 3)))

    total = round(sum(c.contribution for c in comps), 1)
    return RiskScore(total=total, category=categorize(total),
                     is_alert=total >= th.risk_score_alert_threshold,
                     components=comps)

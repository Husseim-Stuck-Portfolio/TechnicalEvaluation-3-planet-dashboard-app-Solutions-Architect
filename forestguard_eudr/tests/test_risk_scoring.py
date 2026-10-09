import pytest

from src.config import RISK_WEIGHTS, Thresholds
from src.risk_scoring import _scale, categorize, compute_risk_score

TH = Thresholds()


def _summary(**over):
    base = {
        "canopy_cover_change_percent": -10.0,
        "carbon_loss_mg_ha": 10.0,
        "canopy_height_change_m": -2.0,
        "post_cutoff_change": True,
    }
    base.update(over)
    return base


def _change(**over):
    base = {"affected_area_percent": 10.0}
    base.update(over)
    return base


def _plot(**over):
    base = {"country": "Brazil", "legality_document_available": True}
    base.update(over)
    return base


def test_weights_sum_to_100():
    assert sum(RISK_WEIGHTS.values()) == pytest.approx(100.0)


def test_scale_bounds():
    assert _scale(-5, 50) == 0.0
    assert _scale(25, 50) == 50.0
    assert _scale(500, 50) == 100.0
    with pytest.raises(ValueError):
        _scale(10, 0)


def test_category_boundaries():
    assert categorize(0) == "Low"
    assert categorize(24.9) == "Low"
    assert categorize(25) == "Moderate"
    assert categorize(49.9) == "Moderate"
    assert categorize(50) == "High"
    assert categorize(74.9) == "High"
    assert categorize(75) == "Critical"
    assert categorize(100) == "Critical"


def test_missing_docs_adds_10_points():
    ok = compute_risk_score(_summary(), _change(), _plot())
    missing = compute_risk_score(_summary(), _change(), _plot(legality_document_available=False))
    assert missing.total - ok.total == pytest.approx(10.0, abs=0.2)


def test_post_cutoff_gate_reduces_imagery_components():
    post = compute_risk_score(_summary(), _change(), _plot())
    pre = compute_risk_score(_summary(post_cutoff_change=False), _change(), _plot())
    assert post.total > pre.total


def test_alert_threshold():
    big = compute_risk_score(
        _summary(canopy_cover_change_percent=-80, carbon_loss_mg_ha=150,
                 canopy_height_change_m=-20),
        _change(affected_area_percent=60), _plot(legality_document_available=False))
    assert big.is_alert is True
    assert big.category in {"High", "Critical"}


def test_breakdown_sums_to_total():
    s = compute_risk_score(_summary(), _change(), _plot())
    assert sum(s.breakdown().values()) == pytest.approx(s.total, abs=0.2)

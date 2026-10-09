import pandas as pd
import pytest

from src.config import Thresholds
from src.metrics import detect_change, pct_change, summarize_plot
from src.validation import check_year_order

TH = Thresholds()


def _meas(plot_id, canopy, height, carbon):
    years = list(range(2015, 2015 + len(canopy)))
    return pd.DataFrame({
        "plot_id": plot_id, "year": years,
        "canopy_cover_percent": canopy,
        "canopy_height_m": height,
        "carbon_density_mg_ha": carbon,
        "data_source": "test", "product_version": "t", "data_quality_flag": "ok",
    })


def test_pct_change_basic():
    assert pct_change(100, 80) == pytest.approx(-20.0)
    assert pct_change(0, 50) == 0.0


def test_year_order_enforced():
    with pytest.raises(ValueError):
        check_year_order(2020, 2019)


def test_post_cutoff_clearing_detected():
    canopy = [80, 80, 81, 79, 80, 82, 30, 12, 10]
    m = _meas("P1", canopy, [30] * 9, [200] * 9)
    s = summarize_plot(m, "P1", 2015, 2023)
    assert s["post_cutoff_change"] is True
    assert s["detected_change_year"] == 2021
    c = detect_change(s, TH)
    assert c["potential_deforestation"] is True
    assert not c["potential_degradation"]


def test_pre_cutoff_change_not_post_cutoff_flagged():
    canopy = [80, 80, 30, 20, 20, 20, 20, 20, 20]
    m = _meas("P2", canopy, [30] * 9, [200] * 9)
    s = summarize_plot(m, "P2", 2015, 2023)
    assert s["post_cutoff_change"] is False
    assert s["detected_change_year"] == 2017


def test_agriculture_never_flagged_as_deforestation():
    canopy = [10, 11, 10, 12, 9, 10, 11, 10, 10]
    m = _meas("P3", canopy, [3] * 9, [15] * 9)
    s = summarize_plot(m, "P3", 2015, 2023)
    c = detect_change(s, TH)
    assert not c["potential_deforestation"]


def test_gradual_degradation_flagged():
    canopy = [75, 74, 72, 70, 66, 60, 55, 50, 48]
    height = [28, 28, 27, 26, 25, 23, 21, 20, 19]
    carbon = [180, 178, 172, 165, 155, 140, 125, 110, 100]
    m = _meas("P4", canopy, height, carbon)
    s = summarize_plot(m, "P4", 2015, 2023)
    c = detect_change(s, TH)
    assert c["potential_degradation"] is True
    assert not c["potential_deforestation"]


def test_missing_measurement_raises():
    m = _meas("P5", [50] * 9, [20] * 9, [100] * 9)
    with pytest.raises(ValueError):
        summarize_plot(m, "P5", 2014, 2023)
